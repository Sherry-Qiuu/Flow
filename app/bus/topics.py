"""Central event topic constants.

The naming rule is ``domain.object.action`` and every topic used by the
application must be declared here. Client/server message types live in
``service.protocol`` because they are transport envelopes, not bus topics.
"""

PHONE_CHANGED = "phone.changed"

SPEECH_FINAL = "speech.final"
INTENT_PARSED = "intent.parsed"
CHANNEL_ENTER = "channel.enter"
CHANNEL_EXIT = "channel.exit"
TASK_CREATED = "task.created"
TASK_UPDATED = "task.updated"
PLAN_DRAFT = "plan.draft"
PLAN_CONFIRMED = "plan.confirmed"
FOCUS_STATE = "focus.state"
REMINDER_FIRED = "reminder.fired"
GESTURE_DETECTED = "gesture.detected"
DISTRACTION_LOGGED = "distraction.logged"
REWARD_EVENT = "reward.event"
EMOTION_FACE = "emotion.face"
ERROR = "error"

ALL_TOPICS = (
    PHONE_CHANGED,
    SPEECH_FINAL,
    INTENT_PARSED,
    CHANNEL_ENTER,
    CHANNEL_EXIT,
    TASK_CREATED,
    TASK_UPDATED,
    PLAN_DRAFT,
    PLAN_CONFIRMED,
    FOCUS_STATE,
    REMINDER_FIRED,
    GESTURE_DETECTED,
    DISTRACTION_LOGGED,
    REWARD_EVENT,
    EMOTION_FACE,
    ERROR,
)
