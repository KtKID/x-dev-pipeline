## ADDED Requirements

### Requirement: x-spec2 最小 run measurement

系统 SHALL 为每个 x-spec2 eval run 生成一个 `measurement.json`，必需字段为 `schema_version`、`eval_id`、`eval_name`、`configuration`、`run_number`、`source`、`model`、`repo_sha`、`prompt_sha256`、`started_at`、`ended_at`、`duration_ms`、`tokens` 与 `quality`。`configuration` SHALL 取 `with_skill|without_skill`；`source` SHALL 含 `kind/id`；`tokens` SHALL 含 `input/cached_input/output/reasoning_output/total`，其中 total 必须为非负整数、其余分桶在来源未提供时为 `null`；`quality` SHALL 含 `passed/total/pass_rate`。

#### Scenario: 合法 run 生成最小 measurement

- **GIVEN** 调用方已准备合法的单次 eval metadata、已结束的 Codex session 与 grading
- **WHEN** 调用方执行 extract
- **THEN** 工具生成包含全部必需字段且通过 schema 校验的 `measurement.json`

#### Scenario: 必需字段缺失

- **GIVEN** metadata、session 或 grading 缺少生成必需字段
- **WHEN** 调用方执行 extract
- **THEN** 工具不得生成成功 measurement，并以退出码 2 报告缺失字段

### Requirement: Codex 单 session token 与 duration 提取

系统 SHALL 只读取调用方显式指定的 Codex rollout JSONL，并以 `session_meta.payload.id` 作为规范 session ID，仅在该字段缺失时回退到 `payload.session_id`。有效样本 SHALL 只有一个规范 session ID、一个 `turn_context`、一个 `task_complete` 和至少一个位于完成事件之前且包含 `total_token_usage` 的 `token_count`；工具 SHALL 取 `task_complete` 之前最后一条累计 token 快照，直接映射 provider 的 input、cached input、output、reasoning output 与 total，并以唯一 `turn_context` 到唯一 `task_complete` 的时间差计算 `duration_ms`。

#### Scenario: 多条累计 token 快照

- **GIVEN** session 包含多条递增的累计 `token_count`
- **WHEN** 工具提取 token 分桶
- **THEN** 工具只使用最后一条累计快照且不逐条相加

#### Scenario: session 边界不满足

- **GIVEN** rollout 含多个 session ID、多个 `turn_context`、缺少或含多个 `task_complete`，或完成事件前缺少累计 token 快照
- **WHEN** 工具校验样本边界
- **THEN** 工具以退出码 1 报告样本边界无效且不写成功 measurement

#### Scenario: 粗粒度 duration

- **GIVEN** rollout 含唯一 turn 开始时间与更晚的唯一 `task_complete` 时间
- **WHEN** 工具计算 session duration
- **THEN** `started_at`、`ended_at` 和 `duration_ms` 可由原始时间戳重复计算得到相同结果

### Requirement: 子 agent 完成通知采集

系统 SHALL 接受主 agent 在子 agent 完成时保存的 `timing.json`。该文件 SHALL 含 `total_tokens`、`duration_ms` 和 agent ID；提取结果 SHALL 使用 `source.kind=subagent_notification`，把未由通知提供的 token 分桶与首末时间戳写为 `null`，不得伪造为零。

#### Scenario: 完成通知生成 measurement

- **GIVEN** 一个子 agent run 已完成且其通知被立即保存为合法 `timing.json`
- **WHEN** 调用方使用 `--timing` 执行 extract
- **THEN** measurement 保存真实 total token、duration 和 agent ID，并把未观测字段写为 `null`

#### Scenario: 通知字段缺失

- **GIVEN** `timing.json` 缺少 total token、duration 或 agent ID
- **WHEN** 调用方执行 extract
- **THEN** 工具以退出码 2 报告 schema 错误且不写成功 measurement

### Requirement: 运行身份与隐私边界

系统 SHALL 从 metadata 读取 eval 身份、prompt、model 与 repo SHA；rollout 模式 SHALL 用 session 事实交叉校验 model 与 repo SHA；系统 SHALL 把 prompt 保存为 SHA-256。`measurement.json` SHALL 不包含绝对 session 路径、prompt 正文、模型回复、工具输出或 transcript 内容。

#### Scenario: measurement 可关联且不复制内容

- **GIVEN** 一个 run 的 metadata 与 rollout 均合法
- **WHEN** 工具成功提取该 run
- **THEN** 结果可由 eval/run/session/repo/prompt hash 唯一关联，且内容字段与本机绝对 session 路径均未写入结果

### Requirement: 独立 grading 质量摘要

系统 SHALL 从独立 grader 的 `grading.json` 汇总断言 `passed`、`total` 与 `pass_rate`。被测生成 session 的输入 SHALL 只包含 eval prompt 与题目输入文件，不含 grading expectations；run metadata 或 transcript 显示 rubric 暴露时，该样本 SHALL 标记无效并退出 1。

#### Scenario: 客观断言汇总

- **GIVEN** grading 含可解析的逐项通过结果
- **WHEN** 工具生成 quality 摘要
- **THEN** measurement 的 quality 数量与 grading 逐项统计一致

#### Scenario: rubric 暴露

- **GIVEN** run 证据表明生成 agent 收到了 expectation 文本或读取了 grader-only rubric 文件
- **WHEN** 工具校验 grading 独立性
- **THEN** 该 run 不进入有效 benchmark，并报告 rubric exposure

### Requirement: x-spec2 paired benchmark 聚合

系统 SHALL 按 `(eval_id, run_number)` 聚合一条 `with_skill` 与一条 `without_skill` measurement。有效配对 SHALL 具有相同 `prompt_sha256`、`model`、`repo_sha` 与评分断言文本及顺序；每臂 measurement 的 quality SHALL 与同目录 `grading.json` 的逐项统计一致。聚合结果 SHALL 输出每种 configuration 的 quality pass rate、真实 total token、真实 duration、样本数及两臂 delta。

#### Scenario: 合法 paired run

- **GIVEN** 一个 eval/run 的两臂 measurement 齐全且可比字段一致
- **WHEN** 调用方执行 aggregate-spec2
- **THEN** `benchmark.json` 与 `benchmark.md` 输出两臂真实 quality/token/duration 和 delta

#### Scenario: 配对缺失或不可比

- **GIVEN** 任一臂缺失，prompt/model/repo 任一字段不一致，评分断言不一致，或 measurement 与 grading 统计不一致
- **WHEN** 调用方执行 aggregate-spec2
- **THEN** 聚合器以退出码 1 列出不可比原因且不把该 pair 计入有效样本

#### Scenario: 单样本 pilot

- **GIVEN** 每个 configuration 只有一个有效 run
- **WHEN** 聚合器生成 benchmark
- **THEN** benchmark 标记 `pilot: true` 与 `sample_size_per_configuration: 1`，并声明结果只验证测量链路

### Requirement: metrics CLI 确定性与兼容边界

系统 SHALL 提供 `extract` 与 `aggregate-spec2` 子命令；`extract` SHALL 要求 `--session` 与 `--timing` 恰好一个。命令使用退出码 0 表示成功、1 表示可读但无效的样本或配对、2 表示参数/IO/JSON/schema 错误。相同输入重复执行 SHALL 生成字节一致的派生产物，写文件 SHALL 使用同目录临时文件与原子替换。现有 x-spec2 产物、validator、`metrics.json` 和 iteration-1 benchmark SHALL 保持原样。

#### Scenario: 重复提取与聚合

- **GIVEN** extract 或 aggregate 的输入内容保持完全相同
- **WHEN** 连续执行两次相同命令
- **THEN** 两次退出码均为 0 且输出文件字节一致

#### Scenario: 历史评测产物兼容

- **GIVEN** iteration-1 的代理指标与现有 x-spec2 产物保持原位置和内容
- **WHEN** 新工具加入仓库并运行回归验证
- **THEN** iteration-1 的代理指标与现有 x-spec2 产物仍可读取，且 xdev validator 行为不变
