import type { CompanionState } from "../state/types";

export function CompanionBadge({
  companion,
}: {
  companion: CompanionState | null;
}) {
  if (companion === null) {
    return null;
  }
  const next = companion.next_exp;
  return (
    <div className="companion-badge">
      <span className="companion-badge__stage">{companion.stage}</span>
      <span className="companion-badge__meta">
        Lv.{companion.level} · {companion.exp}
        {next === undefined || next === null ? " · 满级" : ` / ${next}`}
        {companion.streak > 1 ? ` · 连续 ${companion.streak} 天` : ""}
      </span>
    </div>
  );
}
