# 心流 Flow 开发说明

本文件记录当前已落地的软件任务与验证方法。任务卡原文在
[`docs/software-task-slices/tasks/`](docs/software-task-slices/tasks/)。

## 当前实现范围

| 任务 | 状态 | 说明 |
| --- | --- | --- |
| **T02** HAL 与开机自检 | 已完成（mock 优先） | 设备契约、mock/real 适配、`python -m hal.selftest`、`device_status` 落库、`phone.changed` 事件 |
| **T12** 拆解与规划引擎 | 规则引擎降级已完成 | 3–7 步拆解、时长估算、EDF/精力/缓冲/休息排期、依赖、校验器、可解释理由 |
| T12 LLM 主路径 | 未实现 | 规则引擎就是 LLM 失败时的兜底路径，后续 LLM 适配器可直接复用 |
| T01 / T03 / T10 | 由对应任务负责 | 当前用最小本地事件总线和独立 dataclass 模型，接口已按任务卡预留 |

## 目录

```text
app/
├── bus/                最小线程安全事件总线（T03 可替换）
├── hal/                硬件抽象层
│   ├── contracts.py    设备契约：probe/open/close/health
│   ├── mock/           无外设假实现
│   ├── real/           picamera2 / OpenCV / sounddevice / GPIO
│   ├── selftest.py     python -m hal.selftest
│   └── status_store.py device_status 表
└── planner/            规则拆解与规划
    ├── estimator.py    时长估算（历史优先，规则兜底）
    ├── rules.py        3–7 步拆解
    ├── scheduler.py    装箱、缓冲、休息、依赖
    ├── validator.py    重叠 / 超期 / 容量 / 依赖 / 动词校验
    └── engine.py       RuleEngine 公共入口
tests/                  61 个单元测试
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

### HAL 自检

```powershell
cd Flow/app
$env:FLOW_HAL = "mock"
python -m hal.selftest --audio-seconds 1.0
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
| `FLOW_HAL` | `mock`（默认，非树莓派）/ `real` / `auto` |
| `FLOW_DB` | 显式指定 SQLite 路径 |
| `FLOW_DATA_DIR` | 数据目录，默认 `<repo>/data` |
| `FLOW_PHONE_PRESENT_PIN` | 在位微动开关 GPIO，默认 17 |
| `FLOW_PHONE_CHARGE_PIN` | 可选充电检测 GPIO |
| `FLOW_INA219_ADDR` | INA219 I2C 地址，默认 `0x40` |
| `FLOW_PHONE_POLL_MS` | 支架轮询周期，默认 100 ms |

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

## T02 验收对照

- `python -m hal.selftest` 逐设备输出 `OK / FAIL / SKIP` 及原因，失败也继续跑完。
- `FLOW_HAL=mock` 下六个设备全部可用：显示、摄像头、麦克风、扬声器、支架、手势。
- mock 摄像头返回真实 JPEG；麦克风持续输出 16 kHz mono PCM；支架变化通过
  `phone.changed` 在 300 ms 内发出（默认 100 ms 轮询）。
- 运行中 `camera.unplug()` 后 `capture()` 返回 `None`、`health()` 为
  `missing`，其他设备和服务不受影响。
- 自检失败会写入 `device_status`，上层可用 `Hal.faulted_devices()` 渲染故障图标。

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

- **T03**：把 `LocalEventBus` 换成正式总线即可；HAL 只依赖
  `EventPublisher.publish(topic, payload)`。
- **T10**：`planner.models.Task` / `SubTask` / `Prefs` 是纯 dataclass，可在
  DAO 层做映射；`HistoryProvider.median_minutes()` 用于历史耗时校准。
- **T12 LLM**：LLM 适配器实现同样的 `decompose` / `plan` 返回结构，异常或
  超时后调用 `RuleEngine`；规则结果可直接通过 `validate_plan()` 复核。
- **T09 / T20**：手势和支架真实驱动已在 `hal/real/` 留好接线点。
