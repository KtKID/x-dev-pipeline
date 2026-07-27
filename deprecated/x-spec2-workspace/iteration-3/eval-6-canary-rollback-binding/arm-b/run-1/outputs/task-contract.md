# Task Contract: Canary 回滚与生产任务版本绑定

## 1. 目标

实现生产任务创建、canary 路由、版本切换和回滚之间的强一致绑定：每个生产任务在创建事务提交时选择并永久记录一个已发布 pipeline 版本；同一任务后续的 dev、verify、QA、fix、重试和重放均从该绑定解析完整 skill/template/validator 清单；路由切换与任务创建并发时，以提交成功的路由修订号形成唯一、可审计的先后关系。

交付结果需要满足以下核心结论：

- 任务创建与版本绑定构成一个原子提交。
- 路由变更通过单调递增的 `route_revision` 发布。
- rollback 修订提交后创建的新任务只绑定回滚目标版本。
- rollback 修订提交前已绑定的任务继续使用原版本直至终态。
- 幂等重试返回首次创建的任务及其原绑定。
- 每次选择、切换、回滚和派发都能回指版本、路由修订、操作者、原因与证据。

对应规范：`Requirement: 版本绑定与运行观测`、`Requirement: 可审计晋级与回滚`、`Requirement: 证据驱动的自我进化闭环`。

## 2. 范围

### 2.1 包含

- 已发布 pipeline 版本及其不可变组件清单。
- 生产路由的稳定版、canary 版、流量比例和路由修订。
- 生产任务创建时的确定性 canary 选择与不可变版本绑定。
- 稳定版切换、canary 开启、canary 晋级和 canary 回滚。
- 路由切换与任务创建并发时的线性化语义。
- 创建、派发和执行启动之间的事务 outbox 与幂等恢复。
- `pipeline_run_id`、任务绑定和阶段事件的版本追溯。
- 回滚决策记录、知识记录入口和可复跑并发测试。

### 2.2 排除

- 候选生成、配对回放和 grader 的内部实现。
- 自动修改生产 skill/template/validator。
- 无人审批的版本晋级。
- 已创建任务的隐式中途换版。
- 回滚时自动取消、迁移或重跑已经开始的任务。
- canary 指标计算算法；本任务只消费外部给出的回滚触发和原因。
- 版本制品物理删除和长期保留策略；本任务只保证被任务引用的版本持续可解析。

## 3. 显式假设

1. 系统具有支持事务和唯一约束的一致性存储；任务、绑定、审计事件和 outbox 可在同一数据库事务内提交。
2. 生产路由按一个明确作用域保存，例如 project、tenant 或 pipeline。本文统一记为 `route_scope`；同一作用域只有一条当前路由记录。
3. `task_id` 在路由决策前生成且全局唯一；客户端提供 `idempotency_key`，服务端在 `route_scope + idempotency_key` 上建立唯一约束。
4. pipeline 版本内容不可变。版本的 skill/template/validator 标识、内容指纹和代码快照在发布时固化。
5. 每个路由修订的稳定版与 canary 版都处于 `PUBLISHED`，且制品已通过可读取检查。
6. canary 分配采用 `hash(route_scope, task_id, canary_salt) mod 10000 < canary_bps`；相同任务与 salt 始终得到相同结果。
7. `route_revision` 在作用域内单调递增；数据库提交顺序定义任务创建与路由切换的线性化顺序。墙钟时间只用于展示。
8. 回滚目标是当前 canary 路由记录中保存的上一稳定版本。控制面通过 `expected_route_revision` 执行 compare-and-swap。
9. 一个业务任务跨修复轮次保持同一 `task_id` 和版本绑定。需要用新版本重跑时，调用方创建带 `supersedes_task_id` 的新任务。
10. 队列提供至少一次投递；消费者以 `task_id` / `pipeline_run_id` 去重，任务绑定是执行版本的唯一来源。

假设 1 无法满足时，采用具备等价线性化语义的单写者/一致性协调方案；实现说明必须给出故障窗口和证明。其余实现与验收仍遵守本契约的不变量。

## 4. 状态与数据契约

### 4.1 PipelineVersion

| 字段 | 约束 |
|---|---|
| `pipeline_version_id` | 全局唯一、不可复用 |
| `publish_state` | `CANDIDATE -> PUBLISHED -> RETIRED`；只有 `PUBLISHED` 可进入新路由 |
| `manifest` | skill/template/validator 版本、代码 SHA、内容指纹的完整清单 |
| `manifest_hash` | 对规范化 manifest 计算，发布后不可变 |
| `published_at` / `published_by` | 审计必填 |
| `supersedes_version_id` | 可空；晋级链路使用 |
| `rollback_target_version_id` | 晋级时必填，指向已验证稳定版 |

`RETIRED` 表示停止承接新任务。任何仍被任务绑定引用的版本及 manifest 保持可解析。

### 4.2 ProductionRoute

| 字段 | 约束 |
|---|---|
| `route_scope` | 主键作用域 |
| `route_revision` | 每次控制面变更原子递增 |
| `mode` | `STABLE_ONLY` 或 `CANARY` |
| `stable_version_id` | 必填、指向 `PUBLISHED` |
| `canary_version_id` | `CANARY` 时必填，且与稳定版不同 |
| `canary_bps` | `CANARY` 时为 `1..10000`；`STABLE_ONLY` 时为 `0` |
| `canary_salt` | 每次 canary 活动固定；修改 salt 需要新修订 |
| `previous_stable_version_id` | 晋级或 canary 活动期间保存可审计回滚目标 |
| `policy_version` | 产生流量决策的路由策略版本 |
| `updated_at` / `updated_by` / `reason` | 审计必填 |

有效路由组合：

- 稳定运行：`STABLE_ONLY(stable=v1, canary=null, bps=0)`。
- 开启 canary：`CANARY(stable=v1, canary=v2, bps=n)`。
- canary 回滚：新修订为 `STABLE_ONLY(stable=v1, canary=null, bps=0)`。
- canary 晋级：新修订为 `STABLE_ONLY(stable=v2, canary=null, bps=0, previous_stable=v1)`。

控制面状态变化通过追加 `RouteDecisionEvent` 审计；当前路由表只保存最新视图。

### 4.3 TaskVersionBinding

任务创建事务必须写入以下字段：

| 字段 | 约束 |
|---|---|
| `task_id` | 主键，与生产任务一一对应 |
| `route_scope` | 路由作用域 |
| `idempotency_key` | 与作用域组成唯一键 |
| `pipeline_version_id` | 不可变，指向创建时选中的 `PUBLISHED` 版本 |
| `manifest_hash` | 不可变，与版本注册表一致 |
| `route_revision` | 创建事务读取并据以决策的修订 |
| `route_mode` | 创建时的 `STABLE_ONLY` / `CANARY` 快照 |
| `route_bucket` | `stable` 或 `canary` |
| `decision_input_hash` | 对 task_id、scope、salt、bps、policy version 的规范化输入计算 |
| `bound_at` | 数据库提交时间或数据库生成时间 |
| `supersedes_task_id` | 显式换版重跑时填写 |

业务任务表、`TaskVersionBinding`、`TaskCreated` 审计事件和派发 outbox 记录属于同一创建事务。绑定字段只允许首次插入；数据库约束和应用层校验共同阻止更新。

### 4.4 PipelineRun

每次执行生成唯一 `pipeline_run_id`，并复制以下不可变引用：

- `task_id`
- `pipeline_version_id`
- `manifest_hash`
- `route_revision`
- `code_sha`

执行器只能从 `TaskVersionBinding` 解析版本。请求载荷、队列消息和调用方提供的版本字段属于一致性校验输入；出现差异时，执行进入 `BINDING_MISMATCH` 失败终态并保留证据。

### 4.5 审计事件

至少追加以下事件，事件包含唯一 `event_id`、作用域、操作者/触发者、原因、前后状态、关联证据、数据库提交序号或修订号：

- `ROUTE_CANARY_STARTED`
- `ROUTE_CANARY_UPDATED`
- `ROUTE_CANARY_PROMOTED`
- `ROUTE_CANARY_ROLLED_BACK`
- `TASK_VERSION_BOUND`
- `TASK_DISPATCHED`
- `RUN_BINDING_VERIFIED`
- `RUN_BINDING_REJECTED`

回滚事件还需记录触发指标、阈值、观测窗口、canary 版本、回滚目标、旧/新 `route_revision`、控制命令幂等键和关联知识条目 ID。原始事件保持追加语义。

## 5. 路由与版本选择算法

### 5.1 创建生产任务

1. 接收 `route_scope`、业务输入、服务端生成的 `task_id` 和调用方 `idempotency_key`。
2. 在事务内先按 `route_scope + idempotency_key` 查询既有任务；命中时直接返回原 `task_id` 与原绑定。
3. 读取并锁定当前 `ProductionRoute`，或以可证明等价的 serializable snapshot 获取当前 `route_revision`。
4. 校验稳定版、canary 版的 `publish_state=PUBLISHED`、manifest 可解析、指纹一致。
5. `STABLE_ONLY` 选择 `stable_version_id`。`CANARY` 使用固定哈希公式选择稳定版或 canary 版。
6. 同一事务插入任务、`TaskVersionBinding`、`TASK_VERSION_BOUND` 事件和派发 outbox。
7. 提交成功即为任务创建与版本绑定的线性化点；返回任务及完整绑定摘要。
8. outbox worker 在事务外投递，使用 outbox ID 去重；投递重试保持原绑定。

### 5.2 路由切换

开启 canary、调整比例、晋级和回滚都使用同一控制面写路径：

1. 接收 `expected_route_revision` 和控制命令 `idempotency_key`。
2. 在事务内锁定当前路由并校验 expected revision。
3. 校验目标版本状态、manifest 和合法状态转换。
4. 写入 `route_revision + 1` 的新路由状态与对应审计事件。
5. 提交成功即为切换线性化点。
6. 相同控制幂等键重试时返回首次结果；旧 expected revision 携带新幂等键时返回 `ROUTE_REVISION_CONFLICT`。

路由切换采用单一原子状态替换。稳定版、canary 版、比例、salt 和策略版本在同一修订中一起生效，避免组件级混合版本。

### 5.3 并发判定规则

任务创建和切换同时发生时，数据库串行化顺序给出两种合法结果：

- 任务创建事务先提交：任务保存旧 `route_revision`，并按旧路由合法绑定。后续阶段继续使用该绑定。
- 路由切换事务先提交：任务保存新 `route_revision`，并按新路由合法绑定。

canary 回滚提交形成明确切面。`route_revision > rollback_revision_before` 且创建读取到回滚后修订的任务只能绑定回滚目标稳定版。并发开始时间、API 到达时间和墙钟时间均不改变这一规则。

## 6. 不变量与原子边界

### 6.1 必须持续成立的不变量

1. 每个已提交生产任务恰好存在一条 `TaskVersionBinding`。
2. 每条绑定只引用一个完整、不可变、可解析的 `PUBLISHED` manifest。
3. 一个任务的所有生产 run 与阶段事件使用同一 `pipeline_version_id` 和 `manifest_hash`。
4. 每个绑定的版本是其 `route_revision` 所允许的稳定版或 canary 版。
5. 回滚修订之后的新任务不再获得被回滚 canary 版本。
6. 创建幂等重试保持首次 `task_id`、版本、bucket 和 route revision。
7. 路由控制命令至多产生一个新修订和一条语义审计事件。
8. 任一 route revision 表达一个完整路由快照；消费者不会观察到混合字段。
9. 已提交任务持续执行原绑定；版本切换只影响读取新修订创建的任务。
10. 任务、绑定、创建事件和 outbox 同时存在或同时缺失。
11. 所有回滚决策可追溯到被回滚版本、回滚目标、策略、触发证据和操作者。

### 6.2 原子边界

| 事务 | 同一原子提交中的记录 | 事务外动作 |
|---|---|---|
| 任务创建 | task、binding、`TASK_VERSION_BOUND`、dispatch outbox | 队列投递、执行启动 |
| 路由切换 | 新 route snapshot、revision、decision event、control idempotency result | 指标通知、知识派生、告警 |
| run 创建 | run、binding copy、`RUN_BINDING_VERIFIED` 或拒绝事件 | 阶段执行 |

控制面写入与任务创建通过同一作用域路由锁或 serializable 冲突检测排序。事务发生重试时重新读取路由；`idempotency_key` 已命中时返回原结果。

## 7. 失败恢复

| 故障 | 必须行为 | 恢复与证据 |
|---|---|---|
| 当前路由缺失或字段非法 | 创建事务失败，任务相关记录均不提交 | 返回 `ROUTE_UNAVAILABLE`，记录可定位告警 |
| 目标版本未发布、manifest 缺失或指纹不符 | 阻止路由切换或任务创建 | 返回 `VERSION_UNAVAILABLE` / `MANIFEST_MISMATCH`，保留版本和 revision |
| 任务事务在 commit 前中断 | 事务回滚 | 相同幂等键可安全重试并重新读取当前路由 |
| 任务事务已 commit、响应丢失 | 原任务与绑定保持有效 | 相同幂等键返回原任务；不得按新路由新建任务 |
| outbox 投递失败 | 任务保持 `BOUND/PENDING_DISPATCH` | 后台重试同一 outbox；重复消息由消费者去重 |
| 路由切换 commit 前失败 | 旧路由继续生效 | 同一控制幂等键可重试 |
| 路由切换 commit 后响应丢失 | 新 revision 已生效 | 同一控制幂等键返回首次切换结果 |
| 两个控制操作竞争 | 一个 expected revision 成功 | 另一操作返回 `ROUTE_REVISION_CONFLICT`，调用方基于新快照重新决策 |
| 执行消息版本与绑定不一致 | run 阻止启动 | 写入 `RUN_BINDING_REJECTED` 与 `BINDING_MISMATCH`，保留消息和绑定摘要 |
| 回滚后旧 canary 任务仍在运行 | 任务继续原绑定 | 运行记录标明 canary 版本与旧 revision；运维处置使用独立显式命令 |
| 审计/知识派生下游不可用 | 核心事务保存 outbox | 重试派生；原始 route/task 事件保持事实源 |

服务重启恢复时按 `PENDING_DISPATCH` outbox 继续派发，按绑定恢复 run；不得根据当前路由重新计算既有任务版本。

## 8. 实现 Checklist

- [ ] T1 定义 `PipelineVersion`、`ProductionRoute`、`TaskVersionBinding`、控制命令幂等记录和审计事件 schema，建立主键、外键、唯一约束与不可变字段保护。（覆盖不变量 1、2、6、7）
- [ ] T2 实现版本发布校验：manifest 完整性、内容指纹、代码 SHA、rollback target 和 `PUBLISHED` 状态。（覆盖 AC-02、AC-09）
- [ ] T3 实现单一路由控制写路径，支持 canary 开启/比例更新/晋级/回滚、expected revision CAS 和命令幂等。（覆盖 AC-04、AC-05、AC-08）
- [ ] T4 实现稳定哈希 canary 选择，固定规范化输入与测试向量，持久化 bucket 和 decision input hash。（覆盖 AC-02、AC-03）
- [ ] T5 实现任务创建事务，将 task、binding、审计事件和 dispatch outbox 原子提交；幂等查询优先返回首次结果。（覆盖 AC-01、AC-06、AC-07）
- [ ] T6 实现 route change 与 task creation 的串行化机制，证明线性化点并覆盖高并发冲突重试。（覆盖 AC-04、AC-05）
- [ ] T7 修改 run/阶段启动入口，使其只从任务绑定解析 manifest；增加载荷一致性检查和 `BINDING_MISMATCH` 终态。（覆盖 AC-07、AC-10）
- [ ] T8 实现 outbox dispatcher 与消费者去重，覆盖 commit 后响应丢失、投递失败和重复投递。（覆盖 AC-06、AC-11）
- [ ] T9 实现回滚审计字段及知识记录派生入口，保留触发指标、阈值、观测窗口、版本链和证据。（覆盖 AC-08、AC-12）
- [ ] T10 增加版本引用保护，使绑定中的 manifest 在任务和审计保留期内持续可解析。（覆盖 AC-09）
- [ ] T11 增加数据库迁移、回退说明和兼容读取策略；迁移期间已有任务需要显式生成绑定或进入可定位隔离状态。（覆盖 AC-13）
- [ ] T12 编写单元、事务、并发、故障注入和端到端测试，并保存命令、exit code、固定 seed、关键断言和产物路径。（覆盖全部 AC）

Checklist 完成要求：每项在开发报告中记录改动文件、关联 AC、验证命令和证据路径；任何合理新增假设同步写回任务报告并说明影响。

## 9. 验收用例

### AC-01 稳定版任务绑定

- GIVEN 路由 revision 10 为 `STABLE_ONLY(v1)`，v1 已发布且 manifest 可解析
- WHEN 创建生产任务 A
- THEN A、binding、审计事件和 outbox 同时提交；A 绑定 v1/revision 10/bucket stable；run 使用相同 manifest hash
- 验证：auto

### AC-02 Canary 确定性分配

- GIVEN revision 11 为 `CANARY(stable=v1, canary=v2, bps=1000, salt=s1)`
- WHEN 使用固定 task ID 测试向量创建任务并重复计算路由
- THEN bucket 与固定哈希期望一致；相同 task ID 始终得到同一版本；所有 binding 均引用 v1 或 v2 的完整 manifest
- 验证：auto

### AC-03 Canary 比例边界

- GIVEN 合法的 1、9999、10000 bps 及固定 10,000 个 task ID 数据集
- WHEN 执行路由选择
- THEN 选择规则严格符合整数阈值；0 bps 只允许 `STABLE_ONLY`；非法比例和同版 stable/canary 被拒绝
- 验证：auto

### AC-04 回滚与新任务创建并发

- GIVEN revision 20 为 `CANARY(v1,v2)`，回滚将创建 revision 21=`STABLE_ONLY(v1)`
- WHEN 至少 1,000 个任务创建事务与回滚事务通过 barrier 同时竞争，并使用固定随机 seed 重复至少 20 轮
- THEN 每个任务恰好一条 binding；revision 20 的任务只绑定 v1/v2；revision 21 的任务全部绑定 v1；不存在缺失绑定、混合 manifest、未知 revision 或重复任务
- 验证：auto

### AC-05 晋级与新任务创建并发

- GIVEN revision 30 为 `CANARY(v1,v2)`，晋级将创建 revision 31=`STABLE_ONLY(v2)`
- WHEN 任务创建与晋级同时竞争
- THEN 每个任务按其保存 revision 合法绑定；revision 31 的新任务全部绑定 v2；旧 revision 的已提交任务保持 v1/v2 原绑定
- 验证：auto

### AC-06 创建响应丢失并跨回滚重试

- GIVEN 任务 B 在 revision 40 的 canary 路由下已提交并绑定 v2，服务端响应随后丢失，revision 41 已回滚到 v1
- WHEN 客户端用相同 `route_scope + idempotency_key` 重试
- THEN 返回原 task B、v2、revision 40；任务数量、binding 数量和 outbox 语义事件数量均保持一份
- 验证：auto

### AC-07 已绑定任务跨回滚执行

- GIVEN 任务 C 已绑定 v2，尚未派发或正在执行，路由随后回滚到 v1
- WHEN C 进入 dev、verify、QA、fix 或消息被重复投递
- THEN 每个阶段继续解析 v2 与原 manifest hash；当前 v1 路由不改写 C；重复投递不创建第二个活跃 run
- 验证：auto

### AC-08 回滚命令幂等与竞争

- GIVEN 两个操作者基于同一 expected revision 发起回滚/晋级竞争
- WHEN 两个事务并发提交，并分别重试相同控制幂等键
- THEN 只产生一个后继 revision；成功命令重试返回首次结果；竞争命令得到 `ROUTE_REVISION_CONFLICT`；审计链连续且无重复语义事件
- 验证：auto

### AC-09 无效版本阻断

- GIVEN canary 或回滚目标处于 CANDIDATE/RETIRED、manifest 缺失或 hash 不匹配
- WHEN 控制面尝试发布路由或任务创建读取到非法快照
- THEN 操作以稳定 reason code 失败；不存在部分 route revision、task 或 binding；证据包含目标版本和校验差异
- 验证：auto

### AC-10 执行载荷篡改

- GIVEN 任务绑定 v1，队列消息携带 v2 或错误 manifest hash
- WHEN 执行器启动 run
- THEN run 进入 `BINDING_MISMATCH`，阶段实现不执行，原消息和 binding 摘要写入不可变证据
- 验证：auto

### AC-11 Outbox 故障恢复

- GIVEN 任务与 binding 已提交，队列暂时不可用或 worker 在发送后确认前崩溃
- WHEN worker 恢复并重试
- THEN 任务最终派发；消费者对重复消息幂等；执行仍使用原 binding；outbox 重试次数与最终状态可查询
- 验证：auto

### AC-12 回滚可审计

- GIVEN canary 指标超过已记录策略阈值
- WHEN 执行回滚
- THEN 可从回滚 revision 追溯 canary run、触发指标、策略版本、阈值、证据、canary 版本、稳定目标、操作者和知识条目；后续新任务均记录新 revision
- 验证：auto

### AC-13 迁移期已有任务

- GIVEN 升级前存在缺少显式 binding 的未完成任务
- WHEN 执行迁移并启动新版执行器
- THEN 迁移按可审计规则为可证明版本的任务生成绑定；无法证明版本的任务进入隔离状态并阻止执行；迁移可重复运行且结果幂等
- 验证：auto

## 10. 可复跑证据契约

实现方需在仓库标准测试框架中落地上述用例。基于现有 Python pipeline 工具的默认命令约定如下；若仓库已有等价命令，开发报告记录唯一替代命令及选择依据。

```bash
python3 -m pytest -q tests/test_task_version_binding.py
python3 -m pytest -q tests/test_canary_route_control.py
python3 -m pytest -q tests/test_canary_rollback_concurrency.py
python3 -m pytest -q tests/test_task_binding_recovery.py
python3 -m pytest -q
```

并发测试必须支持固定 seed 与重复次数，推荐命令接口：

```bash
CANARY_BINDING_TEST_SEED=20260721 CANARY_BINDING_TEST_ROUNDS=20 python3 -m pytest -q tests/test_canary_rollback_concurrency.py
```

开发报告必须保存并可再次核验：

- 每条命令的完整文本、UTC 开始/结束时间、exit code 和测试数量。
- 数据库类型、事务隔离级别、worker 数、并发任务数、round 数和 seed。
- AC-04/AC-05 每个 revision 到版本/bucket 的计数矩阵，以及零违规断言。
- AC-06 的 task/binding/outbox 去重计数。
- AC-08 的成功 revision、冲突结果和审计事件序列。
- AC-09/AC-10 的稳定 reason code 与零副作用断言。
- AC-11 的故障注入点、重试次数和最终 binding/run 关联。
- 任务到 `pipeline_run_id`、版本 manifest、route revision、回滚事件和知识入口的完整追溯样例。

通过门槛：全部自动 AC 通过；全量回归 exit code 为 0；并发测试重复 20 轮零不变量违规；证据能够独立判断回滚切面前后的任务版本绑定。
