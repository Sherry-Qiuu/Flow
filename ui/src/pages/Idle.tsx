import { motion } from "framer-motion";
import { Clock } from "../components/Clock";
import { FaceExpression } from "../components/FaceExpression";
import { PageShell, type PageProps } from "../components/PageShell";

export function Idle({ state }: PageProps) {
  return (
    <PageShell
      className="idle"
      footer="说“开始”，或挥一下手"
    >
      <Clock clock={state.clock} date={state.date} compact />
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
    </PageShell>
  );
}
