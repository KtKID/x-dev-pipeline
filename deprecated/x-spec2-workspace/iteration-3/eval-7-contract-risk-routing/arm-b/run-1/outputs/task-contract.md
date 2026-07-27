# 阶段契约一致性与风险路由校准

## 1. 任务目标

为 `x-spec2 -> x-req2 -> x-dev -> x-verify -> x-qa-gate -> x-fix` 建立唯一、可机器校验的阶段交接契约，并实现版本化风险路由与影子 QA 反馈校准。完成后，每个阶段只从约定的上游产物读取 Requirement、Scenario、风险、状态和报告引用；任何旧字段、错误路径、重复真源或非法状态转换都会产生可定位的 `CONTRACT_DRIFT` 并阻止当前 pipeline 版本成为基线。

本任务对应以下 Requirement：

- `统一流水线契约`
- `风险与不确定性路由`
- `V2 方案与任务交接`
- `版本绑定与运行观测` 中与阶段身份、版本和事件有关的最小字段
- `可定位失败归因` 中与契约漂移、路由误判有关的原因码
- `可比配对回放` 中与路由策略候选可比性有关的输入

成功标准：

1. 同一语义只有一个声明真源和一个生效结果；其他产物只能保存稳定引用或不可变快照。
2. 所有生产者和消费者可由确定性校验器逐项核对。
3. 每次路由决策绑定 `pipeline_run_id`、pipeline 版本、路由策略版本、输入指纹和历史信号快照。
4. 低风险路径可轻量执行并接受配置化影子 QA；高风险路径强制完整审查。
5. 影子 QA 发现的 P0/P1 问题形成 `ROUTER_UNDER_REVIEW` 记录，只驱动候选策略，已发布策略保持不可变。

## 2. 范围

### 2.1 包含

- 定义并落地 V2 阶段产物的字段、引用、状态与错误语义。
- 为 x-spec2、x-req2、x-dev、x-verify、x-qa-gate、x-fix 建立 producer/consumer 清单。
- 增加确定性的静态契约校验和运行前契约校验。
- 将声明风险、路由上下文、生效路由决策分层建模。
- 实现轻量与完整两类执行 profile，以及低风险影子 QA 抽样。
- 记录路由命中、影子审查、路由漏判和策略校准所需事实。
- 输出可复跑的命令结果、结构化结果和退出码证据。

### 2.2 排除

- 自动修改生产 skill、template 或 validator。
- 无人审批发布路由策略或 pipeline 候选。
- 知识库物理存储、索引、保留期和访问控制的最终选型。
- 跨项目云服务、组织权限和可视化控制台。
- 模型训练、微调、外部 provider 运行时和 Token 金额换算。
- 完整的自我进化候选生成、全量评测和 canary 发布实现；本任务只提供路由策略进入这些阶段所需的稳定契约。

## 3. 显式假设

| A-ID | 假设 | 处理方式 |
|---|---|---|
| A1 | x-req2 的任务目录至少包含本任务同类的 `task-contract.md` 与可供 x-dev 执行的 checklist。 | 本任务将二者定义为任务契约和执行项真源；实际文件命名存在差异时，先统一生产者与消费者，再启用严格校验。 |
| A2 | `tools/xdev.py` 继续承担确定性校验入口，`tools/req.py`、`tools/verify.py`、`tools/metrics.py` 可扩展或复用。 | 新能力优先作为这些工具的子命令或共享库落地；现有命令结构存在差异时可调整命令名，输出契约与退出码保持本文件定义。 |
| A3 | 首版使用仓库本地产物保存路由决策和校准输入。 | 存储后端可替换；记录 ID、不可变事实、追加修订和引用语义保持稳定。 |
| A4 | 风险等级采用 `low`、`medium`、`high` 三档，P0/P1 表示会触发低风险误判校准的严重问题。 | 策略阈值与抽样比例由版本化配置决定，代码中不得硬编码生产阈值。 |
| A5 | 影子 QA 不改变原执行路径的既有结果，但其 P0/P1 发现会标记路由误判并进入知识与候选策略链。 | 对尚未最终交付的生产任务，现有质量门禁仍可依据发现阻止交付；校准统计必须区分影子观察结果与正式门禁结果。 |
| A6 | `pipeline_run_id` 由运行入口生成并传递给各阶段，本任务不重新定义全局 ID 生成算法。 | 缺失或阶段间变化均按契约漂移阻断。 |
| A7 | Requirement 与 Scenario 使用稳定 ID。 | 标题可作为展示字段；机器引用必须使用稳定 ID。缺少稳定 ID 的 V2 输入在 x-req2 交接前失败。 |
| A8 | 首版 reviewer 数量支持 `0`、`1`、`3`；完整路径的三个 reviewer 分别承担 q1、q2、q3。 | 策略可以把多个维度交给同一 reviewer，但生效决策仍需列出三个维度及其责任者。 |

## 4. 唯一真源与派生关系

| 语义 | 唯一声明真源 | 唯一生效结果 | 允许的下游形式 |
|---|---|---|---|
| Requirement/Scenario | x-spec2 `spec.md` | x-req2 任务承接清单 | 稳定 ID 引用；禁止复制后改写语义 |
| 模块边界 | x-spec2 `modules.md`，动态设计按需来自 `design.md` | x-req2 任务范围 | 模块 ID/边界引用 |
| 任务执行项 | x-req2 checklist | x-dev 执行状态 | checklist item ID 引用 |
| 声明风险 | x-req2 checklist 的结构化 `risk` | 路由器聚合后的 `risk_level` | `risk_ref` 与输入指纹 |
| 生效路由 | 版本化 routing policy | `route_decision` | 决策 ID 引用；下游不得重新计算 |
| 实现结果 | x-dev `dev-report` | dev 终态 | 报告 ID/路径与产物指纹引用 |
| 可复跑事实 | x-verify 结构化结果 | verify 终态 | evidence ID、命令、退出码、输出摘要引用 |
| QA 判断 | x-qa-gate issue/decision | QA 终态 | issue ID、维度、严重度、证据引用 |
| 修复处置 | x-fix fix report | fix 终态及新的回流 run/stage attempt | issue ID、修复证据和回流目标引用 |
| 阶段状态 | 对应阶段事件生产者 | 运行账本的最新合法事件 | 追加事件；禁止覆盖历史 |
| 报告位置 | 产物生产者写入的 artifact reference | 运行账本绑定后的引用 | ID、相对路径、内容指纹；消费者禁止猜路径 |

约束：声明真源表达输入事实，生效结果表达版本化计算结果。两者职责不同，且各自只有一个生产者。下游产物保存快照时必须同时保存源 ID 与源指纹；快照与源不一致即为漂移。

## 5. 统一包络

所有机器可读阶段产物必须包含以下公共包络；Markdown 报告通过同目录结构化 sidecar 提供等价字段：

```yaml
schema_version: 1
artifact_type: <spec|task_contract|checklist|route_decision|dev_report|verify_result|qa_decision|fix_report>
artifact_id: <stable unique id>
pipeline_run_id: <unique run id>
pipeline_version: <published or candidate version>
stage: <spec|req|dev|verify|qa|fix>
stage_attempt: <positive integer>
producer:
  name: <stage/tool name>
  version: <skill/template/validator version set>
created_at: <RFC3339 timestamp>
input_refs:
  - artifact_id: <upstream id>
    fingerprint: <content fingerprint>
artifact_fingerprint: <content fingerprint>
status: <artifact-specific status>
evidence_refs: []
```

公共规则：

- 同一 `pipeline_run_id` 的 `pipeline_version` 固定；修复回流通过 `stage_attempt` 递增表达。
- 原始事实与阶段事件只追加。更正记录使用新 `artifact_id`、`supersedes` 和修订理由。
- 输入引用必须能解析到上游真实产物，且指纹一致。
- 候选版本和已发布版本使用独立身份与独立产物。
- 消费者发现未知的必需 schema major version 时必须失败；新增可选字段允许向前兼容。

## 6. Producer / Consumer 契约

### 6.1 x-spec2 -> x-req2

**Producer：x-spec2**

- 必需产物：非空 `spec.md`、非空 `modules.md`；动态模型适用时提供非空 `design.md`。
- 必需内容：稳定 Requirement ID、稳定 Scenario ID、用户要求追溯、范围边界、关键约束和系统不变量。
- 状态：`draft -> confirmed -> ready_for_req`。

**Consumer：x-req2**

- 只接收 `ready_for_req` 的 V2 需求包。
- 每个任务必须列出 `requirement_refs`、`scenario_refs`、`module_refs`、in-scope、out-of-scope、验收和风险声明。
- 任一引用缺失、悬空或指向旧版 spec 位置时停止拆解。

### 6.2 x-req2 -> 路由器 / x-dev

**Producer：x-req2**

- 产物一：`task-contract`，包含目标、范围、Requirement/Scenario 引用、依赖、不变量触达、验收与证据计划。
- 产物二：checklist，每项包含唯一 item ID、目标、文件/模块范围、`requirement_refs`、`scenario_refs`、结构化 `risk` 和完成条件。
- `risk` 最小字段：

```yaml
risk:
  level_hint: low|medium|high
  requirement_uncertainty: low|medium|high
  module_impact: local|multi_module|system
  invariant_refs: []
  public_contract_change: true|false
  concurrency_or_state: none|reversible|irreversible
  rationale: <non-empty>
```

**Consumer：路由器**

- 校验任务契约与 checklist 引用一致性。
- 读取声明风险，并合并版本化历史信号快照生成 `route_decision`。
- 对缺失字段、矛盾字段或未知枚举返回 `ROUTE_INPUT_INVALID`，不得静默降级。

**Consumer：x-dev**

- 只消费 checklist、任务契约和已生效 `route_decision`。
- 按 checklist item 写入执行结果和证据，不自行提升或降低路由级别。
- 路由决策要求完整审查时，dev-report 必须保留 q1/q2/q3 后续消费所需引用。

### 6.3 x-dev -> x-verify

**Producer：x-dev**

- `dev-report` 逐项记录 `completed|blocked|failed`、变更产物、Requirement/Scenario 回指、实际命令、测试计划、残余风险和证据。
- 终态：`dev_completed|dev_blocked|dev_failed`。

**Consumer：x-verify**

- 只从 `dev-report` 和任务验收读取需复跑命令与 Scenario；命令缺失或引用悬空时返回结构化失败。
- 保存每条命令、工作目录、开始/结束时间、exit code、stdout/stderr 摘要、证据指纹和 Scenario 结果。

### 6.4 x-verify -> x-qa-gate

**Producer：x-verify**

- 结构化结果包含 `verify_passed|verify_failed|verify_interrupted`、命令级事实、Scenario 覆盖和缺失指标原因。
- verify 只陈述可复跑事实，不给出 QA 充分性结论。

**Consumer：x-qa-gate**

- 读取任务契约、`route_decision`、dev-report 和 verify 结果的显式引用。
- `full` profile 必须覆盖 q1-intent、q2-correctness、q3-evidence；`light` profile 仅在影子抽样命中时执行策略指定的 QA 维度。
- issue 最小字段：`issue_id`、`dimension`、`severity`、`requirement_refs`、`scenario_refs`、`detected_stage`、`origin_stage`、`reason_code`、`evidence_refs`、`disposition`。

### 6.5 x-qa-gate -> x-fix -> 回流

**Producer：x-qa-gate**

- 正式门禁终态：`qa_passed|qa_failed|qa_interrupted`。
- 影子审查终态：`shadow_clear|shadow_issue_found|shadow_inconclusive`，并明确 `gate_effect=false`。
- P0/P1 影子 issue 额外产生 `ROUTER_UNDER_REVIEW` 知识输入，绑定原 route decision 与策略版本。

**Consumer / Producer：x-fix**

- 只处置显式 issue ID，记录修复范围、根因状态、修复证据和复审目标。
- fix 完成后创建递增 `stage_attempt` 的 dev/verify/QA 回流链；原结果保留。
- 禁止把 fix-report 直接标记为 verify 或 QA 通过。

## 7. 漂移检测

### 7.1 检测时机

1. **静态校验**：候选 pipeline 进入基线前，扫描阶段契约声明、schema、消费者读取映射和 legacy denylist。
2. **运行前校验**：每个消费者启动前校验上游 artifact type、版本、状态、引用、指纹和必需字段。
3. **运行后校验**：阶段收敛时校验输出包络、合法终态、报告引用和下游必需字段。
4. **配对前校验**：校验 baseline/candidate 的任务、模型、repo SHA、权限、预算、grader 断言与路由评测输入可比。

### 7.2 必检规则

- `SOURCE_UNIQUE`：每个语义字段只有一个生产者；重复声明必须指向同一 source ID 和 fingerprint。
- `NO_LEGACY_READ`：消费者不得读取退役 README、旧 spec 章节、旧 risk 位置或推测报告路径。
- `REFERENCE_RESOLVES`：Requirement、Scenario、module、checklist、issue 和 evidence 引用均可解析。
- `FINGERPRINT_MATCHES`：消费者记录的输入指纹与真实上游产物一致。
- `STATE_TRANSITION_VALID`：当前状态只能由合法前置状态和所有者推进。
- `ROUTE_DECISION_BOUND`：执行 profile 绑定 run、policy version、input fingerprint 和 signal snapshot。
- `REQUIRED_QA_PRESENT`：完整 profile 的 q1/q2/q3 均有责任者和终态。
- `REPORT_REF_EXPLICIT`：消费者通过 artifact reference 取报告，路径与内容指纹一致。
- `RUN_ID_STABLE`：同一运行各阶段的 `pipeline_run_id` 一致，回放和修复关系显式记录。

### 7.3 错误输出

任何必检规则失败均返回非零退出码，并至少输出：

```json
{
  "code": "CONTRACT_DRIFT",
  "rule": "NO_LEGACY_READ",
  "producer": "x-req2",
  "consumer": "x-qa-gate",
  "artifact_id": "...",
  "field": "risk",
  "expected_source": "...",
  "actual_source": "...",
  "evidence_path": "...",
  "message": "..."
}
```

多个 issue 必须一次完整列出并稳定排序，便于一轮修复。校验器自身异常使用独立 `VALIDATOR_ERROR`，不得伪装为契约通过或 `CONTRACT_DRIFT`。

## 8. 风险路由策略

### 8.1 路由输入

- 任务风险声明：需求不确定性、模块影响、不变量引用、公开契约、并发/状态可逆性。
- 运行上下文：pipeline 版本、repo SHA、工具权限、预算、任务输入指纹。
- 历史信号快照：同类任务错误放行率、P0/P1 记录、修复轮数和已确认根因；快照需记录查询窗口与知识修订版本。
- 强制升级条件：系统不变量、高风险模块、公开契约、并发、不可逆状态任一命中时，至少进入 `full`。

### 8.2 决策输出

```yaml
route_decision_id: <unique id>
pipeline_run_id: <run id>
policy_version: <version>
policy_status: published|candidate
input_fingerprint: <task and checklist fingerprint>
signal_snapshot_id: <immutable snapshot id>
risk_level: low|medium|high
profile: light|full
contract_depth: light|stable
verify_required: true
qa_dimensions: [] # full 必须为 q1-intent, q2-correctness, q3-evidence
reviewer_count: 0|1|3
shadow_qa:
  eligible: true|false
  selected: true|false
  sample_rule_id: <id|null>
token_budget: <policy-defined value>
reason_codes: []
decided_at: <RFC3339>
```

决策规则：

- `low`：局部、明确、未触及不变量、无公开契约/并发/不可逆状态，且历史错误放行率低。profile 为 `light`，必须运行 deterministic verify，并按策略进入影子 QA。
- `medium`：任一输入不完整、跨模块影响或历史信号不足。默认 profile 为 `full`；策略只有在有显式证据时才可降级，并记录 reason code。
- `high`：触及系统不变量、高风险模块、公开契约、并发或不可逆状态。profile 固定为 `full`，使用稳定 task contract、verify 及 q1/q2/q3 独立审查。
- 路由器无法确定时使用 `medium + full`，并输出 `ROUTE_UNCERTAIN`；不得将未知值当作低风险。
- 任一人工 override 都要追加记录操作者、理由、原决策和新决策；生产策略是否允许 override 由策略配置决定。

### 8.3 路由策略状态

| 状态 | 所有者 | 进入条件 | 允许后继 |
|---|---|---|---|
| `draft` | 优化控制面 | 新策略已创建 | `evaluating`, `rejected` |
| `evaluating` | 评测控制面 | 关联知识、可证伪假设、baseline、manifest 完整 | `proposed`, `rejected` |
| `proposed` | 晋级判断 | 可比配对回放完成且通过硬门槛 | `published`, `rejected` |
| `published` | 用户审批/发布控制面 | 用户确认，版本唯一 | `superseded`, `rolled_back` |
| `superseded` | 发布控制面 | 新版已发布 | 终态 |
| `rejected` | 评测/晋级判断 | 不可比、关键回归或门槛失败 | 终态；新修订使用新版本 |
| `rolled_back` | 回滚控制面 | canary 达到退化门槛 | 终态；上一稳定版本重新成为生产绑定 |

单次 `route_decision` 状态为 `input_validated -> decided -> consumed -> closed`；命中影子审查时从 `consumed` 进入 `shadow_reviewed` 后再 `closed`。P0/P1 漏判追加 `calibration_required` 标记，不改写原始决策。

## 9. 反馈校准

### 9.1 校准事实

每个被影子 QA 抽中的低风险任务记录：

- `pipeline_run_id`、`route_decision_id`、policy version、任务类别和输入指纹。
- 抽样规则、抽样概率、是否执行成功、QA 三维度结果。
- issue severity、detected/origin stage、reason code、证据和最终 disposition。
- 正式路径是否已放行、影子结果是否会改变该判断。
- 影子 QA、collector 的 Token 计入 `evolution_eval_tokens`。

### 9.2 指标

- `shadow_reviewed_low_risk`：成功完成影子 QA 的低风险样本数。
- `router_false_release_count`：影子 QA 发现 P0/P1 且轻量路径原本会放行的样本数。
- `router_false_release_rate = router_false_release_count / shadow_reviewed_low_risk`。
- 同时按任务类别、模块、不变量、policy version 和时间窗口分桶；分母为零时报告 `insufficient_data`。
- 影子 QA 中断或证据不足归入 `shadow_inconclusive`，不得计入已审查分母。

### 9.3 校准闭环

1. 影子 QA 发现 P0/P1，追加 `ROUTER_UNDER_REVIEW` 知识输入，关联真实 run、决策、策略和证据。
2. 根因保持 `pending_confirmation`，直到证据能区分风险声明遗漏、路由规则错误、历史信号缺失或 QA 假阳性。
3. 聚合达到策略配置的样本量/严重度门槛后，生成候选策略和可证伪假设；生产策略原版本保持不可变。
4. baseline 与 candidate 使用相同任务快照、模型、repo SHA、权限、预算、grader 断言和历史信号快照执行配对回放。
5. 任一关键不变量、P0 holdout 或正确性回归阻止候选；随后比较意图准确性、技术正确性和 Token 效率。
6. 通过的候选进入 `proposed`，由用户确认发布；失败候选保存拒绝原因和已消耗 `evolution_eval_tokens`。

## 10. 实现 checklist

- [ ] C1 建立统一 stage artifact schema 与公共包络，覆盖 spec/task/checklist/route/dev/verify/QA/fix。
- [ ] C2 为 Requirement、Scenario、module、checklist item、issue、evidence 定义稳定引用和解析校验。
- [ ] C3 在 x-req2 产物中收敛任务范围、承接引用和 checklist `risk` 唯一声明位置；移除消费者对旧位置的依赖。
- [ ] C4 建立 producer/consumer registry，逐项声明 artifact type、必需字段、允许状态、报告引用和 schema version。
- [ ] C5 实现静态、运行前、运行后契约校验，完整聚合并稳定排序 `CONTRACT_DRIFT` issues。
- [ ] C6 为 legacy README、旧 spec 章节、旧 risk 位置和猜测式报告路径建立 denylist/规则检查。
- [ ] C7 实现版本化 routing policy schema、加载、校验和指纹；阈值、抽样率、预算和 reviewer 数量均来自策略。
- [ ] C8 实现路由输入归一化、历史信号快照、强制升级和不确定性保守路由。
- [ ] C9 生成不可变 `route_decision`，绑定 run、pipeline/policy version、输入指纹、signal snapshot 和理由。
- [ ] C10 让 x-dev、x-verify、x-qa-gate 只消费生效路由决策；阻止阶段内重复计算和静默改写。
- [ ] C11 实现 low/light 与 high/full profile；所有 profile 都执行 deterministic verify，full 覆盖 q1/q2/q3。
- [ ] C12 实现可复现的影子 QA 抽样，保存 sample rule 和选中证据；同一输入和策略测试夹具可稳定复跑。
- [ ] C13 将影子 P0/P1 发现转换为 `ROUTER_UNDER_REVIEW` 输入，保留 detected/origin stage 与待确认根因。
- [ ] C14 在 metrics 聚合中计算影子样本数、错误放行数/率、分桶结果和 `insufficient_data`。
- [ ] C15 实现候选策略状态机与非法转换检查，发布必须保留用户审批和回滚目标。
- [ ] C16 为修复回流实现 `stage_attempt` 递增和 issue/evidence 关联，保留此前所有阶段事实。
- [ ] C17 添加单元、集成、负例和回归测试；每个错误实现至少被一个验收用例击穿。
- [ ] C18 产出开发报告，列出实际命令、exit code、测试计数、结构化输出路径和输入输出指纹。

依赖顺序：`C1-C4 -> C5-C6 -> C7-C10 -> C11-C16 -> C17-C18`。

## 11. 验收用例

### AC1：完整阶段链零漂移

- GIVEN V2 spec、任务契约、checklist、route decision、dev-report、verify 结果、QA issue/decision 和 fix-report 均使用统一包络
- WHEN 运行严格契约校验
- THEN exit code 为 0，结构化结果 `issues=[]`，每个消费者读取的真实上游 artifact、字段、状态和报告引用均可定位
- 验证：auto

### AC2：消费者读取旧字段

- GIVEN x-qa-gate fixture 指向退役 README、旧 spec 章节或旧 risk 位置
- WHEN 运行严格契约校验
- THEN exit code 非 0，返回 `CONTRACT_DRIFT/NO_LEGACY_READ`，包含 producer、consumer、字段、预期源、实际源和 evidence path
- 验证：auto

### AC3：风险重复真源

- GIVEN task contract 与 checklist 分别声明互相矛盾的风险值，且其中一处没有 source 引用
- WHEN 运行契约校验
- THEN 返回 `CONTRACT_DRIFT/SOURCE_UNIQUE`，当前 pipeline 候选不得进入 baseline
- 验证：auto

### AC4：悬空 Scenario 引用

- GIVEN checklist item 引用 spec 中不存在的 Scenario ID
- WHEN x-dev 启动前校验
- THEN 执行停止，返回 `CONTRACT_DRIFT/REFERENCE_RESOLVES`，不生成伪完成 dev-report
- 验证：auto

### AC5：输入指纹变化

- GIVEN route decision 已生成，随后上游 checklist 内容发生变化
- WHEN x-dev 消费该决策
- THEN 返回 `CONTRACT_DRIFT/FINGERPRINT_MATCHES`，要求重新生成决策并保留旧决策
- 验证：auto

### AC6：低风险局部任务

- GIVEN 任务局部、明确、模块风险低、无不变量/公开契约/并发/不可逆状态且历史错误放行率低
- WHEN published policy 计算路由
- THEN 输出 `risk_level=low`、`profile=light`、`verify_required=true`，并确定性记录是否进入影子 QA
- 验证：auto

### AC7：高风险任务

- GIVEN 任务触及任一系统不变量或公开契约
- WHEN 路由器计算 profile
- THEN 输出 `risk_level=high`、`profile=full`、稳定 contract、q1/q2/q3 和 policy-defined reviewer/token budget
- 验证：auto

### AC8：风险输入缺失

- GIVEN task 的并发/状态风险字段缺失
- WHEN 路由器校验输入
- THEN 返回 `ROUTE_INPUT_INVALID`；若策略允许补全式评估，则最终只能输出 `medium + full + ROUTE_UNCERTAIN`
- 验证：auto

### AC9：影子 QA 发现低风险误判

- GIVEN light profile 被影子 QA 抽中且发现 P1 边界错误
- WHEN 影子审查收敛
- THEN 生成 `shadow_issue_found` 和 `ROUTER_UNDER_REVIEW` 输入，关联 run、decision、policy、反例与 Token；原始决策保持不变
- 验证：auto

### AC10：校准分母保护

- GIVEN 10 个低风险抽样中 8 个完成、1 个中断、1 个证据不足，完成样本中 2 个 P0/P1 漏判
- WHEN 聚合路由指标
- THEN `shadow_reviewed_low_risk=8`、`router_false_release_count=2`、`router_false_release_rate=0.25`，中断和证据不足列入 inconclusive
- 验证：auto

### AC11：候选策略输入不可比

- GIVEN baseline 与 candidate 的 signal snapshot 或预算不同
- WHEN 聚合配对结果
- THEN 样本标记 invalid，列出差异字段，不参与晋级统计
- 验证：auto

### AC12：候选降 Token 但正确性回归

- GIVEN candidate Token 更低且出现 P0 holdout 或关键不变量回归
- WHEN 应用候选策略晋级规则
- THEN candidate 状态为 `rejected`，生产仍绑定 published 策略，拒绝证据和评测 Token 可查询
- 验证：auto

### AC13：非法策略状态转换

- GIVEN `draft` 策略未完成评测
- WHEN 请求直接设为 `published`
- THEN 状态机拒绝转换并输出当前状态、所需前置状态和缺失审批/证据
- 验证：auto

### AC14：阶段中断与修复回流

- GIVEN verify 中断，随后 fix 处置关联 issue 并触发重跑
- WHEN run 账本收敛
- THEN 原 verify 事件为 `verify_interrupted`，缺失指标有原因；新 attempt 递增且引用 fix-report，历史事实均可查询
- 验证：auto

## 12. 可复跑证据契约

开发 agent 必须在 dev-report 中给出可复制执行的命令。若相应子命令尚不存在，按以下语义实现等价 CLI，并在报告中记录最终真实命令：

```bash
python3 tools/xdev.py validate <v2-spec-package>
python3 tools/xdev.py validate-pipeline-contract --manifest <pipeline-manifest> --strict --json-out <contract-result.json>
python3 tools/xdev.py route --task <task-directory> --policy <routing-policy> --json-out <route-decision.json>
python3 tools/verify.py <task-directory> --json-out <verify-result.json>
python3 tools/metrics.py router-calibration --runs <run-records> --policy-version <version> --json-out <router-calibration.json>
```

每次验收必须保存：

- 命令全文、cwd、工具版本、pipeline/policy version、repo SHA 与输入指纹。
- exit code、开始/结束时间、stdout/stderr 摘要和结构化输出路径。
- 测试总数、通过/失败/跳过数及失败用例 ID。
- AC1-AC14 与测试名的映射。
- 至少一份 clean fixture，以及 legacy read、重复真源、悬空引用、指纹变化、低风险、强制高风险、影子漏判、不可比配对和非法状态转换 fixture。

最终交付门槛：严格契约校验零 issue；AC1-AC14 全部通过；负例均产生预期稳定错误码；重复运行得到相同路由与校准结果；生产发布动作仍由用户确认。
