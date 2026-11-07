import { AnimatePresence, MotionConfig } from "framer-motion";
import { useEffect, useReducer, type ComponentType } from "react";
import { OfflineBadge } from "./components/OfflineBadge";
import { Toast } from "./components/Toast";
import { useStageScale } from "./app/useStageScale";
import { initialState, reducer } from "./state/reducer";
import type { Phase } from "./state/types";
import { Celebrate } from "./pages/Celebrate";
import { Executing } from "./pages/Executing";
import { Idle } from "./pages/Idle";
import { Listening } from "./pages/Listening";
import { PlanReview } from "./pages/PlanReview";
import { Resting } from "./pages/Resting";
import { Settings } from "./pages/Settings";
import { Thinking } from "./pages/Thinking";
import type { PageProps } from "./components/PageShell";
import { FlowSocket, getWebSocketUrl } from "./ws/client";

export const PAGE_MAP: Record<Phase, ComponentType<PageProps>> = {
  idle: Idle,
  listening: Listening,
  thinking: Thinking,
  plan_review: PlanReview,
  executing: Executing,
  celebrating: Celebrate,
  resting: Resting,
  settings: Settings,
};

export function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const scale = useStageScale();

  useEffect(() => {
    const socket = new FlowSocket(getWebSocketUrl(), {
      onMessage: (message) => dispatch({ type: "ws", message }),
      onStatus: (status) =>
        dispatch({ type: "connection", status }),
    });
    socket.connect();
    return () => socket.close();
  }, []);

  useEffect(() => {
    const timer = setInterval(
      () => dispatch({ type: "clock", now: new Date() }),
      1000,
    );
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (state.toast === null) {
      return;
    }
    const timer = setTimeout(
      () => dispatch({ type: "clearToast" }),
      5000,
    );
    return () => clearTimeout(timer);
  }, [state.toast]);

  const Page = PAGE_MAP[state.phase] ?? Idle;
  const reconnecting = state.connection === "connecting";

  return (
    <MotionConfig reducedMotion="user">
      <div className="stage">
        <div
          className="canvas"
          style={{ transform: `scale(${scale})` }}
          data-testid="flow-canvas"
        >
          <AnimatePresence mode="wait">
            <Page key={state.phase} state={state} />
          </AnimatePresence>
          <OfflineBadge offline={state.offline} reconnecting={reconnecting} />
          <Toast message={state.toast} />
        </div>
      </div>
    </MotionConfig>
  );
}

export function pageForPhase(
  phase: Phase,
): ComponentType<PageProps> {
  return PAGE_MAP[phase] ?? Idle;
}
