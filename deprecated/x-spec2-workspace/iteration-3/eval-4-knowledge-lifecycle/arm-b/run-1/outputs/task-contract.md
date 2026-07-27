# 失败与扣分知识库：开发任务契约

## 1. 任务目标

实现一个仓库本地、结构化、可查询、可修订的失败与扣分知识库。系统接收 pipeline 阶段失败和独立 grader 扣分，将原始观察、证据、归因、修复、复审与回放结果保存为完整审计链，并为后续问题聚合和候选优化提供稳定输入。

本任务完成后，开发 agent 必须能够证明：

- 每条知识记录关联至少一个真实 `pipeline_run_id` 和一份可定位、带指纹的证据。
- 阶段失败与 grader 扣分使用两个独立记录类型；同一 run 可同时拥有两类记录。
- 原始观察不可变；分类、根因、严重度、处置状态等解释通过追加修订演进。
- 最新视图、任意历史版本和创建某项优化决策时使用的知识版本均可精确查询。
- 重试、并发写入和进程中断不会产生重复记录、丢失已提交记录或半条记录。

对应上游 Requirement：`失败与扣分知识库`、`可定位失败归因`、`知识驱动的优化依据`。

## 2. 范围

### 2.1 包含

- 知识库持久化结构、迁移/初始化、写入接口和查询接口。
- `failure` 与 `grader_deduction` 两类知识记录及各自校验规则。
- run、pipeline 版本、阶段、grader 断言、证据、受影响产物之间的关联。
- 根因推断、原因分类、严重度、处置状态的追加修订模型。
- 修复、复审、回放结果及知识记录间关系的追加记录。
- 并发写入、幂等重试、乐观并发控制和事务边界。
- 当前视图、历史视图、按 run/阶段/reason/status 查询，以及供优化聚合使用的查询。
- 自动化验收测试、可复跑命令和机器可读证据。

### 2.2 排除

- 自动修改生产 skill/template/validator。
- 候选生成、配对回放执行器、晋级审批、canary 和生产回滚本身。
- 通用知识管理、自然语言百科、跨项目云端共享、组织权限和可视化控制台。
- 模型训练、外部 provider 接入和 Token 金额换算。
- 对既有运行事实、grader 原始结果或证据文件的内容改写。

### 2.3 前置依赖

- 上游运行账本提供唯一 `pipeline_run_id`、pipeline 版本、阶段事件、终态和输入输出指纹。
- grader 输出稳定的 grader/rubric 版本、断言 ID、期望、实际、通过状态与评分影响。
- 证据生产者提供可定位 URI/路径及内容指纹；知识库只保存引用和必要摘要。

若前置字段缺失，写入接口必须返回可定位的验证错误，不得用空值或临时字符串代替身份字段。

## 3. 明确假设

1. 首版采用 Python 标准库 SQLite 作为仓库本地持久化后端。原因是首版需要多进程并发、事务、唯一约束、历史查询和确定性测试；数据库路径必须可由配置覆盖，测试使用临时路径。
2. 首版是单仓库、单租户知识库；`pipeline_run_id` 在该仓库的运行账本内全局唯一。
3. run 账本、grader 结果和证据内容由各自生产者持有；知识库存储外键式逻辑引用及指纹，不复制或改写原始事实。
4. `reason_code` 的稳定枚举表由本模块维护并版本化；无法安全归类时使用明确的 `UNCLASSIFIED`，同时要求 `missing_evidence` 与 `next_validation_action`。
5. 时间仅用于展示和审计。修订排序使用单记录内单调递增的 `revision_seq`，不得用客户端时间决定胜者。
6. 所有 ID 使用不可复用的 UUID/ULID 类标识；具体编码可由实现选择，同一字段必须采用一种格式并由校验器验证。
7. 物理清理和保留期延后。本任务中的记录、修订、证据引用和关系均禁止物理删除。

## 4. 领域记录类型

### 4.1 不可变知识锚点 `knowledge_record`

创建后不可更新，最少字段：

| 字段 | 约束 |
|---|---|
| `knowledge_id` | 主键、全局唯一、不可复用 |
| `record_type` | `failure` 或 `grader_deduction` |
| `pipeline_run_id` | 必填，引用真实 run |
| `pipeline_version` | 必填，记录发生时的已绑定或候选版本 |
| `source_identity` | 必填，来源记录稳定身份 |
| `idempotency_key` | 必填且唯一，由记录类型和来源稳定身份确定性生成 |
| `detected_stage` | 必填，问题实际被发现的阶段 |
| `observed_at` | 必填，来源事件发生时间 |
| `created_at` | 必填，知识库接纳时间 |
| `producer` | 必填，写入来源/组件身份 |

`source_identity` 规则：

- `failure`：使用上游阶段失败事件 ID；幂等键至少包含 `failure + pipeline_run_id + source_event_id`。
- `grader_deduction`：使用 grader 结果 ID 与断言 ID；幂等键至少包含 `grader_deduction + pipeline_run_id + grading_result_id + assertion_id`。

### 4.2 失败观察 `failure_observation`

与一个 `knowledge_record(record_type=failure)` 一对一，创建后不可变，最少字段：

- `source_event_id`
- `stage_terminal_status`
- `failure_kind`：进程退出、工具错误、验证失败、契约漂移、中断或受控枚举中的其他值
- `symptom`
- `exit_code` 或明确的 `missing_exit_code_reason`
- `last_successful_stage`，允许无前序成功阶段时为空
- `affected_artifacts[]`
- 至少一个 `evidence_ref`

阶段运行成功时不得创建此类型。后续 grader 扣分使用独立的 `grader_deduction`。

### 4.3 grader 扣分观察 `grader_deduction_observation`

与一个 `knowledge_record(record_type=grader_deduction)` 一对一，创建后不可变，最少字段：

- `grading_result_id`
- `grader_version`
- `rubric_version`
- `assertion_id`
- `expectation`
- `actual_result`
- `assertion_passed=false`
- `score_impact`：数值扣分和计分尺度；无数值分时记录 `severity_impact`
- 至少一个 `evidence_ref`

写入接口必须拒绝 `assertion_passed=true` 的扣分观察。一次正常完成的 run 可拥有零到多条扣分记录，每个失败断言各自形成一条知识记录。

### 4.4 证据 `evidence_ref`

证据引用创建后不可更新，最少字段：

- `evidence_id`
- `uri`：文件路径、报告 URI 或运行账本定位符
- `content_hash`：算法名与摘要值
- `media_type`
- `locator`：行号、JSON Pointer、断言 ID、命令 ID 等可选片段定位
- `captured_at`
- `source_owner`

同一证据可以关联多条知识记录。证据内容变化必须产生新的 `evidence_id` 和指纹；旧引用保持可查。失效或误关联通过追加关系/修订标注，不覆盖旧证据。

### 4.5 知识修订 `knowledge_revision`

每条知识记录在创建事务内同时生成 `revision_seq=1` 的完整解释快照。后续变更追加新快照，最少字段：

- `revision_id`
- `knowledge_id`
- `revision_seq`
- `parent_revision_id`；首版为空
- `reason_code`
- `origin_stage`：问题最早进入证据链的阶段，允许待确认
- `root_cause_status`：`pending`、`confirmed`、`disproven`
- `root_cause_summary`
- `candidate_causes[]`
- `confidence` 与 `confidence_basis`
- `missing_evidence[]`
- `next_validation_actions[]`
- `severity`：稳定枚举，例如 `P0` 至 `P3`
- `knowledge_status`：`active`、`resolved`、`retracted`
- `remediation_status`：`unplanned`、`planned`、`implemented`、`verified`、`failed`
- `affected_artifacts[]`
- `evidence_ids[]`
- `change_reason`
- `author_role`、`author_id`、`created_at`

同一 `knowledge_id` 的 `(knowledge_id, revision_seq)` 唯一。每次修订保存完整快照，使历史读取不依赖可变外部状态。`pending` 根因必须至少包含候选原因或缺失证据，并至少包含一个下一验证动作。`confirmed` 根因必须包含支持证据和置信依据。`disproven` 必须回指推翻依据。

### 4.6 处置与验证事件

修复、复审和回放均使用追加事件，禁止塞入可覆盖的单值字段：

| 类型 | 必填关联与结果 |
|---|---|
| `remediation_event` | `knowledge_id`、修复任务/变更 ID、实现 run、变更指纹、状态、证据 |
| `review_event` | `knowledge_id`、review run、reviewer/grader 版本、结论、证据 |
| `replay_event` | `knowledge_id`、replay run、baseline/candidate 身份、可比性、结果、证据 |

任何修复实现都不能直接证明知识已解决。只有具备通过的复审或有效可比回放证据，归因所有者才能追加 `remediation_status=verified`、`knowledge_status=resolved` 的修订。失败复审或回放追加新事件，并可将记录修订为 `active/failed`。

### 4.7 记录间关系 `knowledge_relation`

关系为不可变追加记录，至少支持：

- `related_to`：失败与扣分等相关现象
- `duplicate_of`：重复知识；被标记项历史仍保留
- `caused_by`：知识间有证据支持的因果关系
- `supersedes`：新知识语义取代旧知识，旧知识仍可查
- `fixed_by`、`validated_by`、`replayed_in`
- `motivates_candidate`：后续优化候选使用的知识版本

关系必须保存 `from_knowledge_id`、`to_identity`、关系类型、创建者、时间、依据证据和创建时使用的 `revision_id`。`failure` 与 `grader_deduction` 可以相互关联，禁止合并成同一记录或通过改类型转换。

## 5. 身份与关联不变量

- 知识库不得自行生成或改写 `pipeline_run_id`、grader 结果 ID、断言 ID 和 pipeline 版本。
- 每条知识记录在提交时必须同时拥有有效 run 关联、至少一个证据引用和首个修订；任一缺失则整笔事务失败。
- `detected_stage` 是不可变观察；`origin_stage` 是可修订归因。例：QA 发现 dev 边界错误时保存 `detected_stage=qa`、`origin_stage=dev`。
- 一个来源事件通过幂等键最多创建一个知识锚点；重放相同请求返回原 `knowledge_id` 和 `revision_id`。
- 相同 run 上的不同失败事件或不同 grader 断言保持独立身份。
- 候选、聚合或决策引用知识时必须固定到具体 `revision_id`，避免最新结论改变历史决策含义。
- 原始观察、证据引用、修订和事件均无 UPDATE/DELETE 业务路径；更正使用新修订或新事件。

## 6. 状态与所有者

| 状态/数据 | 唯一写入所有者 | 允许动作 |
|---|---|---|
| run、阶段事实 | 运行账本 | 知识库只读引用 |
| grader 原始断言 | 独立 grader | 知识库只读引用；grader 无权改写 run 事实 |
| 失败/扣分观察 | knowledge collector | 校验并一次性追加，不做根因确认 |
| reason、origin、root cause、severity、知识状态 | attribution owner（规则引擎或获授权 reviewer） | 基于证据追加修订 |
| 修复事实 | x-fix/修复执行者 | 追加 remediation event，不能自行标记 verified/resolved |
| 复审/回放事实 | verify、QA 或独立 replay/grader | 追加 review/replay event，不能覆盖观察 |
| 当前视图和聚合 | knowledge projector/query 层 | 从已提交追加记录确定性计算，只读 |
| 候选与晋级判断 | 进化控制面 | 读取固定 revision；只能追加关系/决策引用 |

状态转换规则：

1. collector 原子创建锚点、类型观察、证据关联和首个修订，初始 `knowledge_status=active`。
2. attribution owner 可追加 triage/根因修订；证据不足保持 `root_cause_status=pending`。
3. 修复执行者追加 `remediation_event(status=implemented)`；attribution owner据此修订为 `remediation_status=implemented`。
4. 复审或回放生产验证事件。通过且覆盖原反例后，attribution owner才可修订为 `verified/resolved`。
5. 新证据推翻旧判断时，追加修订为 `disproven` 或新的 `pending/confirmed` 结论；历史修订继续可查。
6. 已解决问题复发时追加新观察记录并以 `related_to` 关联旧记录；旧记录可追加 `active` 修订以表达重开，来源事件身份仍各自保留。
7. `retracted` 仅表示记录被证据证明为误报，必须有依据和修订原因；记录及其历史仍参与审计查询，默认聚合可排除该状态。

## 7. 并发、事务与恢复契约

### 7.1 数据库行为

- 启用外键约束；采用 WAL 模式、配置化 busy timeout 和有界重试。
- 创建知识记录的锚点、类型观察、证据引用/关联和首修订必须在一个事务内提交。
- 修订追加在一个事务中完成：检查当前 head、分配下一 `revision_seq`、插入完整快照、提交。
- 数据库约束必须覆盖主键、幂等键、`(knowledge_id, revision_seq)`、类型与观察表匹配、必填关联。应用校验负责跨字段语义，数据库约束负责阻止绕过应用后的明显非法状态。

### 7.2 幂等写入

- ingest 请求必须携带来源稳定身份。相同幂等键和相同 payload 指纹的重试返回既有结果，响应标记 `created=false`。
- 相同幂等键但 payload 指纹不同返回 `IDEMPOTENCY_CONFLICT`，不得覆盖既有记录。
- 进程在提交前退出时事务整体回滚；来源生产者可用同一幂等键重试。
- 进程在提交后、响应前退出时，重试读取并返回已提交记录。

### 7.3 并发修订

- 修订命令必须携带 `expected_head_revision_id`。
- 两个作者基于同一 head 并发修订时，只允许一个事务成功；另一个返回 `REVISION_CONFLICT` 和当前 head，调用者必须读取新 head 后显式重做判断。
- 禁止 last-write-wins、时间戳排序和静默合并根因结论。
- 不同 `knowledge_id` 的写入可并发提交；数据库忙重试耗尽时返回稳定错误，调用者保留原来源事件用于重试。

### 7.4 读取一致性

- `get-current` 返回最高已提交 `revision_seq` 的完整视图及其 `revision_id`。
- `get-history` 按 `revision_seq` 返回全部修订和每次变更依据。
- `get-as-of-revision` 通过精确 `revision_id` 重建当时视图。
- 查询不得展示未提交的观察、孤立证据关联或部分修订。

## 8. 对外能力与错误契约

实现可采用 CLI 或内部 API，必须提供下列等价的确定性能力，并支持 JSON 输入/输出：

- 初始化/迁移知识库。
- 写入阶段失败。
- 写入单条 grader 扣分。
- 追加知识修订，要求 `expected_head_revision_id`。
- 追加证据引用和知识关系。
- 记录修复、复审和回放事件。
- 按 `knowledge_id` 查询 current/history/as-of-revision。
- 按 `pipeline_run_id`、record type、detected/origin stage、reason code、root-cause status、knowledge status、severity 和 pipeline version 过滤。
- 聚合 reason code、责任阶段、失败/扣分次数、严重度、修复轮数和 Token 影响；已确认根因与待确认根因必须分栏，待确认项不得计入“已确认根因”统计。
- 执行全库审计校验，报告孤立引用、序列断裂、类型不匹配和非法状态组合。

稳定错误码至少包括：`VALIDATION_ERROR`、`RUN_REFERENCE_MISSING`、`EVIDENCE_REQUIRED`、`SOURCE_REFERENCE_MISSING`、`IDEMPOTENCY_CONFLICT`、`REVISION_CONFLICT`、`ILLEGAL_STATE_TRANSITION`、`STORAGE_BUSY`、`INTEGRITY_ERROR`。错误结果必须包含字段路径或冲突身份，且不得泄漏 grader-only 规则给执行阶段。

## 9. 实现 checklist

- [ ] 定义并记录 SQLite schema、schema version、迁移入口、约束与索引；数据库位置支持配置覆盖。
- [ ] 实现不可变 `knowledge_record`、两类观察、`evidence_ref`、证据关联、完整快照修订、处置/验证事件和关系表。
- [ ] 为 run、阶段、版本、grader/rubric、断言、证据和受影响产物落实字段校验。
- [ ] 实现 failure ingest，并保证锚点、观察、证据和首修订单事务提交。
- [ ] 实现 grader deduction ingest；每个失败断言独立建档，成功 run 与阶段失败语义解耦。
- [ ] 实现确定性幂等键、payload 指纹、重复成功返回和冲突拒绝。
- [ ] 实现带 `expected_head_revision_id` 的追加修订与 `REVISION_CONFLICT`。
- [ ] 实现根因 `pending/confirmed/disproven` 的字段规则和证据门槛。
- [ ] 实现修复、复审、回放追加事件，以及 verified/resolved 状态门禁。
- [ ] 实现 current、history、as-of-revision 和组合过滤查询。
- [ ] 实现聚合查询；分别显示已确认与待确认根因，保留原始记录追溯列表。
- [ ] 实现不可变保护；业务接口无更新/删除路径，直接非法修改由数据库约束或审计校验捕获。
- [ ] 实现 WAL、busy timeout、有界重试、事务回滚和多进程并发测试。
- [ ] 实现全库审计命令及机器可读错误报告。
- [ ] 为每个自动验收用例提供测试夹具、固定随机种子/时间注入和可复跑命令。
- [ ] 生成开发报告，列出变更文件、schema 版本、命令、退出码、测试摘要和证据路径。

## 10. 验收用例

### AC-01 阶段失败形成完整失败知识

**GIVEN** 一个 verify 阶段失败事件，具有真实 run、pipeline 版本、来源事件 ID、非零退出码、受影响产物和带 hash 的证据
**WHEN** collector 写入失败记录
**THEN** 产生唯一 `failure` 知识 ID；锚点、失败观察、证据关联和首修订全部存在；最新视图含 `reason_code`、现象、严重度、根因状态和后续处置状态。

### AC-02 正常完成 run 的独立 grader 扣分

**GIVEN** run 终态成功，grader 的两个不同 assertion 均为 false
**WHEN** 分别写入两条扣分
**THEN** 产生两个独立 `grader_deduction` 知识 ID，均含 grader/rubric 版本、断言、期望、实际、评分影响和证据；系统不自动创建 failure 记录。

### AC-03 同一 run 同时存在失败与扣分

**GIVEN** 同一 run 有阶段失败事件，也有独立评分的失败断言
**WHEN** 两种来源均被采集
**THEN** 两类记录各自保存并可用 `related_to` 关联；按 run 查询返回两类记录，记录类型和原始身份均未合并。

### AC-04 QA 发现 dev 引入的边界缺陷

**GIVEN** QA 反例证明边界错误由 dev 最早引入
**WHEN** attribution owner 提交有证据的归因修订
**THEN** 当前视图为 `detected_stage=qa`、`origin_stage=dev`，reason code、反例和代码证据可定位；原始 detected stage 保持不变。

### AC-05 证据不足的根因

**GIVEN** spec 歧义、req 拆解和 dev 误解均为合理候选，现有证据无法排除
**WHEN** 提交归因修订
**THEN** 根因保持 `pending`，候选原因、缺失证据、置信依据和下一验证动作均非空；聚合结果不将其计入已确认根因。

### AC-06 新证据修正旧根因

**GIVEN** revision 1 的根因为 pending，revision 2 曾确认 dev，后续回放证据推翻该判断
**WHEN** 基于 revision 2 追加 revision 3
**THEN** current 展示 revision 3 的新判断；history 依序返回三个完整快照与证据；as-of revision 2 仍返回当时确认 dev 的视图。

### AC-07 修复与解决门禁

**GIVEN** 修复任务已实现但尚未复审
**WHEN** 修复执行者记录 implemented 事件
**THEN** 记录不能进入 `verified/resolved`；追加覆盖原反例且通过的 review/replay 事件后，授权归因所有者才能追加解决修订。

### AC-08 幂等重试

**GIVEN** 同一 failure ingest 请求被串行和并发各提交多次
**WHEN** 所有请求结束
**THEN** 数据库只有一个锚点、一个失败观察和一个首修订；每个成功响应返回同一知识 ID；相同幂等键的不同 payload 返回 `IDEMPOTENCY_CONFLICT`。

### AC-09 并发不同记录

**GIVEN** 多个进程同时写入不同来源事件和不同 grader 断言
**WHEN** 写入完成
**THEN** 所有记录完整可查、无 orphan、无 revision seq 冲突；暂时 busy 经有界重试恢复或返回稳定 `STORAGE_BUSY`，重试后不重复。

### AC-10 并发修订冲突

**GIVEN** 两个作者读取同一 current head 并提交不同根因修订
**WHEN** 两个事务并发执行
**THEN** 仅一个创建下一 revision；另一个返回 `REVISION_CONFLICT` 和新 head；历史中无静默覆盖或合并。

### AC-11 进程中断与原子性

**GIVEN** 在插入锚点后、首修订提交前注入故障，以及在事务提交后、响应前注入故障
**WHEN** 调用者使用相同来源身份重试
**THEN** 前一种场景无半条记录且重试完整创建；后一种场景返回既有记录；审计检查为零 orphan/序列断裂。

### AC-12 缺失身份或证据被拒绝

**GIVEN** 写入请求缺少 run、pipeline 版本、来源身份、grader 断言身份或证据
**WHEN** 执行 ingest
**THEN** 返回对应稳定错误和字段路径，数据库行数不变。

### AC-13 不可变审计

**GIVEN** 已存在观察、证据引用和三个修订
**WHEN** 尝试通过业务接口更新/删除历史，随后运行全库审计
**THEN** 修改被拒绝；所有原始记录与历史仍存在；审计结果证明引用完整、修订连续、类型匹配。

### AC-14 精确历史决策追溯

**GIVEN** 候选 C 通过 `motivates_candidate` 引用知识 K 的 revision 2，K 后续产生 revision 3
**WHEN** 查询候选 C 的依据
**THEN** 返回 K revision 2 的完整快照与原证据；current 查询同时可显示 revision 3，二者身份清晰。

### AC-15 查询与聚合

**GIVEN** 多个 run 包含同 reason code、不同责任阶段、confirmed/pending 根因、失败、扣分、修复和 Token 影响
**WHEN** 按 run/类型/阶段/reason/status/version 查询并执行聚合
**THEN** 明细可追溯到原始证据；聚合返回失败数、扣分数、严重度、修复轮数和 Token 影响；confirmed 与 pending 分开显示；retracted 默认排除并可显式包含。

## 11. 可复跑证据要求

开发报告必须记录真实执行的命令，命令名称按仓库测试框架落地，至少覆盖以下证据组：

| 证据组 | 必须证明 | 机器可读产物 |
|---|---|---|
| `schema` | 空库初始化、重复迁移、约束和索引有效 | schema version 与校验 JSON |
| `record-types` | AC-01 至 AC-05 | 测试结果 JSON/XML，失败时含案例 ID |
| `revision-lifecycle` | AC-06、AC-07、AC-14 | current/history/as-of 输出夹具 |
| `concurrency` | AC-08 至 AC-11，多进程重复执行至少一轮 | worker 数、尝试数、成功/幂等/冲突计数 JSON |
| `integrity` | AC-12、AC-13 | 审计结果 `issue_count=0` |
| `query-aggregate` | AC-15 | 固定数据集的查询与聚合 golden JSON |

每条命令须保存：工作目录、完整参数、开始/结束时间、退出码、测试数量、失败数量和产物路径。验收证据必须来自临时数据库或隔离测试数据库，重复执行产生相同业务结果。并发测试不得以单线程 mock 代替；故障恢复测试必须在事务边界注入真实异常。

## 12. 完成定义

- checklist 全部完成。
- AC-01 至 AC-15 全部自动通过，退出码为 0。
- 全库审计报告 `issue_count=0`。
- 测试证明两类记录独立、原始事实不可变、修订可追溯、并发无丢写、重试幂等。
- 开发报告包含实现映射、schema 版本、可复跑命令、真实退出码和机器可读证据路径。
- 所有新增行为限定在本任务范围内，未引入自动生产晋级、自动 skill 修改或 grader 规则向执行阶段泄漏。
