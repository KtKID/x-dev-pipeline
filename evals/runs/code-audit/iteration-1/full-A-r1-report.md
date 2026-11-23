# 代码巡检报告 · f65d922f
<!-- x-code-audit:{"files": ["src/library/__init__.py", "src/library/api/__init__.py", "src/library/api/views.py", "src/library/db/__init__.py", "src/library/db/store.py", "src/library/loan/__init__.py", "src/library/loan/loan.py", "src/library/notify/__init__.py", "src/library/notify/mailer.py", "tests/test_library.py"], "modules": ["src/library/api", "src/library/db", "src/library/loan", "src/library/notify"], "doc_modules": ["src/library/api", "src/library/db", "src/library/loan", "src/library/notify"], "prev": null} -->

> 检查 ID：f65d922f
> 开始时间：2026-11-23 08:28
> 状态：完成
> 代码版本：307b0d0
> 上次巡检：无
> 范围：全量（第一次巡检）
> 层：L1、L2、L3、L4、L5、L6

## 范围

- 模块（4 个）：src/library/api、src/library/db、src/library/loan、src/library/notify
- 文件：10 个，清单在「检查进度」下面

## 结论

| 层 | 结果 | 问题数 |
|---|---|---|
| L1 机器检查 | 有问题 | 6（A13–A18） |
| L2 死代码 | 有问题 | 5（A19–A23） |
| L3 文档对代码 | 有问题 | 5（A1–A3、A24–A25） |
| L4 模块审查 | 有问题 | 6（A4–A6、A26–A28） |
| L5 架构审查 | 有问题 | 4（A7–A10） |
| L6 性能 | 有问题 | 3（A11、A12、A29） |

共 29 条问题：P0 有 0 条，P1 有 12 条（A1–A12），P2 有 17 条（A13–A29）。没有 P0。

最严重的问题：A4（发信失败也返回成功，续借通知可能静默丢失），其次是 A12（读者列表对每个读者各查一次借阅表，读者一多就明显变慢）和 A10（续借上限在两处定义且值不同，列表页显示的上限和实际拦截的不一致）。

注意：A1 与 A3、A24 与 A25 说的是同一件事，分别由脚本（L3）和子 agent（U15）各报一次，修的时候只改一处即可。A8 的循环依赖只出现在 `TYPE_CHECKING` 下的类型标注里，运行时不会成环，严重度可按实际情况下调。

## 问题

### A1 · P1 · L3 · 说明里写的函数 extend_loan() 不存在

- 是什么：`src/library/loan/readme.md` 第 11 行提到函数 `extend_loan()`，但模块代码里找不到这个函数。
- 影响：照着说明去调用会失败，读者会以为模块有这个能力。
- 位置：`src/library/loan/readme.md`，第 11 行
- 证据：在 src/library/loan/ 的代码里搜不到 `extend_loan` 的定义
- 怎么改：用 x-feat-doc 按现在的代码重写这一节
- 来源：U3

### A2 · P1 · L3 · 说明里 RENEW_DAYS 的默认值写错了

- 是什么：`src/library/loan/readme.md` 第 15 行说 `RENEW_DAYS` 默认是 `21`，代码里实际是 `14`。
- 影响：照着说明理解的人会以为是另一个值，配置和排查都会出错。
- 位置：`src/library/loan/readme.md`，第 15 行
- 证据：代码：RENEW_DAYS = 14
- 怎么改：用 x-feat-doc 按代码更新默认值
- 来源：U3

### A3 · P1 · L3 · 说明让人用 extend_loan() 一次延长多次，但这个函数不存在

- 是什么：说明写“要一次延长多次，用 `extend_loan()`”，但 `loan.py` 里没有这个函数。照着说明调用，会直接报错。
- 影响：读者会以为模块能一次延长多次，照做就失败；排查的人也会白找一遍。
- 位置：`src/library/loan/readme.md` 第 11 行
- 证据：第 11 行原文提到 `extend_loan()`；`src/library/loan/` 和整个 `src` 里搜不到 `extend_loan` 的定义。
- 怎么改：用 x-feat-doc 按现在的代码重写“使用方式”这一节，只写真实存在的入口。
- 来源：U15

### A4 · P1 · L4 · 发信失败也报告成功

- 是什么：`send()` 把所有异常用 `except Exception` 吞掉，然后返回 `True`。收件人地址不带 @ 时，先抛出 `ValueError`，又被同一个 `except` 吞掉，还是返回 `True`，邮件其实没有发出去。
- 影响：读者收不到续借通知，续借逻辑却拿到“发送成功”，没有任何地方能发现邮件没发出去。
- 位置：`src/library/notify/mailer.py` 的 `send()`，第 19–20 行
- 证据：第 15–16 行地址不对就 `raise ValueError`；第 19–20 行 `except Exception:` 后 `return True`；`src/library/loan/loan.py` 第 27 行调用 `mailer.send(...)` 时没有检查返回值。
- 怎么改：失败时返回 `False` 或直接抛出异常；`except` 里不要返回成功；调用方要检查返回值。
- 来源：U11

### A5 · P1 · L4 · 表名写错时查询静默返回空列表

- 是什么：`query()` 用 `self.rows.get(table, [])` 取表，表名写错或表不存在时，直接当成空表返回，不报任何错。
- 影响：调用方拿到的是“没有数据”，分不清是真的没有还是写错了表名；列表、统计会悄悄显示成 0，没人会发现。
- 位置：`src/library/db/store.py` 的 `query()`，第 12 行
- 证据：第 12 行 `return [r for r in self.rows.get(table, []) if all(...)]`，没有对表名是否存在做任何检查。
- 怎么改：表不存在时直接抛出异常（比如 `KeyError`），不要用默认空列表掩盖。
- 来源：U7

### A6 · P1 · L4 · 测试只断言邮件被调用，续借结果没有被检查

- 是什么：`test_renew_sends_mail()` 只检查 `send.called` 为真，没有检查到期日是否延长、次数是否加一、超过上限是否报错。
- 影响：改坏 `RENEW_DAYS` 的用法或删掉次数加一的那行，测试照样全部通过；续借出错时没人会知道，测试看着是绿的。
- 位置：`tests/test_library.py` 的 `test_renew_sends_mail()`，第 13–16 行
- 证据：第 16 行 `assert send.called` 是唯一的断言；`tests/test_library.py` 里没有任何地方检查 `due` 或 `renew_count`。
- 怎么改：补断言：续借后 `due` 增加 `RENEW_DAYS` 天、`renew_count` 为 1；再续到上限后应抛出 `ValueError`。
- 来源：U9

### A7 · P1 · L5 · 循环依赖：views.py 和 store.py 互相引用

- 是什么：这几个文件互相 import，形成一个环：`src/library/api/views.py` → `src/library/db/store.py` → `src/library/api/views.py`。
- 影响：改其中一个就可能牵动另一个，测试也没法单独测；启动顺序稍有变化还可能直接报导入错误。
- 位置：`src/library/api/views.py`
- 证据：依赖路径：src/library/api/views.py → src/library/db/store.py → src/library/api/views.py
- 怎么改：把两边共用的部分抽到第三个模块，让依赖只朝一个方向
- 来源：U4

### A8 · P1 · L5 · 循环依赖：loan.py 和 mailer.py 互相引用

- 是什么：这几个文件互相 import，形成一个环：`src/library/loan/loan.py` → `src/library/notify/mailer.py` → `src/library/loan/loan.py`。
- 影响：改其中一个就可能牵动另一个，测试也没法单独测；启动顺序稍有变化还可能直接报导入错误。
- 位置：`src/library/loan/loan.py`
- 证据：依赖路径：src/library/loan/loan.py → src/library/notify/mailer.py → src/library/loan/loan.py
- 怎么改：把两边共用的部分抽到第三个模块，让依赖只朝一个方向
- 来源：U4

### A9 · P1 · L5 · 下层依赖了上层：store.py → views.py

- 是什么：`src/library/db/store.py` 属于下层，却 import 了上层的 `src/library/api/views.py`。
- 影响：分层被打破后，改上层会牵动下层，越改越乱。
- 位置：`src/library/db/store.py`
- 证据：src/library/db/store.py import src/library/api/views.py
- 怎么改：把需要的东西移到下层，或改成由上层把数据传下来
- 来源：U4

### A10 · P1 · L5 · 续借上限写了两遍，值还不一样

- 是什么：续借上限 `MAX_RENEWALS` 在两个地方各定义了一次，值分别是 3 和 2。真正拦住续借的是 `loan.py` 的 2，而列表页显示的上限却是 `views.py` 的 3。
- 影响：列表页告诉读者还能续借，实际续借时会被拒绝（或反过来）；读者和管理员看到的数字对不上，遇到问题也很难查。
- 位置：`src/library/api/views.py` 第 11 行
- 证据：`views.py` 第 11 行 `MAX_RENEWALS = 3`，第 20 行 `"max": MAX_RENEWALS` 把它返回给列表页；`loan.py` 第 7 行 `MAX_RENEWALS = 2`，第 23 行 `if loan.renew_count >= MAX_RENEWALS` 用的是它。
- 怎么改：只保留 `loan.py` 里的一处定义，`views.py` 从 `library.loan.loan` 导入它。
- 来源：U13

### A11 · P1 · L6 · 已发邮件记录只增不减，一直占着内存

- 是什么：`SENT` 是模块级的列表，每发一封就往里加一条（收件人，内容），从来不清空，也没有上限。
- 影响：服务一直运行时，发的邮件越多，内存占得越多，最后会拖慢进程，甚至把它撑爆；平时没人会注意到，直到出事。
- 位置：`src/library/notify/mailer.py` 的 `send()`，第 17 行
- 证据：第 9 行 `SENT: list[tuple[str, str]] = []`，第 17 行 `SENT.append((to, text))`；`src` 里没有任何地方清空、截断或读取 `SENT`。
- 怎么改：不需要留痕的话就删掉这个列表；需要留痕的话写进持久化的日志，或者设上限。
- 来源：U12

### A12 · P1 · L6 · 读者列表对每个读者各查一次借阅表

- 是什么：`member_page()` 先取出所有读者，然后在循环里，每个读者都单独调用一次 `db.query("loans", ...)` 去查借阅表。
- 影响：读者一多，打开列表页要查库几百上千次（也就是常说的 N+1 问题），每次查询都要扫一遍借阅表，页面会明显变慢。
- 位置：`src/library/api/views.py` 的 `member_page()`，第 18–20 行
- 证据：第 18 行 `for member in db.query("members")`，第 19 行在循环里 `loans = db.query("loans", member_id=member["id"])`；`src/library/db/store.py` 的 `query()` 每次调用都会从头扫一遍表。
- 怎么改：循环前一次性取出所有借阅，按 member_id 分组，循环里只读内存里的结果。
- 来源：U6

### A13 · P2 · L1 · 缺少 lint 规则：命名规范（ruff N）

- 是什么：项目没有配置「命名规范（ruff N）」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：在 ruff 的 select 里加上 "N"
- 来源：U1

### A14 · P2 · L1 · 缺少 lint 规则：函数太复杂（ruff C90）

- 是什么：项目没有配置「函数太复杂（ruff C90）」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：在 ruff 的 select 里加上 "C90"，并设 max-complexity
- 来源：U1

### A15 · P2 · L1 · ruff 报了 2 处问题

- 是什么：跑 ruff，有 2 处不过。
- 影响：代码规范不统一，越积越难改。
- 位置：`src/library/api/views.py`，第 4 行
- 证据：src/library/api/views.py:4:8: F401 [*] `json` imported but unused；src/library/loan/loan.py:46:40: E741 Ambiguous variable name: `l`
- 怎么改：按 ruff 的提示逐条改
- 来源：U1

### A16 · P2 · L1 · 缺少 lint 规则：CI 里跑 ruff

- 是什么：项目没有配置「CI 里跑 ruff」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：在 CI（如 .github/workflows/ci.yml）里加一步 `ruff check .`
- 来源：U1

### A17 · P2 · L1 · 缺少 lint 规则：Python 类型检查（mypy）

- 是什么：项目没有配置「Python 类型检查（mypy）」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：加 [tool.mypy]
- 来源：U1

### A18 · P2 · L1 · 缺少 lint 规则：Python 格式化（black 或 ruff format）

- 是什么：项目没有配置「Python 格式化（black 或 ruff format）」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：加 [tool.black]，或在 CI 跑 `ruff format --check`
- 来源：U1

### A19 · P2 · L2 · 函数 member_page 只有测试在用

- 是什么：生产代码里没有任何地方用到 函数 `member_page`，只有测试在调用它。
- 影响：它和它的测试一起白白占着维护成本，读代码的人还会以为它在起作用。
- 位置：`src/library/api/views.py` 的 `member_page()`，第 15 行
- 证据：全项目非测试代码引用 0 处，测试引用 2 处
- 怎么改：确认没用后连同测试一起删掉
- 来源：U2

### A20 · P2 · L2 · 函数 week_header 没人用

- 是什么：全项目找不到任何地方用到 函数 `week_header`。
- 影响：没人用的代码会让人误以为它在起作用，改相关逻辑时还得顺带看它。
- 位置：`src/library/api/views.py` 的 `week_header()`，第 24 行
- 证据：全项目引用 0 处（含测试、字符串）
- 怎么改：删掉
- 来源：U2

### A21 · P2 · L2 · 函数 dispatch 只有测试在用

- 是什么：生产代码里没有任何地方用到 函数 `dispatch`，只有测试在调用它。
- 影响：它和它的测试一起白白占着维护成本，读代码的人还会以为它在起作用。
- 位置：`src/library/loan/loan.py` 的 `dispatch()`，第 37 行
- 证据：全项目非测试代码引用 0 处，测试引用 1 处
- 怎么改：确认没用后连同测试一起删掉
- 来源：U2

### A22 · P2 · L2 · 函数 old_fine_rate 没人用

- 是什么：全项目找不到任何地方用到 函数 `old_fine_rate`。
- 影响：没人用的代码会让人误以为它在起作用，改相关逻辑时还得顺带看它。
- 位置：`src/library/loan/loan.py` 的 `old_fine_rate()`，第 41 行
- 证据：全项目引用 0 处（含测试、字符串）
- 怎么改：删掉
- 来源：U2

### A23 · P2 · L2 · 函数 legacy_export 只有测试在用

- 是什么：生产代码里没有任何地方用到 函数 `legacy_export`，只有测试在调用它。
- 影响：它和它的测试一起白白占着维护成本，读代码的人还会以为它在起作用。
- 位置：`src/library/loan/loan.py` 的 `legacy_export()`，第 45 行
- 证据：全项目非测试代码引用 0 处，测试引用 1 处
- 怎么改：确认没用后连同测试一起删掉
- 来源：U2

### A24 · P2 · L3 · 说明里的链接失效：../../../docs/spec/loan/spec.md

- 是什么：`src/library/loan/readme.md` 第 24 行的链接 `../../../docs/spec/loan/spec.md` 打不开（找不到）。
- 影响：读者点进去什么也找不到，只能自己翻代码。
- 位置：`src/library/loan/readme.md`，第 24 行
- 证据：目标 ../../../docs/spec/loan/spec.md 找不到
- 怎么改：用 x-feat-doc 更新这一节的链接
- 来源：U3

### A25 · P2 · L3 · spec 索引的链接指向不存在的文件

- 是什么：说明末尾的 spec 链接指向 `docs/spec/loan/spec.md`，这个文件在项目里找不到，读者点进去什么也看不到。
- 影响：想看续借规则正式定义的人找不到入口，只能自己翻代码猜规则。
- 位置：`src/library/loan/readme.md` 第 24 行
- 证据：第 24 行链接 `../../../docs/spec/loan/spec.md`；项目副本里没有 `docs/` 目录。
- 怎么改：用 x-feat-doc 更新这一节，指向真实存在的 spec，或在 spec 落地后补上。
- 来源：U15

### A26 · P2 · L4 · 接口层文件里混着和读者列表无关的表头函数

- 是什么：`views.py` 的说明写的是“读者列表页”，但 `week_header()` 算的是一周七天的表头，和读者列表没有关系。
- 影响：读这个文件的人会以为表头也是列表页的一部分；以后改列表页时，容易去顾虑一个根本没人用的函数。
- 位置：`src/library/api/views.py` 的 `week_header()`，第 24–33 行
- 证据：`week_header()` 只用到 `WEEKDAYS`，文件里别的地方不调用它；L2 巡检已在 A13 报过它 0 引用。
- 怎么改：删掉 `week_header()` 和只被它用的 `WEEKDAYS`；如果以后要用，搬到真正用它的地方。
- 来源：U5

### A27 · P2 · L4 · 续借函数里顺带发邮件、写日志文件

- 是什么：`renew()` 除了续借，还调用 `mailer.send()` 发通知，又往 `/tmp/renew.log` 写一行日志，三件事写在同一个函数里。
- 影响：以后改通知方式或日志位置，都要动续借的代码，容易把续借改坏；测续借时也得先准备好邮件和日志环境。
- 位置：`src/library/loan/loan.py` 的 `renew()`，第 21–30 行
- 证据：第 27 行 `mailer.send(loan.member_email, mailer.renew_notice(loan))`，第 28–29 行 `open("/tmp/renew.log", "a", ...)`。
- 怎么改：让 `renew()` 只改到期日和次数，把发通知和写日志挪到调用它的地方，或由通知模块订阅续借事件。
- 来源：U9

### A28 · P2 · L4 · renew() 会原地改传入的借阅对象，签名里看不出来

- 是什么：`renew()` 直接修改传进来的 `Loan` 对象的 `renew_count` 和 `due`，同时又返回这个对象；另外还会发邮件。这些副作用只在函数体里能看到。
- 影响：调用方如果以为传入的对象没变，就会拿着旧的到期日去做别的事；多次调用时还可能重复发邮件。
- 位置：`src/library/loan/loan.py` 的 `renew()`，第 21–22 行
- 证据：第 22 行 docstring 只写“续借一次，并通知读者”，没有说会修改传入对象；第 25–26 行直接赋值给 `loan.renew_count` 和 `loan.due`。
- 怎么改：在说明里写清会改传入对象、会发邮件；或者改成返回新对象，不改原对象。
- 来源：U9

### A29 · P2 · L6 · 每次查询都从头扫整张表，没有索引

- 是什么：`query()` 每次都把整张表从头扫到尾再过滤，没有按字段建的索引。
- 影响：数据一多，每次查询的耗时都跟着变长；加上 U6 那种循环查法，耗时会一次次乘上去。现在数据少，看不出来。
- 位置：`src/library/db/store.py` 的 `query()`，第 12 行
- 证据：第 12 行 `[r for r in self.rows.get(table, []) if all(r.get(k) == v for k, v in where.items())]`，每次都遍历整张表。
- 怎么改：对常用来查的字段建一个“字段值到行列表”的字典，查询时直接取，不扫全表。
- 来源：U8

## 检查进度

| 单位 | 层 | 范围 | 谁查 | 状态 |
|---|---|---|---|---|
| U1 | L1 | 范围内全部文件 | 脚本 | 完成 |
| U2 | L2 | 范围内全部文件 | 脚本 | 完成 |
| U3 | L3 | 范围内模块的说明 | 脚本 | 完成 |
| U4 | L5 | 范围内全部文件 | 脚本 | 完成 |
| U5 | L4 | src/library/api | 子 agent | 完成 |
| U6 | L6 | src/library/api | 子 agent | 完成 |
| U7 | L4 | src/library/db | 子 agent | 完成 |
| U8 | L6 | src/library/db | 子 agent | 完成 |
| U9 | L4 | src/library/loan | 子 agent | 完成 |
| U10 | L6 | src/library/loan | 子 agent | 完成 |
| U11 | L4 | src/library/notify | 子 agent | 完成 |
| U12 | L6 | src/library/notify | 子 agent | 完成 |
| U13 | L5 | src/library/api、src/library/db、src/library/loan、src/library/notify | 子 agent | 完成 |
| U14 | L2 | 拿不准的候选 2 个 | 子 agent | 完成 |
| U15 | L3 | src/library/loan | 子 agent | 完成 |

范围内的文件：`src/library/__init__.py`、`src/library/api/__init__.py`、`src/library/api/views.py`、`src/library/db/__init__.py`、`src/library/db/store.py`、`src/library/loan/__init__.py`、`src/library/loan/loan.py`、`src/library/notify/__init__.py`、`src/library/notify/mailer.py`、`tests/test_library.py`

## 检查记录

### U1 · L1 机器检查

找到的工具：
| 工具 | 配置 |
|---|---|
| ruff | pyproject.toml |

缺的规则：
| 规则 | 该配在哪 | 怎么配 |
|---|---|---|
| 命名规范（ruff N） | pyproject.toml | 在 ruff 的 select 里加上 "N" |
| 函数太复杂（ruff C90） | pyproject.toml | 在 ruff 的 select 里加上 "C90"，并设 max-complexity |
| CI 里跑 ruff | pyproject.toml | 在 CI（如 .github/workflows/ci.yml）里加一步 `ruff check .` |
| Python 类型检查（mypy） | pyproject.toml | 加 [tool.mypy] |
| Python 格式化（black 或 ruff format） | pyproject.toml | 加 [tool.black]，或在 CI 跑 `ruff format --check` |

跑过的命令：
| 工具 | 命令 | 退出码 | 报错条数 |
|---|---|---|---|
| ruff | ruff check --output-format=concise … | 1 | 2 |

### U2 · L2 死代码

| 名字 | 类型 | 位置 | 结论 |
|---|---|---|---|
| member_page | 函数 | `src/library/api/views.py` 的 `member_page()`，第 15 行 | 只有测试在用（2 处） |
| week_header | 函数 | `src/library/api/views.py` 的 `week_header()`，第 24 行 | 确认没用（0 引用） |
| renew | 函数 | `src/library/loan/loan.py` 的 `renew()`，第 21 行 | 拿不准：名字出现在字符串里 |
| handle_overdue | 函数 | `src/library/loan/loan.py` 的 `handle_overdue()`，第 33 行 | 拿不准：名字出现在字符串里 |
| dispatch | 函数 | `src/library/loan/loan.py` 的 `dispatch()`，第 37 行 | 只有测试在用（1 处） |
| old_fine_rate | 函数 | `src/library/loan/loan.py` 的 `old_fine_rate()`，第 41 行 | 确认没用（0 引用） |
| legacy_export | 函数 | `src/library/loan/loan.py` 的 `legacy_export()`，第 45 行 | 只有测试在用（1 处） |

交给 U14 确认的候选：

| 检查项 | 位置 | 为什么拿不准 |
|---|---|---|
| renew | `src/library/loan/loan.py` 的 `renew()`，第 21 行 | 名字出现在字符串里 |
| handle_overdue | `src/library/loan/loan.py` 的 `handle_overdue()`，第 33 行 | 名字出现在字符串里 |

### U3 · L3 文档对代码（脚本部分）

| 说明文件 | 行 | 提到的东西 | 结果 |
|---|---|---|---|
| src/library/loan/readme.md | 11 | 函数 renew() | 对得上 |
| src/library/loan/readme.md | 11 | 函数 extend_loan() | 找不到 |
| src/library/loan/readme.md | 15 | 默认值 RENEW_DAYS=21 | 值不一样（代码是 14） |
| src/library/loan/readme.md | 16 | 默认值 MAX_RENEWALS=2 | 对得上 |
| src/library/loan/readme.md | 20 | 链接 loan.py | 对得上 |
| src/library/loan/readme.md | 20 | 函数 renew() | 对得上 |
| src/library/loan/readme.md | 20 | 函数 dispatch() | 对得上 |
| src/library/loan/readme.md | 24 | 链接 ../../../docs/spec/loan/spec.md | 找不到 |

没有说明文档的模块：src/library/api、src/library/db、src/library/notify（可以用 x-feat-doc 补）

### U4 · L5 架构审查（脚本部分）

循环依赖：
| 依赖路径 |
|---|
| src/library/api/views.py → src/library/db/store.py → src/library/api/views.py |
| src/library/loan/loan.py → src/library/notify/mailer.py → src/library/loan/loan.py |

分层（按 .x-code-audit.json）：
| 下层文件 | 依赖的上层文件 |
|---|---|
| src/library/db/store.py | src/library/api/views.py |

多处定义的常量（交给子 agent 判断是不是同一件事）：
| 名字 | 位置和值 | 值 |
|---|---|---|
| MAX_RENEWALS | `src/library/api/views.py` 第 11 行 = 3；`src/library/loan/loan.py` 第 7 行 = 2 | 已不一致 |

### U10 · L6 性能 · src/library/loan

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 没问题 | `src/library/loan/loan.py` 的 `renew()`，第 21–30 行，没有循环 |
| 没有重复计算 | 没问题 | `src/library/loan/loan.py` 的 `renew()`，第 21–30 行 |
| 数据结构用得合适 | 没问题 | `src/library/loan/loan.py` 的 `renew()`，第 21–30 行，只处理单条借阅 |
| 没有不必要的等待 | 没问题 | `src/library/loan/loan.py` 的 `renew()`，第 28–29 行，每次同步写一行日志，单次开销很小，不算不必要的等待 |
| 资源用完会释放 | 没问题 | `src/library/loan/loan.py` 的 `renew()`，第 28–29 行，用了 `with open(...)`，成功或失败都会关闭文件 |

### U11 · L4 模块审查 · src/library/notify

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 没问题 | `src/library/notify/mailer.py` 的 `send()`，第 12–20 行，只管发邮件 |
| 对外接口说清楚 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 12–13 行 |
| 错误情况处理清楚 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 19–20 行 |
| 测试真在测 | 没法判断 | `tests/test_library.py` 里找不到针对 `send()` 的测试，只有 `test_renew_sends_mail()` 用 mock 把它整个替换掉了 |

### U12 · L6 性能 · src/library/notify

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 没问题 | `src/library/notify/mailer.py` 的 `send()`，第 12–20 行，没有循环 |
| 没有重复计算 | 没问题 | `src/library/notify/mailer.py` 的 `renew_notice()`，第 23–24 行 |
| 数据结构用得合适 | 没问题 | `src/library/notify/mailer.py` 的 `send()`，第 12–20 行 |
| 没有不必要的等待 | 没问题 | `src/library/notify/mailer.py` 的 `send()`，第 12–20 行，这里没有远程调用 |
| 资源用完会释放 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 17 行 |

### U13 · L5 架构审查 · src/library/api、src/library/db、src/library/loan、src/library/notify

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 同一信息只在一处维护 | 有问题 | `src/library/api/views.py` 第 11 行，和 `src/library/loan/loan.py` 第 7 行 |
| 模块放对地方 | 没问题 | `src/library/db/store.py` 第 2 行：下层导入上层的 `PAGE_SIZE` 是分层问题，已由脚本报为 A5，这里不重复记；业务规则和数据访问的位置没有放错 |
| 没有绕过既有抽象 | 没问题 | `src/library/loan/loan.py` 第 5 行，续借通知走的是 `mailer` 模块，没有另造一套 |
| 以前定的约束还守着 | 没法判断 | 项目副本里没有 `docs/` 目录，读不到 engineering 约束、“架构：”约束和 D 规则，无法逐条对照 |
| 没有多余的抽象 | 没问题 | `src/library/loan/loan.py` 的 `HANDLERS` 和 `dispatch()`，只在 A14 中单独看过；这里没有只做转发的接口层 |

### U14 · L2 死代码 · 拿不准的候选 2 个

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| renew | 没问题 | `src/library/loan/loan.py` 的 `renew()`，第 21 行：是 `loan/readme.md` 写明的对外入口，`tests/test_library.py` 也直接调用它 |
| handle_overdue | 没法判断 | `src/library/loan/loan.py` 的 `handle_overdue()`，第 33 行：只通过 `HANDLERS` 里的字符串，由 `dispatch()` 按名字找到；`dispatch()` 只有测试在用（见 A14）。要不要保留它，取决于 A14 的处理结果 |

### U15 · L3 文档对代码 · src/library/loan

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 功能描述对得上 | 没问题 | `src/library/loan/readme.md` 第 3 行，说的续借加通知，和 `src/library/loan/loan.py` 第 21–30 行的 `renew()` 一致 |
| 使用方式能用 | 有问题 | `src/library/loan/readme.md` 第 11 行 |
| 关键函数说明对得上 | 没问题 | `src/library/loan/readme.md` 第 20 行，`renew()` 和 `dispatch()` 都存在，用途和代码一致 |
| spec 索引还对 | 有问题 | `src/library/loan/readme.md` 第 24 行 |

### U5 · L4 模块审查 · src/library/api

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 有问题 | `src/library/api/views.py` 的 `week_header()`，第 24–33 行 |
| 对外接口说清楚 | 没问题 | `src/library/api/views.py` 的 `member_page()`，第 15–21 行，签名和说明能看出输入输出 |
| 错误情况处理清楚 | 没问题 | `src/library/api/views.py` 的 `member_page()`，第 15–21 行，没有吞错误的代码 |
| 测试真在测 | 没问题 | `tests/test_library.py` 的 `test_member_page()`，第 23–25 行，调用真实函数并检查借阅数 |

### U6 · L6 性能 · src/library/api

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 有问题 | `src/library/api/views.py` 的 `member_page()`，第 18–20 行 |
| 没有重复计算 | 没问题 | `src/library/api/views.py` 的 `member_page()`，第 15–21 行，循环里没有重复算同一结果 |
| 数据结构用得合适 | 没问题 | `src/library/api/views.py` 的 `member_page()`，第 15–21 行，查找成本在 db 层，由 U8 判断 |
| 没有不必要的等待 | 没问题 | `src/library/api/views.py` 的 `member_page()`，第 15–21 行，没有异步或阻塞等待 |
| 资源用完会释放 | 没问题 | `src/library/api/views.py` 的 `member_page()`，第 15–21 行，不打开文件也不占连接 |

### U7 · L4 模块审查 · src/library/db

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 没问题 | `src/library/db/store.py` 的 `DB` 类，第 5–16 行，只管按表和条件取数据 |
| 对外接口说清楚 | 没问题 | `src/library/db/store.py` 的 `query()`，第 10–12 行，参数和返回的都是 `list[dict]` |
| 错误情况处理清楚 | 有问题 | `src/library/db/store.py` 的 `query()`，第 12 行 |
| 测试真在测 | 没问题 | `tests/test_library.py` 的 `test_member_page()`，第 23–25 行，经过真实的 `DB.query()` 取数据 |

### U8 · L6 性能 · src/library/db

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 没问题 | `src/library/db/store.py` 的 `query()`，第 10–12 行，本身不循环查库；循环查库的问题在 U6 |
| 没有重复计算 | 没问题 | `src/library/db/store.py` 的 `query()`，第 10–12 行 |
| 数据结构用得合适 | 有问题 | `src/library/db/store.py` 的 `query()`，第 12 行 |
| 没有不必要的等待 | 没问题 | `src/library/db/store.py` 的 `query()`，第 10–12 行，没有等待 |
| 资源用完会释放 | 没问题 | `src/library/db/store.py` 的 `DB` 类，第 5–16 行，没有打开的资源 |

### U9 · L4 模块审查 · src/library/loan

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 有问题 | `src/library/loan/loan.py` 的 `renew()`，第 21–30 行 |
| 对外接口说清楚 | 有问题 | `src/library/loan/loan.py` 的 `renew()`，第 21–22 行 |
| 错误情况处理清楚 | 没问题 | `src/library/loan/loan.py` 的 `renew()`，第 23–24 行，到上限时明确抛出 `ValueError` |
| 测试真在测 | 有问题 | `tests/test_library.py` 的 `test_renew_sends_mail()`，第 13–16 行 |

