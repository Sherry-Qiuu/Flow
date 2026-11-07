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
