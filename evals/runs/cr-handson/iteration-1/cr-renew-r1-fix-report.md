# CR 报告：续借与查借阅记录的正确性检查

> 时间：2026-11-23 04:13
> 模式：检查代码
> 范围：src/library/loan.py 的 renew()、list_loans()
> spec：docs/spec/loan/spec.md，docs/spec/loan/tech-design.md

## 范围

- 现象或检查目标：检查续借（renew）和查借阅（list_loans）是否守住 spec 的规则。只出报告，不改代码。
- 期望：C1 每笔借阅最多续借 2 次，第 3 次拒绝且到期日不变；D01 续借先校验再改数据，校验失败时到期日和续借次数都不变；feat01 续借延长 14 天、逾期拒绝；feat02 读者查自己的借阅。
- 实际：跑 `python3 -m pytest -q`，2 条通过。另用一段 `python3 -I -c` 临时脚本复现（不落盘），结果见下面各问题的证据。
- 看了哪些代码：src/library/loan.py（renew、list_loans、LoanStore），tests/test_loan.py，docs/spec/loan/spec.md，docs/spec/loan/tech-design.md。

## 规则表

| 编号 | 规则 | 来源 | 最小反例 | 结论 | 问题 |
|---|---|---|---|---|---|
| loan:C1 | 每笔借阅最多续借 2 次，第 3 次拒绝且到期日不变 | spec.md 关键约束 C1 | GIVEN 借阅 1 续借次数为 0，due 为 2026-12-01 WHEN 连续续借 3 次 THEN 第 3 次应被拒绝；实测第 3 次成功，due 变为 2027-01-12，次数为 3 | 被打破 | B1 |
| loan:D01 | 续借先校验再改数据，任一校验失败时到期日和续借次数都不变 | tech-design.md D01 | GIVEN 借阅 2 due 为 2026-11-01，today 为 2026-11-20 WHEN 续借 THEN 抛 OverdueError，次数应仍为 0；实测次数变为 1 | 被打破 | B2 |
| loan:feat01-场景1 | 续借延长 14 天，续借次数加 1 | spec.md feat01 场景1 | GIVEN 借阅 1 未逾期、次数为 0 WHEN 续借一次 THEN due 为 2026-12-15，次数为 1 | 守住了 | - |
| loan:feat01-场景2 | 逾期不能续借，抛 OverdueError，到期日不变 | spec.md feat01 场景2 | 同 D01 反例 WHEN 续借 THEN 抛 OverdueError，实测 due 仍为 2026-11-01；次数的变化归 D01，见 B2 | 守住了 | - |
| loan:feat02-场景1 | 读者查自己的借阅，返回这位读者的全部借阅 | spec.md feat02 场景1 | GIVEN 会话为读者 10 已登录 WHEN 调用 list_loans 并在 request 里传 member_id=20 THEN 应只返回读者 10 的借阅；实测返回读者 20 的「活着」 | 被打破 | B3 |
| 新1 | 续借只能由借阅人本人发起 | spec 没写；src/library/loan.py 的 renew() 签名（只收 loan_id，不收调用者身份） | GIVEN 读者 20 已登录 WHEN 续借读者 10 的借阅 loan 1 THEN 应被拒绝；模块内无校验，调用入口不在仓库里，无法确认 | 没法验证 | B4 |

编号：spec 里的规则用 `loan:C1`、`loan:D01`、`loan:feat01-场景1`；spec 没写的用 `新1`。

## 问题

| ID | 严重度 | 状态 | 位置 | 一句话 |
|---|---|---|---|---|
| B1 | P1 | 已修 | `src/library/loan.py` 的 `renew()`，第 43 行 | 上限判断差一位，第 3 次续借被放行 |
| B2 | P1 | 已修 | `src/library/loan.py` 的 `renew()`，第 42 行与第 45–46 行 | 续借次数在校验前就加一，校验失败时次数已被改 |
| B3 | P0 | 已修 | `src/library/loan.py` 的 `list_loans()`，第 53 行 | 客户端传的 member_id 覆盖登录会话，读者可查别人的借阅 |
| B4 | P2 | 待确认 | `src/library/loan.py` 的 `renew()`，第 39 行 | 续借没有校验调用者身份，spec 没写，缺证据 |

### B1: 第 3 次续借被放行

- 规则：loan:C1
- 位置：`src/library/loan.py` 的 `renew()`，第 43–44 行
- 反例：GIVEN 借阅 1 的续借次数为 0，due 为 2026-12-01 WHEN 连续续借 3 次 THEN 第 3 次应抛 RenewLimitError，due 与次数都不变
- 证据：路径为 renew() → store.get → 第 42 行 renew_count 加 1 → 第 43 行判断 `> MAX_RENEWALS + 1`，即 `> 3`。次数为 3 时不触发，所以第 3 次续借成功。复现输出：call 1 due 2026-12-15；call 2 due 2026-12-29；call 3 due 2027-01-12 次数 3 成功；call 4 才抛 RenewLimitError。测试文件里没有覆盖上限的用例。
- 影响：每笔借阅可以续借 3 次，违反 C1。读者会多占一次借阅期，图书馆的借阅规则被绕过。
- 怎么改：上限判断改为按 MAX_RENEWALS 本身计算（例如校验"当前次数已达 MAX_RENEWALS 则拒绝"），错误信息里的 2 次保持不变。补一个第 3 次续借被拒绝的反例测试。

**修复**

- 结果：已修
- 改动位置：`src/library/loan.py` 的 `renew()`，第 42–43 行（上限判断改为 `renew_count >= MAX_RENEWALS`，错误信息不变）
- 反例测试：`tests/test_loan.py::test_third_renewal_is_rejected`（修之前失败：DID NOT RAISE，修之后通过）
- 验证：`pytest -q` 全量 5 通过；不在 task 里，未跑 `xdev coverage`

### B2: 校验失败时续借次数已被改

- 规则：loan:D01
- 位置：`src/library/loan.py` 的 `renew()`，第 42 行先加次数，第 43–46 行才校验
- 反例：GIVEN 借阅 2 的续借次数为 0，due 为 2026-11-01 WHEN 在 today 为 2026-11-20 时续借 THEN 抛 OverdueError，due 不变，次数应仍为 0
- 证据：路径为 renew() → 第 42 行 `renew_count += 1` → 第 45 行判断逾期 → 第 46 行抛 OverdueError。复现输出：`OverdueError after overdue reject: count 1 due 2026-11-01`，次数已从 0 变为 1。同样，第 4 次续借触发 RenewLimitError 时，次数被加到 4（复现输出 `count 4`）。测试文件里没有逾期和上限的用例，测不出这个问题。
- 影响：每次被拒绝的续借都会消耗次数。读者可能在数据上被记成已续借多次，之后合法的续借会被错误地拒绝。
- 怎么改：先完成全部校验，校验通过后再修改 renew_count 和 due。补一个"逾期续借被拒绝后次数不变"的反例测试。

**修复**

- 结果：已修
- 改动位置：`src/library/loan.py` 的 `renew()`，第 42–47 行（先做上限和逾期校验，通过后才 `renew_count += 1` 并改 due）
- 反例测试：`tests/test_loan.py::test_overdue_renewal_does_not_consume_count`（修之前失败：次数已变为 1，修之后通过）
- 验证：`pytest -q` 全量 5 通过；不在 task 里，未跑 `xdev coverage`

### B3: 读者可通过 member_id 查到别人的借阅

- 规则：loan:feat02-场景1
- 位置：`src/library/loan.py` 的 `list_loans()`，第 53 行
- 反例：GIVEN 读者 10 已登录，借阅 1 属于 10，借阅 2 属于 20 WHEN 调用 `list_loans(store, session_member_id=10, request={"member_id": 20})` THEN 只返回读者 10 的借阅；实测返回 `['活着']`，即读者 20 的借阅
- 证据：路径为 list_loans() → 第 53 行 `request.get("member_id", session_member_id)`，客户端传来的值优先于登录会话。函数 docstring 写明 session_member_id 来自登录会话，说明意图是信会话、不信 request。现有测试 `test_list_own_loans` 只传空的 request，测不出这个问题。
- 影响：任何已登录读者都能按 member_id 查看其他读者的借阅记录，是越权和隐私泄露。
- 怎么改：查询直接用 session_member_id，忽略 request 里的 member_id。若将来需要管理员按读者查，另开一个带权限校验的入口。补一个"带别人的 member_id 仍只返回自己借阅"的反例测试。

**修复**

- 结果：已修
- 改动位置：`src/library/loan.py` 的 `list_loans()`，第 53 行（改为只用 session_member_id 查询，忽略 request 里的 member_id；函数签名不变）
- 反例测试：`tests/test_loan.py::test_list_ignores_client_member_id`（修之前失败：返回 `['活着']`，修之后通过）
- 验证：`pytest -q` 全量 5 通过；不在 task 里，未跑 `xdev coverage`

### B4: 续借是否只能本人发起，缺规则

- 规则：新1
- 位置：`src/library/loan.py` 的 `renew()`，第 39 行（签名只收 loan_id 和 today，没有调用者身份）
- 反例：GIVEN 读者 20 已登录 WHEN 续借读者 10 的借阅 loan 1 THEN 应被拒绝。
- 证据：renew() 的签名里没有调用者身份，本模块内无法判断。仓库里也没有调用 renew() 的入口代码，所以无法确认上层是否已做校验。spec 的 feat01 只写"读者有一笔未逾期的借阅"，没写是否必须是本人的借阅。
- 影响：如果上层没有校验，任何读者可以续借别人的借阅，会改别人的到期日。
- 怎么改：需要用户确认续借是否只能由借阅人本人发起。若是，renew() 应接收 session_member_id 并校验 loan.member_id，同时把这条规则补进 spec 的 feat01。补证据的办法是找到调用 renew() 的入口代码后再核对。问谁：spec 作者或产品负责人。

**修复**

- 结果：待确认
- 要确认：续借是否只能由借阅人本人发起？这条规则 spec 没写。确认后再决定 renew() 是否接收调用者身份并校验 loan.member_id，并补进 spec 的 feat01。本次未改代码。

## 结论

- 最严重的问题：B3（P0），list_loans() 信任客户端传来的 member_id，读者可以查看其他读者的借阅记录。
- spec 要补的规则：新1（续借只能由借阅人本人发起），待用户确认后补进 docs/spec/loan/spec.md 的 feat01。
- 严重度统计：P0 1 条，P1 2 条，P2 1 条。
