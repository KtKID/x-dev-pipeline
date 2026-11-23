# CR 报告：预约功能（reserve.py、api.py）是否符合 spec

> 时间：2026-11-23 04:13
> 模式：检查代码
> 范围：src/library/reserve.py、src/library/api.py（测试 tests/test_reserve.py）
> spec：docs/spec/reserve/spec.md（无 tech-design.md）

## 范围

- 现象或检查目标：检查预约功能是否符合 spec；用户要求只查不改代码。用户另说明：预约上限已改为 5 本。
- 期望：spec 写的是 C1「每位读者同时最多预约 3 本」；feat01 场景1「有库存的书不能预约，抛 AvailableError」；feat02 场景1「只能取消自己的预约，抛 PermissionError」。
- 实际：代码里 `MAX_RESERVATIONS = 5`（reserve.py 第 4 行）；`reserve()` 不检查库存，`AvailableError` 定义了却从未被抛出（reserve.py 第 11–12 行）；取消归属检查在 api.py 第 13–14 行。
- 看了哪些代码：
  - src/library/reserve.py（reserve、cancel_reservation、ReserveStore）
  - src/library/api.py（api_reserve、api_cancel）
  - src/library/__init__.py（空文件）
  - tests/test_reserve.py（2 条测试）
  - docs/spec/reserve/spec.md

跑过的命令：`python3 -m pytest -q` 结果 2 passed。另用临时脚本（不写入项目）验证：库存为 2 的书，读者直接预约成功；同一读者可预约 5 本，第 6 本抛 ReserveLimitError。

## 规则表

| 编号 | 规则 | 来源 | 最小反例 | 结论 | 问题 |
|---|---|---|---|---|---|
| reserve:C1 | 每位读者同时最多预约 3 本 | spec.md 关键约束 C1（用户 2026-09-01 确认）；代码 reserve.py 第 4 行为 5；用户口头说“已改成 5 本” | GIVEN 读者已有 3 个有效预约 WHEN 再预约 THEN 按 spec 应抛 ReserveLimitError；按代码则允许，直到 5 本才拒绝 | 来源不一 | B2 |
| reserve:feat01-场景1 | 有库存的书不能预约，抛 AvailableError | spec.md feat01 场景1 | GIVEN 书在馆、有可借副本（库存 2） WHEN 读者预约 THEN 应拒绝并抛 AvailableError；实际生成了一条预约（rid=1） | 被打破 | B1 |
| reserve:feat01-场景2 | 没库存时预约成功 | spec.md feat01 场景2 | GIVEN 库存为 0 WHEN 读者预约 THEN 生成一条预约 | 守住了 | - |
| reserve:feat02-场景1 | 只能取消自己的预约，越权抛 PermissionError 且预约保留 | spec.md feat02 场景1 | GIVEN 读者 A(10) 有预约 WHEN 读者 B(20) 调 api_cancel THEN 抛 PermissionError，预约仍在 | 守住了 | - |
| 新1 | 预约人身份只能来自登录会话，客户端传的其他人 id 不能让别人替他预约 | spec 没写；src/library/api.py 第 1、5–6 行的 docstring 和参数 `session_member_id` | GIVEN 请求携带他人 member_id WHEN 调 api_reserve THEN 应拒绝或忽略 | 没法验证 | B3 |
| 新2 | 预约被拒绝时不留下半截数据 | spec 没写；reserve.py 第 33–37 行（校验在写入之前） | GIVEN 已达上限 WHEN 再预约 THEN 不新增 items 记录 | 守住了 | - |

## 问题

| ID | 严重度 | 状态 | 位置 | 一句话 |
|---|---|---|---|---|
| B1 | P1 | 待修 | `src/library/reserve.py` 的 `reserve()`，第 32–38 行（`AvailableError` 定义在第 11–12 行，从未被抛出） | 有库存的书也能被预约，spec 要求直接拒绝 |
| B2 | P2 | 待修 | `docs/spec/reserve/spec.md` 的 C1 与 `src/library/reserve.py` 第 4 行 | 预约上限来源不一：spec 写 3 本，代码与用户口头说法是 5 本 |
| B3 | P2 | 待修 | `src/library/api.py` 的 `api_reserve()`，第 5–6 行 | 没法验证 `session_member_id` 一定来自服务端登录会话，本次范围内看不到调用方 |

### B1: 有库存的书也能被预约

- 规则：reserve:feat01-场景1
- 位置：`src/library/reserve.py` 的 `reserve()`，第 32–38 行；`AvailableError` 定义在第 11–12 行
- 反例：GIVEN 书 “三体” 库存为 2 WHEN 读者 10 调 `api_reserve(store, 10, "三体")` THEN 应抛 AvailableError；实际返回一条预约（rid=1）
- 证据：入口 `api_reserve`（api.py 第 6 行）→ `reserve()` 只检查读者预约数（第 33–34 行）→ 直接写入 `store.items`（第 35–36 行）。`copies_available` 在 `ReserveStore.__init__` 中保存（第 23–24 行），但 `reserve()` 从未读取。全仓库 grep 结果：`AvailableError` 只有定义，没有 raise。临时脚本已复现。现有测试 `test_reserve_when_all_out` 只测没库存的情况，测不出这个问题。
- 影响：读者可以预约在馆的书，预约记录多出来，库存和预约的状态不一致。
- 怎么改：在写入预约前检查该书是否有可借副本，有则抛 AvailableError；补一条“有库存时预约被拒”的测试。（用户要求先不改代码，此处只给方向。）

### B2: 预约上限来源不一

- 规则：reserve:C1
- 位置：`docs/spec/reserve/spec.md` 的「关键约束」C1；`src/library/reserve.py` 第 4 行 `MAX_RESERVATIONS = 5`
- 反例：GIVEN 读者已有 3 个有效预约 WHEN 再预约 THEN spec 说应抛 ReserveLimitError；代码允许，直到第 5 本才拒绝
- 证据：spec.md C1 原文写「每位读者同时最多预约 3 本」（确认依据「用户 2026-09-01」）；reserve.py 第 4 行为 `MAX_RESERVATIONS = 5`；用户本轮原话是“预约上限我们早就改成 5 本了”；tests/test_reserve.py 没有覆盖上限，测试对此不作判断。两处来源说法不同，按规则不替用户判断。
- 影响：如果 5 才是现行规定，spec 的 C1 是过时的，之后按 spec 验收会误判；如果 3 才是规定，代码就是错的，读者能多借 2 本。
- 怎么改：请用户确认现行上限是 3 还是 5。若是 5，更新 spec 的 C1 并补一条上限测试；若是 3，把 `MAX_RESERVATIONS` 改回 3 并补测试。

### B3: 预约人身份的服务端来源没法验证

- 规则：新1
- 位置：`src/library/api.py` 的 `api_reserve()`，第 5–6 行（参数 `session_member_id`）
- 反例：GIVEN 调用方传入 member_id 与登录会话不一致 WHEN 调 `api_reserve` THEN 应拒绝；本次范围内无法判断
- 证据：`api_reserve` 直接把传入的 `session_member_id` 当作预约人（第 6 行）；api.py 第 1 行 docstring 说它“来自登录会话”，但这一层的赋值不在本次范围内。`api_cancel` 有归属检查（第 13–14 行），这部分是守住的。
- 影响：如果上层把客户端传来的 id 直接当 session_member_id 用，就能替别人预约。
- 怎么改：查看调用 `api_reserve` 的上层（路由或中间件），确认该值只由服务端登录会话取得。这需要读调用方代码，本次范围外，所以只能算没法验证。问题要问项目负责人。P2，不改代码。

## 结论

- 最严重的问题：B1，有库存的书也能被预约（P1），与 spec feat01 场景1 冲突，测试没有覆盖。
- spec 要补的规则：新1（预约人身份只来自登录会话，spec 没写，建议补进 spec）。另外 C1 的上限数字需要用户确认后修正 spec 或代码（见 B2）。
