import { motion } from "framer-motion";
import { Clock } from "../components/Clock";
import { FaceExpression } from "../components/FaceExpression";
import { PageShell, type PageProps } from "../components/PageShell";
import { PhoneBadge } from "../components/PhoneBadge";
import { CompanionBadge } from "../components/CompanionBadge";
import { TouchButton } from "../components/TouchButton";
import { sendIntent } from "../app/touch";
import { useI18n } from "../i18n";

export function Idle({ state }: PageProps) {
  const { t, srv } = useI18n();
  // Button labels follow the UI language; the intent text stays Chinese
  // because the backend router matches Chinese commands.
  return (
    <PageShell className="idle" footer={t.idle.footer}>
      <PhoneBadge phone={state.phone} />
      <CompanionBadge companion={state.companion} />
      <div className="idle__left">
        <div className="idle__face">
          <FaceExpression mood={state.face} size={260} />
        </div>
        <motion.h1
          className="idle__title"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.4 }}
        >
          {t.idle.title}
        </motion.h1>
      </div>
      <div className="idle__right">
        <Clock now={state.now} />
        <p className="idle__message">
          {srv(state.message) || t.phases.idle}
        </p>
        <div className="touch-actions">
          <TouchButton
            label={t.idle.tasks}
            variant="primary"
            onClick={() => sendIntent("打开任务清单")}
          />
          <TouchButton
            label={t.idle.focus}
            onClick={() => sendIntent("开始专注 15 分钟")}
          />
          <TouchButton
            label={t.idle.plan}
            onClick={() => sendIntent("帮我安排今天")}
          />
        </div>
      </div>
    </PageShell>
  );
}
