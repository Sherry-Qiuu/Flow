"""T26 event whitelist."""

EVENTS = (
    "app.started",
    "task.created",
    "task.completed",
    "step.completed",
    "step.skipped",
    "step.stuck",
    "plan.confirmed",
    "plan.replanned",
    "reminder.fired",
    "reminder.responded",
    "phone.contract.started",
    "phone.contract.ended",
    "phone.contract.overdue",
    "distraction.logged",
    "rest.offered",
    "rest.accepted",
)

ALLOWED = frozenset(EVENTS)
