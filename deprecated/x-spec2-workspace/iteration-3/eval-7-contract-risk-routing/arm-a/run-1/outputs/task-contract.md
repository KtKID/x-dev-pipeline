# 阶段契约一致性与风险路由校准：开发任务契约

## 1. 目标

实现一套可审计的阶段边界与风险路由最小闭环，使 `x-spec2 -> x-req2 -> x-dev -> x-verify -> x-qa-gate -> x-fix` 中的每次阶段交接都能回答：

1. producer 产出了什么、依据哪个契约版本、内容是否完整；
2. consumer 接受了什么、支持哪些契约版本、是否发生漂移；
3. 当前任务为何进入某个执行 profile，该决策绑定哪个策略版本；
4. 轻量路径被影子 QA 击穿后，反馈如何形成可回放证据并校准下一版策略；
5. 任一关键契约、路由绑定或高风险门禁异常如何阻止继续执行。

完成后，阶段交接、漂移判定、路由决策和校准结果均可由稳定 ID、结构化记录和固定输入复跑。

## 2. 范围与裁剪

### 2.1 本任务包含

- 版本化阶段契约注册表，以及 producer/consumer 的兼容性声明。
- 统一阶段交接信封、输入输出指纹和 attempt 身份。
- consumer 开始前的契约漂移检测、严重度分类和阻断策略。
- 版本化风险策略、每 run 原子绑定的路由决策和三档执行 profile。
- 轻量路径的确定性影子 QA 抽样、误判记录、策略候选校准和回放。
- 追加式审计事件与机器可读的复跑证据清单。
- 覆盖公开契约、边界、并发、状态转换和失败恢复的验收测试。

### 2.2 本任务延后

- 完整失败/扣分知识库的查询产品、聚类和统计界面。
- 自动改写生产 skill、自动生成生产策略和无人审批晋级。
- baseline/candidate 的完整配对评测平台、canary 发布平台和跨项目控制台。
- Token 金额换算、复杂成本归因和模型训练。
- 各业务阶段内部的功能实现；本任务只约束阶段边界与路由要求。

### 2.3 保留的上游场景

| 上游场景 | 本任务中的落实 |
|---|---|
| 事件重复、乱序或终态后到达 | 追加事件幂等、逻辑序列检查、冲突隔离、迟到证据修订 |
| 测试通过但意图遗漏 | `high` profile 的独立意图门禁 |
| 顺序测试掩盖并发错误 | 并发信号强制 `high`，并要求竞态反例 |
| 评测期间生产基线变化 | 策略激活和校准发布使用 compare-and-set |
| 两个候选并发晋级 | 单一 active 策略与 `BASELINE_STALE` |
| 轻量路径被影子 QA 击穿 | false-negative 反馈、回放案例、候选权重调整 |
| 高风险并发任务 | 稳定阶段契约、确定性验证、独立审查和竞态预算 |

其余候选进化、完整晋级、Token 归一化和知识聚合场景仅保留接口引用，不进入本次实现。

## 3. 合理假设

| A-ID | 假设 | 实现影响 | 验证方式 |
|---|---|---|---|
| A1 | 仓库已有 run 或阶段执行入口，可在 stage 启动和完成边界接入校验器 | 本任务新增边界组件，不重写阶段执行器 | 集成测试证明每个 consumer 启动前均调用校验器 |
| A2 | `pipeline_run_id` 的创建由上游 run owner 完成；本任务只校验、传播和绑定 | 缺失 run ID 直接阻断，返工沿用原 ID 并递增 attempt | 同一 run 两次 attempt 的验收用例 |
| A3 | 指纹算法统一为 `sha256`，结构化数据先按确定性规范化序列化 | 跨进程和重跑可得到相同指纹 | 同语义乱序 key 生成相同 hash 的单测 |
| A4 | 策略阈值和影子抽样率属于配置；首版默认阈值写入策略版本自身 | 任何阈值变化都会产生新 `policy_version` | 配置变化后版本/hash 变化测试 |
| A5 | 人工确认是策略从 canary 进入 active 的必要条件 | 校准闭环生成 candidate，保持人工发布边界 | 缺少 approval 的激活请求失败测试 |
| A6 | `P0` 表示可造成关键不变量破坏、不可恢复数据损失、权限/安全破坏或生产错误放行 | P0 信号或影子发现 P0 时直接选择/升级到 `high` | P0 路由和升级用例 |
| A7 | 实际源码路径和仓库测试命令由开发 agent 根据现有工程布局落位 | 本契约固定逻辑接口、字段、错误码、测试 ID 和证据格式 | dev report 给出最终路径与逐条精确命令 |

开发中发现任一假设不成立时，必须记录 `ASSUMPTION_INVALID` 事件，关联 A-ID、实际证据和影响，停止受影响的实现分支并更新本契约映射。

## 4. 核心不变量

1. 一个用户任务全程使用同一个 `pipeline_run_id`；返工通过递增 `stage_attempt` 表达。
2. 每个已开始的 stage attempt 只能绑定一个 `pipeline_version`、一个 `route_decision_id` 和一个 `policy_version`。
3. 路由与 pipeline 版本在任务创建事务中原子绑定；执行中保持固定。
4. consumer 只读取已通过边界验证的输入；阻断级漂移不能被静默降级。
5. producer 输出及其指纹一经完成即为追加事实；修正通过新 attempt 或修订记录表达。
6. 路由证据必须包含原始信号、归一化值、命中规则、选择结果和策略指纹。
7. `public_contract`、`shared_state_write`、`concurrent_write`、`irreversible_operation` 任一为真时，最低 profile 为 `high`。
8. 未知关键字段、低置信度或无法计算的高影响信号按风险上调处理。
9. 同一时刻只能有一个 active 路由策略；发布和回滚均使用 compare-and-set。
10. 影子 QA 结果只能生成追加反馈和新策略候选，不能改写历史 route decision。
11. 关键契约失败、P0 回归或高风险必需门禁缺失时，run 不能进入 accepted。

## 5. Producer / Consumer 契约

### 5.1 `StageContract`

每个阶段边界必须在注册表声明：

```yaml
contract_id: stage-contract/x-spec2-to-x-req2
contract_version: 1.0.0
producer_stage: x-spec2
consumer_stage: x-req2
input_schema_ref: schema://x-req2/input/1.0.0
output_schema_ref: schema://x-spec2/output/1.0.0
consumer_accepts: ">=1.0.0 <2.0.0"
required_artifacts: [spec]
required_invariants: [intent_traceable, scope_declared, acceptance_present]
compatibility: backward
migration_ref: null
status: active
contract_hash: <sha256>
```

约束：

- `contract_id + contract_version` 唯一且内容不可变。
- `contract_hash` 覆盖除自身以外的规范化完整记录。
- 删除必填字段、收窄 consumer 接受范围、改变字段语义或不变量属于 major 变更。
- 增加可选字段属于 minor 变更；纯说明修订属于 patch 变更。
- consumer 必须显式声明接受范围，禁止把“最新版本”作为运行时解析规则。
- deprecated 契约可供已绑定 run 读取，禁止新 run 绑定。

### 5.2 `StageEnvelope`

producer 完成 attempt 时写入统一交接信封：

```yaml
envelope_version: 1.0.0
event_id: evt-<unique>
pipeline_run_id: prun-<unique>
pipeline_version: pipe-<immutable-version>
stage: x-spec2
stage_attempt: 1
producer_id: <agent-or-runner-id>
contract_id: stage-contract/x-spec2-to-x-req2
contract_version: 1.0.0
contract_hash: <sha256>
route_decision_id: route-<unique>
policy_version: risk-policy/1.0.0
input_refs:
  - artifact_id: <id>
    artifact_hash: <sha256>
output_refs:
  - artifact_id: <id>
    artifact_type: spec
    schema_ref: schema://x-spec2/output/1.0.0
    artifact_hash: <sha256>
status: succeeded
logical_sequence: 4
created_at: <rfc3339>
```

约束：

- `event_id` 用于幂等；相同 ID 与不同 payload 组合产生 `EVENT_ID_COLLISION`。
- `(pipeline_run_id, stage, stage_attempt)` 标识一次 stage 尝试。
- 完成后的同一 attempt 输出引用不可替换；变化通过新 attempt 表达。
- `logical_sequence` 用于重建顺序，接收时间只用于审计。
- 允许迟到证据用 `revision_of_event_id` 追加；迟到证据不改变原终态。

### 5.3 producer 责任

producer 在发布信封前必须：

1. 使用绑定的 contract 精确校验 output schema 和 required invariants；
2. 对输入、输出、contract 和策略生成确定性指纹；
3. 写入完整 run/stage/attempt/version/route 身份；
4. 先持久化 artifact，再追加 `STAGE_OUTPUT_PUBLISHED` 事件；
5. 在部分写入后恢复时复用原 `event_id`，依靠幂等收敛。

### 5.4 consumer 责任

consumer 在执行任何业务逻辑前必须：

1. 读取 envelope 指定的精确 contract 版本；
2. 验证信封 schema、身份连续性、consumer 接受范围及全部 hash；
3. 验证 required artifacts 和 required invariants；
4. 执行漂移分类并写入 `CONTRACT_CHECK_COMPLETED`；
5. 仅在结果为 `pass` 或策略明确允许的 `warn` 时创建 consumer attempt；
6. 将校验结果 ID 写入 consumer attempt，形成可追溯链。

## 6. 漂移检测

### 6.1 检测维度与处置

| 漂移代码 | 判定 | 严重度 | 处置 |
|---|---|---:|---|
| `IDENTITY_DRIFT` | run、pipeline、route 或 policy 身份与绑定记录不一致 | P0 | 隔离事件并阻断 |
| `CONTRACT_HASH_DRIFT` | 同 contract 版本出现不同内容 hash | P0 | 隔离 contract 并阻断所有新消费 |
| `VERSION_INCOMPATIBLE` | producer 版本不在 consumer 接受范围 | P0 | 阻断；要求迁移或新 attempt |
| `SCHEMA_DRIFT` | artifact 不满足声明 schema | P0 | 阻断 producer 完成态 |
| `INVARIANT_MISSING` | required invariant 缺失或失败 | P0/P1，按 invariant 声明 | P0 阻断；P1 至少升级到 high |
| `ARTIFACT_HASH_DRIFT` | 实际内容与信封 hash 不一致 | P0 | 隔离 artifact 并阻断 |
| `REQUIRED_ARTIFACT_MISSING` | 必需 artifact 缺失 | P0 | 阻断 |
| `UNKNOWN_OPTIONAL_FIELD` | 新增可选字段且 consumer 可忽略 | P2 | warn 并继续 |
| `POLICY_BASELINE_STALE` | 激活候选时 active 版本已变化 | P1 | 返回 `BASELINE_STALE` 并要求重放/重基准化 |
| `LATE_EVIDENCE` | run 终态后到达证据 | P2 | 追加 revision，保持已发布事实 |
| `TERMINAL_CONFLICT` | 同 attempt 出现两个冲突终态 | P0 | 双方隔离，等待确定性修复 |

### 6.2 `ContractCheckResult`

```yaml
check_id: ccheck-<unique>
pipeline_run_id: prun-<unique>
consumer_stage: x-req2
producer_envelope_id: evt-<unique>
checked_contract_hash: <sha256>
result: pass | warn | blocked | isolated
drifts:
  - code: VERSION_INCOMPATIBLE
    severity: P0
    expected: ">=1.0.0 <2.0.0"
    actual: 2.0.0
    evidence_refs: [<id>]
action: continue | continue_high | block | isolate
checked_at: <rfc3339>
```

同一固定输入和注册表快照必须得到相同的 `result`、`drifts` 和 `action`；时间与随机 ID 不参与语义结果比较。

## 7. 风险路由

### 7.1 `RiskAssessment`

路由输入必须显式、可归一化、可解释：

```yaml
assessment_id: risk-<unique>
pipeline_run_id: prun-<unique>
policy_version: risk-policy/1.0.0
policy_hash: <sha256>
signals:
  requirement_uncertainty: {value: 0.0, evidence_refs: [<id>]}
  blast_radius: {value: local | module | cross_module | external, evidence_refs: [<id>]}
  public_contract: {value: false, evidence_refs: [<id>]}
  invariant_touch: {value: none | noncritical | critical, evidence_refs: [<id>]}
  shared_state_write: {value: false, evidence_refs: [<id>]}
  concurrent_write: {value: false, evidence_refs: [<id>]}
  irreversible_operation: {value: false, evidence_refs: [<id>]}
  historical_escape_rate: {value: 0.0, sample_size: 0, evidence_refs: [<id>]}
  signal_confidence: {value: 1.0, missing: []}
matched_rules: [R-<id>]
score: 0
profile: lightweight | standard | high
required_gates: [<gate>]
budget_class: small | normal | expanded
reason_codes: [<code>]
```

### 7.2 硬路由规则

规则按以下优先级求值，首个硬规则可抬高最低 profile，后续规则只能继续抬高：

1. 任一 `public_contract`、`shared_state_write`、`concurrent_write`、`irreversible_operation` 为真，选择 `high`。
2. `invariant_touch=critical` 或历史中存在同类 P0 错误放行，选择 `high`。
3. 必填风险信号缺失、`signal_confidence` 低于策略阈值且 blast radius 至少为 module，选择 `high`。
4. cross-module/external 影响、显著需求不确定性或历史 P1 错误放行率达到策略阈值，最低为 `standard`。
5. 仅局部、可逆、无共享状态、无公开契约、信号完整且历史风险低的任务可进入 `lightweight`。
6. 契约检查产生 P1 时，现有 route decision 追加 `ROUTE_ESCALATED`，执行 profile 升至 `high`；已完成的低强度步骤保留审计记录。

具体数值阈值必须存入 `policy_version`，禁止写死在调用方。默认值属于 A4，开发时通过策略 fixture 固定。

### 7.3 执行 profile 契约

| profile | 建模要求 | 验证与审查 | 预算 |
|---|---|---|---|
| `lightweight` | 目标、范围、单一 happy path、直接边界 | 目标测试 + 基础契约检查；按策略进入影子 QA 样本 | small |
| `standard` | 稳定 task contract、主要状态和失败路径 | deterministic verify + 意图/正确性合并审查 + 关键边界用例 | normal |
| `high` | 稳定 spec/task contract、完整不变量、状态/并发/恢复模型 | deterministic verify + 独立意图审查 + 独立正确性审查 + 独立证据审查 + 竞态/恢复反例 | expanded |

profile 是最低要求。阶段可追加更强验证，并记录 `PROFILE_AUGMENTED`；执行方无权弱化绑定要求。

### 7.4 策略生命周期

`RoutingPolicy.status` 状态机：

```text
draft -> shadow -> canary -> active -> retired
                    |          |
                    v          v
                 rejected   rolled_back -> retired
```

| 状态 | 可做操作 | 进入条件 |
|---|---|---|
| `draft` | 静态校验、离线回放 | 关联反馈证据、可证伪假设、baseline 和回滚目标 |
| `shadow` | 对真实输入生成旁路决策，不影响执行 | 静态校验通过 |
| `canary` | 只影响 manifest 指定的新任务样本 | 影子结果通过门禁 + 人工批准 |
| `active` | 供新 run 原子绑定 | canary 门禁通过 + active 版本 CAS 成功 |
| `rejected` | 保留证据，禁止绑定 | 任一关键不变量/P0 回归或人工拒绝 |
| `rolled_back` | 停止新绑定，指向回滚目标 | canary/active 触发回滚条件且 CAS 成功 |
| `retired` | 只供历史 run 读取 | 已有替代 active，且没有新绑定 |

每次状态迁移追加 `POLICY_STATE_CHANGED`，包含 `from`、`to`、actor、approval/evidence、baseline、CAS 期望值与结果。

### 7.5 每 run 的路由绑定状态

`RouteDecision.status` 状态机为 `assessed -> bound -> executing -> completed`；漂移或新证据可使 `bound/executing -> escalated`，随后继续 `executing -> completed`。任务创建事务必须同时写入 pipeline 版本和 `bound` route decision。绑定失败时不创建半绑定 run。

## 8. 影子 QA 与反馈校准

### 8.1 抽样

- 抽样只面向 active 策略判定为 `lightweight` 的任务。
- 是否入样由 `hash(pipeline_run_id + policy_version) mod N` 与策略内阈值决定，保证可复跑。
- 策略可对新规则、低置信度、历史高逃逸类型提高抽样率。
- 影子 QA 使用 `high` profile 的审查强度，结果不改写原 route decision。

### 8.2 反馈记录

```yaml
feedback_id: rfb-<unique>
pipeline_run_id: prun-<unique>
route_decision_id: route-<unique>
policy_version: risk-policy/1.0.0
shadow_selected: true
shadow_result: pass | P1 | P0 | inconclusive
classification: true_lightweight | false_negative | inconclusive
finding_codes: [<code>]
evidence_refs: [<id>]
replay_fixture_ref: <immutable-fixture-id>
root_cause_status: candidate | confirmed
created_at: <rfc3339>
```

当影子 QA 发现 P0/P1 时，必须：

1. 记录 `false_negative`，保留原始信号、策略版本、命中规则和发现证据；
2. 生成不可变回放 fixture，并关联失败类型；
3. 对仍在执行的 run 触发 `ROUTE_ESCALATED`；
4. 创建 draft 策略候选，声明拟调整信号/权重/硬规则、可证伪预期和回归面；
5. 在固定历史集上同时报告 false-negative、false-positive、P0/P1 回归和 profile 分布变化；
6. P0 回归直接拒绝候选；其余门槛由候选 manifest 的版本化指标声明决定；
7. 人工批准后依次经过 shadow/canary/active，历史决策保持原策略引用。

`inconclusive` 不能计作 pass 或已确认根因；它必须保留缺失证据和下一步采集要求。

## 9. 审计事件与失败恢复

最小事件集合：

- `RUN_ROUTE_BOUND`
- `STAGE_ATTEMPT_STARTED`
- `STAGE_OUTPUT_PUBLISHED`
- `CONTRACT_CHECK_COMPLETED`
- `CONTRACT_DRIFT_DETECTED`
- `ROUTE_ESCALATED`
- `SHADOW_QA_COMPLETED`
- `ROUTING_FEEDBACK_RECORDED`
- `POLICY_STATE_CHANGED`
- `ASSUMPTION_INVALID`

所有事件至少包含 `event_id`、`pipeline_run_id`、`event_type`、`logical_sequence`、`payload_version`、`payload_hash`、`created_at`。写入规则：

- 相同 `event_id + payload_hash` 重放视为成功。
- 相同 `event_id` 与不同 hash 进入隔离。
- 存储按追加模式工作；派生视图可重建。
- 乱序事件先保存，再按前置条件归并；缺少前置事件时标记 pending。
- 冲突终态进入 isolated，任何一方都不能覆盖另一方。
- artifact 已保存而事件未落盘时，重试复用稳定 event ID；事件已保存而派生视图未更新时，从事件重建。

## 10. 实现 Checklist

### 10.1 数据与注册表

- [ ] 定义并验证 `StageContract`、`StageEnvelope`、`ContractCheckResult`、`RiskAssessment`、`RouteDecision`、`RoutingPolicy`、`RoutingFeedback` schema。
- [ ] 实现确定性规范化与 sha256 指纹，覆盖 map key 顺序、空值和数组顺序语义。
- [ ] 建立版本不可变的 contract registry 与 consumer 兼容范围查询。
- [ ] 为六个阶段的相邻边界登记 contract；每条声明 producer、consumer、required artifacts 和 invariants。
- [ ] 为结构化记录提供向后兼容解析和未知可选字段策略。

### 10.2 阶段边界

- [ ] producer 完成前执行 output schema/invariant 校验并发布 envelope。
- [ ] consumer 启动前执行身份、版本、hash、artifact 和 invariant 校验。
- [ ] 实现漂移分类表中的错误码、严重度和动作。
- [ ] 确保 blocked/isolated 检查不会创建 consumer attempt。
- [ ] 支持同 run 新 attempt、迟到 evidence revision 和冲突终态隔离。

### 10.3 风险路由

- [ ] 实现风险信号归一化与 evidence refs 完整性检查。
- [ ] 将硬路由规则实现为版本化、可解释的策略数据。
- [ ] 实现 lightweight/standard/high 的 gate 和 budget 映射。
- [ ] 在 run 创建事务内原子绑定 pipeline 版本和 route decision。
- [ ] 实现 profile 只升不降以及 `ROUTE_ESCALATED`。
- [ ] 实现策略生命周期、人工批准校验、active 唯一约束和 CAS 发布/回滚。

### 10.4 反馈校准

- [ ] 实现基于 run ID 和策略版本的确定性影子抽样。
- [ ] 实现 shadow result 分类、不可变回放 fixture 与 false-negative 记录。
- [ ] 从 P0/P1 反馈生成带依据、假设、baseline 和回滚目标的 draft candidate。
- [ ] 实现固定集回放报告，至少输出 FN、FP、P0/P1 回归和 profile 分布。
- [ ] 阻止缺少证据、回放清单或人工批准的策略进入 active。

### 10.5 审计与证据

- [ ] 实现事件幂等、乱序 pending、终态冲突隔离和派生视图重建。
- [ ] 每个决策结果输出机器可读 reason codes 与 evidence refs。
- [ ] 为每个验收用例保存输入 fixture、实际输出、期望摘要和精确复跑命令。
- [ ] dev report 列出改动文件、schema/策略版本、测试命令、exit code 和证据路径。

## 11. 验收用例

### AC-01 正常阶段交接

- GIVEN x-spec2 envelope 使用 consumer 接受的 contract 版本，所有 hash 与 required invariants 有效
- WHEN x-req2 请求启动
- THEN contract check 为 `pass`，consumer attempt 引用该 `check_id` 后开始
- 证据：输入 envelope、registry snapshot、check result、consumer start event

### AC-02 版本不兼容阻断

- GIVEN consumer 接受 `>=1.0.0 <2.0.0`，producer 声明 `2.0.0`
- WHEN 执行边界校验
- THEN 返回 `VERSION_INCOMPATIBLE/P0/block`，不产生 consumer attempt
- 证据：固定 fixture 与事件查询结果

### AC-03 同版本内容漂移

- GIVEN registry 中同一 `contract_id/version` 已有 hash A，新写入内容 hash B
- WHEN 注册或消费该契约
- THEN 返回 `CONTRACT_HASH_DRIFT/P0/isolate`，新消费全部阻断
- 证据：两个 contract fixture、隔离事件

### AC-04 artifact 被修改

- GIVEN envelope 的 artifact hash 与存储内容不一致
- WHEN consumer 校验输入
- THEN 返回 `ARTIFACT_HASH_DRIFT/P0/isolate`
- 证据：原始/篡改 fixture、hash 计算和 check result

### AC-05 幂等、乱序与终态冲突

- GIVEN 相同事件重复提交、sequence 3 先于 2 到达、同 attempt 出现 succeeded/failed 两种终态
- WHEN ledger 归并
- THEN 重复事件只保留一个 canonical 事实；3 等待并在 2 到达后归并；冲突终态进入 isolated
- 证据：提交顺序脚本、最终事件视图和隔离记录

### AC-06 返工保持 run 身份

- GIVEN x-verify 失败后进入 x-fix 并重跑 x-dev
- WHEN 创建返工 attempt
- THEN `pipeline_run_id`、pipeline version、route decision 保持一致，相关 stage attempt 递增且旧输出可查
- 证据：attempt 链和 artifact hash 列表

### AC-07 局部低风险路由

- GIVEN 任务局部、可逆、无公开契约/共享状态/并发写、信号完整且历史风险低
- WHEN 固定策略求值
- THEN profile 为 `lightweight`，reason codes、目标 gate、预算与策略 hash 完整
- 证据：risk fixture 与 route decision

### AC-08 高风险硬路由

- GIVEN `concurrent_write=true`，其余信号均低风险
- WHEN 固定策略求值
- THEN profile 为 `high`，包含 deterministic verify、三类独立审查与竞态反例预算
- 证据：risk fixture、命中规则和 gate 列表

### AC-09 缺失信号保守上调

- GIVEN blast radius 为 cross-module，关键状态信号缺失且置信度低于阈值
- WHEN 路由求值
- THEN profile 为 `high`，reason code 指向缺失字段和置信度规则
- 证据：缺失字段 fixture 与决策说明

### AC-10 路由与 pipeline 原子绑定

- GIVEN route decision 持久化在事务中失败
- WHEN 创建新 run
- THEN run 与 pipeline 版本均没有半绑定可执行记录；重试后只生成一个有效绑定
- 证据：故障注入日志、绑定查询和唯一性检查

### AC-11 影子 QA 击穿轻量路径

- GIVEN active 策略将任务判为 lightweight，确定性抽样命中且影子 QA 发现 P1 边界问题
- WHEN 写入反馈
- THEN 产生 `false_negative`、回放 fixture、知识引用和 draft candidate；进行中 run 升级为 high；原 decision 保持原策略版本
- 证据：抽样计算、shadow result、反馈记录、升级事件、candidate manifest

### AC-12 影子抽样可复跑

- GIVEN 相同 run ID、policy version 与抽样配置
- WHEN 在两个独立进程重复计算
- THEN 抽样结果一致；policy version 或配置版本变化可产生新的确定性结果
- 证据：双进程输出和策略 hash

### AC-13 两个策略候选并发激活

- GIVEN candidate A/B 都以 active V1 为 baseline 并通过门禁
- WHEN 两者并发执行 compare-and-set
- THEN 仅一个成为 active；另一方返回 `BASELINE_STALE`；active 数量始终为一
- 证据：并发测试、状态迁移事件和 active 查询

### AC-14 P0 回归阻止策略晋级

- GIVEN candidate 降低平均 profile，但固定回放集出现 P0 错误放行
- WHEN 评估晋级
- THEN candidate 进入 rejected，无法 canary/active，拒绝证据关联具体 fixture
- 证据：回放报告、拒绝事件和绑定失败结果

### AC-15 回滚与新任务并发

- GIVEN active V2 回滚到 V1，同时创建多个新任务
- WHEN 原子切换提交
- THEN 提交前创建的任务保持原绑定，提交后任务全部绑定 V1，无未绑定或混合版本 run
- 证据：带事务序列的并发测试与逐 run 绑定清单

## 12. 可复跑证据契约

实现交付必须生成一个 evidence manifest；每个 AC 至少一条记录：

```yaml
evidence_version: 1.0.0
implementation_revision: <code-snapshot>
contract_registry_hash: <sha256>
routing_policy_version: <version>
routing_policy_hash: <sha256>
cases:
  - case_id: AC-01
    command: <从仓库根目录可直接执行的精确命令>
    exit_code: 0
    fixture_refs: [<immutable-path-or-id>]
    output_refs: [<machine-readable-result>]
    output_hashes: [<sha256>]
    observed: <关键实际值>
    expected: <关键期望值>
    result: pass
```

证据验收规则：

1. 所有命令从仓库根目录执行，无需依赖未记录的交互状态。
2. 每条命令记录实际 exit code；失败测试通过断言错误码和最终状态表达，测试进程仍应成功。
3. fixture、registry snapshot、策略 snapshot 和机器可读输出均有 sha256。
4. 并发用例至少重复执行多轮，轮数作为命令参数固定并记录；每轮均验证不变量。
5. 漂移和路由测试必须断言结构化错误码、profile、gate 和状态，避免只匹配日志文本。
6. 完整证据集必须支持从空派生视图重建并复跑 AC-01 至 AC-15。

## 13. 完成定义

以下条件全部满足后可交付：

- 六个相邻阶段边界均存在版本化 producer/consumer contract。
- 每个 consumer 启动前执行漂移检测，P0 漂移用验收证据证明会阻断或隔离。
- 风险策略与 pipeline 版本在 run 创建时原子绑定，高风险硬规则和 profile 要求完整生效。
- 轻量路径具备确定性影子 QA、false-negative 反馈、回放和候选校准闭环。
- 策略生命周期具备人工批准、CAS 单 active、P0 拒绝和并发回滚保证。
- AC-01 至 AC-15 全部通过，evidence manifest 非空且每条命令可从仓库根目录复跑。
- 实现没有扩大到第 2.2 节延期能力，所有新增假设均以 A-ID 和验证证据登记。
