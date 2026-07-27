# Journal Index Recovery 横向对比

生成日期：2026-07-24
最新版本：`iteration-6`
结构化数据：`journal-index-recovery-horizontal-comparison.json`

## 结论

完整流水线的真实 all-in Token 已从 baseline 的 **20,619,230** 降到最新的 **10,253,904**，下降 **50.27%**；工具执行调用从 trace 推导的 115 次降到 71 次，下降 **38.26%**。质量同步从当前 Rubric v2 的 **96 分降到 80 分**，最新运行仍有 5/25 项失败，因此未达到晋级门禁。

对抗阶段的首轮效率改善明显：iteration-5 Spec/Risk 使用 **1,411,304 tokens / 621.370 秒 / 25 次工具调用**；最新首次阶段使用 **270,385 tokens / 280.067 秒 / 5 次工具调用**，分别下降 **80.84% / 54.93% / 80.00%**。最新正式 Spec/Risk 分数为 41；同步 live Spec 后的诊断分为 65，仍低于 iteration-5 的 94。

## 运行身份与比较范围

| 名称 | 实际路径 | 执行范围 | 用途 |
|---|---|---|---|
| Baseline | `iteration-4/.../baseline/run-1` | 完整流水线 | 冻结基准 |
| Iteration-5 | `iteration-5/.../terra/run-1` | Spec/Risk，随后继续完整流水线 | 上一版对抗流程 |
| Iteration-6 | `iteration-6/.../terra/run-4` | 干净隔离的 Spec/Risk 单阶段 | 最新 skill 的独立阶段回放 |
| 最新 | `iteration-6/.../terra/run-1` | 原会话继续完成 Req3、Dev、Verify、QA、Fix | 当前完整结果 |

`run-4` 的编号更大，它的范围停在 Spec/Risk。`run-1` 后续继续执行了完整流水线，因此本报告把 `run-1` 的最终状态定义为“最新完整结果”。

## 核心指标

| 运行 | 范围 | 当前完整评分 | Spec/Risk 评分 | 总 Tokens | 有效 Tokens¹ | 主动/墙钟耗时 | 执行器时间和² | 工具执行调用 | LLM 调用 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | Full | **96，24/25** | — | 20,619,230 | 1,126,110 | 2,517.661 s | 3,958.170 s | 115³ | 未持久化 |
| Iteration-5 | Full | **88，22/25** | **94，16/17** | 10,576,219 | 357,979 | 1,765.038 s | 1,931.313 s | 80 | 未持久化 |
| Iteration-6 run-4 | Spec/Risk | — | **65，11/17** | 440,842 | 78,346 | 528.075 s | — | 12 | 未持久化 |
| 最新 Full | Full | **80，20/25** | **41，7/17；归一化 65** | 10,253,904 | 383,056 | 1,812.831 s | 2,070.698 s | 71 | 86 |

1. `有效 Tokens = 未缓存输入 + 输出`。它用于观察真正新增的上下文和输出量；all-in Token 继续作为用户成本主指标。
2. “执行器时间和”把嵌套 reviewer 时间加回主任务，用于表示总计算工作量。
3. Baseline 工具调用从四个冻结 rollout 重建：115 次执行调用，另有 25 次 spawn/wait/followup/list 等协调调用。后续版本保存的是执行工具调用口径。

费用字段为空：冻结产物没有保存模型价格表或货币成本，报告不推算价格。

## 公平的完整流水线对比

| 指标 | Baseline | Iteration-5 | 最新 | Iter-5 vs Baseline | 最新 vs Baseline | 最新 vs Iter-5 |
|---|---:|---:|---:|---:|---:|---:|
| Rubric v2 质量分 | 96 | 88 | 80 | -8 分 | -16 分 | -8 分 |
| Agent tree Tokens | 20,619,230 | 10,576,219 | 10,253,904 | **-48.71%** | **-50.27%** | **-3.05%** |
| 有效 Tokens | 1,126,110 | 357,979 | 383,056 | -68.21% | -65.98% | +7.01% |
| 主任务活跃耗时 | 2,517.661 s | 1,765.038 s | 1,812.831 s | **-29.89%** | **-28.00%** | +2.71% |
| 执行器时间和 | 3,958.170 s | 1,931.313 s | 2,070.698 s | **-51.21%** | **-47.69%** | +7.22% |
| 工具执行调用 | 115 | 80 | 71 | **-30.43%** | **-38.26%** | **-11.25%** |

最新版本实现了完整 Token 和工具调用下降。耗时相对 iteration-5 上升，质量分继续下降。当前优化已经压缩执行成本，质量保持能力仍未达标。

## 公平的 Spec/Risk 单阶段对比

| 指标 | Iteration-5 | Iteration-6 run-4 | 最新首次阶段 | run-4 vs Iter-5 | 最新 vs Iter-5 | 最新 vs run-4 |
|---|---:|---:|---:|---:|---:|---:|
| 固定 17 项评分 | **94** | **65** | **41；归一化 65** | -29 分 | -53 分；归一化 -29 | -24 分；归一化 0 |
| Tokens | 1,411,304 | 440,842 | 270,385 | **-68.76%** | **-80.84%** | **-38.67%** |
| 耗时 | 621.370 s | 528.075 s | 280.067 s | -15.02% | **-54.93%** | **-46.96%** |
| 工具调用 | 25 | 12 | 5 | -52.00% | **-80.00%** | -58.33% |
| Risk Tokens | 960,376 | 未分阶段持久化 | 199,733 | — | **-79.20%** | — |
| Risk 推理轮次 | 14 | 未持久化 | 4 | — | **-71.43%** | — |

最新正式 41 分受到旧 `spec.final.md` 交付产物影响；隔离环境中把 live Spec 同步到 final 后为 65。65 分仍有真实风险覆盖缺口，因此报告同时保留两个数字。

## Token I/O 分布

| 运行 | Input | Cached input | 未缓存 Input | Output | Reasoning output⁴ | Cache/Input | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 20,353,015 | 19,493,120 | 859,895 | 266,215 | 126,518 | 95.78% | 20,619,230 |
| Iteration-5 Full | 10,489,177 | 10,218,240 | 270,937 | 87,042 | 29,117 | 97.42% | 10,576,219 |
| Iteration-6 run-4 | 416,213 | 362,496 | 53,717 | 24,629 | 6,648 | 87.09% | 440,842 |
| 最新首次 Spec/Risk | 255,647 | 212,480 | 43,167 | 14,738 | 3,347 | 83.11% | 270,385 |
| 最新 Full | 10,168,151 | 9,870,848 | 297,303 | 85,753 | 32,477 | 97.08% | 10,253,904 |

4. Reasoning output 已包含在 Output 中，Cached input 已包含在 Input 中。

## Baseline Token 分布

Baseline 只保存了 agent 维度的稳定分桶：

| Agent | Tokens | 占比 |
|---|---:|---:|
| Main | 8,307,600 | 40.29% |
| Q1 intent | 2,389,925 | 11.59% |
| Q2 correctness | 4,044,696 | 19.62% |
| Q3 evidence | 5,877,009 | 28.50% |
| 总计 | **20,619,230** | **100.00%** |

三个 reviewer 合计消耗 59.71%。baseline 的主要效率问题来自完整上下文派生的三路独立评审。

## Iteration-5 Token 阶段分布

| 阶段 | Tokens | 占比 |
|---|---:|---:|
| x-spec3 初版 | 450,928 | 4.26% |
| x-adversarial-risk | 960,376 | 9.08% |
| Skill/tool loading + x-req3 | 2,591,564 | 24.50% |
| x-dev + tests | 1,522,619 | 14.40% |
| dev-report + Gate① | 361,173 | 3.41% |
| Gate② + reviewer | 1,367,399 | 12.93% |
| x-fix + reverify + reports | 3,322,160 | 31.41% |
| 总计 | **10,576,219** | **99.99%⁵** |

5. 百分比显示值经过两位小数舍入。

## 最新完整流水线 Token 阶段分布

| 阶段 | Tokens | 占比 |
|---|---:|---:|
| x-spec3 初版 | 70,652 | 0.69% |
| 首次 x-adversarial-risk | 199,733 | 1.95% |
| 协调、诊断、废弃 workspace | 1,065,039 | 10.39% |
| Risk 后续修正 | 718,657 | 7.01% |
| x-req3 | 338,234 | 3.30% |
| x-dev + local tests | 1,658,185 | 16.17% |
| 首次 Verify 阻断 | 298,892 | 2.91% |
| dev-report 修复 + Gate① | 610,846 | 5.96% |
| Gate② + reviewer | 2,102,165 | 20.50% |
| x-fix + full reverify | 2,263,278 | 22.07% |
| 增量 QA 关闭 + 回执 | 928,223 | 9.05% |
| 总计 | **10,253,904** | **100.00%** |

最新版本的首次 Spec/Risk 只占 2.64%。协调返工、Gate②、x-fix/reverify 合计占 59.97%，它们是后续优化的主要成本中心。

## 分数变化

完整实现统一使用当前 Rubric v2 重评：

| 运行 | 分数 | 通过项 | 关键门禁 |
|---|---:|---:|---|
| Baseline | **96** | 24/25 | 失败 |
| Iteration-5 | **88** | 22/25 | 失败 |
| 最新 | **80** | 20/25 | 失败 |

Baseline 原始旧评分器为 95/100；横向主表使用当前 25 项评分器的 96，保证评分规则一致。

最新 80 分失败项：

- Req3 checklist 的 Spec 指针和机械 validate。
- dev-report 的 unit/smoke/e2e 字面证据。
- 语义不可能 snapshot 的拒绝。
- 物理完整、状态迁移非法的 journal 尾记录 `CORRUPT_LOG` 分类。
- 完整七错误契约；它与上一条共享底层语义分类问题。

## 最终判断

| 目标 | 当前状态 |
|---|---|
| 完整流水线 Token 相对 baseline 下降至少 10% | **通过：-50.27%** |
| 工具调用相对 baseline 下降 | **通过：-38.26%** |
| Spec/Risk 首次 Token 相对 iteration-5 下降 | **通过：-80.84%** |
| 完整质量保持或提高 | **失败：96 → 88 → 80** |
| 当前 Rubric v2 质量 100 | **失败：80** |
| 关键门禁 | **失败** |
| 晋级 | **失败** |

下一轮应把质量恢复到 100 设为先决条件，同时保留“一次读取、一次集中修改、一次验证、一次回执”的首轮效率结构。重点修复 Spec 风险知识覆盖、Req3 指针契约、dev-report 证据生成和 QA 隐藏语义回归；完整 all-in Token 目标继续压到 8.5M 以下。

## 证据路径

- Baseline：`iteration-4/eval-11-journal-index-recovery/baseline/run-1/measurement.json`
- Baseline 当前评分：`iteration-6/eval-11-journal-index-recovery-spec-risk/terra/run-1/comparison-grading/iteration-4-baseline.json`
- Iteration-5 遥测：`iteration-5/eval-11-journal-index-recovery-spec-risk/terra/run-1/token-analysis.json`
- Iteration-5 当前评分：`iteration-6/eval-11-journal-index-recovery-spec-risk/terra/run-1/comparison-grading/iteration-5-terra.json`
- Iteration-6 run-4：`iteration-6/eval-11-journal-index-recovery-spec-risk/terra/run-4/`
- 最新完整遥测：`iteration-6/eval-11-journal-index-recovery-spec-risk/terra/run-1/full-pipeline-metrics.json`
- 最新完整评分：`iteration-6/eval-11-journal-index-recovery-spec-risk/terra/run-1/full-pipeline-grading.json`
- 最新 Spec/Risk 正式评分：`iteration-6/eval-11-journal-index-recovery-spec-risk/terra/run-1/post-pipeline-spec-risk-grading.json`
- 最新 live Spec 诊断：`iteration-6/eval-11-journal-index-recovery-spec-risk/terra/run-1/normalized-live-spec-risk-grading.json`
