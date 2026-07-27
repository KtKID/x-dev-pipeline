> spec_version: 3
> adversarial_risk_version: 1
> complexity: 4
> importance: 4
> risk_average: 4.0
> review_budget: full
> adversarial_review: pending

# Journal Index Recovery

## 任务目标

- 在 `fixture/backend/` 提供仅使用 Python 标准库的本地键值日志：`python3 fixture/backend/cli.py --root <state-dir> <command> [arguments]` 在每次调用时从 `snapshot.json` 与 `events.log` 重建状态，并在调用者指定目录内保存全部状态。
- `put`、`delete`、`get`、`list`、`compact`、`recover` 通过 CLI 向 stdout 各输出一个 JSON object；成功结果包含 `ok: true`，任务规定的失败类别输出 `{"ok":false,"error":{"code":"...","message":"..."}}` 与稳定退出码。
- mutation 按规范化 record 的 CRC-32、全局严格递增 `seq`、乐观版本与 state-dir 全局 `request_id` 幂等性持久化；成功返回前完成 append、flush 与 fsync。
- 启动时精确区分可恢复的最后一条物理记录损坏、历史日志损坏与已提交快照损坏；仅 `recover` 可截断可恢复尾部，任何历史损坏与快照损坏均保留只读失败状态。
- `compact` 在独占锁内原子发布完整 snapshot，并以临时文件与 replace 将日志替换为空文件；重启后仍保留业务状态、tombstone 版本、所有请求指纹/首次结果与 seq 单调性。
- 通过 state-dir 内 `writer.lock` 的标准库文件锁串行化 mutation、`recover` 与 `compact`，使跨进程写入无丢失、seq 唯一、同版本竞争存在唯一提交者。

## 非目标

- 分布式复制、远程存储、数据库、守护进程、网络服务与第三方依赖。
- 在日志中间损坏或已提交快照损坏时尝试猜测、回退或修复业务状态。
- 在 state-dir 外保存持久化真相源，或创建数据库、pickle、缓存索引等额外持久化数据。
- 提供任务命令以外的查询、批量写入、鉴权或自动后台压缩策略。

## 风险评分依据

- 复杂度：4。`store.py` 同时承载日志/快照重放、持久幂等、乐观版本、删除、恢复、双文件原子压缩与跨进程临界区；任何次序或持久化边界偏差都会改变重启后的状态。
- 重要性：4。该组件保存所有调用者业务键值和写入结果；数据丢失、重复提交或错误恢复会影响所有使用该 state-dir 的用户核心状态。
- 预算升级：平均分 4.0 对应 `full`；复杂度与重要性均为 4，单维规则也要求至少 `deep`。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `fixture/backend/record.py` | 目标 | 规范化 record、按规范计算/校验 CRC-32，并分类单条记录损坏 | 非 canonical JSON、CRC 输入含 `crc32` 或字段漏检会把受损记录当作已提交数据 → 重放错误状态 | 每条已提交 record 是带换行 UTF-8 JSON；CRC 只覆盖移除 `crc32` 的 object，以 `sort_keys=True` 与 `separators=(",", ":")` 编码，并格式化为 8 位小写十六进制 | J1、J2 |
| `fixture/backend/store.py` | 目标 | 维护 key/tombstone/version、全局 seq、请求指纹/首次结果，重放、恢复及压缩 | 写入未持久化即返回、丢失 tombstone 或请求历史、压缩半完成被当作提交 → 丢失状态、重复副作用或 seq 回退 | `seq` 全局严格递增正整数；key version 为最近 mutation 的 seq（含 tombstone）；每个 request_id 的首次请求指纹和结果在 state-dir 内持续有效 | J3、J4、J5、J6、J7 |
| `fixture/backend/locking.py` | 目标 | 用 `writer.lock` 提供跨进程读写协调 | 两进程在检查 expected_version 后同时写入 → 丢失更新、重复/乱序 seq | mutation、`recover`、`compact` 在独占锁下串行；不同 key 并发 mutation 无丢失且 seq 唯一；相同 key/expected_version 仅一个提交 | J8 |
| `fixture/backend/cli.py` | 目标 / 上游 | 解析稳定命令参数，调用 store 并编码 stdout JSON 与退出码 | 参数、业务错误或诊断混入 stdout → 调用者无法稳定解析或判断失败 | 每次命令 stdout 恰有一个 JSON object；stderr 仅诊断；任务表中的每种错误使用对应 exit | J9 |
| `<state-dir>/events.log` | 上游 / 下游 | 接收追加的提交 record；恢复和压缩时被截断/替换 | 最后一条与历史损坏混淆、临时替换中断 → 误改历史或将未提交记录可见 | 最后一个有效边界以前的数据保持字节语义；仅可恢复尾部可截断到该边界；历史损坏时所有命令只读失败 | J2、J6 |
| `<state-dir>/snapshot.json`、`.tmp` | 下游 / 相关 | compact 发布已提交 snapshot，启动加载 snapshot 并忽略遗留 tmp | 临时 snapshot 误作为提交或已提交快照坏后回放日志猜测 → 使用错误状态 | `.tmp` 始终代表未提交尝试；已提交 snapshot 损坏返回 `CORRUPT_SNAPSHOT`；snapshot 保留任务规定的全部状态与请求历史 | J6、J7 |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | record 字段为 `crc32`、`expected_version`、`key`、`op`、`request_id`、`seq`、`value`；`delete.value` 为 `null` | 用户任务 `01-record-and-state.md` | 任务给出完整 record JSON、CRC 算法与 delete 值规则 | 已确认 |
| J2 | 已提交 record 每行是带 `\n` 的 UTF-8 JSON；最后物理记录的 UTF-8 截断、缺换行、JSON/字段/CRC 错误可恢复，之前任意记录错误为不可恢复 | 用户任务 `01-record-and-state.md`、`02-recovery-and-compaction.md` | 任务明确物理记录格式与两类损坏位置/后果 | 已确认 |
| J3 | `seq` 是全局严格递增正整数，key version 是最近一次 put/delete 的 seq；tombstone version 参与 version 校验 | 用户任务 `01-record-and-state.md` | 任务定义全局 seq 与删除后的版本语义 | 已确认 |
| J4 | `put` 写字符串；未出现 key 的 expected_version 为 0；已出现 key 用最近 mutation seq；冲突不写日志；未出现 key 的 delete 返回 `NOT_FOUND` | 用户任务 `01-record-and-state.md` | 任务定义 mutation 状态机 | 已确认 |
| J5 | request_id 在 state-dir 全局唯一；同一完整请求返回首次原始结果且不追加，不同内容返回 `IDEMPOTENCY_CONFLICT` 且不追加 | 用户任务 `01-record-and-state.md` | 任务定义幂等边界与禁止副作用 | 已确认 |
| J6 | 每条新 record 在独占锁内 append、flush、fsync 后才能成功；`recover` 只处理可恢复尾部并 fsync；历史损坏使所有命令（含 recover）只读失败 | 用户任务 `01-record-and-state.md`、`02-recovery-and-compaction.md`、`03-cli-and-concurrency.md` | 任务规定提交顺序、恢复操作和锁范围 | 已确认 |
| J7 | compact 依序写/flush/fsync `snapshot.json.tmp`、replace+目录 fsync 发布 snapshot、再同法以空日志替换 events.log；snapshot 保存 last seq、每 key value/tombstone/version、所有 request 指纹和首次结果 | 用户任务 `02-recovery-and-compaction.md` | 任务给出精确发布顺序、存储内容与重启不变量 | 已确认 |
| J8 | `writer.lock` 使用标准库文件锁；mutation、recover、compact 串行；不同 key 的并发写无丢失/seq 唯一，同 key/expected_version 仅一个提交 | 用户任务 `03-cli-and-concurrency.md` | 任务定义并发操作集合和两个竞争结果 | 已确认 |
| J9 | CLI 命令、成功字段、失败 JSON 与稳定退出码固定；stdout 每次仅一个 JSON object | 用户任务 `00-overview.md`、`03-cli-and-concurrency.md` | 任务给出入口、命令、响应字段、错误表与 stdout 规则 | 已确认 |
| J10 | state-dir 首次调用可创建 `events.log`、`writer.lock`，固定布局外禁止数据库、pickle、缓存索引或其他持久化真相源 | 用户任务 `specs/storage-layout.md` | 任务给出固定文件布局与限制 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `record.py` → `events.log` → 启动重放 → store/CLI，及 SC_01、SC_08、SC_19 |
| 状态 | key 的 live/tombstone/version、last seq、request_id 指纹/首次结果，见 J3、J5、J7 与 SC_03–SC_07、SC_19 |
| 时序 | append/flush/fsync、recover 截断、snapshot 与日志 replace/目录 fsync、锁内串行化，见 J6–J8 与 SC_09–SC_18、SC_24–SC_26 |
| 资源 | `events.log`、snapshot 临时/已提交文件、`writer.lock` 与 state-dir 目录 fsync，见影响边界与 SC_15–SC_18、SC_28 |
| 不变量 | `影响边界与不变量`、J1–J10 与所有 Scenarios |
| 故障 | 日志尾部、历史日志、已提交 snapshot、CRC/字段、版本和幂等冲突，见 SC_05–SC_07、SC_09–SC_14、SC_22 |

## 验收清单

### 单元测试

- [ ] record 编码器以任务规定 canonical JSON 字节生成 8 位小写 CRC，解码器区分完整有效 record 与字段/CRC/JSON/UTF-8 故障。
- [ ] store 覆盖初始 put、update、tombstone、get/list 可见性、严格全局 seq、expected_version 与未出现 key 的 delete。
- [ ] store 覆盖相同 request_id 的相同请求回放首次结果和不同请求内容的 `IDEMPOTENCY_CONFLICT`，两者均断言追加次数。
- [ ] 重放/恢复分类覆盖四种尾部故障、历史损坏、遗留 snapshot tmp 与已提交 snapshot 损坏。
- [ ] compact 测试断言 snapshot 的 last seq、所有 key（含 tombstone/version）、请求指纹/首次结果，以及发布步骤中的 flush/fsync/replace/目录 fsync 调用顺序。
- [ ] 以可控文件锁或进程级测试夹具验证 mutation、recover、compact 的互斥和同 version 竞争的唯一提交。

### Smoke 测试

- [ ] 用真实 `python3 fixture/backend/cli.py --root <temporary-state-dir>` 顺序执行 put、get、delete、list、compact、重启后的 get/list 与幂等重试；逐次解析 stdout 的唯一 JSON object、成功字段和持久状态。
- [ ] 用真实日志文件写入可恢复尾部后断言普通命令为 exit 6 / `RECOVERY_REQUIRED`，执行 recover 后断言截断结果、重启状态与健康日志下的 `truncated_bytes`。
- [ ] 用真实 CLI 验证 `NOT_FOUND`、`VERSION_CONFLICT`、`IDEMPOTENCY_CONFLICT`、`CORRUPT_LOG`、`CORRUPT_SNAPSHOT` 分别输出规定错误 JSON 和 exit 3/4/5/7/8。

### E2E 测试

- 决策：需要
- 依据：跨独立 Python 进程共享同一 state-dir 的锁、文件 append 与压缩发布共同决定数据完整性，单进程替身无法证明任务规定的并发契约。
- [ ] 并行启动多个真实 CLI mutation 进程，验证不同 key 全部可恢复且 seq 唯一；并行相同 key/expected_version 请求时仅一个 `ok: true`，其余 exit 4。

## 测试驱动开发

1. `SC_01`、`SC_02`、`SC_03`、`SC_04` → 先写 record canonicalization 和基本状态机的 unit tests。
2. `SC_05`、`SC_06`、`SC_07`、`SC_08` → 先写失败不追加和持久幂等的 unit tests。
3. `SC_09`、`SC_10`、`SC_11`、`SC_12`、`SC_13`、`SC_14` → 先写重放分类、recover 与 snapshot 读取的 unit/smoke tests。
4. `SC_15`、`SC_16`、`SC_17`、`SC_18`、`SC_19` → 先写 compact 发布、重启状态和临时文件的 unit/smoke tests。
5. `SC_20`、`SC_21`、`SC_22`、`SC_23` → 先写真实 CLI 的 JSON、排序、退出码和固定布局 smoke tests。
6. `SC_24`、`SC_25`、`SC_26`、`SC_27`、`SC_28` → 先写多进程与持久化顺序的 e2e/unit tests。
7. 实现满足测试的最小代码，重构后复跑全部已选测试层。

## 对抗性审查记录

| Review | 预算 | 匹配 issue | 被推翻假设 | 新增 Scenario |
|---|---|---|---|---|
| ARV-pending | full | 待审查 | 待审查 | 待审查 |

## Scenarios

### Scenario SC_01: Canonical CRC record round trip

- **GIVEN** 一个含所有规定字段的 put record，且 `crc32` 尚未写入。
- **WHEN** record 被按规定 canonical JSON 字节编码、计算 CRC 并再解码。
- **THEN** 输出 record 的 `crc32` 等于对移除 `crc32` object 的 `zlib.crc32` 8 位小写十六进制，解码结果保留原字段并被判为有效。
- 测试层：unit
- 依据：J1
- 来源：initial-spec

### Scenario SC_02: Delete record carries a null value

- **GIVEN** 一个 `op: "delete"` 的已提交 record。
- **WHEN** record 被编码并由启动重放解码。
- **THEN** `value` 为 JSON `null`，重放后该 key 的业务值不可见且其 mutation 仍提供 version。
- 测试层：unit
- 依据：J1、J3
- 来源：initial-spec

### Scenario SC_03: Initial put and update allocate global versions

- **GIVEN** 空 state-dir，随后对 `alpha` 以 expected_version 0 put，再以该返回 version 更新 `alpha`。
- **WHEN** 两次 mutation 都提交成功。
- **THEN** 两条 record 的 seq 为连续正整数；第二个结果和 `alpha` 当前 version 都等于第二条 record 的 seq。
- 测试层：unit
- 依据：J3、J4
- 来源：initial-spec

### Scenario SC_04: Tombstone version participates in recreation

- **GIVEN** key 已由某个 seq delete 为 tombstone。
- **WHEN** 对该 key 发出 expected_version 为 0 的 put，随后发出 expected_version 为 tombstone seq 的 put。
- **THEN** 前一请求返回 `VERSION_CONFLICT` 且不写日志，后一请求成功且产生高于 tombstone 的新 seq。
- 测试层：unit
- 依据：J3、J4
- 来源：initial-spec

### Scenario SC_05: Missing-key delete returns without a record

- **GIVEN** 从未出现过的 key 和空日志。
- **WHEN** 发出带 expected_version 0 的 delete。
- **THEN** 返回 `NOT_FOUND`，`events.log` 没有新增 record，last seq 保持不变。
- 测试层：unit
- 依据：J4、J9
- 来源：initial-spec

### Scenario SC_06: Version conflict has no write side effect

- **GIVEN** 一个当前 version 为 N 的 live 或 tombstone key。
- **WHEN** mutation 使用非 N 的 expected_version。
- **THEN** 返回 `VERSION_CONFLICT`，日志字节数、last seq、key 状态和 request_id 历史保持调用前的值。
- 测试层：unit
- 依据：J3、J4
- 来源：initial-spec

### Scenario SC_07: Exact request retry replays first result

- **GIVEN** 一个已成功提交的 put 或 delete 及其 request_id。
- **WHEN** 使用完全相同的 op、key、value、expected_version 和 request_id 重试。
- **THEN** 返回首次提交的原始 `seq`、`key`、`version` 与结果字段并标记 `replayed: true`，且不追加日志。
- 测试层：unit
- 依据：J5、J9
- 来源：initial-spec

### Scenario SC_08: Reused request id with different content is rejected

- **GIVEN** request_id 已对应一次已提交请求。
- **WHEN** 同一 request_id 携带任一不同的 op、key、value 或 expected_version。
- **THEN** 返回 `IDEMPOTENCY_CONFLICT`，日志字节数、last seq、key 状态与原请求映射保持不变。
- 测试层：unit
- 依据：J5、J9
- 来源：initial-spec

### Scenario SC_09: UTF-8-truncated final record requires recovery

- **GIVEN** `events.log` 的所有完整记录有效，最后一个物理 record 在 UTF-8 字符中截断。
- **WHEN** 执行普通命令。
- **THEN** 返回 `RECOVERY_REQUIRED` 与 exit 6，且命令不改写日志或业务状态。
- 测试层：smoke
- 依据：J2、J6、J9
- 来源：initial-spec

### Scenario SC_10: Final record without newline requires recovery

- **GIVEN** `events.log` 最后一条物理记录是完整 JSON 但缺少末尾 `\n`，更早记录有效。
- **WHEN** 执行普通命令。
- **THEN** 返回 `RECOVERY_REQUIRED` 与 exit 6，且最后记录在 recover 前不进入重放状态。
- 测试层：smoke
- 依据：J2、J6、J9
- 来源：initial-spec

### Scenario SC_11: Final JSON, field, or CRC defect requires recovery

- **GIVEN** 有效日志前缀后分别追加最后一条 JSON 解析失败、必填字段错误或 CRC 不匹配的 record。
- **WHEN** 每个日志副本执行普通命令。
- **THEN** 每个副本均返回 `RECOVERY_REQUIRED` 与 exit 6，且有效前缀状态保持可用于后续 recover。
- 测试层：unit
- 依据：J1、J2、J6
- 来源：initial-spec

### Scenario SC_12: Earlier log corruption blocks every command

- **GIVEN** `events.log` 中最后物理记录之前存在 UTF-8、JSON、字段或 CRC 损坏，末尾另有物理记录。
- **WHEN** 依次执行 get、put、compact 与 recover。
- **THEN** 每个命令返回 `CORRUPT_LOG` 与 exit 7，日志与 snapshot 的内容保持不变。
- 测试层：smoke
- 依据：J2、J6、J9
- 来源：initial-spec

### Scenario SC_13: Recover truncates only the recoverable tail

- **GIVEN** 有效日志前缀和一个可恢复的最后物理 record，记录可恢复尾部前的字节边界。
- **WHEN** 执行 recover。
- **THEN** `events.log` 截断到该边界并 fsync，结果返回实际 `truncated_bytes`；重启后的状态只包含有效前缀。
- 测试层：smoke
- 依据：J2、J6、J9
- 来源：initial-spec

### Scenario SC_14: Recover is idempotent for a healthy log

- **GIVEN** 每条物理 record 都有效并以换行结束的日志。
- **WHEN** 连续两次执行 recover。
- **THEN** 两次均成功，均不改写有效 record，且每次 `truncated_bytes` 为 0。
- 测试层：smoke
- 依据：J2、J6、J9
- 来源：initial-spec

### Scenario SC_15: Uncommitted snapshot temp is ignored at startup

- **GIVEN** 一个有效 `snapshot.json` 或无 snapshot 的有效日志，以及遗留的 `snapshot.json.tmp`。
- **WHEN** 启动命令重建状态。
- **THEN** 状态只来自已提交 snapshot 与有效 log，`.tmp` 内容不改变结果。
- 测试层：unit
- 依据：J7
- 来源：initial-spec

### Scenario SC_16: Corrupt committed snapshot never falls back to guessed log state

- **GIVEN** `snapshot.json` 已存在且内容损坏，同时 events.log 存在可重放记录。
- **WHEN** 执行每种 CLI 命令，包括 recover。
- **THEN** 每次返回 `CORRUPT_SNAPSHOT` 与 exit 8，且不以 events.log 构造替代状态或改写文件。
- 测试层：smoke
- 依据：J7、J9
- 来源：initial-spec

### Scenario SC_17: Compact snapshot contains complete durable state

- **GIVEN** 已提交的 live key、tombstone key、last seq，以及多个 request_id 的指纹和首次结果。
- **WHEN** 执行 compact。
- **THEN** 发布的 snapshot 包含全局 last seq、每个 key 的 value/tombstone/version 与全部 request_id 映射，且 compact 结果的 `snapshot_seq` 等于该 last seq。
- 测试层：unit
- 依据：J3、J5、J7、J9
- 来源：initial-spec

### Scenario SC_18: Compact publishes snapshot before clearing log

- **GIVEN** 含有效记录的 events.log 与可记录 flush、fsync、replace、目录 fsync 调用的文件系统替身。
- **WHEN** 执行 compact。
- **THEN** 调用顺序为 snapshot tmp 写入/flush/fsync、replace 为 snapshot/目录 fsync、空 events log tmp 写入/flush/fsync、replace 为 events.log/目录 fsync；任一步失败不报告 compact 成功。
- 测试层：unit
- 依据：J6、J7
- 来源：initial-spec

### Scenario SC_19: Restart after compact preserves state and idempotency

- **GIVEN** 已 compact 的 state-dir，其中有 live/tombstone key 和一个已提交 request_id。
- **WHEN** 在新进程中执行 get、list、使用 tombstone version 的 put 及原 request_id 的相同重试。
- **THEN** get/list 显示与 compact 前相同 live 状态，put 使用连续高于 snapshot seq 的 seq，重试返回原始结果且不追加重复 record。
- 测试层：smoke
- 依据：J3、J5、J7
- 来源：initial-spec

### Scenario SC_20: CLI emits exactly one JSON object on stdout

- **GIVEN** 每个支持命令的一次成功调用与一次任务规定的失败调用。
- **WHEN** 通过公开 CLI 入口执行。
- **THEN** 每次 stdout 恰可解析为一个 JSON object，成功对象含 `ok: true`，失败对象的 `error.code` 为相应稳定代码，诊断内容只允许在 stderr。
- 测试层：smoke
- 依据：J9
- 来源：initial-spec

### Scenario SC_21: Command errors use stable exit codes

- **GIVEN** 参数/命令错误、NOT_FOUND、VERSION_CONFLICT、IDEMPOTENCY_CONFLICT、RECOVERY_REQUIRED、CORRUPT_LOG 与 CORRUPT_SNAPSHOT 的独立调用。
- **WHEN** 每个调用完成。
- **THEN** 进程分别以 2、3、4、5、6、7、8 退出，并输出对应的错误 JSON。
- 测试层：smoke
- 依据：J9
- 来源：initial-spec

### Scenario SC_22: List exposes only live keys in lexical order

- **GIVEN** 以非字典序写入多个 key，并删除其中一个 key。
- **WHEN** 执行 list。
- **THEN** `items` 只含 live key，按 key 字典序排列，每项含 key、value、version，已删除 key 不出现。
- 测试层：unit
- 依据：J3、J9
- 来源：initial-spec

### Scenario SC_23: Get returns stored value and mutation version

- **GIVEN** 一个由 put 提交且尚未删除的 key。
- **WHEN** 执行 get。
- **THEN** 返回该 key、字符串 value 与最近 put 的 seq 作为 version；成功对象含 `ok: true`。
- 测试层：unit
- 依据：J3、J4、J9
- 来源：initial-spec

### Scenario SC_24: Concurrent different-key mutations retain all records

- **GIVEN** 多个独立进程对同一 state-dir 的不同新 key 发出 expected_version 0 的 put。
- **WHEN** 这些 mutation 并发运行。
- **THEN** 每个请求成功且各 record 均被重启后的重放状态保留，所有返回 seq 全局唯一并形成严格递增日志顺序。
- 测试层：e2e
- 依据：J3、J6、J8
- 来源：initial-spec

### Scenario SC_25: Same-version concurrent updates have one winner

- **GIVEN** 一个当前 version 为 N 的 key，多个独立进程使用该 N 发送不同 request_id 的 mutation。
- **WHEN** 这些 mutation 并发运行。
- **THEN** 恰一个请求提交并产生 N 之后的 version，其余均返回 `VERSION_CONFLICT` 与 exit 4，日志仅新增一个 record。
- 测试层：e2e
- 依据：J3、J4、J6、J8
- 来源：initial-spec

### Scenario SC_26: Recover and compact are serialized with mutation

- **GIVEN** 一个含可恢复尾部或待 compact 有效状态的 state-dir，以及并发的 mutation 与 recover 或 compact 请求。
- **WHEN** 请求在不同进程中重叠执行。
- **THEN** 操作按 `writer.lock` 的独占顺序完成，每次成功 mutation 的 record 仅出现一次，recover/compact 结果对应某个完整串行前缀，重启重放无损坏分类。
- 测试层：e2e
- 依据：J6、J7、J8
- 来源：initial-spec

### Scenario SC_27: Successful mutation waits for durable append

- **GIVEN** 一个能够记录 append、flush 与 fsync 的 events.log 文件替身。
- **WHEN** 执行首次成功的 put 或 delete。
- **THEN** 在向调用方返回成功之前，该 record 已在独占锁内依次 append、flush、fsync；任一阶段抛错时调用不返回成功结果。
- 测试层：unit
- 依据：J6
- 来源：initial-spec

### Scenario SC_28: First command creates only the fixed storage layout

- **GIVEN** 一个不存在的 state-dir。
- **WHEN** 执行首次支持的 CLI 命令。
- **THEN** state-dir 可被创建并包含初始化所需的 `events.log` 与 `writer.lock`；持久化文件仅来自固定布局的 `events.log`、`snapshot.json`、临时文件和 `writer.lock`，不出现数据库、pickle、缓存索引或其他持久化真相源。
- 测试层：smoke
- 依据：J10
- 来源：initial-spec
