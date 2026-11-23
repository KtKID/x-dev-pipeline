# 代码巡检报告 · b16808b7
<!-- x-code-audit:{"files": ["src/library/__init__.py", "src/library/api/__init__.py", "src/library/api/views.py", "src/library/db/__init__.py", "src/library/db/store.py", "src/library/loan/__init__.py", "src/library/loan/loan.py", "src/library/notify/__init__.py", "src/library/notify/mailer.py", "tests/test_library.py"], "modules": ["src/library/api", "src/library/db", "src/library/loan", "src/library/notify"], "doc_modules": ["src/library/api", "src/library/db", "src/library/loan", "src/library/notify"], "prev": null} -->

> 检查 ID：b16808b7
> 开始时间：2026-11-23 08:28
> 状态：进行中
> 代码版本：0e6b090
> 上次巡检：无
> 范围：全量（第一次巡检）
> 层：L1、L2、L3、L4、L5、L6

## 范围

- 模块（4 个）：src/library/api、src/library/db、src/library/loan、src/library/notify
- 文件：10 个，清单在「检查进度」下面

## 结论

verify 未通过（1 处）：U15 的「使用方式能用」「spec 索引还对」标了“有问题”，但问题里没有 来源 为 U15 的条目；这两项的问题就是 A2 和 A26（脚本在 U3 已报），这里没有重复立项。状态保持“进行中”，等补完再跑。

| 层 | 结果 | 问题数 |
|---|---|---|
| L1 机器检查 | 有问题 | 6 |
| L2 死代码 | 有问题 | 7 |
| L3 文档对代码 | 有问题 | 3 |
| L4 模块审查 | 有问题 | 6 |
| L5 架构审查 | 有问题 | 4 |
| L6 性能 | 有问题 | 4 |

最严重的问题：A1（P0），读者列表页显示的续借上限是 3，实际能续的上限是 2，列表页给读者的是错的结果。

## 问题

### A1 · P0 · L4 · 读者列表页显示的续借上限和实际上限不一样

- 是什么：`member_page()` 把每位读者的 `max` 设成 `MAX_RENEWALS`，而这个常量在本模块是 3。真正拦住续借的是 `loan` 模块里的 `MAX_RENEWALS`，它是 2。列表页显示的上限和续借时实际能续的次数对不上。
- 影响：读者在列表页看到“最多可续 3 次”，实际第 3 次就会被拒绝。页面给的是错的结果，读者和馆员都会被误导。
- 位置：`src/library/api/views.py` 的 `member_page()`，第 20 行（常量定义在第 11 行）
- 证据：第 20 行 `out.append({"name": member["name"], "loans": len(loans), "max": MAX_RENEWALS})`；`src/library/loan/loan.py` 第 7 行 `MAX_RENEWALS = 2`。根因是同一个常量写了两份，见 U13 的问题。
- 来源：U5

### A2 · P1 · L3 · 说明里写的函数 extend_loan() 不存在

- 是什么：`src/library/loan/readme.md` 第 11 行提到函数 `extend_loan()`，但模块代码里找不到这个函数。
- 影响：照着说明去调用会失败，读者会以为模块有这个能力。
- 位置：`src/library/loan/readme.md`，第 11 行
- 证据：在 src/library/loan/ 的代码里搜不到 `extend_loan` 的定义
- 怎么改：用 x-feat-doc 按现在的代码重写这一节
- 来源：U3

### A3 · P1 · L3 · 说明里 RENEW_DAYS 的默认值写错了

- 是什么：`src/library/loan/readme.md` 第 15 行说 `RENEW_DAYS` 默认是 `21`，代码里实际是 `14`。
- 影响：照着说明理解的人会以为是另一个值，配置和排查都会出错。
- 位置：`src/library/loan/readme.md`，第 15 行
- 证据：代码：RENEW_DAYS = 14
- 怎么改：用 x-feat-doc 按代码更新默认值
- 来源：U3

### A4 · P1 · L4 · 发信失败也报告成功

- 是什么：`send()` 用 `try/except Exception` 把所有错误都吞掉，然后返回 True。地址不合法时，它先主动抛出 `ValueError`，马上又被自己的 `except` 接住，最后还是返回 True。也就是说，没发出去的信也报告“成功”。
- 影响：续借成功，但读者其实没收到通知，系统不报错，也没有任何记录。馆员和读者都不会知道，只能等读者来问。`loan.renew()` 也没看返回值，所以这里没人能补救。
- 位置：`src/library/notify/mailer.py` 的 `send()`，第 14–20 行
- 证据：第 14 行 `try:`；第 15–16 行 `if "@" not in to: raise ValueError("bad address")`；第 19–20 行 `except Exception: return True`。`src/library/loan/loan.py` 第 27 行调用 `mailer.send(...)` 时没有检查返回值。
- 来源：U11

### A5 · P1 · L4 · 表名写错时查询静默返回空列表

- 是什么：`query()` 和 `page()` 用 `self.rows.get(table, [])` 取数据。表名拼错或表不存在时，不报错，直接返回空列表。
- 影响：调用方会以为“没有数据”，而不是“表名写错了”。比如把 `"loans"` 写成 `"loan"`，列表页的借阅数会全部显示为 0，看上去像正常结果，很难发现。
- 位置：`src/library/db/store.py` 的 `query()`，第 12 行
- 证据：第 12 行 `return [r for r in self.rows.get(table, []) if all(...)]`；第 16 行 `return self.rows.get(table, [])[...]` 也是同样的写法。
- 来源：U7

### A6 · P1 · L4 · 续借测试只检查邮件有没有被调用

- 是什么：`test_renew_sends_mail` 把 `mailer.send` 整个 mock 掉，只断言它被调用了。它没有检查到期日有没有顺延、续借次数有没有加一，也没有测超上限的情况。
- 影响：续借的核心逻辑改坏了，这条测试照样通过，测试看着全绿，其实测不出续借有没有算错。
- 位置：`tests/test_library.py` 的 `test_renew_sends_mail`，第 13–16 行
- 证据：第 14 行 `with mock.patch.object(loan_mod.mailer, "send") as send:`；第 16 行 `assert send.called`，是唯一的断言。
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

### A10 · P1 · L5 · 续借上限在两个模块各写一份，而且值不一样

- 是什么：“每笔借阅最多能续几次”这件事，`api` 模块写成 3，`loan` 模块写成 2。读者列表页用的是 3，真正拦住续借的是 2。两处没有任何关联，改一处另一处不会跟着变。
- 影响：规则一改（比如把上限改成 3），如果只改了其中一处，列表页和续借行为就会分叉，读者看到的和实际能做的对不上。说明文档也写的是 2，三处各说各的。
- 位置：`src/library/api/views.py` 第 11 行；`src/library/loan/loan.py` 第 7 行
- 证据：`views.py` 第 11 行 `MAX_RENEWALS = 3`；`loan.py` 第 7 行 `MAX_RENEWALS = 2`；`loan.py` 第 23 行实际用于拦截续借。
- 来源：U13

### A11 · P1 · L6 · 发出的每封邮件都被永久记在内存列表里

- 是什么：模块级的 `SENT` 列表，每发一封信都追加一条 `(地址, 正文)`，从来不清空，也没有上限。
- 影响：服务长时间运行，每续借一次就多占一份内存，内存会一直涨，最后可能占满。正常量下不会马上出事，所以定为 P1 而不是 P0。另外，这份记录只有测试在用，生产里没有人读它。
- 位置：`src/library/notify/mailer.py`，第 9 行定义，第 17 行追加
- 证据：第 9 行 `SENT: list[tuple[str, str]] = []`；第 17 行 `SENT.append((to, text))`。全项目里只有这两处引用 `SENT`。
- 来源：U12

### A12 · P1 · L6 · 读者列表页对每位读者各查一次借阅表（N+1）

- 是什么：`member_page()` 先查出所有读者，再在循环里对每位读者单独查一次借阅表。每次查询都要在整张借阅表上过一遍。
- 影响：读者和借阅越多，列表页要查的次数和扫描的行数成倍增长。比如读者 1 万、借阅 10 万，一次打开列表页要扫描约 10 亿行，页面会卡很久甚至超时。数据量小时看不出来，所以不算 P0。
- 位置：`src/library/api/views.py` 的 `member_page()`，第 18–19 行
- 证据：第 18 行 `for member in db.query("members"):`；第 19 行 `loans = db.query("loans", member_id=member["id"])`；`src/library/db/store.py` 第 10–12 行 `query()` 每次都过滤全部行。
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

### A24 · P2 · L2 · handle_overdue 只通过一个生产没人调用的 dispatch 访问

- 是什么：`handle_overdue()` 只能经由 `dispatch("overdue", ...)` 进入，而 `dispatch()` 生产代码里没有调用方，只有测试在用。所以这个函数实际上也只有测试在用，并且它依赖的 `HANDLERS` 字典和 `globals()` 查找也跟着没人用。
- 影响：读代码的人会以为“逾期提醒”有真实的处理路径，实际上没有。改它时要同时理解 `globals()` 的查找方式，徒增负担。
- 位置：`src/library/loan/loan.py` 的 `handle_overdue()`，第 33–34 行；`HANDLERS` 在第 10 行；`dispatch()` 在第 37–38 行
- 证据：第 10 行 `HANDLERS = {"overdue": "handle_overdue"}`；第 38 行 `return globals()[HANDLERS[event]](loan)`；`tests/test_library.py` 第 29 行是唯一经由 `dispatch` 调用的地方。
- 来源：U14

### A25 · P2 · L2 · DB.page 方法没有任何调用方

- 是什么：`DB.page()` 定义了，但全项目没有任何地方调用它。
- 影响：列表页本来应该用它分页（见 U6），它却闲置着。它也是 `store.py` 导入 `PAGE_SIZE`（从而依赖 `api` 层）的唯一理由，删掉它时要连带处理 A5。
- 位置：`src/library/db/store.py` 的 `page()`，第 14–16 行
- 证据：全项目 `page(` 只在 `store.py` 第 14 行的定义处出现。
- 来源：U14

### A26 · P2 · L3 · 说明里的链接失效：../../../docs/spec/loan/spec.md

- 是什么：`src/library/loan/readme.md` 第 24 行的链接 `../../../docs/spec/loan/spec.md` 打不开（找不到）。
- 影响：读者点进去什么也找不到，只能自己翻代码。
- 位置：`src/library/loan/readme.md`，第 24 行
- 证据：目标 ../../../docs/spec/loan/spec.md 找不到
- 怎么改：用 x-feat-doc 更新这一节的链接
- 来源：U3

### A27 · P2 · L4 · 续借函数里顺带发邮件、写日志文件

- 是什么：`renew()` 续借成功后，除了改到期日，还直接调邮件服务发通知，又往 `/tmp/renew.log` 写一行日志。续借、通知、记日志三件事写在同一个函数里。
- 影响：以后要改通知方式（比如改发短信），就得动续借代码，容易把续借改坏。测续借时还得先准备好邮件服务，并且会真的写一个日志文件到 `/tmp`，换个系统就可能失败。
- 位置：`src/library/loan/loan.py` 的 `renew()`，第 27–29 行
- 证据：第 27 行 `mailer.send(loan.member_email, mailer.renew_notice(loan))`；第 28–29 行 `open("/tmp/renew.log", "a", ...)`。
- 来源：U9

### A28 · P2 · L4 · 续借函数原地修改传入的对象，返回值却是同一个对象

- 是什么：`renew()` 直接改传入的 `Loan` 对象（`renew_count` 加一、`due` 往后推），然后把它返回。调用方不看实现，很难知道原来的对象已经被改了。
- 影响：如果调用方还保留着原对象，比如在列表里多处引用，续借后它们的到期日会一起变，容易出现难查的数据错乱。
- 位置：`src/library/loan/loan.py` 的 `renew()`，第 25–26 行
- 证据：第 25 行 `loan.renew_count += 1`；第 26 行 `loan.due = loan.due + timedelta(days=RENEW_DAYS)`；第 30 行 `return loan`。
- 来源：U9

### A29 · P2 · L6 · 读者列表页不分页，一次返回所有读者

- 是什么：`PAGE_SIZE = 20` 已经定义在 `views.py` 第 10 行，`DB.page()` 也是为分页写的，但 `member_page()` 没有用它们，一次把所有读者都取出来。
- 影响：读者变多后，每次打开列表页都要传输和渲染全部读者，页面会越来越慢，而且分页常量形同虚设。
- 位置：`src/library/api/views.py` 的 `member_page()`，第 18 行
- 证据：第 10 行 `PAGE_SIZE = 20`；第 18 行 `db.query("members")` 没有分页参数；全项目里 `page(` 只在 `store.py` 的定义处出现，没有调用。
- 来源：U6

### A30 · P2 · L6 · 每次查询都整表扫描，没有索引

- 是什么：`query()` 每调用一次，都把整张表的每一行拿来比对一遍条件。没有按字段建立的索引，也没有按主键的直接查找。
- 影响：单次查询已经是整表扫描，数据一多，单次就慢；再叠加 U6 里的循环查询，会把代价放大。现在数据量小，影响还不明显，所以定为 P2。
- 位置：`src/library/db/store.py` 的 `query()`，第 10–12 行
- 证据：第 12 行 `[r for r in self.rows.get(table, []) if all(r.get(k) == v for k, v in where.items())]`，每次都遍历整个列表。
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

模型：claude-haiku-5-5（主 agent 自己做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 没问题 | `src/library/loan/loan.py`，没有循环 |
| 没有重复计算 | 没问题 | `src/library/loan/loan.py`，`renew()` 每次只做一次计算 |
| 数据结构用得合适 | 没问题 | `src/library/loan/loan.py` 的 `dispatch()` 用字典和 `globals()` 查找，是 O(1)；数据量不大，不报 |
| 没有不必要的等待 | 没问题 | `renew()` 同步发邮件和写文件，但是单次操作、调用量小，不报 |
| 资源用完会释放 | 没问题 | `src/library/loan/loan.py` 第 28–29 行用 `with open(...)`，成功和失败都会关闭 |

### U11 · L4 模块审查 · src/library/notify

模型：claude-haiku-5-5（主 agent 自己做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 没问题 | `src/library/notify/mailer.py`，`send()` 发信，`renew_notice()` 拼文字，各管一件事 |
| 对外接口说清楚 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 12–13 行：说明写“返回是否成功”，但实际不管成败都返回 True（见下一条） |
| 错误情况处理清楚 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 14–20 行 |
| 测试真在测 | 没法判断 | 没有直接测 `mailer` 的测试文件；`test_renew_sends_mail` 只把 `mailer.send` 整个 mock 掉，看不出它的失败路径有没有被测。覆盖率不在本层判断 |

### U12 · L6 性能 · src/library/notify

模型：claude-haiku-5-5（主 agent 自己做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 没问题 | `src/library/notify/mailer.py`，没有循环 |
| 没有重复计算 | 没问题 | `src/library/notify/mailer.py`，没有重复计算 |
| 数据结构用得合适 | 没问题 | `src/library/notify/mailer.py`，`SENT` 只追加，不做查找 |
| 没有不必要的等待 | 没问题 | `src/library/notify/mailer.py`，`send()` 没有等待 |
| 资源用完会释放 | 有问题 | `src/library/notify/mailer.py` 第 9 行和第 17 行，`SENT` 只增不减 |

### U13 · L5 架构审查 · src/library/api、src/library/db、src/library/loan、src/library/notify

模型：claude-haiku-5-5（主 agent 自己做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 同一信息只在一处维护 | 有问题 | `src/library/api/views.py` 第 11 行 `MAX_RENEWALS = 3`；`src/library/loan/loan.py` 第 7 行 `MAX_RENEWALS = 2`。同一件事（续借上限）写了两份，值已不一致。`readme.md` 第 16 行写的是 2 |
| 模块放对地方 | 有问题 | `src/library/db/store.py` 第 2 行从 `library.api.views` 导入 `PAGE_SIZE`，数据层依赖接口层。已由脚本记为 A5，这里不重复立项 |
| 没有绕过既有抽象 | 没问题 | 邮件统一走 `notify.mailer`，数据统一走 `DB`；`loan.py` 的日志直接写文件，但项目里没有现成的日志抽象可绕 |
| 以前定的约束还守着 | 没法判断 | 项目里没有 `docs/spec/`，没有 engineering spec、没有“架构：”约束、没有 D 规则，无从核对 |
| 没有多余的抽象 | 没问题 | 没有只有一个实现的接口或只做转发的层；`dispatch()` 的问题归 L2 |

### U14 · L2 死代码 · 拿不准的候选 2 个

模型：claude-haiku-5-5（主 agent 自己做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| renew | 没问题 | `src/library/loan/loan.py` 的 `renew()`，第 21 行。是对外入口：`src/library/loan/readme.md` 第 11 行写明“调用 `renew()` 续借一次”。项目内没有生产调用方，只有 `tests/test_library.py` 第 15 行调用 |
| handle_overdue | 有问题 | `src/library/loan/loan.py` 的 `handle_overdue()`，第 33 行。只通过 `HANDLERS` 字典和 `dispatch()` 间接引用；`dispatch()` 生产代码不调用（已记为 A14），所以只有测试间接在用 |
| DB.page（脚本没扫到的方法） | 有问题 | `src/library/db/store.py` 的 `DB.page()`，第 14 行。全项目只有定义处，0 引用。脚本只扫顶层函数和类，漏掉了方法 |

### U15 · L3 文档对代码 · src/library/loan

模型：claude-haiku-5-5（主 agent 自己做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 功能描述对得上 | 没问题 | `src/library/loan/readme.md` 第 3、7 行：续借、延长到期日、发通知，和 `loan.py` 的 `renew()` 一致。默认值写错归 A2 |
| 使用方式能用 | 有问题 | `src/library/loan/readme.md` 第 11 行的 `extend_loan()` 不存在，见 A1 |
| 关键函数说明对得上 | 没问题 | `readme.md` 第 20 行列出的 `renew()`、`dispatch()` 确实在 `loan.py` 里 |
| spec 索引还对 | 有问题 | `src/library/loan/readme.md` 第 24 行的链接打不开，见 A17 |

### U5 · L4 模块审查 · src/library/api

模型：claude-haiku-5-5（主 agent 自己做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 没问题 | `src/library/api/views.py` 的 `member_page()`，只做列表；`week_header()` 与读者列表无关，但已由 L2 的 A13 记录，这里不重复 |
| 对外接口说清楚 | 有问题 | `src/library/api/views.py` 的 `member_page()`，第 15–20 行：返回裸 dict，`max` 字段的含义没写 |
| 错误情况处理清楚 | 没问题 | `src/library/api/views.py` 的 `member_page()`，没有吞错误的写法 |
| 测试真在测 | 没问题 | `tests/test_library.py` 的 `test_member_page`，用真实 DB 对象，断言真实的借阅数 |

### U6 · L6 性能 · src/library/api

模型：claude-haiku-5-5（主 agent 自己做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 有问题 | `src/library/api/views.py` 的 `member_page()`，第 18–19 行 |
| 没有重复计算 | 没问题 | `src/library/api/views.py` 整个模块，没有循环里重算的结果 |
| 数据结构用得合适 | 有问题 | `src/library/api/views.py` 第 19 行，每次查借阅都在整张表上线性扫描（同一问题见下） |
| 没有不必要的等待 | 没问题 | 没有异步代码，没有等待 |
| 资源用完会释放 | 没问题 | 本模块不打开任何资源 |

### U7 · L4 模块审查 · src/library/db

模型：claude-haiku-5-5（主 agent 自己做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 没问题 | `src/library/db/store.py` 的 `DB` 类，只管查询 |
| 对外接口说清楚 | 没问题 | `src/library/db/store.py` 的 `query()`、`page()`，签名和返回值（list[dict]）清楚；`page()` 本身没有调用方，见 U14 |
| 错误情况处理清楚 | 有问题 | `src/library/db/store.py` 第 12 行和第 16 行，表名写错时静默返回空列表 |
| 测试真在测 | 没问题 | `tests/test_library.py` 的 `test_member_page` 用真实 DB 对象检查真实结果。不跑覆盖率，所以不评价 `page()` 有没有测试 |

### U8 · L6 性能 · src/library/db

模型：claude-haiku-5-5（主 agent 自己做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 没问题 | `src/library/db/store.py`，本模块内没有循环里再查库的写法；N+1 在 U6 |
| 没有重复计算 | 没问题 | `src/library/db/store.py`，没有重复计算 |
| 数据结构用得合适 | 有问题 | `src/library/db/store.py` 的 `query()`，第 10–12 行，每次都线性扫描整个列表，没有索引 |
| 没有不必要的等待 | 没问题 | 没有异步或等待 |
| 资源用完会释放 | 没问题 | 本模块不持有资源 |

### U9 · L4 模块审查 · src/library/loan

模型：claude-haiku-5-5（主 agent 自己做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 有问题 | `src/library/loan/loan.py` 的 `renew()`，第 27–29 行：续借时顺带发邮件、写 `/tmp/renew.log` |
| 对外接口说清楚 | 有问题 | `src/library/loan/loan.py` 的 `renew()`，第 21–30 行：传入的 `loan` 被原地修改（`renew_count`、`due`），签名和说明看不出来 |
| 错误情况处理清楚 | 没问题 | `src/library/loan/loan.py` 第 23–24 行超上限时抛 `ValueError`，清楚。`mailer.send` 的失败处理归 U11 |
| 测试真在测 | 有问题 | `tests/test_library.py` 的 `test_renew_sends_mail`，第 13–16 行 |

