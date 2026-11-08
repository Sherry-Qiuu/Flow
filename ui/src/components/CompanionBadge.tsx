import { useI18n } from "../i18n";
import type { CompanionState } from "../state/types";

export function CompanionBadge({
  companion,
}: {
  companion: CompanionState | null;
}) {
  const { t, srv } = useI18n();
  if (companion === null) {
    return null;
  }
  const stage = srv(companion.stage);
  const next = companion.next_exp;
  return (
    <div className="companion-badge">
      {stage ? (
        <span className="companion-badge__stage">{stage}</span>
      ) : null}
      <span className="companion-badge__meta">
        Lv.{companion.level} · {companion.exp}
        {next === undefined || next === null
          ? ` · ${t.companion.max}`
          : ` / ${next}`}
        {companion.streak > 1
          ? ` · ${t.companion.streak(companion.streak)}`
          : ""}
      </span>
    </div>
  );
}
