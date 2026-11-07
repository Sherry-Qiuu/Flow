# T06 · 语音输入管线（唤醒 / VAD / ASR）

> 工作流：**单通道交互**（CHN）・优先级 **P0**・规模 **L**（3.5 人日）

| 字段 | 内容 |
|---|---|
| 任务 ID | `T06` |
| 工作流 | 单通道交互（`CHN`） |
| 优先级 | P0 |
| 规模 | L / 3.5 人日 |
| 前置依赖 | `T02`、`T03` |
| 需协同 | `T04`、`T07`、`T08`、`T11` |
| 建议角色 | 语音 / AI |
| 当前状态 | 🟢 管线核心已完成；真实 ASR 模型/云端账号与降噪参数待上机验收 |
| 子任务数 | 5 项（见第 5 节） |

## 1. 目标

用户随时说一句，设备 1.5 秒内听清并转成带意图的文本。

## 2. 需求依据

- **SR-18** — 语音交互 + 触屏交互（手势已取消）（P43）
- **SR-02** — 用户通过语音表达主动抓取工具的意愿（P14）
- **SR-08** — 用户通过摄像头 / 语音输入告诉机器人自己的任务（P23）

## 3. 输入 / 输出

**输入**

- T02 的 AudioIn 接口
- 一颗 16kHz 麦克风（USB 或 HAT）

**输出（可交付物）**

- SpeechPipeline：start/stop、partial/final 回调
- 云端 ASR 主链路 + Vosk 离线降级
- echo 消除与 barge-in（打断）支持

## 4. 工作内容

- [ ] 音频链路：ALSA/PulseAudio → 16kHz mono → 环形缓冲（保留 3 秒预录，防吞字头）
- [ ] VAD：silero-vad（推荐）或 webrtcvad，端点检测 300ms 静音断句
- [ ] 唤醒策略分两级：MVP 用物理按键 + 近场 VAD 触发；P1 接 openWakeWord 中文唤醒词
- [ ] ASR 主链路：云端流式识别（阿里云 / 腾讯云），同时返回 partial 与 final
- [ ] 离线降级：Vosk 中文小模型，网络异常自动切换并播报“现在用离线识别”
- [ ] 回声消除：播报时暂停拾音，或接 speexdsp AEC 支持边播边听
- [ ] 打断（barge-in）：播报中检测到用户开口，立即停止 TTS 并开始新一轮识别
- [ ] 鲁棒性：连续 3 次空识别提示“没听清，可以说慢一点”；录音时长上限 30 秒
- [ ] 隐私：默认不落盘原始音频，仅调试开关下保存到 /tmp，且自动清理

## 5. 子任务拆解

每项 ≤0.5 人日，可单独勾选验收。做完一项就在 `产物` 那一列把文件建出来。

| 子任务 | 名称 | 产物 | 完成判据 | 人日 |
|---|---|---|---|---|
| `T06.1` | 音频采集与环形缓冲 | `app/voice/capture.py` | 16kHz mono；保留 3 秒预录，吞字头问题消失 | 0.5 |
| `T06.2` | VAD 端点检测 | `app/voice/vad.py` | 300ms 静音断句；一句不多切、不少切 | 0.5 |
| `T06.3` | 云端流式 ASR | `app/voice/asr_cloud.py` | partial/final 两路回调；断线重连；说完 ≤1.5s 出 final | 1.0 |
| `T06.4` | 离线降级 Vosk | `app/voice/asr_local.py` | 断网 3 秒内切离线模型并播报，功能不中断 | 0.75 |
| `T06.5` | 打断与降噪 | `app/voice/bargein.py` | 播报中说“停”立即停 TTS；连续 3 次空识别给提示 | 0.75 |

**小计 3.50 人日**

## 6. 接口契约

```
pipeline = SpeechPipeline(hal.audio_in)
pipeline.on_partial = lambda text: bus.publish("speech.partial", {"text": text})
pipeline.on_final   = lambda text: bus.publish("speech.final", {"text": text})
pipeline.start()
```

## 7. 实现要点

```
采集链：
hal.audio_in.start(on_frame) → RingBuffer(3s 预热) → VAD → ASR

    on_frame  每 20–30ms 一帧 16k mono
    VAD       连续 300ms 静音判定断句
    ASR       partial → speech.partial；断句后 final → speech.final

barge-in：播报时持续监听，检测到语音能量立刻 hal.audio_out.stop()
降级：asr_cloud 连续 2 次失败 → 切 asr_local（Vosk），并播报一句提示
```

## 8. 验收标准（Definition of Done）

- [ ] 安静房间 3 米内，中文短句（10 字左右）识别准确率 ≥ 90%
- [ ] 用户说完后 ≤ 1.5 秒拿到 final 文本并发出 speech.final 事件
- [ ] 播报过程中说“停”或“等一下”能立即中断 TTS
- [ ] 拔掉网线后 3 秒内自动切离线模型，功能不中断
- [ ] 连续说话 5 分钟不丢帧、内存不持续增长

## 9. 风险与降级

- 麦克风阵列噪声大 → 加高通滤波与增益归一化；先做近场（<1.5m）
- 云端 ASR 有配额与延迟 → 必须保留离线方案，演示现场断网也不至于哑掉

## 10. 提示

> 先把“按键说话”跑通，节奏感有了再加唤醒词。唤醒词误触发会毁掉整个体验，别早做。

---

← 返回 [任务总表](../../03-任务切片与排期.md) ・ [优先级队列](../../04-优先级与执行顺序.md) ・ [细化总表](../../05-任务细化总表.md) ・ [索引](../../00-README.md)
