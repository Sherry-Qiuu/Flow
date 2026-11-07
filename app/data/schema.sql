-- Flow data model v1 (T10).
-- All business tables carry user_id except child rows that are scoped
-- through their parent (subtasks.plan_items) and are queried with a join.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    nickname TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    settings_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'pending',
    est_minutes INTEGER,
    due_at TEXT,
    priority INTEGER NOT NULL DEFAULT 3,
    category TEXT,
    depends_on_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_user_status
    ON tasks (user_id, status);

CREATE TABLE IF NOT EXISTS subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    est_minutes INTEGER NOT NULL,
    order_index INTEGER NOT NULL DEFAULT 0,
    done_at TEXT,
    completion_criteria TEXT NOT NULL DEFAULT '',
    depends_on_json TEXT NOT NULL DEFAULT '[]',
    difficulty INTEGER NOT NULL DEFAULT 2,
    source TEXT NOT NULL DEFAULT 'rule',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_subtasks_task_order
    ON subtasks (task_id, order_index);

CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    plan_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,
    breaks_json TEXT NOT NULL DEFAULT '[]',
    notes_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    mode TEXT NOT NULL DEFAULT 'rule',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plans_user_date
    ON plans (user_id, plan_date);

CREATE TABLE IF NOT EXISTS plan_items (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    task_id TEXT REFERENCES tasks(id),
    subtask_id TEXT REFERENCES subtasks(id),
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    order_index INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    title TEXT NOT NULL DEFAULT '',
    est_minutes INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_plan_items_plan_order
    ON plan_items (plan_id, order_index);

CREATE TABLE IF NOT EXISTS focus_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    plan_item_id TEXT REFERENCES plan_items(id),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    interruptions_json TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_focus_sessions_user_started
    ON focus_sessions (user_id, started_at);

CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL DEFAULT 'timer',
    spec_json TEXT NOT NULL DEFAULT '{}',
    next_fire_at TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_fired_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reminders_next_fire
    ON reminders (next_fire_at);

CREATE TABLE IF NOT EXISTS phone_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    purpose TEXT NOT NULL DEFAULT 'phone',
    planned_minutes INTEGER,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    returned_on_time INTEGER,
    present_state TEXT NOT NULL DEFAULT 'placed'
);
CREATE INDEX IF NOT EXISTS idx_phone_sessions_user_started
    ON phone_sessions (user_id, started_at);

CREATE TABLE IF NOT EXISTS distractions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL DEFAULT 'phone',
    note TEXT NOT NULL DEFAULT '',
    minutes INTEGER NOT NULL DEFAULT 0,
    purpose TEXT NOT NULL DEFAULT 'unknown',
    context TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'voice',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reward_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL,
    points INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS companion_state (
    user_id TEXT PRIMARY KEY REFERENCES users(id),
    state_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS device_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_device_events_ts
    ON device_events (ts);
CREATE INDEX IF NOT EXISTS idx_device_events_user_type
    ON device_events (user_id, type);

CREATE TABLE IF NOT EXISTS metrics_daily (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    metric_date TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE (user_id, metric_date)
);

CREATE TABLE IF NOT EXISTS settings (
    user_id TEXT NOT NULL REFERENCES users(id),
    scope TEXT NOT NULL DEFAULT 'default',
    payload_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, scope)
);

-- T02 boot reports share this database; keep the same shape.
CREATE TABLE IF NOT EXISTS device_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    checked_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_device_status_checked_at
    ON device_status (checked_at);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
