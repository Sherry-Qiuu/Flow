import type { Lang } from "./types";

/**
 * English for the chrome the backend still writes in Chinese.
 *
 * The screen owns most copy, but a few strings — channel titles, hints,
 * phase messages, celebration phrases, companion stage names and track
 * names — come from the Python services. Translating them here keeps the
 * backend single-language and the screen bilingual without a protocol
 * change. Content (assistant replies, task and plan titles, reminders)
 * is intentionally passed through: it belongs to the user's language, not
 * the UI language.
 *
 * Every key below is a literal copied from `app/`. When the backend copy
 * changes, unknown strings fall back to the original text instead of
 * failing, so this map can lag safely — but the reverse map should be
 * updated whenever `app/` copy is edited.
 */
const SERVER_COPY: Readonly<Record<string, string>> = {
  // Channel titles and the idle channel.
  "主页": "Home",
  "时钟": "Clock",
  "任务清单": "Tasks",
  "计划表": "Plan",
  "专注计时": "Focus timer",
  "提醒": "Reminders",
  "音乐": "Music",
  "手机使用": "Phone",
  // Channel hints (`app/channel/builtin/*.py`, `app/phone/contract.py`).
  "说“打开任务清单”或“开始专注”": "Say “open tasks” or “start focus”",
  "说“任务清单”查看待办": "Say “tasks” to see your list",
  "说“专注计时”开始专注": "Say “focus” to start focusing",
  "说“完成第一条”标记完成": "Say “done with the first” to mark it done",
  "说“打开专注计时”开始做": "Say “open focus” to start working",
  "说“打开任务清单”查看任务": "Say “open tasks” to see your list",
  "说“开始专注”进入计时": "Say “start focus” to open the timer",
  "说“开始”启动计时": "Say “start” to begin",
  "说“暂停”或“结束”": "Say “pause” or “finish”",
  "说“返回”回到主页": "Say “back” to return home",
  "说“继续”恢复计时": "Say “resume” to continue",
  "说“结束”结束这一步": "Say “finish” to end this step",
  "说“播放”或“暂停”": "Say “play” or “pause”",
  "说“放回去了”结束": "Say “put it back” to end",
  "学习用途可申请延长 5 分钟": "Study use can extend by 5 minutes",
  "提醒到点会自动出现": "Reminders appear when they're due",
  "切换有点频繁，我们先专注在当前通道":
    "Lots of switching — let's stay with this channel for now",
  // Phase and fallback messages.
  "只做眼前这一步。": "Just this step.",
  "这份计划可以吗？": "How does this plan look?",
  "刚才出了点问题，我们回到主页":
    "Something went wrong — back to home",
  // Track names in the music channel.
  "轻音乐 · 专注": "Soft focus",
  "白噪音 · 雨": "Rain",
  // Companion stages (`app/emotion/companion.py`).
  "幼芽": "Sprout",
  "小苗": "Seedling",
  "小树": "Sapling",
  "花期": "Bloom",
  "大树": "Tree",
  // Celebration phrases (`app/emotion/phrases.py`) plus the merged line
  // from `app/emotion/celebrate.py`.
  "这一小步，稳稳的。": "One steady step.",
  "你把它往前推了一点。": "You moved it forward a little.",
  "很好，继续保持这个节奏。": "Nice — keep this rhythm.",
  "这一步已经算数了。": "This step counts.",
  "谢谢你愿意开始。": "Thank you for starting.",
  "思路会越走越清楚的。": "It gets clearer as you go.",
  "今天的光，在这里亮了一下。": "A little light today.",
  "先完成，再完美。": "Done first, perfect later.",
  "你正在把大事拆小。": "You're making it smaller.",
  "这一页翻过去了。": "That page is turned.",
  "给自己一点掌声。": "Give yourself some credit.",
  "这个进度值得被看见。": "This progress is worth seeing.",
  "慢一点也没关系。": "Slow is fine.",
  "你做得很认真。": "You're doing this carefully.",
  "又靠近了一点。": "A little closer.",
  "这段专注很珍贵。": "That focus matters.",
  "现在可以歇一小会儿。": "You can rest a moment.",
  "你的坚持有回声。": "Your effort echoes.",
  "这一小步很了不起。": "This small step is big.",
  "我们把下一步留到等会儿。": "The next step can wait.",
  "这几步连在一起，已经走了一小段路。":
    "Those steps added up — you've come a little way.",
};

/** Translate backend chrome; unknown text (content) is returned as-is. */
export function translateServerText(
  text: string | null | undefined,
  lang: Lang,
): string {
  if (!text) {
    return "";
  }
  if (lang === "zh") {
    return text;
  }
  return SERVER_COPY[text] ?? text;
}

/** Exposed for tests so the map can be checked against backend copy. */
export const SERVER_COPY_KEYS = Object.keys(SERVER_COPY);
