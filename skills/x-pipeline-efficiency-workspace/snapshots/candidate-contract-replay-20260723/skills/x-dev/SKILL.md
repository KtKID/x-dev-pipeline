---
name: x-dev
description: |
  开发任务执行 skill。读取单个 task 的 dev-checklist，按 `spec:` 指针跟读归属 spec 包，按依赖实现、写 verify 证据，并由 checklist 头部 risk 驱动交付或 Gate ②。
  触发：`x-dev <功能名称>` 或现有 task 目录。
---

# x-dev — 统一执行

## 输入与边界

**x-dev 的作用域是单个 task**：目标目录 `docs/spec/<spec-name>/tasks/<task-name>/` 必须有 `dev-checklist.md`。一个 spec 下可以有多个 task，x-dev 只实现指定 task，不扫描或编排同级 task。

checklist 头部 `risk:` 定路由、`spec:` 定归属；任务行定顺序、状态、文件范围和验收范围。按归属 spec 版本读取：

| Profile | task 回指 | 实现边界 | verify 责任 |
|---|---|---|---|
| spec2/req2 | `Requirement` | spec.md Requirement/Scenario + modules.md + 按需 design.md | `验证:auto` 写 auto 块，manual 写步骤块 |
| spec3/req3 | `Scenario` | spec.md 目标、影响边界与不变量、判断依据、建模声明及被引用 Scenario | unit/smoke 写 auto 块；e2e 写 auto 或 manual 块 |

dev-report 记录改动和 verify 证据。x-dev 消费 task，保持 spec 包原样。

## 执行

1. 读 checklist 头部和任务行，识别 spec2 或 spec3 profile，收集本 task 的 Requirement/Scenario 与涉及文件；只加载归属 spec 中实现这些行为所需的边界、判断和模型。同时记录任务提供的可执行契约样本：示例配置的原始字段集、CLI 调用、fixture 输入、wire/schema 和落盘布局。
2. 运行 `python3 tools/xdev.py status <task-dir> --json` 与 `graph <task-dir> --json`。同优先级、无依赖、无同文件写冲突的 ready task 可并行；有依赖的 task 按拓扑序推进。
3. 将当前 checklist 项更新为进行中，保持公开契约、不变量、失败路径和输入所有权；改动落在“涉及文件”范围内。扩展配置或输入 schema 时保留原始样本可运行：新增字段使用兼容默认值，除非 spec 明确要求迁移并提供迁移验收。
4. 为 task 承接的每个 Scenario 写 fenced `verify` 块，`scenario:` 精确回指场景名。spec2 遵循场景的验证标记；spec3 的 unit/smoke 使用 auto，e2e 使用 auto 或 manual。dev-report 用字面标签 `unit`、`smoke`、`e2e` 标明实际采用的证据层。涉及配置、CLI、协议或文件布局时，至少一个 auto 块使用任务原始样本或其最小字段集启动真实入口并完成一条端到端链路。
5. 实现完成后更新 checklist 为待测试，运行全部 verify 块声明的命令；通过后更新为测试通过。
6. 运行 `python3 tools/xdev.py verify <task-dir> --json`：exit 2 修正 dev-report 格式；exit 1 将 fail 与 uncovered 一次交给 x-fix；exit 0 继续 risk 路由。
7. 按 checklist 头部 `risk:` 路由：Q0/Q1 输出完成回执及定级依据；Q2 调 x-qa-gate RC；Q3 调 x-qa-gate R1→R2→R3。Gate ② 全部通过后把 checklist 标为 `[x] ✅`。

## 状态与记录

状态顺序为 `[ ] ⏳ → [ ] ▶️ → [ ] 🟡 → [x] 🟢 → [x] ✅`；Gate ② 负责最终 ✅。`reports/` 位于 task 根目录下，verify 或 qa-gate fail 依既有共享 fix-counter 交给 x-fix 批量修复。

## 完成回执

报告当前 task、完成项、修改文件、verify 结果、risk 路由、Gate ② 结果、manual 待验收项和遗留阻塞。

连续模式只在**当前 task 内部**推进：`graph` 的 ready 项是本 checklist 的任务行。本 task 走完 Gate 即结束，同 spec 的其他 task 由调用方另行启动。
