# Journal Index Recovery 横向对比（含金额）

生成日期：2026-07-26
当前候选：`minimax-glm52-20260725`
Baseline：`iteration-4-terra-baseline`
晋级：**FAIL**

## 金额结论

- 同一案例的 GPT-5.6 Sol 历史结果位于 Iteration 3：run-1 API 等价成本为 **$7.897449**，run-2 为 **$9.938765**，两次均为完整流水线且质量 100。
- Iteration 6 完整流水线 API 等价成本为 **$4.497265**；相对 Iteration 4 Terra baseline 的 **$11.016243** 下降 **$6.518978 / 59.18%**。
- Iteration 7 可计费历史数据为 Top5 本地 replay 的长会话增量切片，API 等价成本为 **$0.257437**。原始 Top1 run 保存了执行产物，Token 遥测字段为空。
- 当前 GLM-5.2 完整流水线 API 等价成本为 **$3.822014**；[Coding Plan FAQ](https://docs.z.ai/devpack/faq) 规定受支持工具内的调用只消耗套餐额度，因此现金增量扣款为 **$0.00**。本次处于 [Coding Plan](https://docs.z.ai/devpack/overview) 定义的 `3×` 峰值额度时段，对应 **$11.466042** API 等价额度权重。
- 当前 GLM-5.2 相对两次 Sol 完整流水线均值 **$8.918107** 的算术金额下降为 **$5.096093 / 57.14%**。模型、provider、reasoning 与 rubric 均发生变化，该值作为跨模型成本背景。

用户所称 `sol5.6` 对应 `gpt-5.6-sol`。Journal Index Recovery 的 Iteration 4–7 历史运行使用 `gpt-5.6-terra`。

## 价格与计算口径

| 模型 | Uncached input / 1M | Cached input / 1M | Output / 1M | 来源 |
|---|---:|---:|---:|---|
| GPT-5.6 Sol | $5.00 | $0.50 | $30.00 | [OpenAI model pricing](https://developers.openai.com/api/docs/models/compare) |
| GPT-5.6 Terra | $2.50 | $0.25 | $15.00 | [OpenAI model pricing](https://developers.openai.com/api/docs/models/compare) |
| GLM-5.2 | $1.40 | $0.26 | $4.40 | [Z.ai Pricing](https://docs.z.ai/guides/overview/pricing) |

基础 API 等价成本：

```text
uncached_input × uncached_rate
+ cached_input × cached_rate
+ output × output_rate
```

GPT-5.6 官方说明 cache write 按 uncached input 的 `1.25×` 计费，cache read 享受 90% 折扣。冻结遥测只区分 cached read 与 uncached input，未单列 cache-write tokens。因此 GPT 行的主金额按普通 uncached input 计费，同时给出“全部 uncached input 均为 cache write”的上界。GLM-5.2 官方页面列出的 cached input storage 当前为限时免费。

报告中的金额属于 **API 等价成本**。历史 GPT/Codex 产物未保存账户账单或套餐边际扣款，现金金额保持 `unknown`；当前 GLM run 保存了 Coding Plan provider 证据，现金增量为 `$0.00`。

## 完整流水线横向金额

| Run | Model / reasoning | Rubric / quality | Input | Cached | Output | Total | API 等价成本 | Cache-write 上界 | 无缓存成本 | 缓存节省 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Iteration 3 Sol run-1 | GPT-5.6 Sol | legacy v1 / 100 | 6,500,553 | 6,175,488 | 106,146 | 6,606,699 | **$7.897449** | $8.303780 | $35.687145 | $27.789696 · 77.87% |
| Iteration 3 Sol run-2 | GPT-5.6 Sol | legacy v1 / 100 | 9,304,267 | 8,951,040 | 123,237 | 9,427,504 | **$9.938765** | $10.380299 | $50.218445 | $40.279680 · 80.21% |
| Iteration 4 Terra baseline | GPT-5.6 Terra / xhigh | v2 / 96 | 20,353,015 | 19,493,120 | 266,215 | 20,619,230 | **$11.016243** | $11.553677 | $54.875763 | $43.859520 · 79.93% |
| Iteration 5 Terra Full | GPT-5.6 Terra / xhigh | v2 / 88 | 10,489,177 | 10,218,240 | 87,042 | 10,576,219 | **$4.537533** | $4.706868 | $27.528573 | $22.991040 · 83.52% |
| Iteration 6 Terra Full | GPT-5.6 Terra / xhigh | v2 / 80 | 10,168,151 | 9,870,848 | 85,753 | 10,253,904 | **$4.497265** | $4.683079 | $26.706673 | $22.209408 · 83.16% |
| Iteration 8 GLM-5.2 Full | GLM-5.2 / max | v3 / 96 | 12,357,980 | 12,167,104 | 88,941 | 12,446,921 | **$3.822014** | $3.822014 | $17.692512 | $13.870499 · 78.40% |

`Cached` 是 `Input` 的子集；`Total = Input + Output`。Reasoning output 已包含在 Output 中。

## 金额变化

| 对比 | 金额变化 | 百分比 | 可比性 |
|---|---:|---:|---|
| Iteration 3 Sol run-2 vs run-1 | +$2.041316 | +25.85% | 同模型、同 prompt、同 100 分；体现运行方差 |
| Iteration 5 Terra Full vs Iteration 4 baseline | -$6.478710 | -58.81% | 同模型与 reasoning；质量 96 → 88 |
| Iteration 6 Terra Full vs Iteration 4 baseline | -$6.518978 | -59.18% | 同模型与 reasoning；质量 96 → 80 |
| Iteration 6 Terra Full vs Iteration 5 Terra Full | -$0.040268 | -0.89% | 同模型与 reasoning；质量 88 → 80 |
| Iteration 8 GLM Full vs Sol 两次均值 | -$5.096093 | -57.14% | 跨 provider/model/rubric 算术背景 |
| Iteration 8 GLM Full vs Iteration 6 Terra Full | -$0.675251 | -15.01% | 跨 provider/model/rubric 算术背景 |

同模型 Terra 成本从 Iteration 5 到 Iteration 6 基本持平，质量下降 8 分。Iteration 5 已完成主要成本压缩；Iteration 6 的继续优化集中在首阶段，完整流水线的 Gate②、修复和复验继续承担主要成本。

## Iteration 6 / 7 Spec-Risk 历史金额

| Run | 范围 | Total | Effective | Tools | API 等价成本 | Cache-write 上界 | 说明 |
|---|---|---:|---:|---:|---:|---:|---|
| Iteration 6 run-4 | 干净隔离 Spec/Risk | 440,842 | 78,346 | 12 | **$0.594352** | $0.627925 | 固定 17 项得分 65 |
| Iteration 6 run-1 initial | 首次 Spec/Risk 阶段 | 270,385 | 57,905 | 5 | **$0.382108** | $0.409087 | 正式 41；live 归一化 65 |
| Iteration 7 Top1 | Spec/Risk 原始 run | — | — | — | **unknown** | unknown | 执行产物完整，历史文件未保存 Token 遥测 |
| Iteration 7 Top5 | 长会话本地 replay 增量切片 | 761,413 | 16,965 | — | **$0.257437** | $0.266595 | 53.188 秒；cached input 744,448 |

Iteration 7 Top5 相对 Iteration 6 run-1 initial 的算术金额下降为 `$0.124671 / 32.63%`，相对 Iteration 6 clean run-4 下降为 `$0.336915 / 56.69%`。Top5 数据来自既有长会话增量，Iteration 6 数据来自完整独立阶段；这两项适合观察金额量级，晋级比较保持隔离。

Iteration 7 当前提供 Spec/Risk 局部数据；完整流水线金额仍由 Iteration 6 历史 run 和 Iteration 8 当前 run 承担横向比较。

## 核心效率指标

| Run | Scope | Total tokens | Effective tokens | Main / wall seconds | Executor seconds | Tools | LLM calls |
|---|---|---:|---:|---:|---:|---:|---:|
| Iteration 3 Sol run-1 | full_pipeline | 6,606,699 | 431,211 | 1,539.247 | — | — | — |
| Iteration 3 Sol run-2 | full_pipeline | 9,427,504 | 476,464 | 1,872.470 | — | — | — |
| Iteration 4 Terra baseline | full_pipeline | 20,619,230 | 1,126,110 | 2,517.661 | 3,958.170 | 115 | — |
| Iteration 5 Terra Full | full_pipeline | 10,576,219 | 357,979 | 1,765.038 | 1,931.313 | 80 | — |
| Iteration 6 Terra Full | full_pipeline | 10,253,904 | 383,056 | 1,812.831 | 2,070.698 | 71 | 86 |
| Iteration 8 GLM-5.2 Full | full_pipeline | 12,446,921 | 279,817 | 1,954.928 | 2,379.348 | 187 | 164 |

Iteration 3 的冻结 measurement 保存的是整次 run wall time；后续行保存 main active time。Iteration 3 的冻结 measurement 未保存稳定的工具调用和 LLM 调用口径，表中保持为空。

## Candidate Token 分布

| Phase | Tokens | Share | Tool calls |
|---|---:|---:|---:|
| bootstrap + x-spec3 + risk | 1,980,931 | 15.92% | 62 |
| x-req3 | 653,356 | 5.25% | 9 |
| x-dev + tests + dev-report | 3,813,884 | 30.64% | 38 |
| Gate 1 verify | 595,598 | 4.79% | 5 |
| Gate 2 orchestration | 246,708 | 1.98% | 2 |
| Gate 2 reviewer | 2,130,997 | 17.12% | 49 |
| x-fix + reverify + closeout | 3,025,447 | 24.31% | 22 |
| **Total** | **12,446,921** | **100.00%** | **187** |

## 晋级门禁

- PASS · 相同 scope 与 Token 口径。
- FAIL · provider/model/reasoning：baseline 为 `gpt-5.6-terra/xhigh`，candidate 为 `GLM-5.2/max`。
- FAIL · 当前 rubric：baseline 为 v2，candidate 为 v3。
- FAIL · 完整流水线质量：`96 < 100`。
- FAIL · critical gate：末条 CRC 损坏恢复断言失败。
- FAIL · Token 与金额降幅：缺少同 provider、同模型、同 reasoning baseline。
- FAIL · workspace preflight：原执行未保存 candidate preflight，且读取了 workspace 外的 embedding model。
- PASS · grader isolation：候选 workspace 与会话 trace 均无 grader-only 材料。

当前 run 保留为失败样本。下一次比较应建立 `GLM-5.2/max` clean baseline，并同时报告 API 等价成本、现金增量和套餐额度权重。

## 证据路径

- Sol 5.6 run-1：`iteration-3/eval-11-journal-index-recovery/with_skill/run-1/measurement.json`
- Sol 5.6 run-2：`iteration-3/eval-11-journal-index-recovery/with_skill/run-2/measurement.json`
- Iteration 4–6 历史总表：`iteration-6/reports/journal-index-recovery-horizontal-comparison.json`
- Iteration 7 Top1：`iteration-7/eval-11-journal-index-recovery-spec-risk/llm/run-1/workspace/artifacts/run-summary.json`
- Iteration 7 Top5：`iteration-7/eval-11-journal-index-recovery-spec-risk/top5/run-1/workspace/artifacts/run-summary.json`
- Iteration 8 GLM：`iteration-8/runs/minimax-glm52-20260725/full-pipeline-metrics.json`
- Iteration 8 GLM 金额与验收：`iteration-8/runs/minimax-glm52-20260725/acceptance-report.md`
