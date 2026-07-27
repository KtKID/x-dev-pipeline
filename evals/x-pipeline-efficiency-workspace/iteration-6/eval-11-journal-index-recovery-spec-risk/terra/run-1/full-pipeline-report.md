# Iteration 6 · Journal Index Recovery 完整流水线效率报告

生成时间：2026-07-24
执行器：`gpt-5.6-terra` / `xhigh`
范围：原 `run-1/workspace` 的 Spec、Risk、Req3、Dev、Verify、QA、Fix 全链路

## 结论

完整实现隐藏评分为 **80/100（20/25）**，关键门禁未通过。内部流水线显示通过：11 个测试通过，Gate① 为 16 pass / 0 fail / 0 uncovered，Gate② 首轮 5 个 P1 已在 1 轮 x-fix 中关闭，最终 P0/P1 均为 0。隐藏评分又发现 5 个漏检项。

效率优化呈现两个结果：

- 初次 `x-adversarial-risk` 从 iteration-5 的 960,376 tokens 降到 199,733，下降 79.2%；工具调用从 13 降到 3，LLM 调用从 14 降到 4。
- 初次结果留下元数据和风险覆盖问题，后续 risk 修正又消耗 718,657 tokens。Risk 从首次执行到门禁通过共 918,390 tokens，只比 iteration-5 低 4.4%；计入门禁诊断和规则解释后为 1,104,044，增加 15.0%。

完整流水线实际全成本为 10,253,904 tokens，比 iteration-5 同范围的 10,576,219 下降 3.0%。主任务活跃耗时为 30 分 12.831 秒，比 iteration-5 增加 2.7%。排除误切 workspace、诊断与重复交接产生的 1,065,039 tokens 后，有效执行成本下降 13.1%。当前质量分比 iteration-5 在同一版 25 项评分器下的 88 分低 8 分。

这说明四轮对抗协议显著压低了单次成本，首轮质量和一次交接成功率决定最终收益。本次额外 risk 修正、错误 workspace、缺失 verify 引擎、dev-report 格式返工和 QA 等待轮询消耗了大部分节省。

## 结果状态

| 项目 | 结果 |
|---|---:|
| 单元 / Smoke / E2E 测试 | 11 tests，exit 0 |
| Gate① | 16 pass，0 fail，0 manual，0 uncovered |
| Gate② 首轮 | P1 ×5 |
| x-fix | 1 轮 |
| Gate② 增量复审 | P0 ×0，P1 ×0 |
| 最终任务 | T1–T6 done，blocked 0 |
| 完整实现隐藏评分 | **80 / 100，20/25，关键门禁失败** |
| Spec/Risk 正式交付评分 | **41 / 100，7/17** |
| Live Spec 归一化诊断 | **65 / 100，11/17** |

内部 Gate 通过证明当前公开 Scenario 的闭环完成。隐藏评分的 80 分证明 QA 仍漏掉 req3 契约、证据层和三项高风险语义。

## 最终评分

### 完整实现：80 / 100

当前 `rubric_version: 2` 共 25 项，每项 4 分。本次通过 20 项、失败 5 项，关键门禁失败：

| 失败项 | 直接原因 |
|---|---|
| Req3 checklist | `spec:` 写成文件路径，R3Q1 期望 task 的真实 spec 归属，机械 validate exit 1 |
| Dev-report 证据 | 修正 verify 字段时移除了 `layer`，报告正文也没有字面 `unit / smoke / e2e` 三层标签 |
| 语义 snapshot | 只校验结构、seq 和 request 集合，没有验证每个 fingerprint 的 `expected_version` 是否能由合法历史产生 |
| 语义 tail | CRC 和字段都正确、状态转换非法的完整末条被判成 `RECOVERY_REQUIRED`，隐藏契约要求 `CORRUPT_LOG` 且保持字节 |
| 七类错误契约 | envelope、message 和多数 exit 正确；语义 tail 的错误分类连带使完整七类契约失败 |

### Spec/Risk：正式 41，语义诊断 65

正式交付评分仍为 41/100。后续 risk 修正只更新了 live `spec.md`，`artifacts/spec.final.md` 保留旧 YAML 版本，评分器继续读到旧产物，并判定 final artifact 与 live Spec 不一致。

隔离诊断中只把 live Spec 同步为 final artifact，分数为 65/100。这个 65 分仍失败：

- 初版 SC_11 的来源被改成 adversarial，破坏初版 Scenario provenance。
- AR-001 的场景关键词/可观测表达不满足固定评分。
- AR-002 语义 snapshot 缺失。
- AR-003 把完整语义非法末条写成可恢复尾部。
- AR-004 缺少 NOT_FOUND 与 VERSION_CONFLICT 的同场景覆盖。
- AR-005 的完整错误字段表达未命中固定契约。

### 同一版 25 项评分器的历史对比

| 运行 | 当前 Rubric v2 分数 | 通过项 | 关键门禁 |
|---|---:|---:|---|
| Iteration 4 baseline | **96** | 24/25 | 失败 |
| Iteration 3 with-skill | **92** | 23/25 | 失败 |
| Iteration 4 with-skill | **88** | 22/25 | 失败 |
| Iteration 5 Terra | **88** | 22/25 | 失败 |
| Iteration 6 本次 | **80** | 20/25 | 失败 |

本次分数比 iteration-5 低 8 分，比 iteration-4 baseline 低 16 分。新增 Risk 和内部 QA 提高了显式检查数量，最终实现仍遗漏语义 snapshot 与语义 tail；内部 Gate 的“通过”没有转化为隐藏质量提升。

## 耗时

耗时采用已完成 turn 的活跃时间，排除用户等待间隔。QA reviewer 嵌套在最终主 turn 中，因此主任务活跃时间代表墙钟执行时间；“执行器时间和”额外加上 reviewer，用于表示总计算工作量。

| 阶段 / turn | 活跃耗时 |
|---|---:|
| 初版 x-spec3 + risk | 280.025 s |
| 门禁诊断 | 34.931 s |
| 修正规则解释 | 16.799 s |
| 误切 workspace 的废弃执行 | 120.310 s |
| Risk 修正轮 | 92.655 s |
| Risk 来源修正 + req3 | 120.296 s |
| Dev + 初次 Verify 阻断 | 464.053 s |
| Gate① + QA + Fix + 复验 | 683.762 s |
| 主任务活跃时间 | **1,812.831 s / 30m12.831s** |
| QA reviewer 嵌套时间 | 257.867 s |
| 执行器时间和 | **2,070.698 s / 34m30.698s** |

排除协调失误后的主任务时间为 1,640.791 秒；加上 reviewer 后的有效执行器时间为 1,898.658 秒。

## Token 总量

计算口径：

```text
total_tokens = input_tokens + output_tokens
uncached_input_tokens = input_tokens - cached_input_tokens
tokens_excluding_cached_reads = uncached_input_tokens + output_tokens
```

`cached_input_tokens` 已包含在 input 中；`reasoning_output_tokens` 已包含在 output 中。

| 执行器 | Input | Cached input | Output | Reasoning output | Input + Output |
|---|---:|---:|---:|---:|---:|
| 主任务 | 9,826,634 | 9,581,568 | 72,213 | 21,098 | 9,898,847 |
| QA reviewer | 341,517 | 289,280 | 13,540 | 11,379 | 355,057 |
| Agent tree | **10,168,151** | **9,870,848** | **85,753** | **32,477** | **10,253,904** |

- 未缓存输入：297,303。
- 去除缓存读后的逻辑总量：383,056。
- 缓存占输入 97.08%，占全部 I/O token 96.26%。
- 全链路工具调用 71 次，LLM 调用 86 次。

高缓存率降低了重复上下文的实际推理输入成本，但总 token 统计、请求调度和墙钟耗时仍受多轮 continuation 影响。

## Token 阶段分布

| 阶段 | Tokens | 占比 |
|---|---:|---:|
| x-spec3 初版 | 70,652 | 0.69% |
| 首次 risk 四轮 | 199,733 | 1.95% |
| 协调、诊断和废弃 workspace | 1,065,039 | 10.39% |
| Risk 后续修正 | 718,657 | 7.01% |
| x-req3 | 338,234 | 3.30% |
| x-dev + 本地测试 | 1,658,185 | 16.17% |
| 缺少 verify 引擎造成的首次阻断 | 298,892 | 2.91% |
| dev-report 格式修正 + Gate① | 610,846 | 5.96% |
| Gate② 调度 + 独立 reviewer | 2,102,165 | 20.50% |
| x-fix + 完整 reverify | 2,263,278 | 22.07% |
| 增量 QA 关闭 + 最终回执 | 928,223 | 9.05% |
| 总计 | **10,253,904** | **100.00%** |

最大两项是 x-fix/reverify 和 Gate②，共占 42.57%。QA 主任务在等待 reviewer 时多次恢复模型，每次都重新携带约 15–16 万 cached input，是 Gate② 达到 210 万 tokens 的主要原因。

## 与 iteration-5 完整流水线对比

| 指标 | Iteration 5 | Iteration 6 本次 | 变化 |
|---|---:|---:|---:|
| Agent tree tokens | 10,576,219 | 10,253,904 | **-3.05%** |
| 主任务活跃时间 | 1,765.038 s | 1,812.831 s | **+2.71%** |
| 执行器时间和 | 1,931.313 s | 2,070.698 s | **+7.22%** |
| 工具调用 | 80 | 71 | **-11.25%** |

排除本次协调与废弃 workspace 开销后：

| 指标 | Iteration 5 | Iteration 6 有效执行 | 变化 |
|---|---:|---:|---:|
| Tokens | 10,576,219 | 9,188,865 | **-13.12%** |
| 执行器时间和 | 1,931.313 s | 1,898.658 s | **-1.69%** |
| 工具调用 | 80 | 59 | **-26.25%** |

Skill 本身带来了 token 和工具调用下降。实际全成本被运行编排问题抵消，耗时没有形成有效下降。

## Spec / Risk 专项对比

| 运行 | Tokens | 耗时 | 隐藏评分 |
|---|---:|---:|---:|
| Iteration 5 Spec/Risk | 1,411,304 | 621.370 s | 94 |
| Iteration 6 run-4 干净执行 | 440,842 | 528.075 s | 65 |
| Iteration 6 run-1 正式交付 | 270,385 | 280.067 s | 41 |
| Iteration 6 run-1 live Spec 归一化诊断 | — | — | 65 |

相对 iteration-5，run-1 首次执行 tokens 下降 80.84%，耗时下降 54.93%。相对干净 run-4，tokens 下降 38.67%，耗时下降 46.96%，正式交付评分从 65 降到 41；归一化后的 live Spec 仍为 65。

Risk 单独看：

| Risk 口径 | Tokens | 对 iteration-5 的变化 |
|---|---:|---:|
| Iteration-5 risk | 960,376 | 基准 |
| Iteration-6 首次四轮 | 199,733 | **-79.20%** |
| Iteration-6 后续修正 | 718,657 | 额外成本 |
| Iteration-6 risk 到门禁通过 | 918,390 | **-4.37%** |
| 再计入诊断与解释 | 1,104,044 | **+14.96%** |

初次四轮从 14 次 LLM 调用降到 4 次；完成全部修正后，risk 共使用 11 次 LLM 调用。计入门禁诊断和解释后达到 14 次，与 iteration-5 相同。

## 成本上升原因

1. 初次 risk 产物使用旧 YAML 元数据并遗漏两处 v2 来源格式，触发两个额外 risk turn。
2. 一次完整 continuation 误切到 `full-pipeline-run-1/workspace`，产生 879,385 tokens 后被废弃。
3. 原 workspace 首次缺少 `tools/xdev.py` 依赖链，Dev 完成后 Verify 停止，再次 continuation。
4. dev-report 由模型写成 `layer / command / expect`，与验证器的 `id / cmd / expect_exit` 契约不一致，Gate①增加 610,846 tokens。
5. QA reviewer 等待期间主任务多次恢复，每次重新读取长上下文；Gate②调度和 reviewer 共消耗 2,102,165 tokens。
6. QA 找到 5 个真实 P1，修复与完整复验消耗 2,263,278 tokens。这部分增强了 snapshot 结构校验、恢复分类、compact、CLI 和并发证据；隐藏评分继续发现语义 snapshot 与语义 tail 漏检。

## 下一轮优化规则

1. 在启动执行器前一次性预检七个 skill、四个 `tools/*.py`、模板和目标 workspace；缺件直接阻断启动。
2. Spec/Risk 同一 turn 内允许 validator 格式错误的一次确定性修正，语义 patch 仍保持一次集中修改。这样保留四轮语义预算，同时避免格式错误开启新 turn。
3. 由 `xdev.py` 从 checklist 机械生成 dev-report verify 块骨架，LLM 只填命令和预期，消除字段漂移。
4. QA reviewer 使用单次长等待或完成回调，主任务等待期间不唤醒模型输出状态消息。
5. Gate①通过后为 QA/Fix建立裁剪上下文，只携带 Spec 相关段、diff、测试、issue ledger 和 verify 结果；完整历史保留在磁盘。
6. 报告同时保留 all-in 与 effective 两个口径。all-in 衡量真实用户成本，effective 用于判断 skill 本身的优化效果。

下一轮验收目标应设为：完整实现隐藏评分 100、Spec/Risk 正式 artifact 与 live Spec 同步、首次 Risk 门禁 exit 0、无 workspace 纠正、无工具缺失、Gate②等待零模型唤醒；在质量门禁达标后，完整流水线 all-in tokens 至少下降 20%。

## 证据

- 当前主会话：`019f8fab-99eb-7f51-badc-9f44be54ee81`
- QA reviewer：`019f9208-7665-72c1-9478-11f800ce8553`
- 结构化指标：`full-pipeline-metrics.json`
- 完整实现评分：`full-pipeline-grading.json`
- Spec/Risk 正式评分：`post-pipeline-spec-risk-grading.json`
- Live Spec 归一化诊断：`normalized-live-spec-risk-grading.json`
- 历史同口径评分：`comparison-grading/*.json`
- Gate②报告：`workspace/docs/spec/journal-index-recovery/tasks/journal-index-recovery-backend/reports/qa-gate/qa-gate-report-20260724-105529.md`
- Fix 报告：`workspace/docs/spec/journal-index-recovery/tasks/journal-index-recovery-backend/reports/fix/fix-gate-r1-20260724-105529.md`
