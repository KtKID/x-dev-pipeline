# qdev-risk-routed-verification

> 创建时间：2026-07-11
> 类型：优化
> 风险等级：Q2
> 审查路线：一个综合只读 reviewer

## 用户原始请求

> “帮我检查qdev技能流程，现在每次都走qa gate太耗时太费token了，而且还不能保证正确，因为文档可能有偏移，派子agent做可能把偏移拉大，后面的验证抓不到重点，你从第一性原理推理要怎么优化流程”
>
> “qdev本身要怎么改，对比现在优化了什么”
>
> “同意 开始改”

## 任务说明

把 x-qdev 从固定进入 x-verify/三段 QA gate 的流程调整为基于真实证据和风险等级分流。同步 qdev 模板及活跃的跨 skill 路由说明，保留完整 gate 作为高风险或用户显式指定的路线。

## 明示假设

| 编号 | 假设 | 依据 | 影响 |
|------|------|------|------|
| A1 | 用户同意此前提出的 Q0/Q1 主 agent 闭环、Q2 单 reviewer、Q3 完整流程方案 | 当前会话连续确认 | 决定本次路由结构 |

## DoD 与证据

| 编号 | DoD | 来源 | 证据计划 | 最终证据 | 状态 |
|------|-----|------|----------|----------|------|
| D1 | Q0/Q1 默认在 qdev 内完成证据闭环 | 用户确认方案 | 检查 x-qdev 路由文本 | 旧自动链扫描无命中；Q0/Q1 主 agent 路线存在 | ✅ |
| D2 | Q2 只使用一个综合 reviewer | 用户确认方案 | 检查 reviewer 输入与问题集 | 同一综合 reviewer 最终 pass，P0/P1/P2 均为 0 | ✅ |
| D3 | Q3 升级完整 x-req/x-dev/gate 流程 | 用户确认方案 | 检查风险触发条件 | `source-qdev` promotion mode 与 ↗️ 终态已验证 | ✅ |
| D4 | README 保存原始请求并区分假设与证据 | 第一性原理结论 | 检查 README 模板 | 原始请求、脱敏、假设、DoD、基线均已进入模板 | ✅ |
| D5 | 活跃文档和上下游触发说明保持一致 | 仓库 skill 契约 | 全局 rg + skill validator | 5 个 skill valid；旧链无命中；fence 平衡 | ✅ |

## 风险判断

- 风险等级：Q2
- 触发因素：修改公开 skill 路由，涉及 qdev、verify、fix 和仓库说明
- 升级条件：发现 manifest/schema 变化或需要新增运行时工具

## 任务起点基线

- `git status --short`：只有 `.claude/`、`.kongming/`、`.xcodeatlas/` 三个既有未跟踪目录
- 起点 changed paths：clean
- 起点 untracked paths：`.claude/`、`.kongming/`、`.xcodeatlas/`
- 与预期任务文件重叠：none
- 重叠文件初始 diff：N/A
- 用户既有改动保护策略：保留三个既有未跟踪目录，任务 diff 只覆盖明确列出的 skill/docs/task 文件

## 开发清单

| 编号 | 优先级 | 状态 | 任务 | 备注 |
|------|--------|------|------|------|
| #1 | P0 | ✅ 已完成 | 重写 x-qdev 风险分流和验证闭环 | D1-D3 |
| #2 | P0 | ✅ 已完成 | 更新 qdev README/dev-report/execution 模板 | D4 |
| #3 | P1 | ✅ 已完成 | 同步活跃跨 skill 和 README 契约 | D5 |
| #4 | P1 | ✅ 已完成 | 执行校验并记录证据 | D1-D5 |

## 预期涉及文件

- `skills/x-qdev/**`
- `skills/x-req/SKILL.md`
- `skills/x-verify/SKILL.md`
- `skills/x-qa-gate/SKILL.md`
- `skills/x-qa-gate/references/r1-spec-conformance.md`
- `skills/x-fix/SKILL.md`
- `skills/x-cr/references/auto-loop-mode.md`
- `skills/x-dev/templates/dev-report-template.md`
- `CLAUDE.md`
- `README.md`
- `README_zh.md`
- `CHANGELOG.md`
- `examples/req-modules-diagram-demo.md`
- `examples/req-modules-diagram-demo.html`

## 实际涉及文件

- `skills/x-qdev/SKILL.md`、`references/execution-rules.md`、`templates/README.md`、`templates/dev-report.md`
- `skills/x-req/SKILL.md`、`skills/x-verify/SKILL.md`、`skills/x-qa-gate/SKILL.md`、`skills/x-qa-gate/references/r1-spec-conformance.md`
- `skills/x-fix/SKILL.md`、`skills/x-cr/references/auto-loop-mode.md`、`skills/x-dev/templates/dev-report-template.md`
- `CLAUDE.md`、`README.md`、`README_zh.md`、`CHANGELOG.md`
- `examples/req-modules-diagram-demo.md`、`examples/req-modules-diagram-demo.html`
- `dev-pipeline/tasks/qdev-risk-routed-verification/README.md`、`changelog.md`、`dev-report.md`
