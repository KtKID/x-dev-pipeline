> spec_version: 3

# Journal Index Recovery

## 任务目标

- 提供仅依赖 Python 标准库的本地键值 journal CLI，在调用者指定目录中持久化字符串值、tombstone、全局序号和幂等请求结果。
- 每次命令从已提交 snapshot 与日志重建状态，正确处理重启、乐观版本、删除、尾部损坏恢复、原子压缩和多进程写入。
- 所有命令仅向 stdout 输出一个 JSON object，并按公开错误码返回稳定进程退出码。

## 非目标

- 不提供网络服务、数据库、守护进程、第三方依赖或额外持久化索引。
- 不自动修复中段日志损坏或已提交 snapshot 损坏。
- 不在 `fixture/backend/` 之外实现运行时代码，也不改变题面与 fixture 说明。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `fixture/backend/record.py` | 目标 | 定义规范 JSON、CRC-32 编解码、字段校验与损坏报告 | 非规范编码或宽松字段校验 → 损坏记录被接受或健康记录被拒绝 → 恢复边界错误 | 每条编码记录恰好一行 UTF-8 JSON；CRC 只覆盖移除 `crc32` 后的规范 object；解码只接受完整合法字段和匹配 CRC | `J1`、`J2` |
| `fixture/backend/store.py` | 目标 | 重放 snapshot+log，实现状态机、幂等、版本、恢复与压缩 | 崩溃窗口或重放次序错误 → 状态、幂等历史或 seq 丢失 → 重启后重复提交或覆盖 | seq 全局严格递增；key version 等于最近 mutation seq；写成功只在 append+flush+fsync 后返回；snapshot 保留完整状态与全部幂等历史 | 用户任务、`J3`、`J4` |
| `fixture/backend/locking.py` | 目标 | 用 `writer.lock` 和标准库文件锁协调跨进程访问 | 检查后写入缺少单一独占区 → seq 重复或更新丢失 → journal 不可重放 | mutation、recover、compact 的加载、校验和提交均处于同一独占锁；只读命令持共享锁观察一致状态 | 用户任务、`J5` |
| `fixture/backend/cli.py` | 上游 | 解析六个命令并输出单一 JSON object 和稳定退出码 | argparse 或异常路径向 stdout 混入文本/多个对象 → 调用方无法机器解析 | 每次调用 stdout 恰有一个 JSON object；业务错误按指定 code/exit 映射；参数或命令错误 exit 2 | 用户任务、`J6` |
| `<state-dir>` 文件布局 | 下游 | 保存 `events.log`、`snapshot.json`、临时文件和锁文件 | 临时文件被当成已提交真相或 replace 后目录项未落盘 → 崩溃恢复到混合代际 | 启动忽略 `snapshot.json.tmp`；只读取已提交 snapshot；compact 对两个 replace 分别执行目录 fsync；不创建布局外持久化真相源 | 用户任务、`J3` |
| CLI 子进程调用方 | 相关 | 消费 JSON、退出码和按 key 排序的 live items | 错误映射或结果形状漂移 → 自动化误判提交状态 | 首次 mutation 与重试均返回 seq/key/version/replayed；get/list 只暴露 live value；失败固定为 error.code/message | 用户任务、`J6` |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | record 解码要求 object 字段集合与 op 对应类型精确匹配，拒绝额外字段、布尔型 seq/version 和非正 seq | 用户任务 + LLM 推断 | 题面定义了完整字段形状和“字段错误”；精确校验是避免日志语义歧义的最小安全解释，Python `bool` 需与 `int` 区分 | 已确认 |
| J2 | `decode_record` 的输入代表一条不含物理换行的 record；物理行尾完整性由 store 扫描器判定 | 仓库事实 + LLM 推断 | record 模块负责编解码，store 才能判断某字节段是否为最后物理记录以及可否截断 | 已确认 |
| J3 | snapshot 使用规范 JSON object，包含 schema version、last_seq、keys 和 requests；临时文件忽略，已提交文件任意 UTF-8/JSON/结构错误均为 `CORRUPT_SNAPSHOT` | 用户任务 + LLM 推断 | snapshot 具体 JSON 形状留白；显式 schema 与严格校验可完整保留题面要求并阻止猜测回退 | 已确认 |
| J4 | 健康空日志、缺失日志和仅 snapshot 状态均可启动；首次命令创建目录、空日志和锁文件 | 用户任务 | 固定布局允许首次命令创建这些文件；compact 会产生空日志 | 已确认 |
| J5 | POSIX 环境使用 `fcntl.flock`：读命令共享锁，mutation/recover/compact 独占锁；锁覆盖目录初始化和完整操作 | 用户任务 + 基础运行环境 | 题面要求标准库文件锁和多进程协调，fixture 由本地 Python 子进程运行 | 已确认 |
| J6 | 参数解析错误由自定义 argparse 错误路径生成 `ARGUMENT_ERROR` JSON，exit 2；未知内部异常也保持单 JSON 并以 exit 2 返回 | LLM 推断 | 题面只固定参数/命令错误 exit 2，且要求所有命令 stdout 为一个 JSON object；统一机器可读形状是最小安全默认 | 已确认 |
| J7 | key、value、request_id 必须为字符串，key 与 request_id 不能为空，expected_version 必须为非负整数 | 用户任务 + LLM 推断 | CLI 参数天然为字符串；空 identity 与负版本没有合法状态含义，早期拒绝可避免不可寻址幂等记录 | 已确认 |
| J8 | `recover` 对健康日志成功返回 `truncated_bytes: 0`；可恢复尾部返回实际移除字节数 | 用户任务 + LLM 推断 | 题面规定健康 recover 幂等成功并要求返回 truncated_bytes | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `record.py` 编解码 → `events.log` → `store.py` 重放 → CLI JSON，见 `SC_01`、`SC_08`、`SC_13` |
| 状态 | live/tombstone/version、last_seq、request fingerprint/result，见 `SC_02` 至 `SC_07` |
| 时序 | 独占锁内加载→校验→append/replace→flush/fsync→返回，见 `SC_03`、`SC_11`、`SC_14` |
| 资源 | 文件描述符、跨进程锁、临时文件与目录 fsync，见边界表及 `SC_10`、`SC_11`、`SC_14` |
| 不变量 | `影响边界与不变量`、`SC_03`、`SC_06`、`SC_11`、`SC_14` |
| 故障 | 尾部损坏、中段损坏、snapshot 损坏、参数/业务错误，见 `SC_08` 至 `SC_10`、`SC_13` |

## 验收清单

### 单元测试

- [ ] record 规范编码产生匹配 CRC 的单行 UTF-8 JSON，字段、类型、JSON、UTF-8 和 CRC 错误均被拒绝。
- [ ] store 覆盖 put/get/list/delete、tombstone version、版本冲突和全局 seq 单调。
- [ ] store 覆盖相同 request 重放、不同 request fingerprint 冲突，以及 compact 后重启仍保留幂等结果。
- [ ] 日志扫描覆盖健康、最后一条缺换行/UTF-8/JSON/字段/CRC 损坏和中段损坏分类。
- [ ] snapshot 严格校验与遗留 `.tmp` 忽略，compact 原子替换和 recover 截断边界可观察。

### Smoke 测试

- [ ] 使用真实 CLI 子进程完成 put→get→list→delete→get 失败，逐项断言单 JSON、结果字段和退出码。
- [ ] 使用真实 CLI 子进程注入尾部损坏，断言普通命令 exit 6、recover 后状态可读且 truncated_bytes 正确。
- [ ] 使用真实 CLI 子进程 compact 并重启，断言状态、幂等结果和后续 seq 单调。
- [ ] 启动多个真实 CLI 子进程并发写入，断言不同 key 无丢失且同 key 只有一个相同版本更新成功。

### E2E 测试

- 决策：需要
- 依据：CLI 进程边界、操作系统文件锁、fsync/replace 和重启恢复属于真实本地基础设施链路，单进程单元测试无法覆盖。
- [ ] 在临时 state-dir 中复跑完整 CLI、损坏注入、compact/restart 和多进程竞争链路，全部输出可解析且最终 journal 可重放。

## 测试驱动开发

1. `SC_01`、`SC_08`、`SC_09`、`SC_10` → 先写 record/log/snapshot 损坏分类单元测试。
2. `SC_02` 至 `SC_07` → 先写状态机、版本与幂等单元测试。
3. `SC_11` → 先写 compact 后重启与幂等保留测试。
4. `SC_12`、`SC_13` → 先写 CLI subprocess Smoke 测试。
5. `SC_14` → 先写多进程竞争 E2E 测试。
6. 实现满足测试的最小代码，重构后复跑全部单元、Smoke 与 E2E 测试。

## Scenarios

### Scenario SC_01: 规范 record 可往返并校验 CRC

- **GIVEN** 字段类型合法的 put 或 delete record 且不含 `crc32`
- **WHEN** 编码后再解码该物理记录内容
- **THEN** 得到与输入语义相同且带 8 位小写 CRC 的 object，编码字节以单个 `\n` 结束，任何字段或 CRC 篡改均抛出 record 错误
- 测试层：unit
- 依据：`J1`、`J2`

### Scenario SC_02: 新 key 写入后可读取和排序列出

- **GIVEN** 健康空 state-dir，两个不同 key 的 expected_version 均为 0
- **WHEN** 依次提交两个 put 并调用 get/list
- **THEN** 两次提交获得唯一递增 seq/version，get 返回值与版本，list 只含 live items 且按 key 字典序排列
- 测试层：unit
- 依据：用户任务

### Scenario SC_03: 版本冲突保持日志和状态不变

- **GIVEN** key 已有最近 mutation version，新的 put/delete 携带不同 expected_version
- **WHEN** 提交 mutation
- **THEN** 返回 `VERSION_CONFLICT`，events.log 不增加字节，last_seq、value、version 和幂等表均不变
- 测试层：unit
- 依据：用户任务

### Scenario SC_04: 删除写入 tombstone 并延续版本

- **GIVEN** live key 的 expected_version 匹配当前 version，或 key 从未出现
- **WHEN** 调用 delete
- **THEN** live key 追加 tombstone 并从 get/list 消失且其新 seq 继续作为后续 expected_version；从未出现的 key 返回 `NOT_FOUND` 且不写日志
- 测试层：unit
- 依据：用户任务

### Scenario SC_05: 相同幂等请求返回首次原始结果

- **GIVEN** request_id 已成功提交且 op/key/value/expected_version 与首次请求完全相同
- **WHEN** 在同进程、重启后或 compact 后重试该请求
- **THEN** 返回首次提交的 seq/key/version 和 `replayed: true`，不追加记录且不改变当前 key 状态
- 测试层：unit
- 依据：用户任务、`J3`

### Scenario SC_06: request_id 内容冲突拒绝提交

- **GIVEN** request_id 已成功提交，重试至少一个 op/key/value/expected_version 字段不同
- **WHEN** 提交该请求
- **THEN** 返回 `IDEMPOTENCY_CONFLICT`，不追加记录且所有状态不变
- 测试层：unit
- 依据：用户任务

### Scenario SC_07: tombstone 参与后续乐观版本

- **GIVEN** key 已删除且 tombstone version 为 N
- **WHEN** 分别以 expected_version 0 与 N 重新 put
- **THEN** 版本 0 请求返回 `VERSION_CONFLICT`，版本 N 请求成功并以新的全局 seq 恢复 live value
- 测试层：unit
- 依据：用户任务

### Scenario SC_08: 最后一条物理记录损坏要求显式恢复

- **GIVEN** events.log 的最后一条物理记录缺换行，或含截断 UTF-8、非法 JSON、字段错误、CRC 错误
- **WHEN** 普通命令加载状态并随后调用 recover
- **THEN** 普通命令返回 `RECOVERY_REQUIRED` 且不改文件；recover 只截断最后有效边界、fsync 并返回实际 truncated_bytes，之后有效前缀可正常重放
- 测试层：smoke
- 依据：用户任务、`J2`、`J8`

### Scenario SC_09: 中段日志损坏使所有命令只读失败

- **GIVEN** 最后一条物理记录之前存在 UTF-8、JSON、字段或 CRC 损坏
- **WHEN** 调用任意普通命令或 recover
- **THEN** 返回 `CORRUPT_LOG`，events.log、snapshot 和状态目录内容均不被修复或提交
- 测试层：unit
- 依据：用户任务

### Scenario SC_10: 已提交 snapshot 损坏禁止日志回退

- **GIVEN** `snapshot.json` 存在但 UTF-8、JSON 或结构无效，同时可能存在可重放 events.log 和遗留 `snapshot.json.tmp`
- **WHEN** 调用任意命令
- **THEN** 返回 `CORRUPT_SNAPSHOT`，忽略 `.tmp` 且不从日志猜测完整状态或改写文件
- 测试层：unit
- 依据：用户任务、`J3`

### Scenario SC_11: compact 保留完整状态并清空日志

- **GIVEN** 健康 journal 含 live key、tombstone、全局 last_seq 和已提交 request_id
- **WHEN** 在独占锁中 compact 后创建新进程重载
- **THEN** snapshot 原子提交、events.log 原子替换为空、返回 snapshot_seq；重启后值/version/tombstone/幂等结果不变且下一 mutation seq 大于 snapshot_seq
- 测试层：e2e
- 依据：用户任务、`J3`、`J5`

### Scenario SC_12: 健康日志 recover 幂等成功

- **GIVEN** events.log 健康或为空
- **WHEN** 一次或重复调用 recover
- **THEN** 每次返回 `ok: true` 与 `truncated_bytes: 0`，日志内容和业务状态不变
- 测试层：smoke
- 依据：`J8`

### Scenario SC_13: CLI 输出和退出码稳定

- **GIVEN** 六个合法命令、参数错误以及每类公开 StoreError 条件
- **WHEN** 通过 `python3 fixture/backend/cli.py --root ...` 启动真实子进程
- **THEN** stdout 每次恰含一个 JSON object，成功含 `ok:true`，失败含 error.code/message，并分别返回 2、3、4、5、6、7、8 的约定退出码
- 测试层：smoke
- 依据：用户任务、`J6`、`J7`

### Scenario SC_14: 多进程 mutation 被同一锁串行化

- **GIVEN** 多个 CLI 进程并发写不同 key，另有多个进程以同一 expected_version 更新同一 key
- **WHEN** 同时释放进程开始 mutation
- **THEN** 不同 key 全部提交且 seq 唯一；同 key 恰有一个成功、其余均为 `VERSION_CONFLICT`；最终日志完整可重放
- 测试层：e2e
- 依据：用户任务、`J5`
