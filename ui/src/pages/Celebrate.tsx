import { motion } from "framer-motion";
import { FaceExpression } from "../components/FaceExpression";
import { PageShell, type PageProps } from "../components/PageShell";

const PARTICLES = Array.from({ length: 14 }, (_, index) => index);

export function Celebrate({ state }: PageProps) {
  return (
    <PageShell
      className="celebrate"
      footer="这一小步，已经算数"
    >
      <div className="celebrate__confetti" aria-hidden="true">
        {PARTICLES.map((index) => (
          <motion.span
            key={index}
            className={`celebrate__particle celebrate__particle--${index % 4}`}
            initial={{ opacity: 0, y: -50, x: 0 }}
            animate={{
              opacity: [0, 1, 0],
              y: [0, 260 + (index % 5) * 30],
              x: [0, (index % 2 === 0 ? 1 : -1) * (20 + index * 4)],
              rotate: [0, 240],
            }}
            transition={{
              duration: 2.4 + (index % 4) * 0.3,
              repeat: Infinity,
              delay: index * 0.12,
              ease: "easeOut",
            }}
          />
        ))}
      </div>
      <FaceExpression mood="excited" size={300} />
      <h1 className="page__title">完成一步</h1>
      <p className="page__message">{state.message}</p>
    </PageShell>
  );
}
