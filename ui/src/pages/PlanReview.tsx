import { motion } from "framer-motion";
import { PageShell, type PageProps } from "../components/PageShell";
import { TouchButton } from "../components/TouchButton";
import { confirmPlan, sendIntent } from "../app/touch";
import { useI18n } from "../i18n";

export function PlanReview({ state }: PageProps) {
  const { t } = useI18n();
  const items = state.plan?.items.slice(0, 3) ?? [];
  const totalItems = state.plan?.items.length ?? 0;
  return (
    <PageShell className="plan-review" footer={t.planReview.footer}>
      <p className="eyebrow">{t.planReview.eyebrow}</p>
      <h1 className="page__title">{t.planReview.title}</h1>
      <div className="plan-review__list">
        {items.length === 0 ? (
          <p className="page__message">{t.planReview.empty}</p>
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
                {item.start ?? t.planReview.step(index + 1)}
              </span>
              <span className="plan-review__title">{item.title}</span>
              <span className="plan-review__minutes">
                {item.est_minutes
                  ? t.planReview.minutes(item.est_minutes)
                  : ""}
              </span>
            </motion.div>
          ))
        )}
      </div>
      {totalItems > 3 ? (
        <p className="plan-review__more">
          {t.planReview.more(totalItems - 3)}
        </p>
      ) : null}
      <div className="touch-actions">
        <TouchButton
          label={t.planReview.confirm}
          variant="primary"
          disabled={!state.plan?.plan_id}
          onClick={() =>
            state.plan?.plan_id
              ? confirmPlan(state.plan.plan_id)
              : sendIntent("确认")
          }
        />
        <TouchButton
          label={t.planReview.revise}
          onClick={() => sendIntent("返回")}
        />
      </div>
    </PageShell>
  );
}
