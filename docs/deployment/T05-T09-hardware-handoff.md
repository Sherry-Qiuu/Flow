# T05/T09 硬件增量交接说明

> **适用场景**：T01/T02 基础整机已经能开机、能跑 `flow-hal` 自检；现在要补上
> **T05 屏幕 UI** 和 **T09 手势/在场感知** 的硬件。
>
> **先看**：[T01/T02 硬件交接说明](T01-hardware-handoff.md)（供电、BOM、整机装配、角色分工）。
> **逐条命令**：[T01 硬件落地手册](T01-hardware-runbook.md)。
> **接线参考**：[A 接线总图](../hardware-tutorials/A-接线总图与引脚分配.md)、
> [H06 手势传感器](../hardware-tutorials/H06-手势传感器I2C.md)、
> [H09 显示屏与外壳装配](../hardware-tutorials/H09-显示屏与外壳装配.md)。

---

## 0. 一页结论

| 谁 | 需要做什么 | 交付什么 |
| --- | --- | --- |
| **硬件同学** | 固定 720×720 屏幕；把 PAJ7620 接到 I2C1；装好外壳开孔；按本文第 2、3 节测试 | 屏幕照片、`i2cdetect`、手势事件日志、签字验收表 |
| **软件同学** | 提供 `ui/dist` 与 `/healthz`、`gesture.detected`、PAJ7620 驱动；配合联调 | 构建产物、服务、日志、问题定位 |
| **共同** | 按第 4 节测试矩阵验收；按第 5 节签收 | 交接包 + 已知问题清单 |

**这次交接完成的定义**：

1. `flow-ui` 在目标屏上显示正式 T05 UI（不是占位页），720×720 画布，中文无方块。
2. 屏幕全屏、无桌面、无鼠标指针；断电重启 90 秒内进入 UI。
3. `i2cdetect -y 1` 能看到 PAJ7620 的 `0x73`。
4. 在传感器前挥手，`gesture.detected` 出现 `wave → confirm`；连续快速重复在 1.5s 内只触发一次。
5. 手机放上/拿走支架，出现 `phone_place` / `phone_take`。
6. 拔掉 PAJ7620 后，`/healthz` 里 `gesture` 变成 `disabled`，backend/UI 不崩溃。

> **当前边界**：T09 的 `approach/leave` 需要真实 ToF（VL53L0X）距离驱动；目前软件已经
> 提供 `GestureService.observe_distance(cm)` 接口，但仓库没有 ToF 驱动，BOM 里也没有
> VL53L0X。**这次只验收 PAJ7620 手势 + 手机在位**；ToF 靠近/离场另开硬件增量。
>
> T04 单通道路由已经接上：`gesture.detected` 会进入 `ChannelService`，挥手/左右挥等
> 动作可以驱动当前通道。硬件同学只需要确认事件出现，不需要等 ToF。
> T09 的 `approach/leave` 仍需 ToF 距离驱动，见 3.7。

---

## 1. 软件侧已经交付了什么

| 能力 | 位置/命令 | 说明 |
| --- | --- | --- |
| T05 正式 UI | `ui/dist/index.html` | React/Vite 构建产物；**树莓派不需要 Node** |
| UI 静态托管 | `GET /` | 后端自动挂载 `ui/dist`；没有构建时才回退占位页 |
| 设计画布 | 720×720 | 按实际窗口等比缩放，800×480 / 1024×600 也不溢出 |
| 页面 | Idle/Listening/Thinking/PlanReview/Executing/Celebrate/Resting + Settings | 由 WS `ui.phase` / `state.sync` 驱动 |
| 表情 | 8 种 | neutral/happy/listening/thinking/sleepy/excited/concerned/resting |
| 离线/重连 | `OfflineBadge` + 自动重连 | WS 断开保留最后画面，恢复后重新同步 |
| T09 检测 | `python -m gesture`、`app/gesture/` | 9 种手势 + presence/phone 状态机 |
| 真实手势驱动 | `hal/real/gesture.py` | PAJ7620 I2C1 `0x73`，Part ID `0x20` |
| 总线事件 | `gesture.detected` | `{type, action, confidence, source}` |
| 健康状态 | `/healthz` → `subsystems.gesture` | 无传感器时 `disabled`，不报错 |
| 安装 | `install.sh` | 自动复制 `ui/dist`、尝试安装 `paj7620` |

**UI 构建产物已经提交在仓库里**，所以不要在树莓派上执行 `npm install` / `npm run build`；
那会多装 200MB 依赖，而且 kiosk 只需要静态文件。

---

## 2. 屏幕增量（T05）

### 2.1 硬件

- 7 英寸 HDMI 或 DSI 屏，目标画布 720×720
  - 优先 **HDMI**：驱动风险低
  - DSI 屏需要确认原生分辨率和 dtoverlay；不要同时改 HDMI 和 DSI 配置
- Pi 5 使用 **micro-HDMI → HDMI** 线；确认插的是 HDMI0（靠近电源口的那一侧，具体以 H09 为准）
- 屏幕供电独立或从 5V 降压分路；不要从 GPIO 取 5V
- 外壳开孔、屏幕固定、排线不要被压；装壳前先裸屏验证

### 2.2 软件/显示配置

先不要执行会改启动配置的命令，先确认现有屏幕能点亮：

```bash
cd ~/Flow
sudo bash install.sh --display none
sudo systemctl start flow-backend flow-ui
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/
```

返回 `200` 后，再尝试 720×720 模式：

```bash
sudo flow-display hdmi720
sudo reboot
```

如果黑屏，回滚：

```bash
sudo flow-display none
sudo reboot
```

> `hdmi720` 会写入自定义 720×720 模式；不是所有屏幕都支持。若屏幕不支持，
> 用 `none` 回到原生分辨率，T05 画布仍按 `min(w/720,h/720)` 缩放。

### 2.3 屏幕验收

```bash
systemctl status flow-backend flow-ui --no-pager
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/
journalctl -u flow-ui -n 60 --no-pager
```

肉眼检查：

- [ ] 屏幕显示 Flow UI（大时钟、表情、底部提示），不是浏览器错误页
- [ ] 界面在 720×720 画布内，无横向/纵向滚动条
- [ ] 中文无方块、无截断；长任务标题在卡片内换行
- [ ] 全屏、无桌面、无鼠标指针；Ctrl+W / 右键不会关闭或弹出菜单
- [ ] 拔网线重启后仍能进入 UI，显示离线角标/重连状态
- [ ] 执行态只显示一个步骤 + 剩余时间，不显示任务列表

**证据**：屏幕照片、`curl` 的 HTTP 200、`journalctl -u flow-ui` 末尾 30 行。

---

## 3. 手势增量（T09）

### 3.1 接线（PAJ7620U2）

| PAJ7620 模块 | 树莓派 | 物理脚 | 注意 |
| --- | --- | --- | --- |
| VCC / V | 3.3V | 1 | **不要接 5V** |
| GND / G | GND | 6 | 共地 |
| SDA | GPIO2 / SDA1 | 3 | 线尽量短（≤10cm） |
| SCL | GPIO3 / SCL1 | 5 | 与 SDA 成对 |
| INT（如果有） | 可不接 | — | 当前驱动轮询，不依赖 INT |

- I2C1 默认地址 **0x73**
- 不要和 INA219（0x40）冲突；同一总线可以并接
- 传感器窗口不要被外壳/胶带遮住；前方留 1–2cm 净空
- 避免强阳光/红外遥控器直射；PAJ7620 是红外手势传感器
- 断电插拔，杜邦线不要受力；装壳后用扎带固定

### 3.2 软件安装

```bash
sudo systemctl stop flow-backend flow-ui

# 安装脚本通常已经尝试；失败时手动补
sudo /opt/flow/.venv/bin/pip install paj7620

# 确认 I2C 认得芯片
i2cdetect -y 1
```

预期在 `0x73` 看到 `73`。再读 Part ID：

```bash
/opt/flow/.venv/bin/python - <<'PY'
try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus
bus = SMBus(1)
try:
    print("part_id = 0x%02X (expect 0x20)" % bus.read_byte_data(0x73, 0x00))
finally:
    bus.close()
PY
```

### 3.3 独立手势测试（先停 backend）

```bash
sudo -u flow env \
  PYTHONPATH=/opt/flow/app \
  FLOW_HAL=real \
  /opt/flow/.venv/bin/python -m gesture --backend real --seconds 15
```

在传感器前依次做：

```text
挥手 → wave → confirm
左挥 → left → prev
右挥 → right → next
上挥 → up → extend
下挥 → down → shorten
顺时针 → cw → channel_next
逆时针 → ccw → channel_prev
向前 → forward → finish_step
向后 → backward → skip_step
```

预期终端输出类似：

```text
wave -> confirm (sensor)
right -> next (sensor)
```

同一个动作 1.5 秒内重复只会出现一次；这是防抖/冷却，不是漏识别。

### 3.4 回到 backend 验证

```bash
sudo systemctl start flow-backend flow-ui
sleep 2
curl -s http://127.0.0.1:8000/healthz | jq '.subsystems.gesture'
```

预期：

```json
{
  "state": "ok",
  "detail": "gesture sensor listening",
  "events": 0
}
```

用 WebSocket 看事件：

```bash
/opt/flow/.venv/bin/python - <<'PY'
from websockets.sync.client import connect
with connect("ws://127.0.0.1:8000/ws") as ws:
    print(ws.recv())  # state.sync
    while True:
        print(ws.recv())
PY
```

在传感器前挥手，应看到：

```json
{"type":"gesture.detected","payload":{"type":"wave","action":"confirm","confidence":1.0,"source":"sensor"}}
```

手机放上/拿走支架，应看到：

```json
{"type":"gesture.detected","payload":{"type":"phone_place","action":"phone_place","confidence":0.9,"source":"presence"}}
{"type":"gesture.detected","payload":{"type":"phone_take","action":"phone_take","confidence":0.9,"source":"presence"}}
```

### 3.5 手势/支架验收

- [ ] `i2cdetect -y 1` 有 `0x73`
- [ ] Part ID 为 `0x20`
- [ ] 挥手出现 `wave → confirm`，1.5s 内重复只触发一次
- [ ] 9 种手势分别对应正确动作（至少抽查 5 种）
- [ ] 手机放上 2 秒内出现 `phone_place`；拿走 2 秒内 `phone_take`
- [ ] 拔掉 PAJ7620：`/healthz` 的 `gesture` 变成 `disabled`，backend/UI 不崩
- [ ] 重新插上并重启 backend，`gesture` 恢复 `ok`
- [ ] 外壳开孔不遮挡传感器，强光/阳光直射下不误触发

**证据**：`i2cdetect` 截图、Part ID 输出、`gesture.detected` 日志/WS 输出、手机事件日志。

### 3.6 防误触/参数

配置文件 `config.yaml` 或环境变量可调：

```yaml
gesture:
  enabled: true
  cooldown_s: 1.5
  debounce_frames: 5
  min_votes: 2
```

- 误触发多：把 `min_votes` 调到 3，或把传感器移离屏幕/阳光
- 识别太迟钝：确认 `0x73`、线长、3.3V；不要用 5V
- 同一动作重复：这是 1.5s 冷却；不要当故障
- 完全没事件：先看 `python -m gesture --backend real`，再看 `/healthz`

### 3.7 可选 ToF（本次不验收）

T09 的 `approach/leave` 需要距离传感器（VL53L0X/APDS9960）。当前状态：

- 软件已有 `PresenceDetector` 和 `GestureService.observe_distance(cm)` 接口，测试覆盖
- 仓库没有 ToF 驱动，BOM 也没有 VL53L0X
- 接 ToF 后需要新增 `hal/real` 距离驱动，并让 `GestureService` 轮询调用
  `observe_distance()`；本次交接只验收 PAJ7620 手势和手机在位

---

## 4. 测试矩阵

| ID | 测试 | 命令/操作 | 预期 | 结果 |
| --- | --- | --- | --- | --- |
| T05-HW-01 | 正式 UI | `curl -I :8000/` | 200，返回 `ui/dist` | |
| T05-HW-02 | 720 画布 | 屏幕照片 | 界面在 720×720 内 | |
| T05-HW-03 | 中文 | 屏幕照片 | 无方块/截断 | |
| T05-HW-04 | kiosk | `systemctl status flow-ui` | active，无桌面/鼠标 | |
| T05-HW-05 | 离线重连 | 断网/重启 | UI 显示离线角标，恢复后重连 | |
| T05-HW-06 | 快捷键 | Ctrl+W/右键 | 不关闭、不弹菜单（xbindkeys） | |
| T09-HW-01 | I2C | `i2cdetect -y 1` | `0x73` | |
| T09-HW-02 | Part ID | 3.2 的 Python 片段 | `0x20` | |
| T09-HW-03 | 挥手 | `python -m gesture` | `wave → confirm` | |
| T09-HW-04 | 9 种手势 | 抽查 5 种 | 动作映射正确 | |
| T09-HW-05 | 冷却 | 1.5s 内重复挥手 | 只出现一次 | |
| T09-HW-06 | 手机在位 | 放上/拿走 | `phone_place/take` | |
| T09-HW-07 | 降级 | 拔 PAJ7620 | `gesture=disabled`，服务不崩 | |

> T05-HW-06 依赖安装脚本的 `xbindkeys` 配置；如果 Ctrl+W 仍能关闭，先确认
  `/opt/flow/config/xbindkeysrc` 存在且 `xbindkeys` 进程在运行。

---

## 5. 交接包与签收

### 5.1 需要发给软件同学

1. `systemctl status flow-backend flow-ui --no-pager`
2. `curl -s http://127.0.0.1:8000/healthz | jq`（含 `gesture`）
3. `i2cdetect -y 1` 和 Part ID 输出
4. 挥手/手机事件的 WS 输出或 `journalctl` 片段
5. 屏幕照片（UI + 720 + 中文）
6. `sudo flow-diag` 生成的包路径

### 5.2 交接判定

| 结论 | 条件 |
| --- | --- |
| **通过** | T05-HW-01~06、T09-HW-01~07 全部 PASS |
| **有条件通过** | 屏幕或手势有一个非阻塞项（如快捷键/外壳开孔）待修；写责任人和复测日期 |
| **不通过** | 屏幕黑屏/中文乱码/不能进 UI；I2C 找不到 0x73 且无法修复；手势误触发严重影响使用 |

### 5.3 签收

```text
T05/T09 硬件增量验收单

设备编号：__________    日期：__________
屏幕型号/接口：__________
PAJ7620 地址：0x73      Part ID：0x20
T05-HW-01~06：____ / 6
T09-HW-01~07：____ / 7
遗留项/责任人/日期：__________________________
硬件：__________  软件：__________  验收：__________
```

---

## 6. 常见问题

| 现象 | 先查 | 处理 |
| --- | --- | --- |
| 屏幕还是占位页 | `ui/dist/index.html` 是否存在 | 重新安装/复制 `ui/dist`；不要在 Pi 上跑 npm |
| 黑屏 | `flow-display hdmi720` 是否支持 | `sudo flow-display none` 回滚 |
| 中文方块 | `fc-list :lang=zh` | 重装 `fonts-noto-cjk` |
| Ctrl+W 仍关闭 | xbindkeys 是否运行 | 检查 `/opt/flow/config/xbindkeysrc`，重启 flow-ui |
| I2C 没有 0x73 | 3.3V/GND/SDA/SCL、线长 | 断电重接，`i2cdetect -y 1` |
| Part ID 不是 0x20 | 地址/供电/模块型号 | 确认 PAJ7620U2，不是其他 I2C 模块 |
| 手势全部无事件 | `paj7620` 是否安装 | `pip install paj7620`，重启 backend |
| `/healthz` gesture disabled | `journalctl -u flow-backend` | 看 probe 原因；拔掉传感器时这是预期 |
| 手机事件不出现 | 霍尔 GPIO27、10k 上拉、backend | 先跑 T02 支架测试，再看 `phone.changed` |
| 强光下乱触发 | 传感器朝向/遮光 | 加遮光罩，移开阳光直射 |

---

## 7. 与 T01/T02 交接文档的关系

- **完整整机装配、供电、BOM、角色分工、整机 20 项验收**：看
  [T01/T02 硬件交接说明](T01-hardware-handoff.md)。
- **逐条上机命令、屏幕/TTS/诊断**：看 [T01 硬件落地手册](T01-hardware-runbook.md)。
- 本文只覆盖 **T05 屏幕 UI + T09 手势/在场** 的增量硬件，避免和整机文档重复。
- T09 的真实 ToF 距离驱动属于后续硬件增量；T04 路由、PAJ7620 手势和手机在位已在
  本次软件范围。硬件同学按本文验收当前能力。
