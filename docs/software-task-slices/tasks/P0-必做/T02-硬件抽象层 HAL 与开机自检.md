# T02 · 硬件抽象层 HAL 与开机自检

> 工作流：**平台底座**（PLT）・优先级 **P0**・规模 **M**（2 人日）

| 字段 | 内容 |
|---|---|
| 任务 ID | `T02` |
| 工作流 | 平台底座（`PLT`） |
| 优先级 | P0 |
| 规模 | M / 2 人日 |
| 前置依赖 | `T01` |
| 需协同 | `T04`、`T09`、`T20` |
| 建议角色 | 嵌入式 |

## 1. 目标

把屏幕、摄像头、麦克风、扬声器、支架传感器收拢成统一的 Python 接口，让上层业务代码永远不直接碰 GPIO 和 ALSA。

## 2. 需求依据

- **SR-19** — 支架：放手机 + 感应 + 充电 + 文件拍照传输（P42）
- **SR-17** — 屏幕显示表情 + 文字信息（P43）
- **SR-18** — 语音交互 + 手势交互，代替触屏（P43）

## 3. 输入 / 输出

**输入**

- T01 的系统环境
- 各外设的引脚与接线方案

**输出（可交付物）**

- hal 包（display / camera / audio_in / audio_out / phone_stand / gesture）
- hal.mock 假实现，使无硬件的电脑也能跑全部上层功能
- python -m hal.selftest 自检命令

## 4. 工作内容

- [ ] 定义统一设备契约：每个设备实现 probe() / open() / close() / health()
- [ ] 设备缺失时返回 Unavailable 状态而不是抛异常（离线开发的关键）
- [ ] mock 实现：环境变量 FLOW_HAL=mock 时启用，用假数据产生合理的事件流
- [ ] 摄像头：Pi Camera（picamera2）或 USB 摄像头（OpenCV），统一 capture() -> JPEG bytes
- [ ] 音频入：sounddevice 采 16kHz mono 帧，暴露回调式接口
- [ ] 音频出：扬声器播放 PCM / 文件，暴露音量控制
- [ ] 支架：微动开关或 ToF 判断在位，INA219 读充电电流，统一 state() -> PhoneState
- [ ] 开机自检：屏幕点亮、摄像头取帧、录音 1 秒、播放提示音、读传感器，结果写 device_status 表
- [ ] 自检失败在 UI 顶部显示故障图标，但服务继续运行（降级而非崩溃）

## 5. 接口契约

```
from typing import Protocol

class DeviceStatus:  # ok / missing / error + detail
    ...

class Camera(Protocol):
    def probe(self) -> DeviceStatus: ...
    def capture(self) -> bytes: ...          # JPEG

class PhoneStand(Protocol):
    def probe(self) -> DeviceStatus: ...
    def state(self) -> dict:
        """{present: bool, charging: bool, current_ma: int, distance_mm: int}"""

class AudioIn(Protocol):
    def start(self, on_frame): ...
    def stop(self): ...

class AudioOut(Protocol):
    def play(self, path_or_pcm) -> None: ...
    def set_volume(self, v: float) -> None: ...
```

## 6. 验收标准（Definition of Done）

- [ ] python -m hal.selftest 逐项输出每个设备的 OK / FAIL 及原因
- [ ] FLOW_HAL=mock 模式下，语音、拍照、传感器等上层功能在无外设电脑上全部可跑通
- [ ] 运行中拔掉摄像头，服务不崩溃，UI 显示降级图标
- [ ] 传感器状态变化通过事件总线 phone.changed 在 300ms 内发出

## 7. 风险与降级

- GPIO 库版本冲突（RPi.GPIO / lgpio / gpiozero）→ 统一用 gpiozero + lgpio 后端
- USB 麦克风与扬声器采样率不一致 → 在 HAL 内部统一重采样到 16kHz

## 8. 提示

> 先写 mock，再写真实实现：整个团队可以提前两周并行开工。

---

← 返回 [任务总表](../../03-任务切片与排期.md) ・ [优先级队列](../../04-优先级与执行顺序.md) ・ [索引](../../00-README.md)
