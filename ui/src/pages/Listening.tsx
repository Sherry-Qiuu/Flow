import { motion } from "framer-motion";
import { FaceExpression } from "../components/FaceExpression";
import { PageShell, type PageProps } from "../components/PageShell";

export function Listening({ state }: PageProps) {
  return (
    <PageShell
      className="listening"
      footer="说完停一下，我会自己断句"
    >
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
      <p className="eyebrow">我在听</p>
      <p className="page__message">{state.message}</p>
    </PageShell>
  );
}
