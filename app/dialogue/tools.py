"""T08 fixed nine-tool schema."""

TOOLS = (
    {
        "name": "open_tool",
        "description": "切换当前工具通道",
        "parameters": {"tool": "clock|tasks|plan|focus|reminder|music"},
    },
    {
        "name": "create_task",
        "description": "创建任务草稿",
        "parameters": {
            "title": "string",
            "deadline": "string?",
            "est": "int?",
        },
    },
    {
        "name": "update_task",
        "description": "修改当前草稿",
        "parameters": {"field": "string", "value": "any"},
    },
    {
        "name": "delete_task",
        "description": "删除任务（需二次确认）",
        "parameters": {"task_id": "string?"},
    },
    {
        "name": "build_plan",
        "description": "生成计划草稿",
        "parameters": {"day": "string?"},
    },
    {
        "name": "modify_plan",
        "description": "修改计划草稿",
        "parameters": {"instruction": "string"},
    },
    {
        "name": "confirm",
        "description": "确认当前动作",
        "parameters": {},
    },
    {
        "name": "cancel",
        "description": "取消当前草稿/确认",
        "parameters": {},
    },
    {
        "name": "query",
        "description": "查询当前状态",
        "parameters": {"what": "tasks|plan|reminders|focus"},
    },
)

TOOL_NAMES = tuple(tool["name"] for tool in TOOLS)
