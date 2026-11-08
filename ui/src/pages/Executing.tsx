import { StepCard } from "../components/StepCard";
import { PageShell, type PageProps } from "../components/PageShell";
import { TouchButton } from "../components/TouchButton";
import { focusControl } from "../app/touch";
import { useI18n } from "../i18n";

export function Executing({ state }: PageProps) {
  const { t } = useI18n();
  return (
    <PageShell className="executing" footer={t.executing.footer}>
      {state.step ? (
        <StepCard step={state.step} />
      ) : (
        <p className="executing-empty">{t.executing.empty}</p>
      )}
      <div className="touch-actions">
        <TouchButton
          label={t.executing.finish}
          variant="primary"
          onClick={() => focusControl("finish")}
        />
        <TouchButton
          label={t.executing.skip}
          onClick={() => focusControl("skip")}
        />
        <TouchButton
          label={t.executing.stuck}
          onClick={() => focusControl("stuck")}
        />
        <TouchButton
          label={t.executing.extend}
          onClick={() => focusControl("extend", 10)}
        />
      </div>
    </PageShell>
  );
}
