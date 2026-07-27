> spec_version: 3
> adversarial_risk_version: 2
> complexity: 5
> importance: 1
> risk_average: 3.0
> review_budget: full
> adversarial_review: complete

# journal-index-recovery

## 任务目标

- 在 `fixture/backend/` 提供仅用 Python 标准库实现的本地键值日志 CLI：`python3 fixture/backend/cli.py --root <state-dir> <command> [arguments]`。
- 每个命令从已提交 `snapshot.json`（如有）和 `events.log` 重建可见状态；支持带 CRC-32 的追加记录、乐观版本、删除、跨重启幂等、尾部恢复、原子压缩和多进程写入。
- 每次调用仅向 stdout 写一个 JSON object；成功含 `ok: true`，失败含稳定错误码和指定退出码。

## 非目标

- 不引入数据库、守护进程、网络、第三方包，或 `state-dir` 中未列出的持久化真相源。
- 不为已损坏的已提交 snapshot 从日志猜测、回退或修复状态；该情形必须失败。
- 不把非末条日志损坏当作可截断尾部，也不允许 `recover` 改写它。
- 不定义任务未要求的跨目录复制、远程同步、鉴权、加密、历史查询或后台自动恢复。

## 风险评分依据

- 复杂度：5；需要跨进程文件锁、同一 request 的幂等状态、严格递增序号、崩溃后的尾部分类，以及 snapshot/log 的多阶段原子替换和目录 fsync，命中“锁、崩溃恢复、多阶段持久化提交”。
- 重要性：1；契约限定为调用者指定目录中的本地单用户 CLI，未涉及资金、隐私、合规或共享在线服务。
- 预算升级：平均分 3.0 原本对应 deep；复杂度为 5 命中单维升级规则，风险预算提升为 full。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `fixture/backend/record.py` | 目标 | 规范化 put/delete record，计算并验证 UTF-8 JSON 的 CRC-32，区分字段、JSON、UTF-8、换行和 CRC 故障。 | 非规范 JSON 或 CRC 输入包含 `crc32` → 重放接受错误字节或错误分类 → 状态不可信/恢复边界错误。 | 已提交 record 一行一条、末尾 `\n`；CRC 只覆盖移除 `crc32` 后的 canonical JSON；`delete.value` 为 `null`。 | J-02、SC_01、SC_10、SC_11 |
| `fixture/backend/store.py` | 目标 | 从 snapshot + log 建状态，执行业务状态机、版本、request 去重、恢复和 compact。 | 重放、tombstone 或压缩遗漏版本/请求结果 → 重启后错误接受写入或重复提交；snapshot 已提交而旧 log 尚未替换 → 重放重复前缀。 | `seq` 全局严格递增正整数；最近 mutation（含 tombstone）决定 key version；任何冲突均不追加；压缩后语义和 seq 单调不变；snapshot 已涵盖的 log 前缀不得再次作为新 mutation 应用。 | J-03、J-04、J-05、J-06、J-07、SC_02–SC_06、SC_09–SC_20 |
| `fixture/backend/locking.py` | 目标 | 以 `writer.lock` 和标准库文件锁协调跨进程读写；mutation、recover、compact 使用独占协调。 | 并发进程各自基于过期状态 append → 重复/丢失 seq 或两个相同版本同时成功。 | 每个新增 record 在独占锁内 append、flush、fsync 后才成功返回；受串行化的动作不交错。 | J-03、J-08、SC_02、SC_15 |
| `fixture/backend/cli.py` | 目标 | 解析七个命令和参数，调用 store，并输出唯一 JSON object 与稳定退出码。 | 诊断混入 stdout 或错误码漂移 → 调用方无法机器解析或重试。 | stdout 恰有一个 JSON object；失败形状为 `{ok:false,error:{code,message}}`，退出码遵守表格。 | J-01、SC_07、SC_08 |
| 调用者与 state-dir | 上游 | 传入 root、命令和参数；首次命令可创建目录、空 log 与锁文件。 | 未初始化目录或残留 `.tmp` 被视为真相源 → 启动失败或读取未提交状态。 | 固定布局只含 `events.log`、`snapshot.json`、两种临时文件和 `writer.lock`；遗留 `snapshot.json.tmp` 被忽略。 | J-07、SC_09、SC_12、SC_16 |
| 文件系统与重启后的 CLI 调用 | 下游 | 消费追加日志和原子文件替换的已提交状态。 | replace 后未 fsync 目录、先清空日志或写坏 snapshot → 崩溃后丢失最后状态。 | compact 先 fsync 临时 snapshot、replace + fsync 目录，再以临时空 log replace + fsync 目录；损坏已提交 snapshot 只读失败。 | J-06、J-07、SC_13、SC_14 |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J-01 | CLI 命令、成功字段、失败 JSON 形状和错误退出码是公开契约。 | `task/03-cli-and-concurrency.md` | 明列 7 个命令、成功返回字段和 2–8 的退出码表。 | 已确认 |
| J-02 | 日志 record 的 CRC 使用去掉 `crc32` 的 canonical JSON（`sort_keys=True`、紧凑 separators、UTF-8）和小写 8 位十六进制。 | `task/01-record-and-state.md` | 给出字段示例和精确计算规则；记录一行 UTF-8 JSON 且以换行提交。 | 已确认 |
| J-03 | 新记录必须在独占锁中 append、flush、fsync 后才可成功；`seq` 为全局严格递增正整数。 | `task/01-record-and-state.md`、`task/03-cli-and-concurrency.md` | 明确提交顺序及 mutation/recover/compact 的串行化要求。 | 已确认 |
| J-04 | key version 是最近 put/delete 的 seq；缺失或已删除业务值不存在，但 tombstone 的 version 仍参与 expected_version 校验。 | `task/01-record-and-state.md` | 明确了 create 的 expected_version 0、delete 的 tombstone 语义和版本冲突无写入。 | 已确认 |
| J-05 | request_id 在整个 state-dir 唯一；相同完整指纹重试回放首次原始结果，不同内容则幂等冲突，二者皆不得重复追加。 | `task/01-record-and-state.md` | 要求保存 op/key/value/expected_version 指纹和首次结果；compact 后还须保留。 | 已确认 |
| J-06 | 仅物理最后 record 的截断 UTF-8、缺换行、JSON/字段/CRC 故障可恢复；更早任意损坏为 `CORRUPT_LOG`，已提交 snapshot 损坏为 `CORRUPT_SNAPSHOT`。 | `task/02-recovery-and-compaction.md` | 明确故障分类、普通命令行为与 `recover` 的拒绝规则。 | 已确认 |
| J-07 | `compact` 的提交顺序固定，snapshot 要保留 last seq、所有 key 的 value/tombstone/version 和全部 request 元数据；未提交 `snapshot.json.tmp` 忽略。 | `task/02-recovery-and-compaction.md` | 给出了两个临时文件的 flush/fsync、replace、目录 fsync 顺序及保留数据。 | 已确认 |
| J-08 | 多进程不同 key 写入不能丢失且 seq 唯一；同 key 相同期望版本只有一个可提交。 | `task/03-cli-and-concurrency.md` | 明确 writer.lock、标准库文件锁和两个并发结果约束。 | 已确认 |
| J-09 | state-dir 可首次创建但不得存在数据库、pickle、缓存索引或其他持久化真相源。 | `task/specs/storage-layout.md`、`task/00-overview.md` | 固定布局及禁止项已列出。 | 已确认 |
| J-10 | 具有有效 JSON、字段和 CRC 但违反全局 seq 严格递增的末条 record 属于末条“字段错误”；在 `recover` 前保留其字节并对普通命令报告可恢复尾部。 | 任务事实推断 | `seq` 必须全局严格递增（J-03），最后 record 的字段错误可恢复（J-06）；该推断仅确定两条已确认规则的交集。 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `record.py` → `events.log`/`snapshot.json` → `store.py` → `cli.py`；SC_01、SC_07、SC_09、SC_14、SC_17。 |
| 状态 | key 的 live/tombstone/version、全局 seq 和 request 指纹/首次结果；J-04、J-05、SC_02–SC_06、SC_14。 |
| 时序 | append/flush/fsync 后才成功；recover 截断；compact 的两次 replace/目录 fsync；J-03、J-06、J-07、SC_02、SC_10、SC_14、SC_17、SC_20。 |
| 资源 | `writer.lock`、log/snapshot 文件、临时文件和状态目录 fsync 的生命周期；SC_02、SC_12、SC_14、SC_16。 |
| 不变量 | `影响边界与不变量`；由 SC_01–SC_16 提供可观察验证。 |
| 故障 | 尾部可恢复、非尾部 `CORRUPT_LOG`、已提交 snapshot `CORRUPT_SNAPSHOT`、失败后 request_id 重用和幂等/版本拒绝；SC_03、SC_06、SC_08、SC_10、SC_11、SC_13、SC_18、SC_19。 |

## 验收清单

### 单元测试

- [ ] 验证 record 的 canonical CRC 输入、8 位小写 CRC、UTF-8/JSON/字段/CRC 故障分类和最后完整 record 边界（SC_01、SC_10、SC_11）。
- [ ] 验证 put/delete 的 expected_version、tombstone version、`NOT_FOUND`、冲突无追加，以及 request 指纹的回放/冲突（SC_02–SC_06）。
- [ ] 用文件系统调用替身断言新增记录的独占锁 → append → flush → fsync → 成功返回顺序，以及 compact 的临时文件、replace 和目录 fsync 顺序（SC_02、SC_14）。
- [ ] 验证从 snapshot/log 重放、忽略 `snapshot.json.tmp`、拒绝损坏已提交 snapshot 和固定布局（SC_09、SC_12–SC_16）。
- [ ] 构造 CRC 正确但 seq 非严格递增的末条 record，并验证其恢复分类，以及版本冲突后同一 request_id 仍可用于一次合法提交（SC_18、SC_19）。

### Smoke 测试

- [ ] 在临时 state-dir 用真实 `python3 fixture/backend/cli.py` 走 put/get/delete/list、重启、idempotent retry、compact 和 recover，断言 stdout 每次只能解析出一个 JSON object（SC_02、SC_04、SC_05、SC_07、SC_09、SC_14）。
- [ ] 手工构造末行损坏与中间损坏的 `events.log`，验证正常命令、`recover`、截断字节数及退出码（SC_08、SC_10、SC_11）。
- [ ] 模拟 compact 已 replace+fsync snapshot、尚未替换旧 log 的崩溃窗口，并验证重启和下一次写入；对健康日志验证 recover 幂等返回 0（SC_17、SC_20）。

### E2E 测试

- 决策：需要
- 依据：公开入口是跨进程 CLI，正确性依赖真实标准库文件锁、真实文件 fsync/replace 和多个进程的调度，单元替身不能证明无丢失与版本串行化。
- [ ] 并发启动多个 CLI 进程，验证不同 key 全部保留且 seq 唯一，以及相同 key/expected_version 恰一成功、其余 `VERSION_CONFLICT`（SC_15）。

## 测试驱动开发

1. `SC_01` → 先写会失败的 `test_record_canonical_crc_and_validation`。
2. `SC_02`、`SC_03`、`SC_04` → 先写 put/delete/version 与 durable append 顺序测试。
3. `SC_05`、`SC_06` → 先写 request_id 回放和冲突测试。
4. `SC_07`、`SC_08` → 先写 CLI JSON/退出码与读模型测试。
5. `SC_09`、`SC_10`、`SC_11`、`SC_12`、`SC_13`、`SC_18`、`SC_20` → 先写重启、恢复、损坏与临时文件测试。
6. `SC_14`、`SC_17` → 先写 compact 提交顺序、崩溃窗口和重启语义保持测试；`SC_19` → 先写失败 request_id 后的合法重用测试。
7. `SC_15` → 先写多进程并发 E2E 测试；`SC_16` → 先写首次布局与禁止真相源测试。
8. 实现满足测试的最小代码，重构后复跑单元、Smoke 和 E2E 测试。

## 对抗性审查记录

| Review | 预算 | 检查候选 | 被推翻假设 | 新增 Scenario |
|---|---|---|---|---|
| ARV-1 | full | AR-001/phased-commit→SC_17；AR-002/semantic-snapshot 不适用：当前契约未定义可验证的 snapshot 结构或语义一致性规则；AR-003/semantic-tail→SC_18；AR-004/failed-idempotency→SC_19；AR-005/error-contract→SC_08；独立假设 healthy-recover-idempotence→SC_20 | 已推翻“compact 的调用顺序断言足以覆盖 replace 间崩溃”和“版本失败后的 request_id 可由间接无追加断言覆盖”；snapshot 语义拒绝无任务证据 | SC_17、SC_18、SC_19、SC_20；复用 SC_08 |

## Scenarios

### Scenario SC_01: 规范 record 的 CRC 可重算且可验证

- **GIVEN** 一个包含全部 put 字段或 `delete` 且 `value:null` 的 record，以及同一对象的字段重排和一个 CRC 不匹配副本。
- **WHEN** `record.py` 编码并随后解码/验证这些 record。
- **THEN** 有效 record 的 `crc32` 恰为去除该字段后以 `sort_keys=True`、`separators=(",", ":")`、UTF-8 计算的 8 位小写十六进制；字段重排不改变验证结果；不匹配副本被标为 CRC 故障。
- 测试层：unit
- 依据：J-02
- 来源：initial-spec

### Scenario SC_02: 首次 mutation 在持锁且持久化后提交

- **GIVEN** 一个新 state-dir，`put --key alpha --value A --request-id r-1 --expected-version 0`，以及可观测的锁、append、flush 和 fsync 调用。
- **WHEN** 执行该 put。
- **THEN** 返回 `ok:true`、`seq:1`、`key:"alpha"`、`version:1`、`replayed:false`，且成功返回前在独占锁内只追加一条带换行的有效 record，并已依次 flush 和 fsync。
- 测试层：unit
- 依据：J-02、J-03、J-04
- 来源：initial-spec

### Scenario SC_03: 版本冲突不写日志

- **GIVEN** `alpha` 最近 mutation 的 seq 为 1，且当前有效日志大小已记录。
- **WHEN** 以 `expected_version:0` 对 `alpha` 执行 put 或 delete。
- **THEN** 返回 `VERSION_CONFLICT` 和退出码 4，日志大小、全局 seq、key 状态和 request 记录均不变。
- 测试层：unit
- 依据：J-01、J-04
- 来源：initial-spec

### Scenario SC_04: tombstone 仍承担下一次版本校验

- **GIVEN** `alpha` 已由 seq 1 的 put 创建。
- **WHEN** 以 `expected_version:1` delete `alpha`，再以 `expected_version:2` put `alpha`。
- **THEN** delete 返回 version 2，get/list 不把 tombstone 当作 live value；后续 put 成功并返回 version 3，而 `expected_version:0` 的同一后续 put 返回 `VERSION_CONFLICT`。
- 测试层：smoke
- 依据：J-04
- 来源：initial-spec

### Scenario SC_05: 完全相同 request_id 重试回放首次结果

- **GIVEN** 已成功提交 `put(alpha,A,r-1,0)` 并记录其 JSON 结果和日志 record 数。
- **WHEN** 用完全相同 op、key、value、expected_version 和 `request_id:r-1` 重试。
- **THEN** 返回首次提交的原始 `seq`、`key`、`version`，其中 `replayed:true`，且日志 record 数、seq 和 key 状态不变。
- 测试层：smoke
- 依据：J-05
- 来源：initial-spec

### Scenario SC_06: 复用 request_id 的不同内容被拒绝

- **GIVEN** `request_id:r-1` 已记录为 `put(alpha,A,0)`，且日志大小已记录。
- **WHEN** 以 `request_id:r-1` 发起 key、value、op 或 expected_version 任一不同的 mutation。
- **THEN** 返回 `IDEMPOTENCY_CONFLICT` 和退出码 5，日志大小、seq、key 状态和既有首次结果都不变。
- 测试层：unit
- 依据：J-01、J-05
- 来源：initial-spec

### Scenario SC_07: 读取模型只暴露 live 值且 list 有确定顺序

- **GIVEN** 已写入 `beta`、`alpha`，并删除 `beta`。
- **WHEN** 分别执行 get `alpha`、get `beta` 和 list。
- **THEN** get `alpha` 返回 key、字符串 value 和 version；get `beta` 返回 `NOT_FOUND` 和退出码 3；list 仅返回 `alpha`，每项含 key/value/version，且 live items 按 key 字典序排列。
- 测试层：smoke
- 依据：J-01、J-04
- 来源：initial-spec

### Scenario SC_08: CLI 成功与失败均保持单 JSON stdout 和稳定退出码

- **GIVEN** 一个可分别触发参数错误、`NOT_FOUND`、`VERSION_CONFLICT`、`IDEMPOTENCY_CONFLICT`、`RECOVERY_REQUIRED`、`CORRUPT_LOG` 与 `CORRUPT_SNAPSHOT` 的 state-dir/调用。
- **WHEN** 对每种调用启动 CLI。
- **THEN** stdout 各自恰为一个 JSON object；成功含 `ok:true`，失败的顶层键恰为 `ok` 和 `error`，`ok` 为 false，`error` 的键恰为 `code` 和字符串类型的 `message`，且 code/退出码依次为参数错误 2、`NOT_FOUND` 3、`VERSION_CONFLICT` 4、`IDEMPOTENCY_CONFLICT` 5、`RECOVERY_REQUIRED` 6、`CORRUPT_LOG` 7、`CORRUPT_SNAPSHOT` 8。
- 测试层：smoke
- 依据：J-01
- 来源：initial-spec

### Scenario SC_09: 重启从已提交 snapshot 和日志恢复完整状态

- **GIVEN** 一个 state-dir 已含有效 snapshot 和其后的有效 events，涵盖 live key、tombstone、last seq 及 request 指纹/首次结果。
- **WHEN** 在新 CLI 进程执行 get、list 或相同 request_id 的重试。
- **THEN** 可见 key/version、全局后续 seq 和幂等回放均与 snapshot 后依序应用日志的结果一致。
- 测试层：smoke
- 依据：J-05、J-07
- 来源：initial-spec

### Scenario SC_10: 仅最后物理 record 损坏时 recover 截断并持久化

- **GIVEN** `events.log` 的若干完整有效 record 后附有最后一条截断 UTF-8、缺换行、JSON/字段错误或 CRC 错误 record，且记录最后有效边界。
- **WHEN** 先执行普通命令，再执行 `recover`。
- **THEN** 普通命令返回 `RECOVERY_REQUIRED` 和退出码 6；recover 将文件截断到该有效边界并 fsync，返回 `ok:true` 与精确 `truncated_bytes`；之后普通命令恢复读取完整记录的状态。
- 测试层：smoke
- 依据：J-06
- 来源：initial-spec

### Scenario SC_11: 非最后 record 损坏使所有命令只读失败

- **GIVEN** `events.log` 中一个非最后 record 有 UTF-8、换行、JSON、字段或 CRC 损坏，且其后还有物理 record。
- **WHEN** 分别执行 get、put、compact 和 recover。
- **THEN** 每次均返回 `CORRUPT_LOG` 和退出码 7，`events.log`、snapshot 和 key 状态均未被改写。
- 测试层：smoke
- 依据：J-06
- 来源：initial-spec

### Scenario SC_12: 未提交 snapshot 临时文件不影响启动

- **GIVEN** state-dir 有有效已提交状态，并遗留任意内容的 `snapshot.json.tmp`。
- **WHEN** 重启 CLI 并读取或写入。
- **THEN** 只从已提交 snapshot 和日志重建状态，临时文件不被当作真相源，操作不因其内容失败。
- 测试层：unit
- 依据：J-07、J-09
- 来源：initial-spec

### Scenario SC_13: 已提交 snapshot 损坏禁止日志回退

- **GIVEN** `snapshot.json` 已存在但无法解析或不满足其已提交格式，同时 `events.log` 看似可用。
- **WHEN** 执行任一 CLI 命令（包括 recover）。
- **THEN** 返回 `CORRUPT_SNAPSHOT` 和退出码 8，且不根据日志猜测状态、不改写 snapshot 或日志。
- 测试层：unit
- 依据：J-06、J-07
- 来源：initial-spec

### Scenario SC_14: compact 原子保留语义并清空已提交日志

- **GIVEN** 有多次 put/delete、request 指纹和首次结果的有效 state-dir，当前 last seq 为 N。
- **WHEN** 执行 compact 后重启并重试一个既有 request，再以正确 expected_version 写入新值。
- **THEN** compact 在独占锁内先将完整 snapshot 写入临时文件并 flush/fsync、replace + fsync 目录，再以临时空 log replace + fsync 目录；返回 `snapshot_seq:N`；重启后 key/tombstone/version、幂等回放保持，下一次成功写入的 seq 大于 N。
- 测试层：smoke
- 依据：J-03、J-05、J-07
- 来源：initial-spec

### Scenario SC_15: 多进程 mutation 无丢失且同版本竞争只赢一次

- **GIVEN** 多个 CLI 进程共享同一 state-dir：一组对不同 key 均以 0 写入，另一组同时以相同 expected_version 更新同一已存在 key。
- **WHEN** 同时放开这些进程执行。
- **THEN** 不同 key 的每个成功值均可在最终 list 中找到且所有成功 seq 唯一；同 key 竞争恰一个成功，其余均为 `VERSION_CONFLICT`，没有交错或损坏 record。
- 测试层：e2e
- 依据：J-03、J-08
- 来源：initial-spec

### Scenario SC_16: 首次初始化遵守固定持久化布局

- **GIVEN** 一个不存在的调用者指定 state-dir。
- **WHEN** 首次执行任意支持初始化的 CLI 命令。
- **THEN** 创建 state-dir、空 `events.log` 和 `writer.lock`；后续只可出现约定的 `snapshot.json`、`snapshot.json.tmp`、`events.log.tmp`，且目录中没有数据库、pickle、缓存索引或其他持久化真相源。
- 测试层：unit
- 依据：J-09
- 来源：initial-spec

### Scenario SC_17: compact 在 snapshot 提交与日志替换之间崩溃后仍可继续

- **GIVEN** compact 已将包含 last seq N、key 状态和 request 元数据的 `snapshot.json.tmp` flush/fsync 后 replace 为 `snapshot.json` 并 fsync 状态目录，但进程在用空 `events.log.tmp` replace 旧 `events.log` 前终止，旧 log 仍含 seq 1 到 N 的有效 record。
- **WHEN** 新 CLI 进程重启并读取状态，再提交一个满足 expected_version 的新 mutation。
- **THEN** 重启后的 key/value/tombstone/version 与 compact 前一致，既有 request_id 仍回放首次结果，旧 log 前缀不被再次作为新 mutation 应用，且新 mutation 的 seq 恰为 N+1；重启不改写已提交 snapshot 以猜测另一状态。
- 测试层：smoke
- 依据：J-03、J-05、J-07
- 来源：adversarial-review (AR-001; pattern:phased-commit)

### Scenario SC_18: 语义非法但物理完整的末条 record 按可恢复尾部处理

- **GIVEN** 健康 `events.log` 的最后有效 seq 为 N，随后追加一条 UTF-8、JSON、字段形状和 CRC 均正确、却将 `seq` 设为 N 或 N+2 的完整末条 record，并记录该 record 的起始字节偏移。
- **WHEN** 先执行普通命令，再执行 recover。
- **THEN** 普通命令返回 `RECOVERY_REQUIRED` 和退出码 6；recover 在此之前不接受该 record，截断到记录的起始偏移并 fsync，之后状态等同于只含 seq 1 到 N 的日志。
- 测试层：smoke
- 依据：J-03、J-06、J-10
- 来源：adversarial-review (AR-003; pattern:semantic-tail)

### Scenario SC_19: 未提交的版本失败不占用 request_id

- **GIVEN** `alpha` 的当前 version 为 1，`request_id:r-failed` 尚未出现。
- **WHEN** 先以 `expected_version:0` 和 `request_id:r-failed` 发起 put 得到 `VERSION_CONFLICT`，再以相同 `request_id:r-failed`、正确 `expected_version:1` 发起 put。
- **THEN** 第二次是首次成功提交而非 `IDEMPOTENCY_CONFLICT` 或 replay，返回 `replayed:false` 和 seq 2，日志只新增这一条成功 record。
- 测试层：unit
- 依据：J-03、J-04、J-05
- 来源：adversarial-review (AR-004; pattern:failed-idempotency)

### Scenario SC_20: 健康日志的 recover 是无副作用的幂等成功

- **GIVEN** `events.log` 和已提交 snapshot（如有）均健康，并记录所有已提交文件的字节内容与可见状态。
- **WHEN** 连续两次执行 recover。
- **THEN** 两次均返回 `ok:true` 与 `truncated_bytes:0`，已提交日志和 snapshot 的字节内容、key 状态、seq 和 request 历史均保持不变。
- 测试层：smoke
- 依据：J-06
- 来源：adversarial-review (assumption:healthy-recover-idempotence)
