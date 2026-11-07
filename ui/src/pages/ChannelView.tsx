import { motion } from "framer-motion";
import {
  channelLabel,
  asRecord,
} from "../state/reducer";
import type { FlowState } from "../state/types";
import { PageShell } from "../components/PageShell";

interface Props {
  state: FlowState;
}

export function ChannelView({ state }: Props) {
  const hints = state.channelHints.slice(0, 2);
  return (
    <PageShell footer={hints[0] ?? "说“返回”回到主页"}>
      <div className="page__body channel-view">
        <div className="channel-kicker">当前通道</div>
        <h1 className="channel-title">
          {state.channelTitle || channelLabel(state.channel)}
        </h1>
        <ChannelBody state={state} />
        {hints.length > 1 && (
          <p className="channel-hint">{hints[1]}</p>
        )}
      </div>
    </PageShell>
  );
}

function ChannelBody({ state }: Props) {
  const data = asRecord(state.channelData);
  switch (state.channel) {
    case "clock":
      return (
        <div className="channel-clock">
          <strong>{text(data.time, "--:--")}</strong>
          <span>{text(data.date, "")}</span>
        </div>
      );
    case "tasks":
      return <ChannelList items={rows(data.items)} empty="还没有任务" dataKey="title" />;
    case "plan":
      return <ChannelList items={rows(data.plans)} empty="还没有计划" dataKey="date" />;
    case "focus":
      return (
        <div className="channel-focus">
          <strong>{clock(data.remaining_seconds)}</strong>
          <span>{data.running === true ? "正在专注" : "已暂停"}</span>
        </div>
      );
    case "reminder":
      return (
        <div className="channel-focus">
          <strong>{number(data.count, 0)}</strong>
          <span>个提醒</span>
        </div>
      );
    case "music":
      return (
        <div className="channel-music">
          <strong>{text(data.track, "轻音乐 · 专注")}</strong>
          <span>{data.playing === true ? "播放中" : "已暂停"}</span>
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
}: {
  items: Record<string, unknown>[];
  empty: string;
  dataKey: string;
}) {
  if (items.length === 0) {
    return <p className="channel-empty">{empty}</p>;
  }
  return (
    <div className="channel-list">
      {items.slice(0, 4).map((item, index) => (
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
          <span className="channel-row__title">
            {text(item[dataKey], "未命名")}
          </span>
        </motion.div>
      ))}
      {items.length > 4 && (
        <p className="channel-more">还有 {items.length - 4} 项</p>
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
