---
name: x-dev
description: |
  开发任务执行 skill。读取 task README 与 dev-checklist，按依赖实现、写 verify 证据，并由 README risk 驱动交付或 Gate ②。
  触发：`x-dev <功能名称>` 或现有 task 目录。
---

# x-dev — 统一执行

## 输入与边界

目标目录必须有 `README.md` 和 `dev-checklist.md`。README 的 `risk:`、验收 Scenario 与技术设计定义实现边界；dev-checklist 定义顺序与状态；dev-report 记录改动及 verify 证据。x-dev 消费 task，不创建需求包。

## 执行

1. 阅读 README 的核心目标、涉及模块、架构拆分策略、技术设计、验收与自动化测试责任；模块段含 spec 引用时跟读对应模块文档。
2. 运行 `python3 tools/xdev.py status <task-dir> --json` 与 `graph <task-dir> --json`。同优先级、无依赖、无同文件写冲突的 ready task 可并行；有依赖的 task 按拓扑序推进。
3. 将当前 checklist 项更新为进行中，实现时保持 README 定义的公开契约、失败路径与范围。
4. 每个 `验证: auto` Scenario 在 `dev-report.md` 写一个 auto fenced `verify` 块，用 `scenario:` 精确回指；补齐单元、契约和边界测试。manual Scenario 写步骤块。
5. 实现完成后更新 checklist 为待测试，运行全部 verify 块声明的命令；通过后更新为测试通过。
6. 运行 `python3 tools/xdev.py verify <task-dir> --json`：exit 2 修正 dev-report 格式；exit 1 将 fail 与 uncovered 一次交给 x-fix；exit 0 继续 risk 路由。
7. Q0/Q1 输出完成回执及定级依据；Q2 调 x-qa-gate RC；Q3 调 x-qa-gate R1→R2→R3。Gate ② 全部通过后把 checklist 标为 `[x] ✅`。

## 状态与记录

状态顺序为 `[ ] ⏳ → [ ] ▶️ → [ ] 🟡 → [x] 🟢 → [x] ✅`；Gate ② 负责最终 ✅。`reports/` 位于 task 根目录下，verify 或 qa-gate fail 依既有共享 fix-counter 交给 x-fix 批量修复。

## 完成回执

报告当前 task、完成项、修改文件、verify 结果、risk 路由、Gate ② 结果、manual 待验收项和遗留阻塞。连续模式在一个 task Gate 完成后按 graph 读取下一批 ready 项。
