# CR 报告：检查 loan.py 的续借和查借阅

> 时间：2026-11-23 04:13
> 模式：检查代码
> 范围：src/library/loan.py（renew、list_loans 及其调用的 LoanStore）
> spec：docs/spec/loan/spec.md 和 docs/spec/loan/tech-design.md

## 范围

- 现象或检查目标：续借次数和逾期校验是否按 spec 生效；查借阅记录时是不是只能看自己的
- 期望：spec 的 C1（每笔最多续借 2 次）、D01（续借先校验再改数据）、feat01 两个场景、feat02 场景1（读者查自己的借阅）
- 实际：用最小反例在项目副本里跑了一遍（只读，没改代码），结果见问题表
- 看了哪些代码：
  - src/library/loan.py：renew()、list_loans()、LoanStore
  - tests/test_loan.py：两条正向测试，没有续借上限、逾期、越权的测试
  - docs/spec/loan/spec.md、docs/spec/loan/tech-design.md

## 规则表

| 编号 | 规则 | 来源 | 最小反例 | 结论 | 问题 |
|---|---|---|---|---|---|
| loan:C1 | 每笔借阅最多续借 2 次，第 3 次被拒绝 | spec.md 关键约束 C1 | GIVEN 借阅已续借 2 次，WHEN 再续借，THEN 拒绝。实际：第 3 次续借成功，到期日从 12-29 推到 2027-01-12 | 被打破 | B1 |
| loan:D01 | 续借先校验再改数据，校验失败时到期日和续借次数都不变 | tech-design.md D01 | GIVEN 借阅已逾期（due 2026-11-01），WHEN 续借，THEN 拒绝且次数不变。实际：抛 OverdueError，但 renew_count 从 0 变成 1 | 被打破 | B2 |
| loan:feat01-场景1 | 未逾期、续借次数少于 2 时，续借延长 14 天 | spec.md feat01 场景1 | GIVEN 到期日 12-01，WHEN 续借，THEN 到期日 12-15、次数 1 | 守住了 | - |
| loan:feat01-场景2 | 已逾期不能续借，到期日不变 | spec.md feat01 场景2 | GIVEN 到期日 11-01，WHEN 续借（today 11-20），THEN 抛 OverdueError，到期日仍是 11-01。实际与 spec 一致（次数的问题见 B2） | 守住了 | - |
| loan:feat02-场景1 | 读者查借阅记录，返回的是自己的全部借阅 | spec.md feat02 场景1 | GIVEN 会话里是会员 10，WHEN 请求参数带 member_id=20，THEN 返回的应只是会员 10 的借阅。实际：返回了会员 20 的《活着》 | 被打破 | B3 |
| 新1 | 查借阅时，查哪个读者的借阅由登录会话决定，客户端传来的同名字段改变不了 | spec 没写；src/library/loan.py 的 list_loans() 注释写明 session_member_id 来自登录会话 | 同 loan:feat02-场景1 的反例 | 被打破 | B3 |

编号说明：spec 里的规则用 `loan:C1`、`loan:D01`、`loan:feat01-场景1` 这类写法；spec 没写的规则是 `新1`。

## 问题

| ID | 严重度 | 状态 | 位置 | 一句话 |
|---|---|---|---|---|
| B1 | P1 | 待修 | `src/library/loan.py` 的 `renew()`，第 43 行 | 续借上限差一，实际允许续借 3 次 |
| B2 | P1 | 待修 | `src/library/loan.py` 的 `renew()`，第 42 行 | 续借被拒绝（逾期或超限）时，续借次数仍被加 1 |
| B3 | P0 | 待修 | `src/library/loan.py` 的 `list_loans()`，第 53 行 | 读者可以用请求参数 member_id 查到别人的借阅 |

### B1: 续借上限差一，第 3 次续借被放行

- 规则：loan:C1
- 位置：`src/library/loan.py` 的 `renew()`，第 42–44 行（判断在第 43 行）
- 反例：GIVEN 借阅已续借 2 次，WHEN 再续借，THEN 应抛 RenewLimitError、到期日不变。实际第 3 次成功。
- 证据：判断写的是 `loan.renew_count > MAX_RENEWALS + 1`，即大于 3 才拒绝。在项目副本里对同一笔借阅连续调用 `renew()` 四次，结果依次为成功、成功、成功、被拒绝（第 4 次才抛错）。测试里没有任何超限测试，所以测试没抓住这个错。
- 影响：读者可以比规则多续借一次，借期比图书馆设定的长。不涉及数据丢失，但是用户可见、也是 C1 明确禁止的结果。
- 怎么改：把判断改成 `renew_count >= MAX_RENEWALS` 的前置检查（或等价写法），并补一条“第 3 次续借被拒绝”的测试。注意 B2 的修法会改同一段代码，两个一起改。

### B2: 续借被拒绝时，续借次数仍被加 1

- 规则：loan:D01
- 位置：`src/library/loan.py` 的 `renew()`，第 42 行（`loan.renew_count += 1` 在校验之前执行）
- 反例：GIVEN 借阅已逾期（due 2026-11-01），WHEN 续借（today 2026-11-20），THEN 抛 OverdueError，且续借次数不变。实际：抛了 OverdueError，但 renew_count 从 0 变成 1。超限的拒绝也一样：第 4 次尝试把计数推到 4。
- 证据：在项目副本里复现，逾期拒绝后 `renew_count == 1`、`due` 仍为 2026-11-01。代码路径：入口 renew() → 读借阅 → 改次数（写状态）→ 校验（超限、逾期）→ 改到期日。校验放在写状态之后，违反 D01 的“先校验再改数据”。
- 影响：读者的续借机会被白白消耗。一笔逾期后被拒的续借，会让之后真正能续的那次变成“已用完”。这是状态被错误修改，属于数据错误，但影响范围限于续借次数。
- 怎么改：把 `renew_count += 1` 挪到两道校验之后、改到期日之前。补一条“逾期续借后次数不变”的测试。

### B3: 查借阅记录可以指定别人的会员号

- 规则：loan:feat02-场景1、新1
- 位置：`src/library/loan.py` 的 `list_loans()`，第 53 行（`member_id = request.get("member_id", session_member_id)`）
- 反例：GIVEN 会话是会员 10，WHEN 请求参数带 `member_id=20`，THEN 只能返回会员 10 的借阅。实际返回了会员 20 的《活着》。
- 证据：项目副本里用 `list_loans(store, 10, {"member_id": 20})` 复现，返回 `['活着']`。代码路径：入口 list_loans() → 取 request 里的 member_id（客户端输入，优先） → 按这个 id 过滤借阅 → 返回。登录会话的 session_member_id 只在客户端没传时才用。
- 影响：任何已登录读者都能看到其他读者的借阅记录，这是隔离被突破，属于越权。
- 怎么改：查询对象只用 session_member_id，删掉对 request 里 member_id 的读取。若将来需要管理员查别人，应该走单独的、带权限判断的入口。补一条“请求带别人的 member_id 也只返回自己借阅”的测试。

## 原因排查

不写：三个问题的原因在代码里一眼可见，不需要排查。

## 结论

- 最严重的问题：B3（P0）：查借阅记录可以指定别人的会员号，读者能看到别人的借阅。
- spec 要补的规则：新1（查借阅时查的是哪个读者，由登录会话决定，不由客户端参数决定）。建议补进 docs/spec/loan/spec.md 的 feat02 或关键约束。另外 tech-design.md 目前只有 D01，建议补 D02 对应 B3 的规则。
- 测试缺口：tests/test_loan.py 只有两条正向测试，C1、D01、feat01 场景2、feat02 的越权情况都没有反例测试，所以这些规则现在靠读代码和复现判断，不靠测试守住。
