# xspec2-evaluation-metrics Design

## Context

### 当前仓库事实

- `skills/x-spec2/evals/evals.json` 已定义生成 case 与 round-trip case，`skills/x-spec2-workspace/iteration-1/` 已保存 with-skill / without-skill 产物、grading 和 benchmark。
- 当前 run 级 `metrics.json` 统计工具调用、步骤和输出字符；`benchmark.json` 的 `tokens` 实际承载 `output_chars`，`time_seconds` 固定为 0。
- Codex rollout JSONL 提供稳定的 `session_id`、turn 上下文、带时间戳的事件、累计 `token_count.info.total_token_usage` 和结束事件 `task_complete`。累计项包含 input、cached input、output、reasoning output 与 provider total。
- Codex 子 agent 完成通知直接提供 `total_tokens` 与 `duration_ms`；skill-creator 要求通知到达时立即保存为 run 级 `timing.json`，该值之后无法从父 session 可靠恢复。
- 已有 baseline 评审指出 rubric 暴露会降低 with-skill / without-skill 的区分度。执行输入与 grading expectations 需要分离。

### 约束

- 工具只使用 Python 标准库。
- 首版只衡量 x-spec2 生成 run；grader、人工等待和整条 pipeline 的资源消耗不进入本阶段样本。
- 每个被测 run 使用一个 fresh、单 turn、无人工交互的 Codex session。session 结束后由独立收尾动作读取，避免 session 自量缺少尾部 token 的悖论。
- 调用方显式传入 session 文件；工具不扫描目录猜归属。

## Goals / Non-Goals

**Goals：**

- 为一次 x-spec2 eval run 产出可复核的真实 total token、duration 与客观 grading 摘要；rollout 可用时补充可重算的 token 分桶与时间边界。
- 用一组同题 paired run 跑通 `extract → measurement.json → aggregate → benchmark`。
- 保持原始 provider token 分桶，避免缓存与 reasoning 字段被重复相加。
- 让无效样本以机器可判定方式失败，避免静默进入 benchmark。

**Non-Goals：**

- 人工等待、模型活跃、工具执行、队列等待与并行 critical path 拆分。
- Claude session adapter、父子 session 聚合、自动 session 扫描与全 pipeline stage 关联。
- token 金额换算、预算线、统计显著性与多 risk 档位比较。
- 修改 x-spec2 产物结构、validator 或语义 rubric。

## Decisions

### 1. 以 fresh 单-turn session 定义测量边界

每个 `with_skill` / `without_skill` run 使用独立 Codex session，session 只接收一次 eval prompt 并自主完成。`started_at` 取唯一 `turn_context` 的时间戳，`ended_at` 取唯一 `task_complete` 的时间戳，`duration_ms = ended_at - started_at`。

选择依据：单-turn session 让 session 边界等于生成 run 边界，首版无需推断同一对话中的 stage span，也自然排除人工确认等待。

备选方案：在长 session 中插入 stage start/end marker。该方案适合后续全 pipeline 观测，本 change 暂缓。

### 2. 收尾采集支持 rollout 与子 agent 通知两种明确来源

CLI 由调用方传入一个已结束的 rollout JSONL。提取器以 `session_meta.payload.id` 作为本次 rollout 的规范 ID，仅在 `id` 缺失时兼容回退到 `payload.session_id`；后者在子 agent rollout 中可能指向父 task。提取器要求全文件只有一个规范 session ID、一个 `turn_context` 和一个 `task_complete`，按时间排序选择 `task_complete` 之前最后一条含 `total_token_usage` 的 `token_count` 累计快照。`cached_input_tokens` 与 `reasoning_output_tokens` 保持 provider 原值；`total_tokens` 直接采用 provider total，不从各分桶重新求和。

子 agent 路径由主 agent 在完成通知到达时立即把 `total_tokens`、`duration_ms` 与 agent ID 保存到 `timing.json`，提取器读取该文件生成相同 schema。通知只提供 total 与 duration，因此 input/cache/output/reasoning 分桶和首末时间戳写 `null`；`source.kind` 标记为 `subagent_notification`，避免把字段缺失误解为零。

选择依据：Codex token 事件是累计快照，逐条相加会重复计数；显式路径消除 session 自动匹配歧义。

备选方案：扫描 `~/.codex/sessions` 按 cwd、时间和 prompt 猜测。该方案会在并发 eval 与恢复 session 下产生错配，进入后续阶段。

### 3. `measurement.json` 只保留最小可信字段

每个 run 的规范化产物为：

```json
{
  "schema_version": 1,
  "eval_id": 1,
  "eval_name": "stackchan-esp32s3-voice-link",
  "configuration": "with_skill",
  "run_number": 1,
  "source": {"kind": "subagent_notification", "id": "agent-..."},
  "model": "...",
  "repo_sha": "...",
  "prompt_sha256": "sha256:...",
  "started_at": null,
  "ended_at": null,
  "duration_ms": 12345,
  "tokens": {
    "input": null,
    "cached_input": null,
    "output": null,
    "reasoning_output": null,
    "total": 84852
  },
  "quality": {
    "passed": 0,
    "total": 12,
    "pass_rate": 0.0
  }
}
```

`eval_id/name/configuration/run_number/prompt/model/repo_sha` 来自 run 的 `eval_metadata.json`，rollout 模式用 session 内事实交叉校验 model/repo；`source/timing/tokens` 来自 rollout 或 `timing.json`；`quality` 来自独立 grader 的 `grading.json`。文件只保存 source ID 和 prompt hash，不复制绝对 session 路径、prompt 正文、模型回复或工具输出。

选择依据：这些字段覆盖身份、可比性、成本、时间和结果质量五个最低维度。工具调用等辅助数据继续留在现有 `metrics.json`。

备选方案：把所有 session 事件复制进 workspace。该方案扩大敏感数据面，也让派生指标与原始 transcript 混在一起。

### 4. 质量使用独立 grading 的客观断言

生成 run 只接收 prompt 与题目输入文件。grading expectations 由 grader 独立读取，生成 session 的输入清单与 transcript 不得包含 rubric 文件或 expectation 文本。`quality` 只汇总 grading 中的 `passed/total/pass_rate`；生成 agent 的自评不进入质量分。

选择依据：下游可复核断言比同一 agent 自评更稳定，也能暴露 baseline rubric 泄漏。

备选方案：让生成 agent 自报质量。该值缺少独立证据，首版不采纳。

### 5. 聚合只接受可比 paired runs

聚合器按 `(eval_id, run_number)` 查找一条 `with_skill` 与一条 `without_skill`。一对样本的 `prompt_sha256`、`model`、`repo_sha` 与评分断言文本及顺序必须一致，measurement 的 quality 还必须能由同目录 `grading.json` 重算；否则样本无效。输出沿用 `benchmark.json` / `benchmark.md`，其中 tokens 使用真实 provider total，time 使用真实 duration，quality 使用断言通过率。

首轮只跑现有 eval 1 的一对 run，并明确标记 `pilot: true`、`sample_size_per_configuration: 1`。该结果用于证明采集链路和数据契约成立，不用于宣称 x-spec2 的稳定增益。

选择依据：paired comparison 控制题目、模型和代码版本；pilot 标签防止把单样本差异扩张为总体结论。

### 6. CLI、退出码与幂等性

```text
python3 tools/metrics.py extract \
  (--session <codex-rollout.jsonl> | --timing <run-dir>/timing.json) \
  --metadata <run-dir>/eval_metadata.json \
  --grading <run-dir>/grading.json \
  --output <run-dir>/measurement.json

python3 tools/metrics.py aggregate-spec2 \
  <iteration-dir> [--json]
```

- exit 0：提取或聚合成功。
- exit 1：输入结构可读，但样本边界或 paired 可比性不成立。
- exit 2：参数、IO、JSON 或 schema 错误。
- `extract` 对相同输入重复执行生成字节一致的 JSON；写入使用同目录临时文件后原子替换。
- `aggregate-spec2` 只读取 `measurement.json` 与既有 grading/metadata，不修改 run 产物；重复执行生成相同 benchmark 内容。

## Risks / Trade-offs

- [风险] session 尾部仍在写入会得到不完整累计值。→ rollout 采集在被测 session 结束后执行；提取器要求唯一 `task_complete` 及其之前的最终 token 累计快照存在。子 agent 直接使用完成通知。
- [风险] `duration_ms` 包含 Codex runtime 调度与工具时间。→ 字段命名保持 session duration；细粒度时间明确进入后续阶段。
- [风险] 一次 paired run 的方差未知。→ benchmark 标记 pilot 和样本数，预算与趋势结论等待重复样本。
- [风险] rubric 经题目辅助文件泄漏。→ 执行输入清单与 grading 输入分离，收尾时审计 run metadata；发现泄漏的样本退出 1。
- [风险] 子 agent 通知缺少 token 分桶与首末时间戳。→ schema 用 `null` 表达未观测，真实 total 与 duration 保持可比较；完整分桶由 rollout 模式提供。
- [取舍] 首版只支持 Codex。→ 当前 x-spec2 benchmark 使用 GPT-5 Codex，可直接修复真实 token/time 缺口；provider adapter 后续扩展。

## Migration Plan

1. 保留现有 iteration-1 产物作为历史代理指标，不回写成真实 token。
2. 实现 extractor、schema 校验、paired aggregator 与 fixture 测试。
3. 更新 x-spec2 eval 运行说明，生成一次新的 pilot iteration。
4. 用两个 fresh 子 agent 运行 eval 1 的 with-skill / without-skill，通知到达时立即保存 timing；再由主 agent 收尾提取并聚合。
5. 验收后归档 change；回滚时删除新工具、测试和 pilot iteration，x-spec2 产物与 validator 保持原样。

## Open Questions

无。人工等待拆分、Claude adapter、全 pipeline stage 与预算线均已明确延后。
