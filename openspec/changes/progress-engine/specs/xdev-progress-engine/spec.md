## ADDED Requirements

### Requirement: flag 参数校验与校验原子性
工具层 SHALL 提供 `python3 tools/xdev.py flag <task-dir> --task <T#列表> --severity <P0|P1|P2> --loc <file:line> --msg <问题描述> [--new-round] [--json]`。没有 pending 事务时，flag SHALL 在写入业务文件与事务标记前验证全部参数：task 项 trim 后必须匹配 `T[1-9][0-9]*`，不得为空或重复，且目标在 checklist 中必须存在且唯一；severity 必须属于 P0/P1/P2；loc 必须是单行 `路径:正整数行号` 且不得包含 `|`、CR、LF；msg trim 后必须非空，CRLF/CR/LF SHALL 归一为空格，剩余字符必须可打印。任一参数或校验错误 SHALL 以 2 退出，checklist、ledger 和事务标记保持原样。语法完整的调用发现 pending 事务时 SHALL 优先恢复旧事务并忽略本次参数。

#### Scenario: 合法参数进入登记
- **WHEN** 运行 `flag <task-dir> --task T2,T3 --severity P0 --loc src/a.py:10 --msg "空输入未处理"`
- **THEN** 参数归一化为有序目标 T2、T3，并进入 issue 登记事务

#### Scenario: 非法 task 列表严格拒绝
- **WHEN** task 列表含空项、重复 T2、非法 t2/T0，或引用不存在/重复于 checklist 的 T9
- **THEN** 命令以 2 退出，checklist、ledger 和事务标记逐字节保持原样

#### Scenario: 非法位置严格拒绝
- **WHEN** loc 为空、缺少正整数行号、包含竖线或换行
- **THEN** 命令以 2 退出且零写入

#### Scenario: 描述换行归一化
- **WHEN** msg 含 CRLF、CR 或 LF，且归一化后仍为非空可打印文本
- **THEN** 各换行被替换为空格，竖线与其他可打印字符原样保留

### Requirement: 轮次文件与 issue 编号
ledger 文件 SHALL 使用 `qa-gate-report-<YYYYMMDD-HHmmss>.md`；同秒冲突 SHALL 依次使用 `qa-gate-report-<YYYYMMDD-HHmmss>-01.md`、`-02.md`。缺省调用 SHALL 选择 `(时间戳, 数值后缀)` 最大的 ledger；`--new-round` SHALL 以独占创建选择当前秒首个空闲名称；无 ledger 时 SHALL 自动创建首轮。新文件 SHALL 由 `render_issue_report` 生成固定标题、代码所有权说明和 `## Issues`。`next_issue_id` SHALL 只匹配代码生成的行首 `^- issue-([0-9]+) \|`，首条为 `issue-1`，后续取本轮最大值加一；系统 MUST NOT 从 ledger 反向解析 severity、T#、loc 或 msg。

#### Scenario: 首轮自动创建 issue-1
- **GIVEN** task 没有 ledger
- **WHEN** 运行一次合法 flag
- **THEN** 创建基础时间戳文件与固定骨架，并写入 `issue-1`

#### Scenario: 同轮编号递增
- **GIVEN** 当前轮已有 `issue-1`
- **WHEN** 再次运行合法 flag 且省略 `--new-round`
- **THEN** 同一文件新增 `issue-2`

#### Scenario: 同秒新轮使用数值后缀
- **GIVEN** 当前秒的基础文件与 `-01` 文件已存在
- **WHEN** 以 `--new-round` 运行 flag
- **THEN** 创建 `-02` 文件并从 `issue-1` 开始

#### Scenario: 描述中的 issue 文本不参与编号
- **GIVEN** 当前 ledger 只有 `issue-1`，其 msg 含 `issue-999`
- **WHEN** 追加下一条合法 issue
- **THEN** 新编号为 `issue-2`

### Requirement: issue 行由代码生成
`append_issue_line` SHALL 是 issue 行唯一格式化点，生成 `- issue-<n> | <严重度> | <T#列表> | <位置> | <描述>`。LLM、reviewer、主 agent 与 x-fix MUST NOT 手写 issue ledger 行。

#### Scenario: 可打印描述完整落盘
- **WHEN** msg 为 `int | None 类型分支未处理 None`
- **THEN** 代码生成单行 ledger 记录并完整保留竖线

### Requirement: 双文件事务前滚恢复
flag SHALL 使用 `<task-dir>/reports/qa-gate/.flag-transaction.json` 协调 ledger 与 checklist。校验通过后，系统 SHALL 在内存生成完整目标内容和结果，将两份内容写入目标同目录唯一临时文件并 flush/fsync。系统 SHALL 把完整 marker JSON 写入 qa-gate 目录的唯一临时文件并 fsync，再以 `os.link` 独占发布 marker；发布成功、删除 marker 临时文件并 fsync 目录后，才可通过 `os.replace` 提交目标。marker SHALL 包含 schema version、目标与临时相对路径、目标 SHA-256、原 JSON 结果。每次替换后 SHALL fsync 目标目录；确认两个目标哈希后 SHALL 删除 marker 并再次 fsync marker 目录。系统只在 marker 清理完成后报告新 issue 登记成功。

任何语法完整的 flag 调用发现 pending marker 时 SHALL 先恢复旧事务：已匹配目标哈希的文件跳过；未匹配且临时文件存在时继续 replace；未匹配且临时文件缺失时以 2 退出并保留 marker。恢复成功 SHALL 返回 marker 保存的旧 issue 结果、设置 `recovered: true`，并 MUST NOT 处理本次新 issue 参数。并发调用发布 marker 遇到已存在时 SHALL 清理自己尚未发布的临时文件，转入既有事务恢复，且 MUST NOT 登记自己的 issue。

#### Scenario: 校验错误不创建事务
- **WHEN** 参数或 checklist 校验失败
- **THEN** marker、临时文件、ledger 和 checklist 均保持原样

#### Scenario: 首个目标提交后中断
- **GIVEN** marker 和两份临时文件已落盘，checklist 已 replace，ledger 尚未 replace
- **WHEN** 下一次调用 flag
- **THEN** 系统完成 ledger replace、验证两个哈希、清理 marker，返回旧 issue 且 `recovered: true`，本次新参数不被登记

#### Scenario: marker 独占发布竞争
- **GIVEN** 两个调用均已写好各自临时内容
- **WHEN** 一个调用先发布 marker，另一个调用遇到 marker 已存在
- **THEN** 后者清理自己的临时文件、恢复前者事务并返回前者 issue，且不登记自己的 issue

#### Scenario: 恢复材料缺失
- **GIVEN** marker 指向的目标哈希未匹配，且对应临时文件缺失
- **WHEN** 调用 flag
- **THEN** 命令以 2 退出、保留 marker，并报告缺失路径与期望哈希

### Requirement: Checklist 只降级写回
severity 为 P0/P1 时，flag SHALL 将每个目标 T# 的状态单元格写为 `[!] 🔴`，保持该行其余内容原样；已 blocked 的目标 SHALL 保持状态。P2 SHALL 只写 ledger。flag MUST NOT 写入 `[x]`。

#### Scenario: P0 降级多个任务
- **GIVEN** T2 为 `[x] ✅`，T3 为 `[ ] ⏳`
- **WHEN** flag 以 P0 引用 T2、T3
- **THEN** 两个状态变为 `[!] 🔴`，其余单元格原样

#### Scenario: P2 只登记
- **WHEN** flag 以 P2 引用 T3
- **THEN** T3 状态原样，ledger 新增 issue

#### Scenario: blocked 任务重复登记
- **GIVEN** T2 已为 `[!] 🔴`
- **WHEN** flag 再次以 P0 引用 T2
- **THEN** T2 状态原样，ledger 新增下一 issue

### Requirement: CLI 输出与退出码
成功登记 SHALL 返回 0，并在 `--json` 下输出 `issue`、`downgraded`、`report`、`recovered` 四个键；正常登记时 `recovered` 为 false。成功恢复 SHALL 返回 0、复用 marker 保存的 issue/downgraded/report，并将 `recovered` 设为 true。参数、校验、事务或 IO 错误 SHALL 返回 2；错误输出 SHALL 包含可操作诊断。

#### Scenario: JSON 返回新 issue
- **WHEN** P0 flag 将 T2、T3 从非 blocked 状态降级
- **THEN** JSON 形如 `{"issue":"issue-1","downgraded":["T2","T3"],"report":"qa-gate-report-<时间戳>.md","recovered":false}`

#### Scenario: JSON 返回恢复结果
- **WHEN** flag 完成 pending `issue-2` 事务
- **THEN** JSON 返回 `issue-2` 的原结果并设置 `recovered:true`

### Requirement: 现有状态解析回归安全
加入 flag 后 SHALL 保持 status 与 graph 的 token+emoji 双轨判定和纯 emoji 历史兼容行为。flag SHALL 只改写引用 T# 的状态单元格，其他历史 checklist 内容保持原样。

#### Scenario: 旧 emoji fixture 保持判定
- **WHEN** status 或 graph 读取纯 emoji 历史 fixture
- **THEN** done、blocked、todo 结果与变更前一致
