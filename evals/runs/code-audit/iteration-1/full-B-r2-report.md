# 代码巡检报告 · c399b228
<!-- x-code-audit:{"files": ["src/library/__init__.py", "src/library/api/__init__.py", "src/library/api/views.py", "src/library/db/__init__.py", "src/library/db/store.py", "src/library/loan/__init__.py", "src/library/loan/loan.py", "src/library/notify/__init__.py", "src/library/notify/mailer.py", "tests/test_library.py"], "modules": ["src/library/api", "src/library/db", "src/library/loan", "src/library/notify"], "doc_modules": ["src/library/api", "src/library/db", "src/library/loan", "src/library/notify"], "prev": null} -->

> 检查 ID：c399b228
> 开始时间：2026-11-23 08:28
> 状态：完成
> 代码版本：0e6b090
> 上次巡检：无
> 范围：全量（第一次巡检）
> 层：L1、L2、L3、L4、L5、L6

## 范围

- 模块（4 个）：src/library/api、src/library/db、src/library/loan、src/library/notify
- 文件：10 个，清单在「检查进度」下面

## 结论

| 层 | 结果 | 问题数 |
|---|---|---|
| L1 机器检查 | 有问题 | 6 |
| L2 死代码 | 有问题 | 5 |
| L3 文档对代码 | 有问题 | 5（A1 与 A3 是同一处 extend_loan() 问题，A24 与 A25 是同一处 spec 链接问题，脚本和子 agent 各报了一次，建议合并） |
| L4 模块审查 | 有问题 | 7 |
| L5 架构审查 | 有问题 | 6（A7、A8 两个循环依赖只出现在 TYPE_CHECKING 的导入里，运行时并不成环，建议降为 P2；A9 与 A11 是同一处 store.py 依赖 views.py） |
| L6 性能 | 有问题 | 3 |

没有 P0。最要紧的三条是：A10，读者列表页显示的续借上限是 3，但系统实际只允许续借 2 次；A4，发信失败也报成功，读者收不到通知却没人知道；A12，读者列表页对每个读者各查一次借阅表，100 个读者要查 101 次。

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

### A3 · P1 · L3 · 使用说明里的 extend_loan() 不存在，照做会报错

- 是什么：`readme.md` 第 11 行写“要一次延长多次，用 `extend_loan()`”，但 `loan.py` 里根本没有这个函数。读者照着做会直接报错。
- 影响：想一次续借多次的人会照文档调用，得到的是“找不到这个名字”的错误，会以为模块有这个能力，然后花时间去找。
- 位置：`src/library/loan/readme.md`，第 11 行
- 证据：我在项目副本里运行 `hasattr(loan, 'extend_loan')`，结果是 `False`。`readme.md` 第 11 行的说明与此不符。这一条和脚本报出的 A1 是同一处问题，子 agent 确认属实。
- 来源：U15

### A4 · P1 · L4 · 发信失败也报成功，地址写错时读者收不到通知却没人知道

- 是什么：`send()` 的说明写着“返回是否成功”，但不管发没发出去，它都返回 `True`。第 14–19 行用 `try/except Exception` 把所有错误都吞掉，第 20 行直接返回 `True`。地址里没有 `@` 时，第 16 行抛出 `ValueError`，立刻被第 19 行接住，然后还是返回 `True`。
- 影响：续借的时候，如果读者邮箱写错了，续借照样显示成功，读者收不到“已续借”的通知，也没有任何报错或记录，只有等读者来问才会发现。
- 位置：`src/library/notify/mailer.py` 的 `send()`，第 14–20 行
- 证据：我在项目副本里运行过 `mailer.send('not-an-email', 'x')`，返回 `True`；同时 `SENT` 列表里没有新增记录（第 17 行没有执行到）。
- 来源：U11

### A5 · P1 · L4 · 查不存在的表时静默返回空列表

- 是什么：`query()` 用 `self.rows.get(table, [])`（第 12 行）取数据，表名写错或表不存在时，直接返回空列表，不报任何错。`page()`（第 15 行）也是同样的写法。
- 影响：调用方分不清“表里没有数据”和“表名写错了”。比如读者列表页把 `"members"` 写成 `"membres"`，页面会正常打开，只是显示 0 个读者，没有任何报错，很难发现。
- 位置：`src/library/db/store.py` 的 `query()`，第 12 行
- 证据：我在项目副本里运行过 `DB({}).query('membres')`，结果是 `[]`，没有任何异常。
- 来源：U7

### A6 · P1 · L4 · 续借测试只检查“发没发邮件”，没检查到期日和次数

- 是什么：`test_renew_sends_mail()` 只断言 `send.called`（第 16 行）。它不检查到期日有没有延长、续借次数有没有加一，也没测“到达上限要报错”的那条分支。
- 影响：哪天 `RENEW_DAYS` 的计算写错了，或者上限判断写反了，这个测试仍然会通过。测试看着全绿，其实测不出续借算错。
- 位置：`tests/test_library.py` 的 `test_renew_sends_mail()`，第 13–16 行
- 证据：我运行过 `pytest -q tests`，4 个测试全部通过；但手动调用 `renew()` 得到的到期日是 2026-12-15（正确延了 14 天），这个数值在测试里没有被检查。
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

### A10 · P1 · L5 · 续借上限在两处写成了不同的数字，读者列表页显示错了

- 是什么：“每笔借阅最多续借几次”这件事，写在两个地方：`views.py` 第 11 行写的是 3，`loan.py` 第 7 行写的是 2。续借真正生效的是 2（`loan.py` 第 23 行用的就是它），readme 也写的是 2。
- 影响：读者列表页的 `max` 字段会显示“最多续借 3 次”，但读者实际只能续借 2 次。读者看到的和系统执行的对不上，客服会遇到“为什么我续借不了”的问题。以后改上限时，只改一处，另一处会悄悄留着旧值。
- 位置：`src/library/api/views.py` 第 11 行，和 `src/library/loan/loan.py` 第 7 行
- 证据：`views.py` 第 20 行 `"max": MAX_RENEWALS`，取的是 3；我运行过 `from library.api.views import MAX_RENEWALS` 得到 3，`loan.MAX_RENEWALS` 得到 2。
- 来源：U13

### A11 · P1 · L5 · 分层约束被打破：db 层依赖了 api 层

- 是什么：`.x-code-audit.json` 规定分层从上到下是 `api`、`loan`/`notify`、`db`，`db` 是最底层。但 `src/library/db/store.py` 第 2 行 import 了 `src/library/api/views.py`，底层反过来依赖了上层。这和脚本报出的分层问题（A5）是同一处，子 agent 确认属实。
- 影响：底层依赖上层，改接口层的东西就可能牵动数据层，改着改着就乱了。
- 位置：`src/library/db/store.py` 第 2 行
- 证据：`store.py` 第 2 行 `from library.api.views import PAGE_SIZE`；`.x-code-audit.json` 的内容是 `{"layers": [["api"], ["loan", "notify"], ["db"]]}`。
- 来源：U13

### A12 · P1 · L6 · 读者列表页对每个读者各查一次借阅表

- 是什么：`member_page()` 先查出所有读者（第 18 行），然后在循环里对每个读者再调用一次 `db.query("loans", ...)`（第 19 行）。读者有多少个，就要查多少次借阅表。
- 影响：读者一多，打开这个列表页要做的查询次数跟着涨（100 个读者要 101 次查询，1000 个读者要 1001 次）。而且每次查询都要从头扫一遍整张借阅表，所以页面会明显变慢。页面也没有分页，所有读者每次都全部加载。
- 位置：`src/library/api/views.py` 的 `member_page()`，第 18–19 行
- 证据：我在项目副本里实际运行过：用 100 个读者的假数据调用 `member_page(db)`，`db.queries` 的值是 101（1 次查读者 + 100 次查借阅）。`src/library/db/store.py` 第 12 行的 `query()` 每次都对整张表做列表推导。
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

### A25 · P2 · L3 · spec 链接打不开

- 是什么：`readme.md` 第 24 行的链接 `../../../docs/spec/loan/spec.md` 指向的文件不存在。项目根目录下根本没有 `docs/` 目录。
- 影响：读者点进去什么也找不到，只能自己在代码里翻找续借的规则。
- 位置：`src/library/loan/readme.md`，第 24 行
- 证据：项目副本的根目录没有 `docs/` 目录，链接目标不存在。这一条和脚本报出的 A17 是同一处问题，子 agent 确认属实。
- 来源：U15

### A26 · P2 · L4 · 接口层文件里混进了和读者列表无关的日历表头函数

- 是什么：`views.py` 的说明是“接口层：读者列表页”，但里面还放着 `week_header()`，它生成“周一(0)”“周二(1)”这类星期表头，和读者列表没有关系。
- 影响：读这个文件的人会以为读者列表页用到了星期表头；以后要改日历相关的东西，也会跑到读者列表的代码里找。
- 位置：`src/library/api/views.py` 的 `week_header()`，第 24 行
- 证据：第 24–33 行是整个函数；全项目没有任何地方调用它（这一点已由 L2 的死代码问题记录）。删掉它，这个问题也跟着消失。
- 来源：U5

### A27 · P2 · L4 · page() 的页码参数没有说明

- 是什么：`page(table, n)` 的 `n` 是从 0 开始算的页码（第 16 行用 `n * PAGE_SIZE` 切片），但签名和模块说明里都没有写。
- 影响：调用方很可能把 `n` 当成从 1 开始的页码，结果第一页被跳过，而且不会报错。
- 位置：`src/library/db/store.py` 的 `page()`，第 14–16 行
- 证据：第 16 行 `self.rows.get(table, [])[n * PAGE_SIZE:(n + 1) * PAGE_SIZE]`；第 1 行模块说明只写了 query 的行为，没提 page 的页码规则。
- 来源：U7

### A28 · P2 · L4 · 续借函数里顺带发邮件、写日志文件

- 是什么：`renew()` 本来只该做“到期日往后延”，但它还直接调用邮件模块发通知（第 27 行），又往 `/tmp/renew.log` 追加一行日志（第 28–29 行）。
- 影响：以后要改通知方式（比如改成短信），就得动续借的代码；测续借的时候也得先准备好邮件和日志文件，否则测试没法单独跑。
- 位置：`src/library/loan/loan.py` 的 `renew()`，第 27–29 行
- 证据：第 27 行 `mailer.send(loan.member_email, mailer.renew_notice(loan))`；第 28–29 行 `open("/tmp/renew.log", "a", ...)`。
- 来源：U9

### A29 · P2 · L4 · renew() 会直接改掉传进来的对象，签名里看不出来

- 是什么：`renew()` 在第 25–26 行直接修改传入的 `Loan` 对象（次数加一、到期日往后延），然后返回同一个对象。签名 `-> Loan` 没有说明它会改参数，也没有说明它会发邮件、写日志。
- 影响：调用方如果以为“传进去的对象不会变”，就会在别处用到旧的到期日，结果对不上。
- 位置：`src/library/loan/loan.py` 的 `renew()`，第 25–26 行
- 证据：第 25 行 `loan.renew_count += 1`，第 26 行 `loan.due = loan.due + timedelta(days=RENEW_DAYS)`；函数直接返回的也是这个 `loan`。
- 来源：U9

### A30 · P2 · L5 · PAGE_SIZE 放在接口层，却被数据层用来分页

- 是什么：分页大小 `PAGE_SIZE` 定义在接口层的 `views.py`（第 10 行），数据层的 `store.py` 却 import 它（第 2 行）来做分页切片（`store.py` 第 16 行）。
- 影响：分页规则本该归数据层管，现在却要靠接口层来决定，以后想让不同页面用不同分页大小，就得改数据层。
- 位置：`src/library/db/store.py` 第 2 行，`src/library/api/views.py` 第 10 行
- 证据：`store.py` 第 2 行 `from library.api.views import PAGE_SIZE`。注意这一条和脚本报出的分层问题（A5，下层依赖上层）是同一处依赖，这里只补充“这个常量放错了层”。
- 来源：U13

### A31 · P2 · L6 · 发过的每封邮件都永远留在内存的列表里

- 是什么：`SENT` 是模块级的列表（第 9 行），`send()` 每成功发一封，就往里面追加一条 `(地址, 正文)`（第 17 行）。代码里没有任何地方清空它，也没有上限。
- 影响：程序跑得越久，这个列表占的内存越多，而且每条都保留完整的邮件正文。正常访问量下增长得很慢，短期不会出事，但程序是长期运行的话，会一直涨下去。
- 位置：`src/library/notify/mailer.py` 的 `send()`，第 17 行
- 证据：第 9 行 `SENT: list[tuple[str, str]] = []`；第 17 行 `SENT.append((to, text))`。我运行过两次 `send()`，`SENT` 长度变成 2，之后没有任何代码会把它清掉。
- 来源：U12

### A32 · P2 · L6 · 每次查询都从头扫整张表，没有索引

- 是什么：`query()` 每次调用都对整张表做一遍列表推导（第 12 行），`where` 条件再逐条比较。没有按字段建立的索引，所以找一个读者的借阅要扫完所有借阅记录。
- 影响：数据量小的时候没感觉；借阅记录一多，每次查询都会变慢，而且会和上层的循环查询叠加在一起。因为模块说明写的是“极简数据库”，这一条的严重度定为 P2，不是 P1。
- 位置：`src/library/db/store.py` 的 `query()`，第 10–12 行
- 证据：第 12 行 `[r for r in self.rows.get(table, []) if all(r.get(k) == v for k, v in where.items())]`，每次调用都遍历整张表。
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
| 循环里没有查库或调接口 | 没问题 | `src/library/loan/loan.py` 的 `renew()`，一次续借只做一次操作，没有循环 |
| 没有重复计算 | 没问题 | `src/library/loan/loan.py` 的 `renew()`，第 21–30 行，没有重复计算 |
| 数据结构用得合适 | 没问题 | `src/library/loan/loan.py` 的 `legacy_export()` 用字符串拼接，数据量小，不在热路径上 |
| 没有不必要的等待 | 没问题 | 发邮件用的 `mailer.send()` 目前只是往内存列表里加一条记录，没有真的网络等待 |
| 资源用完会释放 | 没问题 | `src/library/loan/loan.py` 第 28 行用 `with open(...)` 打开日志文件，会自动关闭 |

### U11 · L4 模块审查 · src/library/notify

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 没问题 | `src/library/notify/mailer.py` 只管发信和生成通知文字 |
| 对外接口说清楚 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 12–20 行 |
| 错误情况处理清楚 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 14–20 行 |
| 测试真在测 | 没法判断 | 这个模块没有自己的测试文件；`tests/test_library.py` 里对 `send` 全部用 mock 替换掉了，看不出它本身的行为有没有被测到 |

### U12 · L6 性能 · src/library/notify

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 没问题 | `src/library/notify/mailer.py` 没有循环 |
| 没有重复计算 | 没问题 | `src/library/notify/mailer.py` 的 `renew_notice()`，只拼一句字符串 |
| 数据结构用得合适 | 没问题 | `src/library/notify/mailer.py` 没有大量查找 |
| 没有不必要的等待 | 没问题 | 发信是同步的内存操作，没有网络等待 |
| 资源用完会释放 | 有问题 | `src/library/notify/mailer.py` 第 9 行的 `SENT` 列表，第 17 行的 `send()` 每成功一次就追加一条 |

### U13 · L5 架构审查 · src/library/api、src/library/db、src/library/loan、src/library/notify

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 同一信息只在一处维护 | 有问题 | `src/library/api/views.py` 第 11 行，和 `src/library/loan/loan.py` 第 7 行 |
| 模块放对地方 | 有问题 | `src/library/db/store.py` 第 2 行，`src/library/api/views.py` 第 10 行 |
| 没有绕过既有抽象 | 没问题 | `src/library/loan/loan.py` 第 5 行直接用 `notify` 模块的 `mailer`，没有另造发信逻辑 |
| 以前定的约束还守着 | 有问题 | `.x-code-audit.json` 的 `layers` 规定 `db` 在最底层，`src/library/db/store.py` 第 2 行却依赖 `src/library/api/views.py` |
| 没有多余的抽象 | 没问题 | `loan.py` 的 `dispatch()` 只是一个字典转发，但生产代码没有调用它，它的问题已记在 L2 的死代码里，删掉不影响生产，不另记 |

### U14 · L2 死代码 · 拿不准的候选 2 个

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| renew | 没问题 | `src/library/loan/loan.py` 的 `renew()`，第 21 行；`readme.md` 把它写成对外入口，`tests/test_library.py` 第 15 行真实调用 |
| handle_overdue | 没法判断 | `src/library/loan/loan.py` 的 `handle_overdue()`，第 33 行。它只能经由 `HANDLERS` 字典的名字找到，再由 `dispatch()` 调用；而 `dispatch()` 只有测试在用。能不能删，要看仓库外有没有人直接调用 `dispatch()`，本仓库里看不到 |

### U15 · L3 文档对代码 · src/library/loan

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 功能描述对得上 | 没问题 | `src/library/loan/readme.md` 第 3、7 行的描述（续借、到期日往后延、发通知）和 `loan.py` 的 `renew()` 一致；默认值不一致的问题已由脚本记为 A2 |
| 使用方式能用 | 有问题 | `src/library/loan/readme.md`，第 11 行 |
| 关键函数说明对得上 | 没问题 | `src/library/loan/readme.md` 第 20 行的 `renew()` 说明“续借一次”与代码一致；`dispatch()` 只列了名字，没有写用途，这属于说明缺内容，不算写错 |
| spec 索引还对 | 有问题 | `src/library/loan/readme.md`，第 24 行 |

### U5 · L4 模块审查 · src/library/api

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 有问题 | `src/library/api/views.py` 的 `week_header()`，第 24–33 行 |
| 对外接口说清楚 | 没问题 | `src/library/api/views.py` 的 `member_page()`，第 15–21 行，签名为 `list[dict]`，返回字段较少 |
| 错误情况处理清楚 | 没问题 | `src/library/api/views.py` 的 `member_page()`，第 15–21 行，没有吞掉错误的写法 |
| 测试真在测 | 没问题 | `tests/test_library.py` 的 `test_member_page()`，用真实 DB 类调用并检查借阅数 |

### U6 · L6 性能 · src/library/api

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 有问题 | `src/library/api/views.py` 的 `member_page()`，第 18–19 行 |
| 没有重复计算 | 没问题 | `src/library/api/views.py` 的 `member_page()`，第 15–21 行，循环里没有重复算同一结果 |
| 数据结构用得合适 | 没问题 | 线性扫描的代价已计入上面那条问题，不再重复记 |
| 没有不必要的等待 | 没问题 | 全部是同步的普通函数，没有异步等待写法 |
| 资源用完会释放 | 没问题 | 没有打开的连接、文件或锁 |

### U7 · L4 模块审查 · src/library/db

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 没问题 | `src/library/db/store.py` 的 `DB` 类，只管存放和查询数据 |
| 对外接口说清楚 | 有问题 | `src/library/db/store.py` 的 `page()`，第 14–16 行 |
| 错误情况处理清楚 | 有问题 | `src/library/db/store.py` 的 `query()`，第 10–12 行 |
| 测试真在测 | 没问题 | `tests/test_library.py` 的 `test_member_page()` 通过真实的 `DB.query` 检查真实结果 |

### U8 · L6 性能 · src/library/db

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 没问题 | `src/library/db/store.py` 本身没有循环查库；循环的问题在 `api/views.py`，见 U6 |
| 没有重复计算 | 没问题 | `src/library/db/store.py` 的 `DB` 类，没有重复计算 |
| 数据结构用得合适 | 有问题 | `src/library/db/store.py` 的 `query()`，第 10–12 行 |
| 没有不必要的等待 | 没问题 | 全部是同步的普通函数 |
| 资源用完会释放 | 没问题 | 没有打开的连接或文件 |

### U9 · L4 模块审查 · src/library/loan

模型：claude-haiku-5-5

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 有问题 | `src/library/loan/loan.py` 的 `renew()`，第 21–30 行 |
| 对外接口说清楚 | 有问题 | `src/library/loan/loan.py` 的 `renew()`，第 21–30 行 |
| 错误情况处理清楚 | 没问题 | `src/library/loan/loan.py` 的 `renew()`，第 23–24 行达到上限时明确抛出 `ValueError`；发通知失败被吞掉的问题记在 U11 |
| 测试真在测 | 有问题 | `tests/test_library.py` 的 `test_renew_sends_mail()`，第 13–16 行 |

