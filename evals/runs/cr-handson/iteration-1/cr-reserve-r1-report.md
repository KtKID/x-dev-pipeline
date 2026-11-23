# CR 报告：预约功能（reserve.py、api.py）的正确性检查

> 时间：2026-11-23 04:13
> 模式：检查代码
> 范围：src/library/reserve.py、src/library/api.py（及其测试 tests/test_reserve.py）
> spec：docs/spec/reserve/spec.md / 无 tech-design.md

## 范围

- 现象或检查目标：检查预约功能是否符合 spec；用户说明预约上限已从 3 本改为 5 本。本次只出报告，不改代码、不改 spec。
- 期望：spec C1 写“每位读者同时最多预约 3 本”；feat01 场景1 写“有库存的书不能预约，拒绝并抛 AvailableError”；feat02 场景1 写“只能取消自己的预约”。
- 实际：reserve.py 中 `MAX_RESERVATIONS = 5`；`reserve()` 不检查库存，`AvailableError` 定义后从未被抛出；`api_cancel()` 有归属校验。
- 看了哪些代码：src/library/reserve.py（reserve、cancel_reservation、ReserveStore）；src/library/api.py（api_reserve、api_cancel）；tests/test_reserve.py；docs/spec/reserve/spec.md。
- 跑过的命令：`python3 -m pytest -q` 结果 2 passed；用 `python3 -I` 直接调用 api_reserve 做最小反例复现（结果见 B1 证据）。

## 规则表

| 编号 | 规则 | 来源 | 最小反例 | 结论 | 问题 |
|---|---|---|---|---|---|
| reserve:C1 | 每位读者同时最多预约 3 本 | spec.md 关键约束 C1（用户 2026-09-01 确认）；代码 reserve.py 的 `MAX_RESERVATIONS = 5` | GIVEN 读者已有 5 个预约 WHEN 再预约 THEN spec 要求拒绝，代码放行到 5 为止 | 来源不一 | B2 |
| reserve:feat01-场景1 | 有库存的书不能预约，拒绝并抛 AvailableError | spec.md feat01 场景1 | GIVEN 书 `三体` 有 2 本可借副本 WHEN 读者 10 调用 api_reserve THEN 应拒绝抛 AvailableError；实际返回了一条预约（rid=1） | 被打破 | B1 |
| reserve:feat01-场景2 | 没库存时预约成功 | spec.md feat01 场景2 | GIVEN 副本数为 0 WHEN 读者预约 THEN 生成一条预约 | 守住了 | - |
| reserve:feat02-场景1 | 只能取消自己的预约，越权抛 PermissionError 且预约还在 | spec.md feat02 场景1 | GIVEN 读者 10 的预约 WHEN 读者 20 调用 api_cancel THEN 抛 PermissionError 且预约仍在 | 守住了 | - |
| 新1 | 服务端不信客户端：预约和取消的主体只能来自登录会话 | spec 没写；src/library/api.py 文件头注释“session_member_id 来自登录会话” | 调用方传入的 session_member_id 是否真来自登录，本次范围内看不到会话层代码 | 没法验证 | B3 |
| 新2 | `cancel_reservation()` 不做归属校验，只能由已核对归属的调用方调用 | spec 没写；src/library/reserve.py 的 `cancel_reservation()` 文档串“调用方负责先核对归属” | 外部直接调用 cancel_reservation 可删他人预约 | 没走到 | - |

没走到的依据（新2）：reserve.py 文件头写明“只由 api.py 调用，不直接对外”；本范围内 api.py 的 `api_cancel()` 先核对归属再调用，外部入口走不到这条路径。

## 问题

| ID | 严重度 | 状态 | 位置 | 一句话 |
|---|---|---|---|---|
| B1 | P1 | 待修 | `src/library/reserve.py` 的 `reserve()`；`src/library/api.py` 的 `api_reserve()` | 有可借副本的书也能预约成功，AvailableError 从未被抛出 |
| B2 | P2 | 待修 | `src/library/reserve.py` 的 `MAX_RESERVATIONS`（第 4 行）；`docs/spec/reserve/spec.md` C1 | 预约上限：spec 写 3 本，代码与用户口头说法是 5 本，需用户定 |
| B3 | P2 | 待修 | `src/library/api.py` 的 `api_reserve()`、`api_cancel()` | 服务端是否真从登录会话取 member_id，本范围内没有证据 |

### B1: 有库存的书也能预约成功

- 规则：reserve:feat01-场景1
- 位置：`src/library/reserve.py` 的 `reserve()`，第 32–38 行；入口 `src/library/api.py` 的 `api_reserve()`
- 反例：GIVEN 书 `三体` 在 `ReserveStore({"三体": 2})` 中有 2 本可借副本 WHEN 读者 10 调用 `api_reserve(store, 10, "三体")` THEN 应抛 AvailableError；实际返回 `Reservation(rid=1, member_id=10, book='三体')`。
- 证据：代码路径 api_reserve → reserve：只检查 `MAX_RESERVATIONS`，然后直接生成预约并写入 `store.items`，全文没有读取 `store.copies_available`；`AvailableError` 在 reserve.py 中定义（第 11 行）但没有任何地方抛出。用 `python3 -I` 复现，输出“有库存仍预约成功”。现有测试 `test_reserve_when_all_out` 只覆盖“无库存可预约”，测不到这条路径。
- 影响：读者可以对能直接借的书占用预约名额，还会得到一条本不该有的预约；错误不报出来，接口返回成功。
- 怎么改：在 `reserve()` 中先检查 `store.copies_available[book] > 0`，有库存时抛 AvailableError；并补一条“有库存时抛 AvailableError 且不生成预约”的测试。（只出方向，本轮不改代码。）

### B2: 预约上限 3 本还是 5 本，来源不一

- 规则：reserve:C1
- 位置：`src/library/reserve.py` 的 `MAX_RESERVATIONS`，第 4 行；`docs/spec/reserve/spec.md` 关键约束 C1
- 反例：GIVEN 读者已有 5 个有效预约 WHEN 再调用 `api_reserve` THEN spec 的判据是“已有 3 个有效预约时再预约，抛 ReserveLimitError”，代码在第 5 个之后才拒绝（已验证：第 6 次预约抛 ReserveLimitError）。两边对不上。
- 证据：spec.md C1 原文“每位读者同时最多预约 3 本”，确认依据“用户 2026-09-01”；reserve.py 原文 `MAX_RESERVATIONS = 5`；用户本次说明“预约上限我们早就改成 5 本了”；git 仓库只有一个 base 提交，看不出 5 何时改的，spec 也没有随之更新。
- 影响：如果用户说的 5 本是真的，spec 的约束和 C1 的判据都过时，之后的验收会拿错的数字判；如果 3 本才是定下的规则，代码就是错的。
- 怎么改：不自己判。请用户确认上限是 3 还是 5。确认 5 本的话，改 spec C1 和判据（由用户或 x-ask-spec 同步）；确认 3 本的话，改 `MAX_RESERVATIONS` 并让测试覆盖上限。

### B3: 服务端身份来源没有证据

- 规则：reserve:新1
- 位置：`src/library/api.py` 的 `api_reserve()`、`api_cancel()`，参数 `session_member_id`
- 反例：GIVEN 客户端在请求里伪造 member_id WHEN 调用 `api_cancel` THEN 应由服务端从会话推出的主体决定；本范围内 `session_member_id` 作为普通参数传入，谁来填它看不到。
- 证据：api.py 文件头注释“session_member_id 来自登录会话”，但这一层只接收参数，没有读取会话的代码。测试直接传入整数。
- 影响：如果上层把客户端字段直接当 session_member_id 传入，越权取消和代订都会发生。本范围内无法确认。
- 怎么改：补看调用 api_* 的上层（路由或中间件）如何取 session_member_id；如果用的是请求体字段，按 P0 重新判。本轮不改代码。

## 结论

- 最严重的问题：B1，有库存的书仍可预约（P1，已用最小反例复现）。
- spec 要补的规则：新1（服务端从会话取主体，spec 没写，建议补进 spec 关键约束）。
- 需要用户定的：B2，预约上限 3 还是 5。spec 里 C1 仍写 3 本，所以本报告按“来源不一”处理，没有改 spec 或代码。
