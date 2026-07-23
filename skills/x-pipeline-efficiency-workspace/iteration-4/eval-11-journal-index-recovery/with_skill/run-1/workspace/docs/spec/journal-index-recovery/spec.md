> spec_version: 3

# journal-index-recovery

## 任务目标

- 在 `fixture/backend/` 实现仅使用 Python 标准库的本地键值 journal；`python3 fixture/backend/cli.py --root <state-dir> <command> [arguments]` 对每次调用从 snapshot 与日志恢复可观察状态。
- 以规范化 JSONL + CRC-32 保存 put/delete，提供乐观版本、全目录 request_id 幂等、删除 tombstone、尾部恢复、原子 compact 与跨进程写串行化。
- 每个命令只在 stdout 输出一个 JSON object；成功包含 `ok:true`，失败包含稳定错误 code，并使用规定的退出码。

## 非目标

- 网络、数据库、守护进程、第三方包、后台服务与超出固定存储布局的持久化真相源。
- 自动修复日志中最后一条之前的损坏，或从损坏的已提交 snapshot 推断回退状态。
- 锁的公平性、吞吐量调优、批量 API 与进程内缓存。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `record.py` | 目标 | 规范化 record、CRC-32 编解码和字段校验 | 非规范化字节或宽松字段校验 → CRC 误判或非法 record 被重放 → 状态错误 | 编码 CRC 覆盖移除 `crc32` 后的排序、紧凑 UTF-8 JSON；每条已提交记录恰为一行并带换行；解码只接受合约字段和值域 | `J1` |
| `store.py` | 目标 | snapshot + log 重放、状态机、幂等、版本、recover、compact | 在 append 前返回或并发重放陈旧状态 → 丢失更新、重复 seq 或错误幂等结果 | 仅 append+flush+fsync 成功后返回写成功；seq 全局严格递增；每个 key 的 version 是最近 mutation 的 seq；请求指纹和首次结果跨重启与 compact 保留 | `J2`、`J3`、`J4` |
| `locking.py` | 目标 | state-dir 文件锁上下文 | 并发 mutation/recover/compact 交错 → 覆盖、截断有效日志或同 seq | 同一 state-dir 的 mutation、recover、compact 独占串行；读取在一致文件快照上重放 | `J5` |
| `cli.py` | 目标/上游 | 参数解析、命令分派、单一 JSON 输出、退出码 | argparse/异常文本写 stdout 或错误码漂移 → 调用方无法稳定处理 | stdout 恰一个 JSON object；所有合约错误映射至规定退出码；stderr 仅诊断 | `J6` |
| `snapshot.json` 与 `events.log` | 下游 | 固定持久化布局和原子 replace | 临时文件被当作已提交，或 snapshot 替换后日志保留导致重复回放 → 重启状态错误 | 忽略遗留 `snapshot.json.tmp`；已提交 snapshot 损坏报告 `CORRUPT_SNAPSHOT`；compact 保存完整状态后原子清空日志并 fsync 目录 | `J4`、`J7` |
| CLI 子进程调用方 | 下游 | 消费 JSON 结果、稳定错误与退出码 | 幂等 retry 被再次写入或错误归类错误 → 调用方产生重复副作用 | 同 request_id 同请求返回原始结果并 `replayed:true`；不同内容返回 `IDEMPOTENCY_CONFLICT` 且无写入 | `J3`、`J6` |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | record 的 CRC 输入是移除 `crc32` 的 object，经 `sort_keys=True`、`separators=(",", ":")`、UTF-8 JSON 得到的字节，crc32 为八位小写十六进制 | `task/01-record-and-state.md` | 合约直接规定；字段错误归为损坏 | 已确认 |
| J2 | 有效日志按顺序重放；seq 是正整数且相对 snapshot 全局严格递增；key 的 version 保留 tombstone 的 seq | `task/01-record-and-state.md` | 合约直接规定，故重放必须校验连续严格递增而非仅取最大值 | 已确认 |
| J3 | request_id 作用域为整个 state-dir；指纹由 op/key/value/expected_version 完全决定；相同请求返回首次提交的原始结果，冲突和版本失败均不得 append | `task/01-record-and-state.md` | 合约直接规定；首次结果需要在 snapshot 保存 | 已确认 |
| J4 | 每次命令从已提交 snapshot（若存在）和 events.log 重建；最后物理记录损坏为可恢复尾部，普通命令返回 `RECOVERY_REQUIRED`，recover 截断至最后有效边界 | `task/02-recovery-and-compaction.md` | 空日志健康；最后一条之外的损坏始终为 `CORRUPT_LOG` | 已确认 |
| J5 | 所有 mutation、recover、compact 在 `writer.lock` 独占锁中串行；标准库文件锁用于进程协调 | `task/03-cli-and-concurrency.md` | Unix 目标环境使用 `fcntl.flock`；锁文件位于 state-dir | 已确认 |
| J6 | 所有命令 stdout 只有一个 JSON object；成功与失败 schema、命令参数和错误退出码固定 | `task/00-overview.md`、`task/03-cli-and-concurrency.md` | CLI 负责将 `StoreError` 编码为 schema 和 exit code | 已确认 |
| J7 | compact 依次写并 fsync snapshot 临时文件、replace snapshot 并 fsync 目录、以临时日志 replace 空 events.log 并 fsync 目录；snapshot 含状态、seq、全部请求元数据 | `task/02-recovery-and-compaction.md`、`task/specs/storage-layout.md` | 保持 committed snapshot 与日志按顺序落盘；遗留 snapshot 临时文件属于未提交写入 | 已确认 |
| J8 | snapshot 的 JSON 结构未被题面固定，采用版本化 object，保存 `last_seq`、按 key 索引的 `value`/`version`/tombstone，以及按 request_id 索引的 fingerprint/result | 最小安全推断 | 这些字段是 J2、J3、J7 的最小表达；JSON 允许标准库跨进程读取 | 已确认 |
| J9 | 读取命令取得共享锁以避免读到 compact 的 replace 中间态；恢复检测结果在锁内得出 | 最小安全推断 | 题面要求每次重建且并发命令存在；共享锁提供一致文件集合且不改变写串行语义 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `J1`、`J4`、SC_01、SC_06、SC_09：CLI 输入到 record、snapshot/log，再到 JSON 输出 |
| 状态 | `J2`、`J3`、`J8`、SC_02 至 SC_07：live value、tombstone、version、seq 与 request registry |
| 时序 | `J4`、`J5`、`J7`、SC_08 至 SC_11：append fsync、尾部截断、replace/fsync、并发锁 |
| 资源 | `J5`、`J7`、SC_09 至 SC_11：锁 FD、日志/临时文件和状态目录 fsync 在操作结束前关闭 |
| 不变量 | `影响边界与不变量`、SC_01 至 SC_11 |
| 故障 | `J1`、`J4`、`J7`、SC_08 至 SC_10：CRC/字段/JSON/UTF-8、snapshot 与尾部恢复 |

## 验收清单

### 单元测试

- [ ] record 编码产生规范 JSONL 和 CRC；错误 CRC、字段、UTF-8 与 JSON 均被分类。
- [ ] put、get、delete、version、tombstone、request 幂等与 request 冲突满足 SC_01 至 SC_07，失败路径无追加。
- [ ] snapshot/log 重放、尾部恢复、早期损坏和 snapshot 损坏满足 SC_08 至 SC_10。
- [ ] compact 保留全部状态与请求 registry，且 append、recover、replace 的 fsync 顺序可由可观察文件结果验证。

### Smoke 测试

- [ ] 以独立 `python3 fixture/backend/cli.py` 子进程完成 put/get/list/delete/restart/compact/retry/recover，并断言每次 stdout 是一个 JSON object 和规定 exit code。
- [ ] 至少两个真实子进程并发写不同 key，断言全部成功、seq 唯一；并发同版本更新一个 key，断言一个成功且其余为 `VERSION_CONFLICT`。

### E2E 测试

- 决策：省略
- 依据：产品边界只有本地 CLI、标准库文件和本地子进程；Smoke 已覆盖真实进程、文件系统、重启与并发链路。

## 测试驱动开发

1. `SC_01`、`SC_02`、`SC_03` → 先写 record codec 和 put/get/list 的失败测试。
2. `SC_04`、`SC_05`、`SC_06`、`SC_07` → 先写 delete、version、幂等和冲突的失败测试。
3. `SC_08`、`SC_09`、`SC_10` → 先写日志重放、尾部和 snapshot 损坏的失败测试。
4. `SC_11` → 先写 compact 重启和多进程竞争的失败测试。
5. 实现满足测试的最小代码，重构后复跑单元与 Smoke 测试。

## Scenarios

### Scenario SC_01: 规范 record 追加与重启读取

- **GIVEN** 空 state-dir，`put alpha=A` 携带 `request_id=r-1` 和 `expected_version=0`
- **WHEN** put 成功返回后，以新 CLI 进程执行 `get alpha`
- **THEN** `events.log` 含一条带换行、有效 CRC 的规范 JSON record；put 返回 `seq=1`、`key=alpha`、`version=1`、`replayed=false`，get 返回 `value=A`、`version=1`
- 测试层：smoke
- 依据：`J1`、`J2`、`J6`

### Scenario SC_02: 按 key 排序列出 live 项

- **GIVEN** 已按有效版本创建 `zeta=Z` 与 `alpha=A`
- **WHEN** 执行 `list`
- **THEN** 成功 JSON 的 items 只含 live key，顺序为 `alpha`、`zeta`，每项含 key、value、version
- 测试层：unit
- 依据：`J2`、`J6`

### Scenario SC_03: 首次删除写 tombstone 且读取视为不存在

- **GIVEN** `alpha` 的当前 version 为 1 且 value 为 `A`
- **WHEN** 以 `expected_version=1` 执行 `delete alpha`
- **THEN** 返回成功的 `seq=2`、`version=2`、`replayed=false`；之后 get 返回 `NOT_FOUND`，list 不含 alpha，tombstone version 仍为 2
- 测试层：unit
- 依据：`J2`、`J6`

### Scenario SC_04: 删除从未出现 key 返回 NOT_FOUND

- **GIVEN** 空 state-dir
- **WHEN** 以任意 request_id、`expected_version=0` 执行 `delete missing`
- **THEN** 返回 `NOT_FOUND` 和 exit 3，events.log 保持为空
- 测试层：unit
- 依据：`J2`、`J6`

### Scenario SC_05: 版本冲突不产生 record

- **GIVEN** `alpha` 的当前 version 为 1
- **WHEN** 以 `expected_version=0` 执行 put 或 delete alpha
- **THEN** 返回 `VERSION_CONFLICT` 和 exit 4，last seq 与 events.log 字节保持不变
- 测试层：unit
- 依据：`J2`、`J6`

### Scenario SC_06: 相同 request 重试回放首次结果

- **GIVEN** put alpha=A、`request_id=r-1`、`expected_version=0` 已首次提交并得到 seq 1
- **WHEN** 重启后以完全相同 op、key、value、expected_version 和 request_id 再次 put
- **THEN** 返回原始的 seq/key/version 并含 `replayed=true`；events.log 与 last seq 保持在首次提交结果
- 测试层：smoke
- 依据：`J3`、`J6`

### Scenario SC_07: 同 request_id 的不同内容拒绝且无写入

- **GIVEN** request_id `r-1` 已提交 put alpha=A、`expected_version=0`
- **WHEN** 使用 `r-1` 发起任一 op/key/value/expected_version 不同的 mutation
- **THEN** 返回 `IDEMPOTENCY_CONFLICT` 和 exit 5，events.log、状态、last seq 均保持不变
- 测试层：unit
- 依据：`J3`、`J6`

### Scenario SC_08: 可恢复尾部阻断普通命令并由 recover 截断

- **GIVEN** events.log 先含有效 record，最后追加无换行、截断 UTF-8、无效 JSON、字段错误或 CRC 不匹配的唯一尾部行
- **WHEN** 先执行普通命令，再执行 `recover`，然后重启执行 get/list
- **THEN** 普通命令返回 `RECOVERY_REQUIRED` 和 exit 6；recover 截断至最后有效边界、fsync 并返回实际 `truncated_bytes`；重启后仅恢复有效前缀，健康日志再次 recover 返回成功且 `truncated_bytes=0`
- 测试层：smoke
- 依据：`J1`、`J4`、`J6`

### Scenario SC_09: 非尾部日志损坏和已提交 snapshot 损坏保持只读失败

- **GIVEN** logs 的最后物理记录之前存在无效 record，或 `snapshot.json` 存在且无法按 snapshot schema 解析
- **WHEN** 执行任意命令（包括 recover）
- **THEN** 前者返回 `CORRUPT_LOG` 和 exit 7，后者返回 `CORRUPT_SNAPSHOT` 和 exit 8；命令不改写状态文件
- 测试层：unit
- 依据：`J4`、`J6`、`J7`

### Scenario SC_10: 遗留 snapshot 临时文件不会改变已提交恢复结果

- **GIVEN** 健康 snapshot/log 状态和任意遗留 `snapshot.json.tmp`
- **WHEN** 重启执行 get 或 list
- **THEN** 输出仅由已提交 snapshot 与 events.log 决定，临时文件保持不作为恢复输入
- 测试层：unit
- 依据：`J4`、`J7`

### Scenario SC_11: compact 和多进程 mutation 保持完整、单调状态

- **GIVEN** 多个有效 mutation、删除 tombstone 与 request registry；两个进程以相同 expected_version 更新同一 key，同时其他进程更新不同 key
- **WHEN** 并发执行 mutation，之后执行 compact、重启并重试一个既有 request_id
- **THEN** 每个不同 key 写入均出现且 seq 唯一严格递增；同 key 竞争恰有一个提交、其余 `VERSION_CONFLICT`；compact 返回 pre-compact last seq，events.log 为空，重启后的值/version、tombstone、last seq 和幂等回放与 compact 前一致
- 测试层：smoke
- 依据：`J2`、`J3`、`J5`、`J7`
