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
  | "home";

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

export interface FlowState {
  phase: Phase;
  channel: Channel;
  face: FaceMood;
  message: string;
  clock: string;
  date: string;
  plan: PlanSummary | null;
  step: StepState;
  phone: PhoneState;
  tasksCount: number;
  connection: ConnectionStatus;
  offline: boolean;
  lastSeq: number;
  toast: string | null;
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
