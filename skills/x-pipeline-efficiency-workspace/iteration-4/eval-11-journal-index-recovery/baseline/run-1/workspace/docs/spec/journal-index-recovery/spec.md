> spec_version: 3

# Journal Index Recovery

## 任务目标

- `python3 fixture/backend/cli.py --root <state-dir> <command> [arguments]` 提供仅依赖 Python 标准库的本地键值日志。
- 每个命令从已提交 snapshot 与 journal 重建可观察状态；`put`、`delete`、`get`、`list`、`compact`、`recover` 满足本规格的状态、恢复、输出与退出码契约。
- 所有状态限定在调用者指定目录的固定存储布局内；stdout 为单个 JSON object。

## 非目标

- 网络服务、守护进程、数据库、第三方包、缓存索引与其他持久化真相源属于本次范围外内容。
- 跨主机分布式协调、权限模型、日志归档与增量 snapshot 属于本次范围外内容。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `fixture/backend/record.py` | 目标 | 提供 canonical JSON record 的 CRC-32 编解码与字段校验 | 任意序列化差异 → CRC 与重放结果分歧 → 有效日志误判损坏 | 编码结果为一行 UTF-8 JSON 加 `\\n`；CRC 基于移除 `crc32` 后的规范 JSON；解码只接受完整且 CRC 匹配的 record | `J1` |
| `fixture/backend/store.py` | 目标 | 重放 snapshot/log，执行状态机、幂等、版本、恢复与压缩 | 写入、重放或压缩窗口中的状态丢失 → 版本/请求历史错误 → 数据或幂等语义损坏 | 全局 `seq` 严格递增；key version 等于最近 mutation 的 seq；请求指纹和首次结果跨重启、压缩保留 | `J2`、`J3`、`J4`、`J5` |
| `fixture/backend/locking.py` | 目标 | 提供 state-dir 级跨进程共享/独占文件锁 | 并发 mutation 的检查与追加交错 → 重复 seq 或丢失更新 → 持久状态损坏 | mutation、`recover`、`compact` 在同一独占锁中完成重放、决策与写入；读取在共享锁中观察一致文件集 | `J6` |
| `fixture/backend/cli.py` | 目标/下游 | 解析参数，调度 store，输出 JSON 和稳定退出码 | 异常泄漏或 stdout 杂讯 → 调用方无法可靠处理结果 | 每次调用 stdout 恰有一个 JSON object；成功含 `ok:true`；规定错误码映射稳定 | `J7` |
| `snapshot.json`、`events.log` | 下游 | 承载已提交快照与 journal | 临时文件或已提交 snapshot 误用 → 回退到错误状态 → 已确认数据丢失 | `snapshot.json.tmp` 始终忽略；已提交 snapshot 损坏产生 `CORRUPT_SNAPSHOT`；每个 commit append 后完成 flush+fsync | `J3`、`J4` |
| 调用 CLI 的并发进程 | 上游 | 提供参数、重试与竞争写入 | 同版本竞争写入同时成功 → 乐观版本失效 → 覆盖更新 | 不同 key 并发 mutation 全部持久化且 seq 唯一；同 key、相同 expected version 的竞争仅一个首次提交成功 | `J2`、`J6` |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | record 的字段集合固定为 `crc32`、`expected_version`、`key`、`op`、`request_id`、`seq`、`value`；`seq` 为正整数，`expected_version` 为非负整数，`put` value 为 string，`delete` value 为 `null` | `task/01-record-and-state.md` | 题面给出字段样例、CRC 输入与操作语义；字段错误属于损坏分类 | 已确认 |
| J2 | 状态同时保存每个 key 最近 mutation（value/tombstone/version）、全局最后 seq 与每个 request_id 的输入指纹和首次结果 | `task/01-record-and-state.md`、`task/02-recovery-and-compaction.md` | tombstone version 参与校验；compact 后须保持状态、幂等与 seq 单调 | 已确认 |
| J3 | 启动先读取 `snapshot.json`，再从 `events.log` 重放；最后物理 record 的 UTF-8、换行、JSON、字段或 CRC 故障产生 `RECOVERY_REQUIRED`，更早 record 故障产生 `CORRUPT_LOG` | `task/02-recovery-and-compaction.md` | 题面逐项定义尾部与中段分类 | 已确认 |
| J4 | snapshot 采用 UTF-8 JSON object：`last_seq`、`keys`、`requests`；每个 key 保存 `value`、`version`，每个 request 保存 `fingerprint` 与首次成功 result。写入临时文件后 flush+fsync、`os.replace`、目录 fsync | LLM 推断 | 题面规定必须保存内容与原子提交步骤，未固定 snapshot JSON schema；该 schema 是最小直接表示 | 已确认 |
| J5 | 空 `events.log` 合法；healthy `recover` 成功并返回 `truncated_bytes:0`；可恢复尾部按最后有效换行边界截断；`CORRUPT_LOG` 与 `CORRUPT_SNAPSHOT` 对全部命令返回只读失败 | `task/02-recovery-and-compaction.md`、`task/03-cli-and-concurrency.md` | 题面要求健康 recover 幂等成功和损坏分类；零截断字节是可判定最小结果 | 已确认 |
| J6 | POSIX 环境使用 `fcntl.flock` 操作 state-dir 内 `writer.lock`；`exclusive=False` 使用共享锁，`exclusive=True` 使用独占锁 | `task/03-cli-and-concurrency.md`、`task/specs/storage-layout.md` | Python 标准库中的进程级文件锁满足执行环境的真实 CLI 子进程并发需求 | 已确认 |
| J7 | CLI 成功 JSON 采用：mutation `ok,seq,key,version,replayed`，`get` 为 `ok,key,value,version`，`list` 为 `ok,items`，`compact` 为 `ok,snapshot_seq`，`recover` 为 `ok,truncated_bytes`；缺失或 tombstoned key 返回 `NOT_FOUND`。参数形状或数值错误返回 exit 2 | `task/03-cli-and-concurrency.md`，LLM 推断 | 题面列出成功字段与错误表，未给出 `list` 容器名和 get 缺失规则；`items` 与 `NOT_FOUND` 是最小稳定 API 选择 | 已确认 |
| J8 | 重试响应复用首次结果中的 `seq`、`key`、`version`，并将本次响应的 `replayed` 设为 `true` | `task/01-record-and-state.md`、`task/03-cli-and-concurrency.md` | “原始结果”约束持久业务结果；CLI 同时明示重试的 `replayed:true` | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `J1`、`J2`、`SC_01`、`SC_03`、`SC_10` 覆盖 CLI 参数、record、journal、snapshot 与 JSON 响应。 |
| 状态 | `影响边界与不变量` 的 store 行、`J2`、`SC_02` 至 `SC_07` 覆盖 live value、tombstone、version、seq 与 request history。 |
| 时序 | `J3`、`J5`、`J6`、`SC_08` 至 `SC_13` 覆盖重放、fsync、原子 replace、恢复与并发顺序。 |
| 资源 | `J4`、`J6`、`SC_10`、`SC_11` 覆盖 lock file、文件句柄、临时文件与状态目录 fsync。 |
| 不变量 | `影响边界与不变量`，由 `SC_01` 至 `SC_13` 观察验证。 |
| 故障 | `J3`、`J5`、`J7`、`SC_08`、`SC_09`、`SC_12`、`SC_13` 覆盖损坏、冲突、恢复与参数失败。 |

## 验收清单

### 单元测试

- [ ] `record.py` 对 canonical CRC 编码、完整 decode、字段类型/操作/value/CRC 拒绝与末尾换行断言。
- [ ] store 状态机覆盖 put/update/delete/tombstone version、缺失删除、版本冲突、重试、idempotency conflict、跨重启与 list 排序。
- [ ] recovery 覆盖每种尾部故障、前置故障、snapshot 损坏、healthy recover 与截断后重放。
- [ ] compact 覆盖 snapshot 内容、跨重启、临时 snapshot 忽略、request history 与 seq 保留。

### Smoke 测试

- [ ] 以真实 `python3 fixture/backend/cli.py --root <临时目录>` 子进程执行完整 put/get/list/delete/retry/compact/restart/recover 链路，逐次校验单 JSON stdout、结果字段和退出码。
- [ ] 启动多个 CLI 子进程竞争 mutation，校验不同 key 全部写入、seq 唯一、同 key 同版本仅一个成功。

### E2E 测试

- 决策：省略
- 依据：系统由本地文件与 CLI 子进程组成；Smoke 已覆盖真实进程、文件系统、锁和重启链路。

## 测试驱动开发

1. `SC_01`、`SC_02` → 先写 `test_record_codec` 与 `test_put_get_version`。
2. `SC_03`、`SC_04`、`SC_05`、`SC_06`、`SC_07` → 先写 `test_delete_and_tombstone`、`test_version_conflict`、`test_idempotent_replay`、`test_idempotency_conflict`、`test_list_sorted`。
3. `SC_08`、`SC_09`、`SC_10`、`SC_11` → 先写 `test_tail_recovery`、`test_middle_corruption`、`test_snapshot_corruption_and_tmp`、`test_compact_restart`。
4. `SC_12`、`SC_13` → 先写 `test_cli_contract` 与 `test_concurrent_mutations`。
5. 实现满足测试的最小代码，重构后复跑全部 unit 与 Smoke 测试。

## Scenarios

### Scenario SC_01: Canonical record encodes and validates CRC

- **GIVEN** 一条合法 `put` 或 `delete` record，包含 `J1` 的全部业务字段。
- **WHEN** 通过 `encode_record` 编码后再通过 `decode_record` 解码。
- **THEN** 字节以单个 `\\n` 结束，record 含小写 8 位 CRC-32，解码结果与编码 record 相同；任意字段、类型、value/op 组合或 CRC 失配触发 `RecordError`。
- 测试层：unit
- 依据：`J1`

### Scenario SC_02: Put creates and updates a versioned live key

- **GIVEN** 新 state-dir，或含 key 当前 version 的健康状态。
- **WHEN** 使用该 version 的 `put --key --value --request-id --expected-version`。
- **THEN** 首次响应含 `ok:true`、新的全局严格递增 `seq`、相同 `key` 与 `version:seq`、`replayed:false`；随后 get 返回该 value 和 version。
- 测试层：unit
- 依据：`J1`、`J2`、`J7`

### Scenario SC_03: Delete writes tombstone and retains its version

- **GIVEN** 已存在 live key，及其当前 version。
- **WHEN** 使用该 version 执行 delete。
- **THEN** mutation 返回新 seq/version；get 返回 `NOT_FOUND`；后续 put 必须携带 tombstone 的 version 才能成功。
- 测试层：unit
- 依据：`J1`、`J2`、`J7`

### Scenario SC_04: Missing delete and stale expected version leave journal unchanged

- **GIVEN** 健康状态中的从未出现 key，或一个已有 key 的过期 expected version。
- **WHEN** 分别执行 delete 或 put/delete。
- **THEN** 缺失 delete 返回 `NOT_FOUND`，过期请求返回 `VERSION_CONFLICT`，`events.log` 字节、全局 seq 和 request history 保持触发前状态。
- 测试层：unit
- 依据：`J1`、`J2`、`J7`

### Scenario SC_05: Identical request retries replay first result

- **GIVEN** 一个已成功提交的 mutation request_id 与其 op/key/value/expected_version。
- **WHEN** 提交完全相同的 mutation。
- **THEN** 无新增日志行，响应复用首次 `seq`、`key`、`version`，并含 `replayed:true`。
- 测试层：unit
- 依据：`J2`、`J8`

### Scenario SC_06: Request-id content change is rejected

- **GIVEN** 一个已成功提交 request_id。
- **WHEN** 提交相同 request_id 且 op、key、value 或 expected_version 中任一字段改变的 mutation。
- **THEN** 返回 `IDEMPOTENCY_CONFLICT`，journal、seq、key state 与 request history 保持原值。
- 测试层：unit
- 依据：`J2`、`J7`

### Scenario SC_07: List exposes live items in key order

- **GIVEN** 含多个 live key、tombstone key 与空状态的健康 store。
- **WHEN** 执行 list。
- **THEN** 响应 `items` 只含 live key，按 key 字典序升序；每项含 key、value、version。
- 测试层：unit
- 依据：`J2`、`J7`

### Scenario SC_08: Recover repairs only a final invalid physical record

- **GIVEN** 有效 record 前缀后追加截断 UTF-8、无换行、JSON、字段或 CRC 故障的最后物理 record。
- **WHEN** 普通命令与 `recover` 分别执行。
- **THEN** 普通命令返回 `RECOVERY_REQUIRED`；recover 截断至最后有效 record 边界并 fsync，返回实际 `truncated_bytes`；随后重放前缀状态。
- 测试层：unit
- 依据：`J3`、`J5`

### Scenario SC_09: Earlier invalid record makes entire log read-only corrupt

- **GIVEN** `events.log` 中任一非最后 record 存在 UTF-8、换行、JSON、字段或 CRC 故障。
- **WHEN** 执行每个 store 命令，包括 recover。
- **THEN** 响应错误 code 为 `CORRUPT_LOG`，文件内容保持原字节。
- 测试层：unit
- 依据：`J3`、`J5`

### Scenario SC_10: Snapshot validates as committed state and ignores abandoned tmp

- **GIVEN** 健康状态目录含已提交 snapshot、journal，或单独遗留 `snapshot.json.tmp`。
- **WHEN** 新进程加载 store。
- **THEN** 已提交 snapshot 重建 J2 的完整状态后继续重放 journal；`snapshot.json.tmp` 未参与状态；已提交 snapshot 的 JSON 或 schema 故障返回 `CORRUPT_SNAPSHOT`。
- 测试层：unit
- 依据：`J2`、`J4`、`J5`

### Scenario SC_11: Compact atomically preserves restart semantics

- **GIVEN** 含 live key、tombstone、多个 request_id 和非零最后 seq 的健康 store。
- **WHEN** 执行 compact 后由新进程加载并提交新的 mutation 或重试旧 request。
- **THEN** `snapshot_seq` 等于 compact 前最后 seq；journal 为空；key state、version、idempotency 结果保持；新 mutation 使用更大 seq。
- 测试层：unit
- 依据：`J2`、`J4`

### Scenario SC_12: CLI emits stable JSON and exits

- **GIVEN** 每种成功命令、每个规定 store error 与错误参数。
- **WHEN** 通过真实 CLI 子进程调用。
- **THEN** stdout 解析为唯一 JSON object；成功含 `ok:true` 和规定字段；错误为 `ok:false,error.code,error.message`；exit 依 J7 的表为 2、3、4、5、6、7 或 8。
- 测试层：smoke
- 依据：`J7`

### Scenario SC_13: Cross-process lock serializes mutation, recovery and compaction

- **GIVEN** 多个真实 CLI 进程共享同一 state-dir，包含不同 key mutation、同 key 同 expected version mutation，以及 compact/recover 与 mutation 的重叠启动。
- **WHEN** 进程并发执行。
- **THEN** journal 可完整解码；不同 key 的成功 mutation 全部可读且 seq 唯一；同 key 竞争产生一个成功和其余 `VERSION_CONFLICT`；compact/recover 完成后 state 可重启重放。
- 测试层：smoke
- 依据：`J3`、`J4`、`J6`
