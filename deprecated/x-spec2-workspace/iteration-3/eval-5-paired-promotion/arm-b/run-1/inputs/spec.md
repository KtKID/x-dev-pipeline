> spec_version: 2

# Pipeline 自我进化

## 需求说明

### 需求本质

让 x-dev-pipeline 把每次真实开发执行转化为可追溯证据，持续识别影响任务准确性、技术正确性和 Token 效率的原因，以隔离候选、配对回放、证据晋级和可回滚发布完成自我进化。

### 系统目标

- 收敛 x-spec2、x-req2、x-dev、x-verify、x-qa-gate 与 x-fix 的生产者/消费者契约，使同一任务在所有阶段使用一致的需求、风险、证据和状态语义。
- 为每次生产执行和评测执行分配唯一 `pipeline_run_id`，记录版本、输入输出指纹、阶段状态、真实 Token、耗时、证据和最终结果。
- 分别判定任务的意图准确性与技术正确性，以关键不变量零回归为硬门槛。
- 建立优化知识库，结构化沉淀每次失败原因、独立评分的扣分原因、根因结论、证据、修复与回放结果。
- 依据知识库聚合高频、高严重度和高 Token 影响问题，生成可追溯的优化点与候选变更假设。
- 在相同任务、模型、代码快照、权限和预算下对当前版与候选版执行隔离配对回放，由独立 grader 评分。
- 以正确交付为前提衡量 Token 效率，降低每个最终正确任务经历开发、验证、审查、修复和重跑后的总 Token。
- 为每次候选晋级、拒绝和回滚保存完整依据，使任一生产结果都能追溯到当时生效的 pipeline 版本。
- 根据风险与不确定性选择所需的建模、验证和审查强度，并通过低风险影子审查持续校准路由质量。

### 范围边界

**包含**：

- 当前主流程 `x-spec2 -> x-req2 -> x-dev -> x-verify -> x-qa-gate -> x-fix` 的统一阶段契约、版本绑定和路由策略。
- `tools/req.py`、`tools/verify.py`、`tools/xdev.py`、`tools/metrics.py` 已有确定性能力的复用与全 pipeline 扩展。
- 生产运行、评测运行、修复回流和候选回放的统一身份、阶段事件与关联关系。
- 失败原因、扣分原因、根因、严重度、证据、修复、复审和回放结果的优化知识库。
- 从知识条目聚类、排序和生成优化假设的证据链。
- pipeline/skill/template/validator/路由策略的版本化候选、配对评测、晋级、拒绝、canary 与回滚记录。
- 意图准确率、技术正确率、错误放行率、首次通过率、修复轮数、`delivery_tokens_to_accepted` 与 `evolution_eval_tokens` 的计算。
- Codex 真实 Token 与时长采集；后续 provider 通过独立适配器接入同一运行事实契约。

**排除/延后**：

- 首版自动修改生产 skill 或在生产目录原地自更新；候选版本在隔离空间生成和评测。
- 首版无人审批的生产晋级；候选达到策略门槛后生成晋级建议，由用户确认发布。
- 模型训练、微调、权重更新和外部模型供应商的运行时实现。
- 通用知识管理、自然语言百科和与 pipeline 优化无关的长期记忆。
- 首版复杂统计显著性平台；先支持可复核的配对样本、重复运行和明确样本量。
- 首版跨项目云端共享、组织级权限系统和可视化控制台。
- Token 金额换算；保留 provider Token 分桶和总量，金额策略后续独立接入。

### 关键约束

- 新系统方案只使用 `skills/x-spec2/` 的 V2 契约，产物固定为 `spec.md`、`modules.md` 和按需 `design.md`；任务拆解交给 x-req2。
- 当前 `xreq-spec-driven` 与 `xdev-task-scoped-verify` 仍处于 active 迁移期；首个落地阶段需要先收敛主流程契约，避免迁移漂移进入观测与知识数据。
- 生产运行只绑定一个已发布 pipeline 版本；候选版本使用独立身份、独立产物和独立运行记录。
- 原始运行事实采用追加语义保存；失败归因、评分、知识条目、优化假设和晋级判断作为带版本的派生记录保存。
- 执行 agent 只接收任务和执行上下文；评分规则与发布策略在独立评分和判断阶段读取。
- 失败原因与扣分原因使用两个明确记录类型：前者描述执行或产物失败，后者描述 grader 断言、期望、实际结果和分数影响。
- 每条知识记录至少关联一个真实 `pipeline_run_id` 和一份可定位证据；推断结论记录置信状态，后续证据通过新修订更新。
- 每个优化候选至少回指一个知识条目、一个可证伪假设和一个目标指标；候选 diff、评测清单与最终决策保持可追溯。
- 正确性门槛采用顺序约束：关键不变量与 P0 回归为零，意图准确率和技术正确率不低于当前版，随后比较 Token 效率。
- `delivery_tokens_to_accepted` 覆盖生产交付链上的开发、verify、QA、fix 和重跑 Token；grader/collector 等进化评测成本单独记录为 `evolution_eval_tokens`。
- 配对回放固定任务快照、模型、仓库 SHA、工具权限、预算和 grader 断言；输入不可比的样本进入无效状态。
- 风险与不确定性路由采用可版本化策略；低风险路径保留配置化影子 QA 样本，用于测量路由错误放行率。
- 知识库的物理存储、索引实现、保留期和访问控制在模块设计阶段确定；逻辑上的追加记录、证据关联和历史可追溯保持稳定。

### 系统不变量

- 每次生产、评测、修复和回放执行都拥有唯一 `pipeline_run_id`；所有阶段事件、报告、知识条目和评测结果通过该标识关联。
- 每个生产任务都能定位到唯一已发布 pipeline 版本、skill/template/validator 版本和代码快照。
- 原始输入指纹、阶段事实、Token、耗时、命令结果和 grader 原始断言结果保持不可变；更正通过追加修订表达。
- 失败原因与扣分原因保持独立记录并共享证据引用；同一次运行可以同时存在执行成功、质量扣分和候选拒绝结果。
- 根因归属指向问题最早进入证据链的阶段；证据不足时状态保持“待确认”，并保存当前推断和置信依据。
- 每个进入评测的候选版本都关联知识条目、变更假设、变更范围、基线版本、回放清单和回滚目标。
- 执行阶段无法读取 grader-only 规则；独立 grader 无权改写原始运行事实。
- 当前版与候选版只有在任务、模型、仓库、权限、预算和评分断言可比时才形成有效配对结果。
- 任一关键不变量或 P0 holdout 回归都会阻止候选晋级；Token 降低无法覆盖正确性回归。
- `delivery_tokens_to_accepted` 只把最终满足意图准确性、技术正确性与当前风险门禁的任务计入分母。
- 知识库中的优化建议必须能回溯到原始运行、失败/扣分记录和证据；无来源建议保持候选草稿状态。
- 新版 x-spec2 是本需求包和后续系统级方案的唯一建模入口；旧版 spec skill 不参与本流程。

## 用户要求追溯

| U-ID | 用户原话要求 | 对应目标 | 落实位置 |
|---|---|---|---|
| U1 | “我想构建当前开发pipeline自我进化流程” | `证据驱动的自我进化闭环` | `spec.md#requirement-证据驱动的自我进化闭环` |
| U2 | “目标是准确完成任务” | `意图准确性门禁` | `spec.md#requirement-意图准确性门禁` |
| U3 | “正确完成任务” | `技术正确性门禁` | `spec.md#requirement-技术正确性门禁` |
| U4 | “尽可能少消耗token” | `正确交付的 Token 效率` | `spec.md#requirement-正确交付的-token-效率` |
| U5 | “每一次进化都可审计” | `可审计晋级与回滚` | `spec.md#requirement-可审计晋级与回滚` |
| U6 | “有依据” | `知识驱动的优化依据` | `spec.md#requirement-知识驱动的优化依据` |
| U7 | “这些步骤都可以增删，只要你分析得对” | `风险与不确定性路由` | `spec.md#requirement-风险与不确定性路由` |
| U8 | “别用老版本的spec技能了，新的叫x-spec2” | `V2 方案与任务交接` | `spec.md#requirement-v2-方案与任务交接` |
| U9 | “需要新增知识库” | `失败与扣分知识库` | `spec.md#requirement-失败与扣分知识库` |
| U10 | “记录每次失败原因” | `失败与扣分知识库` | `spec.md#requirement-失败与扣分知识库` |
| U11 | “记录……扣分原因” | `失败与扣分知识库` | `spec.md#requirement-失败与扣分知识库` |
| U12 | “方便优化点有依据参考” | `知识驱动的优化依据` | `spec.md#requirement-知识驱动的优化依据` |

## 判断依据

| J-ID | 判断 | 来源类型 | 证据或推断说明 | 确认状态 |
|---|---|---|---|---|
| J1 | 当前 V2 task、verify 和 QA 消费契约仍处于迁移期，统一协议需要先于观测和进化数据落地 | 仓库事实 | `repo:openspec/changes/xreq-spec-driven/proposal.md` 与 `repo:openspec/changes/xdev-task-scoped-verify/proposal.md` 均为 active；`repo:skills/x-dev/SKILL.md` 已按 checklist `risk:` 路由，`repo:skills/x-qa-gate/SKILL.md` 正文仍读取旧位置和旧章节 | 已确认 |
| J2 | verify 负责可复跑事实，QA 负责判断事实是否足以信任改动，两类结果需要分别记录 | 仓库事实 | `repo:skills/x-verify/SKILL.md` 运行确定性 verify 引擎；`repo:skills/x-qa-gate/SKILL.md` 分 q1-intent、q2-correctness、q3-evidence 审查 | 已确认 |
| J3 | 现有 metrics 已具备真实 Token、duration、独立 grading 和 paired aggregate，可复用为全 pipeline 观测与评测基础 | 仓库事实 | `repo:tools/metrics.py` 已实现 Codex source、measurement 和 `aggregate-spec2`；`repo:openspec/changes/xspec2-evaluation-metrics/design.md` 固定 rubric 隔离与可比配对规则 | 已确认 |
| J4 | 现有 issue ledger、verify/fix 报告和 grading expectation 能作为知识库原始输入，当前缺少跨来源统一身份和原因模型 | 仓库事实 | `repo:tools/xdev.py` 的 `flag` 生成 `issue-<n>`；task `reports/` 保存 verify/QA/fix 证据；`grading.json` 保存 expectation、passed 与 evidence | 已确认 |
| J5 | 失败原因和扣分原因需要独立建模，因为运行可以成功结束并同时被独立 grader 扣分 | 用户确认 | 用户明确要求同时记录“每次失败原因”和“扣分原因”；现有 x-spec2 pilot 存在运行完成且部分 expectation 为 false 的样本 | 已确认 |
| J6 | 优化目标采用正确性硬门槛后比较 `delivery_tokens_to_accepted`，可避免低成本错误执行获得优势 | 用户确认 | 用户同意“正确性优先、每个正确交付的完整 Token 成本”方案；现有 pilot 同时出现更高通过率与更高原始 Token，说明两项需要按门槛顺序判断 | 已确认 |
| J7 | 自我进化使用稳定生产版和隔离候选版双环结构，候选通过配对回放后再晋级 | 用户确认 | 用户已同意生产执行环与离线进化环方案，并授权开始 x-spec2 建模 | 已确认 |
| J8 | 低风险任务采用轻量路径并保留影子 QA 抽样，可以降低常态 Token，同时持续估计路由错误放行率 | 用户确认 | 用户同意风险路由、Q0/Q1 轻量路径和低风险影子审查方向；具体抽样比例进入可版本化策略 | 已确认 |
| J9 | 知识条目采用追加修订语义，能够同时保护审计历史和后续根因纠正 | LLM 推断 | 根因会随修复、复审和回放证据更新；覆盖旧结论会破坏“每次进化可审计”的用户目标 | 待确认 |
| J10 | 首版生产晋级由用户确认，自动候选生成和无人审批晋级延后，可以先验证证据链与回滚能力 | 暂定默认 | 用户要求自我进化与审计，尚未授权候选自动改写和无人审批发布；保守发布边界减少 pipeline 自身失控风险 | 待确认 |
| J11 | 知识库首版可以采用仓库本地持久化，具体选择 JSONL、SQLite 或两者组合需要在模块设计时依据查询与并发需求决定 | 待确认项 | 当前仓库已有 Markdown/JSON 报告和标准库 Python 工具，尚无统一数据库依赖或并发写入约束 | 待确认 |
| J12 | 配对评测采用逐级扩展：静态检查、目标反例、重复目标集、相关回归、隐藏 holdout、canary，可以在早期失败时停止并节省评测 Token | LLM 推断 | 当前 metrics pilot 已证明单一 paired run 的链路，分层回放能让明显失败候选尽早退出 | 待确认 |

## 建模覆盖声明

| 元组 | 落点或不适用理由 |
|---|---|
| 数据流 | `design.md#数据流`：生产阶段事件进入运行账本，失败/扣分进入知识库，知识条目驱动候选与评测 |
| 状态 | `design.md#状态流转`：生产 run、知识条目、候选版本、评测和晋级分别拥有状态所有者 |
| 时序 | `design.md#时序`：阶段事件顺序、失败回流、配对回放、grader 隔离、晋级与 canary 顺序影响结果 |
| 资源 | `design.md#资源`：执行槽位、Token 预算、候选工作区、评测数据集和知识索引具有生命周期与容量约束 |
| 不变量 | `spec.md#系统不变量`：版本绑定、证据不可变、评分隔离、正确性硬门槛与知识追溯 |
| 故障 | `design.md#故障与恢复`：阶段中断、账本写入失败、知识归因待确认、配对不可比、grader 失败和 canary 回滚 |

## 验收

### Requirement: 证据驱动的自我进化闭环

系统 SHALL 将已发布 pipeline 的真实运行、失败/扣分知识、优化假设、隔离候选、可比配对回放、晋级判断和生产版本绑定连接成完整闭环，并让每次状态转换都能回指原始证据。

依据：`U1`、`J7`

#### Scenario: 一次真实失败驱动候选进化

- **GIVEN** 已发布 pipeline 的真实任务产生可确认失败或 grader 扣分
- **WHEN** 系统完成知识沉淀、优化点排序、候选评测和晋级判断
- **THEN** 可从最终决策逐级追溯候选版本、配对结果、优化假设、知识条目和原始 `pipeline_run_id`，每一环都有明确状态和证据
- 验证: auto

#### Scenario: 当前没有合格候选

- **GIVEN** 新候选缺少依据、配对不可比或未达到正确性与 Token 晋级门槛
- **WHEN** 进化控制面收敛本轮结果
- **THEN** 当前已发布版本继续服务生产，候选拒绝原因和已消耗评测资源保持可查询，后续候选可复用对应知识与反例
- 验证: auto

### Requirement: 统一流水线契约

系统 SHALL 为 x-spec2、x-req2、x-dev、x-verify、x-qa-gate 与 x-fix 定义唯一的阶段输入、输出、风险来源、Requirement/Scenario 回指、证据和状态契约，并以确定性校验阻止生产者/消费者漂移进入运行数据。

依据：`U1`、`J1`、`J2`

#### Scenario: 当前阶段契约完成收敛

- **GIVEN** V2 spec、task checklist、dev-report、verify JSON、QA issue 和 fix 处置产物均存在
- **WHEN** 运行 pipeline 契约校验
- **THEN** 每个消费者读取其上游真实产物字段，risk、Requirement、Scenario、状态和报告路径只有一个有效来源，校验结果为零 issue
- 验证: auto

#### Scenario: 消费者继续读取旧字段

- **GIVEN** 某个 stage skill 继续读取已退役 README、旧 spec 章节或错误 risk 位置
- **WHEN** 运行 pipeline 契约校验
- **THEN** 校验返回可定位的 `CONTRACT_DRIFT`，指出生产者、消费者、缺失字段和证据路径，并阻止该版本进入基线
- 验证: auto

### Requirement: 版本绑定与运行观测

系统 SHALL 为每次生产、评测、修复与回放执行生成唯一 `pipeline_run_id`，记录任务快照、pipeline 版本、skill/template/validator 版本、模型、代码 SHA、阶段事件、输入输出指纹、Token、耗时、证据和终态。

依据：`U1`、`U5`、`J3`、`J7`

#### Scenario: 完整生产任务形成运行记录

- **GIVEN** 一个任务依次经过契约、开发、verify、风险审查和交付
- **WHEN** 任务进入最终终态
- **THEN** 可通过 `pipeline_run_id` 按顺序查询所有阶段、版本、输入输出指纹、真实 Token、耗时、证据和最终门禁结果
- 验证: auto

#### Scenario: 阶段执行中断

- **GIVEN** 某个阶段因进程退出、工具错误或用户中断停止
- **WHEN** 运行账本收敛该次执行
- **THEN** 已发生事件保持可查询，run 标记明确的中断状态和最后成功阶段，缺失指标记录缺失原因
- 验证: auto

### Requirement: 意图准确性门禁

系统 SHALL 根据用户要求、归属 Requirement、Scenario、范围边界和公开契约判断实现是否准确完成目标，并阻止意图遗漏、范围漂移和错误需求解释进入正确交付集合。

依据：`U2`、`J2`、`J6`

#### Scenario: 实现满足全部承接意图

- **GIVEN** task 承接的 Requirement 和 Scenario 均有实现与证据
- **WHEN** q1-intent 或独立 grader 执行意图对照
- **THEN** 每条用户要求都能追溯到通过的 Requirement/Scenario 和实现证据，意图准确性门禁通过
- 验证: auto

#### Scenario: 测试通过但遗漏用户要求

- **GIVEN** deterministic verify 全部通过，但实现遗漏一条用户要求或扩大了声明范围
- **WHEN** 执行意图准确性门禁
- **THEN** 任务被阻止交付并生成带 Requirement、实际差异和证据的扣分/失败记录
- 验证: auto

### Requirement: 技术正确性门禁

系统 SHALL 结合 deterministic verify、边界与失败路径审查、状态/并发/幂等检查和证据真实性审查，判定实现是否在声明场景与关键不变量下正确运行。

依据：`U3`、`J2`、`J6`

#### Scenario: 正常路径与失败路径均正确

- **GIVEN** 实现覆盖正常、非法输入、边界、失败恢复和相关状态路径
- **WHEN** verify 与当前风险要求的 q2-correctness/q3-evidence 完成
- **THEN** 所有自动 Scenario 可复跑通过，关键不变量零违规，证据能够击穿已知错误实现，技术正确性门禁通过
- 验证: auto

#### Scenario: 证据通过但边界实现错误

- **GIVEN** verify 命令退出为零，但边界条件、状态恢复或并发路径存在可复现错误
- **WHEN** 正确性审查发现该反例
- **THEN** 任务被阻止交付，错误被归因到最早引入阶段，并固化为后续回放案例
- 验证: auto

### Requirement: 失败与扣分知识库

系统 SHALL 将每次执行失败和每条 grader 扣分保存为结构化、可查询、可修订的知识记录，并关联原始 run、pipeline 版本、阶段、原因分类、证据、根因、修复、复审与回放结果。

依据：`U9`、`U10`、`U11`、`J4`、`J5`、`J9`、`J11`

#### Scenario: Pipeline 阶段失败形成失败知识

- **GIVEN** spec、req、dev、verify、QA、fix 或评测阶段进入失败终态
- **WHEN** 失败记录写入知识库
- **THEN** 条目包含唯一知识 ID、`pipeline_run_id`、阶段、pipeline 版本、`reason_code`、现象、根因状态、严重度、证据引用、受影响产物和后续处置状态
- 验证: auto

#### Scenario: 独立 grader 产生扣分

- **GIVEN** 一次 run 正常完成且 grader 的某条 expectation 为 false
- **WHEN** 扣分结果写入知识库
- **THEN** 条目包含 grader/rubric 版本、断言 ID、期望、实际结果、分数或严重度影响、证据和关联 run，并与执行失败记录保持独立类型
- 验证: auto

#### Scenario: 新证据修正旧根因

- **GIVEN** 既有知识条目的根因为“待确认”或后续回放推翻原判断
- **WHEN** 写入带新证据的根因修订
- **THEN** 最新视图展示当前判断，历史版本和原始证据继续可查询，相关优化决策能够定位当时使用的知识版本
- 验证: auto

### Requirement: 可定位失败归因

系统 SHALL 使用稳定 `reason_code` 和证据链把问题归属到最早引入错误的阶段，区分发现阶段、责任阶段、根因状态和置信依据。

依据：`U6`、`U10`、`J1`、`J4`

#### Scenario: QA 发现 dev 阶段实现缺陷

- **GIVEN** q2-correctness 在 QA 阶段发现一个由 dev 实现引入的边界错误
- **WHEN** 执行失败归因
- **THEN** 知识条目记录 `detected_stage=qa`、`origin_stage=dev`、对应 reason code、反例和代码证据
- 验证: auto

#### Scenario: 根因证据不足

- **GIVEN** 同一问题可能来自 spec 歧义、req 拆解或 dev 误解，现有证据无法排除合理备选
- **WHEN** 执行失败归因
- **THEN** 根因状态保持“待确认”，记录候选原因、缺失证据和下一验证动作，系统不将该推断计入已确认根因统计
- 验证: auto

### Requirement: 知识驱动的优化依据

系统 SHALL 按频率、严重度、错误放行风险、修复轮数和 Token 影响聚合知识条目，生成可追溯的优化点；每个候选变更必须声明目标知识条目、可证伪假设、预期指标和潜在回归面。

依据：`U6`、`U12`、`J4`、`J12`

#### Scenario: 高频原因生成优化点

- **GIVEN** 多次运行出现相同 reason code 和相同责任阶段，并具有已确认根因
- **WHEN** 查询 pipeline 优化建议
- **THEN** 系统按影响排序返回问题簇、涉及 run、累计扣分/失败次数、Token 损失、证据和建议优化边界
- 验证: auto

#### Scenario: 候选缺少知识依据

- **GIVEN** 一个 pipeline 改动未关联知识条目、真实证据或可证伪假设
- **WHEN** 请求进入正式配对评测
- **THEN** 候选保持草稿状态，返回缺失的依据字段并停止占用完整评测预算
- 验证: auto

### Requirement: 可比配对回放

系统 SHALL 使用相同任务快照、模型、仓库 SHA、工具权限、预算和评分断言，对当前版与候选版执行隔离配对回放，并由执行阶段不可见的独立 grader 生成质量结果。

依据：`U2`、`U3`、`U5`、`J3`、`J7`、`J12`

#### Scenario: 当前版与候选版条件一致

- **GIVEN** baseline 与 candidate 的评测 manifest 具有相同任务、模型、repo、权限、预算和 grader 断言
- **WHEN** 两个隔离 run 完成并评分
- **THEN** 系统生成逐案例配对结果，包含意图、正确性、失败、扣分、Token、耗时和修复轮数差异
- 验证: auto

#### Scenario: 配对输入不可比

- **GIVEN** 两个 run 的任务哈希、模型、repo SHA、权限、预算或评分断言任一不一致
- **WHEN** 聚合配对结果
- **THEN** 样本进入无效状态并列出差异字段，不参与晋级统计
- 验证: auto

#### Scenario: 分层评测提前发现失败

- **GIVEN** 候选在静态校验或目标反例阶段已违反关键契约
- **WHEN** 分层回放策略执行
- **THEN** 系统记录拒绝依据并停止后续大规模回归与 holdout，已消耗 Token 计入 `evolution_eval_tokens`
- 验证: auto

### Requirement: 可审计晋级与回滚

系统 SHALL 为每个 pipeline 候选保存触发知识、假设、版本清单、变更 diff、评测 manifest、配对结果、策略版本、决策理由、审批和回滚目标，并只让满足当前晋级策略的候选成为已发布版本。

依据：`U5`、`U6`、`J7`、`J10`

#### Scenario: 候选满足晋级门槛

- **GIVEN** 候选修复目标知识案例、关键 holdout 零回归、整体准确性和正确性不低于 baseline，Token 指标满足策略
- **WHEN** 用户确认晋级建议
- **THEN** 候选获得唯一已发布版本，生产路由开始绑定该版本，完整决策包和上一回滚目标保持可查询
- 验证: manual

#### Scenario: 候选降低 Token 但引入正确性回归

- **GIVEN** 候选 `delivery_tokens_to_accepted` 低于 baseline，但出现关键不变量、P0 holdout 或正确性回归
- **WHEN** 应用晋级策略
- **THEN** 候选被拒绝，决策记录列出阻断案例、知识条目和配对证据，生产版本保持原绑定
- 验证: auto

#### Scenario: Canary 发现生产退化

- **GIVEN** 已晋级版本在 canary 中触发策略定义的错误放行率、失败率或 Token 退化门槛
- **WHEN** 执行回滚策略
- **THEN** 新生产任务恢复绑定上一稳定版本，canary 运行和回滚原因写入知识库与版本决策记录
- 验证: auto

### Requirement: 正确交付的 Token 效率

系统 SHALL 分别计算生产交付成本和进化评测成本，以满足意图准确性、技术正确性和风险门禁的最终交付数归一化生产 Token，并保留 provider Token 分桶与阶段归属。

依据：`U4`、`J3`、`J6`、`J12`

#### Scenario: 任务经过两轮修复后正确交付

- **GIVEN** 一个任务经历 dev、verify、QA、两轮 fix 和重跑后通过全部门禁
- **WHEN** 计算生产 Token 效率
- **THEN** `delivery_tokens_to_accepted` 包含该任务所有生产阶段与修复回流 Token，分母计为一个正确交付
- 验证: auto

#### Scenario: 低 Token 运行被错误放行检查拦截

- **GIVEN** 一个运行消耗较少 Token，但未满足意图准确性或技术正确性
- **WHEN** 计算 Token 效率与晋级指标
- **THEN** 该运行的 Token 保持计入总消耗，运行不进入 accepted 分母，并形成失败或扣分知识条目
- 验证: auto

#### Scenario: 独立 grader 和 collector 产生评测成本

- **GIVEN** 候选配对回放需要 executor、grader 和 collector
- **WHEN** 汇总进化评测资源
- **THEN** executor 的交付效率指标与 grader/collector 的 `evolution_eval_tokens` 分开显示，同时提供本次进化总 Token
- 验证: auto

### Requirement: 风险与不确定性路由

系统 SHALL 使用版本化路由策略，根据任务风险、需求不确定性、模块影响、不变量触达和历史错误放行信号选择契约深度、QA 维度、reviewer 数量、影子审查比例和 Token 预算。

依据：`U7`、`J6`、`J8`

#### Scenario: 低风险局部任务走轻量路径

- **GIVEN** 任务局部、需求明确、模块风险低、未触及系统不变量且历史同类错误放行率低
- **WHEN** 路由策略计算执行 profile
- **THEN** 系统选择轻量契约、dev 和 deterministic verify，并按策略决定交付或进入影子 QA
- 验证: auto

#### Scenario: 高风险任务执行完整审查

- **GIVEN** 任务触及系统不变量、高风险模块、公开契约、并发或不可逆状态
- **WHEN** 路由策略计算执行 profile
- **THEN** 系统要求稳定 spec、task contract、verify 与独立 q1-intent/q2-correctness/q3-evidence 审查
- 验证: auto

#### Scenario: 影子 QA 发现低风险误判

- **GIVEN** 一个轻量路径任务在影子 QA 中发现 P0/P1 问题
- **WHEN** 路由校准任务运行
- **THEN** 该事件写入 `ROUTER_UNDER_REVIEW` 知识条目，更新候选路由策略的依据，并进入后续配对回放
- 验证: auto

### Requirement: V2 方案与任务交接

系统 SHALL 使用 x-spec2 的 `spec.md`、`modules.md` 和按需 `design.md` 作为系统方案唯一真源，并由 x-req2 从已确认 Requirement/Scenario 和稳定模块拆分 `docs/spec/<spec-name>/tasks/<task-name>/` 任务。

依据：`U8`、`J1`

#### Scenario: Pipeline 自我进化方案完成 V2 建模

- **GIVEN** 用户已确认本 `spec.md`
- **WHEN** x-spec2 完成模块和动态模型设计
- **THEN** 需求包只包含非空 `spec.md`、`modules.md` 和适用的 `design.md`，通过 `python3 tools/xdev.py validate docs/spec/pipeline-self-evolution` 且识别为 spec2
- 验证: auto

#### Scenario: 首个任务交给 x-req2

- **GIVEN** 运行观测相关模块状态为“可进入 x-req”
- **WHEN** 拆分首个 `pipeline-run-observability` task
- **THEN** task 写入 `docs/spec/pipeline-self-evolution/tasks/pipeline-run-observability/`，逐行回指本 spec 的 Requirement，旧版 spec skill 和旧 task 根目录均不参与
- 验证: auto
