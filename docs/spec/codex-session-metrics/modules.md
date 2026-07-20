# 模块设计

## 模块总览

| 模块 | 职责 | 依赖 | 边界类/对外契约 | 风险 | 决策回指 | 状态 | 回指 Requirement |
|---|---|---|---|---|---|---|---|
| Codex Session Source Parser | 把显式 Codex JSONL 转换为隔离后的 normalized source | 无 | `parse_codex_session_source(path, grader_only_inputs)` | 高：父会话前缀或多回合边界错误会污染 Token、耗时和隐私判断 | `D1`、`D2`、`D3`、`D4`、`D6` | 可进入 x-req | `Codex 活动 session 隔离`、`Codex session 多回合提取`、`Codex 增量 Token 提取`、`Codex 完整用量口径`、`Codex 多回合耗时`、`Codex 活动窗口隐私隔离` |
| Measurement Core | 把 provider parser 的 normalized source 与 metadata/grading 组装为稳定 measurement | Codex Session Source Parser 或未来其他 provider parser | `build_measurement(metadata, grading, source)` | 中：provider 假设渗入核心会阻塞 Claude 扩展 | `D5` | 可进入 x-req | `Provider 适配边界`、`Codex 完整用量口径`、`Codex 提取兼容性` |
| Metrics CLI Adapter | 校验 provider 输入选择，路由 Codex/timing source 并保持 CLI 兼容 | Codex Session Source Parser、Measurement Core | `metrics.main(argv)` | 中：参数别名或旧函数迁移可能破坏现有调用方 | `D5`、`D7` | 可进入 x-req | `Codex 专用命名`、`Provider 适配边界`、`Codex 提取兼容性` |

## 关键决策

| D-ID | 决策 | 依据 U/J | 选择理由 | 备选与否决原因 | 重评条件 |
|---|---|---|---|---|---|
| D1 | 以 Codex JSONL 第一条有效 `session_meta` 作为活动 session header，后续不同 session ID 的 metadata 作为 fork 继承内容 | `U2`、`J1` | 真实子 agent 文件首条 metadata 含自己的 ID、repo SHA 和 `source.subagent`，后续父 metadata 属于复制上下文 | 收集全文唯一 session ID：真实 fork 文件存在父子两个 ID，会误判有效样本 | Codex 日志格式提供显式 active-session 字段或事件级 session ID 时重评 |
| D2 | 将生命周期窗口与执行窗口分开：生命周期用于耗时，执行窗口用于 Token、模型和 rubric 泄漏 | `U3`、`U4`、`J2`、`J4`、`J8` | 用户耗时口径从派发到最后回复；Token 与隐私又必须排除派发后注入的父会话前缀 | 用单一窗口承担全部指标：要么漏掉派发等待，要么把继承前缀计入用量与泄漏 | Codex 提供原生 per-agent usage 和 dispatch/completion 字段时可简化窗口推导 |
| D3 | Token 使用活动执行前最后累计快照作为基线，并对最终累计快照逐分桶做差 | `U3`、`U5`、`J3` | 保留 provider 真实计数并排除父会话累计值，能够恢复本次真实子 agent 的 784,530 total | 直接取最终累计值：会把父会话 Token 计入；累加所有快照：累计值重复计算 | Codex 改为每事件增量计数或提供 session-local usage 时重评 |
| D4 | 多回合 session 接受多个 `turn_context/task_complete`；最后一个活动 turn 必须有后续完成事件，最终数据截止最后完成事件 | `U1`、`J5` | 子 agent 可能完成初稿后继续接收修复任务，完整用量必须覆盖所有回合 | 强制恰好一个 turn/complete：真实子 agent 被拒绝；把未完成末回合算入：结果缺少可靠终点 | Codex 引入统一 session-complete 事件时改用显式终点 |
| D5 | Provider parser 统一输出现有 normalized source，Measurement Core 不读取 Codex/Claude 原始事件 | `U6`、`J7` | 当前 measurement 组装已围绕 source contract 工作，独立 adapter 可让 Claude 后续平行接入 | 在 `build_measurement` 内按 provider 分支解析：核心与日志格式耦合，新增 provider 会扩大回归面 | normalized source 无法承载未来 provider 必需指标时版本化扩展契约 |
| D6 | grader-only 检查只扫描 Codex 活动执行窗口 | `J8` | fork 继承文本不代表当前子 agent 接触 rubric，活动窗口仍能拦截真实泄漏 | 扫描整个文件：产生父会话污染假阳性；完全关闭扫描：放过当前 agent 的真实泄漏 | Codex 事件提供输入来源标签时改用结构化 provenance 校验 |
| D7 | 新增 `--codex-session` 与 Codex 命名解析函数；保留 `--session` 和 `parse_rollout_source` 作为兼容委托入口 | `U7`、`J6`、`J9` | 新命名为未来 Claude 提供清晰空间，兼容委托保护现有测试和调用方 | 直接删除旧入口：破坏既有脚本；继续新增泛化名称：Codex 假设继续隐藏 | 仓库完成调用方迁移并发布破坏性版本时可移除旧别名 |

## 模块详情

### 模块：Codex Session Source Parser

**职责**：解析一个显式 Codex rollout JSONL，识别活动 session 与两个窗口，提取增量 Token、生命周期耗时、模型、repo SHA 和 source ID。

**包含范围**：JSONL/schema 校验、首 metadata 解析、fork 前缀隔离、多回合完成性、Token 基线/最终快照、assistant 最终回复、grader-only 活动窗口扫描。

**排除范围**：session 文件发现、Claude 格式、grading 计算、measurement 写盘与 paired 聚合。

**依赖**：Python 标准库；调用方提供路径和 grader-only 输入清单。

**边界类/对外契约**：`parse_codex_session_source(path, grader_only_inputs)`

**核心接口与数据**：

- 输入：Codex JSONL `Path` 与 grader-only 路径/标识字符串列表。
- 输出：normalized source，包含 `source.kind=codex_rollout`、活动 session ID、model、repo SHA、started/ended、duration_ms 和五类 Token 分桶。
- 拥有的数据：仅函数调用期间的行记录、活动 header、窗口边界与累计快照；不持久化 session 内容。

**风险与依据**：Codex fork 前缀与多回合事件没有逐行 session ID；窗口判断必须依赖首 header、时间与事件顺序，并用真实 fixture 固定当前格式（`J1`、`J2`、`J5`）。

**状态**：可进入 x-req

**决策回指**：`D1`、`D2`、`D3`、`D4`、`D6`

**回指 Requirement**：`Codex 活动 session 隔离`、`Codex session 多回合提取`、`Codex 增量 Token 提取`、`Codex 完整用量口径`、`Codex 多回合耗时`、`Codex 活动窗口隐私隔离`

### 模块：Measurement Core

**职责**：校验 metadata/grading 与 normalized source 的一致性，生成不含 prompt 正文和 transcript 内容的确定性 measurement。

**包含范围**：质量通过率、model/repo SHA 交叉校验、prompt hash、Token/duration/source 映射和 schema 稳定性。

**排除范围**：解析任何 provider 原始日志、发现 session、运行 grader 和判断文档语义。

**依赖**：任一 provider parser 或 timing adapter 产生的 normalized source。

**边界类/对外契约**：`build_measurement(metadata, grading, source)`

**核心接口与数据**：

- 输入：标准化 metadata、独立 grading 和 normalized source。
- 输出：`measurement.json` 对象与标准化 expectations。
- 拥有的数据：无长期数据；结果由 CLI 原子写入。

**风险与依据**：Codex 特有字段进入该模块会迫使未来 Claude 伪造 Codex 事件；保持 source contract 可复用（`J7`）。

**状态**：可进入 x-req

**决策回指**：`D5`

**回指 Requirement**：`Provider 适配边界`、`Codex 完整用量口径`、`Codex 提取兼容性`

### 模块：Metrics CLI Adapter

**职责**：暴露 provider 明确的 source 参数，校验互斥输入，调用对应 parser 和 Measurement Core，并保持旧命令兼容。

**包含范围**：`extract` 的 `--codex-session`、`--session` 兼容别名、`--timing` 路由、错误码和输出路径。

**排除范围**：Codex 事件解析细节、Claude parser 实现、grader 执行和 benchmark 算法修改。

**依赖**：Codex Session Source Parser、现有 timing parser、Measurement Core。

**边界类/对外契约**：`metrics.main(argv)`

**核心接口与数据**：

- 输入：CLI 参数、metadata、grading、显式 source 路径。
- 输出：`measurement.json` 或现有 0/1/2 退出码与错误说明。
- 拥有的数据：无；只协调单次调用。

**风险与依据**：argparse alias 必须确保 Codex session 与 timing 恰好选择一个；旧 `--session` 应解析到同一 Codex 路径字段（`J9`）。

**状态**：可进入 x-req

**决策回指**：`D5`、`D7`

**回指 Requirement**：`Codex 专用命名`、`Provider 适配边界`、`Codex 提取兼容性`
