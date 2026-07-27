# 配对评测、候选决策与生产晋级任务契约

## 1. 目标

实现一条可审计、可复跑、支持并发决策的候选晋级链路：

1. 将 baseline 与 candidate 固定到同一评测条件，生成不可变的评测 manifest。
2. 分层执行配对案例，先验证意图与正确性硬门禁，再比较 Token、耗时与修复轮数。
3. 将逐案例事实、聚合结果、人工决定、发布和回滚保存为独立证据。
4. 晋级时以生产版本前置条件执行单一发布；生产基线漂移时停止旧决策并进入重放或重新基准化。
5. canary 与回滚期间，任务创建原子绑定一个路由版本和 pipeline 版本，run 全生命周期保持固定。

完成定义：本契约中的实现项全部完成，自动验收用例通过，每个决策均可由保存的 manifest、原始结果和命令清单离线复算。

## 2. 范围

### 2.1 包含

- 候选登记、证据前置检查与候选状态机。
- 配对评测 manifest 的创建、封存、校验与唯一指纹。
- baseline/candidate 的隔离执行、分层提前停止和逐案例结果记录。
- 条件可比性校验、正确性硬门禁、指标聚合和候选决策包。
- 人工确认、生产版本 compare-and-set、canary 路由、回滚和审计事件。
- 评测期间生产基线变化、两个候选并发晋级、回滚与新任务并发等竞态处理。
- 可复跑命令、输入/输出指纹、日志、版本和决策证据保存。

### 2.2 边界

- 首版由人工确认晋级。
- 首版保存 provider 原始 Token 分桶，不计算金额。
- 候选只能修改 manifest 声明的 pipeline/skill/template/validator 版本集合。
- grader-only 断言仅对 grader 可见；执行身份只能获得公开任务输入。
- 原始运行事实采用追加写；评分、归因和结论通过新修订演进。
- 跨项目云服务、组织权限控制台、模型训练与自动改写生产 skill 延后。

## 3. 显式假设

| A-ID | 假设 | 实现影响 | 验证方式 |
|---|---|---|---|
| A1 | 系统存在可事务写入的持久化存储，并支持唯一约束和 compare-and-set | manifest 封存、状态迁移、生产指针和任务绑定在事务内完成 | 并发集成测试验证唯一约束与 CAS |
| A2 | pipeline、skill、template、validator、模型和代码快照均可用稳定 ID 或内容摘要定位 | manifest 保存 ID 与 digest，复跑时逐项校验 | 篡改单一版本输入后预检失败 |
| A3 | 每个评测执行可使用隔离身份、工作区和记录命名空间 | baseline 与 candidate 互相不可见产物，执行身份不可读 grader-only 断言 | 权限测试与工作区泄漏测试 |
| A4 | grader 可以读取执行结果和 grader-only 断言，但无权修改运行账本事实 | grader 输出作为独立记录追加 | 权限拒绝测试 |
| A5 | 人工审批者身份可验证，审批记录可签名或具备等价的防篡改审计能力 | 晋级操作引用审批记录与决策包摘要 | 审批摘要不匹配时发布失败 |
| A6 | 同一评测案例允许 baseline 与 candidate 使用相同确定性种子；外部不确定依赖可被快照、桩化或记录 | 可比性检查覆盖种子、依赖快照和执行环境 | 重复执行一致性测试 |
| A7 | 生产路由读取一个单调递增的 `routing_epoch` 与当前 pipeline 版本 | 路由切换和新任务版本绑定可原子化 | 回滚/创建并发测试 |
| A8 | `pipeline_run_id` 在全系统唯一；同一用户任务返工使用同一 run 的新 `stage_attempt` | 评测每个 arm execution 也获得独立 run，并关联同一 pair | 唯一性与 attempt 关联测试 |
| A9 | P0、关键不变量、意图门禁和技术正确性门禁的判定规则可版本化 | manifest 固定 gate policy 和 rubric/断言版本 | 政策漂移测试 |
| A10 | 原始 Token 计量包含 provider、模型、输入、缓存输入、输出及其他 provider 分桶 | 效率聚合可复算且不混入进化成本 | 账单字段完整性测试 |

## 4. 核心实体与唯一性约束

| 实体 | 必填标识 | 关键约束 |
|---|---|---|
| `candidate` | `candidate_id` | 关联 `baseline_version_id`、知识条目修订、可证伪假设、修改范围、回滚目标 |
| `evaluation_manifest` | `evaluation_id`, `manifest_digest` | 封存后不可变；相同 canonical 内容得到相同 digest |
| `pair_case` | `(evaluation_id, case_id)` | 每个案例恰有 baseline/candidate 两个 arm 定义 |
| `arm_execution` | `(evaluation_id, case_id, arm, attempt_no)` | 每次执行绑定唯一 `pipeline_run_id`；重试递增 attempt，旧事实保留 |
| `case_result` | `(evaluation_id, case_id, result_revision)` | 引用两个 arm 的输出与 grader 结果；修订追加保存 |
| `decision_package` | `decision_id`, `package_digest` | 固定引用 manifest、结果修订集合、聚合器版本和生产版本快照 |
| `approval` | `approval_id` | 引用精确 `package_digest`；记录 actor、时间、决定和理由 |
| `pipeline_release` | `pipeline_version_id` | 不可变版本对象；发布状态与生产指针分离 |
| `production_pointer` | 单例逻辑键 | 保存 `current_version_id`、`routing_epoch`，通过 CAS 更新 |
| `routing_binding` | `pipeline_run_id` | 任务创建事务中绑定 `routing_epoch` 与 `pipeline_version_id`；之后不可改 |
| `audit_event` | `event_id` | 追加写；重复 `event_id` 幂等；冲突 payload 进入隔离 |

所有时间保存 UTC；所有摘要使用明确的算法字段，例如 `sha256:<hex>`；canonical JSON 使用固定字段排序和编码规则。

## 5. 评测 manifest 契约

### 5.1 必填结构

```yaml
schema_version: paired-eval-manifest/v1
evaluation_id: eval-<unique>
candidate:
  candidate_id: cand-<unique>
  candidate_version_id: pv-<immutable>
  candidate_artifact_digest: sha256:<hex>
  baseline_version_id: pv-<immutable>
  baseline_artifact_digest: sha256:<hex>
  rollback_target_version_id: pv-<immutable>
  knowledge_refs:
    - knowledge_id: <id>
      revision: <integer>
  falsifiable_hypothesis: <text>
  declared_change_scope: [<immutable artifact ref>]
evaluation_conditions:
  repository_snapshot: <commit-or-content-addressed-snapshot>
  task_set_version: <immutable id>
  case_ids: [<stable id>]
  model:
    provider: <name>
    model_id: <id>
    model_revision: <revision-or-digest>
    parameters: <canonical map>
  permissions_profile_id: <immutable id>
  execution_image_digest: sha256:<hex>
  toolchain_versions: <canonical map>
  dependency_snapshot_digest: sha256:<hex>
  budget:
    token_limit: <integer>
    wall_time_limit_ms: <integer>
    max_stage_attempts: <integer>
  seeds:
    default: <integer>
    per_case: <case-id-to-seed map>
  gate_policy_version: <immutable id>
  grader:
    grader_version: <immutable id>
    rubric_version: <immutable id>
    public_assertions_digest: sha256:<hex>
    private_assertions_digest: sha256:<hex>
  metrics_policy_version: <immutable id>
  retry_policy_version: <immutable id>
  early_stop_policy_version: <immutable id>
  ordering_policy: <fixed-or-seeded-random definition>
isolation:
  baseline_identity: <id>
  candidate_identity: <id>
  baseline_workspace: <namespace>
  candidate_workspace: <namespace>
  grader_identity: <id>
production_snapshot:
  current_version_id: pv-<immutable>
  routing_epoch: <integer>
created_by: <actor id>
created_at: <UTC timestamp>
sealed_at: <UTC timestamp>
manifest_digest: sha256:<canonical manifest excluding this field>
```

### 5.2 封存前校验

- candidate 的 `baseline_version_id` 等于创建时 `production_snapshot.current_version_id`。
- baseline 与 candidate 的任务、模型、参数、代码快照、权限、预算、工具链、依赖、grader、断言、种子、重试和提前停止策略一致；唯一允许差异为 `declared_change_scope` 覆盖的候选版本产物。
- 所有引用均可解析为不可变对象，digest 校验成功。
- `case_ids` 非空、无重复，并包含每个案例的稳定输入指纹。
- 候选已关联至少一个知识条目修订、一个可证伪假设、目标指标和回归面。
- baseline/candidate 工作区与身份不同，grader 身份独立。
- grader-only 断言摘要进入 manifest，断言内容保持 grader 权限边界。

封存操作在单事务内完成，状态从 `DRAFT` 迁移到 `SEALED`，写入 `manifest_digest` 与审计事件。任何封存后的字段变化创建新 `evaluation_id`。

## 6. 状态机与版本前置条件

### 6.1 候选状态

`DRAFT -> READY -> EVALUATING -> EVALUATED -> DECISION_PENDING -> APPROVED -> RELEASING -> CANARY -> PROMOTED`

拒绝/失效路径：

- `DRAFT|READY -> BLOCKED_EVIDENCE`：知识、假设、范围或回滚目标缺失。
- `EVALUATING -> EVAL_FAILED`：基础设施失败耗尽重试，或结果完整性无法恢复。
- `EVALUATING|EVALUATED -> REJECTED`：硬门禁、可比性或晋级阈值失败。
- `DECISION_PENDING|APPROVED -> BASELINE_STALE`：生产指针已偏离 manifest baseline。
- `RELEASING|CANARY -> ROLLED_BACK`：发布失败或 canary 回滚条件触发。

每个状态迁移要求 `expected_state` CAS，并追加包含 actor、旧状态、新状态、原因、引用摘要和时间的审计事件。重复同一迁移请求返回原结果；同一幂等键携带不同 payload 进入冲突隔离。

### 6.2 评测状态

`DRAFT -> SEALED -> RUNNING -> RESULTS_COMPLETE -> AGGREGATED -> CLOSED`

终止分支为 `EARLY_STOPPED`、`INVALID_COMPARISON`、`INFRA_FAILED`。终止状态仍需保存已消耗资源、已完成案例和停止依据。

### 6.3 发布版本前置条件

从 `APPROVED` 进入 `RELEASING` 前必须同时满足：

1. approval 引用当前 `package_digest`，批准身份有效。
2. decision package 引用的 manifest、case result 修订和聚合器版本全部可解析且摘要一致。
3. `production_pointer.current_version_id == manifest.candidate.baseline_version_id`。
4. `production_pointer.routing_epoch == decision_package.expected_routing_epoch`。
5. candidate artifact 与已评测摘要一致，发布内容处于 `declared_change_scope`。
6. 回滚目标可用并通过最低健康校验。
7. 同一 `candidate_id + package_digest` 尚无成功发布记录。

生产切换使用事务性 CAS：

```text
CAS(
  expected = {current_version_id: V1, routing_epoch: E},
  update   = {current_version_id: V2, routing_epoch: E + 1}
)
```

CAS 成功后创建唯一 release 记录并进入 canary；CAS 失败返回 `BASELINE_STALE`，保存观察到的当前版本与 epoch。

## 7. 配对执行与结果聚合

### 7.1 执行顺序

每个案例按 manifest 的固定或 seeded 顺序执行。baseline 与 candidate 可以并行运行；两者使用独立工作区、身份和账本。每个 arm 记录：

- `pipeline_run_id`、stage attempt、开始/结束时间和终态。
- 所有版本、输入/输出/工作区快照摘要。
- provider 原始 Token 分桶、耗时、修复轮数和提前停止点。
- deterministic verify 结果、意图检查结果、grader 断言结果和证据 ID。
- 基础设施错误与产品错误分类、重试依据和重试 attempt。

只有 manifest 中的版本化 retry policy 允许重试。配对重试规则需对两个 arm 对称；单臂基础设施失败时，策略可重跑该臂，同时把 attempt 差异标记进可比性报告。产品错误直接形成案例事实。

### 7.2 分层门禁

按以下顺序执行并保存每层结果：

1. 静态结构与版本完整性校验。
2. 目标反例、关键不变量与 P0 回归。
3. 用户意图准确性和实现技术正确性。
4. 公开契约、边界、并发、状态转换和失败恢复用例。
5. 全量 holdout 回放。
6. 仅对通过以上门禁的结果计算 Token、耗时和修复轮数差异。

候选在任一硬门禁失败时按 manifest 的提前停止策略结束后续评测。已经执行的 baseline/candidate 事实和 `evolution_eval_tokens` 全量保留。

### 7.3 可比性判定

聚合前生成 `comparability_report`。以下条件全部成立时状态为 `COMPARABLE`：

- manifest 摘要在整个执行期一致。
- 两个 arm 使用相同任务输入、模型修订与参数、仓库快照、权限、预算、种子、依赖和工具链。
- grader/rubric/断言版本相同。
- 所有必需案例均存在可验证的双臂终态，或提前停止策略给出完整且对称的裁剪依据。
- 基础设施异常处理符合 retry policy，异常未造成单臂额外信息、权限或预算优势。
- 结果摘要、日志摘要与账本引用完整。

任何条件失败产生 `INVALID_COMPARISON`；对应结果可用于诊断，不能进入晋级证据。

### 7.4 指标

正确性指标至少包含：意图门禁、技术正确性、关键不变量、P0/P1 回归、逐案例通过率和错误放行数。

效率指标仅在正确性合格集合上计算：

```text
delivery_tokens_to_accepted =
  sum(dev + verify + qa + fix + production_rerun tokens across all evaluated runs)
  / accepted_delivery_count
```

`evolution_eval_tokens` 单列 baseline/candidate 评测、grader 和 collector 消耗。报告同时提供总量、每案例配对差、分位数、阶段/attempt 下钻和缺失计量标记。

## 8. 晋级、拒绝与重新基准化规则

### 8.1 可进入人工决策的条件

以下条件全部满足，候选进入 `DECISION_PENDING`：

- `comparability_report.status == COMPARABLE`。
- candidate 通过全部意图、技术正确性、关键不变量和 P0 硬门禁。
- candidate 的错误放行数为零。
- candidate 相对 baseline 满足 manifest 固定的质量非退化阈值。
- candidate 达到 manifest 固定的目标收益阈值；收益可来自质量提升，或质量达标后的 Token/耗时/修复轮数改善。
- 所有案例、Token 分桶、日志、摘要和审计引用完整。
- decision package 已生成并通过离线复算。

人工决定只引用一个精确 `package_digest`，决定值为 `APPROVE` 或 `REJECT`，并记录理由。

### 8.2 直接拒绝条件

任一条件触发 `REJECTED`：

- candidate 违反关键不变量或出现 P0 回归。
- 用户意图或技术正确性硬门禁失败。
- grader-only 断言泄漏、身份/工作区隔离失效或运行事实被改写。
- 候选产物超出声明修改范围。
- 正确性相对 baseline 低于允许阈值。
- 必需证据缺失且无法由当前 immutable 输入恢复。

可比性失败使用 `INVALID_COMPARISON`，基础设施耗尽重试使用 `INFRA_FAILED`；两者均关闭当前决策包，保留诊断证据。

### 8.3 生产基线变化

评测期间生产版本变化不会改写 manifest 或已采集结果。聚合继续针对 manifest 固定 baseline 完成。发布前发现当前生产版本与固定 baseline 不同，候选进入 `BASELINE_STALE`，选择以下一种新流程并记录理由：

1. **重放**：创建新 evaluation，使用当前生产版本作为 baseline，保持候选内容摘要；在新的完整 manifest 下重新运行所需案例。
2. **重新基准化**：当版本化政策明确允许复用未受影响的 immutable 案例结果时，创建新 evaluation 和新 decision package；复用项逐条列出等价性证明，其余案例重跑。

旧结果继续可查，只作为旧 baseline 下的历史证据。审批不能跨 package digest 复用。

### 8.4 两个候选并发晋级

两个候选均基于 V1 通过评测时，二者可进入人工批准。发布阶段均以 `{V1, epoch E}` 为预期执行 CAS：第一个成功者更新生产指针；第二个收到 `BASELINE_STALE`，保留其批准和评测历史，并进入重放或重新基准化。任意时刻生产指针只引用一个当前版本。

### 8.5 Canary 与回滚

- canary policy 版本、流量比例/选择规则、观察窗口、健康指标和回滚阈值进入 release 记录。
- 新任务创建在一个事务中读取 `{routing_epoch, current_version_id}`、按 canary 规则选定版本、创建 `pipeline_run_id` 并写入不可变 `routing_binding`。
- 已创建 run 在 canary 扩容、停止或回滚后继续使用原绑定版本。
- 回滚通过 production pointer CAS 切到 `rollback_target_version_id` 并递增 `routing_epoch`。
- 回滚提交后的新任务全部使用新 epoch 下的回滚目标；事务重试处理切换瞬间的创建冲突。
- 失败 release 保留，回滚创建独立审计事件和原因证据。

## 9. 实现 checklist

### T1. 数据模型与存储约束

- [ ] 建立第 4 节实体、外键、不可变字段和唯一约束。
- [ ] 为 manifest、case result、decision package 和 release 实现 canonical serialization 与 digest 校验。
- [ ] 原始事实表采用追加写；修订表显式保存 `supersedes_revision`。
- [ ] 对 `event_id`、执行 attempt、approval 和 release 幂等键建立唯一索引。
- [ ] 为候选、评测和发布状态迁移实现 `expected_state` CAS。

### T2. 候选登记与 manifest

- [ ] 校验知识条目、可证伪假设、基线、目标指标、回归面、修改范围和回滚目标。
- [ ] 从生产指针读取版本与 epoch，生成完整 manifest。
- [ ] 校验全部 immutable 引用和 baseline/candidate 条件对称性。
- [ ] 封存 manifest 并阻止原地修改；变化创建新 evaluation。
- [ ] 建立执行身份、工作区和 grader-only 权限隔离。

### T3. 配对执行器

- [ ] 按 manifest case 顺序和种子启动双臂运行，为每次执行分配唯一 run ID。
- [ ] 记录 stage attempt、输入/输出摘要、测试证据、Token、耗时、修复轮数和终态。
- [ ] 实现版本化 retry 与 early-stop policy，区分基础设施错误和产品错误。
- [ ] 对重复事件幂等归并，对冲突 payload 隔离，对迟到证据创建修订关联。
- [ ] 每层门禁结束后持久化 checkpoint，支持中断恢复且避免重复计费遗漏。

### T4. Grader 与聚合器

- [ ] 独立运行 grader，限制其对账本事实的写权限。
- [ ] 生成逐案例双臂结果和 `comparability_report`。
- [ ] 硬门禁先于效率比较；正确性未达标时跳过晋级效率结论。
- [ ] 计算原始 Token 分桶、accepted 归一化生产 Token 和独立 evolution Token。
- [ ] 生成包含 immutable 引用与摘要的 decision package，并提供离线复算命令。

### T5. 决策与发布

- [ ] 实现绑定 `package_digest` 的人工批准/拒绝记录。
- [ ] 发布前重新校验 approval、摘要、产物范围、回滚目标、生产版本和 epoch。
- [ ] 通过 production pointer CAS 实现唯一晋级，返回稳定错误码 `BASELINE_STALE`。
- [ ] CAS 成功后创建唯一 release 与 canary 配置；重复请求返回已有 release。
- [ ] 为 stale candidate 实现新 evaluation 的重放/重新基准化入口。

### T6. Canary、任务绑定与回滚

- [ ] 原子实现任务 ID、run ID、routing epoch 和 pipeline version 绑定。
- [ ] 保证绑定后全 run 固定版本，包括返工 stage attempt。
- [ ] 通过 policy 触发自动停止/回滚，并保留人工回滚入口和 actor。
- [ ] 回滚使用 CAS、递增 epoch，并校验目标健康与 artifact digest。
- [ ] 实现任务创建和回滚并发重试，消除未绑定与混合版本 run。

### T7. 审计与可复跑证据

- [ ] 提供按 candidate/evaluation/run/decision/release 查询的证据索引。
- [ ] 保存所有命令参数、环境摘要、工具版本、退出码、日志摘要与 artifact URI。
- [ ] 提供 manifest 校验、案例复跑、聚合复算、决策包校验和发布历史查看命令。
- [ ] 输出机器可读 JSON 结果和稳定错误码。
- [ ] 加入事实不可变、权限隔离、摘要篡改和审计完整性测试。

## 10. 验收用例

### AC1. 条件一致的配对评测成功

- GIVEN 已登记 candidate C2，生产为 V1，manifest 固定相同任务、模型、仓库、权限、预算、grader 和种子。
- WHEN 执行全部双臂案例并聚合。
- THEN comparability 为 `COMPARABLE`；逐案例结果可定位两个 run；硬门禁先于效率结论；decision package 可离线复算出相同 digest 和指标。

### AC2. manifest 封存后被修改

- GIVEN evaluation 已处于 `SEALED`。
- WHEN 请求修改模型参数、预算或案例集合。
- THEN 原 evaluation 保持不变；系统要求新建 evaluation；原 digest 与审计事件可验证。

### AC3. grader-only 断言隔离

- GIVEN 执行身份运行 baseline 和 candidate。
- WHEN 执行身份读取 private assertions，或 grader 修改 arm 运行事实。
- THEN 权限层拒绝操作并记录安全事件；当前 evaluation 标记不可用于晋级。

### AC4. 关键不变量提前失败

- GIVEN candidate 在目标竞态反例中产生重复提交。
- WHEN 分层门禁执行到关键不变量层。
- THEN candidate 进入 `REJECTED`，后续全量回放停止；已消耗资源完整计入 `evolution_eval_tokens`；最小复现与证据进入结果包。

### AC5. 单臂基础设施失败与重试

- GIVEN candidate arm 遇到 manifest 定义的可重试基础设施错误。
- WHEN 执行器重试并在上限内成功。
- THEN 新 attempt 保留旧 attempt，Token 与耗时均计入；comparability report 明确重试差异并按 policy 判断可比性。

### AC6. 非对称条件造成不可比

- GIVEN candidate 实际模型修订或权限 profile 与 manifest/baseline 不同。
- WHEN 聚合器校验执行事实。
- THEN evaluation 进入 `INVALID_COMPARISON`；系统不生成可批准的晋级结论；差异字段和证据被保存。

### AC7. 评测期间基线漂移

- GIVEN C2 固定 baseline V1 开始评测，期间生产指针切换到 V3。
- WHEN C2 完成聚合并申请晋级。
- THEN旧评测仍以 V1 完成并保存；发布前置检查返回 `BASELINE_STALE`，记录 V3 与当前 epoch；新评测选择重放或带等价性证明的重新基准化。

### AC8. 两个候选并发发布

- GIVEN C2 与 C3 都基于 `{V1, epoch 10}` 获批。
- WHEN 两个发布请求并发执行 CAS。
- THEN 恰好一个请求成功并把 epoch 更新为 11；另一个返回 `BASELINE_STALE`；生产指针始终指向一个完整版本；两个决策历史均可查。

### AC9. 重复发布请求

- GIVEN C2 已用某 package digest 成功创建 release。
- WHEN 相同幂等键重复提交。
- THEN 返回同一 release，不重复递增 epoch、不重复创建 canary；不同 payload 使用同一幂等键时进入冲突隔离。

### AC10. Canary 回滚与新任务并发

- GIVEN V2 正在 canary，production pointer 为 `{V2, epoch 21}`，回滚目标为 V1。
- WHEN 回滚 CAS 与 100 个新任务创建并发发生。
- THEN 每个任务原子绑定 `{epoch 21, V2}` 或 `{epoch 22, V1}`；不存在空绑定、同一 run 多版本或 epoch/version 交叉组合；已有 V2 run 继续使用 V2。

### AC11. 回滚 CAS 竞争

- GIVEN V2 canary 同时收到自动回滚与人工回滚请求。
- WHEN 两者使用相同预期版本和 epoch 执行。
- THEN 一个请求完成指针切换，另一个幂等收敛到已完成回滚或得到稳定 stale 结果；epoch 只递增一次；审计记录两个请求及最终所有者。

### AC12. 迟到证据与评分修订

- GIVEN evaluation 已关闭，随后到达一个有效迟到日志，且新版 rubric 对旧 run 重评分。
- WHEN 系统接收两者。
- THEN 原始终态与旧评分保持不变；迟到日志和新评分分别形成修订；任何新晋级决定引用新的 package digest 与明确结果修订集合。

### AC13. Token 归一化

- GIVEN案例 A 经两轮 fix 后通过，案例 B 消耗较低但正确性失败。
- WHEN 计算生产效率。
- THEN A/B 的 dev、verify、QA、fix 与重跑 Token 都进入分子；只有 A 进入 accepted 分母；grader/collector Token 单列；结果可下钻到 stage attempt。

### AC14. 候选超出声明范围

- GIVEN candidate 评测 artifact 包含 declared change scope 外的修改。
- WHEN 发布预检比较 artifact 清单与 manifest。
- THEN 候选被拒绝，生产指针不变，差异清单进入审计证据。

### AC15. 中断恢复

- GIVEN执行器在案例完成并写 checkpoint 后崩溃。
- WHEN 相同 evaluation 恢复。
- THEN 已完成 arm 不被隐式重跑；未完成工作按 retry policy 创建新 attempt；所有实际消耗和终态完整可复算。

## 11. 可复跑证据包

每个 evaluation 输出一个内容寻址证据包，至少包含：

```text
evidence/<evaluation_id>/
  manifest.json
  manifest.sha256
  comparability-report.json
  cases/<case_id>/baseline/<attempt_no>/run-ref.json
  cases/<case_id>/candidate/<attempt_no>/run-ref.json
  cases/<case_id>/result-<revision>.json
  aggregate.json
  decision-package.json
  decision-package.sha256
  approvals/<approval_id>.json
  releases/<release_id>.json
  audit-events.jsonl
  commands.json
```

`commands.json` 保存以下逻辑命令及完整参数；具体 CLI 名称由实现统一确定：

1. `manifest verify <manifest>`：校验 schema、引用、digest、封存状态和条件对称性。
2. `eval run --manifest <manifest> [--case <id>]`：按固定输入执行完整评测或单案例复跑，产出新的 run/attempt 记录。
3. `eval aggregate --manifest <manifest> --results <refs>`：生成 comparability report、aggregate 和 decision package。
4. `decision verify <package>`：离线复算结果集合、指标与 package digest。
5. `release promote --package <digest> --approval <id> --expected-version <id> --expected-epoch <n>`：执行发布前检与 CAS。
6. `release rollback --release <id> --expected-version <id> --expected-epoch <n>`：执行可审计回滚。

复跑验收要求：在 manifest 所有 immutable 引用仍可用时，manifest 校验结果一致；确定性用例结果一致；聚合指标和 decision package digest 一致。外部不确定输入通过记录的快照或桩复现。任何差异输出字段级 diff、运行环境摘要和新的 run ID，原证据包保持不变。

## 12. 交付门禁

- [ ] AC1-AC15 全部形成自动测试，其中 AC7-AC11 使用真实并发控制与事务边界。
- [ ] 压测证明并发发布最多一个成功者，任务创建在路由切换下保持版本绑定不变量。
- [ ] 故障注入覆盖 manifest 封存、arm checkpoint、聚合、发布 CAS、canary 和回滚各阶段。
- [ ] 权限测试证明执行身份无法读取 grader-only 断言，grader 无法改写运行事实。
- [ ] 所有状态迁移、拒绝、stale、重放、晋级和回滚均有稳定错误码与审计事件。
- [ ] 从证据包可离线复算 comparability、硬门禁结论、指标与 package digest。
- [ ] 操作文档明确人工审批、基线漂移处理、canary 观察和回滚步骤。

最终发布推荐采用“小比例 canary + 自动健康阈值回滚 + 人工扩大流量”，并以生产版本 CAS 和任务创建原子绑定作为上线硬前置。
