export type Phase =
  | "idle"
  | "listening"
  | "thinking"
  | "plan_review"
  | "executing"
  | "celebrating"
  | "resting"
  | "settings";

export type Channel =
  | "clock"
  | "tasks"
  | "plan"
  | "focus"
  | "reminder"
  | "music"
  | "phone"
  | "home"
  | "idle";

export type FaceMood =
  | "neutral"
  | "happy"
  | "listening"
  | "thinking"
  | "sleepy"
  | "excited"
  | "concerned"
  | "resting";

export type ConnectionStatus = "connecting" | "online" | "offline";

export interface PlanItem {
  task_id?: string;
  subtask_id?: string;
  start?: string;
  end?: string;
  title: string;
  est_minutes?: number;
}

export interface PlanSummary {
  plan_id?: string;
  date?: string;
  items: PlanItem[];
  total_minutes?: number;
}

export interface StepState {
  title: string;
  detail?: string;
  minutes: number;
  remainingMs: number;
  totalMs: number;
  index: number;
  total: number;
}

export interface PhoneState {
  present: boolean;
  charging: boolean;
  current_ma?: number;
}

export interface CompanionState {
  exp: number;
  level: number;
  stage: string;
  streak: number;
  next_exp?: number | null;
}

/**
 * Toast copy is stored as data, not as a ready-made sentence, so the
 * screen can render it in the current language.
 */
export type ToastState =
  | { kind: "tasks"; count: number }
  | { kind: "reminder"; title: string }
  | { kind: "error"; text: string };

export interface FlowState {
  phase: Phase;
  channel: Channel;
  channelActive: boolean;
  channelTitle: string;
  channelData: Record<string, unknown>;
  channelHints: string[];
  face: FaceMood;
  /** Raw backend text; the page localizes it, content passes through. */
  message: string;
  now: Date;
  plan: PlanSummary | null;
  // Null when nothing is running: a placeholder step used to sit here and the
  // executing page rendered it as if it were the real current step.
  step: StepState | null;
  phone: PhoneState;
  companion: CompanionState | null;
  tasksCount: number;
  connection: ConnectionStatus;
  offline: boolean;
  lastSeq: number;
  toast: ToastState | null;
}

export interface WsMessage {
  type: string;
  payload?: Record<string, unknown>;
  seq?: number;
  ts?: string;
}

export type FlowAction =
  | { type: "ws"; message: WsMessage }
  | { type: "connection"; status: ConnectionStatus }
  | { type: "clock"; now: Date }
  | { type: "clearToast" };
