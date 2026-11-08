import { useI18n } from "../i18n";

interface ClockProps {
  now: Date;
  compact?: boolean;
}

export function Clock({ now, compact = false }: ClockProps) {
  const { formatClock, formatDate } = useI18n();
  return (
    <div className={`clock ${compact ? "clock--compact" : ""}`}>
      <div className="clock__time">{formatClock(now)}</div>
      <div className="clock__date">{formatDate(now)}</div>
    </div>
  );
}
