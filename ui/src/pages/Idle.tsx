import { motion } from "framer-motion";
import { Clock } from "../components/Clock";
import { FaceExpression } from "../components/FaceExpression";
import { PageShell, type PageProps } from "../components/PageShell";
import { PhoneBadge } from "../components/PhoneBadge";
import { CompanionBadge } from "../components/CompanionBadge";
import { TouchButton } from "../components/TouchButton";
import { sendIntent } from "../app/touch";

export function Idle({ state }: PageProps) {
  return (
    <PageShell
      className="idle"
      footer="点一下开始，或说一句话"
    >
      <Clock clock={state.clock} date={state.date} compact />
      <PhoneBadge phone={state.phone} />
      <CompanionBadge companion={state.companion} />
      <div className="idle__face">
        <FaceExpression mood={state.face} size={280} />
      </div>
      <motion.h1
        className="idle__title"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.4 }}
      >
        心流
      </motion.h1>
      <p className="idle__message">{state.message}</p>
      <div className="touch-actions">
        <TouchButton
          label="任务"
          variant="primary"
          onClick={() => sendIntent("打开任务清单")}
        />
        <TouchButton
          label="专注 15 分钟"
          onClick={() => sendIntent("打开专注计时器 15 分钟")}
        />
        <TouchButton
          label="计划"
          onClick={() => sendIntent("打开计划表")}
        />
      </div>
    </PageShell>
  );
}
