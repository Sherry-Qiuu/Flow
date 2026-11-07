interface ClockProps {
  clock: string;
  date: string;
  compact?: boolean;
}

export function Clock({ clock, date, compact = false }: ClockProps) {
  return (
    <div className={`clock ${compact ? "clock--compact" : ""}`}>
      <div className="clock__time">{clock}</div>
      <div className="clock__date">{date}</div>
    </div>
  );
}
