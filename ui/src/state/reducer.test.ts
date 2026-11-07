import { describe, expect, it } from "vitest";
import {
  makeInitialState,
  reducer,
  asPhase,
  formatClock,
} from "./reducer";
import type { FlowState } from "./types";

const at = new Date("2026-11-07T10:00:00+08:00");

let nextSeq = 1;

function withMessage(
  state: FlowState,
  type: string,
  payload: Record<string, unknown>,
  seq = nextSeq++,
): FlowState {
  return reducer(state, {
    type: "ws",
    message: { type, payload, seq },
  });
}

describe("flow reducer", () => {
  it("starts on idle with a stable clock", () => {
    const state = makeInitialState(at);
    expect(state.phase).toBe("idle");
    expect(state.face).toBe("neutral");
    expect(state.offline).toBe(false);
    expect(state.clock).toBe(formatClock(at));
  });

  it("switches every phase and face", () => {
    let state = makeInitialState(at);
    const phases = [
      ["listening", "listening"],
      ["thinking", "thinking"],
      ["plan_review", "thinking"],
      ["executing", "neutral"],
      ["celebrating", "excited"],
      ["resting", "sleepy"],
      ["idle", "neutral"],
    ] as const;
    for (const [phase, face] of phases) {
      state = withMessage(state, "ui.phase", { phase, channel: "focus" });
      expect(state.phase).toBe(phase);
      expect(state.face).toBe(face);
    }
  });

  it("applies assistant speech and emotion", () => {
    const state = withMessage(
      makeInitialState(at),
      "assistant.say",
      { text: "先打开文档", emotion: "happy" },
    );
    expect(state.message).toBe("先打开文档");
    expect(state.face).toBe("happy");
  });

  it("restores full state from state.sync and clears offline", () => {
    let state = reducer(makeInitialState(at), {
      type: "connection",
      status: "offline",
    });
    expect(state.offline).toBe(true);
    state = withMessage(state, "state.sync", {
      phase: "executing",
      channel: "focus",
      message: "先做第一步",
      phone: { present: true, charging: true },
      step: {
        title: "列出 3 个论点",
        minutes: 20,
        remaining_ms: 600000,
        total_ms: 1200000,
        index: 1,
        total: 3,
      },
      tasks_count: 2,
    });
    expect(state.phase).toBe("executing");
    expect(state.offline).toBe(false);
    expect(state.phone.present).toBe(true);
    expect(state.step.title).toBe("列出 3 个论点");
    expect(state.tasksCount).toBe(2);
  });

  it("retains the last screen when offline", () => {
    let state = withMessage(
      makeInitialState(at),
      "ui.phase",
      { phase: "plan_review", channel: "plan" },
    );
    state = reducer(state, {
      type: "connection",
      status: "offline",
    });
    expect(state.phase).toBe("plan_review");
    expect(state.offline).toBe(true);
  });

  it("maps plan, focus, reward and error events", () => {
    let state = withMessage(makeInitialState(at), "plan.draft", {
      plan_id: "p_1",
      items: [
        { title: "列出论点", start: "19:00", est_minutes: 20 },
      ],
    });
    expect(state.phase).toBe("plan_review");
    expect(state.plan?.items).toHaveLength(1);

    state = withMessage(state, "focus.state", {
      title: "写出引言",
      remaining_ms: 300000,
      total_ms: 900000,
      index: 2,
      total: 4,
    });
    expect(state.phase).toBe("executing");
    expect(state.step.title).toBe("写出引言");
    expect(state.step.remainingMs).toBe(300000);

    state = withMessage(state, "reward.event", {
      kind: "step_done",
    });
    expect(state.phase).toBe("celebrating");
    expect(state.face).toBe("excited");

    state = withMessage(state, "error", { message: "网络断开" });
    expect(state.face).toBe("concerned");
    expect(state.toast).toBe("网络断开");
  });

  it("opens and closes a T04 channel", () => {
    let state = withMessage(makeInitialState(at), "channel.enter", {
      channel: "focus",
      title: "专注计时",
      snapshot: {
        channel: "focus",
        title: "专注计时",
        data: { remaining_seconds: 300, running: true },
        hints: ["说“暂停”", "说“返回”"],
      },
    });
    expect(state.channelActive).toBe(true);
    expect(state.channel).toBe("focus");
    expect(state.channelTitle).toBe("专注计时");
    expect(state.channelData.remaining_seconds).toBe(300);
    expect(state.channelHints).toHaveLength(2);
    expect(state.phase).toBe("idle");

    state = withMessage(state, "channel.exit", {});
    expect(state.channelActive).toBe(false);
    expect(state.channel).toBe("clock");
    expect(state.channelData).toEqual({});
  });

  it("restores an active channel from state.sync", () => {
    const state = withMessage(makeInitialState(at), "state.sync", {
      phase: "idle",
      channel_state: {
        channel: "tasks",
        title: "任务清单",
        data: { count: 2, items: [{ title: "写引言" }] },
        hints: ["说“完成第一条”"],
      },
    });
    expect(state.channelActive).toBe(true);
    expect(state.channel).toBe("tasks");
    expect(state.channelTitle).toBe("任务清单");
    expect(state.channelData.count).toBe(2);
  });

  it("updates the active focus channel on focus.state", () => {
    let state = withMessage(makeInitialState(at), "channel.enter", {
      channel: "focus",
      title: "专注计时",
      snapshot: {
        channel: "focus",
        data: { remaining_seconds: 600, running: false },
        hints: ["说“开始”"],
      },
    });
    state = withMessage(state, "focus.state", {
      remaining_seconds: 540,
      running: true,
    });
    expect(state.channelData.remaining_seconds).toBe(540);
    expect(state.channelData.running).toBe(true);
  });

  it("maps reward feedback and companion state", () => {
    let state = withMessage(makeInitialState(at), "reward.feedback", {
      message: "这一小步，稳稳的。",
      level: 1,
    });
    expect(state.phase).toBe("celebrating");
    expect(state.message).toContain("这一小步");
    state = withMessage(state, "state.sync", {
      phase: "idle",
      companion: {
        exp: 12,
        level: 1,
        stage: "小苗",
        streak: 3,
        next_exp: 30,
      },
    });
    expect(state.companion?.stage).toBe("小苗");
    expect(state.companion?.streak).toBe(3);
  });

  it("ignores stale sequenced events but accepts a fresh sync", () => {
    const first = withMessage(
      makeInitialState(at),
      "ui.phase",
      { phase: "listening" },
      5,
    );
    const stale = withMessage(
      first,
      "ui.phase",
      { phase: "resting" },
      4,
    );
    expect(stale.phase).toBe("listening");
    const sync = withMessage(
      stale,
      "state.sync",
      { phase: "idle", seq: 1 },
      1,
    );
    expect(sync.phase).toBe("idle");
  });

  it("ignores unknown message types and invalid phases", () => {
    const state = withMessage(
      makeInitialState(at),
      "not.a.real.event",
      { phase: "resting" },
    );
    expect(state.phase).toBe("idle");
    expect(asPhase("nope")).toBeNull();
    expect(asPhase("resting")).toBe("resting");
  });

  it("updates the clock action", () => {
    const later = new Date("2026-11-07T11:00:00+08:00");
    const state = reducer(makeInitialState(at), {
      type: "clock",
      now: later,
    });
    expect(state.clock).toBe(formatClock(later));
  });
});
