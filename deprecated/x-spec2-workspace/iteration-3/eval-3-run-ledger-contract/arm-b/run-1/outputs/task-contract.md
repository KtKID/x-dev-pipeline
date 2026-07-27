# 运行账本与版本绑定：开发任务契约

> contract_version: 1
> source_spec_version: 2
> task_slug: pipeline-run-observability
> verification: auto

## 1. 任务目标

实现统一运行账本，使每次生产、评测、修复与回放执行均获得唯一 `pipeline_run_id`，并永久绑定创建时生效的 pipeline 版本清单。账本以追加事件保存任务快照、阶段事实、输入输出指纹、真实 Token、耗时、命令结果、证据与终态；派生投影视图可从原始事件完整重建。

本任务交付后，调用方能够凭一个 `pipeline_run_id` 回答以下问题：

1. 本次执行属于哪个任务、运行类型和关联运行。
2. 本次执行实际使用哪个 pipeline、skill、template、validator、路由策略、模型与代码 SHA。
3. 各阶段按逻辑顺序发生了什么，当前状态、最后成功阶段和终止原因是什么。
4. 各阶段消耗了多少 Token 和时间，缺失指标的原因是什么。
5. 每项输入、输出、命令结果和证据的内容指纹与定位信息是什么。
6. 重复请求、乱序事件、进程崩溃、账本短暂不可用和发布版本切换如何收敛到确定结果。

### 需求追溯

| 本任务能力 | 上游 Requirement / Scenario |
|---|---|
| 唯一运行身份与完整查询 | `版本绑定与运行观测 / 完整生产任务形成运行记录` |
| 中断收敛与缺失原因 | `版本绑定与运行观测 / 阶段执行中断` |
| 生产版本唯一绑定 | 系统不变量“每个生产任务都能定位到唯一已发布 pipeline 版本…” |
| 原始事实追加与修订 | 系统不变量“原始输入指纹、阶段事实、Token、耗时、命令结果和 grader 原始断言结果保持不可变…” |
| 四类运行统一身份 | 系统不变量“每次生产、评测、修复和回放执行都拥有唯一 pipeline_run_id” |
| 可比性所需运行上下文 | `可比配对回放 / 当前版与候选版条件一致`、`配对输入不可比` |
| 生产与进化成本分桶 | `正确交付的 Token 效率 / 独立 grader 和 collector 产生评测成本` |

## 2. 范围

### 2.1 包含

- `pipeline_run_id`、调用幂等键、运行关联关系与阶段 attempt 身份。
- 已发布 pipeline 版本清单、活动版本指针和创建时原子绑定。
- 追加式运行事件、事件去重、因果关系、来源序号与内容指纹。
- run、stage attempt、指标完整性和账本完整性的派生状态机。
- 输入、输出、命令、Token、耗时、证据和缺失原因的事实契约。
- 重复请求、并发创建、乱序到达、重复投递、过期 worker、进程中断和账本写入失败的恢复协议。
- 单 run 查询、事件查询、版本绑定查询和确定性投影重建能力。
- 自动化契约测试、故障注入测试和可复跑证据包。

### 2.2 范围外

- 失败/扣分知识库、根因分类与知识聚类。
- 候选生成、grader 评分算法、晋级阈值、canary 决策和回滚执行器。
- 风险路由算法、影子 QA 抽样策略和 UI 控制台。
- Token 金额换算与非 Codex provider 的采集实现。
- pipeline skill、template 或 validator 内容的自动改写。

这些后续模块只消费本任务提供的稳定运行事实与版本绑定。

## 3. 显式假设

1. 首版运行账本部署为单一逻辑数据存储，支持事务、唯一约束和 compare-and-swap；多个进程可以并发写入。
2. 已发布版本拥有不可变 `VersionManifest`；生产活动版本通过独立的 `ActiveVersionPointer` 指向某个已发布 manifest。
3. 所有创建调用都提供调用方作用域内唯一的 `idempotency_key`。幂等映射与运行事实采用相同保留期，首版保持永久可查询。
4. `pipeline_run_id`、`stage_attempt_id` 和 `event_id` 使用服务端可生成、全局唯一且不可复用的 UUIDv7；存储层唯一约束处理极低概率碰撞。
5. 所有持久化时间使用 UTC；时钟只用于展示和超时判断。事件逻辑顺序由来源序号与因果依赖决定。
6. 每个已发布 manifest 声明阶段图、必需阶段、阶段顺序和组件版本，因此投影器无需从到达时间猜测流程。
7. 同一次非终态执行的进程恢复沿用原 `pipeline_run_id`，并创建新的 `stage_attempt_id`。终态后的再次执行创建新 `pipeline_run_id`，通过 `parent_run_id` 与 `relation_type` 关联。
8. 修复运行默认继承根生产 run 的版本绑定。显式版本迁移创建新的关联 run，并记录 `migration_reason` 与目标版本；原 run 绑定保持稳定。
9. 仓库测试环境提供 Python 3 与 pytest。现有测试入口存在差异时，开发 agent 保留本文测试 ID 和断言，映射到仓库统一测试命令，并在证据清单记录映射。
10. 运行账本保存元数据和内容指纹；大型产物与日志保存在既有证据存储中，通过不可变定位符和 SHA-256 关联。

## 4. 术语与身份语义

### 4.1 重复请求、恢复和重新执行

| 情况 | 身份结果 | 约束 |
|---|---|---|
| 相同作用域、相同 `idempotency_key`、相同请求指纹 | 返回原 `pipeline_run_id` | 返回内容与首次成功创建一致 |
| 相同作用域、相同 `idempotency_key`、不同请求指纹 | `IDEMPOTENCY_CONFLICT` | 不创建 run，不解析新的活动版本 |
| 创建并发竞争 | 唯一约束产生一个 run | 竞争方读取并返回获胜记录 |
| 非终态 run 的 worker 崩溃后恢复 | 沿用 run，创建下一 `stage_attempt_id` | attempt 编号单调递增 |
| 已终态 run 重新执行 | 创建新 run | 通过 `parent_run_id` 关联，保留各自版本绑定 |
| repair / replay / evaluation | 每次执行创建唯一 run | `run_kind` 和关系字段表达用途 |

请求指纹采用规范化 JSON 的 SHA-256，覆盖 `run_kind`、任务快照指纹、显式运行约束、关联 run、权限摘要、预算摘要、模型选择和调用方作用域；排除 `idempotency_key`、服务端时间与生产活动版本解析结果。生产重试即使跨越版本发布，也会先命中原幂等映射并返回原绑定。

### 4.2 运行类型

`run_kind` 只能取：

- `production`
- `evaluation`
- `repair`
- `replay`

`relation_type` 只能取：

- `root`
- `repairs`
- `replays`
- `paired_baseline`
- `paired_candidate`
- `reexecutes`
- `migrates_version`

根 run 使用 `relation_type=root` 且 `parent_run_id=null`；其余关系必须引用已存在 run。关系引用用于追溯，不共享或覆盖运行事实。

## 5. 数据契约

所有枚举均按值持久化。未知枚举值由读取方以 `UNKNOWN` 展示并保留原值，保证前向兼容；写入方必须通过当前 schema 校验。

### 5.1 `VersionManifest`：不可变发布清单

| 字段 | 类型 | 必填 | 约束 |
|---|---|---:|---|
| `pipeline_version_id` | string | 是 | 全局唯一、不可复用 |
| `manifest_schema_version` | integer | 是 | 正整数 |
| `manifest_digest` | string | 是 | 规范化完整 manifest 的 `sha256:<hex>`；唯一 |
| `pipeline_version` | string | 是 | 人类可读版本 |
| `code_sha` | string | 是 | 完整仓库 commit SHA |
| `skill_versions` | map<string,string> | 是 | 包含本次阶段图引用的全部 skill |
| `template_versions` | map<string,string> | 是 | 包含实际可用模板 |
| `validator_versions` | map<string,string> | 是 | 包含实际校验器及规则版本 |
| `routing_policy_version` | string | 是 | 可定位策略版本 |
| `stage_graph` | object | 是 | 稳定 stage ID、依赖、必需性和顺序 |
| `published_at` | timestamp UTC | 是 | 发布事实时间 |
| `published_by` | string | 是 | 发布主体 |

manifest 发布后禁止原地更新或删除。撤销、替代和生命周期变化使用独立追加记录；`manifest_digest` 始终代表最初发布内容。

### 5.2 `ActiveVersionPointer`：生产活动指针

| 字段 | 类型 | 必填 | 约束 |
|---|---|---:|---|
| `environment` | string | 是 | 首版至少支持 `production`；唯一键组成部分 |
| `pipeline_version_id` | string | 是 | 外键指向已发布 manifest |
| `pointer_revision` | integer | 是 | 每次切换原子递增 |
| `activated_at` | timestamp UTC | 是 | 切换时间 |
| `decision_ref` | string | 是 | 可定位发布决策 |

活动指针允许更新。run 保存创建事务内解析出的 manifest 完整绑定，后续指针切换只影响新幂等请求。

### 5.3 `RunRequestDedup`：创建幂等映射

| 字段 | 类型 | 必填 | 约束 |
|---|---|---:|---|
| `caller_scope` | string | 是 | 与 `run_kind`、`idempotency_key` 组成唯一键 |
| `run_kind` | enum | 是 | 见 4.2 |
| `idempotency_key` | string | 是 | 非空，调用方生成 |
| `request_fingerprint` | string | 是 | `sha256:<hex>` |
| `pipeline_run_id` | UUIDv7 | 是 | 外键，创建后不可改变 |
| `created_at` | timestamp UTC | 是 | 首次提交时间 |

唯一约束：`UNIQUE(caller_scope, run_kind, idempotency_key)`。

### 5.4 `PipelineRun`：不可变身份与绑定快照

| 字段 | 类型 | 必填 | 约束 |
|---|---|---:|---|
| `pipeline_run_id` | UUIDv7 | 是 | 主键 |
| `run_kind` | enum | 是 | 见 4.2 |
| `task_id` | string | 是 | 稳定任务标识 |
| `task_snapshot_digest` | string | 是 | 规范化任务输入 SHA-256 |
| `parent_run_id` | UUIDv7/null | 是 | 与关系类型一致 |
| `relation_type` | enum | 是 | 见 4.2 |
| `pipeline_version_id` | string | 是 | 指向创建时 manifest |
| `version_binding` | object | 是 | manifest 中全部版本字段的规范化快照 |
| `binding_digest` | string | 是 | `version_binding` SHA-256 |
| `model_binding` | object | 是 | provider、模型 ID、可定位版本/快照、参数摘要 |
| `repo_sha` | string | 是 | 实际执行代码快照；生产默认等于 manifest `code_sha` |
| `permission_digest` | string | 是 | 工具权限规范化摘要 |
| `budget_digest` | string | 是 | Token/时间/调用预算摘要 |
| `created_at` | timestamp UTC | 是 | 注册时间 |
| `created_by` | string | 是 | 调用主体 |

生产 run 的 `pipeline_version_id` 必须来自创建事务读取的 production 活动指针。evaluation/replay 可以显式选择已发布或隔离候选 manifest；显式选择值进入请求指纹。所有 stage 执行上下文只能从该 run 的 `version_binding` 构造。

### 5.5 `RunEvent`：追加式原始事实

| 字段 | 类型 | 必填 | 约束 |
|---|---|---:|---|
| `event_id` | UUIDv7 | 是 | 全局唯一 |
| `pipeline_run_id` | UUIDv7 | 是 | 外键 |
| `stage_id` | string/null | 是 | stage 事件必须匹配绑定 manifest 的阶段图 |
| `stage_attempt_id` | UUIDv7/null | 是 | stage 事件必填 |
| `attempt_no` | integer/null | 是 | 同一 run/stage 从 1 递增 |
| `source_id` | string | 是 | 发出事件的 worker/collector/reconciler |
| `source_seq` | integer | 是 | 同一 run + attempt + source 从 1 连续递增 |
| `event_type` | enum | 是 | 见 6.1 |
| `occurred_at` | timestamp UTC | 是 | 事实发生时间 |
| `recorded_at` | timestamp UTC | 是 | 账本接收时间 |
| `predecessor_event_ids` | list<UUIDv7> | 是 | 因果前驱，可为空 |
| `binding_digest` | string | 是 | 必须等于 run 绑定摘要 |
| `payload_schema_version` | integer | 是 | 正整数 |
| `payload` | object | 是 | 由事件类型校验 |
| `payload_digest` | string | 是 | 规范化 payload SHA-256 |
| `supersedes_event_id` | UUIDv7/null | 是 | 修订事件指向旧事实 |
| `correction_reason` | string/null | 是 | 修订事件必填 |

唯一约束：

- `UNIQUE(event_id)`
- `UNIQUE(pipeline_run_id, stage_attempt_id, source_id, source_seq)`
- stage attempt 分配记录满足 `UNIQUE(pipeline_run_id, stage_id, attempt_no)`

同 `event_id` 或同来源序号的重复投递具有相同 `payload_digest` 时返回原接收确认；摘要不同则返回 `EVENT_IDEMPOTENCY_CONFLICT`，原记录保持稳定。账本禁止对 `RunEvent` 执行 update/delete。事实更正通过更高序号的修订事件表达。

### 5.6 标准事件 payload

| 事件族 | payload 必填字段 |
|---|---|
| `RUN_REGISTERED` | `request_fingerprint`, `binding_digest` |
| `STAGE_ATTEMPT_STARTED` | `lease_id`, `worker_id`, `input_refs`, `input_digests` |
| `COMMAND_RECORDED` | `command_id`, `argv_digest`, `cwd_ref`, `exit_code`, `stdout_ref`, `stderr_ref`, `duration_ms`；执行未完成时允许 `exit_code=null` 并提供 `missing_reason` |
| `INPUT_CAPTURED` / `OUTPUT_CAPTURED` | `artifact_type`, `locator`, `digest`, `media_type`, `size_bytes` |
| `TOKEN_RECORDED` | `provider`, `model`, `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_tokens`, `total_tokens`, `cost_bucket`, `measurement_kind` |
| `EVIDENCE_ATTACHED` | `evidence_id`, `locator`, `digest`, `evidence_type`, `producer_event_id` |
| stage 终态事件 | `result_digest`, `reason_code`, `last_checkpoint_ref`, `missing_metrics` |
| `STAGE_ATTEMPT_SUPERSEDED` | `superseded_attempt_id`, `successor_attempt_id`, `reason_code` |
| run 终态事件 | `effective_attempts`, `required_terminal_event_ids`, `final_output_digests`, `gate_result`, `reason_code`, `last_successful_stage`, `missing_metrics` |
| `OUTCOME_REVISED` | `prior_terminal_event_id`, `effective_outcome`, `reason`, `evidence_refs`, `approved_by` |

`missing_metrics` 是对象数组，每项包含 `metric_name`、`missing_reason_code`、`detail`。允许的首版原因至少包含：`PROCESS_EXITED`、`USER_INTERRUPTED`、`TOOL_ERROR`、`LEDGER_UNAVAILABLE`、`PROVIDER_DID_NOT_REPORT`、`RESULT_UNCERTAIN_AFTER_CRASH`。

### 5.7 `RunProjection`：可重建派生视图

| 字段 | 类型 | 说明 |
|---|---|---|
| `pipeline_run_id` | UUIDv7 | 主键 |
| `execution_state` | enum | 见 6.2 |
| `effective_outcome` | enum/null | 原终态或最新有效修订结论 |
| `current_stage_id` | string/null | 当前权威 attempt 所在阶段 |
| `last_successful_stage` | string/null | 按绑定阶段图计算 |
| `authoritative_attempts` | map<stage_id,attempt_id> | 排除已 supersede attempt |
| `stage_states` | object | 各 stage/attempt 状态与摘要 |
| `metric_totals` | object | 原始分桶与按 stage、cost bucket 聚合 |
| `integrity_state` | enum | `COMPLETE`, `WAITING_FOR_GAP`, `INCONSISTENT` |
| `pending_event_ids` | list | 缺前驱或来源序号间隙的事件 |
| `projection_revision` | integer | 每次成功应用事件递增 |
| `last_applied_event_ids` | object | 各来源最高连续序号 |
| `projection_digest` | string | 规范化投影 SHA-256 |

投影属于缓存，可删除后从 `PipelineRun`、manifest 和全部 `RunEvent` 确定性重建。业务消费者读取投影视图，同时可展开原始事实和待处理事件。

### 5.8 `LedgerIngestRejection`：追加式拒绝审计

任何 `binding_digest`、stage ID、schema、序号或 payload 冲突均进入独立追加审计，至少保存 `rejection_id`、`pipeline_run_id`、`request_digest`、`event_id`、`reason_code`、`received_at` 与调用主体。拒绝记录不能推进 run 或 stage 状态。

## 6. 状态与时序契约

### 6.1 事件类型

首版事件类型固定为：

- `RUN_REGISTERED`
- `STAGE_ATTEMPT_STARTED`
- `INPUT_CAPTURED`
- `COMMAND_RECORDED`
- `TOKEN_RECORDED`
- `OUTPUT_CAPTURED`
- `EVIDENCE_ATTACHED`
- `STAGE_ATTEMPT_SUCCEEDED`
- `STAGE_ATTEMPT_FAILED`
- `STAGE_ATTEMPT_INTERRUPTED`
- `STAGE_ATTEMPT_SUPERSEDED`
- `RUN_SUCCEEDED`
- `RUN_FAILED`
- `RUN_INTERRUPTED`
- `RUN_CANCELLED`
- `OUTCOME_REVISED`

### 6.2 状态机

Run `execution_state`：

```text
REGISTERED -> RUNNING -> SUCCEEDED
                      -> FAILED
                      -> INTERRUPTED
                      -> CANCELLED
REGISTERED ----------> INTERRUPTED
REGISTERED ----------> CANCELLED
```

Stage attempt state：

```text
ALLOCATED -> RUNNING -> SUCCEEDED
                     -> FAILED
                     -> INTERRUPTED
                     -> SUPERSEDED
```

执行终态具有吸收性。后续事实修正追加 `OUTCOME_REVISED`，更新 `effective_outcome` 与投影修订号，并保留原 `execution_state` 和原终态事件。

run 进入 `SUCCEEDED` 的条件：绑定 manifest 声明的必需阶段均存在权威成功 attempt；所需门禁为通过；终态事件列出的依赖事件均已应用；版本摘要一致；指标存在或逐项记录缺失原因。任一条件尚未满足时，提前到达的终态事件保存在原始账本并保持 `WAITING_FOR_GAP`。

### 6.3 乱序、重复和并发时序

1. 接收层先校验身份、schema、binding 和幂等冲突，再追加原始事件。
2. 投影器按每个 source 的连续 `source_seq` 与 `predecessor_event_ids` 应用事件；`occurred_at` 只用于展示和超时判断。
3. 后继事件先到达时进入 `pending_event_ids`，投影状态为 `WAITING_FOR_GAP`。前驱到达后自动重放，无需改写后继事件。
4. 永久序号缺口达到恢复阈值后，reconciler 追加 `STAGE_ATTEMPT_INTERRUPTED` 或 `RUN_INTERRUPTED`，填写最后成功阶段和缺失原因；缺口事件仍保持可查询。
5. 同一 stage 同时只存在一个有效 lease。lease 过期后，reconciler 原子分配下一 attempt，并追加 `STAGE_ATTEMPT_SUPERSEDED`。
6. 已 supersede worker 的晚到事件作为原始事实保存，投影标记为非权威；它们不能覆盖 successor attempt 或推进 run 终态。
7. 两个 worker 同时完成同一 attempt 时，完全相同事件被去重；不同结果触发 `EVENT_IDEMPOTENCY_CONFLICT` 与 `INCONSISTENT`，run 不能成功收敛。

### 6.4 创建与版本绑定时序

`CreateRun` 必须在一个事务中执行：

1. 规范化请求并计算 `request_fingerprint`。
2. 先查询幂等唯一键；相同指纹返回原 run，不再读取活动版本。
3. 不同指纹返回 `IDEMPOTENCY_CONFLICT`。
4. 新请求读取目标环境的 `ActiveVersionPointer` 与对应完整 manifest。
5. 校验 manifest 已发布、digest 正确、stage graph 完整；生产 `repo_sha` 与 manifest `code_sha` 一致。
6. 插入 `PipelineRun`、`RunRequestDedup`、`RUN_REGISTERED` 和初始投影。
7. 提交后才向 orchestrator 返回可执行上下文。

事务提交失败时调用方使用原幂等键重试。版本指针在步骤 4 之后发生切换时，本 run 继续使用事务读到并持久化的旧绑定；新幂等请求使用新绑定。

### 6.5 阶段执行与持久化屏障

每个 stage attempt 按以下协议执行：

1. 原子获取 lease 和 attempt 编号。
2. 将 `STAGE_ATTEMPT_STARTED` 写入本地持久 outbox，并等待账本确认。
3. 从 run 的 `version_binding` 构造执行上下文，再启动 stage。
4. 命令、Token、输出和证据事件先写入 outbox，再确认对应工作完成。
5. 终态事件写入 outbox并等待账本确认后，orchestrator 才推进下一 stage。
6. outbox 使用固定 `event_id`、`source_seq` 和 payload 摘要重放，账本按幂等规则收敛。

账本在 stage 开始前不可用时，执行保持等待且不产生未登记副作用。执行完成后、账本确认前不可用时，outbox 重放已持久化结果。进程在外部动作完成与结果落入 outbox 之间崩溃时，reconciler 追加 `RESULT_UNCERTAIN_AFTER_CRASH` 中断事实；恢复使用新 attempt，并由 stage 自身幂等策略或人工处置决定是否重做。

## 7. 状态所有者

| 状态/数据 | 唯一所有者 | 允许动作 | 消费者边界 |
|---|---|---|---|
| 已发布 manifest 与活动指针 | Version Registry / Publisher | 发布不可变 manifest；原子切换指针 | Run Registrar 只读解析 |
| `pipeline_run_id`、幂等映射、绑定快照 | Run Registrar | 事务创建与返回既有 run | orchestrator 无权指定或覆盖绑定 |
| stage lease、attempt 编号、执行推进 | Pipeline Orchestrator | CAS 获取/续租/释放；按绑定阶段图推进 | worker 只执行获授权 attempt |
| 原始 `RunEvent` 与拒绝审计 | Ledger Store | 校验、追加、去重 | 任何组件均无 update/delete 权限 |
| stage/run 派生状态与指标聚合 | Run Projector | 按事件和 manifest 确定性计算 | 查询端只读；重建结果必须同 digest |
| Token/provider 原始计数 | Metrics Collector / stage adapter | 追加 `TOKEN_RECORDED` 或缺失原因 | Projector 负责分桶汇总 |
| 证据内容 | 既有 Evidence Store | 保存不可变内容并返回 locator + digest | Ledger 只保存引用与校验摘要 |
| lease 过期、序号缺口和终态收敛 | Recovery Reconciler | 追加 interrupt/supersede 事件，重放 outbox | 禁止改写历史事件 |
| `effective_outcome` 修订 | 经授权的审计/修订入口 | 追加 `OUTCOME_REVISED` 与证据 | 原执行终态保持可见 |

## 8. 对外接口契约

接口可落为 Python API、CLI 或服务端 endpoint；字段与错误语义保持一致。

### 8.1 `create_run(request)`

输入至少包含：`caller_scope`、`idempotency_key`、`run_kind`、`task_id`、`task_snapshot_digest`、关系字段、model、repo、permission、budget 摘要；evaluation/replay 可附显式版本。

输出：`pipeline_run_id`、`created`、完整 `version_binding`、`binding_digest`、`execution_state=REGISTERED`。

错误码至少包含：`IDEMPOTENCY_CONFLICT`、`NO_ACTIVE_PUBLISHED_VERSION`、`INVALID_VERSION_MANIFEST`、`INVALID_RUN_RELATION`。

### 8.2 `append_event(event)`

输出：`accepted`、`deduplicated`、`event_id`、`projection_revision`、`integrity_state`。

错误码至少包含：`RUN_NOT_FOUND`、`VERSION_BINDING_MISMATCH`、`UNKNOWN_STAGE`、`INVALID_EVENT_SCHEMA`、`EVENT_IDEMPOTENCY_CONFLICT`、`INVALID_ATTEMPT`。

### 8.3 `get_run(pipeline_run_id, include_events=true)`

输出必须包含：身份与关系、完整版本绑定、模型/repo/权限/预算摘要、run 投影、各 stage/attempt、最后成功阶段、原始指标分桶、证据引用、终态/修订、pending 事件和 ingest rejection 摘要。事件同时提供逻辑顺序和接收顺序。

### 8.4 `rebuild_projection(pipeline_run_id)`

从不可变事实重建临时投影，返回旧/新 `projection_digest`、事件计数、pending 列表和差异。无事实变化时两个 digest 必须相同；正式替换缓存使用原子 compare-and-swap。

## 9. 实现 checklist

- [ ] C01 定义并迁移 `VersionManifest`、`ActiveVersionPointer`、`RunRequestDedup`、`PipelineRun`、`RunEvent`、投影缓存、lease/outbox 元数据与 ingest rejection 存储；落实外键、唯一约束和原始事件 update/delete 防护。
- [ ] C02 实现规范化 JSON 与 SHA-256 公共函数；固定字段排序、UTF-8、数值和空值编码，并添加跨进程稳定性 golden test。
- [ ] C03 实现 manifest 发布校验、digest 校验、活动指针 CAS 切换和历史 manifest 查询。
- [ ] C04 实现 `create_run` 原子事务，覆盖幂等命中、指纹冲突、并发竞争、版本指针并发切换和事务失败重试。
- [ ] C05 实现运行关系校验；repair 默认继承根生产绑定，replay/evaluation 保存显式绑定，版本迁移生成新关联 run。
- [ ] C06 实现 stage lease 与单调 attempt 编号；覆盖 lease 续租、过期、supersede 和旧 worker 晚到事件。
- [ ] C07 实现 `append_event` 的 schema、binding、阶段、attempt、序号、payload digest 校验以及重复投递收敛；冲突写入 rejection 审计。
- [ ] C08 实现来源序号和因果前驱驱动的投影器；覆盖乱序 pending、缺口补齐、跨 stage 依赖、权威 attempt 和提前终态。
- [ ] C09 实现 run/stage 状态机、最后成功阶段、指标缺失原因、原始 Token 分桶、`delivery`/`evolution_eval` cost bucket 与 evidence 投影。
- [ ] C10 实现本地持久 outbox 及固定 event ID 重放；stage 开始和结束设置账本确认屏障。
- [ ] C11 实现 Recovery Reconciler，覆盖进程退出、用户中断、工具错误、账本不可用、永久序号缺口和结果不确定场景。
- [ ] C12 实现 `get_run` 与 `rebuild_projection`；证明完整查询可定位版本、阶段、指纹、Token、耗时、证据、终态和修订历史。
- [ ] C13 为执行上下文加入 `binding_digest` 验证；stage 启动前校验，事件接收时再次校验，记录 mismatch rejection。
- [ ] C14 添加单元、事务并发、故障注入和端到端契约测试，对应第 10 节每个 A-ID。
- [ ] C15 生成第 11 节证据包，记录实际实现文件、迁移、测试命令、退出码、测试报告和样例 run 导出。

## 10. 验收用例

所有用例均为自动验证。测试名称需保留 A-ID，便于从 task contract 追溯到可执行证据。

### A01 完整生产 run 可追溯

- **GIVEN** production 活动版本 V1 包含 stage graph、skill/template/validator/routing 版本和 code SHA
- **WHEN** 同一 run 依次追加开发、verify、QA、Token、命令、输入输出和证据事件并成功终结
- **THEN** `get_run` 返回唯一 ID、V1 完整绑定、按逻辑顺序排列的全部权威阶段、指纹、真实 Token 分桶、耗时、证据、成功门禁和最终状态；`last_successful_stage` 为最后必需阶段

### A02 顺序与并发重复创建

- **GIVEN** 相同作用域、幂等键和请求内容
- **WHEN** 顺序提交 3 次并并发提交 20 次 `create_run`
- **THEN** 21 个响应均返回同一 `pipeline_run_id`，存储中只有一条 dedup 映射、一条 run 和一条 `RUN_REGISTERED`，且只有首次响应 `created=true`

### A03 幂等键内容冲突

- **GIVEN** 一个幂等键已绑定任务快照 T1
- **WHEN** 使用同一键提交任务快照 T2
- **THEN** 返回 `IDEMPOTENCY_CONFLICT`，原 run 和版本绑定保持原值，run 总数不变

### A04 重试跨越生产版本切换

- **GIVEN** 首次请求在 V1 活动时创建 R1，随后活动指针切换到 V2
- **WHEN** 首次请求使用原幂等键重试，并使用新幂等键创建 R2
- **THEN** 重试返回 R1 + V1；新请求返回 R2 + V2；两个 run 的 binding digest 分别永久匹配各自 manifest

### A05 创建与指针切换并发

- **GIVEN** `create_run` 与 V1 -> V2 指针切换并发执行
- **WHEN** 重复运行竞争测试至少 100 次
- **THEN** 每个 run 完整绑定 V1 或 V2 中的一个 manifest，所有组件版本来自同一 manifest，零混合版本与悬空引用

### A06 乱序事件与重复投递

- **GIVEN** attempt 产生 seq 1..6，终态 seq 6 与输出 seq 5 先于 seq 2..4 到达，部分事件重复投递
- **WHEN** 账本依次接收乱序批次
- **THEN** 原始唯一事件数为 6；缺口期间 `WAITING_FOR_GAP` 且终态尚未生效；补齐后投影为预期终态，pending 清空，投影摘要与顺序输入基线一致

### A07 同事件不同内容冲突

- **GIVEN** 已接收 event E + payload digest D1
- **WHEN** 再投递 E + digest D2
- **THEN** 返回 `EVENT_IDEMPOTENCY_CONFLICT`，D1 保持原值，rejection 审计可查询，run `integrity_state=INCONSISTENT` 且无法成功收敛

### A08 版本摘要不一致

- **GIVEN** run 绑定 V1
- **WHEN** worker 使用 V2 binding digest 启动 stage 或追加事件
- **THEN** 启动前校验或接收校验返回 `VERSION_BINDING_MISMATCH`，事件不推进投影，拒绝审计保存请求摘要和原因，run 继续绑定 V1

### A09 stage 中断与指标缺失

- **GIVEN** verify stage 已开始并记录部分命令，worker 随后进程退出
- **WHEN** lease 超时且 reconciler 收敛 run
- **THEN** 已发生事实保持可查询；attempt 与 run 标记 `INTERRUPTED`；`last_successful_stage` 指向前一成功阶段；Token/耗时缺失项带 `PROCESS_EXITED` 或 `PROVIDER_DID_NOT_REPORT`

### A10 账本短暂不可用与 outbox 重放

- **GIVEN** stage 开始事件已确认，执行结果已写入本地 outbox，账本随后短暂不可用
- **WHEN** worker 重试直到账本恢复，并重复发送同一批事件
- **THEN** 每项事实只保存一次，stage 正确终结，来源序号连续，投影与无故障基线摘要一致

### A11 动作后、结果落盘前崩溃

- **GIVEN** 外部命令已发出，进程在结果写入 outbox 前崩溃
- **WHEN** reconciler 接管过期 lease
- **THEN** 原 attempt 追加 `STAGE_ATTEMPT_INTERRUPTED`，缺失原因包含 `RESULT_UNCERTAIN_AFTER_CRASH`；run 不产生虚假成功；新 attempt 获得更高 attempt 编号

### A12 旧 worker 晚到

- **GIVEN** attempt 1 lease 过期，attempt 2 已成为权威执行
- **WHEN** attempt 1 的成功事件晚于 attempt 2 事件到达
- **THEN** 晚到事实保持可查询并标记非权威，attempt 1 无法覆盖 attempt 2 或推进 run，投影记录 supersede 关系

### A13 repair/replay 身份与版本关系

- **GIVEN** 已终态 production run R1 绑定 V1
- **WHEN** 创建默认 repair、同版本 replay 和显式 V2 migration
- **THEN** 三次执行各有新 run ID；repair/replay 绑定 V1；migration 绑定 V2 并记录 `migrates_version` 与 reason；R1 保持原绑定

### A14 原始事实不可变与追加修订

- **GIVEN** 一个 run 已成功终结
- **WHEN** 尝试 update/delete 原始 event，并通过授权入口提交结论修订
- **THEN** update/delete 被存储层拒绝；`OUTCOME_REVISED` 成功追加；查询同时返回原执行终态和最新 `effective_outcome`

### A15 投影可重建

- **GIVEN** 一个包含乱序、重复投递、supersede、指标和终态修订的 run
- **WHEN** 删除投影缓存并从 run + manifest + 原始唯一事件重建两次
- **THEN** 两次 `projection_digest` 完全一致，并与删除前摘要一致；事件计数、pending、权威 attempt、状态、指标和证据均一致

### A16 完整性阻断提前终态

- **GIVEN** `RUN_SUCCEEDED` 已到达，但一个必需 stage 终态事件或输入指纹永久缺失
- **WHEN** 投影与恢复阈值到期
- **THEN** run 无法进入有效成功结果；投影展示缺失依赖；reconciler 最终追加中断事实和明确缺失原因

## 11. 可复跑证据契约

开发 agent 必须提交以下命令及原始退出码；测试路径可按仓库布局映射，A-ID 与断言保持一致：

```bash
python3 -m pytest -q tests/run_ledger
python3 -m pytest -q tests/run_ledger/test_run_creation.py -k 'A02 or A03 or A04 or A05'
python3 -m pytest -q tests/run_ledger/test_event_ordering.py -k 'A06 or A07 or A12 or A16'
python3 -m pytest -q tests/run_ledger/test_recovery.py -k 'A09 or A10 or A11'
python3 -m pytest -q tests/run_ledger/test_version_binding.py -k 'A01 or A04 or A05 or A08 or A13'
python3 -m pytest -q tests/run_ledger/test_projection_rebuild.py -k 'A14 or A15'
```

证据包固定包含：

| 证据 | 内容要求 |
|---|---|
| `test-results.xml` | 全部 A01-A16 的测试名、时长、通过状态 |
| `concurrent-create.json` | A02/A05 的请求数、唯一 run 数、各版本绑定计数、冲突结果 |
| `sample-run-export.json` | A01 的 run、binding、事件、stage 投影、指标、证据与终态 |
| `out-of-order-replay.json` | A06 的接收顺序、逻辑顺序、pending 变化和最终 digest |
| `recovery-export.json` | A09-A12 的 attempt、lease、supersede、中断原因和 outbox 重放结果 |
| `projection-rebuild.json` | A15 删除前、两次重建后的 digest 与逐字段差异 |
| `immutability-check.txt` | A14 的 update/delete 拒绝结果与追加修订查询结果 |

每份 JSON 证据包含 `generated_at`、代码 SHA、schema version、测试 seed 和生成命令。并发与乱序测试使用固定 seed，同时至少追加一轮随机 seed；失败输出保留本轮 seed 以便复现。

## 12. 完成定义

- C01-C15 全部完成并能定位到实际实现文件与测试。
- A01-A16 全部自动通过，完整测试命令退出码为 0。
- 同幂等请求、乱序/重复事件、故障恢复和版本切换均产生确定结果。
- 任一 run 的完整版本绑定可独立校验 manifest digest，stage 事实均匹配同一 binding digest。
- 原始事实具备存储层不可变保障，派生投影可确定性重建。
- 中断 run 保留最后成功阶段和每项缺失指标原因，查询结果不伪造完整性。
- 证据包字段齐全，另一开发或验证 agent 可仅凭命令与 seed 复跑相同断言。
