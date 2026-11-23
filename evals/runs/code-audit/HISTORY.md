# code-audit · 运行历史

测什么：真跑一次 x-code-audit。`evals/problems/code-audit/cases/library/project` 埋了各层的问题和陷阱；`evals/scripts/audit_grade.py` 判分：只出一份报告、带 8 位检查 ID、开头写范围、`audit.py verify` 通过、没改代码、问题按 P0→P2 排、每条都有是什么/影响/位置，埋的问题找到没有，陷阱有没有误报，单模块时有没有报到范围外。

A = 子 agent 回执写“怎么改”；B = 不写。iteration-N 下 `<题>-<变体>-rM.json` 是判分，`-report.md` 是报告，`timing.json` 是 token 和耗时。

| iteration | 结果 | 发生了什么 |
|---|---|---|
| 1 | A：全量 17/17 ×2、单模块 12/12；B：全量 15/17、17/17，单模块 12/12（haiku） | 写不写“怎么改”：A 全过；B 一次 verify 没过，两次把问题定成 P0 偏重（列表页显示的上限、发信只是存进内存列表）；token A 全量 12.9–13.3 万，B 12.2–14.0 万，没有省。结论：保留“怎么改”。另外：脚本把 TYPE_CHECKING 下的导入算成运行时循环依赖，四份报告都指出，已改为单独报 P2；子 agent 重复报脚本已报的问题，已加“已由 Ux 报过”的写法并让 verify 认；handle_overdue 的陷阱不成立（dispatch 本身只有测试在用），判分改为说清这一点算对。答题环境派不了子 agent，6 份都是主 agent 逐单位做的，并行派工这一步这次没测到 |
