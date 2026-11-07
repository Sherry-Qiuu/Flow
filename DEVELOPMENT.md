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
| **T12** 拆解与规划引擎 | 规则引擎降级已完成 | 3–7 步拆解、时长估算、EDF/精力/缓冲/休息排期、依赖、校验器、可解释理由 |
| T12 LLM 主路径 | 未实现 | 规则引擎就是 LLM 失败时的兜底路径，后续 LLM 适配器可直接复用 |
| T05 / T10 等 | 由对应任务负责 | 当前 UI 是占位页；数据库只有连接与 WAL，没有业务表 |

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
└── service/             T03 后端骨架
    ├── app.py           create_app / lifespan
    ├── config.py        config.yaml + 环境变量 + .env
    ├── logging.py       JSON lines + trace_id
    ├── ws.py            /ws、state.sync、错误回包
    ├── runtime.py       db → hal → scheduler → ws 生命周期
    ├── db.py            SQLite 连接与 WAL（T10 会替换）
    └── api.py           /healthz、REST 错误结构、占位页
deploy/                  systemd、kiosk、flow-diag、显示配置
install.sh               T01 一键安装脚本
config.yaml              默认配置（可被 FLOW_* 覆盖）
.env.example              密钥模板；真实 .env 被 gitignore
tests/                   100 个单元测试
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
# {"status":"ok","version":"0.1.0",...,"subsystems":{"db":...,"hal":...,"scheduler":...,"websocket":...}}
```

- `/` 是 T05 之前的占位页，会自动连 `/ws`，并显示离线/重连状态。
- `/ws` 连接后立即收到 `state.sync`；非法 JSON 返回 `error` 且连接不断。
- `WEB_CONCURRENCY`/`UVICORN_WORKERS > 1` 会被拒绝；事件总线和调度器必须单进程。
- `scheduler` 当前是 `disabled`，这是 T15 尚未实现的预期状态。

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

- `sudo ./install.sh --display hdmi720` 在树莓派上创建 `/opt/flow`、venv、systemd 单元、
  kiosk、journald 保留策略和 `flow-diag`。
- 开机顺序为 `flow-hal → flow-backend → flow-ui`；`flow-hal` 是自检预检（跑完退出），
  HAL 由 backend 进程持有，避免双开摄像头/麦克风。
- `flow-display hdmi720` 写入 720×720 HDMI 模式；`flow-display none` 可回滚。
- `flow-diag` 打包 journal、config、version、device_status、音频/摄像头/I2C 状态，
  不包含 `.env`。
- 断电重启 90 秒、中文渲染、离线启动这几项必须在真实树莓派上验收，步骤见
  [硬件手册](docs/deployment/T01-hardware-runbook.md)。

## T02 验收对照

- `python -m hal.selftest` 逐设备输出 `OK / FAIL / SKIP` 及原因，失败也继续跑完。
- `FLOW_HAL=mock` 下六个设备全部可用：显示、摄像头、麦克风、扬声器、支架、手势。
- mock 摄像头返回真实 JPEG；麦克风持续输出 16 kHz mono PCM；支架变化通过
  `phone.changed` 在 300 ms 内发出（默认 100 ms 轮询）。
- 运行中 `camera.unplug()` 后 `capture()` 返回 `None`、`health()` 为
  `missing`，其他设备和服务不受影响。
- 自检失败会写入 `device_status`，上层可用 `Hal.faulted_devices()` 渲染故障图标。

## T03 验收对照

- `curl /healthz` 返回 200，包含版本、启动时间、uptime 及 db/hal/scheduler/websocket 状态。
- WS 连接后立即收到 `state.sync`（远小于 10 秒）。
- 非法 JSON / 非法消息结构返回 `error`，连接不关闭。
- `ctrl-c`/systemd `SIGINT` 触发 lifespan 逆序关闭：ws → scheduler → hal → db → bus。
- JSON lines 日志默认带 `trace_id`；HTTP 请求会回显 `X-Trace-ID`。
- 单 worker 由 `ensure_single_worker()` 和 systemd `--workers 1` 双重保证。

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

- **T10**：用 DAO 替换 `service.db.Database`；`planner.models.Task` / `SubTask` /
  `Prefs` 是纯 dataclass，可直接映射；`HistoryProvider.median_minutes()` 用于历史耗时校准。
- **T05**：把 `app/service/placeholder.html` 换成正式 React 构建产物或静态挂载；
  `/ws` 的 `state.sync` 协议已经可用。
- **T12 LLM**：LLM 适配器实现同样的 `decompose` / `plan` 返回结构，异常或
  超时后调用 `RuleEngine`；规则结果可直接通过 `validate_plan()` 复核。
- **T09 / T20 / T15**：手势、支架真实驱动、提醒调度分别在 `hal/real/`、
  `service/scheduler_service.py` 留有接线点。
