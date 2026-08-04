> spec_version: 2

# Pipeline 自我进化

## 需求说明

### 需求本质

把每次真实开发任务转化为可审计证据，用失败、扣分与 Token 数据驱动 pipeline 候选进化；生产版保持稳定，候选版经隔离评测、晋级门禁和可回滚发布后生效。

### 系统目标

- 以用户意图准确、实现技术正确为交付硬门槛。
- 记录每次运行、失败、扣分、候选变更和决策的证据链。
- 把优化信息集中在模型容易遗漏的边界、并发、状态与失败恢复问题。
- 在正确交付前提下，降低包含修复与重跑的总 Token。

### 范围边界

**首版包含**：

- `x-spec2 -> x-req2 -> x-dev -> x-verify -> x-qa-gate -> x-fix` 的运行账本与版本绑定。
- 失败原因、独立 grader 扣分原因及其证据、修订和回放结果的知识库。
- 知识驱动候选、配对评测、人工确认晋级、canary 与回滚。
- 正确交付质量、Token、耗时和修复轮数指标。

**延后**：

- 自动改写生产 skill、无人审批晋级、模型训练或微调。
- 跨项目云服务、组织权限系统、控制台和复杂统计平台。
- Token 金额换算；首版保留 provider 原始分桶。

### 关键约束

- 系统方案只使用 `skills/x-spec2/`；任务拆解交给 x-req2。
- 一个用户任务对应一个 `pipeline_run_id`；同一任务的返工属于该 run 的新 `stage_attempt`。
- 生产任务绑定一个已发布 pipeline 版本；候选使用隔离身份、工作区和记录。
- 原始运行事实追加保存；归因、评分与知识结论通过带版本修订演进。
- 执行 agent 无法读取 grader-only 断言；grader 无权改写运行事实。
- 正确性门槛先于 Token 比较；关键不变量或 P0 回归直接阻止晋级。
- 文档采用信息预算：只保留会改变实现、验证或决策的内容，审计明细按 ID 从运行账本和知识库读取。

### 系统不变量

- 每次生产、评测、修复和回放执行都有唯一 `pipeline_run_id`。
- 每个 run 可定位 pipeline/skill/template/validator 版本、模型和代码快照。
- 失败记录与扣分记录类型独立，并可引用同一证据。
- 未确认根因保留候选解释、置信依据和缺失证据，不能计入已确认统计。
- 候选必须关联知识条目、可证伪假设、基线版本、评测清单和回滚目标。
- 只有条件可比的 baseline/candidate 才能形成晋级证据。
- 任一生产任务创建时原子绑定路由与 pipeline 版本，执行中保持固定。

## 用户要求追溯

| U-ID | 用户原话要求 | 唯一落实位置 |
|---|---|---|
| U1 | “构建当前开发 pipeline 自我进化流程” | `Requirement: 知识驱动的候选进化` |
| U2 | “准确完成任务” | `Requirement: 正确完成门禁` |
| U3 | “正确完成任务” | `Requirement: 正确完成门禁` |
| U4 | “尽可能少消耗 token” | `Requirement: 正确交付 Token 效率` |
| U5 | “每一次进化都可审计” | `Requirement: 可比评测、晋级与回滚` |
| U6 | “有依据” | `Requirement: 知识驱动的候选进化` |
| U7 | “这些步骤都可以增删，只要你分析得对” | `Requirement: 风险与不确定性路由` |
| U8 | “别用老版本的 spec 技能了，新的叫 x-spec2” | `modules.md#模块总览` |
| U9 | “需要新增知识库” | `Requirement: 失败与扣分知识库` |
| U10 | “记录每次失败原因” | `Requirement: 失败与扣分知识库` |
| U11 | “记录……扣分原因” | `Requirement: 失败与扣分知识库` |
| U12 | “方便优化点有依据参考” | `Requirement: 知识驱动的候选进化` |

## 判断依据

| J-ID | 判断 | 依据 | 状态 | 被使用于 |
|---|---|---|---|---|
| J1 | 复用现有 metrics、verify、issue ledger 和 grading 事实，补统一 run 身份 | `pipeline-efficiency-benchmark/scripts/metrics.py`、`x-verify/scripts/verify.py`、`x-dev/scripts/xdev.py flag`、`grading.json` 已有确定性数据 | 已确认 | 运行账本、知识库、Token 效率 |
| J2 | 强模型的主要剩余风险集中于边界、竞态、状态和失败恢复，文档应提高这些信息的占比 | 用户对首版的评审；首版 417 行、13 个 Requirement、31 个 Scenario，评分 58/100 | 已确认 | 正确完成门禁、风险路由 |
| J3 | 失败与扣分需要独立建模 | 用户明确要求两者均记录；运行成功仍可能被 grader 扣分 | 已确认 | 失败与扣分知识库 |
| J4 | 稳定生产版与隔离候选版组成双环，正确性达标后再比较 Token | 用户已确认的演进方向 | 已确认 | 候选进化、配对评测与晋级 |
| J5 | 本 spec 生成本身是一条 pipeline run，返工属于同一 run 的第二次 attempt | 当前 Codex rollout 与用户确认 | 已确认 | 运行账本与版本绑定 |

## 建模覆盖声明

| 元组 | 落点 |
|---|---|
| 数据流 | `design.md#数据流`：运行事件 → 知识 → 候选 → 评测 → 决策 |
| 状态 | `design.md#状态流转`：run、知识条目、候选与发布版本的状态所有者 |
| 时序 | `design.md#并发与时序`：乱序事件、并发写入、晋级和回滚竞态 |
| 资源 | `design.md#资源与预算`：Token、执行槽位、候选工作区和评测集生命周期 |
| 不变量 | `spec.md#系统不变量` |
| 故障 | `design.md#故障与恢复`：中断、不可比评测、部分写入与回滚 |

## 验收

### Requirement: 运行账本与版本绑定

系统 SHALL 在任务开始时分配唯一 `pipeline_run_id`，以追加事件记录版本、阶段 attempt、输入输出指纹、Token、耗时、证据与终态；同一用户任务的反馈返工继续使用原 run。

依据：`J1`、`J5`

#### Scenario: 当前 spec 生成被追认并继续迭代

- **GIVEN** 首版 spec 已生成，用户随后要求评分、压缩并补知识库
- **WHEN** 系统登记这次历史运行和第二次产出
- **THEN** 两次产出归入 `prun-019f84e4-1296-7fb2-a2a1-50b391b11c1c-001` 的 attempt 1/2，各自保留 artifact hash、反馈、分数、Token 与知识引用
- 验证: auto

#### Scenario: 事件重复、乱序或在终态后到达

- **GIVEN** collector 重试同一 `event_id`、阶段事件乱序到达，或 run 终态后收到迟到证据
- **WHEN** 账本归并事件
- **THEN** 重复事件幂等，乱序事件按逻辑序列重建；冲突终态进入隔离，迟到证据以修订关联且不能静默改写已发布结果
- 验证: auto

### Requirement: 正确完成门禁

系统 SHALL 分别验证用户意图准确性与实现技术正确性，并用可复跑证据覆盖公开契约、边界、并发、状态转换和失败恢复；任一硬门禁失败都阻止交付。

依据：`U2`、`U3`、`J2`、`J4`

#### Scenario: 测试通过但意图遗漏

- **GIVEN** deterministic tests 全绿，某条用户要求缺少实现，或实现扩大了声明范围
- **WHEN** 意图门禁逐条核对 U-ID、Requirement、Scenario 和实现证据
- **THEN** run 不能进入 accepted，系统记录期望、实际差异、证据和责任阶段
- 验证: auto

#### Scenario: 顺序测试掩盖并发错误

- **GIVEN** 正常路径和顺序测试通过，两个 worker 并发写状态时会重复提交或丢失更新
- **WHEN** 正确性门禁执行对应竞态反例
- **THEN** 关键不变量失败，run 被阻止交付；最小复现进入知识库和后续 holdout
- 验证: auto

### Requirement: 失败与扣分知识库

系统 SHALL 把执行失败和 grader 扣分保存为独立、结构化、可查询的知识记录，关联 run、版本、阶段、`reason_code`、期望/实际、证据、根因状态、修复和回放结果。

依据：`U9`、`U10`、`U11`、`J1`、`J3`

#### Scenario: 失败、扣分与重评分独立留痕

- **GIVEN** run A 执行失败，run B 正常完成但被 grader 扣分，之后 rubric 升级并重评 run B
- **WHEN** 三类结果写入知识库
- **THEN** 失败、首次扣分和重评分形成独立记录，各自绑定 run、grader/rubric 版本、断言、分数影响和证据，历史终态与旧评分保持原事实
- 验证: auto

#### Scenario: 并发收集与后续根因修订

- **GIVEN** 两个 collector 同时提交同一证据指纹，后续新证据推翻初始根因
- **WHEN** 知识库处理写入和修订
- **THEN** 仅生成一个 canonical 条目，其余写入关联该条目；新结论形成版本修订，历史结论及其决策引用保持可查
- 验证: auto

### Requirement: 知识驱动的候选进化

系统 SHALL 按频率、严重度、错误放行风险、修复轮数和 Token 影响聚合已确认知识，生成关联真实证据、可证伪假设、目标指标与回归面的候选变更。

依据：`U1`、`U6`、`U12`、`J4`

#### Scenario: 问题簇生成候选

- **GIVEN** 多个 run 反复出现同类已确认边界或竞态原因
- **WHEN** 系统排序优化点
- **THEN** 候选回指涉及的知识版本与 run，声明修改范围、预期质量收益、Token 影响和可能回归，并进入隔离评测
- 验证: auto

#### Scenario: 候选缺少依据

- **GIVEN** pipeline 改动没有知识条目、真实证据或可证伪假设
- **WHEN** 请求完整评测
- **THEN** 候选保持草稿，返回缺失依据并停止占用后续评测预算
- 验证: auto

### Requirement: 可比评测、晋级与回滚

系统 SHALL 将 baseline 与 candidate 固定到同一任务、模型、仓库、权限、预算和 grader 断言，保存逐案例结果与决策包，并通过版本前置条件完成单一发布和可审计回滚。

依据：`U5`、`J4`

#### Scenario: 评测期间生产基线变化

- **GIVEN** candidate 开始配对后，另一候选已发布为新的生产版
- **WHEN** 当前评测聚合结果
- **THEN** 结果继续引用 manifest 中固定的 baseline；晋级前重新检查生产版本，基线已漂移则要求重放或明确重新基准化
- 验证: auto

#### Scenario: 两个候选并发晋级

- **GIVEN** 两个候选均基于版本 V1 通过门禁并同时请求发布
- **WHEN** 发布存储执行 compare-and-set
- **THEN** 只有一个候选把 V1 更新为新版本，另一个收到 `BASELINE_STALE` 且生产始终只有一个当前版本
- 验证: auto

#### Scenario: Canary 回滚与新任务并发

- **GIVEN** V2 canary 触发回滚，同时有新任务开始创建
- **WHEN** 路由原子切回 V1
- **THEN** 已创建任务继续绑定其原版本，切换提交后的新任务全部绑定 V1，不存在未绑定或混合版本 run
- 验证: auto

### Requirement: 正确交付 Token 效率

系统 SHALL 以通过意图、正确性和风险门禁的交付数归一化生产 Token，计入 dev、verify、QA、fix 与重跑；grader/collector 等进化成本单列为 `evolution_eval_tokens`。

依据：`U4`、`J1`、`J4`

#### Scenario: 多轮修复后交付

- **GIVEN** 一个任务经历两轮 fix 和重跑后正确交付，另一个低 Token 任务未通过正确性门禁
- **WHEN** 计算 `delivery_tokens_to_accepted`
- **THEN** 两个 run 的生产 Token 均计入总消耗，只有正确任务进入 accepted 分母，且可下钻到阶段和 attempt
- 验证: auto

#### Scenario: 分层评测提前失败

- **GIVEN** 候选在静态校验或目标反例阶段已违反关键契约
- **WHEN** 评测策略提前停止
- **THEN** 后续回放不再执行，已消耗资源完整计入 `evolution_eval_tokens`，拒绝依据可追溯
- 验证: auto

### Requirement: 风险与不确定性路由

系统 SHALL 使用版本化策略，按需求不确定性、影响范围、不变量触达、并发/不可逆状态和历史错误放行率选择建模深度、验证强度、reviewer 与 Token 预算，并用影子 QA 校准轻量路径。

依据：`U7`、`J2`

#### Scenario: 轻量路径被影子 QA 击穿

- **GIVEN** 局部任务被路由到轻量路径，影子 QA 发现 P0/P1 边界问题
- **WHEN** 校准路由策略
- **THEN** 该误判形成知识条目和回放案例，候选策略提高同类任务风险权重；原策略版本和当时决策保持可查
- 验证: auto

#### Scenario: 高风险并发任务

- **GIVEN** 任务触及公开契约、共享状态、并发写入或不可逆操作
- **WHEN** 路由计算执行 profile
- **THEN** profile 要求稳定 spec/task contract、deterministic verify、独立意图/正确性/证据审查及竞态反例预算
- 验证: auto
