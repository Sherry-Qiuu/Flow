import type {
  Channel,
  FaceMood,
  FlowAction,
  FlowState,
  Phase,
  PlanItem,
  PlanSummary,
  StepState,
  WsMessage,
} from "./types";

const PHASES: Phase[] = [
  "idle",
  "listening",
  "thinking",
  "plan_review",
  "executing",
  "celebrating",
  "resting",
  "settings",
];

const CHANNELS: Channel[] = [
  "clock",
  "tasks",
  "plan",
  "focus",
  "reminder",
  "music",
  "home",
  "idle",
];

export const PHASE_FACE: Record<Phase, FaceMood> = {
  idle: "neutral",
  listening: "listening",
  thinking: "thinking",
  plan_review: "thinking",
  executing: "neutral",
  celebrating: "excited",
  resting: "sleepy",
  settings: "neutral",
};

export const PHASE_MESSAGE: Record<Phase, string> = {
  idle: "今天想先做什么？",
  listening: "我在听。",
  thinking: "正在把这件事拆小…",
  plan_review: "这份计划可以吗？",
  executing: "只做眼前这一步。",
  celebrating: "这一步完成了。",
  resting: "休息一下，等会儿继续。",
  settings: "设置由语音或手势打开。",
};

const EMOTION_FACE: Record<string, FaceMood> = {
  neutral: "neutral",
  happy: "happy",
  glad: "happy",
  excited: "excited",
  listening: "listening",
  thinking: "thinking",
  sleepy: "sleepy",
  tired: "sleepy",
  concerned: "concerned",
  sad: "concerned",
  resting: "resting",
};

export function makeInitialState(now = new Date()): FlowState {
  return {
    phase: "idle",
    channel: "clock",
    channelActive: false,
    channelTitle: "",
    channelData: {},
    channelHints: [],
    face: "neutral",
    message: PHASE_MESSAGE.idle,
    clock: formatClock(now),
    date: formatDate(now),
    plan: null,
    step: {
      title: "准备好时，告诉我你想做什么",
      detail: "说一句话，或挥一下手",
      minutes: 25,
      remainingMs: 25 * 60 * 1000,
      totalMs: 25 * 60 * 1000,
      index: 0,
      total: 1,
    },
    phone: { present: false, charging: false },
    tasksCount: 0,
    connection: "connecting",
    offline: false,
    lastSeq: 0,
    toast: null,
  };
}

export const initialState = makeInitialState();

export function reducer(
  state: FlowState,
  action: FlowAction,
): FlowState {
  switch (action.type) {
    case "clock":
      return {
        ...state,
        clock: formatClock(action.now),
        date: formatDate(action.now),
      };
    case "connection":
      return {
        ...state,
        connection: action.status,
        offline:
          action.status === "offline" ? true : state.offline,
      };
    case "clearToast":
      return state.toast === null ? state : { ...state, toast: null };
    case "ws":
      return applyMessage(state, action.message);
    default:
      return state;
  }
}

function applyMessage(state: FlowState, message: WsMessage): FlowState {
  const seq = message.seq;
  if (
    typeof seq === "number" &&
    seq <= state.lastSeq &&
    message.type !== "state.sync"
  ) {
    return state;
  }
  const base: FlowState = {
    ...state,
    lastSeq: typeof seq === "number" ? seq : state.lastSeq,
  };
  const payload = asRecord(message.payload);
  switch (message.type) {
    case "state.sync":
      return applyStateSync(base, payload);
    case "ui.phase":
      return applyPhase(base, payload);
    case "channel.enter":
      return applyChannelEnter(base, payload);
    case "channel.exit":
      return {
        ...base,
        channelActive: false,
        channel: "clock",
        channelTitle: "",
        channelData: {},
        channelHints: [],
      };
    case "assistant.say":
      return applyAssistant(base, payload);
    case "plan.draft":
      return applyPlan(base, payload);
    case "plan.confirmed":
      return {
        ...base,
        phase: "executing",
        message: "计划已确认，先做第一步。",
        face: "neutral",
      };
    case "focus.state":
      return applyFocus(base, payload);
    case "task.created":
      return applyTasks(base, payload);
    case "reminder.fired":
      return {
        ...base,
        message: text(payload.title, "时间到了。"),
        toast: text(payload.title, "时间到了。"),
      };
    case "reward.event":
      return {
        ...base,
        phase: "celebrating",
        face: "excited",
        message: text(payload.message, "完成一步，做得很好。"),
      };
    case "phone.changed":
      return { ...base, phone: phoneFrom(payload, base.phone) };
    case "error":
      return {
        ...base,
        face: "concerned",
        toast: text(payload.message, "刚才没有成功，请再说一次。"),
      };
    default:
      return base;
  }
}

function applyStateSync(
  state: FlowState,
  payload: Record<string, unknown>,
): FlowState {
  const phase = asPhase(payload.phase) ?? state.phase;
  const channel = asChannel(payload.channel) ?? state.channel;
  const channelState = asRecord(payload.channel_state);
  const active = asChannel(channelState.channel);
  const plan = planFrom(payload.plan) ?? state.plan;
  const step = stepFrom(payload.step) ?? state.step;
  return {
    ...state,
    phase,
    channel: active ?? channel,
    channelActive: active !== null && active !== "idle",
    channelTitle: active && active !== "idle"
      ? text(channelState.title, state.channelTitle)
      : "",
    channelData: active && active !== "idle"
      ? asRecord(channelState.data)
      : {},
    channelHints: active && active !== "idle"
      ? stringList(channelState.hints)
      : [],
    face: PHASE_FACE[phase],
    message: text(payload.message, PHASE_MESSAGE[phase]),
    phone: phoneFrom(payload.phone, state.phone),
    plan,
    step,
    tasksCount: integer(payload.tasks_count, state.tasksCount),
    offline: false,
  };
}

function applyChannelEnter(
  state: FlowState,
  payload: Record<string, unknown>,
): FlowState {
  const snapshot = asRecord(payload.snapshot);
  const channel = asChannel(payload.channel) ?? asChannel(snapshot.channel);
  if (channel === null || channel === "idle") {
    return {
      ...state,
      channelActive: false,
      channelTitle: "",
      channelData: {},
      channelHints: [],
    };
  }
  return {
    ...state,
    phase: "idle",
    channel,
    channelActive: true,
    channelTitle: text(
      payload.title ?? snapshot.title,
      channelLabel(channel),
    ),
    channelData: asRecord(snapshot.data),
    channelHints: stringList(snapshot.hints),
    face: "neutral",
    message: text(
      stringList(snapshot.hints)[0],
      "说“返回”回到主页",
    ),
  };
}

function applyPhase(
  state: FlowState,
  payload: Record<string, unknown>,
): FlowState {
  const phase = asPhase(payload.phase);
  if (phase === null) {
    return state;
  }
  return {
    ...state,
    phase,
    channel: asChannel(payload.channel) ?? state.channel,
    face: PHASE_FACE[phase],
    message:
      phase === "executing" && state.step
        ? state.message
        : PHASE_MESSAGE[phase],
  };
}

function applyAssistant(
  state: FlowState,
  payload: Record<string, unknown>,
): FlowState {
  const emotion = text(payload.emotion, "neutral").toLowerCase();
  return {
    ...state,
    message: text(payload.text, state.message),
    face: EMOTION_FACE[emotion] ?? state.face,
  };
}

function applyPlan(
  state: FlowState,
  payload: Record<string, unknown>,
): FlowState {
  const plan = planFrom(payload);
  if (plan === null) {
    return state;
  }
  return {
    ...state,
    plan,
    phase: "plan_review",
    face: PHASE_FACE.plan_review,
    message: "这份计划可以吗？",
  };
}

function applyFocus(
  state: FlowState,
  payload: Record<string, unknown>,
): FlowState {
  const step = stepFrom(payload) ?? state.step;
  const remaining = integer(payload.remaining_seconds, undefined);
  const focusChannel =
    state.channelActive &&
    state.channel === "focus" &&
    remaining !== undefined;
  return {
    ...state,
    phase: "executing",
    face: "neutral",
    step,
    channelData: focusChannel
      ? {
          ...state.channelData,
          remaining_seconds: remaining,
          running: bool(payload.running, false),
        }
      : state.channelData,
    message: text(payload.message, "只做眼前这一步。"),
  };
}

function applyTasks(
  state: FlowState,
  payload: Record<string, unknown>,
): FlowState {
  const tasks = payload.tasks;
  const count = Array.isArray(tasks)
    ? tasks.length
    : integer(payload.count, state.tasksCount);
  return {
    ...state,
    tasksCount: count,
    toast: `已记录 ${count} 个任务`,
  };
}

function planFrom(value: unknown): PlanSummary | null {
  const record = asRecord(value);
  const items = Array.isArray(record.items) ? record.items : [];
  if (!Array.isArray(record.items) && record.plan_id === undefined) {
    return null;
  }
  return {
    plan_id: text(record.plan_id, undefined),
    date: text(record.date, undefined),
    total_minutes: integer(record.total_minutes, undefined),
    items: items
      .map(itemFrom)
      .filter((item): item is PlanItem => item !== null),
  };
}

function itemFrom(value: unknown): PlanItem | null {
  const record = asRecord(value);
  if (record.title === undefined || record.title === null) {
    return null;
  }
  return {
    task_id: text(record.task_id, undefined),
    subtask_id: text(record.subtask_id, undefined),
    start: text(record.start, undefined),
    end: text(record.end, undefined),
    title: String(record.title),
    est_minutes: integer(record.est_minutes, undefined),
  };
}

function stepFrom(value: unknown): StepState | null {
  const record = asRecord(value);
  if (Object.keys(record).length === 0) {
    return null;
  }
  const remaining = integer(record.remaining_ms, undefined);
  const total = integer(record.total_ms, undefined);
  return {
    title: text(record.title, "当前这一步"),
    detail: text(record.detail, undefined),
    minutes: integer(record.minutes, 25),
    remainingMs: remaining ?? 25 * 60 * 1000,
    totalMs: total ?? remaining ?? 25 * 60 * 1000,
    index: integer(record.index, 0),
    total: integer(record.total, 1),
  };
}

function phoneFrom(
  value: unknown,
  fallback: { present: boolean; charging: boolean },
) {
  const record = asRecord(value);
  return {
    present: bool(record.present, fallback.present),
    charging: bool(record.charging, fallback.charging),
    current_ma: integer(record.current_ma, undefined),
  };
}

export function formatClock(date: Date): string {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatDate(date: Date): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(date);
}

export function asRecord(value: unknown): Record<string, unknown> {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

export function asPhase(value: unknown): Phase | null {
  return typeof value === "string" && PHASES.includes(value as Phase)
    ? (value as Phase)
    : null;
}

export function asChannel(value: unknown): Channel | null {
  return typeof value === "string" && CHANNELS.includes(value as Channel)
    ? (value as Channel)
    : null;
}

export function channelLabel(channel: Channel): string {
  const labels: Record<Channel, string> = {
    clock: "时钟",
    tasks: "任务清单",
    plan: "计划表",
    focus: "专注计时",
    reminder: "提醒",
    music: "音乐",
    home: "主页",
    idle: "主页",
  };
  return labels[channel];
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((entry): entry is string => typeof entry === "string")
    : [];
}

function text(value: unknown, fallback: string): string;
function text(value: unknown, fallback: undefined): string | undefined;
function text(
  value: unknown,
  fallback: string | undefined,
): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

function integer(value: unknown, fallback: number): number;
function integer(value: unknown, fallback: undefined): number | undefined;
function integer(
  value: unknown,
  fallback: number | undefined,
): number | undefined {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : fallback;
}

function bool(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}
