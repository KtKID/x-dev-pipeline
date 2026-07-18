## Context

### 当前仓库事实

- `tools/xdev.py` 已有 argparse 子命令、checklist 解析、status/graph/verify 和标准库测试框架。
- x-qa-gate 当前让 reviewer 输出 F1..Fn mini-report，再由主 agent 聚合 QA Gate 报告。
- v7 以 `dev-pipeline/tasks/progress-engine/plan.md` 为需求源，把问题登记改为 `flag` 函数调用，统一使用 `issue-<n>`。
- active OpenSpec change 在用户验收前保持 active。

## Goals / Non-Goals

**Goals:**

- 让参数错误在业务文件写入前暴露，校验错误严格零写入。
- 让代码生成 issue ID、台账文本和 checklist 降级。
- 让台账与 checklist 的跨文件写入具备可检测、可前滚恢复的事务语义。
- 固定同秒轮次、受限 issue ID 扫描、文本净化、角色分权与活跃文档迁移。

**Non-Goals:**

- 指纹、证据过期检测、历史报告防重放和重复 issue 静默去重。
- checklist 进度节、三符号迁移、verify 回执 JSON、行级 verify。
- OS/advisory 文件锁；事务标记使用独占创建协调单写者。
- clean 轮强制创建空 ledger。

## Decisions

### Decision 1: issue 内容只经参数进入

reviewer 返回 T#、severity、loc、msg，主 agent 逐条调用 flag。`append_issue_line` 是 issue 行唯一格式化点。系统只扫描代码生成的 `issue-<n>` 行首分配下一编号，不反向解析 severity、T#、loc 或 msg。

该边界消除了 v6 的五字段解析接口，同时保留轮内稳定 issue ID，供 x-fix 处置和增量复审引用。

### Decision 2: 参数采用严格文法

- task 项 trim 后匹配 `T[1-9][0-9]*`，拒绝空项、重复项、缺失项和 checklist 内重复目标。
- loc 匹配单行 `路径:正整数`，拒绝竖线与换行；路径存在性不作为校验条件。
- msg trim 后非空，换行统一为空格，其余字符必须可打印。
- severity 由 argparse choices 与函数层校验共同限制为 P0/P1/P2。

严格文法让调用错误在落盘前以 exit 2 返回，主 agent 可直接修正参数重试。

### Decision 3: issue ID 采用受限行首扫描

`next_issue_id` 只匹配 `^- issue-([0-9]+) \|`。描述中的 `issue-999`、历史摘要或其他 Markdown 均不参与编号。首条为 `issue-1`，后续取本轮最大值加一。

独立 counter sidecar 会增加第三份一致性状态；代码所有的行首是更小的事实源。

### Decision 4: 轮次文件支持同秒数值后缀

基础文件名使用秒级时间戳；冲突时追加 `-01`、`-02`。文件选择解析时间戳和可选整数后缀，以 `(timestamp, suffix_int)` 排序。新轮以存在性探测选定首个空闲后缀（并发同名由 Decision 5 的 marker 独占发布与提交前哈希校验仲裁），issue 编号从 1 开始。

该规则保留现有文件名前缀，并覆盖自动化测试中同秒创建多轮的路径。

### Decision 5: 事务标记提供跨文件前滚恢复

单次 `os.replace` 只覆盖一个目标。flag 在校验后先生成两份完整新内容，把两份同目录唯一临时文件写入并 fsync。完整 marker JSON 先写入 qa-gate 目录的唯一临时文件并 fsync，再通过 `os.link` 独占发布为 `.flag-transaction.json`；发布完成并 fsync 目录后才允许第一次目标替换。标记记录目标/临时相对路径、读取时旧 SHA-256、目标新 SHA-256 和原 JSON 结果。提交前同时检查两个目标仍等于读取时旧哈希或本事务新哈希；第三种内容表示调用已陈旧，当前事务清理 marker 与临时文件并以 2 退出。前置校验通过后依次替换 checklist 与 ledger，每次替换后 fsync 目标目录；验证两个目标新哈希后删除标记并再次 fsync marker 目录。

任何参数齐全（argparse 解析通过）的 flag 调用看到 pending 标记时先恢复旧事务——恢复优先于参数值校验，值非法的调用同样先完成恢复并返回 0。目标现状分四支：已匹配本事务新哈希时跳过；匹配读取时旧哈希且临时文件存在时继续替换；匹配旧哈希但临时文件缺失时保留标记并 exit 2；与新旧哈希均不匹配（第三方改写）时保留标记、exit 2 并报告哈希差异。恢复成功返回标记保存的旧 issue 结果与 `recovered: true`，本次新参数不进入登记。并发调用发布 marker 遇到已存在时，清理自己尚未发布的临时文件并进入相同恢复路径。

事务语义是“全部成功或可恢复”。IO/进程中断可能留下短暂单目标新状态；标记让该状态显式可检测并在下一调用前收敛。

### Decision 6: 新轮报告由代码创建固定骨架

`render_issue_report` 生成标题、代码所有权说明和 `## Issues`。issue 行在本轮 review 内连续追加。Gate 总结保留在对话回执与 x-fix 处置报告中，clean 轮无需创建空 ledger。

### Decision 7: flag 只拥有降级写权

P0/P1 将目标状态设为 `[!] 🔴`；P2 保持任务状态；flag 全程不写 `[x]`。主 agent 在修复和复审确认后手动升钩。

### Decision 8: 活跃协议一次迁移到 issue 命名

Commit B 覆盖 x-qa-gate SKILL、reviewer references、report template、x-dev execution rules、x-fix SKILL 与 gate-fix reference。Commit C 覆盖 CLAUDE 和中英文 README。历史 task 与归档 change 保持原文。

## Risks / Trade-offs

- [Risk] 中断可能留下 pending 事务或一个已替换目标。→ Mitigation：每次 flag 先恢复，目标哈希用于幂等前滚。
- [Risk] 事务标记或临时文件被人工删除会阻断恢复。→ Mitigation：保留 marker、exit 2，并报告缺失路径与目标哈希。
- [Risk] 同秒轮次出现多个文件。→ Mitigation：数值后缀提供确定排序；并发同名由 marker 独占发布仲裁。
- [Risk] 较慢调用在另一事务完成后取得 marker，可能携带旧 ledger 快照。→ Mitigation：marker 保存读取时旧哈希，首次 replace 前对两个目标做乐观前置校验。
- [Risk] 主 agent 重复完成两次正常 flag 会登记两个 issue。→ Mitigation：重复记录保持可见；事务恢复调用只返回旧结果，不处理新参数。
- [Risk] 旧 emoji checklist 的目标行变为双轨状态。→ Mitigation：只改目标单元格，status/graph 兼容行为保持稳定。

## Migration Plan

1. Commit 0 提交 plan v7、v5 归档与 active OpenSpec change，记录基线验证。
2. Commit A 实现 flag、事务恢复与单元测试。
3. Commit B 同步 active skills、reviewer references、report template 和 x-fix gate reference。
4. Commit C 同步 CLAUDE 与中英文 README。
5. 完整验证后交用户验收；验收通过再归档 change。

## Open Questions

无。issue 命名、参数文法、同秒轮次、事务恢复、JSON 恢复信号与文档迁移范围均已确定。
