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
| 当前状态 | 🟢 已实现（React/Vite/TS/Tailwind/Motion、720 画布、8 表情、7+1 页面、自动重连、ui/dist） |
| 子任务数 | 5 项（见第 5 节） |

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

## 5. 子任务拆解

每项 ≤0.5 人日，可单独勾选验收。做完一项就在 `产物` 那一列把文件建出来。

| 子任务 | 名称 | 产物 | 完成判据 | 人日 |
|---|---|---|---|---|
| `T05.1` | 工程脚手架与设计令牌 | `ui/src/tokens/{colors,typography,motion}.ts` | Vite+React+TS+Tailwind+Motion 跑得起来；720×720 画布变量就位 | 0.5 |
| `T05.2` | WS 客户端与状态 reducer | `ui/src/ws/client.ts, ui/src/state/reducer.ts` | 自动重连；断线保留最后状态并显示离线角标 | 0.5 |
| `T05.3` | 七个页面 | `ui/src/pages/*` | Idle/Listening/Thinking/PlanReview/Executing/Celebrate/Resting 随 ui.phase 切换 | 1.5 |
| `T05.4` | 表情与动效组件 | `ui/src/components/FaceExpression.tsx 等` | 8 种表情状态机；动效用 transform/opacity，60fps | 0.75 |
| `T05.5` | 分辨率适配与 kiosk 接入 | `ui/vite.config.ts + 构建产物挂到 flow-ui` | 800×480 / 720×720 / 1024×600 三档不溢出；kiosk 全屏无滚动条 | 0.75 |

**小计 4.00 人日**

## 6. 接口契约

```
src/
  app/           路由与状态 reducer
  components/    FaceExpression / StepCard / ProgressRing ...
  pages/         Idle / Listening / Thinking / PlanReview / Executing / Celebrate / Resting
  tokens/        colors.ts / typography.ts / motion.ts
  ws/            WebSocket 客户端（自动重连、消息分发）
```

## 7. 实现要点

```
ui/src/
├── tokens/{colors,typography,motion}.ts   设计令牌
├── ws/client.ts                           自动重连 + 事件分发
├── state/reducer.ts                       单一 reducer，消息 → 状态
├── components/FaceExpression.tsx          8 种表情
├── components/{StepCard,ProgressRing,OfflineBadge}.tsx
└── pages/{Idle,Listening,Thinking,PlanReview,Executing,Celebrate,Resting}/

画布 720×720，用 CSS 变量缩放而非重排：
    :root { --scale: calc(100vw / 720); }
    .canvas { width:720px; height:720px; transform: scale(var(--scale)); }

硬规则：屏幕上一个可点元素都不能有，全部由语音/手势等效触发。
```

## 8. 验收标准（Definition of Done）

- [ ] 7 个页面随 ui.phase 事件正确切换，任意顺序切换无白屏、无残留
- [ ] WebSocket 断开后显示离线角标，恢复后自动重连并重新同步状态
- [ ] 在 800×480 / 720×720 / 1024×600 三种分辨率下不溢出、不遮挡、字号可读
- [ ] 中文在目标字号下清晰无截断（含长任务名换行策略）
- [ ] 执行态屏幕只有一个步骤 + 剩余时间，没有任务列表

## 9. 风险与降级

- 在树莓派上跑 Chromium 动画掉帧 → 关闭硬件加速以外的重特效，用 CSS 动画而非 JS 逐帧
- 中文长文本溢出 → 组件层统一做行数与字号自适应

## 10. 提示

> 先在笔记本上把界面全部做完再上板。屏幕只是显示设备，开发阶段完全可以用浏览器调试。

---

← 返回 [任务总表](../../03-任务切片与排期.md) ・ [优先级队列](../../04-优先级与执行顺序.md) ・ [细化总表](../../05-任务细化总表.md) ・ [索引](../../00-README.md)
