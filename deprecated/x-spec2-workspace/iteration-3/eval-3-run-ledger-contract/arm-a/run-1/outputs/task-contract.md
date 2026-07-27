# 运行账本与版本绑定：开发任务契约

## 1. 目标与完成定义

实现一套生产可用的运行账本，使每个用户任务在创建时获得唯一 `pipeline_run_id` 和不可变 pipeline 版本快照；同一任务的反馈返工以新的 `stage_attempt` 继续写入原 run。所有原始运行事实追加保存，重复提交可幂等重放，乱序事实可重建，冲突和迟到事实可审计。

完成后必须同时满足：

- 每个生产、隔离评测和回放执行都能定位 pipeline、skill、template、validator、模型、权限/预算及代码快照。
- 新 run 的路由与 pipeline 版本在同一原子提交中绑定；执行阶段始终读取 run 的版本快照。
- 事件、artifact、Token、耗时、证据和终态均可按 run、阶段、attempt 下钻。
- collector 重试不会重复计数或重复推进状态。
- 乱序、终态冲突、终态后迟到证据、进程崩溃和派生视图落后都有确定恢复路径。
- 当前 spec 历史运行可登记为指定 run 的 attempt 1/2，并保存两版产物和反馈证据。

## 2. 范围

### 2.1 本次实现

- run 身份、幂等创建、父子运行关系和历史导入。
- 已发布 pipeline manifest、当前生产版本指针、原子版本绑定和回滚后的新任务路由。
- `x-spec2 -> x-req2 -> x-dev -> x-verify -> x-qa-gate -> x-fix` 的 stage attempt 分配与事实采集。
- 追加事件、内容寻址 artifact、原始 Token 分桶、耗时、证据引用和版本化派生视图。
- 重复、乱序、缺口、冲突终态、迟到证据、显式用户续作和崩溃恢复。
- 数据迁移、并发/故障测试、单命令验收入口和机器可读证据包。

### 2.2 接口边界

- 知识库消费账本的稳定查询接口；知识聚合、候选生成、评分策略和候选晋级算法属于后续任务。
- grader 可追加独立评分事实及证据引用；运行事实的写权限保留给运行侧 producer。
- 发布组件维护 immutable manifest 和 current-version 指针；本任务实现其与 run 创建之间的事务契约。
- artifact 存储只接收已完成上传且 digest 校验通过的对象；账本只引用可读取的 immutable artifact。

### 2.3 延后

- 自动改写生产 skill、无人审批晋级、模型训练、跨项目云服务、组织权限控制台、复杂统计平台和 Token 金额换算。

## 3. 显式假设

1. 数据库支持事务、唯一约束、行级 compare-and-set，以及可单调递增的提交序号；具体数据库由实现仓库现状决定。
2. pipeline manifest 和 artifact 均可按 digest 内容寻址，已发布对象禁止原地覆盖。
3. 上游能为一个用户任务提供稳定 `client_task_key`；同一 key 的重试代表同一用户任务。
4. producer 能提供稳定 `event_id`、`producer_id` 和 attempt 内单调 `producer_seq`；网络重试沿用原值。
5. `occurred_at` 仅用于展示，因果重建使用 attempt、`producer_seq` 和 `causal_parent_event_ids`。
6. 同一用户任务中的 x-fix、用户反馈返工和门禁重跑属于原 run；隔离 baseline/candidate 执行及后续独立回放各自创建新 run，并通过 `parent_run_id`/`relation_type` 关联来源。
7. run 生命周期终态后，明确的用户续作命令可以创建新的 `lifecycle_revision`；迟到 collector 事件只能补充证据。每个 lifecycle revision 的历史终态保持不可变。
8. 当前 spec 的历史记录可取得两版 artifact、反馈、分数、Token 及版本 digest；缺少任一必填版本定位信息时，历史导入保持 `quarantined`，不得进入完整统计。
9. 仓库测试框架和最终代码目录由开发 agent 依据现状落位；开发 agent 必须提供本契约规定的稳定一键验收入口。

## 4. 核心不变量

| ID | 不变量 |
|---|---|
| I1 | `pipeline_run_id` 全局唯一；`client_task_key` 在生产任务命名空间内唯一。重复创建返回原 run。 |
| I2 | run 行与完整 `pipeline_binding` 在一个事务中提交。未绑定、部分绑定或引用未发布 manifest 的生产 run 无法创建。 |
| I3 | run 创建后 `pipeline_binding` 永久固定；所有阶段按该快照解析组件。 |
| I4 | `(pipeline_run_id, stage_key, attempt_no)` 唯一；`attempt_no` 由服务端事务性单调分配。 |
| I5 | 原始事件只追加；`event_id` 唯一。同 ID 同 payload 返回原确认，同 ID 异 payload 产生完整性冲突。 |
| I6 | arrival 顺序由 `ledger_seq` 保存，逻辑顺序由 stage attempt、producer sequence 和因果引用重建。时间戳不决定状态。 |
| I7 | 每个 lifecycle revision 和 stage attempt 最多有一个有效终态。竞争终态只有一个通过 CAS，其他事实进入冲突隔离。 |
| I8 | 迟到证据通过新事件引用原事件或终态；已发布结果 digest、旧评分和旧终态不被覆盖。 |
| I9 | artifact 事件只引用已完成且 digest 校验成功的 immutable object。 |
| I10 | Token 使用按 provider 请求身份和事件身份去重，保留 provider 原始分桶；派生汇总可由原始事件完整重算。 |
| I11 | 派生视图、搜索索引和统计表均可丢弃重建；它们无权改写原始账本。 |
| I12 | executor 无法读取 grader-only 断言；grader 只能追加评分域事实，无法写运行域事实。 |

## 5. 数据契约

字段名可映射到仓库命名规范，语义、唯一性和不可变性必须保持。

### 5.1 `pipeline_manifest`

```text
pipeline_version       全局唯一、可读版本号
manifest_digest        内容 digest，唯一且不可变
status                 draft | published | retired
published_at/by        发布审计信息
stage_bindings[]       每个 stage_key 的 skill/template/validator locator + digest
router_policy          locator + digest
default_model          provider/model/revision
schema_version         manifest schema 版本
rollback_target        已验证的目标 pipeline_version，可空
```

`published` 后所有组成字段冻结。任一 locator 无法解析或 digest 不匹配时，manifest 不得用于生产绑定。

### 5.2 `production_version_pointer`

```text
route_key              路由命名空间，主键
pipeline_version       当前发布版本
generation             单调递增 CAS 版本
changed_at/by
change_reason
```

发布与回滚使用 `expected_generation + expected_pipeline_version` compare-and-set。一次提交只生成一个当前版本。

### 5.3 `pipeline_run`

```text
pipeline_run_id        prun-...，主键
client_task_key        幂等创建键，生产任务命名空间内唯一
task_fingerprint       规范化意图输入 digest
run_kind               production | evaluation | replay | historical_import
parent_run_id          可空
relation_type          baseline_of | candidate_of | replay_of | imported_from | null
record_origin          live | historical_import
route_key
pipeline_binding       完整快照，见 5.4
code_snapshot          repo locator + commit/tree digest + dirty-state digest/声明
execution_profile      权限、预算、隔离身份和工作区 locator
created_at/by
current_revision_no    当前生命周期修订号
integrity_status       healthy | incomplete | quarantined
schema_version
```

### 5.4 `pipeline_binding`

```text
pipeline_version
manifest_digest
pointer_generation_at_bind
stage_bindings[]       stage_key + skill/template/validator locator/digest
router_policy_digest
default_model          provider/model/revision
bound_at
```

run 创建事务读取 current pointer、解析已发布 manifest、校验所有 digest，然后同时插入 run 与 binding。阶段运行时禁止重新读取 current pointer。

### 5.5 `run_lifecycle_revision`

```text
pipeline_run_id
revision_no            从 1 单调递增；联合主键
opened_by_event_id
open_reason            initial | explicit_user_feedback
status                 open | accepted | failed | canceled
result_artifact_ref    终态时必填或明确 reason_code
terminal_event_id      终态后固定
supersedes_revision_no 显式续作时指向上一修订
```

迟到证据不会创建 revision。`ContinueRunFromFeedback` 是唯一允许在历史终态后开新 revision 的命令，必须携带用户反馈 artifact/evidence 和上一 revision 的 CAS 前置条件。

### 5.6 `stage_attempt`

```text
pipeline_run_id
revision_no
stage_key               x-spec2 | x-req2 | x-dev | x-verify | x-qa-gate | x-fix
attempt_no              对同一 run + stage_key 单调递增
reason_code             initial | retry | feedback_rework | gate_failure | recovery
status                  allocated | running | succeeded | failed | canceled
input_artifacts[]        immutable refs
output_artifacts[]       immutable refs
model_binding            实际 provider/model/revision；覆盖时保留授权依据
started_event_id
terminal_event_id
```

attempt 分配、编号和 `ATTEMPT_ALLOCATED` 事件在同一事务中完成。状态转换采用期望状态 CAS。

### 5.7 `ledger_event`

```text
event_id                全局唯一 UUID/ULID
ledger_seq              数据库提交时分配的全局 arrival 序号
pipeline_run_id
revision_no
stage_key               run 级事件可空
attempt_no              run 级事件可空
event_type
producer_domain         runtime | grader | admin_import
producer_id
producer_seq            producer 在该 attempt/domain 内单调递增
causal_parent_event_ids[]
occurred_at             producer 时间
received_at             服务端时间
schema_version
payload
payload_digest          canonical payload digest
idempotency_key         默认等于 event_id
artifact_refs[]
evidence_refs[]
```

必需事件至少覆盖：run 创建、revision 打开/终结、attempt 分配/开始/终结、artifact 产生、provider usage、验证证据、用户反馈、迟到证据修订、完整性冲突和历史导入。

### 5.8 `artifact_ref`、`evidence_ref` 与 Token

```text
artifact_ref: store, locator, sha256, byte_size, media_type, schema_version
evidence_ref: evidence_id, kind, artifact_ref/url, assertion_id, visibility
provider_usage: provider_request_id, provider, model, bucket_name, raw_value, unit
duration: start_event_id, end_event_id, elapsed_ms, clock_source
```

`provider_request_id + bucket_name` 在单次 run 中唯一。原始分桶包含 provider 返回的 input、cached input、output、reasoning 等字段；未知分桶按原名保存。duration 使用成对事件或单调时钟结果，禁止从乱序 wall-clock 时间直接相减。

### 5.9 冲突与修订

```text
integrity_conflict:
  conflict_id, run_id, conflict_type, existing_event_id,
  incoming_event_id/payload_digest, detected_at, resolution_status,
  resolver, resolution_event_id

event_revision_link:
  new_event_id, target_event_id, relation = supplements | corrects_interpretation,
  reason_code, created_by
```

修订追加新事实并保留旧事实。需要改变对外结论时，授权方创建新 lifecycle revision 或新的 grader score revision，并显式标记 supersedes 关系。

## 6. 命令与错误契约

### 6.1 写命令

- `CreateRun(client_task_key, task_fingerprint, route_key, execution_profile)`：原子解析并绑定 current version；重复同 key、同 fingerprint 返回相同 run；同 key、异 fingerprint 返回 `TASK_KEY_CONFLICT`。
- `ImportHistoricalRun(...)`：管理员域专用；要求完整 binding 和 artifact digest，写入 `record_origin=historical_import`。
- `AllocateAttempt(run_id, revision_no, stage_key, reason_code, expected_revision_status)`：事务性分配下一个 attempt。
- `AppendEvent(event)`：成功确认代表事件已持久化；同 ID 同 digest 返回首次确认；同 ID 异 digest 返回 `EVENT_ID_CONFLICT` 并写冲突记录。
- `FinalizeAttempt(..., expected_status, terminal_event)`：终态 CAS 与事件追加同事务。
- `FinalizeLifecycleRevision(..., expected_status, result_ref, terminal_event)`：终态 CAS 与事件追加同事务。
- `ContinueRunFromFeedback(run_id, expected_revision_no, feedback_ref)`：创建下一 revision 和首个返工 attempt；沿用原 binding。
- `AttachLateEvidence(run_id, target_event_id, evidence_ref)`：追加 supplements 修订，不触发状态转换。
- `PublishOrRollback(route_key, expected_generation, expected_version, target_version)`：更新 current pointer；失败返回 `BASELINE_STALE`。

### 6.2 查询

- `GetRun(run_id, as_of_ledger_seq?)`：返回 binding、revision、attempt、artifact、usage、证据、冲突和投影水位。
- `ListRunEvents(run_id, after_ledger_seq, limit)`：严格按 arrival 序分页，提供 payload digest。
- `GetLogicalTimeline(run_id)`：按 revision/stage/attempt/producer sequence 和因果边输出；缺口及冲突必须显式标注。
- `VerifyRunIntegrity(run_id)`：重算 digest、唯一性、序列缺口、终态、artifact 可读性和 binding 完整性。

统一错误至少包含 `code`、`message`、`run_id`、`event_id`、`retryable` 和 `conflict_ref`。客户端只对 `retryable=true` 使用同一幂等身份重试。

## 7. 状态所有者

| 状态/事实 | 唯一所有者 | 允许操作 | 禁止能力 |
|---|---|---|---|
| current pipeline pointer | 发布注册表 | CAS 发布、CAS 回滚 | 阶段执行器直接修改 |
| run 身份与 binding | Run Registry | 幂等创建、历史导入、读取 | 创建后改写 binding |
| revision/attempt 编号与状态 | Run Coordinator | 分配、CAS 转换、显式续作 | collector 自行分配 attempt 号 |
| 原始 ledger event | Ledger Store | 追加、幂等确认、冲突隔离 | update/delete 历史事实 |
| artifact bytes/digest | Artifact Store | 完成上传、校验、按 digest 读取 | 同 locator 原地覆盖 |
| 派生 timeline/统计 | Ledger Projector | checkpoint、重放、重建 | 成为事实来源 |
| 运行事实提交 | stage producer | 提交本域事件和证据 | 写 grader-only 事实 |
| grader 评分事实 | grader producer | 追加评分/重评分及 grader-only 证据 | 改写运行事实或 artifact |
| 冲突裁决 | 审计/运维角色 | 追加 resolution event | 删除冲突记录 |

## 8. 时序、幂等和恢复规则

### 8.1 重复请求

1. 创建 run 先以 `client_task_key` 命中唯一约束；同 fingerprint 返回已有 run 及原 binding。
2. 追加事件先比较 `event_id` 和 canonical `payload_digest`。完全一致视为成功重放，Token、artifact 和状态均不重复生效。
3. 同 `event_id` 携带不同 payload 时，原事件继续有效；新提交进入 `integrity_conflict`，run 标记 `quarantined`，调用方收到不可重试错误。

### 8.2 乱序和缺口

1. Ledger 接收可独立校验的乱序事件并保存 arrival 序。
2. projector 为每个 producer stream 维护 contiguous watermark；发现 `producer_seq` 缺口时标记 `incomplete`，暂停依赖该缺口的状态推进。
3. 缺失事件到达后，从受影响 attempt 的上一个 checkpoint 重放；重放结果必须与全量重建一致。
4. 两个缺少明确因果关系的并发事件保留为并行分支；系统禁止用 `occurred_at` 猜测先后。

### 8.3 终态竞争与迟到证据

1. attempt/revision 终态通过 expected-status CAS 提交，胜者成为有效终态。
2. 相同终态事件的重试幂等成功；不同终态、不同结果 digest 或无效前置状态进入冲突隔离。
3. 终态后的证据事件使用 `AttachLateEvidence`；查询同时展示原发布结果、迟到证据和 revision link。
4. 用户明确要求继续返工时使用 `ContinueRunFromFeedback`。新 revision 沿用原 pipeline binding，上一 revision 的结果与终态保持可寻址。

### 8.4 崩溃与部分写入

1. 事件持久化、唯一性判定、状态 CAS 和 projector-outbox 通知在同一数据库事务提交。
2. API 只在事务提交后确认成功。连接中断时客户端以原 idempotency key 重试。
3. projector 按 `ledger_seq` checkpoint，处理完成后原子推进水位；重复消费安全。
4. outbox 可重新扫描，派生表可从零重建。重建期间查询返回 `projection_watermark` 和 `stale=true`，禁止伪装最新数据。
5. artifact 先完成上传和 digest 校验，再允许引用事件提交。孤立上传由保留期回收，账本引用对象禁止回收。

### 8.5 版本切换并发

run 创建和 pointer 更新必须具有明确串行化点。串行化点位于回滚提交前的 run 完整绑定旧版本；位于回滚提交后的 run 完整绑定目标版本。任何阶段都只使用 run binding，因而单个 run 内不会混用版本。

## 9. 实现 checklist

- [ ] **T1 数据迁移**：建立 manifest、current pointer、run、binding、lifecycle revision、attempt、ledger event、artifact/evidence ref、冲突、revision link、outbox/checkpoint 表及全部唯一约束；提供向前迁移和可验证回滚方案。
- [ ] **T2 immutable manifest**：实现 manifest 发布前 digest/locator 校验和发布后冻结；无法解析的版本拒绝生产绑定。
- [ ] **T3 原子 run 创建**：实现 `CreateRun` 的幂等键、fingerprint 冲突、路由+版本同事务快照，以及回滚并发下的串行化测试。
- [ ] **T4 历史导入**：实现受限 `ImportHistoricalRun`，登记 `prun-019f84e4-1296-7fb2-a2a1-50b391b11c1c-001` 的 spec attempt 1/2；两次产物分别保留 hash、反馈、分数、Token 和知识引用。
- [ ] **T5 revision 与 attempt**：实现服务端编号、CAS 状态机、显式用户续作；确保反馈返工沿用 run 与 binding，独立 replay 创建关联的新 run。
- [ ] **T6 追加与幂等**：实现 canonical digest、事件唯一性、同 payload 重放、异 payload 冲突隔离和 retryable 错误分类。
- [ ] **T7 逻辑重建**：实现 ledger arrival 序、producer watermark、因果边、缺口标记、乱序重放、并行事件表示和全量重建校验。
- [ ] **T8 终态和迟到事实**：实现 attempt/revision 终态 CAS、冲突终态隔离、迟到 evidence revision link、版本化对外结果。
- [ ] **T9 artifact/usage/duration**：接入内容寻址 artifact；按 provider request 去重原始 Token 分桶；用可靠 elapsed 数据生成阶段和 attempt 汇总。
- [ ] **T10 全 stage 接入**：让 x-spec2、x-req2、x-dev、x-verify、x-qa-gate、x-fix 都读取 run binding、分配 attempt、提交输入输出指纹、使用量、耗时、证据和终态。
- [ ] **T11 权限隔离**：分离 runtime、grader、admin_import 写域；增加 grader-only 断言不可见和 grader 无法改写 runtime 事实的授权测试。
- [ ] **T12 恢复机制**：实现事务 outbox、projector checkpoint、幂等消费、停机后追平、从零重建、artifact 引用完整性扫描。
- [ ] **T13 查询与审计**：实现 run 快照、原始事件分页、逻辑 timeline、as-of 查询、projection watermark 和完整性校验。
- [ ] **T14 可观测性**：暴露冲突数、缺口数、quarantined run、projection lag、重放次数和绑定失败 reason code；日志不得包含 grader-only 内容。
- [ ] **T15 验收入口**：提供 repo 内稳定脚本 `scripts/verify-run-ledger-contract.sh`，串行执行迁移检查、单元、并发、故障恢复和集成测试，并输出第 11 节证据包。

依赖顺序：T1 → T2/T6 → T3/T5/T7/T9 → T4/T8/T10/T11/T12/T13 → T14/T15。T2、T6 可并行；T8、T9、T11 可在 T5/T6 完成后并行。

## 10. 验收用例

每个用例都必须自动化，断言数据库原始事实和公开查询结果。并发用例至少循环 100 次或使用确定性 barrier 控制交错。

### AC1 原子绑定与幂等创建

- GIVEN route 当前指向 V1，manifest 完整发布
- WHEN 20 个 worker 以同一 `client_task_key` 并发创建任务
- THEN 只产生一个 run，所有响应返回相同 `pipeline_run_id`，binding 全部为 V1，run 行与 binding 同一提交可见

同 key、异 task fingerprint 必须返回 `TASK_KEY_CONFLICT`，且不产生第二个 run。

### AC2 回滚与新任务并发

- GIVEN 当前指针为 V2，目标回滚为 V1
- WHEN 一个 worker CAS 回滚，其他 worker 在 barrier 两侧创建不同任务
- THEN 每个 run 完整绑定 V2 或 V1；回滚提交后的 run 全部绑定 V1；任一 run 的各阶段解析结果均等于自身 binding

### AC3 当前 spec 历史运行

- GIVEN 两次 spec 产物及其反馈、分数、Token、知识引用和版本 digest
- WHEN 执行历史导入
- THEN 两次产出归入 `prun-019f84e4-1296-7fb2-a2a1-50b391b11c1c-001` 的 x-spec2 attempt 1/2，artifact hash 独立可查，attempt 2 的 reason 为 `feedback_rework`，run 仅有一份固定 binding

重复导入返回相同 run/事件；改变任一已导入 payload 产生冲突且不覆盖原记录。

### AC4 事件重试与 Token 去重

- GIVEN 一个 provider usage 事件已成功提交，调用方未收到响应
- WHEN 使用相同 event ID、provider request ID 和 payload 重试 10 次
- THEN ledger 仅有一份原始事实，阶段/attempt/run Token 汇总只计一次，每次响应指向相同 ledger 序号

### AC5 同 ID 异 payload

- GIVEN event E 已存在
- WHEN collector 用 E 提交不同 artifact digest 或 Token 数值
- THEN 返回 `EVENT_ID_CONFLICT`、原 E 保持有效、冲突记录含两个 digest、run 进入 `quarantined`，完整性门禁失败

### AC6 乱序与序列缺口

- GIVEN producer sequence 为 1..5 且 3 依赖 2
- WHEN 按 1、4、5、3、2 到达
- THEN arrival timeline 保留该顺序；2 到达前 projection 标记缺口且不提前终结；补齐后 logical timeline 为 1..5，全量重建结果与增量结果 byte-for-byte 等价

### AC7 并行事实

- GIVEN 两个 producer 在同一 attempt 产生无因果边的证据
- WHEN 两者以不同 wall-clock 偏差和相反 arrival 顺序提交
- THEN 查询将其表示为并行事实，最终状态与 wall-clock 大小无关，所有重复排列得到同一规范化投影

### AC8 冲突终态

- GIVEN attempt 为 running
- WHEN success 与 failure 使用相同 expected state 并发终结
- THEN 仅一个 CAS 成功，另一个进入冲突隔离；有效终态、原始竞争事实和冲突依据均可查，artifact/Token 不重复

### AC9 终态后迟到证据

- GIVEN revision 1 已 accepted 且发布结果 digest 为 H1
- WHEN collector 提交指向该终态的迟到证据
- THEN H1 与 accepted 事实保持不变，新证据以 supplements link 可查，查询明确显示迟到时间和 projection revision

### AC10 显式用户反馈续作

- GIVEN revision 1 已 accepted
- WHEN 用户反馈触发 `ContinueRunFromFeedback`
- THEN 同一 run 创建 revision 2 和新的 stage attempt，沿用原 binding；revision 1 的终态/H1 可查；revision 2 独立终结并以 supersedes 关系发布 H2

普通 late-evidence producer 调用该命令必须因权限不足失败。

### AC11 崩溃恢复

- GIVEN ledger 事务已提交且 projector 尚未更新
- WHEN 在事务提交后、响应前和 projection checkpoint 前分别注入崩溃并重启
- THEN客户端原 ID 重试得到同一事件，projector 从 checkpoint 追平，无丢失/重复；从空派生库重建得到同一结果和 digest

### AC12 artifact 原子可见性

- GIVEN artifact 上传未完成或 digest 不匹配
- WHEN producer 尝试提交引用事件
- THEN事件提交失败且可重试，账本不存在悬空引用；完成并校验上传后原事件身份可成功提交一次

### AC13 完整版本定位

- GIVEN 任意 production/evaluation/replay run
- WHEN 执行 `VerifyRunIntegrity`
- THEN可解析 pipeline manifest、每个 stage 的 skill/template/validator、模型、代码快照和执行 profile，digest 全部匹配

缺少任一项时 run 标记 incomplete/quarantined，并从可比评测及 accepted 统计排除。

### AC14 写域隔离

- GIVEN runtime 和 grader 使用各自身份
- WHEN runtime 请求 grader-only 断言，或 grader 尝试更新 runtime event
- THEN授权拒绝；审计日志记录主体和 reason code，日志内容不泄漏断言正文

### AC15 全链路 attempt 下钻

- GIVEN 一个任务经历 x-spec2、x-req2、x-dev、x-verify、x-qa-gate、两轮 x-fix 和重跑后 accepted
- WHEN 查询 run 汇总
- THEN每个阶段/attempt 的输入输出 hash、Token 原始分桶、elapsed、证据和终态可下钻；run 总数由原始事实重算一致；修复和重跑全部计入 production Token

## 11. 可复跑证据契约

开发完成后必须能从干净测试数据库执行：

```bash
bash scripts/verify-run-ledger-contract.sh
```

脚本需满足：

1. 失败即非零退出；成功为 0。
2. 使用固定随机种子，输出 seed；并发交错使用 barrier 或受控 scheduler。
3. 覆盖 AC1–AC15，并打印每个 AC 的 PASS/FAIL、测试标识和耗时。
4. 生成 `artifacts/run-ledger-contract/verification.json`，至少包含：

```json
{
  "contract": "run-ledger-version-binding-v1",
  "spec_version": 2,
  "source_revision": "<code commit/tree digest>",
  "schema_version": "<ledger schema version>",
  "seed": "<fixed seed>",
  "started_at": "<iso8601>",
  "finished_at": "<iso8601>",
  "commands": [{"argv": ["..."], "exit_code": 0, "duration_ms": 0}],
  "acceptance": [{"id": "AC1", "status": "passed", "test_ids": ["..."]}],
  "rebuild": {
    "incremental_projection_digest": "sha256:...",
    "full_rebuild_projection_digest": "sha256:...",
    "equal": true
  },
  "artifacts": [{"path": "...", "sha256": "..."}]
}
```

5. 保存迁移检查、并发交错 trace、崩溃注入点、原始 ledger 导出、重建后投影 digest 和完整性检查结果；证据文件均记录 SHA-256。
6. 对每个测试保留最小必要数据，grader-only 断言正文和凭据不得进入证据包。

## 12. 交付门禁

以下条件全部通过后才可标记实现完成：

- T1–T15 全部完成并能回指代码、测试或迁移证据。
- AC1–AC15 全绿，verification JSON schema 校验通过。
- 增量投影与全量重建 digest 一致。
- 幂等重试、终态竞争和回滚并发测试无重复 run、重复 Token、混合 binding 或丢失事件。
- 每个测试 run 通过 `VerifyRunIntegrity`；预期冲突用例准确进入 quarantined。
- 可审计定位当前 spec 的 attempt 1/2 以及各自 artifact hash、反馈、分数、Token、知识引用。
- 数据迁移与回滚演练完成，回滚不会删除原始账本事实。
