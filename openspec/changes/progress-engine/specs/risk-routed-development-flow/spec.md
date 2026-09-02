## ADDED Requirements

### Requirement: Gate ② issue 登记走 flag 与代码编号
Gate ② reviewer SHALL 只在返回值中给出 T#、severity、loc、msg，MUST NOT 写文件或分配 issue ID。主 agent SHALL 通过 `python3 tools/xdev.py flag` 串行逐条登记；每轮首条使用 `--new-round`。flag SHALL 分配 `issue-<n>`、生成 issue ledger 并执行 checklist 降级，每个 task 长期只保留一份 `dev-checklist.md`。子 agent、reviewer 与 x-fix SHALL 保持状态列和 issue ledger 原样；主 agent SHALL 在修复完成、增量复审干净且亲自确认后手动升回 `[x]`。

#### Scenario: Reviewer 返回问题后由 flag 登记
- **GIVEN** reviewer 返回 T2、P1、src/a.py:10、空输入未处理
- **WHEN** 主 agent 运行对应 flag 命令
- **THEN** flag 分配 `issue-<n>`、写入 ledger、降级 T2，随后 x-fix 以该 issue ID 记录处置

#### Scenario: 每轮首条开启新 ledger
- **GIVEN** 新一轮 review 返回至少一条问题
- **WHEN** 主 agent 登记本轮第一条 issue
- **THEN** 命令带 `--new-round`，本轮从 `issue-1` 开始；后续 issue 追加同一文件

#### Scenario: pending 事务优先恢复
- **GIVEN** 上次 flag 留有 pending transaction marker
- **WHEN** 主 agent 尝试登记新 issue
- **THEN** flag 先恢复并返回旧 issue，主 agent 再次调用后登记新 issue

#### Scenario: 修复 agent 保持状态与 ledger 原样
- **GIVEN** T2 已因 `issue-1` 标记为 `[!] 🔴`
- **WHEN** 子 agent 或 x-fix 修复该问题
- **THEN** 修复只更新实现、测试与处置记录，T2 和 issue ledger 保持原样

#### Scenario: 主 agent 在复审干净后升钩
- **GIVEN** T2 修复完成且增量复审未产生新的阻塞 issue
- **WHEN** 主 agent 亲自确认复审结果
- **THEN** 主 agent 手动将 T2 从 `[!]` 升回 `[x]`

#### Scenario: P2 issue 保持非阻塞
- **WHEN** 主 agent 以 P2 登记 T3 问题
- **THEN** T3 状态保持原样，该 issue 进入 ledger 且不阻塞 Gate 结论

### Requirement: 活跃 QA Gate 文档统一 issue 协议
活跃 `skills/x-qa-gate`、`skills/x-fix`、`skills/x-dev/references/execution-rules.md`、`CLAUDE.md`、`README.md` 与 `README_zh.md` SHALL 使用 `issue-<n>` 和 flag 调用协议。Reviewer references SHALL 移除 F1..Fn 自编号要求；x-fix gate reference SHALL 使用 issue ID 关联处置与增量复审。历史 task 与 archived change SHALL 保持原文。

#### Scenario: 活跃协议无旧编号
- **WHEN** 搜索活跃 QA Gate 与 gate-fix 文档中的 F1、F#、F1..Fn 和手写 issue ledger 指引
- **THEN** 搜索结果为空，示例与处置表统一引用 `issue-1`

#### Scenario: 历史档案保持原文
- **WHEN** 完成活跃协议迁移
- **THEN** `dev-pipeline/tasks/` 历史材料与 `openspec/changes/archive/` 未被批量改写
