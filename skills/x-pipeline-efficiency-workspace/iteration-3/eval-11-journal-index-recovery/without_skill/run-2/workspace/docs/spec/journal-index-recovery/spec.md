> spec_version: 3

# journal-index-recovery

## 任务目标

- 提供仅依赖 Python 标准库的本地键值 journal CLI；每次调用从调用者指定的 state-dir 内的 snapshot 与 append-only log 重建状态。
- 对 put、delete 提供乐观版本、全目录 request_id 幂等、严格递增全局 seq，以及进程重启后的等价结果。
- 对尾部损坏提供显式恢复，对中部日志损坏和已提交 snapshot 损坏提供只读失败。
- compact 原子提交完整状态与幂等历史并清空日志；并发 mutation、recover、compact 在进程间串行化。
- 所有 CLI 调用只在 stdout 输出一个 JSON object，并使用契约规定的稳定退出码。

## 非目标

- 数据库、守护进程、网络服务、第三方依赖和状态目录之外的持久化真相源。
- 跨机器并发、网络文件系统锁语义、日志分片、备份、加密和历史查询。
- 修改 `task/`、`fixture/README.md` 或 `fixture/backend/` 之外的产品实现。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `fixture/backend/record.py` | 目标 | 规范化 record，编码/解码 canonical JSON 与 CRC-32 | 字段类型或 CRC 校验宽松 → 损坏记录被当成已提交 mutation → 状态静默错误 | 编码结果是一条以 LF 结尾的 UTF-8 JSON；CRC 输入与题面算法完全一致；解码只接受完整合法字段集合 | `J1`、`J2` |
| `fixture/backend/store.py` | 目标 | snapshot + log 重放、状态机、幂等、恢复和压缩 | 重放顺序、tombstone 或幂等历史丢失 → 重启后版本、结果或 seq 回退 | 全局 seq 严格递增；每个 key 的 version 是最近 mutation seq；request_id 首次结果跨重启与 compact 保留 | `J3`、`J4`、`J5` |
| `fixture/backend/locking.py` | 目标 | state-dir 内基于 `writer.lock` 的进程锁 | 检查后追加窗口发生并发交错 → seq 重复、更新丢失或错误幂等提交 | mutation、recover、compact 在同一独占锁内完成加载、判定和持久化；读取持共享锁，不观察半次操作 | `J6` |
| `fixture/backend/cli.py` | 上游 | 参数解析、命令分派、单对象 JSON 输出和退出码 | argparse 直接向 stdout 输出 usage 或 traceback → 破坏机器协议 | 每次调用 stdout 恰有一个 JSON object；成功/业务失败/参数失败结构及退出码稳定 | `J7` |
| `events.log` | 下游 | 保存 compact 后的增量提交记录 | 未 fsync 就报告成功或 compact 非原子清空 → 成功写入在重启后丢失 | 每次提交均 append、flush、fsync 后成功返回；每条记录独占一行；recover 只截断可恢复尾部 | 用户任务 |
| `snapshot.json` | 下游 | 保存 compact 时的完整状态、全局 seq 与幂等历史 | snapshot 缺字段或部分提交 → 日志已清空后无法恢复状态 | replace 后的 snapshot 单独足以恢复 keys、tombstones、versions、last seq、请求指纹和首次结果；损坏时停止 | `J8` |
| `task/` 与 `fixture/README.md` | 相关 | 只读需求和评测边界 | 误改输入 → 评测契约漂移 | 文件内容保持不变；产品实现仅在 `fixture/backend/` | 用户任务 |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | record 只接受字段集合 `crc32,expected_version,key,op,request_id,seq,value`，类型严格；`op` 仅为 put/delete，delete value 仅为 null，put value 为字符串 | 用户任务 + LLM 推断 | 题面固定展示字段并将“字段错误”列入损坏；严格 schema 是拒绝歧义数据的最小安全假设 | 已确认 |
| J2 | `decode_record` 的输入必须含单个末尾 LF，且 LF 前为单个 JSON object；缺 LF、UTF-8/JSON/字段/CRC 错误统一抛出记录错误，由 store 按物理位置分类 | 用户任务 | 每条记录占一行且最后物理记录的这些错误均属可恢复尾部 | 已确认 |
| J3 | log 重放要求每条 seq 恰为前一已提交全局 seq + 1；违反者属于字段/顺序损坏并按所在物理记录分类 | 用户任务 + LLM 推断 | seq 必须全局严格递增；连续分配由独占锁下的 `last_seq + 1` 产生，缺口代表状态真相不完整 | 已确认 |
| J4 | 幂等请求指纹是 op/key/value/expected_version 的类型稳定组合；重试返回首次 `seq,key,version` 并把 `replayed` 改为 true | 用户任务 | 题面定义完全相同请求重试与原始结果；replayed 字段区分首次和重试 | 已确认 |
| J5 | 对 tombstone 的 get 返回 `NOT_FOUND`，delete tombstone 继续视为业务值不存在并返回 `NOT_FOUND`；已有 tombstone 的后续 put 使用 tombstone version | 用户任务 + LLM 推断 | 已删除业务值视为不存在，同时 tombstone version 继续参与乐观版本 | 已确认 |
| J6 | get/list 取得共享锁，mutation/recover/compact 取得独占锁；创建根目录与 lock 文件后再锁定 | 用户任务 + LLM 推断 | 题面明确串行化写操作；共享读锁保证 compact 多文件替换期间不会混读代际 | 已确认 |
| J7 | 参数错误包含未知命令、缺参、非整数或负 expected_version；输出统一 `{"ok":false,"error":{"code":"INVALID_ARGUMENT","message":"..."}}` 并退出 2 | 用户任务 + LLM 推断 | 题面固定业务失败 envelope 和“参数或命令错误”退出码，错误 code 留白；稳定 code 便于调用方处理 | 已确认 |
| J8 | snapshot 使用严格的、带格式版本的 JSON object，包含 `format_version,last_seq,keys,requests`；临时文件忽略，已提交文件的 UTF-8/JSON/schema/内部一致性错误均为 `CORRUPT_SNAPSHOT` | 用户任务 + LLM 推断 | 题面规定必须保留的信息及损坏分类，具体 JSON shape 留白；显式版本与严格校验降低错误恢复风险 | 已确认 |
| J9 | root 可在首次命令创建；缺失 `events.log` 视为初始空日志，缺失 snapshot 视为无 compact 基线；遗留 `snapshot.json.tmp` 和 `events.log.tmp` 均不参与加载 | 用户任务 + 固定布局 | 题面允许首次创建目录、空 log、lock，并规定 snapshot tmp 是未提交尝试；events tmp 同属 compact 临时文件 | 已确认 |
| J10 | compact 在健康状态可重复执行，返回当前 `last_seq`；recover 对健康日志返回 `truncated_bytes: 0` | 用户任务 | compact/recover 都要求保持状态，recover 明确健康时幂等成功 | 已确认 |
| J11 | 所有普通命令含 get/list/compact 在可恢复尾部时返回 `RECOVERY_REQUIRED`；所有命令含 recover 在中部损坏或 snapshot 损坏时拒绝改写 | 用户任务 | 题面使用“普通命令”和“所有命令保持只读失败”；snapshot 损坏不得从日志猜测 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `record.py` → `events.log` → `store.py` 重放 → CLI JSON，及 `SC_01`、`SC_06`、`SC_12` |
| 状态 | live/tombstone、key version、last seq、request 指纹/首次结果，见 `SC_02` 至 `SC_07` |
| 时序 | 锁内加载/判定/append-fsync，compact 的 tmp-fsync/replace/dir-fsync 顺序，见 `SC_08`、`SC_12`、`SC_14` |
| 资源 | 文件描述符、进程文件锁、临时文件和目录 fsync，见影响边界及 `SC_08`、`SC_12`、`SC_14` |
| 不变量 | `影响边界与不变量` |
| 故障 | 尾部/中部日志损坏、snapshot 损坏、版本/幂等冲突、并发冲突，见 `SC_04`、`SC_05`、`SC_09` 至 `SC_11`、`SC_14` |

## 验收清单

### 单元测试

- [ ] canonical record 编码 CRC 与题面算法一致，严格解码拒绝缺 LF、坏 UTF-8、坏 JSON、字段/类型/op/value/CRC 错误。
- [ ] put/get/list/delete 满足 seq、version、字典序、tombstone、NOT_FOUND 和 VERSION_CONFLICT 语义。
- [ ] 相同 request 重试不追加且返回首次结果；不同指纹返回 IDEMPOTENCY_CONFLICT。
- [ ] 尾部损坏、中部损坏、snapshot 损坏分类准确，recover 只截断可恢复尾部。
- [ ] compact 后重启恢复 live/tombstone、version、last seq 和全部幂等历史，下一 mutation seq 单调。

### Smoke 测试

- [ ] 真实 CLI 子进程完成 put → 幂等 retry → get → list → delete → compact → 重启读取 → recover，并逐项校验单对象 JSON 和退出码。
- [ ] 注入尾部与中部损坏，真实 CLI 分别返回 RECOVERY_REQUIRED/可恢复截断与 CORRUPT_LOG/拒绝改写。
- [ ] 多进程写不同 key 得到唯一 seq 且无丢失；同 expected_version 更新同 key 仅一个成功。

### E2E 测试

- 决策：需要
- 依据：核心风险跨越真实 CLI 子进程、操作系统文件锁、fsync/replace、进程重启和并发进程，单进程单元测试无法覆盖。
- [ ] 在临时 state-dir 中以多个真实 `python3 fixture/backend/cli.py` 进程覆盖完整链路，所有进程退出码、输出、最终日志与重启状态符合 Scenarios。

## 测试驱动开发

1. `SC_01` → 先写 record canonical/CRC/损坏拒绝测试。
2. `SC_02`、`SC_03` → 先写基本 put/get/list/delete、重启与 tombstone 版本测试。
3. `SC_04`、`SC_05` → 先写版本冲突与 request_id 幂等/冲突测试。
4. `SC_06`、`SC_07` → 先写 CLI 输出、退出码和参数失败测试。
5. `SC_08` → 先写 append 已 flush/fsync 后返回且重启可见的行为测试。
6. `SC_09`、`SC_10`、`SC_11` → 先写尾部、中部与 snapshot 损坏注入测试。
7. `SC_12`、`SC_13` → 先写 compact 原子布局、重启、幂等历史和 seq 单调测试。
8. `SC_14` → 先写多进程不同 key 与同 key 竞态测试。
9. 实现满足测试的最小代码，重构后复跑单元、Smoke 和 E2E。

## Scenarios

### Scenario SC_01: canonical record 可验证编码

- **GIVEN** 一个字段类型合法的 put 或 delete record，或一个缺 LF、坏 UTF-8、坏 JSON、字段错误、顺序错误、CRC 不匹配的物理记录
- **WHEN** record codec 编码或解码
- **THEN** 合法记录输出单行 canonical UTF-8 JSON、8 位小写 CRC 和末尾 LF并可往返；非法记录产生可分类的 `RecordError`
- 测试层：unit
- 依据：`J1`、`J2`、`J3`

### Scenario SC_02: put、get 与有序 list 跨重启保持

- **GIVEN** 空 state-dir，依次对不同 key 使用当前 expected_version 提交字符串值
- **WHEN** 新 CLI 进程执行 get 和 list
- **THEN** 每次 put 的 seq/version 为全局连续正整数，get 返回当前值/version，list 只含 live item 且按 key 字典序排列
- 测试层：e2e
- 依据：用户任务

### Scenario SC_03: delete 写入 tombstone 并保留版本

- **GIVEN** 一个 live key，及从未出现、已删除和 tombstone version 已知的 key
- **WHEN** 分别执行合法 delete、get、重复 delete 和 tombstone 后 put
- **THEN** 合法 delete 提交新 seq/version 并令 get/list 不再显示值；从未出现或已删除 key 的 delete 返回 NOT_FOUND 且不追加；后续 put 只有使用 tombstone version 才能提交
- 测试层：unit
- 依据：`J5`

### Scenario SC_04: 乐观版本冲突无副作用

- **GIVEN** key 当前 version 与请求 expected_version 不同
- **WHEN** 执行 put 或对 live key 执行 delete
- **THEN** 返回 VERSION_CONFLICT/退出 4，events.log、last seq、key 状态与幂等表均不变化
- 测试层：unit
- 依据：用户任务

### Scenario SC_05: request_id 全目录幂等且检测冲突

- **GIVEN** 已成功提交一个 request_id
- **WHEN** 以完全相同指纹重试，随后以任一 op/key/value/expected_version 不同的指纹复用该 ID
- **THEN** 相同重试返回首次 seq/key/version、`replayed:true` 且不追加；不同指纹返回 IDEMPOTENCY_CONFLICT/退出 5 且无副作用
- 测试层：e2e
- 依据：`J4`

### Scenario SC_06: CLI 成功输出稳定单对象 JSON

- **GIVEN** 每个命令的合法参数与健康 state-dir
- **WHEN** 通过公开入口执行 put/get/delete/list/compact/recover
- **THEN** stdout 恰含一个 `ok:true` JSON object，各命令字段符合题面，成功退出 0，诊断信息只可出现在 stderr
- 测试层：smoke
- 依据：`J7`

### Scenario SC_07: CLI 参数与业务失败使用稳定 envelope 和退出码

- **GIVEN** 缺失/未知/非法参数，或触发 NOT_FOUND、VERSION_CONFLICT、IDEMPOTENCY_CONFLICT、RECOVERY_REQUIRED、CORRUPT_LOG、CORRUPT_SNAPSHOT 的状态
- **WHEN** 执行公开 CLI
- **THEN** stdout 恰含一个 `ok:false` error object，并分别退出 2、3、4、5、6、7、8
- 测试层：e2e
- 依据：用户任务、`J7`

### Scenario SC_08: mutation 在独占锁内持久提交

- **GIVEN** 健康状态和可提交 mutation
- **WHEN** put/delete 返回成功
- **THEN** 对应完整 record 已 append、flush、fsync；释放锁后启动的新进程能重放该结果
- 测试层：unit
- 依据：用户任务、`J6`

### Scenario SC_09: 最后物理记录损坏要求恢复并可安全截断

- **GIVEN** 健康日志后附加一个缺 LF、截断 UTF-8、坏 JSON、字段/顺序错误或 CRC 错误的最后物理记录
- **WHEN** 先执行普通命令再执行 recover
- **THEN** 普通命令返回 RECOVERY_REQUIRED/退出 6 且不改文件；recover 截断到最后有效边界、fsync、返回准确 truncated_bytes，随后状态等于损坏前状态
- 测试层：e2e
- 依据：`J2`、`J3`、`J11`

### Scenario SC_10: 最后一条之前损坏令所有命令只读失败

- **GIVEN** 任一损坏物理记录之后仍有另一条物理记录
- **WHEN** 执行普通命令或 recover
- **THEN** 返回 CORRUPT_LOG/退出 7，日志、snapshot 和临时文件均不变化
- 测试层：e2e
- 依据：用户任务、`J11`

### Scenario SC_11: 已提交 snapshot 损坏阻止日志猜测恢复

- **GIVEN** `snapshot.json` 存在但 UTF-8、JSON、schema 或内部一致性损坏，同时日志可能含有效记录
- **WHEN** 执行任一命令含 recover
- **THEN** 返回 CORRUPT_SNAPSHOT/退出 8，所有持久化文件保持不变
- 测试层：e2e
- 依据：`J8`、`J11`

### Scenario SC_12: compact 原子保存完整状态并清空日志

- **GIVEN** 健康状态包含 live key、tombstone、非零 last seq 和多个 request_id
- **WHEN** 在独占锁中执行 compact
- **THEN** snapshot 经 tmp flush/fsync、replace、目录 fsync 提交，events.log 经独立 tmp/replace/目录 fsync 成为空文件，返回当前 snapshot_seq，state-dir 仅含固定布局文件
- 测试层：unit
- 依据：用户任务、`J8`

### Scenario SC_13: compact 后重启保持 seq 与幂等历史

- **GIVEN** 已 compact 的状态及遗留未提交 tmp 文件
- **WHEN** 新进程读取、重试 compact 前 request_id 并提交下一 mutation
- **THEN** tmp 被忽略；状态/tombstone/version 不变；重试不追加且返回首次结果；下一 seq 为 snapshot last seq + 1；健康 compact/recover 可重复成功
- 测试层：e2e
- 依据：`J9`、`J10`

### Scenario SC_14: 多进程写入串行化且无丢失

- **GIVEN** 多个进程同时写不同 key，或以相同 expected_version 写同一 key
- **WHEN** 所有进程通过同一 state-dir 的 writer.lock 竞争
- **THEN** 不同 key 全部成功且 seq 唯一连续；同 key 只有一个成功，其余 VERSION_CONFLICT；重启后最终状态与成功记录完全一致
- 测试层：e2e
- 依据：用户任务、`J6`
