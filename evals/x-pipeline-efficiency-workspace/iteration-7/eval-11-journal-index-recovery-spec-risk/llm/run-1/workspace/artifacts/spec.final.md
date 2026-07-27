> spec_version: 3
> adversarial_risk_version: 3
> complexity: 5
> importance: 1
> risk_average: 3.0
> review_budget: full
> adversarial_review: complete

# journal-index-recovery

## 任务目标

- 在 `fixture/backend/` 实现仅依赖 Python 标准库的本地键值 journal，使 CLI 从任意工作目录运行时都能在调用者指定的 state-dir 中完成初始化、持久化 mutation、重启恢复、幂等重试、乐观版本、删除、原子 compact、损坏分类与多进程并发。
- 每条已提交 mutation 使用规范 JSON 与 CRC-32 写入 `events.log`，成功响应发生在独占锁内 append、flush 和 fsync 完成之后。
- 启动时从已提交 snapshot 与 journal 重建唯一状态；物理尾部损坏可由 `recover` 截断，语义非法记录、非尾部损坏和已提交 snapshot 损坏进入稳定只读失败路径。
- CLI 的成功与失败输出保持单个 JSON object，公开字段、错误码和退出码可由自动化测试判定。

## 非目标

- 不引入数据库、守护进程、网络服务、第三方 Python 包、pickle、缓存索引或额外持久化真相源。
- 不扩展 `put`、`get`、`delete`、`list`、`compact`、`recover` 之外的业务命令。
- 不修改 `fixture/backend/` 之外的运行时代码；测试与 pipeline 文档可以位于工作区约定目录。
- 不定义跨 state-dir 事务、分布式锁、远程复制、加密或访问控制。

## 风险评分依据

- 复杂度：5。任务同时包含幂等请求账本、跨进程文件锁、全局序列、崩溃恢复、损坏分类和 snapshot/log 多阶段持久化提交；任一信号已触发最高复杂度锚点。
- 重要性：1。公开入口是本地单用户命令行工具，状态范围限定在调用者指定目录，不涉及资金、隐私、合规或全用户核心服务。
- 预算升级：平均分为 3.0；complexity 单维为 5，按规则升级为 `full`。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `fixture/backend/record.py` | 目标 | 实现 record 规范化、CRC 编解码和物理格式校验 | canonical 输入或字段集合漂移 → 同一逻辑 record 产生不同 CRC 或错误接受损坏 → 重放结果失真 | record 字段固定；CRC 只覆盖移除 `crc32` 后的 canonical JSON；已提交行以 UTF-8 `\n` 结束 | `J2` |
| `fixture/backend/store.py` | 目标 | 实现 snapshot/journal 重放、状态机、幂等、版本、recover 和 compact | 语义非法状态或部分提交被接受 → seq、key version、request 账本分叉 → 重启后状态不可证明 | 状态只能由合法 snapshot 与严格有序 mutation 推导；失败请求无持久化副作用；compact 前后语义等价 | `J3`–`J6` |
| `fixture/backend/locking.py` | 目标 | 实现 state-dir 跨进程锁 | mutation、recover、compact 交错 → 丢失提交、重复 seq 或替换竞态 → 持久化状态损坏 | 所有 mutation、recover、compact 在同一 `writer.lock` 独占区串行化 | `J8` |
| `fixture/backend/cli.py` | 目标 | 实现命令解析、JSON 输出与稳定退出码 | 错误路径输出形状或退出码漂移 → 调用方无法可靠判断结果 → 自动化集成失效 | stdout 每次恰为一个 JSON object；成功/失败字段及 code/exit 映射稳定 | `J7` |
| 调用者与 state-dir | 上游 | 提供命令参数、request_id、expected_version 和根目录 | 相对路径、首次初始化或重试输入处理不一致 → 状态写入错误位置或合法重试失败 | 所有状态只写入指定 state-dir；首次创建和从任意 cwd 启动行为一致 | `J1`、`J9` |
| `events.log`、`snapshot.json` 与临时文件 | 下游 | 承载唯一持久化事实 | snapshot 发布、journal 清空和目录 fsync 间崩溃 → 重放旧前缀或丢失状态 → seq 与幂等账本倒退 | 已发布 snapshot 覆盖的 journal 前缀最多应用一次；临时文件不成为已提交真相；下一次 seq 严格递增 | `J5`、`J6`、`J9` |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | 运行时代码限于 `fixture/backend/`，只使用 Python 标准库、本地文件和本地进程，CLI 可从任意 cwd 启动。 | 用户任务、仓库事实 | `PROMPT.md` 的实现范围与运行约束；fixture 仅提供四个 TODO 模块入口。 | 已确认 |
| J2 | journal record 字段、canonical JSON 参数、CRC-32 格式、UTF-8 和提交换行是精确公开格式。 | 用户任务 | `PROMPT.md` 给出完整示例、固定字段和 CRC 输入算法。 | 已确认 |
| J3 | `seq` 全局严格递增；key version 等于最近 put/delete 的 seq；tombstone 继续参与版本校验。 | 用户任务 | Journal record 与状态语义章节直接定义。 | 已确认 |
| J4 | request_id 在 state-dir 内唯一；相同指纹回放首次结果，不同指纹冲突；未提交失败不占用 request_id。 | 用户任务 | 状态与幂等语义章节直接定义。 | 已确认 |
| J5 | 只有最后一条物理记录的截断、缺换行、JSON、字段或 CRC 故障属于可恢复尾部；语义非法记录即使位于尾部也属于 `CORRUPT_LOG`。 | 用户任务 | 启动、损坏与恢复章节明确区分物理尾部故障和语义非法记录。 | 已确认 |
| J6 | 已提交 snapshot 必须保存 last seq、全部 key 状态和全部 request 元数据；compact 使用临时文件、replace 与目录 fsync，并跳过 snapshot 已覆盖的旧 journal 前缀。 | 用户任务 | Snapshot 与 compact 章节直接定义提交顺序和崩溃窗口。 | 已确认 |
| J7 | CLI 成功字段、失败 JSON 形状和退出码 2–8 是公开契约。 | 用户任务 | CLI 契约章节给出命令、字段和 code/exit 表。 | 已确认 |
| J8 | mutation、recover 和 compact 使用 state-dir 内 `writer.lock` 串行化；并发不同 key 无丢失，同 key 同版本恰一提交。 | 用户任务 | 并发要求章节直接定义。 | 已确认 |
| J9 | 持久化布局固定为 journal、snapshot、两个临时文件和 writer.lock；首次初始化只创建允许的文件。 | 用户任务 | 存储布局章节直接定义并禁止额外真相源。 | 已确认 |
| J10 | 当前 fixture 只有模块入口与 `NotImplementedError`，没有可复用实现事实。 | 仓库事实 | `cases/journal-index-recovery/fixture/backend/*.py` 的当前内容。 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `record.py` 编码 → `events.log`/`snapshot.json` → `store.py` 重放 → `cli.py` JSON；SC_01、SC_09、SC_14。 |
| 状态 | live/tombstone/version、全局 seq、request 指纹与首次结果；J3、J4、SC_02–SC_06。 |
| 时序 | 持锁 append/flush/fsync、recover 截断、compact 两阶段 replace/目录 fsync；J5、J6、SC_02、SC_10、SC_14、SC_15。 |
| 资源 | state-dir、writer.lock、journal、snapshot 和临时文件生命周期；J8、J9、SC_12、SC_17。 |
| 不变量 | `影响边界与不变量` 表；SC_01–SC_20 提供可观察验证。 |
| 故障 | 物理尾部、语义损坏、非尾部损坏、snapshot 损坏、版本/幂等冲突和 compact 崩溃窗口；SC_03、SC_06、SC_10–SC_15。 |

## 验收清单

### 单元测试

- [ ] 验证 record 固定字段、canonical CRC、delete `value:null`、UTF-8/JSON/字段/CRC 分类和换行边界（SC_01、SC_10）。
- [ ] 验证 put/delete、expected_version、tombstone version、冲突无写入、request_id 回放/冲突/失败后复用（SC_02–SC_06）。
- [ ] 验证 snapshot 结构和语义、snapshot 已覆盖 journal 前缀跳过、临时文件忽略与固定布局（SC_09、SC_12–SC_14、SC_17）。
- [ ] 使用文件系统与锁替身断言 mutation、recover、compact 的锁和持久化调用顺序及目录 fsync 崩溃窗口（SC_02、SC_10、SC_14、SC_20）。

### Smoke 测试

- [ ] 从任意 cwd 使用真实 CLI 走 put/get/delete/list、重启、幂等重试、compact 和健康 recover，并逐次解析单 JSON stdout（SC_02、SC_04、SC_05、SC_07、SC_09、SC_18）。
- [ ] 构造物理尾部、语义非法尾部、非尾部损坏和坏 snapshot，验证 code、exit、只读性、截断字节与文件内容（SC_10–SC_13）。
- [ ] 分别在 snapshot 发布后旧 journal 尚未清空，以及空 journal replace 后第二次目录 fsync 尚未完成时模拟 compact 崩溃，验证重启语义一致并继续以 N+1 写入（SC_15、SC_20）。

### E2E 测试

- 决策：需要
- 依据：公开入口是跨进程 CLI，正确性依赖真实标准库文件锁、文件 replace/fsync 与多进程调度，单元替身无法证明无丢失和竞争结果。
- [ ] 并发运行多个 CLI 进程，验证不同 key 全保留、成功 seq 唯一，同 key/expected_version 恰一成功且最终状态一致（SC_16）。

## 测试驱动开发

1. `SC_01` → 先写 record canonical CRC、字段集合和损坏分类单元测试。
2. `SC_02`–`SC_06` → 先写 mutation、版本、tombstone 和幂等账本测试。
3. `SC_07`、`SC_08` → 先写读取模型与 CLI JSON/退出码测试。
4. `SC_09`–`SC_13`、`SC_18`、`SC_19` → 先写重启、recover、日志/snapshot 物理与语义损坏测试。
5. `SC_14`、`SC_15`、`SC_20` → 先写 compact 提交顺序、两个目录项崩溃窗口和 snapshot 前缀重放测试。
6. `SC_16` → 先写多进程并发 E2E；`SC_17` → 先写初始化布局和任意 cwd Smoke。
7. 实现满足测试的最小代码，重构后复跑 unit、Smoke 和 E2E。

## 对抗性审查记录

| Review | 预算 | 风险来源 | 查询 | 召回 ID | 复用 Scenario | 新增 Scenario | CLI |
|---|---|---|---|---|---|---|---|
| ARV-1 | full | RAG:A-risk-003；assumption:compact-log-replace-dir-fsync-window | journal、snapshot、compact、events.log、崩溃恢复、旧日志前缀、序列单调；snapshot 已发布但 journal 清空尚未稳定提交时发生崩溃，重启可能重复应用已覆盖 mutation 或丢失状态 | A-risk-003 | SC_11 | SC_20 | exit=0; matches=1 |

## Scenarios

### Scenario SC_01: record 使用固定 canonical CRC 格式

- **GIVEN** 一个字段齐全的 put record、一个 delete record 和字段顺序不同但逻辑相同的副本。
- **WHEN** `record.py` 编码并解码这些 record。
- **THEN** 输出字段恰为 `crc32`、`expected_version`、`key`、`op`、`request_id`、`seq`、`value`；CRC 等于移除 `crc32` 后以指定 canonical JSON 和 UTF-8 计算的 8 位小写值；delete 的 value 为 null；已提交编码以换行结束。
- 测试层：unit
- 依据：`J2`
- 来源：initial-spec

### Scenario SC_02: mutation 在持锁持久化后才成功

- **GIVEN** 一个新 state-dir 和可观测的锁、append、flush、fsync 调用。
- **WHEN** 执行 `put(alpha,A,r-1,expected_version=0)`。
- **THEN** 系统在独占 writer.lock 内只追加一条 seq 1 record，完成 flush 与 fsync 后返回 `ok:true`、`seq:1`、`key:"alpha"`、`version:1`、`replayed:false`。
- 测试层：unit
- 依据：`J2`、`J3`、`J8`
- 来源：initial-spec

### Scenario SC_03: 版本冲突不写入也不占用 request_id

- **GIVEN** alpha 当前 version 为 1，日志大小和全局 seq 已记录，`r-failed` 尚未出现。
- **WHEN** 先以 `r-failed` 和 expected_version 0 更新 alpha，再以同一 `r-failed` 和正确 expected_version 1 更新。
- **THEN** 第一次返回 `VERSION_CONFLICT`/exit 4 且日志、seq、状态和 request 账本不变；第二次首次提交成功、`replayed:false`，且只追加一条 seq 2 record。
- 测试层：unit
- 依据：`J3`、`J4`、`J7`
- 来源：initial-spec

### Scenario SC_04: tombstone 继续承担版本校验

- **GIVEN** alpha 已由 seq 1 创建。
- **WHEN** 以 expected_version 1 删除 alpha，再以 expected_version 2 重新 put。
- **THEN** delete 写入 seq/version 2 tombstone，get/list 不暴露 live 值；后续 put 返回 seq/version 3，使用 expected_version 0 则返回 `VERSION_CONFLICT`。
- 测试层：smoke
- 依据：`J3`
- 来源：initial-spec

### Scenario SC_05: 相同 request_id 与相同指纹回放首次结果

- **GIVEN** `put(alpha,A,r-1,0)` 已提交，并记录首次 JSON 结果和日志 record 数。
- **WHEN** 使用完全相同的 op、key、value、expected_version 和 request_id 重试。
- **THEN** 返回首次 seq、key、version 与 `replayed:true`，日志、seq、key 状态和 request 账本均不新增。
- 测试层：smoke
- 依据：`J4`
- 来源：initial-spec

### Scenario SC_06: 相同 request_id 的不同指纹被拒绝

- **GIVEN** `r-1` 已记录为 `put(alpha,A,0)`，并记录日志大小。
- **WHEN** 用 `r-1` 发起 op、key、value 或 expected_version 任一不同的 mutation。
- **THEN** 返回 `IDEMPOTENCY_CONFLICT`/exit 5，日志、seq、业务状态和首次结果保持不变。
- 测试层：unit
- 依据：`J4`、`J7`
- 来源：initial-spec

### Scenario SC_07: get 与 list 只返回 live 值且顺序稳定

- **GIVEN** 依次写入 beta、alpha 并删除 beta。
- **WHEN** 执行 get alpha、get beta 和 list。
- **THEN** get alpha 返回 key/value/version；get beta 返回 `NOT_FOUND`/exit 3；list 只含 alpha，items 按 key 字典序排列且每项字段恰为 key、value、version。
- 测试层：smoke
- 依据：`J3`、`J7`
- 来源：initial-spec

### Scenario SC_08: CLI 成功与失败保持单 JSON 和稳定退出码

- **GIVEN** 可分别触发参数错误、NOT_FOUND、VERSION_CONFLICT、IDEMPOTENCY_CONFLICT、RECOVERY_REQUIRED、CORRUPT_LOG、CORRUPT_SNAPSHOT 的输入。
- **WHEN** 对每类输入启动 CLI。
- **THEN** stdout 各自只能解析为一个 JSON object；成功字段符合命令契约；失败顶层恰为 `ok:false` 与 error，error 恰含 code 和字符串 message，退出码依次为 2、3、4、5、6、7、8。
- 测试层：smoke
- 依据：`J7`
- 来源：initial-spec

### Scenario SC_09: 重启从 snapshot 与后续 journal 恢复唯一状态

- **GIVEN** 已提交 snapshot 保存 last seq、live/tombstone/version 和 request 指纹/首次结果，其后 journal 含更高 seq 的合法 mutation。
- **WHEN** 新 CLI 进程执行 get、list、相同 request_id 重试和新 mutation。
- **THEN** 可见状态等于 snapshot 后按 seq 应用未覆盖 journal 的结果，幂等重试返回首次结果，新 mutation 的 seq 严格大于所有已提交 seq。
- 测试层：smoke
- 依据：`J3`、`J4`、`J6`
- 来源：initial-spec

### Scenario SC_10: 最后一条物理损坏 record 可被 recover 截断

- **GIVEN** 若干健康 record 后附有最后一条截断 UTF-8、缺换行、JSON、字段或 CRC 故障 record，并记录最后健康边界。
- **WHEN** 先执行普通命令，再执行 recover。
- **THEN** 普通命令返回 `RECOVERY_REQUIRED`/exit 6；recover 在独占锁内截断到健康边界并 fsync，返回精确 truncated_bytes；之后状态只包含健康 record。
- 测试层：smoke
- 依据：`J5`、`J8`
- 来源：initial-spec

### Scenario SC_11: 物理完整但语义非法的尾部 record 是 CORRUPT_LOG

- **GIVEN** 最后一条 record 的 UTF-8、换行、JSON、固定字段和 CRC 都正确，但 seq 重复/跳跃、expected_version 或状态转换违反合法历史。
- **WHEN** 分别执行 get、put、compact 和 recover。
- **THEN** 每次均返回 `CORRUPT_LOG`/exit 7，events.log、snapshot、seq、业务状态和 request 账本不被改写。
- 测试层：smoke
- 依据：`J3`、`J5`、`J7`
- 来源：initial-spec

### Scenario SC_12: 非尾部物理损坏使所有命令只读失败

- **GIVEN** events.log 的一个非末条 record 存在 UTF-8、换行、JSON、字段或 CRC 故障，后面仍有物理 record。
- **WHEN** 分别执行读取、mutation、compact 和 recover。
- **THEN** 每次均返回 `CORRUPT_LOG`/exit 7，所有已提交文件字节保持不变。
- 测试层：smoke
- 依据：`J5`、`J7`
- 来源：initial-spec

### Scenario SC_13: 临时 snapshot 被忽略且坏的已提交 snapshot 被拒绝

- **GIVEN** 一次场景只有任意内容的 `snapshot.json.tmp` 与健康已提交状态，另一次场景的 `snapshot.json` 存在 JSON、字段或状态语义损坏。
- **WHEN** 分别重启 CLI 并执行任一命令。
- **THEN** 临时 snapshot 不参与重建；坏的已提交 snapshot 返回 `CORRUPT_SNAPSHOT`/exit 8，不回退 journal 猜测状态且不改写文件。
- 测试层：unit
- 依据：`J5`、`J6`
- 来源：initial-spec

### Scenario SC_14: compact 原子保留业务状态、幂等账本与 seq

- **GIVEN** state-dir 含 live、tombstone、多次 mutation 和已提交 request 首次结果，last seq 为 N。
- **WHEN** 执行 compact 后重启，重试既有 request 并提交一个满足 expected_version 的新 mutation。
- **THEN** compact 在独占锁内按 snapshot 临时写/flush/fsync/replace/目录 fsync、空 log 临时写/flush/fsync/replace/目录 fsync执行；返回 snapshot_seq N；重启状态和回放结果保持，新 mutation 为 N+1。
- 测试层：unit
- 依据：`J4`、`J6`、`J8`
- 来源：initial-spec

### Scenario SC_15: snapshot 发布后旧 journal 尚未清空的重启不重复应用前缀

- **GIVEN** compact 已发布并目录 fsync 包含 last seq N 的 snapshot，进程在替换旧 events.log 前终止，旧 log 仍含 snapshot 已覆盖的 seq 1..N。
- **WHEN** 新 CLI 进程重启读取并提交满足版本条件的新 mutation。
- **THEN** 重启状态与 compact 前一致，旧前缀最多应用一次，既有 request 仍回放首次结果，新 mutation 的 seq 恰为 N+1。
- 测试层：smoke
- 依据：`J3`、`J4`、`J6`
- 来源：initial-spec

### Scenario SC_16: 多进程 mutation 无丢失且同版本竞争只成功一次

- **GIVEN** 多个 CLI 进程共享 state-dir：一组以 expected_version 0 写不同 key，另一组以同一 expected_version 更新同一个既有 key。
- **WHEN** 同时释放全部进程执行。
- **THEN** 不同 key 的每个成功 mutation 均可见且成功 seq 全局唯一；同 key 竞争恰一成功，其余为 VERSION_CONFLICT；journal、snapshot、账本和查询结果一致。
- 测试层：e2e
- 依据：`J3`、`J8`
- 来源：initial-spec

### Scenario SC_17: 初始化遵守固定布局且 CLI 支持任意 cwd

- **GIVEN** 一个不存在的 state-dir 和位于 fixture 目录之外的当前工作目录。
- **WHEN** 通过绝对或正确解析的 CLI 路径首次执行支持初始化的命令。
- **THEN** 只创建 state-dir、空 events.log 和 writer.lock；后续只允许出现 snapshot 与两个约定临时文件，目录中没有数据库、pickle、缓存索引或其他真相源。
- 测试层：smoke
- 依据：`J1`、`J9`
- 来源：initial-spec

### Scenario SC_18: 健康日志 recover 幂等成功

- **GIVEN** events.log 和已提交 snapshot 均健康，并记录文件字节与可见状态。
- **WHEN** 连续两次执行 recover。
- **THEN** 两次均返回 `ok:true`、`truncated_bytes:0`，已提交文件、状态、seq 和 request 账本保持不变。
- 测试层：smoke
- 依据：`J5`
- 来源：initial-spec

### Scenario SC_19: snapshot 语义必须可由合法状态历史产生

- **GIVEN** 一个 JSON 和字段类型均合法、但 last seq、key version、tombstone 或 request 首次结果组合无法由合法 mutation 序列产生的已提交 snapshot。
- **WHEN** 启动任一 CLI 命令。
- **THEN** 返回 `CORRUPT_SNAPSHOT`/exit 8，不接受该状态、不回退 journal 推断并且不改写已提交文件。
- 测试层：unit
- 依据：`J3`–`J6`
- 来源：initial-spec

### Scenario SC_20: 空 journal replace 后目录 fsync 前崩溃保持 compact 语义

- **GIVEN** compact 已发布并目录 fsync 包含 last seq N 的 snapshot，随后将已 flush/fsync 的空 `events.log.tmp` replace 为 `events.log`，进程在第二次 fsync state-dir 前终止；重启后目录项可能呈现旧 journal 或新空 journal。
- **WHEN** 新 CLI 进程重启读取状态并提交一个满足 expected_version 的 mutation。
- **THEN** 两种可见目录结果都恢复出与 compact 前相同的 key、tombstone、version 和 request 账本；旧 journal 前缀最多应用一次，新 mutation 的 seq 恰为 N+1，且启动过程不改写已提交 snapshot 猜测状态。
- 测试层：smoke
- 依据：`J3`、`J4`、`J6`
- 来源：adversarial-review (assumption:compact-log-replace-dir-fsync-window)
