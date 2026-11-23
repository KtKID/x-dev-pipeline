# 代码巡检报告 · 17080599
<!-- x-code-audit:{"files": ["src/library/__init__.py", "src/library/api/__init__.py", "src/library/api/views.py", "src/library/db/__init__.py", "src/library/db/store.py", "src/library/loan/__init__.py", "src/library/loan/loan.py", "src/library/notify/__init__.py", "src/library/notify/mailer.py", "tests/test_library.py"], "modules": ["src/library/api", "src/library/db", "src/library/loan", "src/library/notify"], "doc_modules": ["src/library/api", "src/library/db", "src/library/loan", "src/library/notify"], "prev": null} -->

> 检查 ID：17080599
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
| L1 机器检查 | 有问题 | 6 |
| L2 死代码 | 有问题 | 5 |
| L3 文档对代码 | 有问题 | 3 |
| L4 模块审查 | 有问题 | 7 |
| L5 架构审查 | 有问题 | 4 |
| L6 性能 | 有问题 | 3 |

共 28 个问题，没有 P0。最严重的是 P1 里的几条：A1 和 A2 是说明文档写的函数不存在、默认值写错，照着做会失败；A3 是发信失败也报成功，读者可能永远收不到续借通知；A4 是列表页显示的续借上限（3）和实际上限（2）对不上；A11 是读者列表对每个读者各查一次借阅表，读者一多就会明显变慢。

注意：A8（loan 与 mailer 的循环依赖）是脚本按 import 报的。mailer 里引用 `Loan` 只在 `TYPE_CHECKING` 下面，运行时并不构成循环，这条的严重度可能偏高，留给用户判断。

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

### A3 · P1 · L4 · 发信失败也返回成功，错误被吞掉

- 是什么：`send()` 的文档写的是“返回是否成功”，但不管发没发成功，都返回 `True`。地址格式错误时，它先抛出异常，又被 `except Exception` 接住，然后还是 `return True`。
- 影响：读者邮箱写错了，续借后系统以为通知已经发出，读者永远收不到，也没有任何记录或报错。
- 位置：`src/library/notify/mailer.py` 的 `send()`，第 14–20 行
- 证据：第 16 行 `raise ValueError("bad address")`；第 19 行 `except Exception:`；第 20 行 `return True`。地址里没有 `@` 时，结果也是 `True`。
- 怎么改：`except` 里返回 `False` 并记录原因，或者直接把错误抛给调用方；函数的返回值要和文档一致。
- 来源：U11

### A4 · P1 · L4 · 读者列表里的「上限」和真正的续借上限对不上

- 是什么：`member_page()` 每条记录里的 `max` 字段用的是 views 里的 `MAX_RENEWALS = 3`，但真正拦住续借的是 loan 模块里的 `MAX_RENEWALS = 2`。列表页告诉读者的上限和实际不一样。
- 影响：读者看到“还能续 3 次”，实际第 3 次就会被拒。页面给的信息是错的。
- 位置：`src/library/api/views.py` 的 `member_page()`，第 20 行
- 证据：第 20 行 `"max": MAX_RENEWALS`，这里的 `MAX_RENEWALS` 在第 11 行定义为 3；`src/library/loan/loan.py` 第 7 行定义为 2，`renew()` 用的是这个。
- 怎么改：只保留一处定义（放在 loan 模块），views 从那里导入。
- 来源：U5

### A5 · P1 · L4 · 表名写错时返回空列表，调用方以为没有数据

- 是什么：`query()` 和 `page()` 用 `self.rows.get(table, [])` 取数据。表名拼错或表不存在时，不报错，直接返回空列表。
- 影响：调用方看到“没有数据”，会当成正常结果继续往下走。比如读者列表会显示“0 条借阅”，查不出来的原因永远不会被发现。
- 位置：`src/library/db/store.py` 的 `query()`，第 12 行（`page()` 同样在第 16 行）
- 证据：第 12 行 `return [r for r in self.rows.get(table, []) ...]`；第 16 行 `return self.rows.get(table, [])[...]`。没有任何分支处理表不存在。
- 怎么改：表不存在时抛出明确的错误（比如 KeyError 或自定义异常），不要悄悄返回空列表。
- 来源：U7

### A6 · P1 · L4 · 续借测试只看邮件有没有被调用，测不出续借逻辑错

- 是什么：`test_renew_sends_mail()` 把 `mailer.send` 整个 mock 掉，然后只断言它被调用过。没有检查到期日是不是加了 14 天、续借次数是不是加了 1、超过上限会不会报错。
- 影响：到期日算错、上限不生效，这些测试都会通过。测试看着全绿，实际测不出续借出错。
- 位置：`tests/test_library.py` 的 `test_renew_sends_mail()`，第 13–16 行
- 证据：第 14 行 `mock.patch.object(loan_mod.mailer, "send")`；第 16 行 `assert send.called`，是唯一的断言。`MAX_RENEWALS` 的 `raise ValueError` 和到期日计算都没有用例。
- 怎么改：补用例：检查 `due` 加了 14 天、`renew_count` 加了 1，超过上限时抛 `ValueError`。
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

### A10 · P1 · L5 · 续借上限在两个模块各定义一次，值已经不一样

- 是什么：`MAX_RENEWALS` 在 api 的 views 里定义为 3，在 loan 模块里定义为 2。两处说的是同一件事（续借上限），但值不一样，而且已经不一致。
- 影响：列表页显示的上限和真正生效的上限对不上，读者会被误导（见 U5 的问题）。以后改一处，另一处很可能忘了改。
- 位置：`src/library/api/views.py` 第 11 行；`src/library/loan/loan.py` 第 7 行
- 证据：`views.py` 第 11 行 `MAX_RENEWALS = 3`；`loan.py` 第 7 行 `MAX_RENEWALS = 2`。脚本 U4 也报了这两处值不同。
- 怎么改：只留 loan 模块里的一处定义，api 从 loan 导入。
- 来源：U13

### A11 · P1 · L6 · 读者列表页对每个读者各查一次借阅表，而且一次全拉出来

- 是什么：`member_page()` 先取出全部读者，然后在循环里，每个读者再去查一次借阅表。列表页也没有用 store 里现成的分页方法，读者一多就是一整串查询。
- 影响：读者数翻几倍，列表页要查的次数跟着翻几倍，页面会明显变慢。这是常见的 N+1 查询问题。
- 位置：`src/library/api/views.py` 的 `member_page()`，第 18–19 行
- 证据：第 18 行 `db.query("members")` 一次取出所有读者；第 19 行在 `for` 循环里 `db.query("loans", member_id=member["id"])`，每个读者查一次。`PAGE_SIZE` 已经定义（第 10 行）但这里没用到。
- 怎么改：借阅一次查出来，按读者编号分组后再组装结果；列表页也改成按页取数据。
- 来源：U6

### A12 · P1 · L6 · 每次查询都从头扫一遍整张表

- 是什么：`query()` 每次都把整张表的每一行逐条比对，没有按字段建索引。查借阅时，就是在全部借阅记录里线性找。
- 影响：借阅记录越多，每次查询越慢；配合读者列表的逐个查询（见 U6），总比较次数是“读者数 × 借阅数”，数据一大就明显变慢。
- 位置：`src/library/db/store.py` 的 `query()`，第 12 行
- 证据：第 12 行 `[r for r in self.rows.get(table, []) if all(r.get(k) == v for k, v in where.items())]`，每次调用都遍历整张表。
- 怎么改：按常用字段（比如 `member_id`）建一次索引（字典），之后查询直接取。
- 来源：U8

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

### A25 · P2 · L4 · 续借函数里顺带发邮件、写日志文件

- 是什么：`renew()` 续借成功后，直接调邮件模块发通知，还直接往 `/tmp/renew.log` 写一行日志。续借和通知、日志写在同一个函数里。
- 影响：以后要改通知方式（比如改成短信），就得动续借代码，容易把续借改坏；测续借时也得先处理邮件和文件。
- 位置：`src/library/loan/loan.py` 的 `renew()`，第 27–28 行
- 证据：第 27 行 `mailer.send(loan.member_email, mailer.renew_notice(loan))`；第 28 行 `open("/tmp/renew.log", "a", ...)`。
- 怎么改：`renew()` 只改数据并返回结果，通知和日志交给调用方或单独的事件处理。
- 来源：U9

### A26 · P2 · L4 · 续借函数改了传入的对象，说明里没写清楚

- 是什么：`renew()` 直接改传进来的 `Loan` 对象（次数加一、到期日往后推），然后返回同一个对象。说明里只写了“续借一次，并通知读者”，没写会改传入对象、会写日志文件。
- 影响：调用方不知道自己手里的对象被改了，可能重复续借或拿着旧值比较，出错时很难查。
- 位置：`src/library/loan/loan.py` 的 `renew()`，第 25–26 行
- 证据：第 25 行 `loan.renew_count += 1`；第 26 行 `loan.due = loan.due + timedelta(days=RENEW_DAYS)`；第 22 行的说明没提这两点。
- 怎么改：在说明里写清楚会原地修改传入对象；或者改成返回新对象，不动原来的。
- 来源：U9

### A27 · P2 · L4 · 续借时不检查通知有没有发成功

- 是什么：`renew()` 调用 `mailer.send()` 后，不看它的返回值。通知失败了，续借照样算成功。
- 影响：读者可能没收到续借通知，但系统已经显示续借成功，没人会发现。根子在 notify 模块（见 U11 的问题），这里是调用方没接住。
- 位置：`src/library/loan/loan.py` 的 `renew()`，第 27 行
- 证据：第 27 行 `mailer.send(...)` 的结果直接丢弃。
- 怎么改：检查返回值，失败时记录或报错；同时修 notify 模块的返回值（见 U11）。
- 来源：U9

### A28 · P2 · L6 · 发过的每封邮件都留在内存里，只增不减

- 是什么：`SENT` 是模块级的列表，每发一封就往里面加一条，没有清空，也没有上限。
- 影响：服务一直开着，内存会一直涨，发的邮件越多涨得越多。现在不会马上出事，但会慢慢变坏。
- 位置：`src/library/notify/mailer.py` 的 `send()`，第 17 行
- 证据：第 9 行 `SENT: list[tuple[str, str]] = []` 是模块级列表；第 17 行 `SENT.append((to, text))`，全项目找不到任何清空或限长的地方。
- 怎么改：不需要长期保留的话删掉这个列表；需要保留时，改成写到持久存储或设上限。
- 来源：U12

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

模型：claude-haiku-5-5（本次派不了子 agent，由执行者逐单位代做）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 没问题 | `src/library/loan/loan.py` 没有循环查库或调接口 |
| 没有重复计算 | 没问题 | `src/library/loan/loan.py` 没有重复计算 |
| 数据结构用得合适 | 没问题 | `src/library/loan/loan.py` 的 `dispatch()` 用字典查处理函数，没有大列表查找 |
| 没有不必要的等待 | 没问题 | `src/library/loan/loan.py` 的 `renew()` 调用的 `mailer.send()` 现在只往内存列表里追加，不阻塞；真接 SMTP 时要重新看 |
| 资源用完会释放 | 没问题 | `src/library/loan/loan.py` 的 `renew()` 用 `with open(...)` 写日志，自动关闭 |

### U11 · L4 模块审查 · src/library/notify

模型：claude-haiku-5-5（本次派不了子 agent，由执行者逐单位代做）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 没问题 | `src/library/notify/mailer.py` 只管发信和拼通知文字 |
| 对外接口说清楚 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 14–20 行 |
| 错误情况处理清楚 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 14–20 行 |
| 测试真在测 | 没法判断 | `notify` 模块没有自己的测试；`tests/test_library.py` 里的续借测试把 `mailer.send` 整个 mock 掉了，测不到发信本身 |

### U12 · L6 性能 · src/library/notify

模型：claude-haiku-5-5（本次派不了子 agent，由执行者逐单位代做）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 没问题 | `src/library/notify/mailer.py` 没有循环查库或调接口 |
| 没有重复计算 | 没问题 | `src/library/notify/mailer.py` 没有重复计算 |
| 数据结构用得合适 | 没问题 | `src/library/notify/mailer.py` 的发信记录用列表顺序追加，没有大量查找 |
| 没有不必要的等待 | 没问题 | `src/library/notify/mailer.py` 没有阻塞等待 |
| 资源用完会释放 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 17 行 |

### U13 · L5 架构审查 · src/library/api、src/library/db、src/library/loan、src/library/notify

模型：claude-haiku-5-5（本次派不了子 agent，由执行者逐单位代做）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 同一信息只在一处维护 | 有问题 | `src/library/api/views.py` 第 11 行；`src/library/loan/loan.py` 第 7 行 |
| 模块放对地方 | 没问题 | 分层问题（db 依赖 api）已由脚本报出，见 A5，这里不重复记 |
| 没有绕过既有抽象 | 没问题 | 发通知只有 `notify/mailer.py` 这一条路径，没有另造一套 |
| 以前定的约束还守着 | 没法判断 | 项目副本里没有 `docs/spec/` 目录，engineering 约束、“架构：”约束和 D 规则都找不到，没法逐条核对 |
| 没有多余的抽象 | 没问题 | `dispatch()` 和 `HANDLERS` 的死代码问题已由 U2 记为 A14，这里不另开问题；删掉只影响测试，属于死代码，不是抽象问题 |

### U14 · L2 死代码 · 拿不准的候选 2 个

模型：claude-haiku-5-5（本次派不了子 agent，由执行者逐单位代做）

| 检查项 | 结论 | 位置 |
|---|---|---|
| renew | 没问题 | `src/library/loan/loan.py` 的 `renew()`，第 21 行。`tests/test_library.py` 的 `test_renew_sends_mail()` 直接调用它，`src/library/loan/readme.md` 也把它写成使用入口，是对外入口 |
| handle_overdue | 没法判断 | `src/library/loan/loan.py` 的 `handle_overdue()`，第 33 行。项目里只能经 `dispatch("overdue")` 按字符串名字找到它，而 `dispatch()` 在生产代码里没有调用方。要判断是否真的没用，得看项目外有没有服务调用 `dispatch("overdue")` |

### U15 · L3 文档对代码 · src/library/loan

模型：claude-haiku-5-5（本次派不了子 agent，由执行者逐单位代做）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 功能描述对得上 | 没问题 | `src/library/loan/readme.md` 第 3、7 行说的“到期日往后延、最多续 MAX_RENEWALS 次、收到通知邮件”，和 `src/library/loan/loan.py` 的代码一致 |
| 使用方式能用 | 没问题 | `src/library/loan/readme.md` 第 11 行写的 `renew()` 用法能跑通；它提到的 `extend_loan()` 不存在，这一点已由 U3 的 A1 记录，这里不重复记 |
| 关键函数说明对得上 | 没问题 | `src/library/loan/readme.md` 点名的 `renew()`、`dispatch()` 都存在；说明只列了名字，没写 `dispatch()` 是做什么 |
| spec 索引还对 | 没法判断 | `src/library/loan/readme.md` 第 24 行的链接指向的 spec 在项目副本里找不到（已由 U3 的 A17 记录），所以没法核对 spec 里说的关系还成不成立 |

### U5 · L4 模块审查 · src/library/api

模型：claude-haiku-5-5（本次派不了子 agent，由执行者逐单位代做）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 没问题 | `src/library/api/views.py` 的 `member_page()` 只统计借阅数；`week_header()` 只做表头 |
| 对外接口说清楚 | 有问题 | `src/library/api/views.py` 的 `member_page()`，第 20 行 |
| 错误情况处理清楚 | 没问题 | `src/library/api/views.py` 只做查询，不吞错误 |
| 测试真在测 | 没问题 | `tests/test_library.py` 的 `test_member_page()` 断言了真实的借阅数 |

### U6 · L6 性能 · src/library/api

模型：claude-haiku-5-5（本次派不了子 agent，由执行者逐单位代做）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 有问题 | `src/library/api/views.py` 的 `member_page()`，第 18–19 行 |
| 没有重复计算 | 没问题 | `src/library/api/views.py` 的 `week_header()` 每次只算 7 天表头，成本可忽略 |
| 数据结构用得合适 | 没问题 | `src/library/api/views.py` 没有大量查找 |
| 没有不必要的等待 | 没问题 | `src/library/api/views.py` 没有阻塞等待 |
| 资源用完会释放 | 没问题 | `src/library/api/views.py` 不打开文件或连接 |

### U7 · L4 模块审查 · src/library/db

模型：claude-haiku-5-5（本次派不了子 agent，由执行者逐单位代做）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 没问题 | `src/library/db/store.py` 的 `DB` 只负责按表取行 |
| 对外接口说清楚 | 没问题 | `src/library/db/store.py` 的 `query()` 和 `page()` 的参数清楚 |
| 错误情况处理清楚 | 有问题 | `src/library/db/store.py` 的 `query()`，第 12 行（`page()` 同样在第 16 行） |
| 测试真在测 | 没法判断 | `DB` 没有自己的测试，只有 `tests/test_library.py` 的 `test_member_page()` 间接经过 `query()`；`page()` 没有任何测试 |

### U8 · L6 性能 · src/library/db

模型：claude-haiku-5-5（本次派不了子 agent，由执行者逐单位代做）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 没问题 | `src/library/db/store.py` 本身没有循环查库；循环在 views 里（见 U6） |
| 没有重复计算 | 没问题 | `src/library/db/store.py` 没有重复计算 |
| 数据结构用得合适 | 有问题 | `src/library/db/store.py` 的 `query()`，第 12 行 |
| 没有不必要的等待 | 没问题 | `src/library/db/store.py` 是同步的内存操作，没有等待 |
| 资源用完会释放 | 没问题 | `src/library/db/store.py` 不占用外部资源 |

### U9 · L4 模块审查 · src/library/loan

模型：claude-haiku-5-5（本次派不了子 agent，由执行者逐单位代做）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 有问题 | `src/library/loan/loan.py` 的 `renew()`，第 27–28 行 |
| 对外接口说清楚 | 有问题 | `src/library/loan/loan.py` 的 `renew()`，第 25–26 行 |
| 错误情况处理清楚 | 有问题 | `src/library/loan/loan.py` 的 `renew()`，第 27 行 |
| 测试真在测 | 有问题 | `tests/test_library.py` 的 `test_renew_sends_mail()`，第 13–16 行 |

