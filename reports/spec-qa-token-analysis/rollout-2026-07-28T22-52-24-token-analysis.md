# Codex Session Token 与分布分析

- **来源**: `rollout-2026-07-28T22-52-24-019fa936-6dd6-7450-b38b-ed3c9c9ab4d0.jsonl`
- **Session ID**: `019fa936-6dd6-7450-b38b-ed3c9c9ab4d0`
- **分析方法**: `skills/pipeline-efficiency-benchmark` 阶段 4 collect 口径
- **生成日期**: 2026-07-28

## 1. Run 身份与执行窗口

| 字段 | 值 |
|---|---|
| 模型 | `gpt-5.6-terra`（3 个 turn_context 均唯一模型） |
| Codex / originator | Codex Desktop 0.146.0-alpha.3.1（VS Code） |
| cwd | `/Volumes/machub_app/proj/kongming-agent` |
| 执行窗口（墙钟） | 14:53:16 → 15:13:40 UTC ≈ **20 分 24 秒（1224 s）** |
| Repo SHA | session_meta 内 `git.commit_hash` 一致，无跨 session 漂移 |
| 完整性 | 3 / 3 turn 均以 `task_complete` 收尾，`complete=true` |
| Sub-agent | 1 个 fork：`fork_lineage_tri_lens`（thread `019fa941…`），由 turn 3 内 `spawn_agent` 触发 |
| 任务 | x-dev-pipeline 完整链路 `x-spec → x-req → x-dev → Gate① → Q2 Gate②`，落地 fork 血缘导航 |

> 单一根 session，无 fork 前缀累计快照；Token 基线 = 0，所有累计量直接进入归一化。

## 2. Token 总量与归一化（整段 session）

口径：`total = input + output`；`uncached_input = input − cached_input`；`effective = uncached_input + output`。Cached input 是 Input 子集，reasoning_output 是 Output 子集。

| 分桶 | Tokens | 占比 |
|---|---:|---:|
| input | 9,238,501 | — |
| &nbsp;&nbsp;cached_input | 9,027,584 | 97.72% of input |
| &nbsp;&nbsp;uncached_input | 210,917 | 2.28% of input |
| output | 33,323 | 0.36% of total |
| &nbsp;&nbsp;reasoning_output | 11,750 | 35.3% of output |
| **total_tokens** | **9,271,824** | 100% |
| **effective_tokens** | 244,240 | 2.63% of total |

观察：

- **Input 完全主导**（≈99.6%），output 极小。这是典型长上下文 + 工具循环的 profile。
- 缓存命中率 **97.7%**，使实际付费 input 接近 cache read 单价。
- effective_tokens（真正"计费有意义"的部分）只有 24.4 万，约为 raw total 的 1/38 —— all-in total 受历史 context 累计放大严重。

## 3. 阶段（turn）分布

按 `task_started → task_complete` 边界切片，用各自前序 token_count 快照做 baseline。

| Turn / scope | input | cached | uncached | output | reasoning | total | 占比 | 墙钟 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| T1（spec / risk） | 36,073 | 11,520 | 24,553 | 160 | 107 | 36,233 | 0.4% | 5.8 s |
| T2（x-req） | 287,133 | 261,632 | 25,501 | 1,874 | 830 | 289,007 | 3.1% | 44.1 s |
| T3（dev→verify→qa→fix，含 fork） | 8,915,295 | 8,754,432 | 160,863 | 31,289 | 10,813 | 8,946,584 | 96.5% | 1,071 s |

- **T3 占据 96.5% 的 Token 与 87.6% 的墙钟**。其中 fork 子 agent 在 `fork_lineage_tri_lens` 完成实际编码与验证（T3 内含 `spawn_agent` + 4× `wait_agent`）。
- 每轮 uncached input 都稳定在 2.4–2.8 万区间 —— 说明新增净输入很小，绝大部分是重复发送的缓存 prefix。
- T3 的 output 增量（31 k）远高于 T1/T2，对应 spec/dev 报告与多轮工具往返。

## 4. 工具调用与失败率

| 指标 | 值 |
|---|---:|
| LLM 调用（token_count 快照） | 68 |
| 工具调用总数 | 65 |
| `exec`（custom） | 56 |
| `wait` / `wait_agent`（function） | 4 / 4 |
| `spawn_agent` | 1 |
| `patch_apply_end` | 10（成功 10，**失败 0**） |
| 错误输出（前缀含 error/failed） | 0 |

分布：T1 = 0 次工具调用；T2 = 5× exec；T3 = 51× exec + 4× wait + 4× wait_agent + 1× spawn_agent。无失败命令、无补丁回滚，执行链稳定。

## 5. 金额（gpt-5.6-terra 官方定价）

- **价格来源**: https://openai.com/api/pricing/
- **查询日期**: 2026-07-28
- **计费口径**: API 标准价（非 batch）

| 计费项 | 单价 / 1M Tokens | Tokens | 金额 (USD) |
|---|---:|---:|---:|
| Uncached input（标准输入） | $2.50 | 210,917 | $0.5273 |
| Cache-write input | $2.50（上限口径） | 0 | $0.0000 |
| Cached input（cache read） | $0.25 | 9,027,584 | $2.2569 |
| Output | $15.00 | 33,323 | $0.4998 |
| **API 等价成本（api_equivalent）** | | | **$3.2840** |
| API 等价成本（cache-write 上界） | | | $3.2840 |
| 无缓存成本（no_cache_api_equivalent） | | | $23.5961 |
| **缓存节省（cache_savings）** | | | **$20.3121（86.1%）** |

> provider 未单列 cache-write Tokens（本 session `cache_write_input_tokens=0`），故基础金额与上限金额相等；节省完全来自 cache read 的 90% 折扣。

金额结构：

- Cached input 占 api_equivalent 的 **68.7%**（最大单一项，但单价已是 1/10）。
- Uncached input 16.1%、Output 15.2% —— 由于 output 单价是 input 的 6 倍，3.3 万 output 的金额几乎与 21 万 uncached input 持平。
- 实付 input 均价 ≈ **$0.3555 / 1M**（相对 $2.50 基准打了 1.4 折）。

**各阶段金额（api_equivalent）**

| Turn | 金额 | 占比 |
|---|---:|---:|
| T1 spec/risk | $0.0667 | 2.0% |
| T2 x-req | $0.1573 | 4.8% |
| T3 dev→verify→qa→fix（fork） | $3.0601 | 93.2% |
| **合计** | **$3.2840** | 100% |

## 6. 套餐 / 现金口径

- **实际现金增量**: `unknown`（缺少该次调用的账单/套餐扣费证据；Codex Desktop subscription 口径未知）。
- **套餐额度倍数**: `unknown`（未提供订阅档位）。
- **可比性**: 本 run 为单根 session、单一模型、统一 cache 口径，可与其他同 scope（`full_pipeline`）、同模型 run 横向比较；不与不同 provider / 口径 run 直接比。

## 7. 关键结论

1. **Token 看似巨大（9.27M），实际计费只有 $3.28**。差异来自 97.7% 缓存命中 + cache read 1/10 单价。用 raw total 做降幅比较会严重失真，应改用 `api_equivalent` 或 `effective_tokens`。
2. **T3（dev + 验证 + QA + Fix，含 fork）独占 96.5% Token 与 93% 金额** —— 这是最值得做增量优化的阶段；T1/T2 优化空间可忽略。
3. **Output 极少但单价高**：3.3 万 output 贡献了 15% 的金额，压缩 assistant 回复长度有边际收益。
4. **工具链健康**：65 次调用、0 失败、10/10 补丁成功，无重试浪费。
5. 优化建议方向（不在本分析的范围）：减少 T3 内重复发送的 prefix、缩短 spec/dev 报告输出、评估 fork 子 agent 是否可裁剪上下文窗口。

## 附：缺失与局限

- 现金增量与套餐倍数缺失，金额章节以 `unknown` 标注原因后保留（符合 skill 规则：禁止静默省略金额）。
- 本分析为单 run descriptive，不构成 paired baseline/iteration 的降幅结论。
