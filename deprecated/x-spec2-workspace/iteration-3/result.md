# Scenario Pruning Paired Eval Result

## Comparison

- `arm-a` / metrics `with_skill` = `compact_spec`（15 Scenario）
- `arm-b` / metrics `without_skill` = `verbose_spec`（31 Scenario）
- Model: `gpt-5.6-sol`
- Repo SHA: `7a4b49821d6d394897b3937fba9b26f95048b99c`
- 每个 case 各执行一组 paired run；executor 只读取同一题面和匿名 `inputs/spec.md`，grader-only rubric 隔离。

## Results

| Eval | Compact quality | Verbose quality | Compact tokens | Verbose tokens | Finding |
|---|---:|---:|---:|---:|---|
| Run ledger | 5/6 | 5/6 | 110,940 | 199,805 | 总分相同，遗漏行为互补 |
| Knowledge lifecycle | 5/6 | 2/6 | 107,937 | 150,826 | Compact 更完整 |
| Paired promotion | 6/6 | 6/6 | 106,499 | 205,489 | 质量相同，Compact 成本更低 |
| Canary rollback | 4/6 | 6/6 | 106,559 | 150,469 | Compact 存在关键回归 |
| Contract/risk routing | 3/6 | 5/6 | 108,624 | 152,511 | Compact 存在关键回归 |
| **Overall** | **23/30 (76.7%)** | **24/30 (80.0%)** | **540,559** | **859,100** | Compact 少 37.1% executor Token，质量门禁失败 |

Compact 的 P0 失败为 5 条，Verbose 为 1 条。正确性硬门槛优先于 Token，当前 Compact 不能晋级为稳定 spec。

## Minimum Scenario Additions

保留 Compact 的结构与已验证收益，增加以下 5 个可执行 Scenario：

1. Stage 中断、部分持久化、安全重放与缺失指标原因。
2. 根因证据不足时分离 `detected_stage` 与 `origin_stage`。
3. 发布与回滚共享 revision/fencing，阻止旧控制操作覆盖新状态。
4. Canary 触发阈值、观测窗口、受影响 run、回滚原因与知识入库。
5. 逐阶段唯一 producer/consumer/source，以及退役字段或旧路径触发 `CONTRACT_DRIFT` 并阻止 baseline。

目标版本为约 20 个高价值 Scenario，保留“同一 run 新 attempt”、重评分、并发 canonical 去重、attempt 追溯和高风险完整路由等 Compact 已验证优势。

## Measurement Boundaries

- 5 个不同 case 各运行一次；结果证明跨题方向，尚未测量同题随机方差。
- `aggregate-spec2` 因共有 5 对样本输出 `pilot:false`，该字段当前无法表达“每题只有一次重复”。
- benchmark 中 `tool_calls=0` 表示 grader 未提供 execution metrics，不能解释为 executor 没有工具调用。
- Executor Token 为 1,399,659；5 个 grader 为 2,248,396；analyzer 为 653,712。
- 主 orchestrator 从 eval 阶段开始到 `2026-07-21T15:52:19.314Z` 的 provider 累计差分为 17,523,236 Token；当前 eval 设计与执行的总观测成本为 21,825,003 Token。
- Task-contract 已触发质量门禁，实施级 dev eval 本轮提前停止。

## Decision

当前 `compact_spec` 状态：`candidate_rejected_quality_gate`。

下一轮先创建约 20-Scenario 的 attempt 3，复跑 eval 3、4、6、7；关键断言全部通过后复跑 5 个 case，并增加同题重复次数衡量随机方差。
