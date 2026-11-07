"""REST routes and uniform error handling."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from service.logging import get_trace_id

logger = logging.getLogger(__name__)

router = APIRouter()

_PLACEHOLDER = Path(__file__).with_name("placeholder.html")


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def error_payload(code: str, message: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "trace_id": get_trace_id(),
        }
    }


@router.get("/healthz")
def healthz(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise ApiError(
            "not_ready",
            "service runtime is not initialized",
            503,
        )
    return runtime.health_payload()


@router.get("/api/system/status")
def system_status(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise ApiError(
            "not_ready",
            "service runtime is not initialized",
            503,
        )
    return runtime.snapshot()


class IntentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    source: str = Field(default="voice", max_length=20)


class PhoneManualRequest(BaseModel):
    present: bool
    charging: bool = False
    current_ma: int = Field(default=0, ge=0)


class PhoneSessionRequest(BaseModel):
    purpose: str = Field(default="leisure", pattern="^(study|leisure)$")
    minutes: int | None = Field(default=None, ge=1, le=180)


class PhoneExtendRequest(BaseModel):
    minutes: int = Field(default=5, ge=1, le=15)


class ReminderRequest(BaseModel):
    text: str | None = Field(default=None, max_length=300)
    kind: str = Field(default="at", max_length=20)
    at: str = Field(default="", max_length=40)
    minutes: int = Field(default=0, ge=0)
    weekday: int = Field(default=-1, ge=-1, le=6)
    on: str = Field(default="", max_length=60)
    template: str = Field(default="", max_length=300)
    allow_quiet: bool = False


class SayRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    emotion: str = Field(default="neutral", max_length=20)
    priority: str = Field(default="normal", max_length=20)


class CaptureTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    source: str = Field(default="text", max_length=20)


class CaptureCommitRequest(BaseModel):
    drafts: list[dict[str, Any]] = Field(default_factory=list)


class PlanCreateRequest(BaseModel):
    day: str | None = Field(default=None, max_length=10)
    task_ids: list[str] = Field(default_factory=list)


class PlanReviseRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=500)


class FocusControlRequest(BaseModel):
    action: str = Field(min_length=1, max_length=20)
    minutes: int | None = Field(default=None, ge=1, le=60)


class ReplanRequest(BaseModel):
    reason: str = Field(default="delay", max_length=20)


class DialogueRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    source: str = Field(default="voice", max_length=20)
    execute: bool = True


class DistractionRequest(BaseModel):
    minutes: int = Field(default=0, ge=0, le=600)
    purpose: str = Field(default="unknown", max_length=30)
    context: str = Field(default="", max_length=100)
    source: str = Field(default="voice", max_length=20)


class RestAckRequest(BaseModel):
    hours: float = Field(default=2.0, ge=0.1, le=24)


class UserCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    nickname: str = Field(default="", max_length=80)
    role: str = Field(default="member", pattern="^(admin|member)$")


class PrefsUpdateRequest(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class UsageIngestRequest(BaseModel):
    packages: dict[str, int] = Field(default_factory=dict)


class UsageToggleRequest(BaseModel):
    enabled: bool


class CelebrateRequest(BaseModel):
    kind: str = Field(default="step_done", max_length=20)


@router.get("/api/companion")
def get_companion(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.companion is None:
        raise ApiError("not_ready", "companion not ready", 503)
    return runtime.companion.state()


@router.post("/api/celebrate")
def celebrate(
    body: CelebrateRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.celebrate is None:
        raise ApiError("not_ready", "celebration not ready", 503)
    return runtime.celebrate.celebrate(body.kind)


@router.get("/api/phone/usage")
def get_phone_usage(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.usage is None:
        raise ApiError("not_ready", "usage service not ready", 503)
    return runtime.usage.status()


@router.post("/api/phone/usage")
def ingest_phone_usage(
    body: UsageIngestRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.usage is None:
        raise ApiError("not_ready", "usage service not ready", 503)
    return runtime.usage.ingest(body.packages)


@router.post("/api/phone/usage/toggle")
def toggle_phone_usage(
    body: UsageToggleRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.usage is None:
        raise ApiError("not_ready", "usage service not ready", 503)
    return runtime.usage.set_enabled(body.enabled)


@router.get("/api/users")
def list_users(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.users is None:
        raise ApiError("not_ready", "users not ready", 503)
    return {
        "items": runtime.users.list(),
        "active": runtime.users.active_user_id,
    }


@router.post("/api/users")
def create_user(
    body: UserCreateRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.users is None:
        raise ApiError("not_ready", "users not ready", 503)
    return runtime.users.create(
        body.name,
        nickname=body.nickname,
        role=body.role,
    )


@router.post("/api/users/{user_id}/switch")
def switch_user(user_id: str, request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.users is None:
        raise ApiError("not_ready", "users not ready", 503)
    return runtime.switch_user(user_id)


@router.get("/api/users/{user_id}/export")
def export_user(user_id: str, request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.users is None:
        raise ApiError("not_ready", "users not ready", 503)
    return runtime.users.export(user_id)


@router.delete("/api/users/{user_id}")
def delete_user(
    user_id: str,
    request: Request,
    confirm: bool = False,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.users is None:
        raise ApiError("not_ready", "users not ready", 503)
    return {"deleted": runtime.users.delete(user_id, confirm=confirm)}


@router.get("/api/prefs")
def get_prefs(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.users is None:
        raise ApiError("not_ready", "users not ready", 503)
    return runtime.users.prefs()


@router.put("/api/prefs")
def set_prefs(
    body: PrefsUpdateRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.users is None:
        raise ApiError("not_ready", "users not ready", 503)
    return runtime.users.set_prefs(body.values)


@router.get("/api/metrics")
def get_metrics(request: Request, range: str = "7d") -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.analytics is None:
        raise ApiError("not_ready", "analytics not ready", 503)
    return runtime.analytics.metrics(_range_days(range))


@router.get("/api/insights/distraction")
def distraction_insights(
    request: Request,
    range: str = "7d",
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.distractions is None:
        raise ApiError("not_ready", "analytics not ready", 503)
    return runtime.distractions.insights(_range_days(range))


@router.post("/api/distraction")
def log_distraction(
    body: DistractionRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.distractions is None:
        raise ApiError("not_ready", "analytics not ready", 503)
    return runtime.distractions.log(
        minutes=body.minutes,
        purpose=body.purpose,
        context=body.context,
        source=body.source,
    )


@router.get("/api/load")
def get_load(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.load is None:
        raise ApiError("not_ready", "load service not ready", 503)
    return runtime.load.snapshot()


@router.post("/api/load/ack")
def acknowledge_load(
    body: RestAckRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.load is None:
        raise ApiError("not_ready", "load service not ready", 503)
    runtime.load.acknowledge(body.hours)
    return runtime.load.snapshot()


@router.post("/api/load/rest")
def offer_rest(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.load is None:
        raise ApiError("not_ready", "load service not ready", 503)
    return runtime.load.offer()


@router.get("/api/degrade")
def get_degrade(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise ApiError("not_ready", "runtime not ready", 503)
    return runtime.degrade.snapshot()


@router.get("/api/recovery")
def get_recovery(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise ApiError("not_ready", "runtime not ready", 503)
    return runtime.recovery.snapshot()


@router.post("/api/demo/reset")
def demo_reset(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.repos is None:
        raise ApiError("not_ready", "demo not ready", 503)
    from demo.service import DemoService

    service = DemoService(
        runtime.repos,
        connection=runtime.db.connection,
        marker=runtime.settings.data.dir / "demo_state.json",
    )
    return service.reset()


@router.get("/api/weekly")
def get_weekly(request: Request, range: str = "7d") -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.weekly is None:
        raise ApiError("not_ready", "weekly report not ready", 503)
    return runtime.weekly.generate(_range_days(range))


@router.post("/api/files")
async def upload_file(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.inbox is None:
        raise ApiError("not_ready", "inbox not ready", 503)
    filename = request.headers.get("X-Filename", "upload")
    data = await request.body()
    try:
        return runtime.inbox.save(filename, data)
    except ValueError as exc:
        raise ApiError("invalid_file", str(exc), 400) from exc


@router.get("/api/files")
def list_files(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.inbox is None:
        raise ApiError("not_ready", "inbox not ready", 503)
    return {"items": runtime.inbox.list()}


@router.get("/api/files/{name}")
def download_file(name: str, request: Request) -> FileResponse:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.inbox is None:
        raise ApiError("not_ready", "inbox not ready", 503)
    path = runtime.inbox.root / Path(name).name
    if not path.is_file():
        raise ApiError("not_found", "file not found", 404)
    return FileResponse(path)


@router.get("/upload", response_class=HTMLResponse, include_in_schema=False)
def upload_page() -> str:
    return _UPLOAD_PAGE


_UPLOAD_PAGE = """<!doctype html><html lang="zh"><meta charset="utf-8">
<title>Flow 文件上传</title>
<style>body{font-family:system-ui;background:#1c1713;color:#f4ecdf;
padding:8vw}button{padding:1em;font-size:1.2em}</style>
<h1>把资料传给 Flow</h1>
<p>图片 / PDF，单个文件不超过 20MB。上传后会出现在设备的待确认列表。</p>
<input id="f" type="file" multiple accept="image/*,.pdf">
<button onclick="up()">上传</button><pre id="out"></pre>
<script>
async function up(){const out=document.getElementById('out');
for(const f of document.getElementById('f').files){
 out.textContent+='上传 '+f.name+'...\\n';
 const r=await fetch('/api/files',{method:'POST',
  headers:{'X-Filename':f.name,
  'Content-Type':f.type||'application/octet-stream'},
  body:f}); out.textContent+=await r.text()+'\\n';}}
</script></html>"""


def _range_days(value: str) -> int:
    text = str(value or "7d").lower().rstrip("d")
    try:
        return max(1, min(90, int(text)))
    except ValueError:
        return 7


@router.post("/api/dialogue")
def dialogue_turn(
    body: DialogueRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise ApiError("not_ready", "runtime not ready", 503)
    actions = runtime.dialogue.turn(body.text, source=body.source)
    results: list[dict[str, Any]] = []
    if body.execute:
        from dialogue.actions import DialogueDispatcher

        def on_channel(payload):
            if runtime.channels is None:
                return {"ok": False}
            return runtime.channels.machine.activate(str(payload["tool"]))

        def on_create_task(payload):
            if runtime.capture is None:
                return {"ok": False}
            tasks = runtime.capture.commit([payload["draft"]])
            return [task.to_dict() for task in tasks]

        def on_update_task(payload):
            return payload

        def on_delete_task(payload):
            if runtime.repos is None:
                return {"ok": False}
            tasks = runtime.repos.tasks.list()
            index = int(payload.get("index", 1)) - 1
            if 0 <= index < len(tasks):
                return {
                    "deleted": runtime.repos.tasks.soft_delete(tasks[index].id)
                }
            return {"deleted": False}

        def on_plan(kind, payload):
            if runtime.plan_service is None:
                return {"ok": False}
            if kind == "build":
                draft = runtime.plan_service.create_from_repo()
                return draft.to_dict()
            plan_id = runtime.focus.state.plan_id if runtime.focus else ""
            if plan_id:
                return runtime.plan_service.revise(
                    plan_id,
                    str(payload.get("text", "")),
                )
            return {"ok": False}

        def on_ask(payload):
            if runtime.say_service is not None:
                runtime.say_service.say(
                    str(payload.get("text", "")),
                    emotion="listening",
                    priority="dialogue",
                )
            return {"ok": True}

        dispatcher = DialogueDispatcher(
            on_channel=on_channel,
            on_create_task=on_create_task,
            on_update_task=on_update_task,
            on_delete_task=on_delete_task,
            on_plan=on_plan,
            on_confirm=lambda payload: {"ok": True},
            on_cancel=lambda payload: {"ok": True},
            on_query=lambda payload: runtime.snapshot(),
            on_ask=on_ask,
        )
        results = dispatcher.dispatch(actions)
    return {
        "actions": [action.to_dict() for action in actions],
        "results": results,
        "context": runtime.dialogue.summary(),
    }


@router.post("/api/plan")
def create_plan(
    body: PlanCreateRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.plan_service is None:
        raise ApiError("not_ready", "plan service not ready", 503)
    from datetime import date

    tasks = (
        [runtime.repos.tasks.get(task_id) for task_id in body.task_ids]
        if runtime.repos is not None
        else []
    )
    tasks = [task for task in tasks if task is not None]
    if not tasks and runtime.repos is not None:
        tasks = runtime.repos.tasks.list()
    draft = runtime.plan_service.create(
        tasks,
        day=date.fromisoformat(body.day) if body.day else None,
    )
    return draft.to_dict()


@router.get("/api/plan/{plan_id}")
def get_plan(plan_id: str, request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.plan_service is None:
        raise ApiError("not_ready", "plan service not ready", 503)
    draft = runtime.plan_service.get(plan_id)
    if draft is None:
        raise ApiError("not_found", "plan not found", 404)
    return {
        "plan": draft.to_dict(),
        "summary": runtime.plan_service.summary(plan_id),
    }


@router.post("/api/plan/{plan_id}/revise")
def revise_plan(
    plan_id: str,
    body: PlanReviseRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.plan_service is None:
        raise ApiError("not_ready", "plan service not ready", 503)
    return runtime.plan_service.revise(plan_id, body.instruction)


@router.post("/api/plan/{plan_id}/confirm")
def confirm_plan(plan_id: str, request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.plan_service is None:
        raise ApiError("not_ready", "plan service not ready", 503)
    draft = runtime.plan_service.confirm(plan_id)
    if draft is None:
        raise ApiError("not_found", "plan not found", 404)
    started = (
        runtime.focus.begin(plan_id)
        if runtime.focus is not None
        else {"ok": False}
    )
    return {"plan": draft.to_dict(), "focus": started}


@router.post("/api/plan/{plan_id}/undo")
def undo_plan(plan_id: str, request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.plan_service is None:
        raise ApiError("not_ready", "plan service not ready", 503)
    draft = runtime.plan_service.undo(plan_id)
    if draft is None:
        raise ApiError("not_found", "no previous version", 404)
    return draft.to_dict()


@router.get("/api/focus")
def get_focus(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.focus is None:
        raise ApiError("not_ready", "focus service not ready", 503)
    return runtime.focus.snapshot()


@router.post("/api/focus/control")
def focus_control(
    body: FocusControlRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.focus is None:
        raise ApiError("not_ready", "focus service not ready", 503)
    return runtime.focus.control(body.action, body.minutes)


@router.post("/api/plan/replan")
def replan(body: ReplanRequest, request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.focus is None:
        raise ApiError("not_ready", "focus service not ready", 503)
    return runtime.focus.replan(body.reason)


@router.post("/api/capture/text")
def capture_text(
    body: CaptureTextRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.capture is None:
        raise ApiError("not_ready", "capture service not ready", 503)
    drafts = runtime.capture.from_text(body.text, source=body.source)
    return {"drafts": drafts, "count": len(drafts)}


@router.post("/api/capture/commit")
def capture_commit(
    body: CaptureCommitRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.capture is None:
        raise ApiError("not_ready", "capture service not ready", 503)
    tasks = runtime.capture.commit(body.drafts)
    return {
        "tasks": [task.to_dict() for task in tasks],
        "count": len(tasks),
    }


@router.post("/api/capture/photo")
def capture_photo(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.capture is None:
        raise ApiError("not_ready", "capture service not ready", 503)
    return runtime.capture.capture_photo()


@router.post("/api/phone/manual")
def post_phone_manual(
    body: PhoneManualRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.phone_sessions is None:
        raise ApiError(
            "not_ready",
            "phone service is not initialized",
            503,
        )
    transition = runtime.phone_sessions.manual(
        body.present,
        body.charging,
        current_ma=body.current_ma,
    )
    return {
        "transition": transition,
        "phone": runtime.phone_sessions.snapshot(),
    }


@router.post("/api/phone/session")
def post_phone_session(
    body: PhoneSessionRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.phone_contract is None:
        raise ApiError("not_ready", "phone contract not ready", 503)
    contract = runtime.phone_contract.begin(body.purpose, body.minutes)
    return runtime.phone_contract.snapshot()


@router.post("/api/phone/session/end")
def end_phone_session(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.phone_contract is None:
        raise ApiError("not_ready", "phone contract not ready", 503)
    ended = runtime.phone_contract.end("manual")
    return {"ended": ended, **runtime.phone_contract.snapshot()}


@router.post("/api/phone/session/extend")
def extend_phone_session(
    body: PhoneExtendRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.phone_contract is None:
        raise ApiError("not_ready", "phone contract not ready", 503)
    extended = runtime.phone_contract.extend(body.minutes)
    return {
        "extended": extended,
        **runtime.phone_contract.snapshot(),
    }


@router.get("/api/reminders")
def list_reminders(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.repos is None:
        raise ApiError("not_ready", "reminders not ready", 503)
    return {
        "items": runtime.repos.reminders.list_all(),
        "upcoming": runtime.scheduler.upcoming(),
    }


@router.post("/api/reminders")
def create_reminder(
    body: ReminderRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.repos is None:
        raise ApiError("not_ready", "scheduler not ready", 503)
    if not runtime.scheduler.enabled:
        raise ApiError("disabled", "scheduler is disabled", 503)
    if body.text:
        reminder_id = runtime.scheduler.create_from_text(body.text)
    else:
        from scheduler.model import ReminderSpec

        spec = ReminderSpec(
            kind=body.kind,
            at=body.at,
            minutes=body.minutes,
            weekday=body.weekday,
            on=body.on,
            template=body.template,
            allow_quiet=body.allow_quiet,
        )
        reminder_id = runtime.scheduler.create(spec)
    return {"id": reminder_id}


@router.delete("/api/reminders/{reminder_id}")
def delete_reminder(reminder_id: str, request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.repos is None:
        raise ApiError("not_ready", "reminders not ready", 503)
    return {"deleted": runtime.repos.reminders.disable(reminder_id)}


@router.post("/api/say")
def post_say(body: SayRequest, request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.say_service is None:
        raise ApiError("not_ready", "speech output not ready", 503)
    queued = runtime.say_service.say(
        body.text,
        emotion=body.emotion,
        priority=body.priority,
    )
    return {"queued": queued, "say": runtime.say_service.health()}


@router.get("/api/channel/current")
def channel_current(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.channels is None:
        raise ApiError(
            "not_ready",
            "channel service is not initialized",
            503,
        )
    return runtime.channels.snapshot()["current"]


@router.post("/api/intent")
def post_intent(
    body: IntentRequest,
    request: Request,
) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.channels is None:
        raise ApiError(
            "not_ready",
            "channel service is not initialized",
            503,
        )
    actions = runtime.channels.handle_text(
        body.text,
        source=body.source,
    )
    state = runtime.channels.snapshot()
    return {
        "intent": runtime.channels.last_intent.to_dict()
        if runtime.channels.last_intent is not None
        else None,
        "actions": [action.to_dict() for action in actions],
        "channel": state["current"],
        "stack": state["stack"],
        "overloaded": state["overloaded"],
    }


def placeholder_html() -> str:
    if _PLACEHOLDER.exists():
        return _PLACEHOLDER.read_text(encoding="utf-8")
    return "<h1>Flow</h1>"


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(
        request: Request,
        exc: ApiError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=422,
            content=error_payload(
                "validation_error",
                "request validation failed",
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        del request
        message = (
            exc.detail
            if isinstance(exc.detail, str)
            else "request failed"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload("http_error", message),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception(
            "unhandled request error",
            extra={
                "event": "http.error",
                "method": request.method,
                "path": request.url.path,
            },
        )
        return JSONResponse(
            status_code=500,
            content=error_payload(
                "internal_error",
                "internal server error",
            ),
        )
