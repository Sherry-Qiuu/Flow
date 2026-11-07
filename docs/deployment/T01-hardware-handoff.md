# Flow 硬件交接说明书（T01 / T02）

> **适用对象**：负责采购、接线、装配、上机测试的同学，以及负责软件联调和最终验收的同学。
>
> **关联任务**：[T01 设备镜像与运行基座](../software-task-slices/tasks/P0-必做/T01-设备镜像与运行基座.md)、
> [T02 硬件抽象层 HAL 与开机自检](<../software-task-slices/tasks/P0-必做/T02-硬件抽象层 HAL 与开机自检.md>)
>
> **执行手册**：[T01 硬件落地手册](T01-hardware-runbook.md)（逐条命令、预期输出、排错）。
>
> **T05 触屏增量**：720×720 屏幕、触控与 kiosk 验收见
> [T05 触屏交接说明](T05-hardware-handoff.md)。
>
> **参考教程**：[H01 开箱](../hardware-tutorials/H01-开箱核对与工具准备.md)、[A 接线总图](../hardware-tutorials/A-接线总图与引脚分配.md)、
> [B 故障排查](../hardware-tutorials/B-故障排查手册.md)、[D 安全手册](../hardware-tutorials/D-安全手册与红线.md)。
>
> **当前状态**：软件侧 T01 部署资产 + T02 HAL/自检已完成并推到 `main`；物理装配和断电重启验收还没有在真实机器上执行。

---

## 0. 一页结论

| 谁 | 现在要做什么 | 交付什么 |
| --- | --- | --- |
| **硬件同学** | 采购/核对物料，按 A 接线，按 H01–H09 装配，按本文第 5、6 节上机 | 一台能开机、能显示、能拍照、能录音/放音、能感知手机的整机 + 验收证据 |
| **软件同学** | 提供镜像/安装脚本、`flow-hal`/`flow-backend`/`flow-ui`、诊断命令；配合联调 | 可重复安装的服务、日志、`flow-diag` 包、问题定位 |
| **共同** | 按第 6 节测试矩阵逐项验收，按第 8 节签收 | 签字的交接单、`flow-diag` 包、已知问题清单 |

**交接完成的定义**：

1. `flow-hal` 预检 6 个设备项有明确结果（OK / FAIL / SKIP），失败项有记录。
2. `flow-backend` 的 `/healthz` 返回 200，`db`/`hal`/`scheduler`/`websocket` 状态可见。
3. `flow-ui` 能在目标屏上显示 720×720 画布，中文无方块。
4. 断电重启 90 秒内自动进入界面；断网仍能启动。
5. `flow-diag` 生成的包已交给软件同学，里面能看出硬件状态。
6. 验收表（第 9 节）签字，未完成项写清责任人和下次检查时间。

> **重要原则**：硬件同学不需要改 Python 代码；如果必须改针脚/设备地址，只改
> `/opt/flow/.env` 并通知软件同学，不要直接改仓库源码。

---

## 1. 交接边界：软件已经给了什么，硬件还要做什么

### 1.1 软件侧已交付

| 能力 | 位置/命令 | 交接说明 |
| --- | --- | --- |
| 一键安装 | [`install.sh`](../../install.sh) | 装 venv、依赖、systemd、kiosk、日志、诊断 |
| systemd 服务组 | [`deploy/systemd/`](../../deploy/systemd/) | hal 预检 → backend → ui |
| HAL mock + real | [`app/hal/`](../../app/hal/) | 摄像头/麦克风/扬声器/屏幕/支架 |
| 开机自检 | `python -m hal.selftest` / `python -m hal.daemon` | 逐设备 OK/FAIL/SKIP，写 `device_status` |
| 后端骨架 | `uvicorn app.main:app`、`/healthz`、`/ws` | T03：健康检查、状态同步、事件总线 |
| 显示/kiosk | `flow-display`、`flow-kiosk` | 720×720 HDMI 模式、Chromium 全屏 |
| 诊断包 | `sudo flow-diag` | journal、config、版本、设备状态、硬件探测 |
| 上机手册 | [T01 硬件落地手册](T01-hardware-runbook.md) | 逐条命令和预期输出 |

### 1.2 硬件侧需要交付

| 工作包 | 内容 | 对应教程 | 完成标志 |
| --- | --- | --- | --- |
| **WP1 电源与基础** | 12V 电池、5V/5A 降压、Pi 5、SD、散热、HDMI 屏 | H01/H02/H03/H09 | 电池供电可开机，`vcgencmd get_throttled` 为 `0x0` |
| **WP2 显示与结构** | 7" 屏、HDMI/micro-HDMI、外壳、支架、铰链 | H09 | 720×720 显示，屏幕固定可靠 |
| **WP3 感知** | CSI 摄像头、A3144 霍尔、INA219 | H04/H07/H08 | 拍照清晰、手机在位可感知 |
| **WP4 音频/反馈** | USB 麦克风、USB 音箱、STOP 按钮、振动马达 | H04/H05 | 录音/放音正常，按钮按下有响应（软件集成见 T04/T16） |
| **WP5 整机联调** | 装壳、理线、上电、跑 T01/T02 验收 | H10 + 本文 | 第 6 节测试矩阵全绿，`flow-diag` 已归档 |

### 1.3 角色与签字

| 角色 | 姓名/联系方式 | 负责 |
| --- | --- | --- |
| 硬件负责人 | ______ | BOM、接线、装配、上机证据 |
| 软件联调负责人 | ______ | 安装、服务、日志、代码问题 |
| 验收人 | ______ | 按测试矩阵签字，判定通过/有条件通过 |
| 指导/产品 | ______ | 需求取舍、演示排期 |

> 交接时至少 **2 人** 在场：一人操作，一人按表核对并记录。

---

## 2. 物料清单与缺口

完整清单见 [H01 开箱核对](../hardware-tutorials/H01-开箱核对与工具准备.md)。下面只列交接必须确认的项目。

### 2.1 核心件

| 类别 | 物品 | 数量 | 关键检查 |
| --- | --- | --- | --- |
| 计算 | 树莓派 5（4GB+，4B 也可） | 1 | 板子无磕碰，散热片/风扇先装 |
| 存储 | microSD 32GB A2 | 1 | **套件可能只给读卡器，没给卡**；确认容量和 A2 |
| 电源 | 5.1V/5A PD 电源 | 1 | Pi 5 调试必须；电池方案另配 5V/5A 降压 |
| 显示 | 7" HDMI/DSI 屏 | 1 | 记下型号、分辨率、接口；优先 HDMI |
| 视频 | micro-HDMI 转 HDMI 线 | 1 | Pi 5 是 micro-HDMI |
| 摄像头 | IMX219 CSI + 22 针 FPC | 1 | **Pi 5 用 22 针，不是 12 针/15 针** |
| 音频 | USB 麦克风 + USB 小音箱 | 各 1 | 免驱，`arecord -l` / `aplay -l` 能看到 |
| 输入 | 720×720 触屏 | 1 | HDMI/DSI + 触控 USB |
| 感知 | A3144 霍尔 ×2 | 2 | 手机在位/磁吸；必须 10kΩ 上拉 |
| 感知 | INA219（充电电流） | 1 | I2C 0x40；无线充电流检测用 |
| 交互 | 12mm 自复位金属按钮 | 1 | STOP；GPIO17 |
| 反馈 | 1027 振动马达 + S8050 + 1N4148 | 1 套 | 不能直连 GPIO，必须三极管 + 续流二极管 |
| 结构 | 外壳、铰链、硅胶包边、VHB、磁铁、铜柱/螺丝 | 1 套 | 按 H09 尺寸，磁铁建议 10×3mm |
| 电源 | 12V 电池 + DC 降压 + DC 母座 + 开关 | 1 套 | 万用表量电压，正负极不能反 |
| 无线充 | 无线充模块 + 铁氧体隔磁片 | 1 套 | 必须隔磁片，线圈旁不能有金属 |
| 工具 | 万用表、剥线钳、杜邦线、面包板、扎带 | 1 套 | **万用表是硬性要求** |

### 2.2 已知缺口/易漏买

按 H01 的核对结果，重点确认：

- [ ] microSD 卡（套件可能没有）
- [ ] 1N4148/1N4007 续流二极管（清单常漏）
- [ ] 无线充铁氧体隔磁片
- [ ] Type-C 公对公数据线（电池→Pi）
- [ ] DC5.5×2.1 公头带线
- [ ] 更大的强磁铁（D10×3mm，原 D3×3mm 吸不住手机）
- [ ] M2.5×4+10 铜柱（原 4+6 可能不够）
- [ ] 10kΩ（霍尔上拉）和 1kΩ（三极管基极）电阻
- [ ] 若用 USB 摄像头：确认安装时加 `--with-opencv`

### 2.3 安全红线

- **断电再插拔** CSI 排线、HDMI、杜邦线；不要带电插拔。
- **5V 绝对不能接 GPIO**；传感器只用 3.3V。
- 电池正负极先量再插；降压输出先空载调到 5.1V 左右再接 Pi。
- 无线充线圈旁不要放金属；必须贴隔磁片。
- 振动马达必须并联续流二极管，否则会烧三极管/GPIO。
- 装壳前先在工作台上跑通全部外设，不要先封壳。

---

## 3. 系统架构与接口

```text
                 ┌──────────────────────────────┐
                 │  flow-ui.service             │
                 │  Xorg + openbox + Chromium   │
                 │  http://127.0.0.1:8000       │
                 └──────────────┬───────────────┘
                                │ WebSocket /ws
                 ┌──────────────▼───────────────┐
                 │  flow-backend.service        │
                 │  FastAPI :8000               │
                 │  EventBus / state.sync       │
                 │  持有 HAL（摄像头/音频/GPIO） │
                 └──────────────┬───────────────┘
                                │ Python HAL
      ┌──────────────┬──────────┼──────────┬──────────────┐
      │              │          │          │              │
   HDMI 屏        CSI 摄像头   USB 音频   GPIO27/INA219
   720×720        22 针 FPC    麦克风/音箱  手机在位/充电
```

### 3.1 服务与端口

| 项目 | 值 |
| --- | --- |
| 后端地址 | `http://127.0.0.1:8000` |
| 健康检查 | `GET /healthz` |
| 系统状态 | `GET /api/system/status` |
| 实时通道 | `WS /ws`，连接后立即收到 `state.sync` |
| 数据库 | `/opt/flow/data/flow.db`（WAL） |
| 配置 | `/opt/flow/config.yaml` |
| 密钥 | `/opt/flow/.env`（权限 600，禁止入库） |
| 安装根目录 | `/opt/flow/` |
| 服务顺序 | `flow-hal`（预检）→ `flow-backend`（常驻）→ `flow-ui` |

### 3.2 引脚契约（硬件必须按这个接）

| 功能 | BCM | 物理脚 | 方向 | 说明 |
| --- | --- | --- | --- | --- |
| 手机在位霍尔 | **GPIO27** | **13** | 输入 | A3144 OUT；**10kΩ 上拉到 3.3V** |
| STOP 按钮 | GPIO17 | 11 | 输入 | 按钮另一端接 GND；T04 集成 |
| 振动马达 | GPIO18 | 12 | 输出 | 经 1kΩ → S8050 B；马达并联 1N4148；T16 集成 |
| 触控 USB | USB | — | 触摸输入，evtest 验证 |
| 状态灯（可选） | GPIO22 | 15 | 输出 | LED + 限位电阻 |
| 人体感应（可选） | GPIO23 | 16 | 输入 | HC-SR501 / LD2410 |
| 无线充开关（可选） | GPIO24 | 18 | 输出 | MOSFET/继电器 |
| 备用 | GPIO25 | 22 | — | 留出 |

### 3.3 软件侧使用的环境变量

硬件变更针脚/地址时，只改 `/opt/flow/.env`：

```dotenv
FLOW_HAL=real
FLOW_PHONE_PRESENT_PIN=27
FLOW_INA219_ADDR=0x40
FLOW_PHONE_POLL_MS=100
```

- `FLOW_HAL=real`：设备上必须用真实驱动；查问题时才临时改 `mock`/`auto`。
- 如果针脚改了，必须同步告诉软件同学，否则 HAL 会读错脚。
- I2C 总线默认 `/dev/i2c-1`；如果换总线，需要软件侧确认。
- USB 摄像头需要安装 `opencv-python`（`install.sh --with-opencv`）；CSI 用 picamera2。

### 3.4 当前软件能力边界（交接必须说清）

| 功能 | 现在 | 说明 |
| --- | --- | --- |
| T01 服务/kiosk/诊断 | 已交付 | 见本文第 5 节 |
| T02 HAL/自检 | 已交付（mock 全绿，真实待上机） | 真实驱动需在 Pi 上验证 |
| T03 后端/WS/健康检查 | 已交付 | scheduler/phone/voice 子系统已接入 |
| T05 正式 UI | 已交付 | React + Vite + TS + Tailwind + Motion；720 画布、8 表情、自动重连 |
| T04 STOP/工具路由 | 已交付 | 6 通道状态机/意图路由已完成；STOP 物理按钮待硬件验证 |
| T06 语音管线 | 核心已交付 | 采集/VAD/ASR 降级/打断已完成；真实 ASR 模型/云账号待配 |
| T10 数据层 | 已交付 | SQLite 14 表、迁移、DAO、备份/恢复 |
| T20 手机在位/充电契约 | 已交付（mock） | T02 GPIO/INA219 + T20 会话落库/角标；真机 20 次充电验收待做 |
| T16 振动反馈 | 未完成 | 马达可先装、可测；软件后续接 |
| T15 提醒调度 | 未完成 | 健康检查里显示 `disabled` 是正常 |

> 交接时不要把“硬件装好”说成“功能全部完成”。T01/T02 验收和 T16/STOP 硬件
> 仍需上机；T04/T06/T10/T20 的软件部分已交付，真机参数/模型仍需联调。

---

## 4. 装配与上电顺序

**原则：先台面、后装壳；先单件、后整机；先断电、后接线。**

### Phase 0 · 开箱与安全（30 分钟）

1. 按 H01 核对物料，填缺口清单。
2. 装 Pi 5 散热片/风扇；不要裸板长时间跑。
3. 万用表测电池、降压输出；确认 5V 和 GND 不短路。
4. 读 [D 安全手册](../hardware-tutorials/D-安全手册与红线.md)。

### Phase 1 · 桌面最小系统（1 小时）

1. 烧录 Raspberry Pi OS Lite 64-bit Bookworm（见 [T01 手册第 2 节](T01-hardware-runbook.md#2-烧录系统)）。
2. 配主机名 `flow`、用户 `flow`、WiFi、时区、SSH。
3. 接 HDMI 屏、网线、5.1V/5A 电源，首次开机。
4. `ssh flow@flow.local`，跑 `rpicam-hello --list-cameras`、`arecord -l`、`aplay -l`、`ls /dev/i2c-*`。
5. 先不要装壳；屏幕/摄像头/音频都能在桌面看到。

**检查点**：能 SSH、能上网、能看温度、能识别摄像头/音频/I2C。

### Phase 2 · 摄像头与音频（1 小时）

1. 断电，插 CSI 22 针 FPC（注意触点方向，卡扣压紧）。
2. 上电，`rpicam-still -o /tmp/test.jpg --timeout 2000` 看图片。
3. 插 USB 麦克风/音箱，`arecord -d 3 ...` + `aplay ...` 回放。
4. 如果 USB 摄像头：安装时加 `--with-opencv`；确认 `FLOW_HAL=real` 时 selftest 能找到。

**检查点**：A4 纸 30cm 拍照文字可辨；录音 3 秒能回放。

### Phase 3 · GPIO 与支架（1–2 小时）

1. 断电，按 A 接线：
   - 霍尔 VCC→3.3V，GND→GND，OUT→GPIO27，OUT 与 3.3V 之间 10kΩ 上拉。
   - INA219 VCC→3.3V/5V（按模块），GND→GND，SDA/SCL→GPIO2/3；地址 0x40。
   - STOP：GPIO17 ↔ 按钮 ↔ GND。
   - 振动马达：GPIO18→1kΩ→S8050 B，马达接 3.3V/5V 与 C，E→GND，马达并联 1N4148。
2. 上电，`i2cdetect -y 1` 应看到 `0x40`（INA219）；触摸设备用 `evtest` 确认。
3. 用磁铁靠近/离开霍尔，确认 GPIO27 电平变化；用万用表或 gpio 测试脚本。
4. 手机放上支架，确认霍尔触发；INA219 电流读数变化。

**检查点**：手机放上/拿走 2 秒内状态变化；I2C 扫描稳定；没有 5V 进 GPIO。

### Phase 4 · 结构、无线充与整机（2–3 小时）

1. 按 H09 装屏幕、触控、摄像头、支架、电池、降压、无线充。
2. 无线充必须贴铁氧体隔磁片；线圈与金属保持距离。
3. 理线：电源线、HDMI、FPC 分开走，避免压伤；用扎带/胶带固定。
4. 装壳前再跑一次台面自检；装壳后复测屏幕/摄像头/触摸（如有）。
5. 电池供电测试：拔墙插，确认能启动且 `vcgencmd get_throttled` 为 `0x0`。

**检查点**：外壳不压排线；支架开合顺畅；手机磁吸不掉；无线充能充。

### Phase 5 · 软件安装与整机联调

按第 5 节执行。装壳后如出现摄像头/音频异常，优先怀疑排线被压/USB 松动。

---

## 5. 软件安装与联调（硬件同学照抄）

### 5.1 安装

```bash
git clone https://github.com/Sherry-Qiuu/Flow.git ~/Flow
cd ~/Flow
sudo bash install.sh --display hdmi720
```

USB 摄像头加 `--with-opencv`：

```bash
sudo bash install.sh --display hdmi720 --with-opencv
```

如果屏幕不支持 720×720 自定义模式，先不写显示配置：

```bash
sudo bash install.sh --display none
# 起来后确认原生分辨率，再试：
sudo flow-display hdmi720
```

### 5.2 配置

```bash
sudo nano /opt/flow/.env
sudo chmod 600 /opt/flow/.env
```

设备上保持：

```dotenv
FLOW_HAL=real
FLOW_PHONE_PRESENT_PIN=27
FLOW_INA219_ADDR=0x40
```

密钥只放本机 `.env`，不要发到群里/不要提交。

### 5.3 HAL 预检

```bash
sudo systemctl restart flow-hal
journalctl -u flow-hal -n 80 --no-pager
sqlite3 -header -column /opt/flow/data/flow.db \
  "select device,status,detail,checked_at from device_status order by id desc limit 12;"
```

说明：`flow-hal` 是 **oneshot 预检**，跑完自检就退出；真正的 HAL 由
`flow-backend` 常驻进程持有，避免两个进程同时抢摄像头/麦克风。

### 5.4 后端

```bash
sudo systemctl start flow-backend
systemctl status flow-backend --no-pager
curl -s http://127.0.0.1:8000/healthz | jq
```

期望：HTTP 200，`status` 为 `ok`，`subsystems` 有 `db/hal/scheduler/phone/voice/websocket`。
`scheduler` 在配置启用时为 `ok`；没配 ASR 时 `voice` 为 `disabled`，都不影响后端启动。

WebSocket：

```bash
/opt/flow/.venv/bin/python - <<'PY'
from websockets.sync.client import connect
with connect("ws://127.0.0.1:8000/ws") as ws:
    print(ws.recv())
PY
```

应收到 `state.sync`。

### 5.5 UI

```bash
sudo systemctl start flow-ui
journalctl -u flow-ui -n 80 --no-pager
```

检查：720×720、中文无方块、无鼠标指针、Ctrl+W/右键被拦截。
黑屏先 `sudo flow-display none` 回滚，再排查 HDMI。

### 5.6 诊断包

```bash
sudo flow-diag
# 需要时（先停 backend，避免设备被占用）：
sudo systemctl stop flow-backend
sudo flow-diag --with-selftest
```

输出在 `/opt/flow/data/diag/flow-diag-*.tar.gz`，不包含 `.env`。

---

## 6. 测试矩阵与证据

> 在表里填 `PASS/FAIL/BLOCKED` 和证据文件名。T01/T02 为本次交接必须通过项；
> T16/T20 只要求“硬件装好/可手动验证”；T20 软件已接入，真机充电验收另行做。

| ID | 测试 | 命令/操作 | 预期 | 结果 | 证据 |
| --- | --- | --- | --- | --- | --- |
| T01-01 | 系统启动 | 接电源/电池开机 | 90 秒内进入 Flow 界面 | | 计时视频 |
| T01-02 | 网络/SSH | `ssh flow@flow.local` | 能登录 | | 终端截图 |
| T01-03 | 服务状态 | `systemctl status flow-hal flow-backend flow-ui` | 三个服务 active | | 截图 |
| T01-04 | 健康检查 | `curl -s :8000/healthz \| jq` | 200，db/hal/scheduler/phone/voice/websocket 可见 | | JSON |
| T01-05 | WS | 5.4 的 Python 脚本 | 收到 `state.sync` | | 终端输出 |
| T01-06 | 中文 | 屏幕显示 Flow UI | 无方块/截断 | | 屏幕照片 |
| T01-07 | 分辨率 | 屏幕设置/照片 | 720×720（或 T05 设计画布） | | 照片 |
| T01-08 | 离线启动 | 拔网线重启 | 仍进入界面，显示离线/重连 | | 视频/照片 |
| T01-09 | 日志 | `journalctl -b -u flow-backend -n 100` | 无异常堆栈、无字体缺失 | | 日志 |
| T02-01 | HAL 自检 | `sudo systemctl restart flow-hal` + journal | 6 项有结果 | | journal |
| T02-02 | 摄像头 | H07 拍照命令 | 画面清晰，A4 30cm 文字可辨 | | 样张 |
| T02-03 | 麦克风 | `arecord`/`aplay` | 3 秒录音可回放 | | 录音 |
| T02-04 | 扬声器 | 播放提示音 | 有声音 | | 视频 |
| T02-05 | 手机在位 | 放上/拿走手机 | 2 秒内状态变化；事件日志可见 | | 日志/视频 |
| T02-06 | 充电电流 | 手机放上无线充 | INA219 电流变化 | | 读数 |
| T02-07 | 拔摄像头降级 | 运行中拔 CSI/USB | 服务不崩，health 显示 degraded | | 日志 |
| T20-HW | 支架结构 | 开合/磁吸/充电 | 顺畅、不掉、能充 | | 视频 |
| T05-HW | 触屏 | `evtest` + 点按 UI | 触摸坐标正确、按钮可触发 | | 照片 |
| T16-HW | 振动硬件 | 手动给 GPIO18 高电平 | 马达震动 | | 视频 |
| T04-HW | STOP 硬件 | 万用表/引脚测试 | 按下导通 | | 记录 |

**证据命名建议**：

```text
evidence/
  T01-01-boot-timing.mp4
  T01-04-healthz.json
  T01-06-screen.jpg
  T02-01-flow-hal.txt
  T02-02-camera.jpg
  T02-03-audio.wav
  T02-05-phone-event.txt
  flow-diag-YYYYmmdd-HHMMSS.tar.gz
```

---

## 7. 交接流程（建议 60 分钟）

### 7.1 会前

- [ ] 硬件负责人跑完第 5 节，填好第 6 节测试矩阵。
- [ ] 生成 `flow-diag` 包。
- [ ] 软件负责人确认仓库 `main` 最新、`/healthz` 可访问。
- [ ] 准备一台手机、磁铁、A4 纸、万用表、备用 SD 卡。

### 7.2 会中议程

1. **10 分钟**：软件演示 `/healthz`、`/ws`、`flow-hal` 自检。
2. **15 分钟**：硬件走线/结构展示，指出改过的针脚和缺口。
3. **20 分钟**：按第 6 节逐项验收，FAIL 项写清现象。
4. **10 分钟**：已知限制和后续任务（T04/T16/T20/T05）。
5. **5 分钟**：签字，确定下次复测时间。

### 7.3 交接判定

| 结论 | 条件 |
| --- | --- |
| **通过** | T01-01~09、T02-01~07 全部 PASS，证据齐全 |
| **有条件通过** | T01/T02 核心 PASS，个别非阻塞项（如触控/振动/无线充）待后续；需写责任人和日期 |
| **不通过** | 摄像头/麦克风/屏幕/电源任一核心不可用；或 5V 进 GPIO、电池反接、过热等安全问题未修复 |

### 7.4 交接包清单

- [ ] 本文档 + [T01 硬件落地手册](T01-hardware-runbook.md)
- [ ] 最新 `main` commit hash
- [ ] `flow-diag-*.tar.gz`
- [ ] `/healthz` JSON
- [ ] `flow-hal` 自检输出
- [ ] 屏幕/结构/接线照片
- [ ] 第 6 节测试矩阵（签字版）
- [ ] 已知问题/缺口清单
- [ ] 设备 `.env` 只在设备上，**不进交接包**

---

## 8. 故障处理与升级

| 现象 | 先查 | 处理 | 升级给 |
| --- | --- | --- | --- |
| 黑屏 | HDMI 线、供电、`flow-display` | `flow-display none` 回滚；换线/换口 | 硬件 |
| 中文方块 | `fc-list :lang=zh` | 重装 fonts-noto-cjk | 软件 |
| 摄像头 missing | FPC 方向/卡扣、`rpicam-hello` | 断电重插；USB 摄像头加 opencv | 硬件 |
| 麦克风/音箱 missing | `arecord -l`/`aplay -l` | 换 USB 口；确认是默认设备 | 硬件 |
| 手机在位不变化 | GPIO27、10k 上拉、共地 | 万用表测电平；确认磁铁位置 | 硬件 |
| INA219 无读数 | `i2cdetect -y 1`、0x40 | 查 SDA/SCL、供电、地址 | 硬件 |
| `flow-hal` FAIL | journal + `device_status` | 按失败设备查；触控不在 HAL，使用 evtest | 软件/硬件 |
| 后端起不来 | `journalctl -u flow-backend` | 看端口/配置/DB 权限 | 软件 |
| UI 起不来 | `journalctl -u flow-ui` | 查 xinit/openbox/chromium/tty1 | 软件 |
| 发热/重启 | `vcgencmd get_throttled`、电源 | 换 5A 电源/查降压/散热 | 硬件 |

**升级规则**：

1. 单设备失败先按 H 系列教程排错，记录命令输出。
2. 30 分钟无法定位，带 `flow-diag` + journal + 照片找软件同学。
3. 出现电池鼓包、异味、5V 进 GPIO、板子过热 >80°C：立即断电，停止交接并上报。

---

## 9. 附录 A · 打印版验收清单

```text
Flow 硬件交接验收单

设备编号：__________   日期：__________
Pi 型号：__________    SD 卡：__________
屏幕型号/分辨率：__________
摄像头：CSI / USB    麦克风/音箱：__________
参与人：硬件__________ 软件__________ 验收__________

[ ] T01-01 90 秒内进入界面（实测 ______ 秒）
[ ] T01-02 SSH 可登录
[ ] T01-03 三个服务 active
[ ] T01-04 /healthz 200
[ ] T01-05 /ws 收到 state.sync
[ ] T01-06 中文渲染正确
[ ] T01-07 分辨率 720×720
[ ] T01-08 断网仍能启动
[ ] T01-09 启动日志无异常/字体警告
[ ] T02-01 HAL 自检 6 项有结果
[ ] T02-02 摄像头拍照清晰
[ ] T02-03 麦克风录音可回放
[ ] T02-04 扬声器有声音
[ ] T02-05 手机在位 2 秒内变化
[ ] T02-06 INA219 电流变化
[ ] T02-07 拔摄像头服务不崩
[ ] T20-HW 支架/磁吸/无线充
[ ] T05-HW 触屏坐标/按钮
[ ] T16-HW 振动马达
[ ] T04-HW STOP 按钮

结论：通过 / 有条件通过 / 不通过
未完成项/责任人/日期：
________________________________________________
签字：____________________
```

## 10. 附录 B · 现场记录表

| 项目 | 记录 |
| --- | --- |
| 树莓派 IP / 主机名 | |
| Pi 型号 / 内存 | |
| SD 卡型号/容量 | |
| 屏幕型号/分辨率/接口 | |
| 摄像头型号/接口 | |
| 麦克风/音箱型号 | |
| 电池电压（空载/带载） | |
| 降压输出（空载/带载） | |
| 空闲温度 / 满载温度 | |
| 无线充型号/隔磁片 | |
| 改过的针脚/地址 | |
| 已知问题 | |

## 11. 附录 C · 交接签收

| 项目 | 签名 | 日期 |
| --- | --- | --- |
| 硬件交付 | | |
| 软件联调 | | |
| 验收 | | |
| 遗留项复测 | | |

---

## 12. 版本记录

| 日期 | 变更 | 作者 |
| --- | --- | --- |
| 2026-11-07 | 初版：T01/T02 交接边界、物料、引脚、测试矩阵、签收表 | Flow 软件组 |
