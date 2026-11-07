"""LLM main path for T12 task decomposition.

``RuleEngine`` stays the guaranteed offline path: this module only replaces
the *decomposition* step. Daily packing, breaks and consistency checks still
run through :mod:`planner.scheduler` and :mod:`planner.validator`, so a model
reply that ignores the caps can never turn into an overlapping or overdue
plan on the screen.

Design notes
------------
* No new dependency: the HTTP call uses ``urllib.request`` (same approach as
  :mod:`voice.asr`), which keeps the Raspberry Pi image small.
* Every reply is normalised against the product rules (3-7 steps, 15-45
  minutes per step, first step <= 20 minutes, verb-first titles). A reply
  that cannot be repaired falls back to the rule engine instead of being
  shown to the user.
* Replies are cached for 24 hours on disk, keyed by the task text and the
  active caps, so re-planning the same backlog costs at most one call.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from planner.engine import RuleEngine
from planner.estimator import HistoryProvider, estimate_minutes
from planner.models import PlanDraft, Prefs, SubTask, Task, make_plan_id
from planner.rules import max_decomposable_minutes
from planner.scheduler import build_plan
from planner.validator import ValidationResult, is_verb_first, validate_plan

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT_S = 8.0
DEFAULT_CACHE_TTL_S = 24 * 60 * 60

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}

# The validator's whitelist is deliberately narrow (it also scores the rule
# engine's own templates). Model output is livelier, so the LLM path matches
# against a wider prefix set and strips common leading adverbs first.
_EXTRA_VERB_PREFIXES = (
    "找出", "算出", "翻到", "翻到", "补写", "浏览", "列出", "查到",
    "标出", "记下", "抄下", "摘录", "朗读", "试做", "试着", "勾选",
    "核对", "梳理", "背诵", "概括", "提炼", "归纳", "修订", "校对",
)
_ADVERB_PREFIXES = (
    "快速", "仔细", "认真", "简单", "先", "再", "接着", "然后",
    "首先", "其次", "尝试", "尝试着", "试着",
)


def _verb_first_lenient(title: str) -> bool:
    """Accept lively model titles; still reject preposition-opened ones."""
    text = (title or "").strip()
    for adverb in _ADVERB_PREFIXES:
        if text.startswith(adverb):
            text = text[len(adverb):].lstrip("，,、 ")
    if not text:
        return False
    if is_verb_first(text):
        return True
    return text.startswith(_EXTRA_VERB_PREFIXES)

SYSTEM_PROMPT = (
    "你是「心流 Flow」的拆解助手，服务对象是容易因为任务积压而焦虑的学生。"
    "你只做一件事：把一件任务拆成可以立刻动手的小步骤。"
    "回答必须是严格合法的 JSON，不要输出解释、不要输出 markdown 代码块。"
)

_STEP_RULES = (
    "拆解要求：\n"
    "1. 拆成 {min_steps}-{max_steps} 步，按执行顺序排列；\n"
    "2. 每一步以动词开头（例如 打开/列出/写出/整理/读/算/做/检查）；\n"
    "3. 标题禁止用「为、把、将、给、用、通过、按照、根据、需要」这类介词或"
    "助词开头——不要写「为每个观点找例子」，要写「找出每个观点的例子」；\n"
    "4. 每一步都能独立完成，并且有可判断的完成标准；\n"
    "5. 单步 {min_step}-{max_step} 分钟，第一步不超过 {max_first} 分钟；\n"
    "6. 第一步要小到「现在就能开始」，不要写成「完成整篇论文」这种大块。"
)

_SINGLE_SCHEMA_HINT = (
    '只输出这样的 JSON：{{"steps":[{{"title":"打开文档，列出 3 个核心论点",'
    '"est_minutes":20,"completion_criteria":"文档里有 3 条论点",'
    '"difficulty":1}}]}}'
)

_BATCH_SCHEMA_HINT = (
    '只输出这样的 JSON：{{"tasks":[{{"task_id":"t1","steps":[{{"title":"...",'
    '"est_minutes":20,"completion_criteria":"...","difficulty":1}}]}}]}}'
)


class LlmError(RuntimeError):
    """Raised when the provider answers with something unusable."""


@dataclass(frozen=True)
class LlmSettings:
    """Non-secret knobs live in ``config.yaml``; the key comes from ``.env``."""

    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout_s: float = DEFAULT_TIMEOUT_S
    cache_ttl_s: int = DEFAULT_CACHE_TTL_S
    temperature: float = 0.2
    enabled: bool = True

    @property
    def available(self) -> bool:
        """The LLM path is on only when it is enabled *and* has a key."""
        return bool(self.enabled and self.api_key.strip())

    @property
    def endpoint(self) -> str:
        base = (self.base_url or DEFAULT_BASE_URL).rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"


def settings_from_env(
    env: Mapping[str, str] | None = None,
    *,
    base_url: str | None = None,
    model: str | None = None,
    timeout_s: float | None = None,
    cache_ttl_s: int | None = None,
    temperature: float | None = None,
    enabled: bool | None = None,
) -> LlmSettings:
    """Build settings from ``config.yaml`` defaults plus ``DEEPSEEK_API_KEY``.

    ``.env.example`` already ships ``DEEPSEEK_API_KEY``; ``FLOW_LLM_*``
    overrides exist for bench runs against Qwen or a local gateway.
    """

    values = os.environ if env is None else env
    key = (
        values.get("FLOW_LLM_API_KEY")
        or values.get("DEEPSEEK_API_KEY")
        or values.get("QWEN_API_KEY")
        or values.get("DASHSCOPE_API_KEY")
        or ""
    ).strip()
    return LlmSettings(
        api_key=key,
        base_url=str(values.get("FLOW_LLM_BASE_URL") or base_url or DEFAULT_BASE_URL),
        model=str(values.get("FLOW_LLM_MODEL") or model or DEFAULT_MODEL),
        timeout_s=_coerce_float(
            values.get("FLOW_LLM_TIMEOUT_S"),
            DEFAULT_TIMEOUT_S if timeout_s is None else timeout_s,
        ),
        cache_ttl_s=_coerce_int(
            values.get("FLOW_LLM_CACHE_TTL_S"),
            DEFAULT_CACHE_TTL_S if cache_ttl_s is None else cache_ttl_s,
        ),
        temperature=_coerce_float(
            values.get("FLOW_LLM_TEMPERATURE"),
            0.2 if temperature is None else temperature,
        ),
        enabled=_coerce_bool(values.get("FLOW_LLM_ENABLED"), enabled),
    )


class ChatClient(Protocol):
    """Minimal surface so tests can inject a scripted provider."""

    def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        timeout_s: float | None = None,
    ) -> str: ...


class OpenAiCompatibleClient:
    """``POST /chat/completions`` client used by DeepSeek / Qwen."""

    name = "openai-compatible"

    def __init__(
        self,
        settings: LlmSettings,
        *,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.settings = settings
        self._opener = opener or urllib.request.urlopen
        self.calls = 0

    def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        timeout_s: float | None = None,
    ) -> str:
        payload = {
            "model": self.settings.model,
            "messages": list(messages),
            "temperature": self.settings.temperature,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.settings.endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.api_key}",
            },
            method="POST",
        )
        self.calls += 1
        timeout = timeout_s or self.settings.timeout_s
        try:
            with self._opener(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            raise LlmError(f"provider returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LlmError(f"provider unreachable: {exc}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LlmError("provider returned non-JSON envelope") from exc
        choices = data.get("choices") or []
        if not choices:
            raise LlmError("provider returned no choices")
        message = choices[0].get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise LlmError("provider returned empty content")
        return content


class DecomposeCache:
    """Small on-disk TTL cache: same task text reuses the reply for 24h."""

    VERSION = 1

    def __init__(
        self,
        path: str | Path | None = None,
        ttl_s: int = DEFAULT_CACHE_TTL_S,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = Path(path) if path else None
        self.ttl_s = int(ttl_s)
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def get(self, key: str) -> list[dict[str, Any]] | None:
        if self.ttl_s <= 0:
            return None
        with self._lock:
            self._load_locked()
            entry = self._entries.get(key)
            if entry is None:
                return None
            if self._clock() - float(entry.get("at", 0)) > self.ttl_s:
                self._entries.pop(key, None)
                return None
            steps = entry.get("steps")
            return list(steps) if isinstance(steps, list) else None

    def put(self, key: str, steps: list[dict[str, Any]]) -> None:
        if self.ttl_s <= 0:
            return
        with self._lock:
            self._load_locked()
            self._entries[key] = {"at": self._clock(), "steps": steps}
            self._prune_locked()
            self._write_locked()

    # -- internals ---------------------------------------------------
    def _load_locked(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if self.path is None or not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("llm cache unreadable, starting empty: %s", self.path)
            return
        entries = raw.get("entries") if isinstance(raw, dict) else None
        if isinstance(entries, dict):
            for key, entry in entries.items():
                if isinstance(entry, dict) and isinstance(entry.get("steps"), list):
                    self._entries[str(key)] = entry

    def _prune_locked(self) -> None:
        now = self._clock()
        expired = [
            key
            for key, entry in self._entries.items()
            if now - float(entry.get("at", 0)) > self.ttl_s
        ]
        for key in expired:
            self._entries.pop(key, None)

    def _write_locked(self) -> None:
        if self.path is None:
            return
        payload = {"version": self.VERSION, "entries": self._entries}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(self.path)
        except OSError:
            logger.warning("could not persist llm cache: %s", self.path)


class LlmEngine:
    """``decompose``/``plan`` with the same contract as :class:`RuleEngine`."""

    def __init__(
        self,
        prefs: Prefs | None = None,
        history: HistoryProvider | None = None,
        *,
        settings: LlmSettings | None = None,
        client: ChatClient | None = None,
        cache: DecomposeCache | None = None,
        cache_path: str | Path | None = None,
        fallback: RuleEngine | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.prefs = prefs or Prefs()
        self.history = history
        self.settings = settings or settings_from_env()
        self.fallback = fallback or RuleEngine(self.prefs, history)
        self.client = client or (
            OpenAiCompatibleClient(self.settings)
            if self.settings.available
            else None
        )
        self.cache = cache or DecomposeCache(
            cache_path,
            self.settings.cache_ttl_s,
            clock=clock,
        )
        self.last_validation: ValidationResult | None = None
        self.last_mode = "rule"
        self.last_error = ""

    # -- contract ----------------------------------------------------
    @property
    def usable(self) -> bool:
        return self.client is not None and self.settings.available

    def decompose(
        self,
        task: Task,
        prefs: Prefs | None = None,
    ) -> list[SubTask]:
        active = prefs or self.prefs
        return self._decompose_many([task], active)[task.id]

    def plan(
        self,
        plan_date: date,
        tasks: list[Task],
        prefs: Prefs | None = None,
    ) -> PlanDraft:
        """Decompose with the model, then pack with the deterministic planner."""
        active = prefs or self.prefs
        self.last_error = ""
        pending = [
            task
            for task in tasks
            if not task.completed and not task.subtasks
        ]
        decomposed = self._decompose_many(pending, active) if pending else {}

        prepared: list[Task] = []
        capped: list[tuple[Task, int]] = []
        for task in tasks:
            if task.completed or task.subtasks:
                prepared.append(task)
                continue
            steps = decomposed.get(task.id)
            if not steps:
                steps = self.fallback.decompose(task, active)
            estimate = estimate_minutes(task, self.history)
            if estimate > max_decomposable_minutes(active):
                capped.append((task, estimate))
            prepared.append(replace(task, subtasks=steps))

        mode = "llm" if self._used_llm(prepared) else "rule"
        try:
            draft = build_plan(plan_date, prepared, active, mode=mode)
        except Exception as exc:  # pragma: no cover - safety net
            logger.exception("llm planner failed")
            draft = PlanDraft(
                plan_id=make_plan_id(plan_date),
                date=plan_date.isoformat(),
                warnings=[f"规划失败，已返回空计划：{exc}"],
                mode="rule",
            )
            mode = "rule"
        for task, estimate in capped:
            draft.warnings.append(
                f"《{task.title}》预计 {estimate} 分钟，超过单日拆解上限，"
                "已压缩为可执行的前几步"
            )
        if self.last_error:
            if mode == "llm":
                draft.warnings.append(
                    "部分任务的 AI 拆解不可用，已用内置规则补齐"
                )
            else:
                draft.warnings.append(
                    "AI 拆解暂时不可用，已用内置规则完成这次规划"
                )

        self.last_validation = validate_plan(
            draft,
            prepared,
            active,
            plan_date=plan_date,
        )
        if not self.last_validation.ok:
            for issue in self.last_validation.errors:
                draft.warnings.append(f"内部校验未通过：{issue.message}")
        self.last_mode = mode
        return draft

    def validate(
        self,
        plan: PlanDraft,
        tasks: list[Task],
        prefs: Prefs | None = None,
    ) -> ValidationResult:
        return validate_plan(
            plan,
            tasks,
            prefs or self.prefs,
            plan_date=date.fromisoformat(plan.date),
        )

    # -- decomposition -----------------------------------------------
    def _decompose_many(
        self,
        tasks: list[Task],
        prefs: Prefs,
    ) -> dict[str, list[SubTask]]:
        result: dict[str, list[SubTask]] = {}
        pending: list[Task] = []
        for task in tasks:
            if task.subtasks:
                result[task.id] = list(task.subtasks)
                continue
            cached = self._cached_steps(task, prefs)
            if cached is not None:
                result[task.id] = cached
                continue
            pending.append(task)

        if not pending:
            return result

        if not self.usable:
            for task in pending:
                result[task.id] = self.fallback.decompose(task, prefs)
            return result

        try:
            replies = self._request(pending, prefs)
        except LlmError as exc:
            self.last_error = str(exc)
            logger.warning("llm decompose fell back to rules: %s", exc)
            for task in pending:
                result[task.id] = self.fallback.decompose(task, prefs)
            return result

        for task in pending:
            raw_steps = replies.get(task.id)
            steps = _normalise_steps(task, raw_steps, prefs)
            if steps is None:
                self.last_error = "model reply did not satisfy the step rules"
                logger.warning(
                    "llm reply rejected for task %s, using rules", task.id
                )
                result[task.id] = self.fallback.decompose(task, prefs)
                continue
            self.cache.put(self._cache_key(task, prefs), _steps_to_json(steps))
            result[task.id] = steps
        return result

    def _request(
        self,
        tasks: list[Task],
        prefs: Prefs,
    ) -> dict[str, list[dict[str, Any]]]:
        assert self.client is not None  # guarded by ``usable``
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _batch_prompt(tasks, prefs),
            },
        ]
        content = self.client.complete(messages, timeout_s=self.settings.timeout_s)
        payload = _loads_json(content)
        return _pick_task_steps(payload, tasks)

    # -- helpers -----------------------------------------------------
    def _cached_steps(
        self,
        task: Task,
        prefs: Prefs,
    ) -> list[SubTask] | None:
        if not self.usable:
            return None
        raw = self.cache.get(self._cache_key(task, prefs))
        if not raw:
            return None
        return _normalise_steps(task, raw, prefs)

    def _cache_key(self, task: Task, prefs: Prefs) -> str:
        material = "|".join(
            [
                task.title.strip(),
                task.description.strip(),
                task.category.value if task.category else "",
                str(prefs.min_steps),
                str(prefs.max_steps),
                str(prefs.min_step_minutes),
                str(prefs.max_step_minutes),
                str(prefs.max_first_step_minutes),
                self.settings.model,
            ]
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def _used_llm(prepared: list[Task]) -> bool:
        return any(
            subtask.source == "llm"
            for task in prepared
            for subtask in task.subtasks
        )


def default_engine(
    *,
    settings: LlmSettings | None = None,
    cache_path: str | Path | None = None,
    history: HistoryProvider | None = None,
    env: Mapping[str, str] | None = None,
) -> RuleEngine | LlmEngine:
    """Return the LLM path when a key exists, otherwise the offline path."""
    resolved = settings or settings_from_env(env)
    if not resolved.available:
        return RuleEngine(history=history)
    return LlmEngine(
        history=history,
        settings=resolved,
        cache_path=cache_path,
    )


# -- prompt construction ---------------------------------------------
def _rule_block(prefs: Prefs) -> str:
    return _STEP_RULES.format(
        min_steps=prefs.min_steps,
        max_steps=prefs.max_steps,
        min_step=prefs.min_step_minutes,
        max_step=prefs.max_step_minutes,
        max_first=prefs.max_first_step_minutes,
    )


def _batch_prompt(tasks: list[Task], prefs: Prefs) -> str:
    lines = ["请把下面这些任务各自拆解成小步骤。"]
    for task in tasks:
        detail = f"（{task.description.strip()}）" if task.description.strip() else ""
        category = task.category.value if task.category else "未分类"
        lines.append(f"- task_id={task.id}；标题={task.title}{detail}；类别={category}")
    lines.append("")
    lines.append(_rule_block(prefs))
    lines.append("")
    lines.append(_BATCH_SCHEMA_HINT)
    return "\n".join(lines)


def single_prompt(task: Task, prefs: Prefs) -> str:
    """Exposed for the offline ``python -m planner`` debug entry point."""
    lines = [f"任务：{task.title}"]
    if task.description.strip():
        lines.append(f"补充说明：{task.description.strip()}")
    lines.append(f"类别：{task.category.value if task.category else '未分类'}")
    lines.append("")
    lines.append(_rule_block(prefs))
    lines.append("")
    lines.append(_SINGLE_SCHEMA_HINT)
    return "\n".join(lines)


# -- reply parsing ----------------------------------------------------
def _loads_json(content: str) -> Any:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LlmError("model reply is not JSON") from exc


def _pick_task_steps(
    payload: Any,
    tasks: list[Task],
) -> dict[str, list[dict[str, Any]]]:
    """Accept ``{"tasks": [...]}``, a bare list, or a single ``{"steps": ...}``."""
    wanted = [task.id for task in tasks]
    if isinstance(payload, dict) and isinstance(payload.get("steps"), list):
        if len(tasks) != 1:
            raise LlmError("single-task reply for a batch request")
        return {wanted[0]: list(payload["steps"])}
    if isinstance(payload, dict):
        rows = payload.get("tasks")
    else:
        rows = payload
    if not isinstance(rows, list):
        raise LlmError("model reply is missing the tasks array")

    replies: dict[str, list[dict[str, Any]]] = {}
    unmatched: list[list[dict[str, Any]]] = []
    by_title = {task.title.strip(): task.id for task in tasks}
    for row in rows:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("task_id") or "").strip()
        if task_id not in wanted:
            title = str(row.get("title") or "").strip()
            task_id = by_title.get(title, "")
        steps = row.get("steps") if isinstance(row.get("steps"), list) else []
        steps = [step for step in steps if isinstance(step, dict)]
        if task_id in wanted:
            replies[task_id] = steps
        elif steps:
            unmatched.append(steps)
    # Models sometimes invent their own task ids; with a single task there
    # is only one sensible assignment, so take it instead of falling back.
    if len(tasks) == 1 and wanted[0] not in replies and unmatched:
        replies[wanted[0]] = unmatched[0]
    return replies


def _normalise_steps(
    task: Task,
    raw_steps: list[dict[str, Any]] | None,
    prefs: Prefs,
) -> list[SubTask] | None:
    """Clamp the reply to the product rules; ``None`` means "use the rules"."""
    if not raw_steps:
        return None
    cleaned: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_steps, start=1):
        title = str(raw.get("title") or raw.get("name") or "").strip()
        if not title:
            continue
        if not _verb_first_lenient(title):
            # One weak title must not sink the whole decomposition; drop the
            # step and keep the rest if there are still enough of them.
            logger.warning(
                "dropping non verb-first step for %s: %r",
                task.id,
                title[:24],
            )
            continue
        minutes = _coerce_int(raw.get("est_minutes"), 0)
        if minutes <= 0:
            minutes = prefs.min_step_minutes
        criteria = str(
            raw.get("completion_criteria") or raw.get("criteria") or ""
        ).strip()
        difficulty = _coerce_int(raw.get("difficulty"), 2)
        cleaned.append(
            {
                "title": title,
                "est_minutes": minutes,
                "completion_criteria": criteria,
                "difficulty": difficulty,
                "order": index,
            }
        )
    if len(cleaned) < prefs.min_steps:
        return None
    if len(cleaned) > prefs.max_steps:
        cleaned = _merge_excess(cleaned, prefs)
    for position, step in enumerate(cleaned):
        cap = (
            prefs.max_first_step_minutes
            if position == 0
            else prefs.max_step_minutes
        )
        step["est_minutes"] = max(
            prefs.min_step_minutes,
            min(cap, int(step["est_minutes"])),
        )
        step["difficulty"] = max(1, min(3, int(step["difficulty"])))
    return _build_subtasks(task, cleaned)


def _merge_excess(
    steps: list[dict[str, Any]],
    prefs: Prefs,
) -> list[dict[str, Any]]:
    """Card rule: more than 7 steps is merged instead of dropped."""
    head = steps[: prefs.max_steps]
    last = dict(head[-1])
    for extra in steps[prefs.max_steps :]:
        last["est_minutes"] = int(last["est_minutes"]) + int(
            extra["est_minutes"]
        )
        extra_criteria = str(extra.get("completion_criteria") or "").strip()
        if extra_criteria:
            joined = "；".join(
                part
                for part in (
                    str(last.get("completion_criteria") or "").strip(),
                    extra_criteria,
                )
                if part
            )
            last["completion_criteria"] = joined
    head[-1] = last
    return head


def _build_subtasks(task: Task, steps: list[dict[str, Any]]) -> list[SubTask]:
    subtasks: list[SubTask] = []
    for position, step in enumerate(steps, start=1):
        subtasks.append(
            SubTask(
                id=f"{task.id}_s{position}",
                task_id=task.id,
                title=str(step["title"]),
                est_minutes=int(step["est_minutes"]),
                completion_criteria=str(step.get("completion_criteria") or ""),
                order=position,
                difficulty=max(1, min(3, int(step.get("difficulty", 2)))),
                source="llm",
            )
        )
    return subtasks


def _steps_to_json(steps: list[SubTask]) -> list[dict[str, Any]]:
    return [
        {
            "title": step.title,
            "est_minutes": step.est_minutes,
            "completion_criteria": step.completion_criteria,
            "difficulty": step.difficulty,
            "order": step.order,
        }
        for step in steps
    ]


# -- coercion helpers -------------------------------------------------
def _coerce_int(value: Any, default: int) -> int:
    if value is None or isinstance(value, bool):
        return default
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        return float(default)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return float(default)


def _coerce_bool(value: Any, default: bool | None) -> bool:
    if value is None or str(value).strip() == "":
        return True if default is None else bool(default)
    text = str(value).strip().lower()
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    return True if default is None else bool(default)
