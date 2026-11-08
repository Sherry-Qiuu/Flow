import { motion } from "framer-motion";
import { asRecord } from "../state/reducer";
import type { FlowState } from "../state/types";
import { PageShell } from "../components/PageShell";
import { TouchButton } from "../components/TouchButton";
import { endPhoneSession, sendIntent } from "../app/touch";
import { useI18n } from "../i18n";

interface Props {
  state: FlowState;
}

export function ChannelView({ state }: Props) {
  const { t, srv } = useI18n();
  const hints = state.channelHints.slice(0, 2);
  return (
    <PageShell footer={srv(hints[0]) || t.channel.footerHint}>
      <div className="page__body channel-view">
        <div className="channel-kicker">{t.channel.kicker}</div>
        <h1 className="channel-title">
          {srv(state.channelTitle) || t.channel.labels[state.channel]}
        </h1>
        <ChannelBody state={state} />
        {hints.length > 1 && (
          <p className="channel-hint">{srv(hints[1])}</p>
        )}
        <div className="touch-actions">
          {state.channel === "phone" ? (
            <TouchButton
              label={t.channel.phoneBack}
              variant="primary"
              onClick={endPhoneSession}
            />
          ) : (
            <TouchButton
              label={t.channel.back}
              onClick={() => sendIntent("返回")}
            />
          )}
        </div>
      </div>
    </PageShell>
  );
}

function ChannelBody({ state }: Props) {
  const { t, srv, formatIsoDate } = useI18n();
  const data = asRecord(state.channelData);
  switch (state.channel) {
    case "clock":
      return (
        <div className="channel-clock">
          <strong>{text(data.time, "--:--")}</strong>
          <span>{formatIsoDate(text(data.date, ""))}</span>
        </div>
      );
    case "tasks":
      return (
        <ChannelList
          items={rows(data.items)}
          empty={t.channel.emptyTasks}
          dataKey="title"
        />
      );
    case "plan":
      return (
        <ChannelList
          items={rows(data.plans)}
          empty={t.channel.emptyPlans}
          dataKey="date"
          renderValue={formatIsoDate}
        />
      );
    case "focus":
      return (
        <div className="channel-focus">
          <strong>{clock(data.remaining_seconds)}</strong>
          <span>
            {data.status === "running"
              ? t.channel.focusRunning
              : data.status === "paused"
                ? t.channel.focusPaused
                : t.channel.focusReady}
          </span>
        </div>
      );
    case "phone": {
      const purpose = text(data.purpose, "");
      const purposeLabel =
        t.channel.phonePurpose[purpose] ||
        purpose ||
        t.channel.labels.phone;
      return (
        <div className="channel-focus">
          <strong>{clock(data.remaining_seconds)}</strong>
          <span>
            {purposeLabel} ·{" "}
            {data.status === "overdue"
              ? t.channel.phoneOverdue
              : t.channel.phoneInUse}
          </span>
        </div>
      );
    }
    case "reminder": {
      const count = number(data.count, 0);
      return (
        <div className="channel-focus">
          <strong>{count}</strong>
          <span>{t.channel.reminderUnit(count)}</span>
        </div>
      );
    }
    case "music":
      return (
        <div className="channel-music">
          <strong>
            {srv(text(data.track, "")) || t.channel.musicFallback}
          </strong>
          <span>
            {data.playing === true
              ? t.channel.musicPlaying
              : t.channel.musicPaused}
          </span>
        </div>
      );
    default:
      return null;
  }
}

function ChannelList({
  items,
  empty,
  dataKey,
  renderValue,
}: {
  items: Record<string, unknown>[];
  empty: string;
  dataKey: string;
  renderValue?: (value: string) => string;
}) {
  const { t } = useI18n();
  if (items.length === 0) {
    return <p className="channel-empty">{empty}</p>;
  }
  return (
    <div className="channel-list">
      {items.slice(0, 4).map((item, index) => {
        const raw = text(item[dataKey], "");
        const value = raw
          ? renderValue
            ? renderValue(raw)
            : raw
          : t.channel.unnamed;
        return (
          <motion.div
            className="channel-row"
            key={`${dataKey}-${index}`}
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05 }}
          >
            <span className="channel-row__index">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="channel-row__title">{value}</span>
          </motion.div>
        );
      })}
      {items.length > 4 && (
        <p className="channel-more">{t.channel.more(items.length - 4)}</p>
      )}
    </div>
  );
}

function rows(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.map((entry) => asRecord(entry))
    : [];
}

function text(value: unknown, fallback: string): string {
  return typeof value === "string" && value.length > 0
    ? value
    : fallback;
}

function number(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : fallback;
}

function clock(secondsValue: unknown): string {
  const seconds = Math.max(0, number(secondsValue, 0));
  const minutes = Math.floor(seconds / 60);
  const rest = Math.floor(seconds % 60);
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}
