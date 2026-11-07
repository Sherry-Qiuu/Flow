import { motion } from "framer-motion";
import { FaceExpression } from "../components/FaceExpression";
import { PageShell, type PageProps } from "../components/PageShell";

export function Thinking({ state }: PageProps) {
  return (
    <PageShell
      className="thinking"
      footer="通常只要几秒钟"
    >
      <FaceExpression mood="thinking" size={300} />
      <div className="thinking__dots" aria-hidden="true">
        {[0, 1, 2].map((index) => (
          <motion.span
            key={index}
            animate={{ opacity: [0.2, 1, 0.2], y: [0, -6, 0] }}
            transition={{
              duration: 1.4,
              repeat: Infinity,
              delay: index * 0.18,
            }}
          />
        ))}
      </div>
      <p className="page__message">{state.message}</p>
    </PageShell>
  );
}
