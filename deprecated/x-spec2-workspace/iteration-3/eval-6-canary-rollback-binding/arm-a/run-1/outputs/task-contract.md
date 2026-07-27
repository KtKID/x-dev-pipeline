# Canary 回滚与生产任务版本绑定：开发任务契约

## 1. 目标与交付边界

### 1.1 目标

实现生产路由的 canary 回滚和生产任务的不可变版本绑定，保证 V2 canary 回滚到 V1 与新任务创建并发时满足以下结果：

1. 每个生产用户任务只得到一个 `pipeline_run_id`。
2. run 创建时原子记录路由快照和唯一 `pipeline_version_id`。
3. 回滚提交前完成创建的 run 保持原绑定；其中被 canary 选中的 run 可继续使用 V2。
4. 回滚提交后完成创建的新 run 全部绑定 V1。
5. 所有 worker 只按 run 绑定解析版本，执行期间不读取当前生产路由来改选版本。
6. 创建、回滚、失败与重试均留下可复跑、可关联的追加事实。

### 1.2 范围

- 生产路由状态和发布版本的最小持久化模型。
- 生产 run 的幂等创建、路由选择、版本冻结和事实事件。
- `V2 -> V1` 回滚的前置条件、原子切换、审计和重试。
- worker 读取绑定以及已绑定版本的制品保留。
- 并发、崩溃、超时、重复请求和陈旧回滚的自动化验证。
- 记录测试命令、退出码、日志、状态快照和数据库断言的证据包。

### 1.3 范围外

- 自动决定何时触发 canary 回滚。
- 自动改写 pipeline skill、无人审批晋级和跨项目权限系统。
- 对已绑定 run 做原地换版。
- 控制台、复杂统计和 Token 金额换算。

## 2. 合理假设

| A-ID | 假设 | 实现影响 |
|---|---|---|
| A1 | 路由、run、幂等键和事实 outbox 可写入同一支持事务与行锁的持久化存储。 | 下文以关系型数据库事务描述；其他存储必须提供等价的线性一致 CAS、原子批写和持久幂等语义。 |
| A2 | V1、V2 已拥有不可变 `pipeline_version_id` 和 `artifact_digest`；V1 是已发布且可执行的回滚目标。 | 回滚只切换路由，不复制或重建制品。 |
| A3 | canary 路由规则可由输入中稳定字段计算，且同一路由 epoch 内结果确定。 | run 保存规则版本和 bucket，审计时可复算选择结果。 |
| A4 | “创建完成”和“回滚完成”均以各自路由事务成功提交为准。 | 数据库提交是本契约的线性化点。 |
| A5 | 回滚后，已绑定 V2 的 run 按原版本继续执行；紧急停止属于独立的 run 取消策略。 | V2 退出新任务路由后，其不可变制品仍受已绑定 run 引用保护。 |
| A6 | 同一用户任务有稳定的 `task_request_key`，调用方在网络重试时复用该键。 | 唯一约束可消除重复 `pipeline_run_id`。 |

## 3. 核心不变量

| I-ID | 不变量 |
|---|---|
| I1 | `(production_scope, task_request_key)` 唯一映射到一个 `pipeline_run_id`。 |
| I2 | 每个生产 run 在创建事务提交时同时拥有非空的 `pipeline_version_id`、`route_epoch`、`route_rule_version`、`artifact_digest` 和代码/模型快照引用。 |
| I3 | run 的版本绑定创建后不可更新；返工只新增该 run 的 `stage_attempt`。 |
| I4 | worker 的实际制品摘要必须等于 run 保存的 `artifact_digest`。 |
| I5 | 路由 epoch 单调递增；一次成功回滚以一次 CAS 将含 V2 的预期 epoch 更新为只选择 V1 的新 epoch。 |
| I6 | 回滚事务提交后获得路由锁的创建事务只能观察新 epoch，并绑定 V1。 |
| I7 | 回滚事务提交前释放路由锁的创建事务保持其已提交绑定，包括 V2 绑定。 |
| I8 | 任一成功状态变更都在同一事务写入追加事实或 transactional outbox；事实发布失败可重试且 `event_id` 幂等。 |
| I9 | 一个路由 scope 在任一已提交 epoch 只有一个有效配置；生产任务不存在空绑定、多版本绑定或执行中漂移。 |
| I10 | 已绑定版本的制品在所有引用 run 到达保留策略允许的终态前保持可解析。 |

任何实现路径违反 I1-I10 时必须中止提交或让 run 进入明确失败态；禁止静默选择其他版本。

## 4. 状态与数据契约

### 4.1 发布版本 `pipeline_release`

最少字段：

```text
pipeline_version_id   PK
artifact_digest       immutable, unique
baseline_version_id   nullable
release_status        CANDIDATE | CANARY | PUBLISHED | ROLLED_BACK
routable               bool
executable             bool
created_at
```

约束：

- V1 在回滚提交时必须为 `PUBLISHED`、`routable=true`、`executable=true`。
- V2 回滚后设置 `routable=false` 和 `release_status=ROLLED_BACK`。
- `executable` 与 `routable` 分离；V2 有存量绑定时保持 `executable=true`。
- 版本和摘要均为不可变值。修订内容产生新版本 ID。

### 4.2 生产路由 `production_route`

每个 `production_scope` 恰有一行：

```text
production_scope      PK
route_epoch           bigint, monotonically increasing
stable_version_id     FK pipeline_release
canary_version_id     nullable FK pipeline_release
canary_rule_version   nullable
canary_allocation     nullable
route_status          ACTIVE | CANARY
updated_at
last_operation_id     unique nullable
```

canary 期间示例状态为 `{epoch: 41, stable: V1, canary: V2, status: CANARY}`；回滚后的单次原子状态为 `{epoch: 42, stable: V1, canary: null, status: ACTIVE}`。任何读取方只能消费一行完整的已提交状态。

### 4.3 生产 run `pipeline_run`

最少字段：

```text
pipeline_run_id       PK
production_scope
task_request_key
run_kind              PRODUCTION
pipeline_version_id   immutable FK pipeline_release
artifact_digest       immutable
route_epoch           immutable
route_rule_version    immutable nullable
route_bucket          immutable nullable
model_snapshot        immutable reference
code_snapshot         immutable reference
run_status
created_at
UNIQUE(production_scope, task_request_key)
```

数据库应通过权限、触发器或只提供 insert 的 repository API 强制版本绑定字段不可更新。`stage_attempt` 另表追加，不修改上述绑定。

### 4.4 追加事实与操作幂等

事实至少包含：

```text
event_id              unique
event_type            RUN_VERSION_BOUND | ROUTE_ROLLBACK_COMMITTED | OPERATION_REJECTED
operation_id
pipeline_run_id       nullable
production_scope
before_route_epoch    nullable
after_route_epoch     nullable
pipeline_version_id
artifact_digest       nullable
reason_code           nullable
evidence_refs[]
occurred_at
```

回滚命令使用唯一 `rollback_operation_id`。相同 operation 重试返回首次已提交结果；同一 operation 携带不同参数时返回 `IDEMPOTENCY_CONFLICT`。

## 5. 路由与原子边界

### 5.1 新生产任务创建

`CreateProductionRun(production_scope, task_request_key, routing_inputs, model_snapshot, code_snapshot)` 必须执行：

1. 开启事务并处理 `task_request_key` 幂等占位；已存在映射时返回原 run 及原绑定。
2. 对对应 `production_route` 执行 locking read。推荐 `SELECT ... FOR SHARE`，锁持有至事务提交；存储不支持共享锁时使用排他锁或等价线性一致原语。
3. 从这一份已锁定快照计算目标版本：`ACTIVE` 选择 stable；`CANARY` 根据固定规则选择 stable 或 canary。
4. 校验目标 release 的 `routable`、`executable` 和摘要完整性。
5. 在同一事务插入 `pipeline_run`、初始 attempt 关联和 `RUN_VERSION_BOUND` outbox 事实。
6. 提交事务。提交成功即“任务已创建”；提交失败不产生可见 run。

路由选择必须在服务端完成。调用方提交的版本只能作为诊断字段，不能覆盖持久化路由。

### 5.2 Canary 回滚

`RollbackCanary(production_scope, rollback_operation_id, expected_epoch, expected_canary=V2, target=V1, reason, evidence_refs)` 必须执行：

1. 开启事务并查询 operation 幂等记录。
2. 对同一 `production_route` 执行 `SELECT ... FOR UPDATE`。
3. 校验当前 `route_epoch == expected_epoch`、`canary_version_id == V2`、V1 可路由且制品可执行。
4. 以单次更新完成 CAS：清空 canary 字段，stable 指向 V1，状态改为 `ACTIVE`，epoch 加一并保存 operation ID。
5. 将 V2 标为退出路由；保留其可执行制品及存量 run 引用。
6. 在同一事务追加 `ROUTE_ROLLBACK_COMMITTED` outbox，包含旧/新 epoch、V2、V1、原因和证据引用。
7. 提交事务。该提交是回滚生效边界。

校验失败返回稳定 reason code，并保持路由、release 和事实终态不变：

- `BASELINE_STALE`：epoch 或当前 canary 与请求前置条件不符。
- `ROLLBACK_TARGET_INVALID`：V1 状态、摘要或制品不可用。
- `IDEMPOTENCY_CONFLICT`：相同 operation ID 的参数发生变化。

### 5.3 并发顺序保证

创建事务持有共享路由锁，回滚事务持有排他路由锁，两者形成全序：

| 已提交顺序 | 新 run 结果 |
|---|---|
| 创建提交在回滚提交之前 | run 保存创建时 epoch；按该 epoch 的稳定/canary 规则绑定 V1 或 V2。 |
| 回滚提交在创建提交之前 | 创建读取新 epoch；run 绑定 V1。 |
| 两者同时到达 | 数据库锁确定唯一顺序，结果归入上述两行之一。 |

业务日志时间、请求到达时间和 worker 启动时间只用于观察；它们不定义绑定归属。

### 5.4 执行读取

worker 接收 `pipeline_run_id` 后执行：

1. 读取 run 的 `pipeline_version_id` 和 `artifact_digest`。
2. 按摘要解析不可变制品并校验摘要。
3. 将实际版本和摘要写入每个 stage attempt 事件。
4. 发现消息内版本、缓存版本或当前路由与 run 绑定不同，返回 `RUN_BINDING_MISMATCH` 并停止该 attempt。

worker 禁止用 `production_route` 为已有 run 重新选版。回滚不得批量更新已有 `pipeline_run.pipeline_version_id`。

## 6. 失败恢复契约

| 故障 | 可观察状态 | 恢复动作 | 必须保持 |
|---|---|---|---|
| 创建事务在提交前崩溃 | 无可见 run，或事务最终回滚 | 使用同一 `task_request_key` 重试整个事务 | I1、I2、I8 |
| 创建响应超时且提交结果未知 | 客户端状态不确定 | 先按 `(scope, task_request_key)` 查询；已存在则返回原 run，缺失则重试 | 禁止生成第二个 run |
| 回滚在提交前崩溃 | 路由仍为旧 epoch | 使用同一 operation ID 重试 | V2/V1 配置保持完整旧状态 |
| 回滚提交后响应或进程丢失 | 新 epoch 已为 V1-only，outbox 已持久化 | 按 operation ID 返回首次结果；后台重投 outbox | 禁止再次递增 epoch |
| outbox 投递失败或重复 | 数据库事实存在，消费者可能延迟或重复接收 | 按 `event_id` 重试并去重 | 已提交路由与绑定不受消息可用性影响 |
| 回滚请求基于陈旧 epoch | `BASELINE_STALE` | 读取最新路由，重新决策并使用新 operation | 禁止覆盖更新后的生产路由 |
| V1 校验失败 | `ROLLBACK_TARGET_INVALID`，旧路由保持 | 修复或恢复 V1 制品后重新发起新 operation | 禁止产生半回滚状态 |
| 数据库死锁或序列化失败 | 当前事务回滚 | 有界退避并以相同幂等键重跑完整事务 | 禁止在事务外补写绑定 |
| 已绑定 V2 的 worker 在回滚后启动 | run 仍引用 V2 | 加载 V2 摘要并继续；制品缺失则 attempt 明确失败并告警 | 禁止静默降级为 V1 |
| worker 发现绑定/制品摘要不符 | `RUN_BINDING_MISMATCH` 或 `ARTIFACT_DIGEST_MISMATCH` | 停止 attempt，记录期望/实际与证据，修复制品解析后重跑同一 run 的新 attempt | run 绑定保持不变 |

## 7. 开发 checklist

### 数据与约束

- [ ] 新增或补齐 `pipeline_release`、`production_route`、`pipeline_run`、operation 幂等表和 transactional outbox 的字段及索引。
- [ ] 建立 `(production_scope, task_request_key)`、`event_id`、`rollback_operation_id` 唯一约束。
- [ ] 强制 run 版本、摘要、route epoch、规则版本和 bucket 非空/不可变；nullable 字段仅限非 canary 路由确实无值的规则字段。
- [ ] 分离 release 的 `routable` 与 `executable`，并让制品回收检查存量 run 引用。
- [ ] 提供向前迁移、回滚迁移和兼容旧数据的策略；旧生产 run 缺失绑定时阻止执行并进入显式修复队列。

### 服务与事务

- [ ] 实现 `CreateProductionRun` 的幂等、locking read、确定性 canary 选择、run/attempt/event 同事务提交。
- [ ] 实现 `RollbackCanary` 的 operation 幂等、排他锁、expected epoch/version 校验、单次 CAS 和同事务事实。
- [ ] 统一所有生产 run 创建入口，绕过入口无法插入生产 run。
- [ ] 定义锁顺序为“幂等键/operation -> production_route -> release/run -> outbox”，所有路径保持一致并对序列化失败做有界重试。
- [ ] 让 API 返回 `pipeline_run_id`、绑定版本、摘要、route epoch、operation/result ID 和稳定 reason code。

### 执行与保留

- [ ] worker 只从 run 绑定加载版本，并在每个 attempt 校验/记录制品摘要。
- [ ] 拒绝消息、缓存或调用参数覆盖 run 绑定。
- [ ] 回滚后允许存量 V2 run 解析 V2 制品；回收器保护仍被 run 引用的版本。
- [ ] 返工继续使用原 `pipeline_run_id` 和原版本，并新增 `stage_attempt`。

### 可观测与审计

- [ ] 为创建锁等待、回滚锁等待、事务重试、`BASELINE_STALE`、绑定不匹配和 outbox backlog 建立结构化日志及指标。
- [ ] 日志同时记录 operation/run ID、scope、old/new epoch、selected version 和 event ID；禁止记录 grader-only 断言正文。
- [ ] 提供按 run 和 rollback operation 查询完整证据链的只读接口。

### 测试

- [ ] 完成第 8 节所有确定性测试；并发测试使用 barrier/latch 控制顺序，禁止依赖 sleep 猜测竞态。
- [ ] 为每条核心不变量建立数据库级或服务级反例测试。
- [ ] 在真实事务隔离级别上运行并发套件，记录数据库类型与隔离级别。

## 8. 验收用例

### AC-01：回滚先提交，新任务绑定 V1

- GIVEN 路由 epoch 41 为 stable V1 + canary V2，创建线程尚未取得路由共享锁。
- WHEN 回滚线程取得排他锁并提交 epoch 42 的 V1-only 路由，随后释放创建线程。
- THEN 创建 run 的 `route_epoch=42`、`pipeline_version_id=V1`，绑定字段完整且只有一条 `RUN_VERSION_BOUND`。

### AC-02：创建先提交，V2 绑定保持

- GIVEN epoch 41 的固定 routing inputs 会选择 V2。
- WHEN 创建线程取得共享锁、写入并提交 V2 run，随后回滚提交 epoch 42。
- THEN 该 run 始终绑定 V2；worker 在回滚后仍按原摘要加载 V2；生产路由为 V1-only。

### AC-03：创建持锁时回滚等待

- GIVEN 创建事务已锁定 epoch 41 路由并暂停在提交前。
- WHEN 回滚请求尝试取得排他锁。
- THEN 回滚保持等待；创建提交后回滚继续并成功；数据库中不存在空绑定和混合字段。

### AC-04：回滚持锁时创建等待

- GIVEN 回滚事务已取得排他锁并完成未提交更新。
- WHEN 创建请求尝试取得共享锁。
- THEN 创建保持等待；回滚提交后创建读取 epoch 42 并绑定 V1。

### AC-05：高并发切换分界

- GIVEN 100 个带唯一 request key 的创建请求在一个 barrier 后与一次回滚并发执行。
- WHEN 全部事务结束。
- THEN 每个 request key 恰有一个 run；epoch 41 run 可绑定 V1/V2，epoch 42 run 全部绑定 V1；不存在其他 epoch、空绑定和重复事实；总 run 数为 100。

### AC-06：创建幂等与未知提交

- GIVEN 同一 `task_request_key` 被并发发送 20 次，首次响应在提交后丢失。
- WHEN 所有调用重试并查询结果。
- THEN 所有响应指向同一 run 和同一版本，数据库只有一个 run 与一个绑定事实。

### AC-07：回滚幂等

- GIVEN 相同 `rollback_operation_id` 的回滚请求并发执行且首次响应丢失。
- WHEN 请求重试。
- THEN 路由只从 epoch 41 增加到 42，一条 canonical 回滚事实存在，所有成功响应返回同一结果。

### AC-08：陈旧回滚被拒绝

- GIVEN 当前路由已经由其他操作从 epoch 41 变为 42。
- WHEN 仍以 `expected_epoch=41` 发起回滚。
- THEN 返回 `BASELINE_STALE`，epoch 42 内容、release 状态和已绑定 run 均保持不变，并记录可审计拒绝原因。

### AC-09：无效回滚目标保持旧状态

- GIVEN V1 摘要缺失或 `executable=false`。
- WHEN 尝试把 V2 回滚至 V1。
- THEN 返回 `ROLLBACK_TARGET_INVALID`；路由、epoch、V2 routable 状态均保持原值；不存在 `ROUTE_ROLLBACK_COMMITTED`。

### AC-10：事务崩溃原子性

- GIVEN 故障注入点分别位于 route 更新后、release 更新后、outbox 插入前和提交确认后。
- WHEN 回滚进程在各点崩溃并以同一 operation ID 恢复。
- THEN 提交前故障呈现完整旧状态；提交后故障呈现完整新状态；恢复后只有一个 epoch 增量和一条 canonical 事实。

### AC-11：worker 拒绝版本漂移

- GIVEN V2 run 在回滚后收到携带 V1 的执行消息，或 worker 缓存当前路由为 V1。
- WHEN worker 启动 attempt。
- THEN worker 依据 run 加载 V2；消息覆盖尝试产生 `RUN_BINDING_MISMATCH`；run 版本不变且没有 V1/V2 混合 stage 证据。

### AC-12：返工保持绑定

- GIVEN V2 run 在回滚后收到用户反馈并进入第二次 `stage_attempt`。
- WHEN 返工执行。
- THEN attempt 2 继续关联同一 `pipeline_run_id`、V2 和相同摘要，attempt 1/2 均可查询。

### AC-13：outbox 重投

- GIVEN route/run 事务已经提交，事实消费者停机后恢复并重复拉取。
- WHEN outbox 被至少投递两次。
- THEN 消费端按 `event_id` 只形成一个 canonical 事实，持久化路由与 run 结果始终不变。

### AC-14：制品保留

- GIVEN 回滚后仍有 V2 run 处于非终态。
- WHEN 回收任务扫描 `routable=false` 的 V2。
- THEN V2 制品被保留；相关 run 到达允许回收的终态和保留期限后才可回收，回收决策留下引用计数证据。

## 9. 可复跑证据要求

开发 agent 必须提交一个证据索引，逐项关联 `I-ID`、checklist 项和 `AC-ID`。每次命令执行保存：

```text
evidence_id
git_commit_or_code_snapshot
database_engine_and_version
transaction_isolation
command               完整、可复制命令
started_at / ended_at
exit_code
stdout_stderr_ref
test_report_ref
state_snapshot_ref
covered_invariants[]
covered_acceptance_cases[]
```

证据至少包含以下四组可独立复跑的命令；开发 agent 应按仓库实际测试工具填写并执行精确命令，禁止仅写“测试通过”：

1. 数据迁移与 schema 约束测试：覆盖唯一键、非空、不可变绑定和 release 引用。
2. 路由/绑定单元与集成测试：覆盖 AC-01、AC-02、AC-06、AC-08、AC-09、AC-11、AC-12、AC-14。
3. 真实数据库并发测试：覆盖 AC-03、AC-04、AC-05、AC-07；输出每个 run 的 `task_request_key, route_epoch, pipeline_version_id` 排序清单和断言计数。
4. 故障注入与 outbox 恢复测试：覆盖 AC-10、AC-13；输出故障点、提交结果、epoch 增量和 canonical event 数。

并发证据必须包含：

- 回滚前后两份 `production_route` 快照。
- 回滚 operation 的 old/new epoch、V2/V1 和 event ID。
- 每个创建请求的唯一键、run ID、route epoch、绑定版本和摘要。
- 汇总断言：`duplicate_run_count=0`、`unbound_run_count=0`、`mixed_version_run_count=0`、`post_rollback_non_v1_count=0`。
- barrier 的释放顺序或事务 trace，用于证明 AC-01 至 AC-05 的确定性时序。

验收门槛：第 8 节全部通过；I1-I10 均有自动化断言；所有命令退出码为 0；证据能从 `pipeline_run_id` 或 `rollback_operation_id` 回查到版本、路由 epoch、制品摘要、事实事件和测试输出。

## 10. 完成定义

- 数据约束、创建路径、回滚路径、worker 读取路径和制品保留共同实现 I1-I10。
- 生产入口无法创建未绑定 run，执行入口无法绕过已冻结绑定。
- AC-01 至 AC-14 在真实事务存储上稳定复跑通过。
- 开发报告列出实际修改文件、迁移影响、完整验证命令、退出码和证据索引。
- 所有合理假设均已由实现验证或在开发报告中转化为明确风险与后续任务。
