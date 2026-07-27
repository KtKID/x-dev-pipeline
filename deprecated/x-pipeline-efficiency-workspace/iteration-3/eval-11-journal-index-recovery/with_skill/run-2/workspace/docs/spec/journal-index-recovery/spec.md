> spec_version: 3

# journal-index-recovery

## 任务目标

- 在 `fixture/backend/` 实现仅依赖 Python 标准库的本地 journal/index，通过指定 state-dir 的 CLI 完成 put、get、delete、list、compact 与 recover。
- 每次进程启动都从已提交 snapshot 与 journal 重建状态，保持值、tombstone、全局 seq、乐观版本和 request_id 幂等结果。
- 对尾部未提交损坏、中段已提交损坏和 snapshot 损坏给出稳定、可判定且不扩大损坏的处理结果。
- 使用标准库文件锁和持久化顺序保证多进程 mutation、recover、compact 串行化，并发提交无丢失且 seq 唯一。
- 所有 CLI 调用向 stdout 输出恰好一个 JSON object，并按契约返回稳定退出码。

## 非目标

- 不引入数据库、网络、守护进程、第三方包或固定 state-dir。
- 不在 state-dir 创建固定布局之外的持久化真相源；`.tmp` 只服务于原子替换。
- 不提供批量 mutation、事务、历史查询、日志跨目录复制、加密或访问控制。
- 不修改 `task/` 或 `fixture/README.md`。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `fixture/backend/record.py` | 目标 | 定义 journal record 的严格字段校验、规范 JSON、CRC-32 编解码 | 非规范字段或 CRC 漏检 → 损坏记录进入状态机 → 恢复出错误状态 | 已提交记录一行一个 UTF-8 JSON，以 `\n` 结束；CRC 输入与输出算法唯一；put value 为字符串，delete value 为 null | `J1`、`J2` |
| `fixture/backend/locking.py` | 目标 | 在 state-dir 的 `writer.lock` 上提供进程级共享/独占锁 | mutation 在读取后追加前交错 → seq 重复或更新丢失 → 持久状态分叉 | mutation、recover、compact 从重放开始到持久化完成始终持有独占锁；只读命令重放期间持有共享锁 | `J3` |
| `fixture/backend/store.py` | 目标 | 实现 snapshot + log 重放、状态机、错误分类、压缩和恢复 | 崩溃窗口、重复请求或腐败边界误判 → 重复提交、合法数据被截断或静默回退 | seq 为正整数且每次提交加一；key version 等于最近 mutation seq；幂等检查先于当前版本检查；中段损坏与 snapshot 损坏不改写任何真相源 | `J4`、`J5`、`J6`、`J7` |
| `fixture/backend/cli.py` | 目标/上游 | 解析参数，调用 store，将成功和失败映射到 JSON 与退出码 | argparse 或未捕获异常输出非 JSON/多对象 → 调用方无法稳定消费 | stdout 每次调用恰好一个 JSON object；已定义业务错误使用固定退出码；诊断只写 stderr | `J8`、`J9` |
| `<state-dir>/snapshot.json` | 下游 | 原子保存完整 materialized state 与幂等历史 | snapshot 已 replace、旧 log 尚未清空时崩溃 → 重启重复重放 → 状态或 seq 错误 | 已提交 snapshot 优先作为基线；遗留 `snapshot.json.tmp` 被忽略；旧 log 中已被 snapshot 覆盖的合法连续记录只校验不重放 | `J6`、`J7` |
| `<state-dir>/events.log` | 下游 | append-only 提交 journal；recover 截尾；compact 原子替换为空文件 | flush/fsync 前报告成功或错误截断 → 已确认写入丢失 | mutation append 后完成 flush + fsync 才返回；recover 只删除最后物理记录起始处之后的可恢复尾部；compact 用 tmp + replace + 目录 fsync | `J1`、`J5`、`J6` |
| CLI 调用方与并发子进程 | 上游/相关 | 提供字符串参数、重复请求和并发调用，消费 JSON/退出码 | 相同版本并发检查后共同提交 → 多胜者或 seq 冲突 | 不同 key 并发无丢失且 seq 唯一；同 key 同 expected_version 并发只有一个首次提交成功 | `J3`、`J4`、`J8` |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | journal record 恰好包含 `crc32, expected_version, key, op, request_id, seq, value`，类型严格且拒绝 bool 冒充 int；`expected_version >= 0`、`seq > 0` | 用户任务 + LLM 推断 | 题面给出固定字段和版本域；严格集合与整数类型可避免未定义字段进入 CRC 或状态机 | 已确认 |
| J2 | record 编码输出规范 JSON 加单个换行；解码输入是一条含换行的完整物理记录 | 用户任务 | CRC 使用移除 crc32 后的 sort_keys/紧凑分隔 JSON UTF-8；已提交记录必须以换行结尾 | 已确认 |
| J3 | `fcntl.flock` 在 `writer.lock` 上实现跨进程共享/独占锁；root、lock、空 log 可在首次调用创建 | 用户任务 | 运行平台与题面要求标准库文件锁，并明确允许首次命令创建这些路径 | 已确认 |
| J4 | request_id 已存在时先比较完整指纹；同指纹返回原 seq/key/version 且 `replayed=true`，异指纹返回 `IDEMPOTENCY_CONFLICT`；随后才做版本和 delete 存在性判断 | 用户任务 | 该顺序保证原始写入之后 key 再变化时，合法重试仍返回首次结果 | 已确认 |
| J5 | delete 只作用于当前 live key；已 tombstone 或从未出现均为 `NOT_FOUND`。新 request 的 expected_version 先与最近 mutation seq 比较，因此错误版本优先得到 `VERSION_CONFLICT` | 用户任务 + LLM 推断 | 题面规定不存在或已删除业务值均视为不存在，同时所有 mutation 必须做乐观版本校验；这是最小一致状态机 | 已确认 |
| J6 | snapshot 内部格式采用版本化 JSON，保存 `last_seq`、所有 key 的 value/tombstone/version、所有 request_id 的指纹与首次结果；加载时严格校验闭包与 seq 覆盖 | 用户任务 + LLM 推断 | 题面固定保存语义，未固定 JSON 形状；版本字段与严格校验让损坏稳定归类为 `CORRUPT_SNAPSHOT` | 已确认 |
| J7 | compact 的 snapshot replace 与 log replace 之间崩溃时，snapshot 已覆盖的旧 log 前缀允许存在；这些记录必须连续、CRC 正确并与 snapshot 幂等历史逐项一致，然后跳过状态应用 | 用户任务 + 仓库事实推断 | 题面规定先提交 snapshot 再清空 log；这段必然崩溃窗口需要可重启解释，且不能回退 snapshot | 已确认 |
| J8 | CLI 的语法错误输出 `INVALID_ARGUMENT` JSON 并退出 2；未列举的本地 OS/内部失败输出 `INTERNAL_ERROR` JSON 并退出 1 | 用户任务 + LLM 推断 | 题面要求所有命令 stdout 为一个 JSON object，只给业务错误的固定映射；补齐未定义失败仍保持机器可消费 | 已确认 |
| J9 | key、value、request_id 接受 CLI 能提供的任意字符串，包括空字符串；负 expected_version 作为参数域错误退出 2 | 用户任务 + LLM 推断 | 题面未设置非空或长度限制；只施加版本域本身要求的最小校验 | 已确认 |
| J10 | 最后一条物理记录的缺换行、UTF-8、JSON、字段或 CRC 错误是可恢复尾部；同类错误只要后面仍有物理记录就是 `CORRUPT_LOG` | 用户任务 | 题面按“最后一条物理记录”和“最后一条之前”明确划分 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | record → `events.log` → store 重放 → CLI JSON，见影响边界、`SC_01`、`SC_02`、`SC_12` |
| 状态 | live/tombstone/version/seq/request_id 状态机，见 `J4`、`J5`、`SC_02` 至 `SC_05` |
| 时序 | append 持久化、recover 截尾、compact 双 replace 崩溃窗口与并发锁，见 `J3`、`J7`、`SC_06`、`SC_09` 至 `SC_11` |
| 资源 | 文件描述符、共享/独占锁、flush/fsync 与 state-dir fsync，见影响边界、`SC_09`、`SC_10` |
| 不变量 | `影响边界与不变量`、`SC_02` 至 `SC_11` |
| 故障 | 尾部/中段/snapshot 损坏、参数和业务错误，见 `SC_03`、`SC_05` 至 `SC_08`、`SC_12` |

## 验收清单

### 单元测试

- [ ] record 规范编码可复算 CRC，严格拒绝字段、类型、op/value、换行和 CRC 错误。
- [ ] store 覆盖 put/get/list、版本冲突、delete/tombstone/recreate、全局 seq 和无失败追加。
- [ ] 幂等重试与冲突在后续 mutation、进程重启和 compact 后保持首次结果。
- [ ] 最后一条与中段损坏按物理位置分类，recover 只截可恢复尾部且健康调用返回 0。
- [ ] snapshot 严格加载，忽略遗留 tmp，并接受 compact 提交窗口留下且与 snapshot 一致的旧 log。

### Smoke 测试

- [ ] 在新临时 state-dir 依次通过真实 CLI 子进程执行 put/get/list/delete/compact/restart/get，逐个断言单 JSON 输出、字段和退出码。
- [ ] 通过真实 CLI 注入尾部损坏，断言普通命令退出 6，recover 成功并报告准确 `truncated_bytes`，随后状态可读。

### E2E 测试

- 决策：需要
- 依据：契约包含真实 CLI 跨进程重启、多进程锁竞争、文件损坏注入与原子压缩边界，单进程单元测试无法覆盖锁和进程生命周期。
- [ ] 并发启动多个 CLI mutation 进程，验证不同 key 无丢失/seq 唯一，以及同 key 同版本只有一个成功、其余退出 4。

## 测试驱动开发

1. `SC_01` → 先写会失败的 record codec 单元测试。
2. `SC_02`、`SC_03`、`SC_04` → 先写会失败的 store 状态机与日志不变性单元测试。
3. `SC_05` → 先写会失败的跨实例/compact 幂等测试。
4. `SC_06`、`SC_07`、`SC_08`、`SC_09` → 先写会失败的故障注入与崩溃窗口单元测试。
5. `SC_12` → 先写会失败的真实 CLI smoke 测试。
6. `SC_10`、`SC_11` → 先写会失败的多进程 CLI E2E 测试。
7. 实现满足测试的最小代码，重构后复跑单元、Smoke 和 E2E。

## Scenarios

### Scenario SC_01: Record 规范编解码与 CRC 校验

- **GIVEN** 字段完整且类型、op/value 组合合法的 put 或 delete record，以及任一字段/类型/CRC/行尾被破坏的反例
- **WHEN** 编码合法 record 或解码单条物理记录
- **THEN** 合法输出是 sort_keys 紧凑 UTF-8 JSON 加 `\n` 且 CRC 可复算；每个反例抛出 `RecordError`，不返回部分 record
- 测试层：unit
- 依据：`J1`、`J2`

### Scenario SC_02: Mutation 建立全局 seq 与可查询状态

- **GIVEN** 新 state-dir 和多个不同 key 的合法 put，后续包含同 key 更新
- **WHEN** 依次提交并通过 get/list 重建查询
- **THEN** 每次首次提交 seq 从 1 连续递增且 version=seq，get 返回最新 live 值，list 仅含 live key 并按 key 字典序排列，进程重建结果一致
- 测试层：unit
- 依据：用户任务、`J3`

### Scenario SC_03: 乐观版本冲突不产生持久副作用

- **GIVEN** key 当前 version 与 mutation 的 expected_version 不同
- **WHEN** 执行 put 或 delete
- **THEN** 返回 `VERSION_CONFLICT`，events.log 字节、全局 seq、值和幂等表均不变化
- 测试层：unit
- 依据：用户任务、`J4`

### Scenario SC_04: Delete tombstone 与重建语义

- **GIVEN** live、从未出现和已 tombstone 三类 key
- **WHEN** 对 live key 以匹配版本 delete、查询/重复新 delete，并以 tombstone version put 重建
- **THEN** 首次 delete 写入 value=null 的新 seq，查询和 list 隐藏 tombstone；不存在态 delete 返回 `NOT_FOUND` 且不追加；匹配 tombstone version 的 put 恢复 live 值并取得新 seq
- 测试层：unit
- 依据：`J5`

### Scenario SC_05: request_id 全局幂等跨重启与压缩

- **GIVEN** 已提交 mutation 的 request_id，随后 key 状态继续变化、进程重启或执行 compact
- **WHEN** 用完全相同指纹重试，或用相同 request_id 改变任一 op/key/value/expected_version 字段
- **THEN** 同指纹返回首次 seq/key/version 且 replayed=true 并不追加；异指纹返回 `IDEMPOTENCY_CONFLICT` 且不改变状态
- 测试层：unit
- 依据：`J4`、`J6`

### Scenario SC_06: 可恢复尾部阻断普通命令并精确截断

- **GIVEN** 健康 journal 后附加最后物理记录，其缺换行或存在 UTF-8、JSON、字段、CRC 任一种错误
- **WHEN** 先执行普通命令再执行 recover
- **THEN** 普通命令返回 `RECOVERY_REQUIRED` 且不改写；recover 截断到最后有效记录边界、flush+fsync、返回实际删除字节数；再次 recover 返回 0 且状态可读
- 测试层：unit
- 依据：`J10`

### Scenario SC_07: 中段损坏拒绝所有改写

- **GIVEN** 最后一条之前的物理 record 存在 UTF-8、JSON、字段或 CRC 损坏且后面仍有物理 record
- **WHEN** 执行任意普通命令、compact 或 recover
- **THEN** 均返回 `CORRUPT_LOG`，events.log、snapshot 与 seq 保持原字节和状态
- 测试层：unit
- 依据：`J10`

### Scenario SC_08: Snapshot 损坏与临时文件隔离

- **GIVEN** 已提交 `snapshot.json` 存在 JSON、schema 或状态闭包损坏，同时可存在健康 log；另有任意遗留 `snapshot.json.tmp`
- **WHEN** 执行任意命令
- **THEN** 已提交 snapshot 损坏返回 `CORRUPT_SNAPSHOT` 且不回退 log、不改写；仅临时文件存在时被忽略并按已提交真相源工作
- 测试层：unit
- 依据：`J6`

### Scenario SC_09: Compact 原子持久化并覆盖提交窗口

- **GIVEN** 包含 live、tombstone、幂等历史和 last_seq 的健康状态
- **WHEN** compact 完成，或模拟 snapshot 已 replace 而旧 events.log 尚未清空的崩溃窗口后重启
- **THEN** snapshot 保存完整状态与历史，正常完成后 log 为空；崩溃窗口中的连续旧记录经 CRC 与 snapshot 历史一致性校验后不重复应用；后续 mutation 从 last_seq+1 提交
- 测试层：unit
- 依据：`J6`、`J7`

### Scenario SC_10: 不同 key 多进程写入无丢失

- **GIVEN** 多个 CLI 进程从同一 state-dir、expected_version=0 向不同 key 写入
- **WHEN** 进程并发执行 put
- **THEN** 所有进程成功，提交 seq 两两唯一且覆盖连续区间，重启 list 包含全部值
- 测试层：e2e
- 依据：`J3`

### Scenario SC_11: 同 key 同版本并发只有一个胜者

- **GIVEN** 多个 CLI 进程用不同 request_id 和相同 expected_version 更新同一 key
- **WHEN** 进程并发执行 put
- **THEN** 恰好一个进程首次提交成功，其余返回 `VERSION_CONFLICT`/退出 4，journal 只增加一条记录且最终值来自胜者
- 测试层：e2e
- 依据：`J3`、`J4`

### Scenario SC_12: CLI 输出与退出码稳定

- **GIVEN** 每个合法命令、语法/参数错误以及各业务错误状态
- **WHEN** 通过 `python3 fixture/backend/cli.py --root <dir> ...` 启动独立进程
- **THEN** stdout 恰好可解析为一个 JSON object；成功含 ok=true，失败含 ok=false/error code/message；参数、NOT_FOUND、VERSION_CONFLICT、IDEMPOTENCY_CONFLICT、RECOVERY_REQUIRED、CORRUPT_LOG、CORRUPT_SNAPSHOT 分别退出 2、3、4、5、6、7、8
- 测试层：smoke
- 依据：`J8`、`J9`
