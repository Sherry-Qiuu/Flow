import { motion } from "framer-motion";
import type { ReactNode } from "react";
import type { FlowState } from "../state/types";

export interface PageProps {
  state: FlowState;
}

export function PageShell({
  children,
  className = "",
  footer,
}: {
  children: ReactNode;
  className?: string;
  footer?: ReactNode;
}) {
  return (
    <motion.section
      className={`page ${className}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      <div className="page__body">{children}</div>
      {footer ? <footer className="page__footer">{footer}</footer> : null}
    </motion.section>
  );
}
