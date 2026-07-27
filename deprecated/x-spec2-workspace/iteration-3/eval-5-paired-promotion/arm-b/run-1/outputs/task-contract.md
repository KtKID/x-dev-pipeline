# 配对评测、候选决策与生产晋级任务契约

## 1. 任务定义

### 1.1 目标

交付一个确定性的候选评测与晋级控制面，完成以下闭环：

1. 冻结 baseline、candidate、任务集、执行环境和评分断言为评测 manifest。
2. 为每个案例启动相互隔离且条件一致的 baseline/candidate 配对回放。
3. 区分有效配对、不可比样本、执行失败和 grader 失败，生成逐案例与聚合证据。
4. 按“可比性 → 关键正确性 → 整体正确性 → Token 效率 → 人工审批”的顺序生成晋级或拒绝决定。
5. 通过版本前置条件、幂等键和原子 compare-and-swap（CAS）保证并发晋级只有一个胜者。
6. 保存从生产版本决定到 manifest、run、grader 断言、知识条目和原始证据的完整追溯链。

承接 Requirement：`可比配对回放`、`可审计晋级与回滚`、`正确交付的 Token 效率`、`版本绑定与运行观测`、`意图准确性门禁`、`技术正确性门禁`、`知识驱动的优化依据`。

### 1.2 范围

本任务包含：

- 候选进入正式评测前的资格校验与候选内容冻结。
- 版本化评测 manifest 的创建、规范化、签名/哈希和校验。
- baseline/candidate 配对 run 的调度身份、状态收敛、可比性判断和结果聚合。
- 独立 grader 输入隔离、断言结果采集与评分证据关联。
- 晋级策略的版本化执行，以及 `PROMOTE`、`REJECT`、`INVALID`、`STALE` 四类决策结果。
- 用户审批记录、生产版本原子切换、并发冲突、崩溃恢复和回滚目标记录。
- `delivery_tokens_to_accepted` 与 `evolution_eval_tokens` 的分账和可复跑证据包。
- 覆盖运行期间 baseline、candidate、策略和生产指针变化的状态处理。

### 1.3 范围外

- 候选内容的自动生成或生产 skill 的原地自修改。
- 无人审批的首次生产晋级。
- 模型训练、权重更新、Token 金额换算和可视化控制台。
- 知识库物理存储、组织级权限和跨项目云同步的最终选型。
- 生产执行主流程各阶段契约的全面改造；本任务只消费其稳定运行事实。

### 1.4 显式假设

| A-ID | 假设 | 契约处理 |
|---|---|---|
| A1 | 运行账本已经能追加保存唯一 `pipeline_run_id`、版本、阶段事实、Token、耗时和证据引用 | 本任务通过运行账本接口消费事实；缺失字段令对应样本进入 `INVALID` |
| A2 | baseline 与 candidate 都能解析为不可变版本快照及内容摘要 | manifest 保存版本 ID 和 digest；评测开始后的内容漂移令受影响样本进入 `INVALID` |
| A3 | 每个生产环境只有一个带单调递增 `generation` 的当前版本指针 | 发布使用 `(environment, expected_version, expected_generation)` 执行 CAS |
| A4 | 用户审批可表达审批人、时间、决定、decision digest 和凭证引用 | 审批只绑定一个不可变 decision digest；决定变化后重新审批 |
| A5 | 晋级策略的具体数值阈值由版本化 policy 提供 | 评测结果保存 `policy_id`、`policy_version`、`policy_digest`；缺少阈值时无法形成 `PROMOTE` |
| A6 | grader 断言可提供稳定 ID、版本和规范化摘要 | executor 只获得任务与执行上下文；grader 在独立阶段读取断言正文 |
| A7 | 同一任务允许配置多次重复运行 | `case_id + repetition + manifest_id` 唯一标识一个配对样本，聚合遵循 policy 声明的最小样本数 |
| A8 | 物理持久化可采用事务数据库或加锁的仓库本地实现 | 实现必须提供相同的追加事实、唯一约束、CAS、崩溃恢复和查询语义 |
| A9 | 首版由用户确认每次生产晋级 | `APPROVED` 是生产切换的硬前置条件；审批主体与权限校验由现有宿主机制提供 |

## 2. 核心产物与身份

### 2.1 身份规则

所有 ID 使用全局唯一且稳定的字符串。重新执行会创建新的 run ID，同时通过幂等键关联同一次意图。

| 实体 | 主键 | 唯一约束/关联 |
|---|---|---|
| 候选 | `candidate_id` | 关联 `candidate_version`、`candidate_digest`、至少一个 `knowledge_entry_id` 和一个 `hypothesis_id` |
| Manifest | `manifest_id` | 规范化内容摘要为 `manifest_digest`；相同幂等键与相同摘要返回同一实体 |
| 配对样本 | `pair_id` | `manifest_id + case_id + repetition` 唯一 |
| 单次运行 | `pipeline_run_id` | 每个 pair 分别关联唯一 baseline run 和 candidate run |
| Grading | `grading_id` | `pipeline_run_id + assertion_set_digest + grader_version` 唯一 |
| 聚合结果 | `evaluation_id` | 绑定唯一 `manifest_digest` 和输入事实集合摘要 `result_set_digest` |
| 决策 | `decision_id` | 绑定 `evaluation_id + policy_digest + production_snapshot`，内容摘要为 `decision_digest` |
| 审批 | `approval_id` | 绑定 `decision_id + decision_digest` |
| 发布事务 | `promotion_id` | `decision_id + environment` 唯一，重复请求返回相同终态 |

### 2.2 不可变与派生记录

- 原始 run 事件、命令结果、输入输出指纹、Token、耗时和 grader 原始断言结果采用追加语义。
- manifest 在 `FROZEN` 后保持不可变；任何变更创建新 `manifest_id`。
- evaluation 和 decision 是带输入摘要的派生记录；重新计算创建新修订并保留旧修订。
- candidate 在 `FROZEN` 后由 version + digest 唯一绑定；内容变化创建新候选版本。
- 生产指针的每次切换追加发布事件，保存 previous、next、generation、decision、approval 和回滚目标。

## 3. 评测 Manifest 契约

### 3.1 必填结构

```yaml
schema_version: "1"
manifest_id: evalm-...
manifest_digest: sha256:...
created_at: 2026-07-21T00:00:00Z
created_by: actor-ref

baseline:
  pipeline_version: pv-baseline
  artifact_digest: sha256:...
  release_status: PUBLISHED
candidate:
  candidate_id: cand-...
  pipeline_version: pv-candidate
  artifact_digest: sha256:...
  knowledge_entry_ids: [knowledge-...]
  hypothesis_id: hypothesis-...
  hypothesis: "可证伪陈述"
  target_metrics: [intent_accuracy, technical_correctness, delivery_tokens_to_accepted]
  regression_surface: [contract, routing, verification]

execution:
  model_provider: provider-id
  model_id: exact-model-id
  model_revision: exact-revision
  model_parameters_digest: sha256:...
  repo_sha: full-commit-sha
  toolchain_digest: sha256:...
  permission_profile_digest: sha256:...
  environment_digest: sha256:...
  token_budget: 100000
  time_budget_seconds: 3600
  tool_call_budget: 500
  seed_policy: fixed

grading:
  assertion_set_id: assertions-...
  assertion_set_version: "1"
  assertion_set_digest: sha256:...
  grader_id: grader-...
  grader_version: exact-version
  grader_config_digest: sha256:...
  executor_visibility: hidden

cases:
  - case_id: case-...
    task_snapshot_id: task-...
    task_snapshot_digest: sha256:...
    classification: target|regression|holdout
    priority: P0|P1|P2
    repetitions: 1
    seed: 12345

metrics:
  schema_version: "1"
  token_source: provider_usage
  duration_clock: monotonic
  accepted_definition: intent_and_correctness_and_risk_gate_passed

policy:
  policy_id: promotion-policy-...
  policy_version: "1"
  policy_digest: sha256:...
  minimum_valid_pairs: 1
  required_case_classes: [target, holdout]
```

### 3.2 规范化和哈希

- manifest digest 基于排除 `manifest_digest` 自身后的规范化完整内容计算。
- 规范化固定键顺序、字符编码、时间格式、数值表示和数组排序规则。
- 执行器收到的视图保留 `assertion_set_id/version/digest`，隐藏断言正文、评分权重和发布阈值。
- grader 收到 run 的不可变产物与断言正文，获得只读运行事实访问权。
- baseline 与 candidate 共享同一个 case snapshot、seed、模型、仓库 SHA、工具链、权限、环境、预算和断言摘要。

### 3.3 冻结前校验

manifest 进入 `FROZEN` 需要同时满足：

1. candidate 关联至少一个真实知识条目、一个可证伪假设、目标指标和潜在回归面。
2. baseline 状态为 `PUBLISHED`，版本和 digest 可解析。
3. candidate 状态为 `READY`，版本和 digest 可解析。
4. case 集至少包含目标案例和 policy 要求的 holdout；每个 task snapshot 内容可定位且摘要匹配。
5. 所有可比字段完整；grader 断言集合和 policy 都有稳定版本及 digest。
6. baseline 与 candidate 的执行视图仅在 pipeline 版本和其候选变更范围内存在差异。
7. 预算、重复次数、seed 和提前停止规则已经冻结。

校验失败返回结构化 issue：`code`、`field_path`、`expected`、`actual`、`evidence_ref`。候选保持 `DRAFT` 或 `READY`，完整评测资源保持未分配状态。

## 4. 状态与版本前置条件

### 4.1 Manifest 状态

```text
DRAFT -> VALIDATED -> FROZEN -> RUNNING -> COMPLETED
  |          |           |         |
  +--------> INVALID <---+---------+
                         +-------> CANCELLED
```

- `FROZEN` 固定全部输入及 digest。
- `RUNNING` 只允许追加 pair/run 事实和状态事件。
- 所有 required pair 达到终态后进入 `COMPLETED`；存在不可比 pair 时仍可完成采集，由聚合规则决定 evaluation 结果。

### 4.2 Pair 与 Run 状态

Pair 状态：

```text
PLANNED -> RUNNING -> COLLECTING -> GRADED -> VALID
   |          |            |          +----> INVALID
   |          |            +---------------> FAILED
   |          +----------------------------> CANCELLED
   +---------------------------------------> SKIPPED
```

单侧 run 状态：`CREATED -> RUNNING -> EXECUTOR_COMPLETED -> GRADING -> COMPLETED`，并支持终态 `FAILED`、`INTERRUPTED`、`CANCELLED`。

Pair 进入 `VALID` 需要：

- 两侧 run 都完整记录终态、输入摘要、实际执行上下文摘要和资源使用。
- 两侧的 case、model、repo SHA、toolchain、权限、环境、预算、seed 和 assertion set 相等。
- 两侧 grader 使用同一断言集合和 grader 版本完成全部必需断言。
- 任何预算超限、工具不可用或上下文漂移均作为对称条件被显式记录；单侧环境漂移令 pair 进入 `INVALID`。

执行失败是被测结果时，pair 可以保持 `VALID` 并记录失败差异。评测基础设施故障、证据缺失或可比字段差异产生 `INVALID`。

### 4.3 Candidate 状态

```text
DRAFT -> READY -> FROZEN -> EVALUATING -> EVALUATED -> PENDING_APPROVAL
  |        |        |           |             |              |
  +------> WITHDRAWN            +----------> REJECTED <-------+
                         EVALUATED/PENDING_APPROVAL -> STALE
PENDING_APPROVAL -> APPROVED -> PROMOTING -> PUBLISHED
PROMOTING -> PROMOTION_FAILED
PUBLISHED -> SUPERSEDED
PUBLISHED -> ROLLED_BACK
```

状态所有者：候选构建器负责 `DRAFT/READY`；评测控制面负责 `FROZEN` 至 `EVALUATED/REJECTED/STALE`；审批主体负责 `APPROVED`；发布控制面负责 `PROMOTING/PUBLISHED/PROMOTION_FAILED/SUPERSEDED/ROLLED_BACK`。

### 4.4 Decision 状态

| 状态 | 含义 | 允许后继 |
|---|---|---|
| `CALCULATED` | 已按指定 policy 和 production snapshot 计算 | `PROMOTE_PROPOSED`、`REJECTED`、`INVALID` |
| `INVALID` | 可比样本或证据不足，无法用于晋级 | 新 manifest/evaluation |
| `REJECTED` | 有效评测触发一项拒绝规则 | 新候选版本或新评测 |
| `PROMOTE_PROPOSED` | 全部自动门槛通过，等待用户审批 | `APPROVED`、`DECLINED`、`STALE` |
| `APPROVED` | 用户审批绑定当前 decision digest | `APPLYING`、`STALE` |
| `APPLYING` | 发布事务已取得幂等记录并执行 CAS | `APPLIED`、`CONFLICT`、`FAILED` |
| `APPLIED` | 生产指针切换完成且审计事件持久化 | 终态 |
| `STALE` | baseline、candidate、policy、evidence 或生产快照已变化 | 重新计算 decision |
| `CONFLICT` | 并发发布先改变了生产指针 | 重新基于当前生产版本评测 |

### 4.5 各动作前置条件

| 动作 | 必须满足的版本与状态条件 |
|---|---|
| 启动评测 | manifest=`FROZEN`；baseline 版本/digest 与 manifest 相等；candidate=`FROZEN` 且版本/digest 相等；case、grader、policy 资源可解析 |
| 启动单个 pair | pair=`PLANNED`；该 pair 唯一键尚无运行中实例，或现有实例为同一幂等请求 |
| 聚合结果 | manifest 的 required pair 均终结；有效 pair 数量和分类覆盖可计算；输入事实摘要已冻结 |
| 计算决策 | evaluation 输入摘要有效；policy digest 可解析；生产快照包含当前 version + generation |
| 请求审批 | decision=`PROMOTE_PROPOSED`；decision digest 完整；所有证据引用可读 |
| 应用晋级 | decision=`APPROVED`；approval 绑定同一 digest；candidate digest 未变化；policy digest 未变化；生产 current version/generation 与 decision snapshot 相等 |
| 回滚 | 当前生产版本存在已记录 rollback target；canary 证据触发 policy 回滚条件；回滚事务使用当前 generation 执行 CAS |

## 5. 运行期间状态变化处理

| 变化时点 | 检测 | 状态收敛 | 后续动作 |
|---|---|---|---|
| baseline 在评测期间被其他发布取代 | 订阅/读取生产指针 generation；决策前再次读取 | 已启动 run 继续按冻结快照完成；evaluation 保留；decision=`STALE` | 以新生产版本创建新 manifest 并配对回放 |
| candidate 在评测期间产生新内容 | 比对 candidate version/digest | 当前 manifest 继续绑定旧快照；旧快照缺失时相关 pair=`INVALID` | 新内容创建新 candidate version 和 manifest |
| policy 在评测期间升级 | 比对 policy digest | 已冻结评测按旧 policy 保存；晋级前策略前置条件失败令 decision=`STALE` | 使用新 policy 重算；新 policy 改变 manifest 条件时补跑评测 |
| grader/assertion set 升级 | 比对 assertion digest 和 grader version | 当前 pair 继续绑定旧版本；所需资源无法解析时 pair=`INVALID` | 新断言集合创建新 manifest 或补充独立 evaluation |
| repo、模型、权限或预算发生单侧漂移 | 采集实际执行上下文摘要 | pair=`INVALID`，列出所有差异字段 | 重新运行完整 pair |
| 用户在运行中取消 | 写入取消事件和最后成功阶段 | run=`CANCELLED`，pair=`CANCELLED`；已用 Token 计入 `evolution_eval_tokens` | policy 决定重新排队或结束 manifest |
| grader 暂时失败 | 保存 executor 完整事实和 grader failure | run 保持 `GRADING` 或进入可重试子状态；超过重试上限后 pair=`FAILED` | 使用相同 grader 版本和断言摘要幂等重试 |
| 收集器在 executor 完成后崩溃 | 以 run ID 重放追加事件 | 从最后持久化 checkpoint 恢复；去重事件 | 收敛至单一 run 终态 |
| 审批后证据修订 | decision 输入事实摘要与最新视图对比 | decision=`STALE`，旧 approval 保留审计但失去适用性 | 重算并重新审批 |

## 6. 可比性与聚合规则

### 6.1 可比字段

以下字段逐 pair 完全相等：

- task snapshot ID/digest、case classification、priority、repetition 和 seed；
- model provider/ID/revision/参数摘要；
- repo SHA、toolchain digest、environment digest；
- permission profile、Token/时间/tool-call 预算；
- assertion set ID/version/digest、grader ID/version/config digest；
- metrics schema 与 accepted 定义。

差异报告采用：

```json
{
  "pair_id": "pair-...",
  "status": "INVALID",
  "reason_code": "PAIR_INPUT_MISMATCH",
  "differences": [
    {"field": "execution.repo_sha", "baseline": "...", "candidate": "..."}
  ],
  "baseline_run_id": "run-...",
  "candidate_run_id": "run-...",
  "evidence_refs": ["evidence-..."]
}
```

### 6.2 逐案例结果

每个有效 pair 至少输出：

- baseline/candidate 的 intent gate、technical gate、risk gate、关键不变量与 P0 断言结果；
- 每条 grader assertion 的 expected、actual、passed、severity、score impact 和 evidence refs；
- 执行失败、扣分原因、`detected_stage`、`origin_stage` 和 reason code；
- provider Token 分桶、生产链 Token、评测辅助 Token、耗时、fix 轮数和最终 accepted 状态；
- 差值及方向：质量变化、Token 变化、耗时变化、修复轮数变化。

### 6.3 Token 口径

- `accepted = intent_pass && technical_pass && risk_gate_pass`。
- `delivery_tokens_to_accepted = sum(同一任务全部 dev/verify/QA/fix/重跑 Token) / accepted_task_count`。
- 未 accepted 的运行 Token 保留在生产总消耗中，accepted 分母保持不变。
- grader、collector、评测编排和额外回放成本计入 `evolution_eval_tokens`。
- 评测包同时展示 baseline/candidate 交付 Token、评测辅助 Token、总进化 Token和 provider 分桶；缺失用量携带 `missing_reason`，相关指标状态标记为 `INCOMPLETE`。

### 6.4 提前停止

policy 可以按 `静态契约校验 -> 目标反例 -> 重复目标集 -> 相关回归 -> P0 holdout -> canary` 分层执行。任一关键契约、关键不变量或 P0 门槛失败后：

1. 记录明确拒绝依据和当时已完成层级。
2. 后续高成本层进入 `SKIPPED_BY_POLICY`。
3. 已消耗资源完整计入 `evolution_eval_tokens`。
4. 结果归类为有效 `REJECTED`；基础设施问题归类为 `INVALID`。

## 7. 晋级、拒绝与失效规则

### 7.1 顺序决策算法

决策器固定按以下顺序执行，并保存每一步输入、结果和证据：

1. **资格与可比性**：manifest 有效；有效 pair 数、分类覆盖、重复次数达到 policy；必需指标完整。
2. **目标修复**：candidate 对关联知识条目的全部 required target case 达到 policy 规定结果。
3. **关键硬门槛**：candidate 的系统关键不变量违规数为 0，P0 holdout 回归数为 0。
4. **意图准确性**：candidate 聚合意图准确率达到 baseline 及 policy 下限；关键案例逐例满足 policy。
5. **技术正确性**：candidate 聚合技术正确率达到 baseline 及 policy 下限；错误放行率、失败率、修复轮数满足 policy。
6. **Token 效率**：仅在前述正确性门槛通过后比较 `delivery_tokens_to_accepted`，按 policy 的绝对/相对阈值判断。
7. **审计完整性**：candidate diff、知识、假设、manifest、run、grading、聚合结果、policy 和 rollback target 全部可定位。
8. **用户审批**：生成 `PROMOTE_PROPOSED`，用户签署同一 `decision_digest` 后进入 `APPROVED`。
9. **发布前重验**：再次核对 candidate、policy、证据摘要和 production version/generation，随后执行 CAS。

### 7.2 结果分类

| 结果 | 触发条件 | 生产效果 |
|---|---|---|
| `INVALID` | 输入不可比、样本不足、证据/指标缺失、基础设施故障或 manifest 漂移 | 当前生产版本继续服务；新 pair 或新 manifest 补齐证据 |
| `REJECTED` | 有效评测触发目标修复、关键正确性、整体正确性、Token 或审计门槛 | 当前生产版本继续服务；保存首个阻断项和全部已计算阻断项 |
| `PROMOTE_PROPOSED` | 全部自动门槛通过 | 等待用户审批 |
| `DECLINED` | 用户拒绝晋级 | 当前生产版本继续服务；保存审批意见 |
| `STALE` | 自动决定或审批后，baseline/candidate/policy/evidence/production snapshot 变化 | 基于最新快照重新决策，必要时重跑 |
| `CONFLICT` | CAS 时生产 generation 已改变 | 并发胜者保持生效；本决定进入冲突终态并重新评测 |
| `APPLIED` | 审批有效且 CAS 成功，审计事件完整持久化 | 新任务绑定 candidate；previous version 成为 rollback target |

### 7.3 硬拒绝规则

以下任一条件直接产生 `REJECTED`：

- candidate 出现任一关键系统不变量违规。
- candidate 相对 baseline 出现任一 P0 holdout 回归。
- candidate 的意图准确性或技术正确性低于 baseline，或低于 policy 绝对下限。
- candidate 未修复其声明目标知识案例。
- candidate 的错误放行率、失败率或其他正确性保护指标越过 policy 上限。
- 正确性通过后，Token 效率仍未达到当前 policy 的晋级阈值。

Token 改善只参与第 6 步，无法抵消第 2 至第 5 步的失败。

## 8. 并发、幂等与原子发布

### 8.1 并发评测

- `manifest_id + case_id + repetition` 建立唯一 pair 记录。
- 调度请求携带 `idempotency_key`；相同 key 和相同 payload 返回现有 pair/run，payload 摘要不同返回 `IDEMPOTENCY_CONFLICT`。
- worker 通过带 lease generation 的原子 claim 获取 pair；lease 超时后可重领，旧 worker 的迟到写入按 generation 拒绝。
- run 事件使用 `(pipeline_run_id, sequence)` 去重，终态采用一次性 compare-and-set。
- baseline 与 candidate 可以并行执行；两侧实际上下文均在启动和结束时采集，聚合以事实摘要判断可比性。

### 8.2 并发决策

- evaluation 绑定 `result_set_digest`，新增或修订 run/grading 事实会产生新的 evaluation revision。
- decision 绑定 evaluation、policy 和 production snapshot；同一输入重复计算得到相同语义结果和稳定 digest。
- 多个 worker 可并行计算；唯一约束收敛为一条当前 revision，其余结果作为幂等重放处理。

### 8.3 原子生产晋级

发布事务按以下顺序执行：

1. 以 `decision_id + environment` 创建或读取幂等 promotion 记录。
2. 在同一互斥事务中读取 production pointer。
3. 校验 `current_version == expected_baseline_version` 且 `generation == expected_generation`。
4. 校验 decision/approval/candidate/policy/evidence digest 仍与审批时一致。
5. 追加 `PROMOTION_INTENT`，将 production pointer 切换为 candidate，并把 generation 加一。
6. 追加 `PROMOTION_APPLIED`，记录 previous、next、rollback target、decision 和 approval。
7. 返回唯一 `promotion_id` 和新 generation。

实现需要保证步骤 5 的指针切换与可恢复的发布意图同属一个原子边界。事务数据库可在单事务内提交；文件型实现使用锁、临时记录、原子替换和启动恢复器提供等价语义。

### 8.4 并发结果

- 两个 candidate 同时基于相同 generation 晋级时，首个 CAS 成功；另一个返回 `PROMOTION_CONFLICT` 并进入 `CONFLICT`。
- 同一 decision 的重复请求返回第一次发布结果；生产 generation 只增加一次。
- 进程在指针切换后、完成事件前崩溃时，恢复器读取 `PROMOTION_INTENT` 和实际 pointer，补写完成事件或明确失败事件。
- 任何冲突都保留完整证据；发布控制面不会覆盖较新的生产指针。

## 9. 回滚与 Canary

- `APPLIED` 事件固定记录 previous version/digest/generation 为 rollback target。
- canary run 绑定已发布版本、canary policy 和发布 decision；错误放行率、失败率或 Token 退化达到 policy 门槛后生成回滚决定。
- 回滚也是带 `expected_current_version + expected_generation` 的 CAS 发布事务。
- 回滚成功后，新生产任务绑定上一稳定版本；在途任务继续绑定其启动时的唯一版本。
- canary 运行、触发断言、回滚审批/自动策略依据、指针变更和知识条目保持完整关联。
- 并发新发布先于回滚改变 generation 时，回滚返回冲突并重新读取当前拓扑，避免把更新版本覆盖为更旧目标。

## 10. 实现 Checklist

### T1. 定义领域模型与确定性序列化

- [ ] 定义 manifest、pair、run reference、grading、evaluation、decision、approval、promotion 和 production pointer 模型。
- [ ] 定义所有枚举、合法状态转换、reason code、唯一约束和版本字段。
- [ ] 实现规范化序列化与 digest；为键顺序、数组规则、时间和数值编写固定向量测试。
- [ ] 对应 Scenario：`当前版与候选版条件一致`、`配对输入不可比`。

### T2. 实现 Manifest 构建与冻结校验

- [ ] 校验候选知识来源、假设、目标指标、回归面和版本摘要。
- [ ] 校验任务分类覆盖、重复次数、预算、grader、metrics 和 policy 完整性。
- [ ] 生成 executor-safe view，验证 grader-only 正文和发布阈值无法进入执行上下文。
- [ ] 冻结 manifest 并拒绝原地修改。
- [ ] 对应 Scenario：`候选缺少知识依据`、`当前版与候选版条件一致`。

### T3. 实现 Pair 调度与运行收敛

- [ ] 为 baseline/candidate 创建隔离 run 与共享 pair identity。
- [ ] 实现 idempotency key、唯一 pair、worker lease、generation 和迟到写保护。
- [ ] 捕获启动/结束实际上下文摘要、run 终态、Token、耗时与证据。
- [ ] 实现取消、执行中断、grader 重试和 collector 崩溃恢复。
- [ ] 对应 Scenario：`阶段执行中断`、`当前版与候选版条件一致`。

### T4. 实现可比性校验与配对聚合

- [ ] 逐字段比较任务、模型、repo、权限、预算、环境、seed 和断言摘要。
- [ ] 区分被测执行失败与评测基础设施失败。
- [ ] 输出逐案例质量、失败、扣分、Token、耗时和修复轮数差值。
- [ ] 计算 `result_set_digest`，支持最小有效样本数和 required case class。
- [ ] 对应 Scenario：`配对输入不可比`、`当前版与候选版条件一致`。

### T5. 实现分账指标

- [ ] 按 accepted 定义计算完整生产交付链 Token。
- [ ] 单列 grader/collector/编排成本和本轮总进化 Token。
- [ ] 保存 provider Token 分桶、阶段归属和缺失原因。
- [ ] 覆盖错误运行消耗计入总量且不进入 accepted 分母。
- [ ] 对应 Scenario：`任务经过两轮修复后正确交付`、`低 Token 运行被错误放行检查拦截`、`独立 grader 和 collector 产生评测成本`。

### T6. 实现版本化晋级决策器

- [ ] 按第 7.1 节固定顺序执行门槛并收集全部证据。
- [ ] 区分 `INVALID`、`REJECTED`、`PROMOTE_PROPOSED` 和 `STALE`。
- [ ] 实现分层评测提前停止及 `SKIPPED_BY_POLICY`。
- [ ] 保存 policy 版本/digest、生产快照、decision digest 和 rollback target。
- [ ] 对应 Scenario：`分层评测提前发现失败`、`候选降低 Token 但引入正确性回归`、`候选满足晋级门槛`。

### T7. 实现审批与并发安全发布

- [ ] 审批绑定 decision digest，并在任一输入变化后标记 `STALE`。
- [ ] 实现 promotion 幂等记录、生产 pointer CAS、generation 和发布事件。
- [ ] 实现两个 candidate 并发晋级、同一请求重放和发布中途崩溃恢复。
- [ ] 验证新任务读取新版本，在途任务保持启动版本绑定。
- [ ] 对应 Scenario：`候选满足晋级门槛`。

### T8. 实现 Canary 回滚

- [ ] 绑定 canary run、发布 decision、版本和 rollback policy。
- [ ] 触发阈值后生成回滚证据，通过当前 production generation 执行 CAS。
- [ ] 保存回滚事件与知识条目；覆盖回滚与新发布并发冲突。
- [ ] 对应 Scenario：`Canary 发现生产退化`。

### T9. 提供查询与证据导出

- [ ] 支持按 candidate、manifest、pair、run、decision、promotion 和生产版本双向查询。
- [ ] 导出单一证据包，包含规范化输入、摘要、原始引用、聚合、决策、审批、发布/回滚事件。
- [ ] 提供机器可读 JSON 和稳定人类可读摘要。
- [ ] 对应 Scenario：`一次真实失败驱动候选进化`、`当前没有合格候选`。

## 11. 验收用例

### AC1. 有效配对生成完整差异

- GIVEN 同一 manifest 中 baseline/candidate 的可比字段完全相等，双方完成执行与 grading
- WHEN 聚合该 pair
- THEN pair=`VALID`，结果包含意图、正确性、失败、扣分、Token、耗时、修复轮数及证据引用
- 验证：自动

### AC2. 任一可比字段变化令样本失效

- GIVEN candidate 侧实际 repo SHA 与 baseline 侧不同
- WHEN 聚合 pair
- THEN pair=`INVALID`，reason=`PAIR_INPUT_MISMATCH`，差异精确定位 `execution.repo_sha`，该 pair 不进入晋级统计
- 验证：自动；表驱动覆盖任务、模型、权限、预算、断言和 seed

### AC3. 被测实现失败仍可形成有效 pair

- GIVEN 两侧上下文可比，candidate 执行因自身产物错误失败，运行事实完整
- WHEN grading 和聚合完成
- THEN pair=`VALID`，candidate technical gate 失败，失败原因进入决策证据
- 验证：自动

### AC4. 基础设施失败产生无效样本

- GIVEN candidate worker 丢失工具权限且与 manifest 不符
- WHEN pair 收敛
- THEN pair=`INVALID`，已用 Token 计入 `evolution_eval_tokens`，调度器允许重跑完整 pair
- 验证：自动

### AC5. 运行期间生产 baseline 更新

- GIVEN manifest 绑定 production generation=7，评测期间另一个发布将其更新为 generation=8
- WHEN 当前评测完成并计算/应用决定
- THEN run 与 evaluation 保持可查询，decision=`STALE` 或发布返回 `CONFLICT`，generation=8 的生产指针保持生效
- 验证：自动并发测试

### AC6. 运行期间 candidate 更新

- GIVEN manifest 冻结 candidate digest=A，候选构建器产生 digest=B
- WHEN digest=A 的快照仍可读取
- THEN 当前评测只评价 A；B 获得新 candidate version 和 manifest
- AND WHEN digest=A 的快照已经缺失
- THEN 相关 pair=`INVALID` 并报告 `CANDIDATE_SNAPSHOT_UNAVAILABLE`
- 验证：自动

### AC7. Policy 更新使审批过期

- GIVEN decision 使用 policy digest=P1 并已获审批
- WHEN 发布前当前 policy digest=P2
- THEN decision=`STALE`，旧审批保留审计记录，生产指针保持原 generation
- 验证：自动

### AC8. Token 改善伴随正确性回归

- GIVEN candidate 的 `delivery_tokens_to_accepted` 改善 30%，同时出现一个 P0 holdout 回归
- WHEN 执行晋级决策
- THEN decision=`REJECTED`，首要 reason=`P0_HOLDOUT_REGRESSION`，Token 改善保留为观察指标
- 验证：自动

### AC9. 全部门槛通过后等待审批

- GIVEN 目标案例修复、关键不变量/P0 零回归、意图与技术正确性达到 baseline、Token 达到 policy 阈值
- WHEN 计算决策
- THEN decision=`PROMOTE_PROPOSED`，生产指针保持当前值，证据包包含 rollback target
- 验证：自动

### AC10. 审批绑定不可变决定

- GIVEN 用户审批 decision digest=D1
- WHEN evaluation 修订令最新 decision digest=D2
- THEN D1 的审批无法应用 D2，D2 进入重新审批流程
- 验证：自动

### AC11. 两个候选并发晋级只有一个胜者

- GIVEN candidate A/B 均基于 production version=V1、generation=10 获得有效审批
- WHEN 两个发布事务并发 CAS
- THEN 恰好一个进入 `APPLIED` 并生成 generation=11；另一个进入 `CONFLICT`；最终 production pointer 等于胜者版本
- 验证：自动并发压力测试，重复至少 100 次

### AC12. 同一发布请求幂等重放

- GIVEN 一个 decision 已成功发布
- WHEN 使用相同 idempotency key 重放 10 次
- THEN 返回同一 promotion ID 和 generation，发布事件与 pointer 变更各发生一次
- 验证：自动

### AC13. 发布中途崩溃可恢复

- GIVEN 在写入 `PROMOTION_INTENT` 后的每个持久化边界注入崩溃
- WHEN 重启恢复器
- THEN 系统收敛为一个明确 `APPLIED` 或 `FAILED` 终态，生产 pointer 与审计记录一致，不产生双重 generation 增量
- 验证：自动故障注入

### AC14. 提前停止保留成本和依据

- GIVEN candidate 在目标反例层违反关键契约
- WHEN policy 启用分层提前停止
- THEN decision=`REJECTED`，后续回归/holdout=`SKIPPED_BY_POLICY`，已耗 Token 计入 `evolution_eval_tokens`
- 验证：自动

### AC15. Canary 回滚与新发布并发

- GIVEN version=V2 触发 canary 回滚，同时另一个审批发布尝试改变 production pointer
- WHEN 两个事务并发执行
- THEN CAS 只允许一个事务成功，失败方获得明确 conflict；最终 pointer 对应一条完整可追溯发布事件
- 验证：自动并发测试

### AC16. 证据包可离线复核

- GIVEN 一个 `APPLIED`、一个 `REJECTED` 和一个 `INVALID` 决策
- WHEN 导出各自证据包并在空缓存环境执行复核命令
- THEN 所有 digest 可重算，状态转换合法，聚合指标和决策结果与原记录一致，原始证据引用可定位
- 验证：自动

## 12. 可复跑证据要求

### 12.1 每次实现提交必须附带

- 测试使用的 fixture manifest、baseline/candidate run facts、grading facts、policy 和 production pointer 初态。
- 实际执行命令、退出码、开始/结束时间、代码 SHA、工具版本和环境摘要。
- 单元测试、状态转换测试、表驱动可比性测试、属性测试、并发压力测试和故障注入测试报告。
- 每个命令的 stdout/stderr 原始引用与摘要；摘要携带内容 digest。
- AC1 至 AC16 的用例到测试 ID 映射，任何跳过项包含 owner、原因和解除条件。

### 12.2 最低复跑命令语义

实现应提供仓库内确定性入口，至少支持以下等价命令语义；实际命令名在实现报告中固定：

```text
manifest validate <manifest> --json
manifest freeze <manifest> --json
pair aggregate <manifest> <run-facts> <grading-facts> --json
decision evaluate <evaluation> <policy> <production-snapshot> --json
promotion apply <decision> <approval> --expected-version <v> --expected-generation <n> --json
evidence verify <evidence-bundle> --json
```

所有验证命令在相同输入上产生语义等价的规范化 JSON、digest 和退出码：成功为 0；输入/可比性错误、决策拒绝、状态冲突和系统错误使用稳定且互异的非零退出码。

### 12.3 完成门槛

- AC1 至 AC16 全部通过，包含真实并发和故障注入测试。
- 状态机拒绝所有未声明转换；append-only 原始事实测试证明历史记录保持完整。
- executor 隔离测试证明执行上下文只暴露断言集合摘要，grader-only 正文和发布阈值保持隔离。
- 同一 evidence bundle 在独立进程中重算出相同 manifest、result set 和 decision digest。
- 任一生产版本可查询其 candidate、manifest、pair/run、grading、policy、decision、approval、promotion 和 rollback target。
- 验收报告明确列出 `delivery_tokens_to_accepted`、`evolution_eval_tokens`、有效/无效 pair 数和最终生产 generation。

## 13. Reason Code 最小集合

| 类别 | Reason code |
|---|---|
| Manifest | `MANIFEST_FIELD_MISSING`、`MANIFEST_DIGEST_MISMATCH`、`CANDIDATE_EVIDENCE_MISSING`、`SNAPSHOT_UNAVAILABLE` |
| 可比性 | `PAIR_INPUT_MISMATCH`、`ASSERTION_SET_MISMATCH`、`EXECUTION_CONTEXT_DRIFT`、`METRIC_INCOMPLETE` |
| 运行 | `EXECUTOR_FAILED`、`RUN_INTERRUPTED`、`GRADER_FAILED`、`COLLECTOR_FAILED`、`BUDGET_EXCEEDED` |
| 正确性 | `TARGET_CASE_UNFIXED`、`CRITICAL_INVARIANT_REGRESSION`、`P0_HOLDOUT_REGRESSION`、`INTENT_REGRESSION`、`TECHNICAL_REGRESSION` |
| 效率 | `TOKEN_THRESHOLD_UNMET` |
| 状态 | `ILLEGAL_STATE_TRANSITION`、`STALE_DECISION`、`STALE_APPROVAL`、`IDEMPOTENCY_CONFLICT` |
| 发布 | `PROMOTION_PRECONDITION_FAILED`、`PROMOTION_CONFLICT`、`PROMOTION_RECOVERY_FAILED`、`ROLLBACK_CONFLICT` |

每个失败响应至少包含 `reason_code`、实体 ID、当前状态、期望状态/版本、实际状态/版本、evidence refs 和推荐的确定性下一动作。
