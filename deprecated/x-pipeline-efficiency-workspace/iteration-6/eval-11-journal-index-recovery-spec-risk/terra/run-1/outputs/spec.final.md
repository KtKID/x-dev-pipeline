---
spec_version: 3
adversarial_risk_version: 2
complexity: 4
importance: 3
risk_average: 3.5
review_budget: deep
adversarial_review: complete
---

# Journal Index Recovery

## 任务目标

- 在 `fixture/backend/` 交付仅用 Python 标准库实现的本地键值日志 CLI；调用者指定的 state-dir 是全部持久化状态。
- 所有命令从 `snapshot.json`（存在时）与 `events.log` 重建可观察状态，并通过 stdout 上唯一 JSON object 与稳定退出码报告结果。
- 为 mutation、恢复和压缩提供跨进程串行化、幂等请求、乐观版本、尾部修复和原子快照/日志切换；重启后保持相同语义。

## 非目标

- 数据库、守护进程、网络服务、第三方依赖和 state-dir 以外的持久化。
- 覆盖已提交 `snapshot.json` 后以日志猜测或恢复其内容。
- 为未提交的 `snapshot.json.tmp` 赋予已提交快照语义。

## 风险评分依据

- 复杂度：4；同一状态机同时约束 append 的 fsync 顺序、CRC 记录协议、snapshot+log 重放、尾部损坏分级、原子 replace、请求去重和跨进程并发。
- 重要性：3；该 CLI 的所有调用者依赖持久化值、版本冲突和恢复结果，错误会影响整个 state-dir 的数据正确性；任务未提供资金、隐私或合规链路。
- 预算升级：平均分 3.5 对应 `deep`；复杂度为 4 也要求至少 `deep`。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `fixture/backend/record.py` | 目标 | 规范化 record，按固定 JSON 字节计算/校验 CRC-32，并区分物理记录损坏 | 编码、字段或 CRC 规则偏差 → 健康记录被拒绝或损坏记录被接受 → 重放错误 | 已提交行始终为 UTF-8 JSON + `\\n`；CRC 基于移除 `crc32` 后的排序紧凑 JSON；`crc32` 为 8 位小写十六进制 | 用户任务，`J1` |
| `fixture/backend/store.py` | 目标 | 重放 snapshot/log、维护 key/version/seq/request-id 状态机，并实现 recover/compact | 错误的恢复边界、快照遗漏或日志替换时序 → 数据、幂等或 seq 回退 | `seq` 全局严格递增；每个 key 的最近 mutation seq 始终是其 version；tombstone version 继续参与校验；首次结果与请求指纹可跨重启查询 | 用户任务，`J2`，`J3` |
| `fixture/backend/locking.py` | 目标 | 基于 state-dir 内 `writer.lock` 提供标准库文件锁 | 多进程交错 append/compact/recover → 记录丢失、重复 seq 或截断健康日志 | mutation、recover、compact 全程独占串行；读操作从完整一致的持久化视图建立结果 | 用户任务，`J4` |
| `fixture/backend/cli.py` | 目标/上游 | 解析固定命令参数，调用 store，并向 stdout 输出一个 JSON object 与退出码 | 多余 stdout 或错误码漂移 → 自动调用方无法可靠消费结果 | 每次命令 stdout 恰有一个 JSON object；成功含 `ok: true`；任务列出的失败 code 映射固定退出码 | 用户任务，`J5` |
| `events.log`、`snapshot.json`、`snapshot.json.tmp` | 下游持久化边界 | 承载可提交记录、已提交快照与未提交临时尝试 | 将末尾损坏当健康、将中段损坏当可修复，或使用临时快照 → 静默数据篡改 | 末条物理记录以外的损坏使所有命令只读失败；`recover` 仅截断可恢复尾部并 fsync；提交快照损坏拒绝回退；遗留 tmp 被忽略 | 用户任务，`J3` |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | record 的 canonical CRC 输入由移除 `crc32` 后、`sort_keys=True`、`separators=(",", ":")` 的 UTF-8 JSON 字节确定 | 用户任务 | 输入、算法 `zlib.crc32` 与八位小写格式均已明确 | 已确认 |
| J2 | 可见业务状态包含 live value、tombstone/version、全局最后 seq 与每个 request_id 的原始请求指纹和首次结果 | 用户任务 | 版本、幂等与 compact 后重启语义要求保留这些状态 | 已确认 |
| J3 | 启动先判断已提交 snapshot 的完整性，再按物理行检查日志；仅有效前缀后的最后一条物理记录可作为 recover 的截断目标 | 用户任务 | 明确区分 `CORRUPT_SNAPSHOT`、`CORRUPT_LOG` 和可恢复尾部 | 已确认 |
| J4 | 写路径在独占文件锁内重放当前状态、分配 seq、append、flush、fsync 后才报告成功 | 用户任务 | 并发 mutation/recover/compact 串行化和提交顺序直接给出 | 已确认 |
| J5 | CLI 的成功结构、错误结构、命令集合与失败退出码是公开契约 | 用户任务 | 命令表及输出/exit 规则直接给出 | 已确认 |
| J6 | `get`/`list` 在发现可恢复尾部时也报告 `RECOVERY_REQUIRED`，不会读取到未完成记录后的推测状态 | 用户任务 | “普通命令返回 `RECOVERY_REQUIRED`”覆盖所有普通命令 | 已确认 |
| J7 | `compact` 的重放与两次 replace 都位于同一独占锁内，且每次 replace 后 fsync state-dir | 用户任务 | compact 的四个有序步骤直接给出 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `J1`、`J2`、SC_01、SC_08、SC_10 |
| 状态 | `影响边界与不变量` 的 `store.py` 行，SC_02 至 SC_05、SC_09 |
| 时序 | `J4`、`J7`、SC_02、SC_06、SC_10、SC_12 |
| 资源 | `record.py` 的行尾与文件、`locking.py` 的锁、SC_02、SC_07、SC_10 |
| 不变量 | `影响边界与不变量` |
| 故障 | `J3`、`J5`、SC_06 至 SC_09、SC_12 |

## 验收清单

### 单元测试

- [ ] 覆盖 canonical record CRC、字段分类、put/delete/version/idempotency 状态机、snapshot 序列化及日志重放。
- [ ] 覆盖有效前缀后的可恢复尾部、前置损坏、已提交 snapshot 损坏、遗留 tmp、失败 mutation 未占用 request_id 与每个指定失败 code/exit 映射。
- [ ] 覆盖 compact 后 tombstone、request fingerprint/首次结果和全局 seq 的持久化，以及 snapshot 已 replace 而旧日志仍在的崩溃窗口。

### Smoke 测试

- [ ] 在临时 state-dir 依次运行 CLI `put`、`get`、`list`、重启后的幂等 `put`、`compact` 与后续 mutation；每次 stdout 为一个可解析 JSON object，保留的 value/version/seq 与预期一致。
- [ ] 人工构造有效前缀加末尾无换行记录，普通 CLI 返回 exit 6，`recover` 后重启读取有效前缀且截断字节数可观察。

### E2E 测试

- 决策：需要
- 依据：真实进程之间共享 state-dir 的文件锁、flush/fsync 和原子 replace 行为属于跨进程持久化链路风险。
- [ ] 两个独立 Python CLI 进程并发 mutation：不同 key 的提交均保留且 seq 唯一；同 key/相同 expected_version 仅一方成功，另一方 exit 4。

## 测试驱动开发

1. `SC_01`、`SC_02`、`SC_03` → 先写会失败的 record canonicalization 与单进程 mutation 状态机单元测试。
2. `SC_04`、`SC_05`、`SC_06`、`SC_07`、`SC_08` → 先写会失败的版本、幂等、重放和损坏分类单元测试。
3. `SC_09`、`SC_10`、`SC_11`、`SC_12`、`SC_13`、`SC_14` → 先写会失败的 compact/restart、CLI 输出、多进程竞争和失败残留 Smoke/E2E 测试。
4. 实现满足测试的最小代码，重构后复跑全部已选测试层。

## 对抗性审查记录

| Review | 预算 | 检查候选 | 被推翻假设 | 新增 Scenario |
|---|---|---|---|---|
| ARV-1 | deep | failure-residue；phased-commit；tail-corruption；semantic-corruption | 失败 mutation 会占用 request_id；snapshot replace 与清空旧日志之间可安全忽略 | SC_13、SC_14 |

## Scenarios

### Scenario SC_01: 写入记录使用固定 CRC 编码

- **GIVEN** put `key=alpha`、`value=A`、`request_id=r-1`、`expected_version=0`，分配 `seq=1`
- **WHEN** store 生成并提交该 record
- **THEN** `events.log` 追加一行以 `\\n` 结尾的 UTF-8 JSON；其 `crc32` 等于移除该字段后按 `J1` 的字节计算的 8 位小写值
- 测试层：unit
- 依据：`J1`
- 来源：initial-spec

### Scenario SC_02: 首次 put 在持锁 fsync 后分配连续版本

- **GIVEN** 健康的空 state-dir 与 `put alpha=A r-1 expected_version=0`
- **WHEN** CLI 执行该 put
- **THEN** 独占锁内 append、flush、fsync 后返回 `ok=true`、`seq=1`、`key=alpha`、`version=1`、`replayed=false`；重启后 get 返回 `value=A`、`version=1`
- 测试层：smoke
- 依据：`J2`、`J4`
- 来源：initial-spec

### Scenario SC_03: 版本冲突不产生日志记录

- **GIVEN** key `alpha` 最近 mutation 的 version 为 4，且 `events.log` 的字节长度已记录
- **WHEN** 执行 `put alpha=B r-2 expected_version=3`
- **THEN** 返回 `VERSION_CONFLICT` 和 exit 4，日志字节长度及全局最后 seq 保持不变
- 测试层：unit
- 依据：`J2`、`J5`
- 来源：initial-spec

### Scenario SC_04: 删除写入 tombstone 并保留版本校验语义

- **GIVEN** `alpha` 已由 seq 5 的 put 创建；随后执行 `delete alpha r-3 expected_version=5`
- **WHEN** 删除提交并重启，然后执行 `put alpha=B r-4 expected_version=6`
- **THEN** delete 返回 `seq=6`、`version=6`、`replayed=false`；get/list 不把 alpha 作为 live value；后续 put 以 tombstone 的最近 version 6 校验并成功
- 测试层：unit
- 依据：`J2`
- 来源：initial-spec

### Scenario SC_05: request_id 的精确重试复用首次结果

- **GIVEN** `put alpha=A r-1 expected_version=0` 已首次成功并保存其请求指纹、原始成功 JSON 与 seq
- **WHEN** 重启后以完全相同的 op/key/value/expected_version 再次提交 `request_id=r-1`
- **THEN** 不追加日志，返回首次的 `seq`、`key`、`version` 并将 `replayed=true`；同一 ID 改为不同 value 时返回 `IDEMPOTENCY_CONFLICT` 和 exit 5，仍不追加日志
- 测试层：smoke
- 依据：`J2`、`J5`
- 来源：initial-spec

### Scenario SC_06: 从未出现的 key 删除报告未找到

- **GIVEN** 健康 state-dir 中不存在 `alpha` 的任何 mutation，且日志长度已记录
- **WHEN** 执行 `delete alpha r-1 expected_version=0`
- **THEN** 返回 `NOT_FOUND` 和 exit 3，日志长度、request_id 集合和全局最后 seq 保持不变
- 测试层：unit
- 依据：`J2`、`J5`
- 来源：initial-spec

### Scenario SC_07: 有效前缀后的终末坏记录要求恢复

- **GIVEN** `events.log` 含有效 record 前缀，末条物理记录为截断 UTF-8、无换行、JSON 解析失败、字段错误或 CRC 不匹配之一
- **WHEN** 执行任一普通命令
- **THEN** 返回 `RECOVERY_REQUIRED` 和 exit 6，文件字节与已确认状态均不改写；执行 recover 后仅截断该末条至最后有效边界并 fsync，返回 `truncated_bytes`；健康日志的 recover 返回 `ok=true` 且 `truncated_bytes=0`
- 测试层：smoke
- 依据：`J3`、`J6`
- 来源：initial-spec

### Scenario SC_08: 中段损坏锁定为只读失败

- **GIVEN** `events.log` 的最后一条之前有一条 CRC 不匹配或字段错误记录，后面仍有物理记录
- **WHEN** 执行 get、list、put、delete、compact 或 recover
- **THEN** 每个命令返回 `CORRUPT_LOG` 和 exit 7，`events.log`、`snapshot.json` 与业务状态均不改写
- 测试层：unit
- 依据：`J3`、`J5`
- 来源：initial-spec

### Scenario SC_09: 已提交快照损坏阻止日志回退

- **GIVEN** state-dir 存在无法解析或结构无效的已提交 `snapshot.json`，并且 `events.log` 自身健康
- **WHEN** 执行任意命令
- **THEN** 返回 `CORRUPT_SNAPSHOT` 和 exit 8，不以 events.log 构造猜测状态，且不修改任何持久化文件
- 测试层：unit
- 依据：`J3`、`J5`
- 来源：initial-spec

### Scenario SC_10: compact 原子保留完整重启状态

- **GIVEN** 多次 put/delete 已产生全局最后 seq、live value、tombstone/version 与 request_id 首次结果；state-dir 同时遗留 `snapshot.json.tmp`
- **WHEN** 执行 compact、重启，并以已提交 request_id 重试，再以当前最后 version 写入新值
- **THEN** compact 在同一独占锁内先 fsync 临时 snapshot、replace+fsync 目录，再以临时空 events.log replace+fsync 目录；启动忽略遗留 tmp；重启后的状态、幂等首次结果与 seq 单调性保持，compact 返回 `snapshot_seq` 等于 compact 前的最后 seq
- 测试层：smoke
- 依据：`J2`、`J4`、`J7`
- 来源：initial-spec

### Scenario SC_11: CLI 只输出一个 JSON object 并使用稳定 code

- **GIVEN** 调用者以有效参数执行 get，随后以缺失必填参数和以不存在 key 执行 get
- **WHEN** 分别运行 `python3 fixture/backend/cli.py --root <state-dir> <command>`
- **THEN** 每次 stdout 恰好包含一个可解析 JSON object；成功对象含 `ok=true`，参数错误 exit 2，缺失 key 的错误对象 code 为 `NOT_FOUND` 且 exit 3
- 测试层：smoke
- 依据：`J5`
- 来源：initial-spec

### Scenario SC_12: 多进程 mutation 串行化且不丢失提交

- **GIVEN** 两个独立 CLI 进程共享 state-dir：一组向不同 key 写入，另一组以相同 expected_version 写同一 key
- **WHEN** 两组进程并发执行 put
- **THEN** 不同 key 的所有成功提交均重放可见且 seq 全局唯一严格递增；同 key 的竞争仅一个返回成功，其他进程返回 `VERSION_CONFLICT` 和 exit 4，未成功进程不追加 record
- 测试层：e2e
- 依据：`J2`、`J4`、`J5`
- 来源：initial-spec

### Scenario SC_13: 失败 mutation 不占用 request_id

- **GIVEN** key `alpha` 的 version 为 4，且 `request_id=r-2` 从未由成功 mutation 使用
- **WHEN** `put alpha=B r-2 expected_version=3` 返回 `VERSION_CONFLICT` 后，以相同 `request_id=r-2` 执行 `put alpha=B r-2 expected_version=4`
- **THEN** 第二次请求作为首次提交成功，追加恰好一个 record 且返回 `replayed=false`；失败请求未留下 request 指纹或首次结果
- 测试层：unit
- 依据：`J2`、`J5`
- 来源：adversarial-review (pattern:failure-residue)

### Scenario SC_14: compact 的快照发布窗口保持可恢复状态

- **GIVEN** compact 已将包含最后 seq 7、key 状态和 request_id 结果的 `snapshot.json` 通过 replace 提交并 fsync state-dir，而旧的健康 `events.log` 尚未替换为空文件
- **WHEN** 进程在该窗口终止并由下一次 CLI 启动重建状态
- **THEN** 启动得到 seq 7 的已提交 snapshot 状态，旧日志不造成重复 mutation、version/请求结果偏移或 `CORRUPT_LOG`；随后以当前 version 的新 mutation 成功并分配 seq 8
- 测试层：smoke
- 依据：`J2`、`J3`、`J7`
- 来源：adversarial-review (pattern:phased-commit)
