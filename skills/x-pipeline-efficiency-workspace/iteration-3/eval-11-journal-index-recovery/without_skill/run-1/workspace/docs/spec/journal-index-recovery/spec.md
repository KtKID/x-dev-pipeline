> spec_version: 3

# journal-index-recovery

## 任务目标

- 实现仅依赖 Python 标准库的本地 journal/index CLI，在调用者指定的 state-dir 中持久化字符串键值、tombstone、全局 seq 和幂等结果。
- 进程重启、日志尾部损坏恢复、原子压缩以及多进程并发下，对外可观察状态与已提交结果保持一致。
- `python3 fixture/backend/cli.py --root <state-dir> <command>` 始终向 stdout 输出唯一 JSON object，并按契约返回稳定退出码。

## 非目标

- 不提供数据库、网络服务、守护进程、第三方依赖或跨主机锁。
- 不在 state-dir 内引入固定布局之外的持久化真相源。
- 不修改 `task/` 与 `fixture/README.md`，实现范围限定为 `fixture/backend/`。
- 不自动修复中段日志或损坏 snapshot，不从日志猜测替代已损坏的已提交 snapshot。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `record.py` | 目标 | 规范化 record，生成/校验 CRC-32，拒绝非法字段 | 非规范 JSON 或宽松类型校验 → 损坏未被发现 → 重放状态偏离 | 编码始终为单行 UTF-8 JSON + `\n`；CRC 仅覆盖移除 `crc32` 后的规范 JSON 字节；字段和类型严格符合契约 | 用户任务，`J1` |
| `store.py` | 目标 | 加载 snapshot + log、状态机、幂等、版本、恢复和压缩 | snapshot/log 跨步骤崩溃或错误重放 → 重复应用/丢失更新 → 已确认结果改变 | seq 为全局严格递增正整数；key version 等于最近 mutation seq；只有 append+flush+fsync 后返回首次提交成功；失败不写日志 | 用户任务，`J2`、`J3` |
| `locking.py` | 目标 | 通过 `writer.lock` 提供跨进程共享/独占锁 | 加载后写入的检查-执行窗口 → seq 重复或丢失更新 → 持久状态损坏 | mutation、recover、compact 的“加载-判定-持久化”全部在同一独占锁内；读取与独占操作互斥 | 用户任务，`J4` |
| `cli.py` | 上游/目标 | 解析参数，调用 store，渲染唯一 JSON 结果和退出码 | argparse 默认输出或异常泄漏 → stdout 缺失/多对象 → 调用方无法稳定解析 | 每次调用 stdout 恰好一个 JSON object；业务错误码到退出码映射稳定；诊断仅可写 stderr | 用户任务，`J5` |
| state-dir 文件 | 下游 | `events.log`、`snapshot.json`、两个 tmp 和 `writer.lock` 的生命周期 | 临时文件被当作已提交真相或 replace 后未 fsync 目录 → 崩溃后回退 → 丢失已返回成功的状态 | `snapshot.json.tmp` 启动时忽略；compact 每个临时文件在 replace 前 fsync，replace 后 fsync 目录；日志和 snapshot 的崩溃重叠可幂等重放 | 用户任务，`J3`、`J6` |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | record 固定为 `crc32,expected_version,key,op,request_id,seq,value` 七字段；整数字段拒绝 bool，put value 为字符串，delete value 为 null | 用户任务 + LLM 推断 | 题面给出完整 record 形状并将“字段错误”定义为损坏；严格字段/类型是最小安全解释 | 已确认 |
| J2 | get/list/delete 将 tombstone 视为业务上不存在；新 delete 请求先比较当前 version，版本匹配后对从未出现或已 tombstone 的 key 返回 `NOT_FOUND` | 用户任务 + LLM 推断 | 题面明确“不存在或已删除的业务值均视为不存在”和“版本不匹配返回 VERSION_CONFLICT”；该顺序使 tombstone version 可观察地参与校验 | 已确认 |
| J3 | snapshot 采用带 format version 的内部 JSON object，保存 last_seq、全部 key 状态与全部已提交 request；日志中 `seq <= snapshot.last_seq` 的记录只有与 snapshot 幂等表中的指纹和首次结果一致时才作为 compact 崩溃重叠忽略 | 用户任务 + LLM 推断 | snapshot 字段语义已固定，文件内部形状留白；compact 的两次 replace 存在 snapshot 新/log 旧的授权崩溃窗口，幂等重叠解析可保持两步原子语义 | 已确认 |
| J4 | 基于 POSIX `fcntl.flock`；get/list 持共享锁，put/delete/compact/recover 持独占锁 | 用户任务 + 运行环境事实 | 题面要求 state-dir 文件锁和多进程串行 mutation；Python 标准库在目标 POSIX 环境可提供 flock | 已确认 |
| J5 | CLI 参数/命令错误也输出 `ok:false` JSON 并退出 2；内部未预期错误同样收敛为一个 JSON 对象和退出 2 | 用户任务 + LLM 推断 | “所有命令只向 stdout 输出一个 JSON object”与“参数或命令错误 exit 2”共同约束解析失败路径 | 已确认 |
| J6 | state-dir 可在首次命令创建；运行时只创建固定布局文件，遗留 tmp 可存在但不读取 | 用户任务 | `storage-layout.md` 明确布局与首次命令创建权限 | 已确认 |
| J7 | 已提交 request_id 先于当前 version/存在性检查：完全相同指纹返回首次 seq/version 且 `replayed:true`，不同指纹返回 `IDEMPOTENCY_CONFLICT`；未提交的失败请求不占用 request_id | 用户任务 + LLM 推断 | 只有“首次提交的原始结果”可持久并重放；该顺序保证后续 mutation 不会改变幂等响应 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `record.py` → `events.log` → snapshot/log 重放 → CLI JSON；`SC_01`、`SC_06`、`SC_12` |
| 状态 | live/tombstone/version、last_seq、request 指纹/首次结果；`SC_02`–`SC_07`、`SC_12` |
| 时序 | 锁内加载-检查-append-fsync、compact 两阶段 replace、并发串行；`SC_08`、`SC_12`–`SC_15` |
| 资源 | 锁 fd、log fd、tmp fd 与目录 fd 的获取、fsync、关闭；`SC_08`、`SC_12`、`SC_14` |
| 不变量 | `影响边界与不变量`，`SC_01`–`SC_16` |
| 故障 | 可恢复尾部、中段损坏、snapshot 损坏、参数错误、版本/幂等冲突；`SC_04`、`SC_05`、`SC_09`–`SC_11`、`SC_16` |

## 验收清单

### 单元测试

- [ ] record 规范编码得到精确 CRC/换行，对 CRC、UTF-8、JSON、字段、类型错误分类失败。
- [ ] put/get/list/delete 覆盖首建、更新、tombstone、字典序、版本冲突、NOT_FOUND 和失败无追加。
- [ ] request_id 覆盖完全相同重试、指纹冲突、compact/restart 后重试。
- [ ] 日志每种尾部损坏返回 `RECOVERY_REQUIRED` 并可精确截断，中段损坏和 snapshot 损坏保持只读失败。
- [ ] compact 保存全部状态并清空 log，忽略遗留 snapshot tmp，能安全解析 snapshot 已提交/log 未清空的重叠状态。

### Smoke 测试

- [ ] 用真实 CLI 子进程执行 put/get/list/delete、错误路径、compact/restart、尾部注入/recover，校验唯一 JSON 输出与退出码。

### E2E 测试

- 决策：需要
- 依据：多进程真实文件锁、子进程 CLI、持久文件与损坏注入构成跨进程用户链路，单进程单元测试无法验证锁语义。
- [ ] 并发不同 key 写入无丢失且 seq 唯一；并发同 key/同 expected_version 恰好一个成功，其余为 `VERSION_CONFLICT`。
- [ ] 并发 mutation、compact、recover 在真实子进程中串行完成，重启后日志/snapshot 可重放且 seq 继续单调。

## 测试驱动开发

1. `SC_01`–`SC_07` → 先写 record 与状态机单元测试，覆盖规范编码、CRUD、版本和幂等。
2. `SC_08`–`SC_13` → 先写真实文件的持久化、损坏分类、恢复和压缩测试。
3. `SC_14`–`SC_15` → 先写多进程并发 E2E 测试。
4. `SC_16` → 先写 CLI 参数、JSON schema 和退出码 smoke 测试。
5. 实现满足测试的最小代码，重构后复跑单元、Smoke 和 E2E。

## Scenarios

### Scenario SC_01: record 规范编解码与损坏识别

- **GIVEN** 一个字段和类型正确的 put 或 delete record，以及分别包含错误 UTF-8、JSON、字段、类型或 CRC 的字节
- **WHEN** 编码健康 record 并解码各类输入
- **THEN** 健康 record 产生字段排序、紧凑 JSON、8 位小写 CRC 和单个换行，损坏输入均抛出 `RecordError`
- 测试层：unit
- 依据：用户任务，`J1`

### Scenario SC_02: 创建更新与重启重放

- **GIVEN** 空 state-dir，以及同一 key 上 expected_version 依次为 0 和首次 seq 的两个 put
- **WHEN** 分别通过新 CLI 进程提交并再用新进程 get/list
- **THEN** 两条 log record 的 seq 严格递增，get/list 返回最新字符串值与最新 seq 版本
- 测试层：smoke
- 依据：用户任务

### Scenario SC_03: 删除 tombstone 与字典序列表

- **GIVEN** 多个乱序 key，其中一个 live key 使用正确 version 删除
- **WHEN** 执行 delete、get 已删 key 和 list
- **THEN** delete 追加 value=null 的 tombstone 并返回新 seq/version，get 返回 `NOT_FOUND`，list 排除 tombstone 且 live items 按 key 字典序排列
- 测试层：unit
- 依据：用户任务，`J2`

### Scenario SC_04: 版本冲突不产生日志副作用

- **GIVEN** 当前 key version 与 put/delete 携带的 expected_version 不同
- **WHEN** 提交该新 request_id 的 mutation
- **THEN** 返回 `VERSION_CONFLICT`，events.log 字节长度、last_seq、key 状态和幂等表全部不变
- 测试层：unit
- 依据：用户任务

### Scenario SC_05: 未找到的读取和删除

- **GIVEN** 从未出现或当前为 tombstone 的 key，且 delete 携带该 key 的当前 version
- **WHEN** 执行 get 或使用新 request_id 执行 delete
- **THEN** 返回 `NOT_FOUND`，delete 不追加 record；若 expected_version 不匹配则 delete 返回 `VERSION_CONFLICT`
- 测试层：unit
- 依据：用户任务，`J2`

### Scenario SC_06: 幂等重试返回首次结果

- **GIVEN** 某 request_id 已提交，其后该 key 又发生了 mutation
- **WHEN** 使用完全相同的 op/key/value/expected_version 重试原 request_id
- **THEN** 返回首次提交的 seq/key/version 与 `replayed:true`，不追加 record，当前 key 状态不回退
- 测试层：unit
- 依据：用户任务，`J7`

### Scenario SC_07: request_id 指纹冲突

- **GIVEN** 某 request_id 已提交
- **WHEN** 使用该 ID 提交 op/key/value/expected_version 中至少一项不同的请求
- **THEN** 返回 `IDEMPOTENCY_CONFLICT`，日志、seq、key 状态和幂等首次结果不变
- 测试层：unit
- 依据：用户任务，`J7`

### Scenario SC_08: 首次提交的持久化边界

- **GIVEN** 健康 store 与一个可提交 mutation
- **WHEN** 该 mutation 返回 `ok:true`
- **THEN** record 在独占锁内完整 append，且 flush 和 fsync 已在返回前完成
- 测试层：unit
- 依据：用户任务

### Scenario SC_09: 最后物理记录损坏需要恢复

- **GIVEN** 健康日志后追加一条最后物理记录，其分别呈现截断 UTF-8、缺少换行、JSON 错误、字段错误或 CRC 不匹配
- **WHEN** 执行 recover 以外的任意命令
- **THEN** 返回 `RECOVERY_REQUIRED`/exit 6，日志字节不被改写
- 测试层：unit
- 依据：用户任务

### Scenario SC_10: 恢复只截断可恢复尾部

- **GIVEN** 日志拥有 N 个有效 record 和一个损坏尾部
- **WHEN** 执行 recover，然后对健康日志再次 recover
- **THEN** 首次在独占锁内截断到第 N 个 record 边界并 fsync，返回精确 truncated_bytes；第二次成功返回 0
- 测试层：smoke
- 依据：用户任务

### Scenario SC_11: 中段日志和 snapshot 损坏保持只读

- **GIVEN** 最后记录之前有任意损坏 record，或已提交 snapshot 无法解析/不符合 schema
- **WHEN** 执行包括 recover 在内的任意命令
- **THEN** 前者返回 `CORRUPT_LOG`/exit 7，后者返回 `CORRUPT_SNAPSHOT`/exit 8，所有持久文件字节不变
- 测试层：unit
- 依据：用户任务

### Scenario SC_12: 原子压缩保留完整重启状态

- **GIVEN** 包含 live/tombstone key、last_seq 和多个 request 结果的健康 store
- **WHEN** 在独占锁内执行 compact 并重启
- **THEN** snapshot 通过 tmp flush+fsync+replace+目录 fsync 提交，events.log 通过相同流程置空，返回 snapshot_seq；重启后状态/幂等结果不变且新 seq 继续递增
- 测试层：smoke
- 依据：用户任务，`J3`

### Scenario SC_13: compact 中断遗留物安全启动

- **GIVEN** 遗留的任意 `snapshot.json.tmp`，或已提交新 snapshot 与尚未清空的旧 events.log 同时存在
- **WHEN** 新进程加载 store
- **THEN** tmp 内容被忽略；与 snapshot 记载一致的日志重叠 record 不重复应用，加载后状态、last_seq 和幂等结果保持一致
- 测试层：unit
- 依据：`J3`

### Scenario SC_14: 并发不同 key 写入无丢失

- **GIVEN** 多个 CLI 进程各使用唯一 request_id，对不同新 key 使用 expected_version=0
- **WHEN** 这些进程同时执行 put
- **THEN** 所有请求成功，全部 seq 唯一且严格形成 1..N，list 包含所有 key 且无丢失更新
- 测试层：e2e
- 依据：用户任务，`J4`

### Scenario SC_15: 并发同 key 乐观版本只提交一次

- **GIVEN** 某 live key 的当前 version 为 V，多个 CLI 进程使用不同 request_id 但相同 expected_version=V
- **WHEN** 这些进程同时更新该 key
- **THEN** 恰好一个返回成功，其余均返回 `VERSION_CONFLICT`/exit 4，日志只增加一条 record
- 测试层：e2e
- 依据：用户任务，`J4`

### Scenario SC_16: CLI JSON 输出与稳定退出码

- **GIVEN** 每个成功命令、参数/未知命令错误以及全部七类业务失败
- **WHEN** 通过真实子进程调用 CLI
- **THEN** stdout 恰好包含一个 JSON object，成功对象含 `ok:true`，失败对象含稳定 error.code/message，退出码依次符合 2/3/4/5/6/7/8 契约
- 测试层：smoke
- 依据：用户任务，`J5`
