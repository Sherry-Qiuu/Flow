# Android 伴侣 App 决策（T23，P2）

## 结论

设备是 Linux（树莓派），**无法直接读取手机 App 使用数据**。T23 必须依赖手机端配合，
因此按 P2 可选处理：资源紧张时整块砍掉，不影响 T21 + T18 的主链路。

## 方案

- **Android**：伴侣 App 使用 `UsageStatsManager` 读取前台应用时长，汇总后通过局域网
  `POST /api/phone/usage` 只上传 `{package, minutes}`，不上传内容、截图或通知。
- **iOS**：系统不开放 per-app 使用数据；设置页明确提示“暂不支持”，不静默失败。
  可让用户用“屏幕使用时间”截图走 T11 拍照导入，但不是自动回流。
- **设备端**：`app/phone/usage.py` 默认关闭，必须显式 `POST /api/phone/usage/toggle`
  才接收；关闭后直接拒绝并返回 `accepted:false`。

## 边界

- 本仓库只实现设备端接收、Top5、隐私开关和 iOS 说明；Android App 不在本仓库。
- 不做静默自动开启，不做行为内容采集，不把数据上传云端。
- 没有该模块时，T21 的手机契约和 T18 的坦白仍然完整可用。
