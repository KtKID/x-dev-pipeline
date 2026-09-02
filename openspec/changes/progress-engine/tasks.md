## 1. 前置门禁与 planning 提交

- [x] 1.1 T1：以 plan v7 为需求源，维护 proposal、design、`xdev-progress-engine` spec 与 `risk-routed-development-flow` delta；统一 `issue-<n>`、事务恢复、同秒后缀、严格参数文法和活跃文档迁移范围。
- [x] 1.2 T2：复跑基线 unittest 与 OpenSpec strict validation，记录 planning 基线。（57 tests OK；change strict 1/1、all strict 5/5）
- [x] 1.3 T3：按 commit 0 边界提交 plan、v5 归档与 active OpenSpec change，保留无关工作区文件原样。

## 2. Commit A：flag 命令、事务恢复与测试

- [x] 2.1 T4：在 `tools/xdev.py` 注册 flag，完成 severity、严格 T# 列表、loc、msg 与 checklist 唯一性校验；校验失败零写入。
- [x] 2.2 T5：实现数值后缀轮次选择、`render_issue_report`、受限 `next_issue_id` 与 `append_issue_line`。
- [x] 2.3 T6：实现 `downgrade_task_rows`，只更新 P0/P1 目标状态单元格；P2、其他单元格与升钩保持现有边界。
- [x] 2.4 T7：实现单写者 `.flag-transaction.json`、固定同目录临时路径、无变化目标跳过临时文件、读取时/目标 SHA-256、陈旧写前置校验、目录 fsync、双目标 replace 与 `recover_flag_transaction`；恢复兼容旧版 UUID marker，返回旧 issue 且不处理新参数。
- [x] 2.5 T8：实现 JSON 四键输出与 0/2 退出码，补充人类可读成功、恢复和错误输出。
- [x] 2.6 T9：新增 `test/test_xdev_flag.py`，覆盖参数矩阵、issue 编号、受限扫描、同秒轮次、ledger 骨架、降级、P2 无 checklist 临时文件、固定临时路径、零残留、陈旧写保护、事务中断恢复、恢复优先于值校验、缺失恢复材料和 emoji 回归。
- [x] 2.7 T10：运行完整 unittest 与 flag 正反样例，仅提交 `tools/xdev.py` 和 `test/` 为 Commit A。（74 tests OK；Commit A `1a90a36`）

## 3. Commit B：skills 与 gate-fix 协议

- [x] 3.1 T11：更新 x-qa-gate SKILL、四份 reviewer references 和 report template：reviewer 返回 T#/severity/loc/msg；主 agent 每轮首条以 `--new-round` 调 flag；ledger 骨架声明首条由代码分配为 `issue-1`。
- [x] 3.2 T12：更新 x-dev execution rules、x-fix SKILL 与 `qa-gate-fix-mode.md`：状态/ledger 分权、issue ID 处置表和增量复审引用一致。
- [x] 3.3 T13：搜索 active skills，确认旧 F 编号与手写 issue ledger 指引清零；仅提交 `skills/` 为 Commit B。（plugin strict passed；Commit B `118649a`）

## 4. Commit C：仓库文档同步

- [x] 4.1 T14：更新 `CLAUDE.md` reviewer 协议，移除 reviewer 自编号，改为 flag 分配 `issue-<n>`。
- [x] 4.2 T15：更新 `README.md` 与 `README_zh.md` 的 Gate ② 报告说明、flag 命令和 issue ledger 语义。
- [x] 4.3 T16：搜索 active CLAUDE/README 契约并提交仓库文档为 Commit C；历史 task 与 archived change 保持原文。（Commit C `f93bf80`）

## 5. 交付验证与用户验收

- [x] 5.1 T17：复跑完整 unittest、flag fixture、change/all strict validation 与 `git diff --check`。（74 tests OK；change 1/1；all 5/5；plugin strict passed）
- [x] 5.2 T18：执行手工样例：P0 issue 登记、T9/重复 T#/非法 loc 原子拒绝、同秒新轮、msg 竖线、pending 事务恢复和主 agent 升钩。（全部通过）
- [x] 5.3 T19：汇总 active change、commit stats、测试输出与偏离说明，交用户验收并保持 active。
- [ ] 5.4 T20：用户验收通过后归档 change，复验主 specs，并提交归档材料。

## 6. 2026-08-05 单写者与唯一 checklist 修复

- [x] 6.1 T21：删除 UUID 临时文件协议；主 `flag.py` 与 benchmark 镜像改用固定临时路径，内容无变化时跳过 checklist 临时文件，提交与恢复后清理 scratch 文件。
- [x] 6.2 T22：同步 x-qa-gate/x-dev、CLAUDE、README、plan 与 OpenSpec 契约；新增 P2、重复 blocked、固定路径和恢复零残留反例。验证结果：120 tests OK；progress-engine strict 通过；all strict 12/12；`git diff --check` 通过；手工连续 P2 + P1 后仅保留一份 `dev-checklist.md`。

## 7. T# → 文件 → DoD 映射

| T# | 涉及文件 | 对应 DoD |
|----|----------|----------|
| T1 | plan 与 OpenSpec planning artifacts | DoD 11-13 |
| T2 | `test/`、OpenSpec change | DoD 1、11 |
| T3 | plan、v5 归档、OpenSpec change | DoD 12 |
| T4 | `tools/xdev.py` | DoD 5、9 |
| T5 | `tools/xdev.py` | DoD 4、7 |
| T6 | `tools/xdev.py` | DoD 2、3、8、10 |
| T7 | `tools/xdev.py` | DoD 6、6a、6b |
| T8 | `tools/xdev.py` | DoD 6 |
| T9 | `test/test_xdev_flag.py`、orchestration fixture | DoD 2-10 |
| T10 | `tools/xdev.py`、`test/` | DoD 1、12 |
| T11 | x-qa-gate SKILL/references/template | DoD 13 |
| T12 | x-dev execution rules、x-fix SKILL/reference | DoD 13 |
| T13 | `skills/` | DoD 13 |
| T14 | `CLAUDE.md` | DoD 13 |
| T15 | `README.md`、`README_zh.md` | DoD 13 |
| T16 | active repo docs | DoD 12、13 |
| T17 | 全部影响文件 | DoD 1、10、11 |
| T18 | 手工临时 fixture | DoD 2、4-9 |
| T19 | active change 与交付材料 | DoD 11、12 |
| T20 | archived change 与主 specs | DoD 11 |
| T21 | `skills/x-qa-gate/scripts/flag.py`、benchmark executor mirror | DoD 3、6、14 |
| T22 | tests、skills、plan、OpenSpec、CLAUDE、README | DoD 1、11、13、14 |
