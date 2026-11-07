import { motion } from "framer-motion";

interface OfflineBadgeProps {
  offline: boolean;
  reconnecting: boolean;
}

export function OfflineBadge({
  offline,
  reconnecting,
}: OfflineBadgeProps) {
  if (!offline) {
    return null;
  }
  return (
    <motion.div
      className="offline-badge"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      role="status"
      aria-live="polite"
    >
      <span className="offline-badge__dot" />
      {reconnecting ? "离线模式 · 正在重连" : "离线模式"}
    </motion.div>
  );
}
