---
name: x-dev
description: |
  开发任务执行 skill。读取单个 task 的 dev-checklist，按 `spec:` 指针跟读归属 spec 包，按依赖实现、写 verify 证据，并由 checklist 头部 risk 驱动交付或 Gate ②。
  触发：`x-dev <功能名称>` 或现有 task 目录。
---

# x-dev — 统一执行

## 输入与边界

**x-dev 的作用域是单个 task**：目标目录 `docs/spec/<spec-name>/tasks/<task-name>/` 必须有 `dev-checklist.md`（无 README，x-req 不再产出）。一个 spec 下可以有多个 task，x-dev 只实现被指定的这一个，不扫描同级 task、不跨 task 编排、不为兄弟 task 的 Requirement 负责。

输入分三层：checklist 头部 `risk:` 定路由、`spec:` 定归属；checklist 任务行定顺序、状态与本 task 承接的 Requirement 范围；归属 spec 包定实现边界——`spec.md` 给需求、系统不变量与验收 Scenario，`modules.md` 给模块职责、边界类/对外契约与依赖，`design.md`（按需产出，可能不存在）给数据流、状态流转与故障恢复。dev-report 记录改动及 verify 证据。x-dev 消费 task，不创建也不修改 spec 包。

## 执行

1. 读 `dev-checklist.md` 的头部（`spec:`、`risk:`）与任务行，收集本 task 承接的 Requirement 名与涉及文件；按 `spec:` 跟读归属 spec 包：`spec.md` 只读这些 Requirement 及其 Scenario、加上系统不变量与范围边界（兄弟 task 承接的 Requirement 不在本次实现范围内），`modules.md` 读涉及模块的职责、边界类/对外契约、依赖与风险，`design.md` 存在时读相关动态模型。
2. 运行 `python3 tools/xdev.py status <task-dir> --json` 与 `graph <task-dir> --json`。同优先级、无依赖、无同文件写冲突的 ready task 可并行；有依赖的 task 按拓扑序推进。
3. 将当前 checklist 项更新为进行中，实现时保持 `modules.md` 的边界类/对外契约、`spec.md` 的系统不变量与 `design.md` 的失败路径；改动落在 checklist「涉及文件」声明的范围内。
4. 本 task 承接的 Requirement 下每个 `验证: auto` Scenario，在 `dev-report.md` 写一个 auto fenced `verify` 块，用 `scenario:` 精确回指 `spec.md` 的场景名；补齐单元、契约和边界测试（spec 包不声明测试责任，由 x-dev 按实际改动负责）。manual Scenario 写步骤块。
5. 实现完成后更新 checklist 为待测试，运行全部 verify 块声明的命令；通过后更新为测试通过。
6. 运行 `python3 tools/xdev.py verify <task-dir> --json`：exit 2 修正 dev-report 格式；exit 1 将 fail 与 uncovered 一次交给 x-fix；exit 0 继续 risk 路由。
7. 按 checklist 头部 `risk:` 路由：Q0/Q1 输出完成回执及定级依据；Q2 调 x-qa-gate RC；Q3 调 x-qa-gate R1→R2→R3。Gate ② 全部通过后把 checklist 标为 `[x] ✅`。

## 状态与记录

状态顺序为 `[ ] ⏳ → [ ] ▶️ → [ ] 🟡 → [x] 🟢 → [x] ✅`；Gate ② 负责最终 ✅。`reports/` 位于 task 根目录下，verify 或 qa-gate fail 依既有共享 fix-counter 交给 x-fix 批量修复。

## 完成回执

报告当前 task、完成项、修改文件、verify 结果、risk 路由、Gate ② 结果、manual 待验收项和遗留阻塞。

连续模式只在**当前 task 内部**推进：`graph` 的 ready 项是本 task checklist 的任务行，不是同 spec 下的兄弟 task。本 task 走完 Gate 即结束，同 spec 的其他 task 需要另行调用 x-dev，由调用方决定顺序。
