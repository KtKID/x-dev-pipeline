# CR 报告：借阅模块

> 时间：2026-11-20 10:15
> 模式：检查代码
> 范围：src/library/loan.py
> spec：docs/spec/loan/spec.md

## 范围

- 现象或检查目标：检查借阅模块
- 期望：loan spec 的 C1、C2、feat01、feat02
- 实际：读代码、跑测试
- 看了哪些代码：src/library/loan.py、tests/test_loan.py

## 规则表

| 编号 | 规则 | 来源 | 最小反例 | 结论 | 问题 |
|---|---|---|---|---|---|
| loan:feat02-场景1 | 只能查自己的借阅 | spec.md feat02 场景1 | 读者 10 请求带 member_id=20 | 被打破 | B1 |
| loan:C1 | 最多续借 2 次 | spec.md C1 | 已续借 2 次再续借 | 被打破 | B2 |
| loan:feat02-场景2 | 只能还自己的书 | spec.md feat02 场景2 | 读者 10 还读者 20 的书 | 被打破 | B3 |
| loan:C2 | 单笔罚款上限 50 元 | spec.md C2；用户 2026-11-20 说上限是 100 元 | fine_cap() 返回 10000 | 来源不一 | B4 |
| 新1 | 逾期天数不能为负 | spec 没写；`src/library/loan.py` 的 `overdue_days()` | 到期日之前查询 | 守住了 | B5 |

## 问题

| ID | 严重度 | 状态 | 位置 | 一句话 |
|---|---|---|---|---|
| B1 | P0 | 已修 | `src/library/loan.py` 的 `list_loans()` 第 33 行 | 客户端传的 member_id 能查别人的借阅 |
| B2 | P1 | 已修 | `src/library/loan.py` 的 `renew()` 第 58 行 | 第 3 次续借没被拒 |
| B3 | P1 | 误报不修 | `src/library/loan.py` 的 `return_book()` | 没核对借阅归属，能还别人的书 |
| B4 | P2 | 待确认 | `src/library/loan.py` 的 `fine_cap()` | spec 写 50 元，代码和用户说法是 100 元 |
| B5 | P2 | 已修 | `src/library/loan.py` 的 `overdue_days()` | 到期前查询会得到负数 |

### B1: 查借阅可以指定别人

- 规则：loan:feat02-场景1
- 位置：`src/library/loan.py` 的 `list_loans()`，第 33 行
- 反例：GIVEN 读者 10 登录 WHEN 请求带 member_id=20 THEN 应只返回读者 10 的借阅；实际返回读者 20 的
- 证据：`member_id = request.get("member_id") or session_member_id` 优先用客户端参数
- 影响：任何读者能看别人的借阅记录
- 怎么改：只用 session_member_id 查询

**修复**

- 结果：已修
- 改动位置：`src/library/loan.py` 的 `list_loans()`，第 34 行，去掉客户端 `member_id` 参数，只用 `session_member_id` 查询
- 反例测试：`tests/test_loan.py::test_list_loans_ignores_client_member_id`
- 验证：`python3 -m pytest -q` 全量 4 通过

### B2: 续借上限多放行一次

- 规则：loan:C1
- 位置：`src/library/loan.py` 的 `renew()`，第 58 行
- 反例：GIVEN 已续借 2 次 WHEN 再续借 THEN 应抛 RenewLimitError；实际成功
- 证据：判断写成 `renew_count > MAX_RENEWALS`，次数为 2 时放行
- 影响：可以多续借一次
- 怎么改：改成 `>=`

**修复**

- 结果：已修
- 改动位置：`src/library/loan.py` 的 `renew()`，第 40 行，判断改为 `>=`
- 反例测试：`tests/test_loan.py::test_renew_after_limit`
- 验证：`python3 -m pytest -q` 全量 4 通过

### B3: 还书没核对归属

- 规则：loan:feat02-场景2
- 位置：`src/library/loan.py` 的 `return_book()`
- 反例：GIVEN 读者 10 登录 WHEN 还读者 20 的借阅 THEN 应抛 PermissionError
- 证据：读代码时觉得 return_book() 直接把 returned 设为 True
- 影响：读者能替别人还书
- 怎么改：先核对 loan.member_id 和 session_member_id

**修复**

- 结果：误报不修
- 理由：`return_book()` 第 49–50 行已经核对 `loan.member_id != session_member_id`，不符时抛 PermissionError，第 51 行才设 `returned = True`。归属核对存在，报告对代码的判断不成立。

### B4: 罚款上限说法不一

- 规则：loan:C2
- 位置：`src/library/loan.py` 的 `fine_cap()`
- 反例：fine_cap() 返回 10000（100 元），spec C2 写 50 元
- 证据：spec.md C2 与用户 2026-11-20 的说法不同
- 影响：按哪个上限收罚款不确定
- 怎么改：请用户确认按 50 元还是 100 元，确认后改代码或改 spec

**修复**

- 结果：待确认
- 要确认：spec C2 写单笔罚款上限 50 元，用户 2026-11-20 说是 100 元，要定按哪个；定了之后改 `fine_cap()` 的返回值或改 spec。

### B5: 逾期天数为负

- 规则：新1
- 位置：`src/library/loan.py` 的 `overdue_days()`
- 反例：GIVEN 到期日 12-01 WHEN 11-01 查询 THEN 应返回 0
- 证据：原来直接返回 `(today - loan.due).days`
- 影响：罚款可能算成负数
- 怎么改：加 max(0, …)

**修复**

- 结果：已修
- 改动位置：`src/library/loan.py` 的 `overdue_days()`，加了 `max(0, …)`
- 反例测试：`tests/test_loan.py::test_overdue_days_never_negative`
- 验证：`python3 -m pytest -q` 全量 2 通过

## 结论

- 最严重的问题：B1
- spec 要补的规则：新1
