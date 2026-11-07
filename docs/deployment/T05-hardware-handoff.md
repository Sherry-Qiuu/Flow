# T05 屏幕与触屏交接说明

> 适用：T01/T02 基础整机已能开机，现在接入 **720×720 触屏**并验收 T05 UI。
> 接线、供电和 BOM 见 [T01/T02 硬件交接说明](T01-hardware-handoff.md)，
> [T01 硬件落地手册](T01-hardware-runbook.md)。

## 1. 一页结论

| 谁 | 需要做什么 | 交付什么 |
| --- | --- | --- |
| 硬件 | 固定 720×720 屏幕，接 HDMI/DSI 和触控 USB；确认触摸坐标 | 屏幕照片、触摸测试结果 |
| 软件 | `ui/dist`、`/healthz`、kiosk；触屏按钮已接入 API | 构建产物、服务日志 |
| 共同 | 按第 3 节测试矩阵验收并签字 | 交接包 |

完成标准：

1. 屏幕显示正式 T05 UI（不是占位页），720×720 无溢出。
2. 触摸有效：Idle 的“任务/专注/计划”按钮、PlanReview 的“确认”、Executing 的
   “完成/跳过/卡住/延长”都能触发后端。
3. 全屏、无桌面、无鼠标指针；Ctrl+W/右键不关闭/不弹菜单。
4. 中文无方块，断网后仍显示离线角标并自动重连。

## 2. 屏幕与触摸

- 7 英寸 HDMI 或 DSI，目标 720×720；Pi 5 使用 micro-HDMI 转 HDMI。
- 触控通常是 USB 或 I2C 触摸层；先确认 `evtest` 能看到触摸设备。
- 屏幕供电独立/5V 降压，不要从 GPIO 取 5V。

```bash
cd ~/Flow
sudo bash install.sh --display none
sudo systemctl start flow-backend flow-ui
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/
# 如果屏幕支持 720×720：
sudo flow-display hdmi720
sudo reboot
# 黑屏回滚：
sudo flow-display none
```

触摸坐标测试：

```bash
sudo evtest
# 找到触摸设备，点四个角，确认坐标覆盖 0..720
```

如果触摸方向反了，优先在 `deploy/configure-display.sh` / Xorg 输入配置里旋转，
不要在 React 代码里硬编码坐标。

## 3. 验收矩阵

| ID | 测试 | 操作 | 预期 |
| --- | --- | --- | --- |
| T05-HW-01 | 正式 UI | `curl -I :8000/` | 200，返回 `ui/dist` |
| T05-HW-02 | 720 画布 | 屏幕照片 | 无滚动/溢出 |
| T05-HW-03 | 中文 | 屏幕照片 | 无方块/截断 |
| T05-HW-04 | kiosk | `systemctl status flow-ui` | active，无桌面/鼠标 |
| T05-HW-05 | 触摸 | 点 Idle 的“任务/专注/计划” | 2 秒内切通道 |
| T05-HW-06 | 计划确认 | PlanReview 点“确认” | 进入 Executing |
| T05-HW-07 | 执行控制 | 点完成/跳过/卡住 | 状态更新并切下一步 |
| T05-HW-08 | 离线重连 | 断网再恢复 | 角标出现，WS 自动恢复 |

## 4. 常见问题

| 现象 | 先查 | 处理 |
| --- | --- | --- |
| 占位页 | `ui/dist/index.html` | 重新安装/复制 `ui/dist`；Pi 上不要跑 npm |
| 黑屏 | `hdmi720` 是否支持 | `sudo flow-display none` 回滚 |
| 触摸无反应 | `evtest`、USB/I2C 连接 | 重插触摸线，检查 Xorg 输入设备 |
| 触摸坐标偏移 | `evtest` 四角坐标 | 调 Xorg calibration/旋转，不改 UI 组件 |
| 中文方块 | `fc-list :lang=zh` | 安装 `fonts-noto-cjk` |
| Ctrl+W 仍关闭 | xbindkeys | 检查 `/opt/flow/config/xbindkeysrc` |

## 5. 交接包

1. `systemctl status flow-backend flow-ui --no-pager`
2. `curl -s http://127.0.0.1:8000/healthz | jq`
3. `sudo evtest` 触摸设备名和四角坐标
4. 屏幕照片 + 触摸操作录屏（10 秒）
5. `sudo flow-diag` 生成的诊断包

签收前确认：T05-HW-01~08 全部 PASS；遗留项写清责任人和复测日期。

```text
T05 触屏验收单
设备编号：__________  日期：__________
屏幕/触摸型号：__________
T05-HW-01~08：____ / 8
遗留项/责任人：__________________________
硬件：__________  软件：__________
```

> 手机在位/充电仍属于 T20/T21，与本屏幕交接独立。
