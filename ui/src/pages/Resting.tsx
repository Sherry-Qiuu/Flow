import { motion } from "framer-motion";
import { FaceExpression } from "../components/FaceExpression";
import { PageShell, type PageProps } from "../components/PageShell";
import { useI18n } from "../i18n";

export function Resting({ state }: PageProps) {
  const { t, srv } = useI18n();
  return (
    <PageShell className="resting" footer={t.resting.footer}>
      <div className="resting__stage">
        <motion.div
          className="resting__breath"
          animate={{ scale: [0.92, 1.08, 0.92], opacity: [0.2, 0.4, 0.2] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
        />
        <FaceExpression mood="sleepy" size={300} quiet />
      </div>
      <p className="eyebrow">{t.resting.eyebrow}</p>
      <p className="page__message">
        {srv(state.message) || t.phases.resting}
      </p>
    </PageShell>
  );
}
