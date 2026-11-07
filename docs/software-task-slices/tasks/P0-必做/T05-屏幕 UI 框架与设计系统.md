# T05 · 屏幕 UI 框架与设计系统

> 工作流：**单通道交互**（CHN）・优先级 **P0**・规模 **L**（4 人日）

| 字段 | 内容 |
|---|---|
| 任务 ID | `T05` |
| 工作流 | 单通道交互（`CHN`） |
| 优先级 | P0 |
| 规模 | L / 4 人日 |
| 前置依赖 | `T01` |
| 需协同 | `T03`、`T04`、`T13`、`T16` |
| 建议角色 | 前端 |

## 1. 目标

14×14cm 屏幕上的整套视觉语言：极简、大字号、低认知负荷，并且有表情。

## 2. 需求依据

- **SR-17** — 屏幕：显示表情 + 文字信息（P43）
- **SR-05** — 开始执行计划的时候屏幕上极简显示步骤（P19）
- **SR-01** — 单通道强制聚焦，降低过载（P16）

## 3. 输入 / 输出

**输入**

- T01 的屏幕分辨率与字体环境
- T03 的 WS 协议

**输出（可交付物）**

- React + Vite + TS 前端工程
- 设计令牌与组件库
- 7 个页面状态 + 表情组件
- 构建产物接入 Chromium kiosk

## 4. 工作内容

- [ ] 技术栈：React 18 + Vite + TypeScript + TailwindCSS + Framer Motion
- [ ] 设计画布 720×720，按实际屏幕分辨率等比缩放（CSS 变量 + transform scale）
- [ ] 设计令牌：低饱和暖色板、字号阶梯（正文 ≥ 28px、步骤主字 ≥ 40px）、圆角、间距、动效时长（200/400/800ms）
- [ ] 页面：Idle（待机：表情 + 时钟 + 一句话）、Listening、Thinking、PlanReview、Executing（单步大字卡）、Celebrate、Resting、Settings
- [ ] 组件：FaceExpression（8 种表情状态机）、BigText、StepCard、ProgressRing、Toast、OfflineBadge
- [ ] 状态管理：单一 reducer 消费 WS 事件；断线时保留最后状态并显示离线角标
- [ ] 无触屏原则：屏幕上不出现只能点的按钮，所有操作必须同时存在语音/手势的等效路径
- [ ] 性能：动效用 transform/opacity，避免长列表；字体子集化减少首屏

## 5. 接口契约

```
src/
  app/           路由与状态 reducer
  components/    FaceExpression / StepCard / ProgressRing ...
  pages/         Idle / Listening / Thinking / PlanReview / Executing / Celebrate / Resting
  tokens/        colors.ts / typography.ts / motion.ts
  ws/            WebSocket 客户端（自动重连、消息分发）
```

## 6. 验收标准（Definition of Done）

- [ ] 7 个页面随 ui.phase 事件正确切换，任意顺序切换无白屏、无残留
- [ ] WebSocket 断开后显示离线角标，恢复后自动重连并重新同步状态
- [ ] 在 800×480 / 720×720 / 1024×600 三种分辨率下不溢出、不遮挡、字号可读
- [ ] 中文在目标字号下清晰无截断（含长任务名换行策略）
- [ ] 执行态屏幕只有一个步骤 + 剩余时间，没有任务列表

## 7. 风险与降级

- 在树莓派上跑 Chromium 动画掉帧 → 关闭硬件加速以外的重特效，用 CSS 动画而非 JS 逐帧
- 中文长文本溢出 → 组件层统一做行数与字号自适应

## 8. 提示

> 先在笔记本上把界面全部做完再上板。屏幕只是显示设备，开发阶段完全可以用浏览器调试。

---

← 返回 [任务总表](../../03-任务切片与排期.md) ・ [优先级队列](../../04-优先级与执行顺序.md) ・ [索引](../../00-README.md)
