import { motion } from "framer-motion";
import { PageShell, type PageProps } from "../components/PageShell";

export function PlanReview({ state }: PageProps) {
  const items = state.plan?.items.slice(0, 3) ?? [];
  const totalItems = state.plan?.items.length ?? 0;
  return (
    <PageShell
      className="plan-review"
      footer="说“开始”确认，或挥手"
    >
      <p className="eyebrow">计划草案</p>
      <h1 className="page__title">今天先做这些</h1>
      <div className="plan-review__list">
        {items.length === 0 ? (
          <p className="page__message">还没有计划，先说一件想做的事。</p>
        ) : (
          items.map((item, index) => (
            <motion.div
              key={`${item.subtask_id ?? item.task_id ?? index}`}
              className="plan-review__item"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.08 * index, duration: 0.35 }}
            >
              <span className="plan-review__time">
                {item.start ?? `第 ${index + 1} 步`}
              </span>
              <span className="plan-review__title">{item.title}</span>
              <span className="plan-review__minutes">
                {item.est_minutes ? `${item.est_minutes} 分钟` : ""}
              </span>
            </motion.div>
          ))
        )}
      </div>
      {totalItems > 3 ? (
        <p className="plan-review__more">
          还有 {totalItems - 3} 步，确认后再看
        </p>
      ) : null}
    </PageShell>
  );
}
