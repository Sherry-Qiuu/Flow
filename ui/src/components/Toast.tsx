import { AnimatePresence, motion } from "framer-motion";
import { useI18n } from "../i18n";
import type { ToastState } from "../state/types";

interface ToastProps {
  toast: ToastState | null;
}

export function Toast({ toast }: ToastProps) {
  const { t, srv } = useI18n();
  const message = toast === null ? null : toastText(toast, t.toast, srv);
  return (
    <AnimatePresence>
      {message ? (
        <motion.div
          key={message}
          className="toast"
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.2 }}
          role="status"
          aria-live="polite"
        >
          {message}
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function toastText(
  toast: ToastState,
  copy: {
    tasks: (count: number) => string;
    reminder: string;
    error: string;
  },
  srv: (text: string | null | undefined) => string,
): string {
  switch (toast.kind) {
    case "tasks":
      return copy.tasks(toast.count);
    case "reminder":
      return srv(toast.title) || copy.reminder;
    case "error":
      return srv(toast.text) || copy.error;
  }
}
