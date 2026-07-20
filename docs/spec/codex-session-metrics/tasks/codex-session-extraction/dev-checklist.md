# codex-session-extraction · 开发清单

**状态体系**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

需求、模块与验收 Scenario 见归属 spec 包（`spec.md` + `modules.md`）。本清单只跟踪任务拆解与状态，不复述 spec 内容。

---

> spec: docs/spec/codex-session-metrics
> risk: Q3

## 任务清单

| # | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---------|-------------|------|---------|------|------|-----|
| T1 | P0 契约与边界：审查现有 diff，定义 Codex normalized source 与 provider-neutral measurement 的接口边界，新增 Codex 专用函数统一使用 `codex` 命名 | Provider 适配边界 | Measurement Core 中风险；Codex Session Source Parser 高风险 | 🔍 product:../../../../../tools/metrics.py | None | [x] ✅ | None |
| T2 | P0 活动窗口：实现首 metadata 身份、fork 前缀隔离、多回合完成性、统一模型、生命周期/执行窗口和活动窗口 rubric 扫描 | Codex 活动 session 隔离 | session 身份、窗口边界和 grader-only 系统不变量；Codex Session Source Parser 高风险 | 🔍 product:../../../../../tools/metrics.py | T1 | [x] ✅ | issue-1 |
| T9 | P0 多回合边界：接受多个活动 turn/task-complete，并要求最终活动 turn 被最后完成事件闭合 | Codex session 多回合提取 | 多回合完成性系统不变量；Codex Session Source Parser 高风险 | 🔍 product:../../../../../tools/metrics.py | T2 | [x] ✅ | issue-2 |
| T3 | P0 Token 差分：从活动回合前最后累计快照到最终完成前快照逐分桶计算，校验负增量并保留 provider total | Codex 增量 Token 提取 | Token 基线、分桶与总量系统不变量；Codex Session Source Parser 高风险 | 🔍 product:../../../../../tools/metrics.py | T9 | [x] ✅ | issue-2,issue-3,issue-4 |
| T4 | P0 生命周期耗时：以活动 session metadata 为开始、最后 assistant 回复为结束，并使用最终 task-complete 校验完整性 | Codex 多回合耗时 | 生命周期与执行窗口系统不变量；Codex Session Source Parser 高风险 | 🔍 product:../../../../../tools/metrics.py | T9 | [x] ✅ | None |
| T5 | P1 CLI 与兼容入口：加入 `--codex-session` 规范参数、保留 `--session` 与 `parse_rollout_source` 委托入口，维持 measurement schema | Codex 专用命名 | Metrics CLI Adapter 中风险；公共 CLI/API 兼容性 | 🔍 product:../../../../../tools/metrics.py | T1,T3,T4 | [x] ✅ | None |
| T6 | P0 回归测试：覆盖 fork 多回合精确用量/耗时、完整 Token 分桶、计数器回退、模型变化、未完成末回合、活动窗口 rubric 隔离及单回合兼容 | Codex 完整用量口径 | 全部系统不变量；Codex Session Source Parser 高风险 | 🔍 product:../../../../../test/test_metrics.py | T2,T3,T4,T5 | [x] ✅ | issue-5,issue-6 |
| T7 | P1 Provider 回归：验证 Measurement Core、quality 与 paired aggregate 继续消费 normalized source | Codex 提取兼容性 | Measurement Core 与 Metrics CLI Adapter 中风险 | product:../../../../../test/test_metrics.py | T5,T6 | [x] ✅ | None |
| T8 | P1 隐私与真实样本验收：验证父前缀 rubric 不误报、活动窗口 rubric 被拦截，并对真实 Codex session 核验 784,530 Token 与 466,265 ms | Codex 活动窗口隐私隔离 | grader-only 与活动窗口系统不变量；Codex Session Source Parser 高风险 | 🔍 product:../../../../../test/test_metrics.py, ../../../../../tools/metrics.py | T6,T7 | [x] ✅ | None |

## 并行机会

无依赖关系、可并行起子 agent 同时做（也可由 `python3 tools/xdev.py graph <task-dir> --json` 的 parallel_batches 自动算出）：

- T3 与 T4 在 T9 完成后可并行。

## 推荐执行顺序

```
T1 → T2 → T9 → [T3 ‖ T4] → T5 → T6 → T7 → T8
```

## fix-attempts 记录

每个 task 自身走完整 verify + qa-gate 流程时的 fix 次数累计，超 6 次须升级。

| Task | fix 次数 | 触发节点 | 备注 |
|------|---------|---------|------|
| codex-session-extraction | 1 | Gate ② q2/q3 | issue-1..6 已修复并通过增量复审 |

---

*产出时间：2026-07-21*
