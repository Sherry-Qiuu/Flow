# Flow · Documentation

Design, planning and build documentation for the Flow single-channel task companion.

| Document set | What it covers |
| --- | --- |
| [software-task-slices](software-task-slices/00-README.md) | Software requirements (22 items), architecture and tech stack, 30 independently ownable task cards, priority queue |
| [deployment](deployment/T01-hardware-runbook.md) | T01 Raspberry Pi bring-up: flash, wiring, install, systemd, display, acceptance; [hardware handoff](deployment/T01-hardware-handoff.md) covers scope, BOM, roles, test matrix and sign-off |
| [hardware-tutorials](hardware-tutorials/00-总览与学习路径.md) | 10 build tutorials from unboxing to full assembly, plus wiring, troubleshooting, safety and BOM gap appendices |

## Software task slices

Start with [software-task-slices/00-README.md](software-task-slices/00-README.md).

| File | Contents |
| --- | --- |
| [01-需求梳理](software-task-slices/01-需求梳理.md) | Product document mapped to 22 software requirements (`SR-01` … `SR-22`) |
| [02-架构与技术选型](software-task-slices/02-架构与技术选型.md) | System architecture, stack, WebSocket message protocol, data model |
| [03-任务切片与排期](software-task-slices/03-任务切片与排期.md) | Task table, dependency graph, milestones, schedule, role split |
| [04-优先级与执行顺序](software-task-slices/04-优先级与执行顺序.md) | The single execution queue: 30 tasks in 8 dependency waves |
| `tasks/P0-必做/`, `P1-应做/`, `P2-可选/` | One card per task with scope, interface contract and acceptance checks |

Status: **30 tasks / ~66 person-days** (P0: 18 tasks / 43 days).

## Hardware tutorials

Start with [hardware-tutorials/00-总览与学习路径.md](hardware-tutorials/00-总览与学习路径.md).

| Chapter | Topic |
| --- | --- |
| H01 | Unboxing, parts check, tools |
| H02 | First boot of the Raspberry Pi 5 |
| H03 | Power system: 12 V pack → buck → Pi 5 |
| H04 | Digital inputs: push button and hall sensor |
| H05 | Vibration motor with transistor driver |
| H06 | I2C gesture sensor |
| H07 | CSI camera |
| H08 | Qi wireless charging module |
| H09 | Display and enclosure assembly |
| H10 | Full assembly integration and acceptance |
| A–D | Wiring/pin map, troubleshooting, missing parts, safety |

## Conventions

- Branch: `main`
- Commit messages: Conventional Commits (`docs:`, `feat:`, `fix:` …)
- Documentation prose may be Chinese; code, code comments and commit messages are American English.
