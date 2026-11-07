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
- 真实 ASR/TTS/ToF/摄像头准确率需要上机验收。
