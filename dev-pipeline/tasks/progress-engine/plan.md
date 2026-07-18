# progress-engine 开发方案（v7，issue 登记改为函数调用）

> 一句话：review 发现问题后，由主 agent 调用 `xdev.py flag` 逐条登记——issue 编号、
> 台账格式化、checklist 降级全部由代码完成；LLM 只传参数。
> 升 `[x]` 仍由主 agent 复审确认后手动执行。
> 本文档自包含。先转 OpenSpec change 交用户确认再实现。验收通过前保持 active。
>
> v7 背景：v6 让 LLM 手写五段竖线行、代码事后解析，格式错误反馈链过长。
> 用户于 2026-07-18 拍板：格式由 Python 生成，LLM 只传参；问题编号统一为
> `issue-1`、`issue-2`。v5 指纹版归档于同目录 `plan-v5-fingerprint-archived.md`。

---

## 0. 执行须知

- **仓库**：`/Volumes/machub_app/proj/x-dev-pipeline`
- **前置条件**：实现基线 clean，且 `python3 -m unittest discover -s test` 全过；
  本 change 独立于 fixes-and-metrics
- **提交拆分**：commit 0（planning：本 plan + `plan-v5-fingerprint-archived.md` +
  active OpenSpec change）→ A（`tools/xdev.py` flag + `test/`）→ B（`skills/`）→
  C（`CLAUDE.md` + README）→ 收尾归档提交
- **范围守卫**：保留 token+emoji 双轨状态、fix 计数、评审维度语义和 capability 回流；
  issue 台账行只经 flag 命令落盘

## 1. 背景与目标

原始意图：LLM review 后记录哪个 task 有 bug，checklist 对应 task 行标为 `[!]`。

v7 将 issue 写入口收窄为函数调用。LLM 传入 task、严重度、位置和描述；代码负责参数
校验、`issue-<n>` 编号、轮次文件选择、台账格式化、事务恢复和 checklist 降级。

## 2. 分权模型

| 动作 | 谁 | 说明 |
|------|----|------|
| 写代码 / 修 bug | 子 agent | 保持状态列与 issue 台账原样 |
| 发现问题 | reviewer 子 agent | 只在返回值中给出 T#、严重度、位置和描述 |
| 登记 issue | `xdev.py flag` | 主 agent 逐条调用；代码分配编号、写台账、只降级 |
| 升 `[x]` | 主 agent | 修复与复审确认后手动签字 |

## 3. 契约

### 3.1 flag 命令

```text
python3 tools/xdev.py flag <task-dir> --task <T#列表> --severity <P0|P1|P2> \
    --loc <file:line> --msg <问题描述> [--new-round] [--json]
```

#### 参数校验

没有 pending 事务时，flag 在任何业务文件写入前完成全部校验：

1. `--severity` 仅接受 `P0`、`P1`、`P2`。
2. `--task` 按逗号拆分并 trim；每项严格匹配 `T[1-9][0-9]*`；空项、重复项、
   checklist 中缺失或重复的目标 T# 均为错误。
3. `--loc` 必须是单行 `路径:正整数行号`；路径非空；拒绝 `|`、`\r`、`\n`。
4. `--msg` trim 后非空；先把 `\r\n`、`\r`、`\n` 统一替换为空格；其余字符必须
   为可打印字符，竖线原样保留。
5. 任一参数或校验错误返回 2，checklist、台账、事务标记均保持原样。语法完整的
   调用若发现 pending 事务，优先恢复旧事务并忽略本次参数。

#### 台账轮次与 issue 编号

1. 基础文件名为 `qa-gate-report-<YYYYMMDD-HHmmss>.md`。
2. 同一秒内再次 `--new-round` 时，依次使用 `-01`、`-02` 后缀；后缀按整数递增，
   选择最新报告时按 `(时间戳, 后缀整数)` 排序。
3. 缺省追加到最新报告；目录或报告缺失时自动创建首轮文件。
4. 新报告由代码创建固定骨架：标题、代码所有权说明、`## Issues`。
5. `next_issue_id` 只扫描代码生成的行首 `^- issue-([0-9]+) \|`，取最大值加一；
   首条为 `issue-1`。severity、T#、位置和描述均不从台账反向解析。
6. 台账行由 `append_issue_line` 唯一生成：
   `- issue-<n> | <严重度> | <T#列表> | <位置> | <描述>`。

#### 双文件事务与恢复

flag 同时更新 issue 台账和 `dev-checklist.md`，使用
`<task-dir>/reports/qa-gate/.flag-transaction.json` 协调：

1. 参数校验后，在内存生成完整新台账、完整新 checklist 和 JSON 结果。
2. 两份新内容分别写入目标同目录的唯一临时文件并 flush/fsync。
3. 把完整 marker JSON 写入 qa-gate 目录的唯一临时文件并 fsync，再用 `os.link`
   独占发布为 `.flag-transaction.json`；发布成功后删除 marker 临时文件并 fsync 目录。
   标记保存版本、目标相对路径、临时路径、目标 SHA-256 和本次 JSON 结果。
4. marker 已存在表示另一调用先获得提交权；当前调用清理自己尚未发布的临时文件，
   转入既有事务恢复，并且不登记自己的 issue。
5. marker 完整发布后，才通过 `os.replace` 依次提交两个目标；每次替换后 fsync 目标目录。
   每个文件自身无半写状态。两个目标哈希匹配后删除标记并再次 fsync marker 目录。
6. 任意语法完整的 flag 调用发现事务标记时，先前滚完成该事务并返回标记保存的原 issue 结果，
   `recovered: true`；本次新参数留待调用方再次执行，避免重试产生重复 issue。
7. 临时文件缺失且目标哈希不匹配时返回 2，保留事务标记并输出可操作诊断。
8. flag 仅在两个目标一致且事务标记清理完成后返回登记成功。IO/中断可能暂时留下
   标记或单目标新状态，下一次调用按上述协议恢复。

#### 降级、输出与退出码

1. P0/P1 将每个目标 T# 的状态单元格写为 `[!] 🔴`，该行其余内容保持原样；
   已 blocked 的目标保持原样。P2 只写台账。
2. flag 永远不写 `[x]`。
3. `--json` 固定输出：
   `{"issue":"issue-<n>","downgraded":[...],"report":"<文件名>","recovered":false}`。
4. 成功登记或成功恢复返回 0；参数、校验、事务或 IO 错误返回 2。

### 3.2 内部函数

| 函数 | 职责 |
|------|------|
| `flag_command(...)` | CLI 入口：恢复 → 校验 → 生成 → 事务提交 |
| `recover_flag_transaction(task_dir)` | 完成 pending 事务并返回原结果 |
| `resolve_current_report(reports_dir, new_round)` | 解析时间戳/数值后缀并选定或创建轮次 |
| `next_issue_id(report_text)` | 只扫描代码生成的 `issue-<n>` 行首 |
| `render_issue_report(...)` | 创建新轮台账固定骨架 |
| `append_issue_line(report_text, issue)` | 唯一 issue 行格式化点 |
| `downgrade_task_rows(checklist_text, task_ids)` | 只改目标状态单元格 |
| `commit_flag_transaction(...)` | 临时文件、marker 完整独占发布、替换与哈希确认 |

### 3.3 升钩规则

子 agent 修复 → reviewer 增量复审 → 仍有问题时主 agent 在新轮首条 flag 使用
`--new-round` → 复审干净后主 agent 亲自确认并把 `[!]` 手动升回 `[x]`。

## 4. skill 与文档同步清单

| 文件 | 改动 |
|------|------|
| `skills/x-qa-gate/SKILL.md` | reviewer 返回结构化问题；主 agent 逐条调用 flag；每轮首条 `--new-round` |
| `skills/x-qa-gate/references/*.md` | 移除 reviewer 自分配 F#；输出 T#、severity、loc、msg |
| `skills/x-qa-gate/templates/qa-gate-report-template.md` | 对齐 flag 生成的 issue ledger 骨架与 `issue-1` 样例 |
| `skills/x-dev/references/execution-rules.md` | 子 agent 保持状态列与台账原样；主 agent 验收后升 `[x]` |
| `skills/x-fix/SKILL.md` | 处置表引用 `issue-<n>`；修复保持状态列与台账原样 |
| `skills/x-fix/references/qa-gate-fix-mode.md` | gate-fix 输入与增量复审引用 `issue-<n>` |
| `CLAUDE.md` | reviewer 协议从 F1..Fn 更新为无编号返回，由 flag 分配 issue ID |
| `README.md`、`README_zh.md` | Gate ② 描述更新为 flag 生成 issue ledger |

## 5. 明确不做

指纹、证据过期检测、checklist 进度节、状态列三符号化、历史 checklist 批量迁移、
verify 回执 JSON、scaffold `--risk`、行级 verify、OS/advisory 文件锁、clean 轮强制留档、
重复 issue 静默去重。

## 6. DoD

| # | 验收项 | 预期 |
|---|--------|------|
| 1 | 完整 unittest | OK |
| 2 | P0 登记 | issue 台账新增 `issue-<n>`；目标状态变 `[!] 🔴`；其余内容原样 |
| 3 | P2 登记 | 台账新增 issue，所有任务状态原样 |
| 4 | 编号与轮次 | `issue-1`、`issue-2`；同秒新轮生成 `-01`；新轮从 `issue-1` 开始 |
| 5 | 校验原子性 | 无 pending 事务时，T9、重复 T#、非法 loc、空 msg 等返回 2；checklist、ledger、marker 均无写入 |
| 6 | 事务恢复 | 模拟首个 replace 后中断；下次 flag 前滚完成原 issue，返回 `recovered:true` 且不登记新 issue |
| 7 | 受限扫描 | msg 含 `issue-999` 不影响下一编号；仅行首 issue ID 参与计数 |
| 8 | 只降不升 | flag 永不写 `[x]`；已 blocked 时台账仍新增 issue |
| 9 | 文本净化 | msg 含竖线/换行正确落盘；loc 含竖线/换行被拒绝 |
| 10 | 旧格式回归 | emoji fixture 的 status/graph 行为不变 |
| 11 | OpenSpec | change strict 通过；验收前保持 active |
| 12 | 提交结构 | commit 0/A/B/C/归档；tasks.md 含 T#→文件→DoD 映射 |
| 13 | 活跃契约同步 | skills、CLAUDE、README 中 QA Gate 编号统一为 `issue-<n>`，无 F1/F# 与手写 issue 行指引 |

## 7. 交付材料

1. active OpenSpec change 与各 commit `git show --stat`
2. 单测完整输出与事务中断恢复 fixture
3. 手工样例：P0 登记、T9 原子拒绝、同秒新轮、msg 竖线、pending 事务恢复、主 agent 升钩
4. 每项偏离及理由
