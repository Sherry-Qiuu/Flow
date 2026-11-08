import { motion } from "framer-motion";
import { useI18n } from "../i18n";

interface OfflineBadgeProps {
  offline: boolean;
  reconnecting: boolean;
}

export function OfflineBadge({
  offline,
  reconnecting,
}: OfflineBadgeProps) {
  const { t } = useI18n();
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
      {reconnecting ? t.offline.reconnecting : t.offline.base}
    </motion.div>
  );
}
