> spec_version: 2

# Codex Session Metrics 提取

## 需求说明

### 需求本质

让 `tools/metrics.py` 能从真实 Codex session JSONL 中准确提取一个子 agent 跨多回合执行的增量 Token 与端到端耗时，同时隔离 fork 继承的父会话数据，并为未来 Claude session 提取保留清晰的 provider 边界。

### 系统目标

- 接受调用方显式指定的 Codex session JSONL，识别该文件所属的活动 Codex session。
- 支持活动 session 中存在多个 `turn_context`、多个 `task_complete` 和重复 `session_meta`。
- 从累计 Token 快照中扣除 fork 继承前缀的基线，输出仅属于活动 Codex session 的增量用量。
- 以任务发送并创建活动 Codex session 的时间到子 agent 最后一条 assistant 回复计算端到端耗时，覆盖生成、工具调用、校验、等待后续消息和返工全过程。
- 保持现有 `measurement.json` 的 Token 分桶、质量摘要和 paired benchmark 契约可用。
- 将 Codex 日志解析放入名称明确的 Codex 专用函数，为后续 Claude session 适配器保留独立入口。

### 范围边界

**包含**：

- `tools/metrics.py` 中 Codex session 身份、活动窗口、累计 Token 基线与最终快照的解析。
- Codex 多回合完成语义、模型和仓库 SHA 一致性校验、grader-only 输入泄漏扫描。
- CLI 的 Codex session 输入命名与现有调用方式兼容。
- `test/test_metrics.py` 中单回合、多回合、fork 前缀、计数器异常和隐私隔离回归测试。
- 使用本次真实子 agent session 作为验收样本。

**排除/延后**：

- Claude session 文件格式解析与 Claude 专用实现。
- 自动发现或扫描本机 Codex session 目录；调用方继续显式提供文件路径。
- LLM-as-a-Judge、grader 生成和文档语义评分规则。
- 改变 `measurement.json` 的质量字段或 paired benchmark 统计口径。
- 把 Markdown 文件字符数、词数或文件大小当作模型 Token 用量。

### 关键约束

- 所有新增的 Codex 专用函数名必须包含 `codex`（`U7`）。
- Provider 特有解析与 provider-neutral measurement 组装保持分离，Claude 后续通过独立适配器接入（`U6`、`J7`）。
- Token 使用 Codex/provider 记录的累计用量，推理 Token 保留独立分桶；总量直接采用累计 `total_tokens` 的增量，禁止按文档文本估算或重复相加分桶（`U3`、`U5`、`J3`）。
- 耗时是活动 Codex session 的生命周期墙钟时间，从任务派发到最后回复，包含多回合之间等待主 agent 反馈的时间（`U4`、`J4`）。
- fork 继承前缀不得污染 Token、耗时、模型、repo SHA 或 rubric 泄漏判断（`J1`、`J2`、`J8`）。
- 当前 `tools/metrics.py` 与 `test/test_metrics.py` 已有未提交修改；实现阶段必须先审查现有 diff，并在其基础上增量修改。

### 系统不变量

- 活动 Codex session ID 与 repo SHA 来自文件首个有效 `session_meta`；继承前缀中的父 session metadata 不得替换它。
- Codex 生命周期窗口从文件首个活动 `session_meta` 的时间开始，到活动执行段最后一条 assistant 回复结束；该窗口用于计算端到端耗时。
- Codex 执行窗口从首个活动 `turn_context` 开始，到其后最后一个 `task_complete` 结束；该窗口用于模型一致性、Token 快照和 grader-only 泄漏判断。
- 多个活动 `turn_context` 必须使用同一个模型；模型发生变化时样本进入无效状态，避免单条 measurement 混合模型。
- Token 增量等于最终累计快照减活动窗口开始前的最后累计基线；缺少基线时使用零基线；任一分桶出现负增量时样本无效。
- `reasoning_output_tokens` 代表 Codex/provider 报告的推理用量；`total_tokens` 使用 provider 总量增量，禁止再次叠加 reasoning 分桶。
- grader-only 泄漏检查只扫描活动窗口，继承的父会话文本不构成当前子 agent 的 rubric exposure。
- 单回合 Codex rollout 的既有 schema、Token、source、model 与 repo SHA 保持兼容；耗时统一采用本规格定义的派发到最后回复口径；相同输入重复提取仍产生字节一致的 measurement。
- `metrics.py` 继续只读取显式路径，不扫描 session 目录。

## 用户要求追溯

| U-ID | 用户原话要求 | 对应目标 | 落实位置 |
|---|---|---|---|
| U1 | “你修改脚本代码” | `Codex session 多回合提取` | `spec.md#requirement-codex-session-多回合提取` |
| U2 | “从 codex session 中拿数据” | `Codex 活动 session 隔离` | `spec.md#requirement-codex-活动-session-隔离` |
| U3 | “先告诉我 token 消耗” | `Codex 增量 Token 提取` | `spec.md#requirement-codex-增量-token-提取` |
| U4 | “先告诉我……耗时” | `Codex 多回合耗时` | `spec.md#requirement-codex-多回合耗时` |
| U5 | “token 包括子 agent 推理……不止是产出文档的 token” | `Codex 完整用量口径` | `spec.md#requirement-codex-完整用量口径` |
| U6 | “注意以后有 claude” | `Provider 适配边界` | `spec.md#requirement-provider-适配边界` |
| U7 | “现在新增函数命名都要带 codex” | `Codex 专用命名` | `spec.md#requirement-codex-专用命名` |

## 判断依据

| J-ID | 判断 | 来源类型 | 证据或推断说明 | 确认状态 |
|---|---|---|---|---|
| J1 | Codex rollout 的首个 `session_meta.payload.id` 是当前文件活动 session ID，后续不同 ID 的 metadata 属于 fork 继承前缀 | 仓库事实 | 本次子 agent 文件 `rollout-...019f802e....jsonl` 首个 metadata 为 `019f802e...` 且 `source.subagent` 存在，随后出现父 session `019f800c...` | 已确认 |
| J2 | 活动回合从文件头 metadata 之后首个真实 `turn_context` 开始；此前累计事件作为继承基线 | 仓库事实 | 本次文件在 `15:39:13.100Z` 保留父会话累计快照，活动子 agent 首个 `turn_context` 位于 `15:39:16.375Z` | 已确认 |
| J3 | fork session 的实际 Token 应按最终累计快照减活动开始前最后累计快照逐分桶计算 | 用户确认 | 当前 parser 直接取最终累计值会把父会话 1,575,780 Token 计入子任务；用户确认差分口径，活动 session 增量为 784,530 | 已确认 |
| J4 | 多回合 `duration_ms` 使用任务派发对应的首个活动 `session_meta` 到活动执行段最后一条 assistant 回复的时间差 | 用户确认 | 用户明确指定“以发送给子 agent 开始计时，到子 agent 最后回复为结束时间”；本次口径得到 466,265 ms | 已确认 |
| J5 | 活动窗口允许多个 `turn_context/task_complete`，只要求最后一个活动回合已完成 | 仓库事实 | 本次子 agent 初次生成与 P0 修复形成两个活动回合和两个完成事件 | 已确认 |
| J6 | 保留旧 `parse_rollout_source` 兼容入口，并把实现委托给新增 Codex 命名函数 | 暂定默认 | 现有测试和潜在调用方使用旧函数名；兼容委托可降低迁移风险 | 待确认 |
| J7 | Provider parser 输出统一 normalized source，`build_measurement` 继续保持 provider-neutral | 用户确认 | 当前 `build_measurement(metadata, grading, source)` 已天然消费标准化 source；用户确认 Codex/Claude 使用独立 parser | 已确认 |
| J8 | grader-only 文本扫描限定在活动窗口 | LLM 推断 | fork 前缀可能包含父会话读过的 rubric 路径，全文件扫描会把未接触 rubric 的子 agent 误判为泄漏 | 待确认 |
| J9 | CLI 新增规范参数 `--codex-session`，现有 `--session` 作为兼容别名 | 用户确认 | 用户确认显式 Codex 参数和现有兼容入口同时保留 | 已确认 |

## 建模覆盖声明

| 元组 | 落点或不适用理由 |
|---|---|
| 数据流 | `design.md#数据流` |
| 状态 | `design.md#状态流转` |
| 时序 | `design.md#时序` |
| 资源 | 不适用：提取器只流式/顺序读取调用方给定文件，不新增长期资源所有权；若实现引入缓存则重评 |
| 不变量 | `spec.md#系统不变量` |
| 故障 | `design.md#故障与恢复` |

## 验收

### Requirement: Codex 活动 session 隔离

系统 SHALL 以显式 Codex rollout 文件的首个有效 `session_meta` 确定活动 session 身份和 repo SHA，并隔离其携带的父会话 metadata 与历史事件。

依据：`U2`、`J1`、`J2`

#### Scenario: fork rollout 含父 session 前缀

- **GIVEN** 文件首个 metadata 是子 agent session，后续继承前缀包含不同父 session ID 和 repo SHA
- **WHEN** 提取 Codex source
- **THEN** source ID 与 repo SHA 使用首个子 agent metadata，父 metadata 不触发“多个 session ID”无效样本
- 验证: auto

### Requirement: Codex session 多回合提取

系统 SHALL 支持一个活动 Codex session 内的多个回合和完成事件，并以首个活动回合至最后完成事件形成一次完整 measurement。

依据：`U1`、`J5`

#### Scenario: 子 agent 生成后接受修复反馈

- **GIVEN** 活动 session 依次包含首次生成回合、完成事件、修复回合和最终完成事件
- **WHEN** 提取运行边界
- **THEN** 样本保持有效，最终 measurement 覆盖两个回合且 source ID 保持不变
- 验证: auto

#### Scenario: 最后回合未完成

- **GIVEN** 活动窗口最后一个 `turn_context` 之后不存在 `task_complete`
- **WHEN** 提取运行边界
- **THEN** 工具以无效样本退出且不写成功 measurement
- 验证: auto

### Requirement: Codex 增量 Token 提取

系统 SHALL 对 input、cached input、output、reasoning output 与 total 使用“最终累计快照减活动前基线”的增量，输出活动 Codex session 的真实用量。

依据：`U3`、`J3`

#### Scenario: 真实 fork 子 agent session

- **GIVEN** 活动前 total 基线为 1,575,780，最终累计 total 为 2,360,310
- **WHEN** 工具提取本次子 agent Token
- **THEN** `tokens.total` 为 784,530，input 为 765,666，cached input 为 704,256，output 为 18,864，reasoning output 为 3,906
- 验证: auto

#### Scenario: 无继承基线的独立 session

- **GIVEN** 首个活动回合前不存在累计 Token 快照
- **WHEN** 工具提取 Token
- **THEN** 使用零基线，结果等于完成前最后累计快照
- 验证: auto

#### Scenario: 累计计数器回退

- **GIVEN** 任一最终累计分桶小于对应基线
- **WHEN** 工具计算增量
- **THEN** 工具以无效样本报告 Codex Token 计数器重置或窗口错误
- 验证: auto

### Requirement: Codex 完整用量口径

系统 SHALL 保存 Codex/provider 报告的输入、缓存输入、可见输出、推理输出和总 Token 增量，使结果覆盖子 agent 全部模型调用而非文档文本大小。

依据：`U5`、`J3`

#### Scenario: 推理 Token 纳入 measurement

- **GIVEN** Codex 最终与基线快照的 `reasoning_output_tokens` 存在正增量
- **WHEN** 生成 measurement
- **THEN** `tokens.reasoning_output` 保存该增量，`tokens.total` 直接保存 provider total 增量且不再次叠加 reasoning 值
- 验证: auto

### Requirement: Codex 多回合耗时

系统 SHALL 使用任务派发对应的首个活动 `session_meta` 到活动执行段最后一条 assistant 回复的带时区时间戳计算端到端 `duration_ms`，同时保留最后 `task_complete` 作为完成性校验。

依据：`U4`、`J4`

#### Scenario: 真实两回合子 agent session

- **GIVEN** 活动 Codex session 创建于 `2026-07-20T15:39:13.099Z`，子 agent 最后一条 assistant 回复位于 `2026-07-20T15:46:59.364Z`
- **WHEN** 工具计算 session 耗时
- **THEN** `duration_ms` 为 466,265，并把上述派发/回复时间保存为 started/ended 时间戳
- 验证: auto

### Requirement: Provider 适配边界

系统 SHALL 让 Codex parser 只负责把 Codex JSONL 转换为 normalized source，由 provider-neutral measurement 组装逻辑消费；未来 Claude parser 可独立产生同一 normalized source。

依据：`U6`、`J7`

#### Scenario: 后续增加 Claude session parser

- **GIVEN** 后续实现提供 Claude session 到 normalized source 的转换
- **WHEN** 接入 measurement 组装
- **THEN** Codex parser 无需修改，quality 与 aggregate 逻辑继续复用
- 验证: manual

### Requirement: Codex 专用命名

系统 SHALL 让本次新增的 Codex 特有函数名全部包含 `codex`，并让兼容入口只承担委托职责。

依据：`U7`、`J6`、`J9`

#### Scenario: 检查新增函数命名

- **GIVEN** 本次代码 diff 中存在新增 session 解析函数
- **WHEN** 检查其定义和调用关系
- **THEN** 所有 Codex 专用新增函数名均包含 `codex`，provider-neutral 函数不含伪装的 Codex 格式假设
- 验证: auto

### Requirement: Codex 活动窗口隐私隔离

系统 SHALL 仅在活动 Codex session 窗口内检查 grader-only 输入泄漏，避免继承父会话内容污染当前样本，同时继续拦截当前子 agent 实际读取 rubric 的情况。

依据：`J8`

#### Scenario: rubric 路径只存在于继承前缀

- **GIVEN** 父会话前缀包含 grader-only 路径，活动窗口未包含该路径
- **WHEN** 校验 rubric exposure
- **THEN** 当前子 agent 样本保持有效
- 验证: auto

#### Scenario: 活动窗口读取 rubric

- **GIVEN** grader-only 路径出现在活动窗口文本中
- **WHEN** 校验 rubric exposure
- **THEN** 当前样本以退出码 1 标记为无效
- 验证: auto

### Requirement: Codex 提取兼容性

系统 SHALL 保持既有单回合 rollout、`measurement.json` schema、质量统计、paired aggregate 和确定性写入行为。

依据：`J6`、`J9`

#### Scenario: 既有单回合 fixture

- **GIVEN** 单 session、单 turn、单 assistant 回复和单 task-complete rollout
- **WHEN** 经兼容入口或 Codex 规范入口提取
- **THEN** Token、source、model、repo SHA 与修改前结果一致，耗时按 session metadata 到 assistant 回复的新口径计算
- 验证: auto

#### Scenario: 回归测试集

- **GIVEN** 完成代码实现与新增 Codex fixtures
- **WHEN** 运行 `python3 -m unittest test.test_metrics -v`
- **THEN** 全部 metrics 测试通过
- 验证: auto
