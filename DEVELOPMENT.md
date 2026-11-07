# 心流 Flow 开发说明

本文件记录当前已落地的软件任务与验证方法。任务卡原文在
[`docs/software-task-slices/tasks/`](docs/software-task-slices/tasks/)；
树莓派上机步骤见 [`docs/deployment/T01-hardware-runbook.md`](docs/deployment/T01-hardware-runbook.md)。

## 当前实现范围

| 任务 | 状态 | 说明 |
| --- | --- | --- |
| **T01** 设备镜像与运行基座 | 部署资产已完成，硬件验收待上机 | `install.sh`、systemd、journald、kiosk、`flow-diag`、显示配置脚本 |
| **T02** HAL 与开机自检 | 已完成（mock 优先） | 设备契约、mock/real 适配、`python -m hal.selftest`、`device_status` 落库、`phone.changed` 事件 |
| **T03** 后端骨架与事件总线 | 已完成 | FastAPI、WS、asyncio EventBus、配置/`.env`、JSON 日志、健康检查、单 worker 生命周期 |
| **T04** 单通道状态机与工具路由 | 已完成 | 6 通道、先 exit 再 enter、返回栈 ≤3、意图路由、异常回退、30 分钟过载收敛 |
| **T05** 屏幕 UI 框架 | 已完成 | React + Vite + TS + Tailwind + Framer Motion，720 画布、8 表情、7+1 页面、自动重连、通道视图 |
| **T06** 语音输入管线 | 核心完成 | 16k 采集/3s 预录、能量 VAD、partial/final、云端/Vosk 降级、打断、空识别提示 |
| **T07** 语音输出与表情联动 | 已完成（mock/espeak） | 优先级播报队列、去重、缓存、静音时段、emotion + 文字 + TTS；edge-tts 仅保留可选钩子 |
| **T08** 对话管理与多轮确认 | 已完成 | 8 轮上下文、9 工具、单槽澄清、破坏性二次确认、改口、30s 超时、Action 分发 |
| **T09** 手势与在场感知 | 已取消 | 产品改为触屏；PAJ7620、gesture 服务与相关配置已移除，手机在位仍由 T20/T21 保留 |
| **T10** 数据模型与持久化 | 已完成 | 14 张业务表 + 迁移、14 个 Repository、UTC 映射、每日备份/恢复、损坏自动回退 |
| **T11** 任务捕获 | 已完成（规则/拍照兜底） | 文本多任务抽取、字段/去重、拍照质量、确认前不入库、VLM/OCR 接口待模型 |
| **T12** 拆解与规划引擎 | 规则引擎降级已完成 | 3–7 步拆解、时长估算、EDF/精力/缓冲/休息排期、依赖、校验器、可解释理由 |
| **T13** 计划协商与确认 | 已完成 | 时间轴/列表数据、revise/conflict/undo/confirm API、UI PlanReview |
| **T14** 执行态单步引导 | 已完成 | 单步计时、完成/跳过/卡住/延长、局部重排、焦点状态落盘恢复 |
| **T15** 提醒调度 | 已完成 | at/daily/weekly/every/event、持久化、补偿、静音、语音创建 |
| **T16** 完成反馈与庆祝 | 已完成 | 三级反馈、20 条无指责文案、连续合并、夜间静音、reward.feedback |
| **T17** 养成游戏与激励 | 已完成 | 5 阶段、exp/level/streak、积分规则、不扣分、待机角标 |
| **T18** 分心坦白与画像 | 已完成 | 一句话坦白、次数/时长/高峰/Top 情境、无指责词表、统一口径 |
| **T19** 负荷检测与休息 | 已完成 | 负荷分、三级干预、休息库、2 小时免打扰、深夜加权 |
| **T20** 手机在位与充电 | 已完成（mock 验收） | 三次采样去抖、`phone.changed{at}`、phone_sessions 落库、待机角标、无传感器手动替代 |
| **T21** 手机使用时长契约 | 已完成 | study/leisure、倒计时通道、到点提醒、归位自动结束、学习可延长一次、超时落库 |
| **T22** 文件传输通道 | 已完成（设备侧） | `/upload` 页面、20MB 白名单、inbox.json、inbox.file 事件；热点脚本/二维码待硬件 |
| **T23** 应用使用回流 | P2 边界完成 | 设备端接收/Top5/隐私开关/iOS 说明；Android App 不在本仓库 |
| **T24** 用户模型与切换 | 已完成（API/DAO） | 创建/列表/切换/角色/导出/级联删除；执行态冻结待与 T14 深接 |
| **T25** 数据隔离与偏好 | 已完成 | DAO 强制 user_id、偏好模型、导出/删除、跨用户隔离测试 |
| **T26** 事件埋点与分析 | 已完成 | 15 事件白名单、device_events、7 日指标、隐私开关 |
| **T27** 周报与洞察 | 已完成 | 3 屏卡片、无数据友好文案、无指责词、文本导出；LLM 润色可选 |
| **T28** 端到端与演示 | 已完成（mock） | 主链路 e2e、flow-reset、分镜/兜底/彩排记录 |
| **T29** 稳定性与降级 | 已完成（mock/脚本） | 降级矩阵、恢复报告、错误文案、soak 脚本；真实 12h 上机待跑 |
| **T30** 打包与出厂 | 已完成（脚本/手册） | first-run wizard、upgrade、flow-backup/restore、安装手册；定制 img 未做 |
| T12 LLM 主路径 | 未实现 | 规则引擎就是 LLM 失败时的兜底路径，后续 LLM 适配器可直接复用 |

## 目录

```text
app/
├── main.py              uvicorn app.main:app 入口
├── bus/                 EventBus（asyncio + 线程安全）与 topic 常量
├── hal/                 硬件抽象层
│   ├── contracts.py     设备契约：probe/open/close/health
│   ├── mock/            无外设假实现
│   ├── real/            picamera2 / OpenCV / sounddevice / GPIO
│   ├── selftest.py      python -m hal.selftest
│   ├── daemon.py        flow-hal.service 的开机预检
│   └── status_store.py  device_status 表
├── planner/             规则拆解与规划
│   ├── estimator.py     时长估算（历史优先，规则兜底）
│   ├── rules.py         3–7 步拆解
│   ├── scheduler.py     装箱、缓冲、休息、依赖
│   ├── validator.py     重叠 / 超期 / 容量 / 依赖 / 动词校验
│   └── engine.py        RuleEngine 公共入口
├── channel/             T04 单通道
│   ├── base.py          Channel / Intent / Action / Context
│   ├── registry.py      通道注册表
│   ├── machine.py       状态机、返回栈、过载收敛
│   ├── router.py        中文工具别名与歧义单句
│   └── builtin/         clock/tasks/plan/focus/reminder/music
├── data/                T10 本地数据层
│   ├── schema.sql       14 张业务表 + device_status + schema_version
│   ├── migrate.py       幂等迁移、旧库备份
│   ├── repositories.py  14 个按 user_id 强隔离的 Repository
│   ├── mapping.py       planner dataclass ↔ UTC 行
│   ├── backup.py        每日 03:00 备份、保留 7 份
│   └── restore.py       python -m data.restore / flow-restore
├── phone/                T20 手机在位
│   ├── session_store.py 三次采样去抖 + phone_sessions
│   └── service.py       轮询 HAL、手动替代、健康状态
├── voice/                T06/T07 语音
│   ├── capture.py       3s 环形预录
│   ├── vad.py           300ms 静音断句
│   ├── asr.py           云端/Vosk/脚本降级
│   ├── tts.py           espeak/edge 钩子与缓存
│   ├── say.py           优先级播报、去重、静音
│   ├── bargein.py       打断与连续空识别提示
│   └── pipeline.py      speech.partial/final
├── capture/              T11 任务捕获
├── plan/                 T13 计划协商
├── focus/                T14 执行态
├── scheduler/            T15 提醒
├── emotion/              T16/T17 庆祝与养成
├── dialogue/             T08 多轮对话
├── analytics/            T18/T19/T26/T27 画像/负荷/指标/周报
├── users/                T24/T25 用户与偏好
├── setup/                T30 首次开机
├── demo/                 T28 演示重置
├── recovery.py            T29 恢复报告
├── degrade.py             T29 降级矩阵
└── service/             T03 后端骨架
    ├── app.py           create_app / lifespan / UI 静态挂载
    ├── config.py        config.yaml + 环境变量 + .env
    ├── logging.py       JSON lines + trace_id
    ├── ws.py            /ws、state.sync、错误回包
    ├── runtime.py       db → hal → phone → channel → voice → scheduler → ws
    ├── db.py            T10 FlowDatabase 适配器
    └── api.py           /healthz、/api/intent、/api/channel/current、UI 静态回退
ui/                      T05 React 前端
├── src/tokens/          颜色、字号、动效令牌
├── src/ws/              自动重连客户端
├── src/state/           单一 reducer
├── src/components/      FaceExpression / StepCard / ProgressRing / PhoneBadge ...
├── src/pages/           Idle / ... / ChannelView / Settings
└── dist/                构建产物；后端和 kiosk 直接使用
deploy/                  systemd、kiosk、flow-diag、显示配置
scripts/flow-restore     T10 一键恢复命令
install.sh               T01 一键安装脚本
config.yaml              默认配置（可被 FLOW_* 覆盖）
.env.example              密钥模板；真实 .env 被 gitignore
tests/                   181 个 Python 测试 + ui 27 个前端测试
```

## 运行

### 测试

```powershell
cd Flow
python -m pytest -q -p no:cacheprovider
```

普通开发机直接 `python -m pytest -q` 即可。本仓库的测试 fixtures 会把临时
文件写到 `.test_tmp/`（已被 `.gitignore` 忽略），避免在部分 Windows 沙箱
环境中被临时目录权限挡住。

### 后端服务

```powershell
cd Flow
$env:PYTHONPATH = "app"
$env:FLOW_HAL = "mock"
python -m service
# 或者：uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

验证：

```powershell
curl.exe -s http://127.0.0.1:8000/healthz
# {"status":"ok",...,"subsystems":{"db":...,"hal":...,"scheduler":...,"phone":...,"voice":...,"websocket":...}}
```

- `/` 优先返回 `ui/dist` 的正式界面；没有构建产物时回退到 `app/service/placeholder.html`。
- `/ws` 连接后立即收到 `state.sync`；非法 JSON 返回 `error` 且连接不断。
- `WEB_CONCURRENCY`/`UVICORN_WORKERS > 1` 会被拒绝；事件总线和调度器必须单进程。
- `scheduler` 在配置启用时为 `ok`；T15 提醒调度已落地，未启用时显示 `disabled`。
- `voice` 未配置云端 ASR 或 Vosk 模型时为 `disabled`，不阻塞其他子系统。
- `phone` 是 T20 会话服务；无支架传感器时为 `disabled`，可用手动接口替代。

### T04 通道与意图路由

```powershell
curl.exe -s http://127.0.0.1:8000/api/channel/current
curl.exe -s -X POST http://127.0.0.1:8000/api/intent `
  -H "Content-Type: application/json" `
  -d '{\"text\":\"打开专注计时器 10 分钟\"}'
```

- 6 个通道：clock / tasks / plan / focus / reminder / music
- 任意时刻只有一个 active；切换先 `exit` 再 `enter`
- 返回栈最多 3 层；`channel.enter` / `channel.exit` 通过 WS 广播
- 30 分钟内切换达到阈值（默认 12）会在快照 hints 里提示收敛
- `speech.final` 进入 `ChannelService` 的意图路径。

### T10 数据与备份

```powershell
# 默认数据库和备份目录
$env:FLOW_DB = "data/flow.db"
$env:PYTHONPATH = "app"
python -m data.restore --list
python -m data.restore --latest
```

- 14 张业务表 + `device_status` + `schema_version`
- 启动时自动迁移；旧库升级前先备份
- `data/backup/flow-*.db` 保留 7 份，每日 03:00 自动备份
- 所有 Repository 强制 `user_id`；A 用户读不到 B 用户数据
- 数据库损坏时自动尝试最近备份；恢复失败会在 `/healthz` 明确报错

### T20 手机在位

```powershell
curl.exe -s -X POST http://127.0.0.1:8000/api/phone/manual `
  -H "Content-Type: application/json" `
  -d '{\"present\":true,\"charging\":true,\"current_ma\":420}'
```

- 支架轮询 100ms，连续 3 次采样一致才切换，避免抖动产生虚假会话
- `phone.changed` 增加 `at`；`phone_sessions` 写入放上/取下时间
- 待机页右上角显示“手机在架 / 充电中 / 不在架”
- 无传感器时用 `/api/phone/manual` 或语音替代，不报错

### T06 语音输入

```powershell
# 云端 ASR（返回 {"text": "...", "confidence": 0.9} 的 HTTP JSON 端点）
$env:FLOW_ASR_URL = "https://your-asr.example/recognize"
$env:FLOW_ASR_KEY = "..."

# 或离线 Vosk（模型目录需自行下载）
$env:FLOW_VOSK_MODEL = "D:\\models\\vosk-model-small-cn"
```

- 16kHz mono、3 秒环形预录、300ms 静音断句、30 秒上限
- `SpeechPipeline` 发布 `speech.started` / `speech.partial` / `speech.final`
- 云端连续失败后切 Vosk；两者都没有时 `voice=disabled`
- 播报时暂停拾音，检测到能量可 `audio_out.stop()` 并发布 `speech.barge_in`
- 连续 3 次空识别发布 `speech.empty`，提示“没听清，可以说慢一点”
- 默认不落盘原始音频

### T05 前端

```powershell
cd Flow/ui
npm.cmd install
npm.cmd run dev       # http://127.0.0.1:5173，/ws 代理到 8000
npm.cmd test          # 27 个 reducer / ws / 页面测试
npm.cmd run build     # 生成 ui/dist，后端自动挂载
```

生产不需要 Node：`ui/dist` 是构建产物，`install.sh` 会把它一起复制到
`/opt/flow/ui/dist`。kiosk 仍然访问 `http://127.0.0.1:8000/`。

### HAL 自检

```powershell
cd Flow/app
$env:FLOW_HAL = "mock"
python -m hal.selftest --audio-seconds 1.0

# T01 的 flow-hal.service 使用的入口：
python -m hal.daemon --audio-seconds 1.0
```

也可以从仓库根目录运行：

```powershell
$env:PYTHONPATH = "app"
$env:FLOW_HAL = "mock"
python -m hal.selftest --audio-seconds 1.0 --db data/flow.db
```

输出逐项 `OK / FAIL / SKIP`。结果同时写入 `device_status` 表；默认库位置是
仓库根目录的 `data/flow.db`。常用环境变量：

| 变量 | 作用 |
| --- | --- |
| `FLOW_HAL` | `mock` / `real` / `auto`；未配置时非树莓派环境回退 mock，树莓派自动探测 |
| `FLOW_DB` | 显式指定 SQLite 路径 |
| `FLOW_DATA_DIR` | 数据目录，默认 `<repo>/data` |
| `FLOW_PHONE_PRESENT_PIN` | 在位霍尔/微动 GPIO，默认 **27** |
| `FLOW_PHONE_CHARGE_PIN` | 可选充电检测 GPIO |
| `FLOW_INA219_ADDR` | INA219 I2C 地址，默认 `0x40` |
| `FLOW_PHONE_POLL_MS` | 支架轮询周期，默认 100 ms |
| `FLOW_CONFIG` | 显式指定 config.yaml |
| `FLOW_ENV_FILE` | 显式指定 .env |

`auto` 会逐设备尝试真实驱动，失败后回退到 mock，并把原因记录在
`Hal.fallbacks`。

### 触屏交互

产品已改为 720×720 触屏，手势输入已移除。UI 的通道/计划/执行按钮通过同源
`fetch` 调用 `/api/intent`、`/api/plan/{id}/confirm`、`/api/focus/control`；
语音仍通过 T06/T04 进入同一套后端动作。手机在位与充电契约属于 T20/T21，独立
于触屏。

### 规划引擎

```powershell
cd Flow/app
python -m planner          # 人读演示
python -m planner --json   # 机器可读
```

代码内调用：

```python
from datetime import date
from planner import RuleEngine, Task, Prefs

engine = RuleEngine(Prefs())
steps = engine.decompose(Task(id="t1", title="写 3000 字论文"))
draft = engine.plan(date(2026, 11, 8), [Task(id="t1", title="写 3000 字论文")])
assert engine.last_validation.ok
```

## T01 验收对照

- `sudo bash install.sh --display hdmi720` 在树莓派上创建 `/opt/flow`、venv、systemd 单元、
  kiosk、journald 保留策略和 `flow-diag`。
- 开机顺序为 `flow-hal → flow-backend → flow-ui`；`flow-hal` 是自检预检（跑完退出），
  HAL 由 backend 进程持有，避免双开摄像头/麦克风。
- `flow-display hdmi720` 写入 720×720 HDMI 模式；`flow-display none` 可回滚。
- `flow-diag` 打包 journal、config、version、device_status、音频/摄像头/I2C 状态，
  不包含 `.env`。
- 断电重启 90 秒、中文渲染、离线启动这几项必须在真实树莓派上验收，步骤见
  [硬件手册](docs/deployment/T01-hardware-runbook.md)；团队分工、物料、测试矩阵和
  签收表见 [硬件交接说明](docs/deployment/T01-hardware-handoff.md)；T05 触屏增量见
  [T05 硬件增量](docs/deployment/T05-hardware-handoff.md)。

## T02 验收对照

- `python -m hal.selftest` 逐设备输出 `OK / FAIL / SKIP` 及原因，失败也继续跑完。
- `FLOW_HAL=mock` 下五个设备全部可用：显示、摄像头、麦克风、扬声器、支架。
- mock 摄像头返回真实 JPEG；麦克风持续输出 16 kHz mono PCM；支架变化通过
  `phone.changed` 在 300 ms 内发出（默认 100 ms 轮询）。
- 运行中 `camera.unplug()` 后 `capture()` 返回 `None`、`health()` 为
  `missing`，其他设备和服务不受影响。
- 自检失败会写入 `device_status`，上层可用 `Hal.faulted_devices()` 渲染故障图标。

## T03 验收对照

- `curl /healthz` 返回 200，包含版本、启动时间、uptime 及 db/hal/scheduler/phone/voice/websocket 状态。
- WS 连接后立即收到 `state.sync`（远小于 10 秒）。
- 非法 JSON / 非法消息结构返回 `error`，连接不关闭。
- `ctrl-c`/systemd `SIGINT` 触发 lifespan 逆序关闭：ws → scheduler → voice → channel → phone → backup → hal → db → bus。
- JSON lines 日志默认带 `trace_id`；HTTP 请求会回显 `X-Trace-ID`。
- 单 worker 由 `ensure_single_worker()` 和 systemd `--workers 1` 双重保证。

## T04 验收对照

- 6 个通道可注册、列举；激活 clock 后 `GET /api/channel/current` 只返回 clock。
- 切换到 tasks 时先发 `channel.exit` 再发 `channel.enter`，不并存。
- 返回栈最多 3 层；`channel.enter` / `channel.exit` 通过 WS 广播。
- `POST /api/intent` 的 `open_tool` 路由打开 focus 并传入分钟数；歧义只回复一句。
- 通道 handler 人为抛异常时回到 idle，并发布 error / 播报兜底。
- 30 分钟窗口内切换达到阈值会返回过载 hint；阈值可配置。

## T05 验收对照

- 7 个页面随 `ui.phase` 切换；`Settings` 是额外设计系统页，不影响主流程。
- `state.sync` 恢复完整状态；断线保留最后画面并显示离线角标，重连后重新同步。
- 720×720 画布按实际窗口 `min(w/720,h/720)` 缩放；800×480、720×720、1024×600
  均不溢出（浏览器截图验证）。
- 正文 ≥30px、步骤 48px，中文长标题 `overflow-wrap + line-clamp`，无横向滚动。
- 执行态只有 `StepCard + ProgressRing + 剩余时间`，不显示任务列表。
- 页面主操作使用大尺寸触屏按钮；语音和触屏最终走同一套后端动作。

## T09 范围变更

- T09 手势方案已取消；手机在位/充电仍由 T20/T21 保留。

## T06 验收对照

- 16kHz mono 音频进入 3 秒环形预录，VAD 以 300ms 静音断句，单句上限 30 秒。
- `speech.partial` / `speech.final` 事件可被总线订阅；final 文本进入 T04 路由。
- 云端 ASR 失败后切 Vosk；没有配置时 voice 子系统 disabled，不影响其他服务。
- 播报时默认暂停拾音；检测到能量调用 `audio_out.stop()` 并发布 `speech.barge_in`。
- 连续空识别达到阈值发布 `speech.empty`；原始音频不落盘。
- 真实识别准确率、1.5 秒延迟和 5 分钟稳定性需要真实麦克风 + ASR 模型验收。

## T10 验收对照

- 空库启动自动建 14 张业务表；重复迁移幂等；`schema_version` 只保留当前版本。
- 进程退出/重启后 WAL 已提交数据仍可读。
- 备份 → 破坏 → `flow-restore --latest` 恢复后数据一致。
- 所有 Repository 强制 user_id；A 用户不能读/改 B 用户的数据。
- 数据库损坏时自动尝试最近备份；恢复失败在健康检查中明确报错。
- 每日 03:00 备份保留 7 份；库内时间统一 UTC，展示层 Asia/Shanghai。

## T20 验收对照

- 支架连续 3 次采样一致才切换；抖动不会产生大量 phone_sessions。
- 放上/取下在轮询周期内更新，`phone.changed` 包含 `at`。
- `phone_sessions` 写入开始/结束时间，可供 T21/T18 使用。
- 待机页右上角显示在架/充电；无传感器时 `/api/phone/manual` 可替代且不报错。
- 真实充电识别 20 次 ≥95% 需要上机验收。

## T07/T08/T11/T13–T19/T21–T30 验收摘要

- **T07**：15 字短句走缓存/本地；同文本 5 秒去重；22:00–07:00 只发文字+emotion；
  TTS 失败不阻塞；播报队列高优先级可打断。
- **T08**：9 工具固定；缺槽位只问一句；删除/清空需二次确认；30 秒超时回 idle；
  “打开计时器然后提醒我喝水”能拆成两个 Action。
- **T11**：一句三任务可拆；取消确认不写库；标题+截止时间去重；拍照失败可重拍；
  VLM/OCR 不可用时使用规则草稿。
- **T13**：revise 触发重叠时返回 conflict 而非静默保存；confirm 立即启动首步；
  undo 回到上一版；PlanReview 由 plan.draft/plan.revised 驱动。
- **T14**：执行态只发单步；完成/跳过/卡住/延长/重排 API 可用；连续两次卡住缩成
  5 分钟版本；`data/focus_state_<user>.json` 支持重启恢复。
- **T15**：at/daily/weekly/every/event 五类；DB 重启恢复；>2h 错过合并；夜间静音
  由 T07 执行；语音“每天 7 点提醒我背单词”可创建。
- **T16/T17**：小步/任务/里程碑三级反馈；20 条无指责文案；连续 5 次合并；深夜降级；
  经验/等级/连续天数落库，不扣分；待机页显示角色阶段。
- **T18/T19**：坦白一句话落库；7 日次数/时长/高峰/Top 情境；负荷分三级干预；
  “知道了”后 2 小时免打扰；休息库可回到原步骤。
- **T21**：study 默认 15、leisure 默认 10；到点发布 overdue 并提醒；放回结束；
  study 可延长一次；超时写入 returned_on_time=false。
- **T22/T23**：`/upload` 单页、20MB、扩展名白名单、inbox.json、inbox.file；使用
  数据默认关闭，关闭后拒绝接收；iOS 明确不支持。
- **T24/T25**：用户创建/切换/角色/导出/级联删除；DAO 强制 user_id；切换时重绑
  capture/plan/focus/companion/analytics/phone/scheduler 和 channel context。
- **T26/T27**：15 个白名单事件；device_events + 7 日指标；隐私开关；周报三屏、
  无数据友好文案、文本导出；不出现指责词。
- **T28/T29/T30**：`tests/test_e2e.py` 主链路；`flow-reset`；降级矩阵/恢复报告/
  soak 脚本；first-run wizard、upgrade、flow-backup/restore、安装手册。

## T12 验收对照

- 五条杂乱任务排期不重叠、不超截止、总时长不超可用时段；20% 缓冲与
  45–50 分钟休息节奏已实现。
- 每步 15–45 分钟、动词开头、第一步 ≤20 分钟，由校验器逐条检查。
- “写 3000 字论文”首步固定为“打开文档，列出 3 个核心论点”。
- 规则引擎单次规划远低于 3 秒，无网络依赖。
- `validate_plan()` 可拦截人为注入的 `overlap`、`overdue`、
  `outside_available`、`capacity_exceeded`、`break_overlap`、
  `dependency_violation` 等问题。

## 与后续任务的接口

- **T10 → T26/T15**：`data.repositories` 已接管业务表；T26 指标和 T15 提醒直接使用
  `Repositories.metrics` / `Repositories.reminders`，不要写裸 SQL。
- **T12 LLM**：LLM 适配器实现同样的 `decompose` / `plan` 返回结构，异常或
  超时后调用 `RuleEngine`；规则结果可直接通过 `validate_plan()` 复核。
- **T13 / T14 / T16**：在 `ui/src/state/reducer.ts` 增加事件类型，在
  `PAGE_MAP` / `ChannelView` 增加页面即可；UI 不持有业务状态。
- **T09**：已取消，不再提供手势或 ToF 距离输入；触屏按钮和语音是主交互。
- **T20 / T21 / T15**：支架会话已落库；手机使用契约、提醒调度分别接
  `phone_sessions`、`service/scheduler_service.py`。
- **T06 硬件**：云端 ASR 的请求格式是 `{audio: base64, encoding, sample_rate,
  channels}` → `{text, confidence}`；Vosk 模型目录由 `FLOW_VOSK_MODEL` 指定。
