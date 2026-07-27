# 失败与扣分知识库：开发任务契约

## 1. 目标与交付边界

### 1.1 目标

实现一个可审计、可并发写入、可版本化修订的“失败与扣分知识库”，为 pipeline 优化提供稳定证据。系统必须：

1. 独立记录执行失败、grader 扣分和后续重评分。
2. 把每条知识关联到 run、pipeline/skill 版本、阶段 attempt、证据、原因、根因结论、修复与回放结果。
3. 保持原始运行事实和历史评分追加保存；归因、根因和处置结论通过修订演进。
4. 对重复、乱序、并发和迟到写入提供确定性结果。
5. 让下游候选生成与统计只消费满足明确状态条件的知识版本。

### 1.2 首版范围

- 失败、扣分、重评分三类记录的存储模型和写入 API。
- 证据的内容寻址、访问级别和复用关系。
- canonical 知识条目、知识修订、修复记录、回放结果及它们之间的关联。
- collector、grader、根因分析者和 replay runner 的状态所有权与权限边界。
- 幂等写入、并发归并、乐观并发修订、迟到证据处理和冲突隔离。
- 按 run、阶段、reason code、根因状态、知识版本和证据 ID 查询。
- 数据迁移、确定性测试、竞态测试和可复跑验收证据。

### 1.3 范围外

- 自动修改生产 skill 或 template。
- 自动批准候选晋级或发布。
- 控制台、复杂统计平台、跨项目云服务和组织级权限系统。
- Token 金额换算。
- 候选评测与发布流程本身；本任务只提供其所需的稳定知识引用。

### 1.4 硬约束

- 一个用户任务对应一个 `pipeline_run_id`；返工使用同一 run 下的新 `stage_attempt_id`。
- 原始事实采用追加写；已提交事实不可原地覆盖。
- 失败记录与扣分记录类型独立；二者可引用同一证据或同一 canonical 知识条目。
- 一次 rubric 版本下的一次评分结果是独立事实；重评分创建新记录。
- 未确认根因保留候选解释、置信依据和缺失证据；统计层不得将其计入“已确认根因”。
- grader-only 断言及受限证据保持访问隔离；执行 agent 只能获得脱敏后的公开摘要和允许读取的证据。
- grader 无权创建、修改或删除运行事实。
- 历史决策固定引用具体 `knowledge_revision_id`；后续修订不得改变历史决策的含义。

## 2. 显式假设

| A-ID | 假设 | 实现影响 | 验证方式 |
|---|---|---|---|
| A1 | 运行账本能够提供稳定的 `pipeline_run_id`、`stage_attempt_id`、事件 ID、版本绑定和 artifact hash | 本模块引用账本身份，不重新生成 run/attempt 身份 | 集成测试使用已存在与不存在的身份写入 |
| A2 | 存储层支持唯一约束、事务和 compare-and-set；首版可用关系数据库实现 | canonical 归并、幂等写入和修订提交都放在单事务内 | 并发测试验证唯一结果与无丢失更新 |
| A3 | 证据正文可大于数据库行限制 | 数据库保存 `evidence_id`、摘要、hash 和 URI；正文进入不可变 artifact 存储 | 写入大证据并按 hash 取回 |
| A4 | `reason_code` 使用版本化词表，未知原因允许进入 `UNCLASSIFIED` | 摄取不因新原因丢失事实；后续修订可补分类 | 未知 reason code 验收用例 |
| A5 | collector 可能重复、乱序或在 run 终态后投递 | 所有摄取端点要求幂等键；迟到内容以关联事实或知识修订保存 | 重放、乱序和终态后写入测试 |
| A6 | 根因确认需要独立角色或策略授权 | 只有 root-cause owner 能提交 `CONFIRMED` 修订 | 权限矩阵测试 |
| A7 | 同一证据指纹只能说明内容相同，不能单独证明两个事件语义相同 | 证据去重与知识归并使用不同的键和规则 | 相同证据、不同断言的测试 |
| A8 | 首版不需要把已有事实做物理合并或删除 | 错误归并通过 supersede 修订纠正，保留完整历史 | 拆分/撤销归并测试 |

## 3. 领域模型与记录类型

### 3.1 不可变事实记录

#### `FailureRecord`

表示执行、验证、QA、修复或回放中的实际失败。

| 字段 | 约束 |
|---|---|
| `failure_id` | 全局唯一，格式建议 `fail_<ulid>` |
| `source_event_id` | 必填；来源事件的幂等身份 |
| `pipeline_run_id` | 必填；引用运行账本 |
| `stage_attempt_id` | 必填；必须属于该 run |
| `pipeline_version_id` | 必填；从 run 绑定复制并校验一致 |
| `stage` | 必填；版本化枚举 |
| `occurred_at` / `observed_at` | 必填；分别表示业务发生时间和摄取时间 |
| `reason_code` / `reason_code_version` | 必填；未知值映射为 `UNCLASSIFIED` 并保留原值 |
| `expected_summary` / `actual_summary` | 必填；脱敏、可查询摘要 |
| `failure_class` | 必填；如 process、contract、state、concurrency、recovery |
| `terminal_effect` | 必填；如 attempt_failed、run_blocked、delivery_blocked |
| `evidence_refs[]` | 至少一个可解析的 `evidence_id` |
| `producer` | 必填；collector 身份与版本 |
| `payload_hash` | 必填；规范化 payload 的内容 hash |
| `recorded_at` | 服务端生成 |

唯一约束：`(producer_namespace, source_event_id)`。相同幂等键且 hash 相同返回原记录；hash 不同写入 `IngestionConflict`，不覆盖原记录。

#### `DeductionRecord`

表示 grader 在某次评分中对一个断言给出的扣分事实。一次评分内每个断言生成一条记录。

| 字段 | 约束 |
|---|---|
| `deduction_id` | 全局唯一，格式建议 `ded_<ulid>` |
| `grading_run_id` | 必填；标识一次完整评分或重评分 |
| `pipeline_run_id` | 必填；被评分 run |
| `stage_attempt_id` | 可选；扣分面向具体 attempt 时必填 |
| `grader_id` / `grader_version` | 必填 |
| `rubric_id` / `rubric_version` | 必填 |
| `assertion_id` | 必填；同 rubric 版本内稳定 |
| `reason_code` / `reason_code_version` | 必填 |
| `expected_summary` / `actual_summary` | 必填；公开可见内容经过脱敏 |
| `score_impact` | 必填；保存原始单位、满分与扣分值 |
| `evidence_refs[]` | 至少一个；可包含 grader-only 证据 |
| `visibility` | `PUBLIC_SUMMARY` 或 `GRADER_ONLY` |
| `payload_hash` / `recorded_at` | 必填 |

唯一约束：`(grading_run_id, rubric_version, assertion_id)`。rubric 升级后的重评分必须创建新的 `grading_run_id` 和新的扣分记录，并通过 `supersedes_grading_run_id` 关联上一轮评分。旧评分及其当时的 run 终态保持可查。

#### `EvidenceRecord`

| 字段 | 约束 |
|---|---|
| `evidence_id` | `sha256:<canonical-bytes-hash>`，内容寻址 |
| `media_type` / `schema_version` | 必填 |
| `artifact_uri` | 必填；指向不可变对象 |
| `content_length` | 必填 |
| `summary` | 必填；不得泄漏 grader-only 断言 |
| `visibility` | `PUBLIC`、`PIPELINE_INTERNAL`、`GRADER_ONLY` |
| `created_by` / `created_at` | 必填 |

相同内容只创建一条证据记录。访问控制作用于证据记录和 artifact 读取，知识引用不能提升访问权限。

#### `ReplayResult`

记录某个修复或知识假设在指定版本上的回放事实。

必填字段：`replay_result_id`、`pipeline_run_id`、`source_knowledge_revision_id`、`fix_id`（可空）、`pipeline_version_id`、`code_snapshot`、`outcome`、`evidence_refs[]`、Token 原始分桶、耗时、`recorded_at`。`outcome` 取 `PASS | FAIL | INCONCLUSIVE | INFRA_ERROR`；只有 `PASS` 或 `FAIL` 可作为假设证伪结果，基础设施错误保持独立。

### 3.2 可修订知识记录

#### `KnowledgeEntry`

canonical 身份容器，只保存稳定身份和创建信息：

- `knowledge_entry_id`
- `canonical_key`
- `created_at` / `created_by`
- `current_revision_id`
- `lifecycle_state`

`canonical_key` 由服务端基于以下规范化元组计算：

`project_scope + knowledge_kind + reason_code_version + reason_code + affected_contract + normalized_failure_signature`

其中 `normalized_failure_signature` 排除 run ID、时间戳、临时路径、随机端口等瞬时值。证据 hash 不参与 canonical key，避免相同问题因新证据被拆成多条。canonical key 相同只创建一个 `KnowledgeEntry`；各来源通过关联表追加。

#### `KnowledgeSourceLink`

把知识条目关联到事实，联合唯一键为：

`(knowledge_entry_id, source_type, source_id)`

`source_type` 取 `FAILURE | DEDUCTION | REPLAY`。关联写入幂等，且必须校验 source 存在。失败与扣分可同时关联同一条知识，但任何一方都不能替代另一方的事实记录。

#### `KnowledgeRevision`

| 字段 | 约束 |
|---|---|
| `knowledge_revision_id` | 全局唯一 |
| `knowledge_entry_id` | 必填 |
| `revision_no` | 从 1 单调递增，entry 内唯一 |
| `parent_revision_id` | 除 revision 1 外必填 |
| `root_cause_status` | `UNASSESSED | HYPOTHESIS | CONFIRMED | REJECTED` |
| `root_cause_statement` | `HYPOTHESIS`/`CONFIRMED` 时必填 |
| `confidence` | 0..1；必须附方法和依据 |
| `supporting_evidence_refs[]` | 可为空；确认时至少一个 |
| `contradicting_evidence_refs[]` | 可为空 |
| `missing_evidence[]` | 未确认状态时必填至少一项 |
| `reason_code` / `affected_contract` | 当前分类结论 |
| `recommended_action` | 可选；必须保持为建议，不能写运行事实 |
| `change_reason` | 必填 |
| `authored_by` / `authored_at` | 必填 |
| `decision_eligible` | 服务端派生，客户端不可写 |

`decision_eligible=true` 的必要条件：`root_cause_status=CONFIRMED`、支持证据可读且完整、无未解决的修订冲突、分类词表有效。优化聚合器默认只读取该状态，并按具体 revision ID 输出引用。

#### `FixRecord`

修复尝试独立于知识结论，字段包括 `fix_id`、`knowledge_revision_id`、目标 pipeline/code 版本、改动摘要、artifact hash、实施 run/attempt、状态和时间。状态取 `PROPOSED | APPLIED | REPLAYED | VERIFIED | INEFFECTIVE | REVERTED`；状态转移由 fix owner 管理，必须引用对应 `ReplayResult` 才能进入 `VERIFIED` 或 `INEFFECTIVE`。

### 3.3 摄取冲突记录

`IngestionConflict` 用于保存以下异常：

- 同一 source event ID 对应不同 payload hash。
- source 声称的 run/attempt 关系与运行账本冲突。
- 终态冲突或不可解析的事实顺序。
- 同一 grading identity 对应不同分数内容。

冲突状态取 `OPEN | RESOLVED | QUARANTINED`。冲突记录引用双方 payload hash 与证据；冲突解决只能追加 resolution，不能覆盖任一输入。处于冲突中的事实不可进入 `decision_eligible` 知识。

## 4. 身份与关系契约

```text
PipelineRun 1 ── * StageAttempt
PipelineRun 1 ── * FailureRecord
PipelineRun 1 ── * DeductionRecord
GradingRun 1 ── * DeductionRecord

EvidenceRecord * ── * FailureRecord / DeductionRecord / KnowledgeRevision / ReplayResult

FailureRecord  * ── * KnowledgeEntry   (via KnowledgeSourceLink)
DeductionRecord * ── * KnowledgeEntry  (via KnowledgeSourceLink)
KnowledgeEntry 1 ── * KnowledgeRevision
KnowledgeRevision 1 ── * FixRecord
KnowledgeRevision 1 ── * ReplayResult
FixRecord 0..1 ── * ReplayResult
```

引用规则：

1. 所有外部身份先向运行账本校验存在性和归属关系。
2. 事实记录保存写入时的 pipeline、grader、rubric 和词表版本，查询时不回填当前版本。
3. 历史候选、决策或统计必须保存 `knowledge_revision_id`，禁止只保存可漂移的 `current_revision_id`。
4. 物理删除不属于业务 API；依法清除敏感正文时保留 tombstone、hash、清除原因和审计事件。

## 5. 状态与所有者

| 对象/状态 | 唯一状态所有者 | 允许动作 | 禁止动作 |
|---|---|---|---|
| 运行事实与 run 终态 | 运行账本 | collector 只提交引用和观测事实 | grader、知识服务改写 run 事实 |
| `FailureRecord` | failure collector | 创建不可变记录、追加知识关联 | 原地改原因、证据或终态 |
| `DeductionRecord` | grader adapter | 从签名评分结果创建不可变记录 | 改运行事实、覆盖旧评分 |
| `EvidenceRecord` | evidence service | 内容寻址创建、执行访问控制 | 引用方修改正文或权限 |
| `KnowledgeEntry.current_revision_id` | knowledge service | CAS 提交新修订后更新 | collector 直接更新 |
| 根因 `CONFIRMED/REJECTED` | root-cause owner | 基于证据提交修订 | 普通执行 agent 自行确认 |
| `FixRecord` | fix owner | 记录修复生命周期 | 反写知识历史 |
| `ReplayResult` | replay runner | 追加回放事实 | 修改修复或知识结论 |
| `IngestionConflict` | conflict resolver | 追加 resolution、解除或保持隔离 | 删除冲突输入 |

所有状态变化写入不可变 `AuditEvent`：actor、角色、action、object type/id、前置 revision、结果 revision、request ID、时间与理由。

## 6. 写入、并发与时序

### 6.1 事实摄取事务

一次 `ingest-failure` 或 `ingest-deduction` 请求按以下顺序在单事务内执行：

1. 验证调用者角色、schema version 和必填字段。
2. 规范化 payload 并计算 `payload_hash`。
3. 校验 run/attempt/版本归属；无法确认时写冲突隔离，不生成可消费事实。
4. 以唯一幂等键尝试插入。
5. 已存在且 hash 相同：返回既有 ID 和 `idempotent_replay=true`。
6. 已存在且 hash 不同：追加 `IngestionConflict`，返回冲突错误。
7. upsert 内容寻址证据并插入事实到证据的关联。
8. 提交事实与 `AuditEvent`。

事实创建与 canonical 知识归并分两个事务。队列重试通过事实 ID 幂等，避免知识归并失败回滚已接收事实。

### 6.2 canonical 归并事务

1. 基于事实快照和词表版本计算 `canonical_key`。
2. 以 `canonical_key` 唯一约束执行 insert-on-conflict-return-existing。
3. 幂等插入 `KnowledgeSourceLink`。
4. 新 entry 创建 revision 1：状态为 `UNASSESSED`，列出缺失证据。
5. 已有 entry 保持当前修订不变；新来源本身不自动提升置信度或确认根因。

两个 collector 同时提交相同证据或同一问题时，数据库唯一约束决定单一 canonical entry；失败事务读取胜出条目并追加来源关联。实现不得使用先查后写作为唯一互斥手段。

### 6.3 修订提交与并发分支

提交新修订必须携带 `expected_parent_revision_id`：

- 当前修订等于 expected parent：插入 `revision_no + 1`，CAS 更新 `current_revision_id`。
- 当前修订已前进且拟提交内容语义等价：返回已有修订，标记幂等。
- 当前修订已前进且内容不同：保存 `RevisionProposal` 为 `CONFLICTED`，返回 `REVISION_STALE`；不得静默覆盖。
- resolver 可创建一个同时引用冲突 proposal 和当前 revision 的合并修订，`change_reason` 必须说明取舍。

任何推翻初始根因的新证据都创建新修订：旧修订继续可查，旧决策继续引用旧 revision，新查询的 `current_revision_id` 指向新结论。若已确认根因被推翻，新修订使用 `REJECTED` 或新的 `HYPOTHESIS/CONFIRMED`，并触发下游“知识失效”事件供候选系统重新评估。

### 6.4 乱序、迟到与终态后事件

- 以 `occurred_at` 展示业务顺序，以 `recorded_at` 保证审计顺序；禁止用时间戳做幂等键。
- 乱序到达不改变已存事实；服务端通过 source sequence 和运行账本关系生成派生视图。
- run 终态后到达的新失败或证据保留为迟到事实，并记录 `late_after_terminal=true`。
- 迟到事实可以触发新的知识修订；它不能重写 run 终态、已发布结果或旧评分。
- 互斥终态、序列缺口和归属不一致进入冲突隔离，等待 owner 解决。

### 6.5 失败恢复

- 事务提交前崩溃：客户端使用相同幂等键重试。
- 事实已提交、归并任务未完成：outbox 事件重放，联合唯一键保证一次效果。
- 证据 artifact 上传成功、数据库提交失败：后台按 request ID 重试注册；孤儿对象按保留策略回收。
- 数据库提交成功、响应丢失：重试返回原事实 ID。
- schema 或词表暂时不可用：原始请求进入隔离队列，保留 hash 和接收时间，恢复后确定性重放。

## 7. 修订生命周期

```text
事实摄取
  -> canonical entry 创建
  -> revision 1: UNASSESSED
  -> revision N: HYPOTHESIS
  -> revision N+1: CONFIRMED ──> decision_eligible
                       |               |
                       |               -> FixRecord -> ReplayResult
                       |
                       -> 新反证 -> REJECTED 或新 HYPOTHESIS/CONFIRMED
```

生命周期规则：

1. `UNASSESSED -> HYPOTHESIS`：需要候选根因、置信方法、支持依据和缺失证据。
2. `HYPOTHESIS -> CONFIRMED`：需要授权 owner、至少一个可复跑证据、反例检查结果和确认理由。
3. 任意当前结论可通过新修订进入 `REJECTED`；必须引用反证。
4. `REJECTED` 后可基于新证据创建新的 `HYPOTHESIS`，保留完整 parent 链。
5. 修复成功不会自动确认根因；它作为支持证据进入新的知识修订。
6. 回放失败、基础设施错误和无结论分别记录，禁止折叠为同一种失败。
7. canonical 误归并通过新 revision 标记 `SUPERSEDED_BY` 或 `SPLIT_REQUIRED`，随后创建新 entry 并迁移未来消费指针；历史 source links 和决策引用保持不变。

## 8. 查询与消费契约

首版提供以下读取能力：

- 按 `pipeline_run_id` 返回失败、扣分、评分轮次、证据可见摘要和知识 revision 引用。
- 按 `knowledge_entry_id` 返回完整 revision 链、source links、修复与回放结果。
- 按 reason code、stage、pipeline version、root-cause status 和时间范围分页过滤。
- 按 `decision_eligible=true` 获取优化聚合输入，响应固定包含 `knowledge_revision_id`、来源事实 ID 和版本信息。
- 按 grading run 对比重评分，明确展示 rubric/grader 版本和 `supersedes` 链。

权限裁剪发生在服务端：无 grader 权限的调用者只能看到 `GRADER_ONLY` 证据的存在、不可逆 opaque ID 和脱敏摘要，不能看到断言正文、artifact URI 或可推导内容。

统计口径：

- 失败次数按唯一 `failure_id` 计数。
- 扣分次数与分值按唯一 `deduction_id` 和对应 grading run 计数。
- 重评分默认单列；需要“当前评分”视图时选择指定评分策略认可的最新 grading run，历史值仍返回。
- 已确认根因只统计查询时明确选择的 `CONFIRMED` revision；可复现历史报表必须固定 revision 集合和查询参数 hash。
- 一个事实关联多条知识时，事实总量统计去重；问题簇统计按 knowledge entry 分组。

## 9. 实现 checklist

### 9.1 Schema 与迁移

- [ ] 为所有记录定义版本化 schema、枚举和字段校验。
- [ ] 创建事实表、知识 entry/revision 表、source link、evidence、fix、replay、conflict、proposal、audit 和 outbox 表。
- [ ] 添加幂等键、canonical key、revision number、source link 的数据库唯一约束。
- [ ] 添加所有外键和 run/attempt 归属校验适配层。
- [ ] 创建向前迁移和可复跑的迁移验证；迁移失败不留下部分 schema。

### 9.2 写入路径

- [ ] 实现 failure 摄取，覆盖相同重放与 payload 冲突。
- [ ] 实现 deduction 摄取和 grading run/supersedes 关系。
- [ ] 实现证据内容寻址、不可变存储和访问分级。
- [ ] 实现 transactional outbox 与幂等 canonical 归并 worker。
- [ ] 实现 `expected_parent_revision_id` CAS 修订提交和冲突 proposal。
- [ ] 实现修复、回放和知识失效事件的追加写。
- [ ] 实现迟到、乱序和冲突隔离标记。

### 9.3 读取与权限

- [ ] 实现 run 视图、entry 历史视图、重评分对比和 decision-eligible 查询。
- [ ] 所有列表查询使用稳定排序和 cursor 分页。
- [ ] 对 grader-only 字段、摘要和 artifact 下载分别做服务端授权测试。
- [ ] 查询响应返回 schema、词表、pipeline、grader、rubric 和 revision 版本。

### 9.4 可观测性与运维

- [ ] 记录摄取成功、幂等重放、冲突、归并延迟、outbox backlog、修订冲突和证据读取拒绝指标。
- [ ] 日志携带 request ID、事实 ID、run ID 和知识 entry ID；日志不得输出 grader-only 正文。
- [ ] 提供隔离队列重放命令，支持 dry-run、固定输入清单和结果 manifest。
- [ ] 提供一致性检查：孤儿引用、断裂 revision 链、current pointer 漂移、缺失证据和未消费 outbox。

### 9.5 测试

- [ ] 单元测试覆盖规范化 hash、canonical key、状态转移和统计去重。
- [ ] 集成测试覆盖事务回滚、唯一约束、权限和重评分。
- [ ] 使用真实并发执行覆盖相同事实、相同 canonical key 和同 parent 修订竞态。
- [ ] 故障注入覆盖响应丢失、worker 崩溃、artifact/DB 部分失败和词表不可用。
- [ ] 所有验收用例输出机器可读结果、命令、exit code、输入 manifest 和 artifact hash。

## 10. 验收用例

### AC-01：失败、扣分与重评分独立留痕

**GIVEN** run A 的 attempt 失败；run B 正常完成但 grader G1/rubric R1 对断言 Q1 扣分；随后 rubric R2 重评 run B。
**WHEN** 三类结果依次摄取。
**THEN**：

- 存在 1 条 `FailureRecord` 和 2 个 grading run 下的独立 `DeductionRecord`。
- R2 评分通过 `supersedes_grading_run_id` 指向 R1，R1 内容与分数保持原值。
- run A/B 的历史终态不被知识写入或重评分改变。
- 三条事实可各自关联知识，失败与扣分查询计数互不替代。

验证：自动化集成测试。

### AC-02：重复投递幂等

**GIVEN** collector 连续 100 次提交相同 source event ID 和 payload。
**WHEN** 并发度设为 20。
**THEN** 只存在 1 条事实、1 个证据对象、1 条对应 source link；所有成功响应返回同一 ID，无冲突记录。

验证：真实并发数据库测试。

### AC-03：幂等键内容冲突

**GIVEN** 两个请求使用相同 source event ID、不同 payload hash。
**WHEN** 同时提交。
**THEN** 仅一个请求创建事实；另一个产生 `IngestionConflict`，原事实不变，冲突事实不进入 decision-eligible 聚合。

验证：真实并发数据库测试。

### AC-04：相同证据与不同语义

**GIVEN** 一个日志片段同时支持执行失败 F1 和 grader 断言扣分 D1。
**WHEN** 两条事实引用相同内容。
**THEN** 系统保存 1 条 `EvidenceRecord`、独立的 F1/D1 和各自关联；知识归并由 canonical key 决定，证据 hash 本身不会强制合并语义。

验证：自动化集成测试。

### AC-05：并发 canonical 归并

**GIVEN** 两个 collector 同时提交可归一为相同 canonical key 的不同事实。
**WHEN** 两个 outbox 任务并发处理。
**THEN** 只生成 1 个 `KnowledgeEntry`，两条 `KnowledgeSourceLink` 均存在，revision 1 只创建一次且状态为 `UNASSESSED`。

验证：真实并发数据库测试，重复运行至少 50 轮。

### AC-06：根因被新证据推翻

**GIVEN** revision 3 已确认根因 C1，并被决策 P1 引用；新证据反驳 C1。
**WHEN** root-cause owner 提交 revision 4。
**THEN** revision 3、证据和 P1 引用保持可查；revision 4 指向 revision 3，标记 C1 为 `REJECTED` 或提交新结论，current pointer 原子更新，并发消费者收到知识失效事件。

验证：自动化集成测试与审计日志断言。

### AC-07：并发修订无丢失更新

**GIVEN** 两名分析者都以 revision 4 为 parent，分别提交不同 revision。
**WHEN** 请求并发到达。
**THEN** 一个请求成功成为 revision 5；另一个保存为 `CONFLICTED` proposal 并收到 `REVISION_STALE`，current pointer 无覆盖且 revision 链连续。

验证：真实并发数据库测试，交换到达顺序复跑。

### AC-08：未确认根因不进入确认统计

**GIVEN** 一个知识条目处于 `HYPOTHESIS`，具有高 confidence，但仍列出缺失证据。
**WHEN** 查询确认根因聚合和候选输入。
**THEN** 该 revision 在历史查询中可见，`decision_eligible=false`，确认统计和默认候选输入均不包含它。

验证：查询契约测试。

### AC-09：grader-only 隔离

**GIVEN** deduction 引用 grader-only 断言和证据。
**WHEN** grader、知识分析者和执行 agent 分别查询同一 deduction。
**THEN** grader 获得授权内容；知识分析者按其权限获得允许字段；执行 agent 只获得脱敏摘要和 opaque ID；日志、错误和审计事件不泄漏正文。

验证：权限矩阵测试与日志快照扫描。

### AC-10：迟到证据不改写历史终态

**GIVEN** run 已 accepted，随后 collector 提交发生于终态前但晚到的失败证据。
**WHEN** 系统摄取该事件。
**THEN** 事实带 `late_after_terminal=true` 保存并可触发知识修订；run 终态、旧评分和已发布结果保持原值。

验证：集成测试。

### AC-11：部分失败可恢复

**GIVEN** 事实事务成功后 worker 在创建 source link 前崩溃。
**WHEN** outbox 恢复并重复处理消息。
**THEN** 最终存在恰好一个 canonical entry 和一条 source link，无事实丢失、重复 revision 或悬空 outbox。

验证：故障注入测试与一致性检查。

### AC-12：修复与回放保持独立语义

**GIVEN** 同一知识 revision 有一次 `INFRA_ERROR` 回放和随后一次 `PASS` 回放。
**WHEN** fix owner 更新修复状态。
**THEN** 两个 `ReplayResult` 均保留；基础设施错误不计为假设失败；只有引用 PASS 的状态转移可将 fix 标记为 `VERIFIED`，知识确认状态仍需独立修订。

验证：状态机测试。

## 11. 可复跑证据契约

每次验收执行必须生成一个不可变 evidence bundle，至少包含：

```text
evidence/<run-id>/
  manifest.json
  commands.jsonl
  results.json
  junit.xml
  logs/
  db-snapshot-summary.json
  audit-events.jsonl
```

`manifest.json` 必填：

- 代码 commit、工作区 dirty 状态和 schema migration 版本。
- 数据库类型/版本、运行环境、并发参数和随机种子。
- pipeline、reason-code、grader/rubric fixture 版本。
- 执行用例清单、每个输入 fixture 的 SHA-256。
- 开始/结束时间、执行器版本和 evidence bundle 总 hash。

`commands.jsonl` 每行保存精确 argv、工作目录、允许公开的环境变量名、开始/结束时间和 exit code；secret 值必须脱敏。`results.json` 按 AC-ID 保存 pass/fail、断言、实际值和关联 artifact。并发测试必须保存 worker 数、barrier 设置、每个请求结果以及最终数据库基数。

验收命令由实现仓库确定后写入固定脚本；最终交付至少提供以下稳定入口，并让连续两次执行结果一致：

```bash
<test-command> --suite knowledge-lifecycle --seed 20260721
<test-command> --suite knowledge-concurrency --seed 20260721 --repeat 50
<test-command> --suite knowledge-permissions
<consistency-check-command> --fail-on-error
```

交付门槛：所有 AC-01 至 AC-12 通过；并发套件零重复 canonical entry、零丢失 source link、零断裂 revision 链；一致性检查零错误；evidence bundle 可仅凭 manifest 和固定输入在干净环境复跑并得到同一业务结果。

## 12. 完成定义

- Schema、迁移、写入、查询、权限、审计、恢复与一致性检查全部实现。
- 所有事实保持追加写，所有知识结论通过 revision 演进。
- 失败、首次扣分与重评分可独立查询并追溯到 run、版本、断言和证据。
- 重复、乱序、迟到、并发与部分失败均满足本契约的确定性结果。
- 下游只能通过固定 `knowledge_revision_id` 消费已确认知识。
- AC-01 至 AC-12 的可复跑证据齐全，且无 grader-only 内容泄漏。
