# CR 报告：检查 loan 的续借和查借阅记录

> 时间：2026-11-23 03:59
> 模式：检查代码
> 范围：`src/library/loan.py` 的 `renew()`、`list_loans()`（续借和查借阅），测试 `tests/test_loan.py`
> spec：`docs/spec/loan/spec.md` 和 `docs/spec/loan/tech-design.md`

## 范围

- 现象或检查目标：用户要求检查续借和查借阅记录的正确性，本次只出报告，不改代码。
- 期望：spec 的 C1（最多续借 2 次）、feat01（续借延长 14 天，逾期不能续）、feat02（读者只查自己的借阅），tech-design 的 D01（校验失败时到期日和续借次数都不变）。
- 实际：通过读代码、运行现有测试（2 通过）、直接调用函数复现，发现三处问题（见问题表）。
- 看了哪些代码：
  - `src/library/loan.py`（`renew()`、`list_loans()`、`LoanStore`）
  - `tests/test_loan.py`
  - `docs/spec/loan/spec.md`、`docs/spec/loan/tech-design.md`

复现结果（在项目副本里直接调用，未改任何文件）：

- 同一笔借阅连续续借 4 次：第 1、2、3 次都成功（到期日分别变为 12-15、12-29、01-12），第 4 次抛 `RenewLimitError`。
- 一笔已逾期的借阅（到期日 11-01，今天 11-20）续借被拒绝，但 `renew_count` 从 0 变成 1，到期日不变。
- 读者 10 登录后，请求里带 `member_id=20`，返回的是读者 20 的《活着》。

## 规则表

| 编号 | 规则 | 来源 | 最小反例 | 结论 | 问题 |
|---|---|---|---|---|---|
| loan:C1 | 每笔借阅最多续借 2 次，第 3 次续借被拒绝，抛 RenewLimitError，到期日不变 | spec.md 关键约束 C1 | GIVEN 续借次数已为 2 WHEN 读者再续借 THEN 抛 RenewLimitError；实际第 3 次续借成功，次数变为 3 | 被打破 | B1 |
| loan:D01 | 续借先校验再改数据：任一校验失败时，到期日和续借次数都不变 | tech-design.md D01 | GIVEN 借阅已逾期 WHEN 读者续借 THEN 拒绝，到期日和续借次数都不变；实际续借次数从 0 变成 1 | 被打破 | B2 |
| loan:feat01-场景1 | 续借延长 14 天，续借次数加 1 | spec.md feat01 场景1 | GIVEN 未逾期、次数为 0 WHEN 续借 THEN 到期日 +14 天，次数为 1；实际到期日 2026-12-15，次数 1，`test_renew_extends_14_days` 通过 | 守住了 | - |
| loan:feat01-场景2 | 逾期不能续借，抛 OverdueError，到期日不变 | spec.md feat01 场景2 | GIVEN 到期日 11-01、今天 11-20 WHEN 续借 THEN 抛 OverdueError，到期日不变；实际抛 OverdueError，到期日仍为 11-01。这条场景只说到期日，次数的问题记在 B2 | 守住了 | - |
| loan:feat02-场景1 | 读者只查自己的借阅，返回这位读者的全部借阅 | spec.md feat02 场景1 | GIVEN 读者 10 已登录 WHEN 请求参数带 member_id=20 THEN 只返回读者 10 的借阅；实际返回读者 20 的《活着》 | 被打破 | B3 |

## 问题

| ID | 严重度 | 状态 | 位置 | 一句话 |
|---|---|---|---|---|
| B1 | P1 | 待修 | `src/library/loan.py` 的 `renew()` 第 43 行 | 第 3 次续借能成功，续借上限实际是 3 次，不是 2 次 |
| B2 | P1 | 待修 | `src/library/loan.py` 的 `renew()` 第 42 行 | 续借被拒绝时，续借次数仍会加 1，拒绝的一次也会占用额度 |
| B3 | P0 | 待修 | `src/library/loan.py` 的 `list_loans()` 第 53 行 | 客户端传来的 member_id 覆盖了登录会话里的读者，可以查到别人的借阅 |

### B1: 续借上限多放行一次（off-by-one）

- 规则：loan:C1
- 位置：`src/library/loan.py` 的 `renew()`，第 43 行（`if loan.renew_count > MAX_RENEWALS + 1:`）
- 反例：GIVEN 借阅的续借次数已为 2 WHEN 读者续借 THEN 必须抛 RenewLimitError
- 证据：代码路径为入口 `renew()` → 第 42 行把次数加 1 → 第 43 行判断 `count > 3`。续借次数为 2 时，加 1 后是 3，`3 > 3` 为假，放行。复现：连续调用 4 次，前 3 次成功，第 4 次才抛 `RenewLimitError`。现有测试只测了第 1 次续借，没有覆盖上限，所以测试没有抓住这个错误。
- 影响：读者可以比规则多续借一次，到期日多延长 14 天，图书馆的借出时间被多占一次。
- 怎么改：把第 43 行的判断改成“续借次数已经达到 MAX_RENEWALS 时拒绝”，并补一条第 3 次续借被拒绝的测试。

### B2: 被拒绝的续借仍然占用次数

- 规则：loan:D01
- 位置：`src/library/loan.py` 的 `renew()`，第 42 行（先加次数），第 43–46 行（之后才校验）
- 反例：GIVEN 借阅已逾期（到期日 2026-11-01，今天 2026-11-20）WHEN 读者续借 THEN 抛 OverdueError，到期日和续借次数都不变
- 证据：代码路径为入口 `renew()` → 第 41–42 行取出借阅并把次数加 1 → 第 45 行判断逾期并抛错。数据对象是 store 里的同一份引用，所以次数的改动会保留。复现：逾期续借被拒后，`renew_count` 为 1，到期日仍为 11-01。第 43 行的上限拒绝也有同样的问题（次数已经加上去了）。
- 影响：读者因逾期或达到上限而被拒绝的每一次尝试，都会消耗一次续借额度。之后真正合法的续借可能因为次数已被占用而被提前拒绝，同时次数字段不再代表真实续借次数。
- 怎么改：把次数加 1 挪到所有校验通过之后、改到期日的同时进行。同时补一条“逾期被拒后次数不变”的测试。

### B3: 查借阅记录可以指定别的读者（越权）

- 规则：loan:feat02-场景1
- 位置：`src/library/loan.py` 的 `list_loans()`，第 53 行（`member_id = request.get("member_id", session_member_id)`）
- 反例：GIVEN 读者 10 已登录（会话 `session_member_id=10`）WHEN 请求参数带 `member_id=20` THEN 只返回读者 10 的借阅；实际返回读者 20 的借阅《活着》
- 证据：代码路径为入口 `list_loans()` → 第 53 行优先取客户端参数 `request["member_id"]` → 第 54 行按该值查询。文件说明里写着 `session_member_id` 来自登录会话，`request` 是客户端传来的参数，但代码仍信了客户端。复现结果见上文。现有测试只用空请求 `{}`，所以没有抓住这个错误。
- 影响：任何已登录的读者都能看到其他读者的全部借阅记录，属于隔离被突破。
- 怎么改：查询只用 `session_member_id`，不读取 `request["member_id"]`。补一条测试：会话是读者 10、请求带 `member_id=20` 时，只返回读者 10 的借阅。

## 原因排查

本次是检查代码模式，不是查已知现象，因此不写原因排查表。

## 结论

- 最严重的问题：B3，查借阅时客户端可以指定 member_id，读者能看到别人的借阅记录（P0）。
- spec 要补的规则：无。上面三条都能从现有 spec 的 C1、D01、feat02 直接判断。

本次统计：P0 1 条（B3），P1 2 条（B1、B2），P2 0 条。
