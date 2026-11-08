import { motion } from "framer-motion";
import { FaceExpression } from "../components/FaceExpression";
import { PageShell, type PageProps } from "../components/PageShell";
import { useI18n } from "../i18n";

export function Listening({ state }: PageProps) {
  const { t, srv } = useI18n();
  return (
    <PageShell className="listening" footer={t.listening.footer}>
      <div className="listening__stage">
        <motion.div
          className="listening__ring"
          animate={{ scale: [0.9, 1.15, 0.9], opacity: [0.18, 0.05, 0.18] }}
          transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="listening__ring listening__ring--second"
          animate={{ scale: [1.05, 1.3, 1.05], opacity: [0.1, 0.02, 0.1] }}
          transition={{
            duration: 3.2,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0.6,
          }}
        />
        <FaceExpression mood="listening" size={300} />
      </div>
      <p className="eyebrow">{t.listening.eyebrow}</p>
      <p className="page__message">
        {srv(state.message) || t.phases.listening}
      </p>
    </PageShell>
  );
}
