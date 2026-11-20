# task-loan-core · 开发清单

> spec: spec.md
> tech-design: tech-design.md
> 拆解基线：spec@a1b2c3 · tech-design@d4e5f6

| # | 任务 | 场景回指 | 涉及文件 | 状态 |
|---|---|---|---|---|
| 1 | 借书与借阅上限（C1；D01、D02；用例 T1、T2；unit） | feat01 场景1-2 | src/loan/borrow.ts, tests/borrow.test.ts | [x] 🟢 |
| 2 | 续借（D02、D03；用例 T3、T4；unit） | feat02 场景1-2 | src/loan/renew.ts, tests/renew.test.ts | [x] 🟢 |
| 3 | 逾期天数（D02；用例 T5；unit） | feat03 场景1 | src/loan/overdue.ts, tests/overdue.test.ts | [x] 🟢 |
