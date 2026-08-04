# Benchmark 验收报告

生成日期：2026-07-27
Iteration / Run：spec-flow-20260727 / codex session `019fa27a-d0e0-7e30-9146-bf5478a5b02d`
验收结论：单次完整 spec→QA 流水线 token 与成本审计（无横向 baseline，不判定晋级）

## 结论

- 质量：本次仅做 token/成本审计，未运行隐藏 rubric。会话内主观终态为 x-verify 11/11 通过、x-qa-gate tri-lens 与增量复审均通过、x-fix 3 个 P1 全部关闭。
- 效率：spec→QA 全链路消耗 **25,878,594 all-in tokens**，wall-clock **67.5 分钟**，**159 次工具调用**，**183 次 LLM 完成（reasoning blocks）**。
- 金额：API 等价成本 **$18.17**；cache-write 上界 **$18.78**；无缓存成本 **$131.95**；缓存节省 **$113.78（86.2%）**；实际现金增量 unknown（Codex Desktop 订阅，无 token 级账单）。
- 晋级：不适用。本次为单 run 调查报告，未生成 baseline，未运行晋级门禁。

## 运行身份与范围

| 字段 | 值 |
|---|---|
| Provider / model / reasoning | openai / **gpt-5.6-sol** / 默认（reasoning_output 占 output 31.3%） |
| Context window | 258,400（短上下文档位，未触发长上下文单价） |
| Scope | `full_pipeline`（x-spec → x-req → x-dev → x-verify → x-qa-gate → x-fix → 增量复审） |
| Workspace preflight | 不适用（事后调查，非 candidate run） |
| Grader isolation | 不适用（未运行 grader） |
| Rubric | 不适用 |
| 会话来源 | `~/.codex/sessions/2026/07/27/rollout-2026-07-27T15-29-45-019fa27a-d0e0-7e30-9146-bf5478a5b02d.jsonl`（4.0 MB / 1328 行） |

### 流水线边界判定方法

会话前半段是关于「thread-12ac91193ce4 documents fail 气泡」的只读调查与方向讨论，**不属于本次 spec 流程**。spec 流程的起点由用户消息锚定：

- **起点**：line 310，`2026-07-27T08:04:22`，用户消息「补充首个非法工具出现时还得记录日志。走 x-spec流程吧」。
- **终点**：line 1318，`2026-07-27T09:11:29`，update_plan `explanation`：「x-dev 实现、x-verify 11/11、Q3 tri-lens 审查、gate-fix 与增量复审均已完成」。

Token 取 `token_count` 事件的累计 `total_token_usage`（223 个事件，全字段单调，跨子代理全局累计）。spec 起点前的累计基线为 line 304（`08:01:30`，cum_total 8,384,450），终点为最后一个 token 事件 line 1326（`09:11:52`，cum_total 34,263,044）。

## Token、耗时与调用

| 指标 | 值 |
|---|---:|
| Input | 25,776,408 |
| Cached input | 25,284,608（占 input **98.1%**） |
| Uncached input | 491,800 |
| Output | 102,186 |
| └ Reasoning output | 31,965（占 output **31.3%**） |
| Cache-write input | 0（provider 未单列 cache-write） |
| Total / all-in | **25,878,594** |
| Effective（uncached + output） | 593,986 |
| Main active（wall-clock） | 4,051 s（67.5 min，`08:04:22 → 09:11:52`） |
| 工具调用 | **159** |
| LLM 调用（reasoning blocks 代理） | **183** |
| 子代理 spawn | 2（`qa_tri_lens` @ line 1052，`qa_incremental` @ line 1260） |

> 说明：cached input 占比极高（98.1%）符合单 thread 长会话的特征——每一次新 LLM 请求都会把前面几乎完整的上下文作为缓存前缀复用，真正「新鲜」的输入只有约 49 万 tokens。Output 极低（10 万）相对 2580 万输入，说明这是一个重读、重审查的流水线（大量探索与 grep + 长上下文复核），而不是大量生成代码的任务。

## 金额

### 价格快照

| 字段 | 值 |
|---|---|
| 币种 | USD |
| 模型 | gpt-5.6-sol（Standard，短上下文） |
| 查询日期 | 2026-07-27 |
| 官方来源 | https://developers.openai.com/api/docs/pricing |
| Uncached input / 1M | $5.00 |
| Cached input / 1M | $0.50 |
| Cache-write input / 1M | $6.25 |
| Output / 1M | $30.00 |
| Cache-write tokens | 0（provider 未单列；按规则取上界估算） |

### 金额计算

provider 未单列 cache-write tokens（`cache_write_input_tokens = 0`），因此基础金额把全部 uncached input 按普通输入单价 $5.00 计算；cache-write 上界把全部 uncached input 按 $6.25 计算。

| 计费项 | Tokens | 单价 / 1M | 金额 |
|---|---:|---:|---:|
| Uncached input | 491,800 | $5.00 | $2.459 |
| Cached input | 25,284,608 | $0.50 | $12.642 |
| Cache-write input | 0（上界 491,800） | $6.25 | $0.000（上界 $3.074） |
| Output | 102,186 | $30.00 | $3.066 |
| **API 等价成本** | — | — | **$18.17** |
| Cache-write 上界 | — | — | $18.78 |
| 无缓存成本 | — | — | $131.95 |
| 缓存节省 | — | — | $113.78（86.2%） |

### 账单与套餐

| 字段 | 值 |
|---|---|
| Billing mode | unknown |
| 实际现金增量 | unknown |
| 套餐额度倍数 | unknown |
| 套餐额度等价金额 | unknown |
| 说明 | 会话来源是 Codex Desktop（VS Code 扩展，`thread_source: user`、`approval_policy: on-request`、`model_provider: openai`）。session_meta 未携带 token 级账单或套餐额度倍数，因此实际现金增量不可从遥测推导。仅给出按 OpenAI 公开 Standard 单价折算的 API 等价成本。 |

API 等价成本、实际现金增量、套餐额度等价金额分别陈列；后两项因无账单证据保留 `unknown`。

## Phase 分布

按 `update_plan` + `spawn_agent` 锚点切分。注意：x-verify 未单独成段，它发生在 x-dev 实现块内（line 1020 agent 报告「x-verify 已正式通过：11 个 Scenario 全绿」）。x-qa-gate 由两个子代理执行：`qa_tri_lens`（Q3 三视角审查）和 `qa_incremental`（修复后增量复审）。

| Phase | Tokens | Share | Wall-clock | Tool calls | LLM 调用 | API 等价成本 |
|---|---:|---:|---:|---:|---:|---:|
| x-spec | 2,134,330 | 8.2% | 14.3 min | 21 | 35 | $2.31 |
| x-req | 2,488,146 | 9.6% | 6.7 min | 14 | 19 | $1.73 |
| clarify（req→dev，术语澄清） | 357,612 | 1.4% | 3.7 min | 1 | 3 | $0.22 |
| x-dev 实现 + x-verify | 9,590,211 | **37.1%** | 18.3 min | 74 | 76 | **$7.10** |
| x-qa-gate tri_lens（含 spawn 等待） | 3,300,588 | 12.8% | 9.2 min | 12 | 13 | $1.96 |
| x-fix round 1（修 3×P1） | 5,239,875 | **20.2%** | 6.4 min | 26 | 26 | $3.18 |
| x-qa-gate incremental（含 spawn 等待） | 1,058,588 | 4.1% | 4.8 min | 5 | 5 | $0.58 |
| final report | 1,529,536 | 5.9% | 2.1 min | 6 | 6 | $0.98 |
| 段间过渡（turn 交接/收尾） | 179,708 | 0.7% | — | — | — | ~$0.14 |
| **合计** | **25,878,594** | **100%** | **67.5 min** | **159** | **183** | **$18.17** |

### 分布观察

1. **x-dev 实现块是唯一的大头（37.1% / $7.10）**——T1~T7 的红灯测试、Runner 合同实现、evo reviewer 集成与 11 个 Scenario 验证全部集中在此段，工具调用占整条链 46%（74/159），是优化优先级最高的阶段。
2. **x-fix round 1 占 20.2% / $3.18**——一次 tri-lens 审查触发 3 个 P1，修复 + 反例 + 完整复验成本接近整个 x-spec 阶段的 1.4 倍。说明「审查→修复」回路在长上下文下代价显著，因为每轮都要把完整 diff/Scenario 重新喂回。
3. **x-qa-gate 合计 16.9%（$2.54）**——两次子代理 spawn 各有 ~5–9 分钟的等待（`wait_agent` 共 12 次），子代理把完整高风险事实源逐条复核，input 主要来自缓存命中（cached 占比 99%+），所以金额不高但 wall-clock 明显。
4. **x-spec（8.2%）与 x-req（9.6%）相当**——x-spec 虽然耗时长（14.3 min，含一次 deep 风险预算的独立对抗审查），但 token 量与 x-req 接近，说明规划阶段 read-heavy 但生成少。
5. **缓存命中率 98.1%**——若无缓存，等价成本会从 $18.17 暴涨到 $131.95，缓存节省 $113.78（86.2%）。任何会进一步降低缓存复用的改动（例如频繁切换 thread、插入大段不重复内容）都会显著抬高成本。

## 横向比较

| Run | Scope | Quality | Total tokens | Tools | API 等价成本 | 实际现金增量 | 套餐额度等价金额 |
|---|---|---:|---:|---:|---:|---:|---:|
| Baseline | — | — | — | — | — | — | — |
| Candidate（本次 spec→QA） | full_pipeline | unknown（会话内自报通过） | 25,878,594 | 159 | $18.17 | unknown | unknown |

本次为单 run 调查，未生成 baseline run，横向对比留空。如需晋级判定，需在同一 model / reasoning / scope / Token 口径下另跑一次 baseline（仅移除待测 skill 影响）并产出 `comparison.json`。

## 晋级门禁

不适用。本次任务范围是「调查一次会话中 spec→QA 流程的 token 消耗与分布」，不包含 baseline、隐藏 rubric、preflight 与 grader-only 隔离检查，因此不执行 7 项默认晋级门禁。如需正式 benchmark，应按 `pipeline-efficiency-benchmark` SKILL 的 prepare→preflight→execute→collect→grade→compare→validate 流程重跑。

## 证据路径

- 原始 session：`~/.codex/sessions/2026/07/27/rollout-2026-07-27T15-29-45-019fa27a-d0e0-7e30-9146-bf5478a5b02d.jsonl`
- Token 遥测来源：session 内 `event_msg.payload.type == "token_count"` 的 `total_token_usage`（223 个事件，全字段单调递增，跨子代理全局累计）
- 价格来源：https://developers.openai.com/api/docs/pricing （gpt-5.6-sol Standard，查询日期 2026-07-27）
- 阶段锚点：session 内 `response_item` 的 `function_call name=update_plan`（7 次）与 `function_call name=spawn_agent`（2 次：`qa_tri_lens`、`qa_incremental`）
- `pricing.json` / `comparison.json` / `comparison.md`：未生成（本次为事后调查，非 candidate run）
- 模型判定依据：session_meta `payload.model == "gpt-5.6-sol"`（line 7 turn_context）

## 方法论备注

1. **起点为什么不是 line 8 的「documents fail」问题**：那是只读调查 + 方向讨论，用户在 line 309 才明确「走 x-spec 流程吧」，这是 pipeline 的真正入口。line 304 的累计 token（8,384,450）作为 baseline 扣除。
2. **为什么用累计差而不是 `last_token_usage` 求和**：`last_token_usage` 是单次请求增量，但子代理 spawn 后会把子代理的消耗并入主会话累计；直接对 `last` 求和会漏掉子代理合并的尖峰。累计差法（终点累计 − 起点累计）能完整覆盖主会话 + 两个 spawn 子代理的全部消耗。
3. **段间过渡 179,708 tokens（0.7%）**：phase 区段之间（spec→req、clarify→dev）的 agent 收尾消息与 token flush，未归入任何单一阶段，单独列出以保证合计自洽。
4. **失败工具输出 41 次**：其中 30 次集中在 x-dev 实现块——这是预期的「红灯测试先写后转绿」流程，不是异常重试。
