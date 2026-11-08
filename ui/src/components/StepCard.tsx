import { motion } from "framer-motion";
import { useI18n } from "../i18n";
import type { StepState } from "../state/types";
import { ProgressRing } from "./ProgressRing";

interface StepCardProps {
  step: StepState;
}

export function StepCard({ step }: StepCardProps) {
  const { t } = useI18n();
  const progress =
    step.totalMs > 0 ? step.remainingMs / step.totalMs : 0;
  return (
    <motion.div
      className="step-card"
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      <div className="step-card__meta">
        <span>{t.executing.step(step.index + 1)}</span>
        <span>{t.executing.minutes(step.minutes)}</span>
      </div>
      <div className="step-card__visual">
        <ProgressRing progress={progress} size={300}>
          <div className="step-card__time">
            {formatRemaining(step.remainingMs)}
          </div>
          <div className="step-card__hint">{t.executing.ringHint}</div>
        </ProgressRing>
      </div>
      <div className="step-card__copy">
        <h1 className="step-card__title">
          {step.title || t.executing.currentStep}
        </h1>
        {step.detail ? (
          <p className="step-card__detail">{step.detail}</p>
        ) : null}
      </div>
    </motion.div>
  );
}

export function formatRemaining(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.ceil(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}
