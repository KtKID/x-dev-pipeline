# Benchmark 验收报告

生成日期：2026-07-28
Iteration / Run：baseline-directdev-20260727 / Codex session `019fa431-8211-7ee0-a222-c90ac0dd3cc6`
验收结论：单 run token/成本基线（不走 spec 流程的纯开发）；无 candidate、无隐藏 rubric，不判定晋级

## 结论

- 质量：未运行隐藏 rubric。会话内事实——直接开发产出代码与 32 次 patch_apply，但在 turn 2 被用户判定为流程违规（"你为什么直接开发了，还没走 x-spec 流程"），产出需重走流程；turn 3 在尝试 x-spec 时被用户中断（turn_aborted）。
- 效率：全 session 消耗 **19,674,483 all-in tokens**，wall-clock **39.9 分钟**，**147 次工具调用**，**145 次 LLM 完成（reasoning blocks 代理）**，**32 次 patch_apply**。其中 **97.7% 的 token 发生在"直接开发"窗口**（19.22M / 30.0 min）。
- 金额：API 等价成本 **$13.56**；cache-write 上界 **$14.12**；无缓存成本 **$99.80**；缓存节省 **$86.24（86.41%）**；实际现金增量 unknown（Codex Desktop 订阅会话，无 token 级账单）。
- 晋级：不适用。本次为"不走流程纯开发"的 **baseline 基线调查**，未运行候选 skill、隐藏 rubric、preflight 与 grader-only 隔离检查，不执行 7 项默认晋级门禁。

## 运行身份与范围

| 字段 | 值 |
|---|---|
| Provider / model / reasoning | openai / **gpt-5.6-sol** / default（reasoning_output 占 output 31.0%） |
| Session id | `019fa431-8211-7ee0-a222-c90ac0dd3cc6` |
| Repo sha（session 内） | `b19e5d36519ccc9ea47a76e848408cd6c146e1da`（分支 `private-main`） |
| Scope | `full_pipeline`（事后归档；实际为"直接开发 + 被纠偏 + 中断"三段） |
| Workspace preflight | 不适用（事后调查，非 candidate run） |
| Grader isolation | 不适用（未运行 grader） |
| Rubric | 不适用 |
| 会话来源 | `~/.codex/sessions/2026/07/27/rollout-2026-07-27T23-28-55-019fa431-8211-7ee0-a222-c90ac0dd3cc6.jsonl`（2.4 MB / 749 行） |

### 为什么直接调用 skill 的 `parse_codex_session_source` 会失败

skill 的 `assets/executor-tools/metrics.py::parse_codex_session_source` 要求"最后活动 turn_context 之后存在 task_complete"，否则按 `InvalidSample` 拒绝。本 session 最后一个 turn（L740）以 `turn_aborted`（L749）结束，无 task_complete，因此官方 parser 不接受。

本次采用 collect 阶段的等价方法论手工切窗：以 `event_msg.payload.type == "token_count"` 的累计 `total_token_usage` 做基线/终态差值（与 parser 内部 `_codex_token_delta` 同源），151 个快照全字段单调通过校验，再把归一化后的 usage 以 `full_session` schema 喂给 `scripts/normalize_run.py` 完成金额归一化（这是 normalize_run.py 支持的输入路径，对应 `metrics_schema: token-analysis-full-session`）。

## Token、耗时与调用

| 指标 | 值 |
|---|---:|
| Input | 19,617,273 |
| Cached input | 19,165,184（占 input **97.7%**） |
| Uncached input | 452,089 |
| Output | 57,210 |
| └ Reasoning output | 17,719（占 output **31.0%**） |
| Cache-write input | 未单列（provider 未提供，按规则取上界估算） |
| Total / all-in | **19,674,483** |
| Effective（uncached + output） | 509,299 |
| Main active（wall-clock） | 2,394 s（39.9 min，`15:29:00 → 16:08:57`） |
| 工具调用 | **147** |
| LLM 调用（reasoning blocks 代理） | **145** |
| patch_apply_end | **32**（全部集中在直接开发窗口） |

> 说明：cached input 占比 97.7% 是单 thread 长会话的典型特征——每次新 LLM 请求都把前面几乎完整的上下文作为缓存前缀复用，真正"新鲜"输入仅约 45 万 tokens。Output 极低（5.7 万）相对 1962 万输入，说明这是一个重读、重搜索、重改代码的任务，而不是大量生成新文本。

## 金额

### 价格快照

| 字段 | 值 |
|---|---|
| 币种 | USD |
| 模型 | gpt-5.6-sol（Standard，短上下文，未触发长上下文单价） |
| 查询日期 | 2026-07-27 |
| 官方来源 | https://developers.openai.com/api/docs/pricing |
| Uncached input / 1M | $5.00 |
| Cached input / 1M | $0.50 |
| Cache-write input / 1M | $6.25 |
| Output / 1M | $30.00 |
| Cache-write tokens | unknown（provider 未单列；按规则全部 uncached input 取 $6.25 上界） |

### 金额计算

provider 未单列 cache-write tokens，基础金额把全部 uncached input 按普通输入单价 $5.00 计算；cache-write 上界把全部 uncached input 按 $6.25 计算。

| 计费项 | Tokens | 单价 / 1M | 金额 |
|---|---:|---:|---:|
| Uncached input | 452,089 | $5.00 | $2.260 |
| Cached input | 19,165,184 | $0.50 | $9.583 |
| Cache-write input | unknown（上界 452,089） | $6.25 | unknown（上界 $2.826） |
| Output | 57,210 | $30.00 | $1.716 |
| **API 等价成本** | — | — | **$13.559** |
| Cache-write 上界 | — | — | $14.124 |
| 无缓存成本 | — | — | $99.803 |
| 缓存节省 | — | — | $86.243（86.41%） |

### 账单与套餐

| 字段 | 值 |
|---|---|
| Billing mode | unknown |
| 实际现金增量 | unknown |
| 套餐额度倍数 | unknown |
| 套餐额度等价金额 | unknown |
| 说明 | 会话来源是 Codex Desktop（VS Code 扩展），`turn_context` 含 `approval_policy: on-request`、`multi_agent_mode`、`sandbox_policy` 等，但 session_meta 未携带 token 级账单或套餐额度倍数，实际现金增量不可从遥测推导。仅给出按 OpenAI 公开 Standard 单价折算的 API 等价成本。 |

API 等价成本、实际现金增量、套餐额度等价金额分别陈列；后两项因无账单证据保留 `unknown`。

## Phase 分布

按 turn_context / task_complete / turn_aborted 锚点切分（非按 skill，因本次未走 skill）。

| 窗口 | Tokens | Share | Wall-clock | Tool calls | LLM 调用 | patch_apply | API 等价成本 |
|---|---:|---:|---:|---:|---:|---:|---:|
| W1 直接开发（L8→L710，turn1） | 19,217,074 | **97.7%** | 30.0 min | 145 | 141 | **32** | **$13.24** |
| W2 被纠偏后尝试 x-spec（L713→L735，turn2） | 457,409 | 2.3% | 0.7 min | 2 | 3 | 0 | $0.31 |
| W3 turn 被中断（L740→L749，turn3，aborted） | 0 | 0.0% | 0.3 min | 0 | 1 | 0 | $0.00 |
| **合计** | **19,674,483** | **100%** | **39.9 min** | **147** | **145** | **32** | **$13.56** |

> W1 的 API 等价成本按其 uncached/cached/output 占比折算（uncached≈439,001、cached≈18,722,560、output≈55,513）。

### 分布观察

1. **W1 独占 97.7%（19.22M / $13.24）**——这就是"不走流程、纯开发"的全部代价：fork 功能从调研证据读取、后端 `ThreadManager.fork_thread()` 实现、REST `POST /api/threads/{id}/fork`、前端入口，到 32 次 patch_apply，全部集中在一个 turn 内直冲到底。
2. **W2 仅 2.3%（0.46M / $0.31）却触发流程中断**——用户 L715 一句"你为什么直接开发了，还没走 x-spec 流程"后，agent 立即认错（"我错误选择了 x-qdev-gene，违反了应先 x-spec 固化契约的流程"），并停在 x-spec 的风险语料步骤请求输入。这一段 token 极少，但决定了后续走向。
3. **W3 = 0 token（被中断）**——用户回"跳过 rag"后，turn 在 L749 被 `turn_aborted` 主动中断，未产生 token_count 快照。这也正是 skill 官方 parser 拒绝本 session 的原因。
4. **缓存命中率 97.7%**——若无缓存，等价成本会从 $13.56 暴涨到 $99.80，缓存节省 $86.24（86.41%）。任何会进一步降低缓存复用的改动（频繁切 thread、插入大段不重复内容）都会显著抬高成本。

## 横向比较

| Run | Scope | Quality | Total tokens | Tools | patch_apply | API 等价成本 | 实际现金增量 | 套餐额度等价金额 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **Baseline（本次纯开发）** | full_pipeline | 流程违规（会话内判定） | 19,674,483 | 147 | 32 | $13.56 | unknown | unknown |
| Candidate | — | — | — | — | — | — | unknown | unknown |

本次为单 run baseline 调查，未生成 candidate。如需晋级判定，应在**同一 model / reasoning / scope / Token 口径**下跑一次 candidate（按 `skills/README.md` 完整走 x-spec→x-req→x-dev→x-verify→x-qa-gate→x-fix），产出 `comparison.json` 后由 `validate_comparison.py` 判定。

## 晋级门禁

不适用。本次任务范围是"调查一次不走流程、纯开发会话的 token 消耗"，作为 baseline 基线，不包含 candidate、隐藏 rubric、preflight 与 grader-only 隔离检查，因此不执行 7 项默认晋级门禁。

## 证据路径

- 原始 session：`~/.codex/sessions/2026/07/27/rollout-2026-07-27T23-28-55-019fa431-8211-7ee0-a222-c90ac0dd3cc6.jsonl`
- 归一化产物：`reports/spec-qa-token-analysis/runs/baseline-directdev-20260727/benchmark-run.json`（schema_version 2，由 `normalize_run.py` 生成，exit 0）
- 价格快照：`reports/spec-qa-token-analysis/runs/baseline-directdev-20260727/pricing.json`
- 输入 metrics：`reports/spec-qa-token-analysis/runs/baseline-directdev-20260727/metrics.json`（`token-analysis-full-session` schema）
- 元数据：`reports/spec-qa-token-analysis/runs/baseline-directdev-20260727/eval_metadata.json`
- Token 遥测来源：session 内 151 个 `event_msg.payload.type == "token_count"` 的累计 `total_token_usage`，全字段单调递增通过校验
- 价格来源：https://developers.openai.com/api/docs/pricing （gpt-5.6-sol Standard，查询日期 2026-07-27）
- `comparison.json` / `comparison.md`：未生成（本次为单 run baseline，无 candidate 可比较）

## 方法论备注

1. **窗口切分依据**：以 4 个 `turn_context`（L8/L351/L713/L740）和 2 个 `task_complete`（L710/L735）+ 1 个 `turn_aborted`（L749）为锚点。W1 = L8→L710（首段直接开发，正常完成）；W2 = L713→L735（被纠偏后尝试 x-spec，正常完成）；W3 = L740→L749（被用户中断，无 token 产出）。W1 与 W2 之间有 L712 `task_started`/L713 `turn_context` 自然分界；W2 与 W3 之间有 L737 `task_started`/L740 `turn_context` 分界。
2. **为什么用累计差而不是单次 `last_token_usage` 求和**：累计差法（窗口终点累计 − 窗口起点累计）能完整覆盖主会话的全部消耗，且天然处理 compaction（L349/L353 `context_compacted` 后累计计数器不重置，单调性保持）。直接对 `last` 求和会受 flush 时序影响。
3. **W3 token 为 0 的原因**：L747 的 token_count 快照值与 L734（W2 终点）完全相同（in=19,617,273 / tot=19,674,483），说明 L740 之后的 turn 在产生任何模型消耗前就被 `turn_aborted` 中断。
4. **provider 未单列 cache-write**：Codex token_count 的 `total_token_usage` 只有 5 个标准分桶，无 cache-write 字段。按 SKILL.md 规则，金额上界把全部 uncached input（452,089）按 $6.25 计算，得 $14.12；基础金额把全部 uncached input 按 $5.00 计算，得 $13.56。
