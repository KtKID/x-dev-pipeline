# cr-handson · 评审侧考点

题目项目 `evals/problems/cr-handson/project/` 埋了三个问题：

| 编号 | 问题 | 位置 | 期望规则编号 | 期望结论 | 期望严重度 |
|---|---|---|---|---|---|
| X1 | 第 3 次续借没被拒（`> MAX_RENEWALS + 1`） | `src/library/loan.py` 的 `renew()` | loan:C1 | 被打破 | P1（P0 也接受） |
| X2 | 先加续借次数再校验，校验失败也改了次数 | `renew()` | loan:D01（或 loan:feat01-场景2） | 被打破 | P1 |
| X3 | `list_loans()` 用请求里的 member_id 查库，可查别人借阅 | `list_loans()` | 新N（spec 没写） | 被打破 | P0 |

x-cr 阶段（cr 报告）判分：

1. `validate_report.py` 通过。
2. 规则表三条都在，编号如上；X3 用“新N”且结论里提醒补 spec。
3. 三个问题都有 Bn，严重度如上；位置写文件 + 函数。
4. 没改代码（`git diff` / 文件哈希比对 src/ 无变化）。

x-fix 阶段判分（在 x-cr 报告的副本上跑）：

1. `validate_report.py` 通过，三个 Bn 状态都是“已修”，修复段写全，改动位置不是 commit 哈希。
2. 项目全量测试全绿（含 x-fix 新加的反例测试，每个 P0/P1 至少一条）。
3. `answers/cr-handson/hidden_test.py` 全部通过。
4. 没有新建 `reports/fix/` 或其他修复报告文件。
