# T01 硬件落地手册（树莓派 + Flow）

这份手册把 [T01 任务卡](../software-task-slices/tasks/P0-必做/T01-设备镜像与运行基座.md)
变成可以在桌面上照着做的步骤。代码和安装脚本已经在本仓库里，剩下的是**物理接线、
烧录 SD 卡和在树莓派上执行命令**。

> 先读：[H02 树莓派首次开机](../hardware-tutorials/H02-树莓派首次开机.md)、
> [A 接线总图与引脚分配](../hardware-tutorials/A-接线总图与引脚分配.md)、
> [D 安全手册](../hardware-tutorials/D-安全手册与红线.md)。
>
> 团队分工、物料、测试矩阵和签收表见 [T01 硬件交接说明](T01-hardware-handoff.md)。
>
> T05 触屏的增量验收见
> [T05 触屏交接说明](T05-hardware-handoff.md)。

## 0. 先明确：哪些我做、哪些你做

| 已经完成（仓库里） | 需要你在硬件旁完成 |
| --- | --- |
| `install.sh` 一键安装、venv、systemd、journald、kiosk、`flow-diag` | 烧录 SD 卡、接线、上电、屏幕/摄像头/麦克风固定 |
| T02 HAL + mock + `python -m hal.selftest` | 在树莓派上跑真实 HAL 自检，确认每个设备 |
| T03 FastAPI + WebSocket + 事件总线 + `/healthz` | 用 `curl`、浏览器或 WS 客户端确认服务 |
| 显示配置脚本 `flow-display hdmi720\|hdmi1024x600\|hdmi1280x800\|dsi` | 确认屏幕实际分辨率、中文无方块 |
| 开机服务顺序 `flow-hal → flow-backend → flow-ui` | 断电重启，计时 90 秒内进入界面 |

我无法隔着网络替你插 CSI 排线、确认 HDMI 口或听扬声器；下面每一步都给了
**预期输出**，你只需要把不符合的地方发回来。

## 1. 硬件清单

最低配置（T01 验收用）：

- 树莓派 5（4GB+）或 4B，A2 级 32GB+ microSD
- 5V/5A 电源（树莓派 5 必须 5A；4B 至少 3A）
- 14×14cm 屏幕（优先 HDMI；DSI 屏也可，但先确认原生分辨率）
- CSI 摄像头 + 22 针 FPC 排线
- USB 麦克风、USB 扬声器（或 3.5mm/USB 声卡）
- 手机支架：霍尔/微动在位传感器 + 10kΩ 上拉 + INA219（充电电流）
- 杜邦线、面包板、万用表（接线前测通断）

引脚以 [A 接线总图](../hardware-tutorials/A-接线总图与引脚分配.md) 为准：

| 功能 | BCM | 物理脚 | 说明 |
| --- | --- | --- | --- |
| 手机在位（霍尔 A3144） | **GPIO27** | **13** | 输出接 GPIO27，**必须 10kΩ 上拉到 3.3V** |
| STOP 按钮（T04 用） | GPIO17 | 11 | 按钮另一端接 GND |
| 触控 USB | USB | — | 触摸输入，evtest 验证 |
| 振动马达（T16 用） | GPIO18 | 12 | 经三极管，必须加续流二极管 |
| 摄像头 | CSI | — | Pi 5 用 CAM0/CAM1，注意 FPC 方向 |
| 显示 | HDMI0（Pi 5） | — | 优先 HDMI，避免 DSI 驱动问题 |
| 音频 | USB | — | 麦克风和扬声器都建议 USB，免去 ALSA 混音 |

> 当前 T02 的手机在位默认引脚是 **GPIO27**（不是 GPIO17）。
> 如果你的支架用的是微动开关而不是霍尔，仍然接 GPIO27，另一端接 GND。

## 2. 烧录系统

按 [H02](../hardware-tutorials/H02-树莓派首次开机.md) 用 Raspberry Pi Imager：

1. 设备选 `Raspberry Pi 5`（或 4B）。
2. 系统选 **Raspberry Pi OS Lite (64-bit) Bookworm**。T01 的目标是无桌面
   kiosk；H02 教学阶段用 Desktop 也可以，但最后要切到 `multi-user.target`。
3. 齿轮设置里必须配置：
   - 主机名 `flow`
   - 用户名 `flow`（安装脚本默认服务用户也是 `flow`）
   - WiFi、时区 `Asia/Shanghai`、键盘 `us`
   - 开启 SSH（密码登录）
4. 写入后插卡、接 HDMI、键盘（第一次可选）、网线/电源，开机。

在电脑上验证：

```powershell
ssh flow@flow.local
# 如果 flow.local 不解析，去路由器找 IP，然后 ssh flow@192.168.x.x
```

## 3. 第一次上机检查（不接业务代码）

```bash
sudo apt update && sudo apt full-upgrade -y
sudo raspi-config nonint do_i2c 0        # 启用 I2C
sudo raspi-config nonint do_spi 0        # 需要 SPI 时
rpicam-hello --list-cameras              # 应看到 imx219/imx708 等
arecord -l                               # 应看到 USB 麦克风
aplay -l                                 # 应看到 USB 扬声器
ls /dev/i2c-*                            # 应出现 /dev/i2c-1
vcgencmd measure_temp                    # 40–60°C 正常
```

如果摄像头没有列出：先断电，重插 FPC，确认金色触点朝向和卡扣；再试
`libcamera-hello --list-cameras`（旧系统命令名）。CSI 摄像头走 picamera2；
如果你用的是 USB 摄像头，安装时加 `--with-opencv`，否则 HAL 会报告 camera missing。

## 4. 把代码放到树莓派

有网络时直接克隆：

```bash
git clone https://github.com/Sherry-Qiuu/Flow.git ~/Flow
cd ~/Flow
```

没有网络时，在 Windows 上传：

```powershell
scp -r .\Flow flow@flow.local:/home/flow/Flow
```

## 5. 一键安装

在树莓派上：

```bash
cd ~/Flow
sudo bash install.sh --display hdmi720
```

脚本会做这些事：

- 安装 Chromium、Noto CJK 字体、Xorg/openbox、音频/摄像头/I2C 工具、chrony
- 创建 `flow` 用户组权限（audio/video/gpio/i2c/spi/render）
- 把代码复制到 `/opt/flow`
- 建 venv 并安装 FastAPI/uvicorn/HAL 依赖
- 安装 `flow-hal.service`、`flow-backend.service`、`flow-ui.service`
- 安装 `flow-diag`、`flow-display`、kiosk 启动脚本
- 设置时区、中文 locale、journald 保留 7 天

> `flow-hal.service` 是**开机预检**：跑 T02 自检、写 `device_status`，然后退出。
> 真正的 HAL 由 `flow-backend` 进程持有（T03 的生命周期是 db → hal →
> scheduler → ws）。这样不会出现两个进程同时打开摄像头/麦克风。

安装完成后编辑密钥（只放在设备本地，不要提交）：

```bash
sudo nano /opt/flow/.env
# 填 DEEPSEEK_API_KEY=... 等；其他保持默认
sudo chmod 600 /opt/flow/.env
```

`.env` 已由 `.gitignore` 排除，安装脚本从不会把它复制回仓库。

## 6. 硬件自检

```bash
sudo systemctl restart flow-hal
journalctl -u flow-hal -n 80 --no-pager
```

预期看到 5 个设备的 `OK`（没有接传感器时可能是 `SKIP`）：

```text
[OK  ] display ...
[OK  ] camera  ...
[OK  ] audio_in ...
[OK  ] audio_out ...
[OK  ] phone_stand ...
[OK  ] phone_stand ...
SELF-TEST: 6 OK, 0 FAIL, 0 SKIP
```

再看写入数据库的状态：

```bash
sqlite3 -header -column /opt/flow/data/flow.db \
  "select device,status,detail,checked_at from device_status order by id desc limit 12;"
```

单项排查：

```bash
# 摄像头
rpicam-still -o /tmp/test.jpg --timeout 2000
ls -lh /tmp/test.jpg

# 麦克风录 1 秒并回放
arecord -d 1 -f S16_LE -r 16000 -c 1 /tmp/test.wav
aplay /tmp/test.wav

# I2C 扫描：INA219 应在 0x40；触摸设备用 evtest 确认
i2cdetect -y 1
```

## 7. 启动后端并验证接口

```bash
sudo systemctl start flow-backend
systemctl status flow-backend --no-pager
curl -s http://127.0.0.1:8000/healthz | jq
```

预期 `status` 为 `ok`，`subsystems` 包含 `db`、`hal`、`scheduler`、`phone`、`voice`、`websocket`。
`scheduler` 在配置启用时为 `ok`；没配 ASR 时 `voice` 是 `disabled`，不影响其他服务。
提醒调度由 T15 管理；没有配置提醒时它仍为 `ok`，只是队列为空。

WebSocket 连接测试（用 venv 里的 websockets）：

```bash
/opt/flow/.venv/bin/python - <<'PY'
from websockets.sync.client import connect
with connect("ws://127.0.0.1:8000/ws") as ws:
    print(ws.recv())
PY
```

应收到一条 `state.sync`，里面含 `phase`、`channel`、`hal`、`phone`、`subsystems`。

非法 JSON 验证（服务不能退出）：

```bash
/opt/flow/.venv/bin/python - <<'PY'
from websockets.sync.client import connect
with connect("ws://127.0.0.1:8000/ws") as ws:
    print("first:", ws.recv())
    ws.send("{bad json")
    print("error:", ws.recv())
PY
```

应收到 `{"type":"error","payload":{"code":"invalid_json",...}}`，连接仍然可用。

## 8. 启动屏幕 Kiosk

```bash
sudo systemctl start flow-ui
journalctl -u flow-ui -n 80 --no-pager
```

- 屏幕应为 1024×600 画布（点对点），无桌面、无鼠标光标（`unclutter`）。
- kiosk 通过 `xbindkeys` 屏蔽 `Ctrl+W`、`Ctrl+Q`、`Alt+F4` 和鼠标右键；
  蓝牙默认关闭（安装时设 `KEEP_BLUETOOTH=1` 可保留）。
- 中文应正常显示；若出现方块，执行 `fc-list :lang=zh | head` 确认 Noto CJK。
- 若屏幕黑屏：先把显示恢复原生模式 `sudo flow-display none`，重启后再排查
  HDMI 线/接口；各 hdmi 模式都依赖屏幕支持对应自定义模式（RTD2660TP 7" 屏
  1024×600，10.1" 16:10 屏 1280×800，方屏 720×720）。
- `flow-ui` 使用 tty1 + Xorg + openbox + Chromium；如果用的是 Desktop 镜像，
  安装脚本会把默认 target 切到 `multi-user.target`，否则桌面会和 kiosk 抢显示。

## 9. 断电重启验收（T01 DoD）

```bash
sudo reboot
```

重启后不要手动登录，观察：

1. **90 秒内**屏幕进入 Flow 界面（不是登录提示符/桌面）。
2. 拔掉网线再重启，界面仍能起来；T05 UI 会显示离线角标，后端 WS 断开时
   自动重连并重新同步状态。
3. `journalctl -b -u flow-backend --no-pager | tail -50` 能看到完整启动日志。
4. `journalctl -b -u flow-ui --no-pager | tail -30` 没有字体缺失警告。
5. 中文在目标屏幕上无方块、无截断。
6. 分辨率为 720×720（或 T05 的 720 设计画布一致）。

逐项勾选：

- [ ] 断电重启 90 秒内进入产品界面
- [ ] 断网可启动，显示离线/重连状态
- [ ] `journalctl -u flow-backend` 日志完整，无字体缺失
- [ ] 中文渲染正确
- [ ] 屏幕分辨率与 720×720 设计画布一致

## 10. 出问题时把什么发给我

优先跑：

```bash
sudo flow-diag
```

它会打包 journal、`config.yaml`、`version.json`、`device_status`、音频/摄像头/I2C
状态到 `/opt/flow/data/diag/flow-diag-*.tar.gz`（不包含 `.env`）。
如果要现场重跑 HAL 自检，先 `sudo systemctl stop flow-backend`，再加
`sudo flow-diag --with-selftest`，避免摄像头/麦克风被 backend 占用。

同时贴这几条命令的原始输出：

```bash
systemctl status flow-hal flow-backend flow-ui --no-pager
curl -s http://127.0.0.1:8000/healthz | jq
journalctl -b -u flow-backend -n 100 --no-pager
journalctl -b -u flow-ui -n 100 --no-pager
rpicam-hello --list-cameras
arecord -l
aplay -l
i2cdetect -y 1
```

## 11. 常见故障

| 现象 | 先查什么 | 处理 |
| --- | --- | --- |
| 屏幕黑屏 | `flow-display hdmi720` 是否匹配屏幕 | `sudo flow-display none` 重启，恢复原生分辨率 |
| 中文方块 | `fc-list :lang=zh` | 重跑安装脚本或 `sudo apt install fonts-noto-cjk` |
| Chromium 不起 | `journalctl -u flow-ui` | 确认 `/usr/bin/xinit`、`openbox`、`chromium` 存在；Desktop 镜像先切 multi-user |
| 摄像头缺失 | `rpicam-hello --list-cameras` | 断电重插 FPC；确认没有启用 legacy camera |
| 麦克风缺失 | `arecord -l` | 换 USB 口；`usermod -aG audio flow` 后重启 |
| 支架一直 absent | `i2cdetect -y 1` / 万用表 | 霍尔 GPIO27、10kΩ 上拉、共地；微动一端 GPIO27 一端 GND |
| `flow-hal` 失败 | `journalctl -u flow-hal` | 看具体设备；触控用 evtest 检查 |
| 后端 502/连不上 | `systemctl status flow-backend` | 看 `/healthz`；单 worker 是强制的，不要加 `--workers 2` |
| 断电后 SD 卡损坏 | 是否 A2 卡 | 备份 `data/`；可选 overlayfs（见 T01 卡风险项） |

## 12. 完成 T01 后告诉我什么

请把下面 6 项结果发回来，我就能判断 T01 是否算完成：

1. `systemctl status flow-hal flow-backend flow-ui --no-pager` 的输出
2. `curl -s http://127.0.0.1:8000/healthz | jq` 的输出
3. 重启计时：从按电源到界面出现多少秒
4. 屏幕照片（中文 + 分辨率）
5. `sudo flow-diag` 生成的包路径
6. 摄像头/麦克风/支架三项的 `hal.selftest` 结果

如果某一项不通过，把对应日志贴回来，不需要重装整机。
