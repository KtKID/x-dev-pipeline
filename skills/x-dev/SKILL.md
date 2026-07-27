---
name: x-dev
description: |
  开发任务执行 skill。读取单个 task 的 dev-checklist，按 `spec:` 指针跟读归属 spec 包，按依赖实现、写 verify 证据，并由 checklist 头部 risk 驱动交付或 Gate ②。
  触发：`x-dev 功能名称` 或现有 task 目录。
---

# x-dev — 统一执行

## 输入与边界

**x-dev 的作用域是单个 task**：目标目录 `docs/spec/<spec-name>/tasks/<task-name>/` 必须有 `dev-checklist.md`。一个 spec 下可以有多个 task，x-dev 只实现指定 task，不扫描或编排同级 task。

checklist 头部 `risk:` 定路由、`spec:` 定归属；任务行定顺序、状态、文件范围和验收范围。当前只读取 spec：

| Profile | task 回指 | 实现边界 | verify 责任 |
|---|---|---|---|
| spec/req | `Scenario` | spec.md 目标、影响边界与不变量、判断依据、建模声明及被引用 Scenario | unit/smoke 写 auto 块；e2e 写 auto 或 manual 块 |

dev-report 记录改动和 verify 证据。x-dev 消费 task，保持 spec 包原样。

## 执行

高能力模型在以下步骤内采用批次执行：独立读取、测试与静态检查放入同一工具批次；文件只在内容变化后重读；状态更新只携带新证据或阻塞，完成回执复用 dev-report 与 verify 结果。

1. 首个取证批次同时读取 checklist、引用的 spec 章节、原始契约样本、涉及的实现与测试文件，收集本 task 的 Scenario、涉及文件、所需边界、判断和模型，建立一次性的“Scenario → 代码 → 反例 → verify”矩阵。同时记录示例配置的原始字段集、CLI 调用、fixture 输入、wire/schema 和落盘布局。
2. 在取证批次运行 `python3 tools/xdev.py status <task-dir> --json` 与 `graph <task-dir> --json`。同优先级、无依赖、无同文件写冲突的 ready task 可并行；有依赖的 task 按拓扑序推进。
3. 将当前 checklist 项更新为进行中，按依赖批次集中修改实现、独立测试、dev-report 与 checklist 状态；每个失败根因一次修完全部关联位置。保持公开契约、不变量、失败路径和输入所有权，改动落在“涉及文件”范围内。扩展配置或输入 schema 时保留原始样本可运行：新增字段使用兼容默认值，除非 spec 明确要求迁移并提供迁移验收。
4. 为 task 承接的每个 Scenario 写 fenced `verify` 块，`scenario:` 精确回指 Scenario ID。unit/smoke 使用 auto，e2e 使用 auto 或 manual。dev-report 用字面标签 `unit`、`smoke`、`e2e` 标明实际采用的证据层。涉及配置、CLI、协议或文件布局时，至少一个 auto 块使用任务原始样本或其最小字段集启动真实入口并完成一条端到端链路。
5. 实现完成后更新 checklist 为待测试，先运行一个聚焦反例，再一次运行全部 verify 块声明的命令作为当前 task 完整测试；通过后更新为测试通过。每层绿灯只执行一次；失败时消费完整输出并按根因批量修复。
6. 运行一次 `python3 tools/xdev.py verify <task-dir> --json` 完成递增验证链：exit 2 修正 dev-report 格式；exit 1 将 fail 与 uncovered 一次交给 x-fix；exit 0 继续 risk 路由。
7. 按 checklist 头部 `risk:` 路由：Q0/Q1 输出完成回执及定级依据；Q2 调 x-qa-gate RC；Q3 调 x-qa-gate tri-lens reviewer。Gate ② 全部通过后把 checklist 标为 `[x] ✅`。

## 状态与记录

状态顺序为 `[ ] ⏳ → [ ] ▶️ → [ ] 🟡 → [x] 🟢 → [x] ✅`；Gate ② 负责最终 ✅。`reports/` 位于 task 根目录下，verify 或 qa-gate fail 依既有共享 fix-counter 交给 x-fix 批量修复。

## 完成回执

报告当前 task、完成项、修改文件、verify 结果、risk 路由、Gate ② 结果、manual 待验收项和遗留阻塞。

连续模式只在**当前 task 内部**推进：`graph` 的 ready 项是本 checklist 的任务行。本 task 走完 Gate 即结束，同 spec 的其他 task 由调用方另行启动。
