import { StepCard } from "../components/StepCard";
import { PageShell, type PageProps } from "../components/PageShell";

export function Executing({ state }: PageProps) {
  return (
    <PageShell
      className="executing"
      footer="完成这一步后，说“完成”"
    >
      <StepCard step={state.step} />
    </PageShell>
  );
}
