# T30 安装、升级与出厂自检

## 全新设备

1. 烧录 Raspberry Pi OS Lite，接 720×720 触屏/麦克风/音箱/支架。
2. 复制仓库到设备，执行 `sudo bash install.sh --display hdmi720`。
3. 编辑 `/opt/flow/.env`（参考 `.env.example`），不要提交到 git。
4. 执行 `sudo flow-start` 或重启，检查：
   - `systemctl status flow-hal flow-backend flow-ui`
   - `curl -s :8000/healthz | jq`
   - `i2cdetect -y 1`（INA219 `0x40`、PAJ7620 `0x73`）
   - `sudo python -m hal.selftest --audio-seconds 1`
5. 首次开机向导写入 `config.yaml`：
   `PYTHONPATH=/opt/flow/app /opt/flow/.venv/bin/python -m setup.wizard --name 小A`

## 自主运行（拔掉笔记本也能用）

安装完只代表代码到位，`--display none` 的机器开机是不亮屏、也听不懂人话的。
把设备变成“插电就自己跑”的两步：

```bash
# 已经装过：一条命令补显示 + 离线语音 + 开机自启校验
sudo bash deploy/setup-standalone.sh --display hdmi720   # 或 dsi
sudo reboot
```

- `--display hdmi720|dsi` 写入 `/boot/firmware/config.txt` 的托管块，回滚用
  `sudo flow-display none`；用 HDMI 方屏选 `hdmi720`，排线触屏选 `dsi`
- 离线语音由 `deploy/setup-voice.sh` 独立完成，也可单跑：
  `sudo bash deploy/setup-voice.sh`（装 `vosk` + 中文小模型到
  `/opt/flow/models`，并写好 `FLOW_VOSK_MODEL`）。模型在本地推理，
  **断网也能识别**；想换模型或走镜像：`--model` / `--model-url`
- 全新安装可以一步到位：`sudo bash install.sh --display hdmi720 --vosk`
- 语音播报需要 `espeak-ng`，脚本会顺带装上（`--no-tts` 可跳过）

验收（重启后不连电脑也能复现）：

```bash
systemctl is-enabled flow-hal flow-backend flow-ui   # 三行 enabled
curl -s http://127.0.0.1:8000/healthz                # voice.state = ok
```

任何一个 `disabled` 都说明它不会自己起来；`voice.state` 是 `disabled` 则是
ASR 没配好，重新跑一次 `setup-voice.sh` 看输出。

## 升级（保留数据）

```bash
sudo /opt/flow/deploy/upgrade.sh /path/to/new-release
# 失败时：
# mv /opt/flow /opt/flow.failed && mv /opt/flow.previous /opt/flow
```

升级脚本保留 `data/` 与 `.env`，旧目录留在 `/opt/flow.previous`。

## 备份与恢复

```bash
flow-backup
flow-restore --latest
```

## 出厂自检

烧录后自动跑 `hal.selftest`，报告逐项 `OK/FAIL/SKIP`；任何 FAIL 先查接线，
不要把“硬件装好”当成“软件验收通过”。

## 已知边界

- 真正定制 `.img` 需要 rpi-imager/firstrun，本仓库提供可复现的安装脚本作为交付方式。
- 离线 ASR 用 Vosk 中文小模型即可跑通；识别准确率仍要按现场噪声验收，
  在线 ASR（`FLOW_ASR_URL`）配好后会优先走在线、失败再落回离线。
