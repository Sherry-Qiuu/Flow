"""Central event topic constants.

The naming rule is ``domain.object.action`` and every topic used by the
application must be declared here. Client/server message types live in
``service.protocol`` because they are transport envelopes, not bus topics.
"""

PHONE_CHANGED = "phone.changed"

SPEECH_FINAL = "speech.final"
SPEECH_PARTIAL = "speech.partial"
SPEECH_STARTED = "speech.started"
SPEECH_EMPTY = "speech.empty"
SPEECH_BARGE_IN = "speech.barge_in"
ASSISTANT_SAY = "assistant.say"
PHONE_SESSION_STARTED = "phone.session.started"
PHONE_SESSION_ENDED = "phone.session.ended"
PHONE_SESSION_OVERDUE = "phone.session.overdue"
INTENT_PARSED = "intent.parsed"
CHANNEL_ENTER = "channel.enter"
CHANNEL_EXIT = "channel.exit"
TASK_CREATED = "task.created"
TASK_UPDATED = "task.updated"
PLAN_DRAFT = "plan.draft"
PLAN_CONFIRMED = "plan.confirmed"
FOCUS_STATE = "focus.state"
REMINDER_FIRED = "reminder.fired"
DISTRACTION_LOGGED = "distraction.logged"
REWARD_EVENT = "reward.event"
REWARD_FEEDBACK = "reward.feedback"
COMPANION_CHANGED = "companion.changed"
INBOX_FILE = "inbox.file"
EMOTION_FACE = "emotion.face"
ERROR = "error"

ALL_TOPICS = (
    PHONE_CHANGED,
    SPEECH_FINAL,
    SPEECH_PARTIAL,
    SPEECH_STARTED,
    SPEECH_EMPTY,
    SPEECH_BARGE_IN,
    ASSISTANT_SAY,
    PHONE_SESSION_STARTED,
    PHONE_SESSION_ENDED,
    PHONE_SESSION_OVERDUE,
    INTENT_PARSED,
    CHANNEL_ENTER,
    CHANNEL_EXIT,
    TASK_CREATED,
    TASK_UPDATED,
    PLAN_DRAFT,
    PLAN_CONFIRMED,
    FOCUS_STATE,
    REMINDER_FIRED,
    DISTRACTION_LOGGED,
    REWARD_EVENT,
    REWARD_FEEDBACK,
    COMPANION_CHANGED,
    INBOX_FILE,
    EMOTION_FACE,
    ERROR,
)
