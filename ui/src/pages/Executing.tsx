import { StepCard } from "../components/StepCard";
import { PageShell, type PageProps } from "../components/PageShell";
import { TouchButton } from "../components/TouchButton";
import { focusControl } from "../app/touch";

export function Executing({ state }: PageProps) {
  return (
    <PageShell
      className="executing"
      footer="点按钮，或说“完成/跳过/卡住”"
    >
      {state.step ? (
        <StepCard step={state.step} />
      ) : (
        <p className="executing-empty">这一步已经结束了。</p>
      )}
      <div className="touch-actions">
        <TouchButton
          label="完成"
          variant="primary"
          onClick={() => focusControl("finish")}
        />
        <TouchButton
          label="跳过"
          onClick={() => focusControl("skip")}
        />
        <TouchButton
          label="卡住"
          onClick={() => focusControl("stuck")}
        />
        <TouchButton
          label="延长 10 分钟"
          onClick={() => focusControl("extend", 10)}
        />
      </div>
    </PageShell>
  );
}
