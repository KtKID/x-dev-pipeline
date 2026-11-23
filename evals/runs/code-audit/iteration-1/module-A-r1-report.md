# 代码巡检报告 · 055d1b4c
<!-- x-code-audit:{"files": ["src/library/notify/__init__.py", "src/library/notify/mailer.py"], "modules": ["src/library/notify"], "doc_modules": ["src/library/notify"], "prev": null} -->

> 检查 ID：055d1b4c
> 开始时间：2026-11-23 08:28
> 状态：完成
> 代码版本：307b0d0
> 上次巡检：无
> 范围：指定模块 src/library/notify
> 层：L1、L2、L3、L4、L5、L6

## 范围

- 模块（1 个）：src/library/notify
- 文件：2 个，清单在「检查进度」下面

## 结论

| 层 | 结果 | 问题数 |
|---|---|---|
| L1 机器检查 | 有问题 | 5 |
| L2 死代码 | 没问题 | 0 |
| L3 文档对代码 | 没问题 | 0（notify 没有 readme，脚本没有可核对的内容） |
| L4 模块审查 | 有问题 | 3 |
| L5 架构审查 | 有问题 | 2 |
| L6 性能 | 有问题 | 1 |

没有 P0。最严重的是 A1：`send()` 遇到地址错误时吞掉异常并返回 True，续借通知会被当成已发出，读者收不到，也没人知道。A2 说明测试全是 mock，测不出这个问题。A3 是脚本报的循环依赖，经核对，`mailer.py` 引用 `Loan` 只在 `TYPE_CHECKING` 下，运行时不成立；影响和严重度以 A10（P2）为准，A3 里“导入错误”的说法作废。

本次没有改动任何代码，只新增了 `reports/audit/audit-055d1b4c.md`。派不了子 agent，三个子 agent 单位（U5、U6、U7）由主 agent 逐个做，回执格式照旧，模型记为 claude-haiku-5-5。

## 问题

### A1 · P1 · L4 · send() 发送失败也报成功，调用方以为邮件已经发出

- 是什么：`send()` 写着“返回是否成功”，但 `try` 里的地址检查一旦失败（比如地址里没有 @），`except` 直接 `return True`，失败原因被整个吞掉。
- 影响：地址写错的续借通知会被当成已经发出，读者收不到，也没有任何报错，管理员无从发现。
- 位置：`src/library/notify/mailer.py` 的 `send()`，第 14–20 行
- 证据：第 15–16 行 `raise ValueError("bad address")` 被第 19–20 行 `except Exception: return True` 吞掉；`loan.py` 第 27 行调用 `mailer.send(...)` 之后，续借照常完成。
- 怎么改：失败时返回 False 或把异常抛给调用方，让 `renew()` 能决定怎么处理。
- 来源：U5

### A2 · P1 · L4 · 测试只断言 mock 被调用，发送失败的情况没人测

- 是什么：`test_renew_sends_mail()` 把 `mailer.send` 整个换成假的，只检查它被调用过。`notify` 模块自己没有任何测试。
- 影响：上面“发送失败也报成功”的问题，测试全绿，永远测不出来；以后改坏地址检查，测试照样通过。
- 位置：`tests/test_library.py` 的 `test_renew_sends_mail()`，第 13–16 行
- 证据：第 14 行 `mock.patch.object(loan_mod.mailer, "send")` 把被测的发送函数整个替换；第 16 行只断言 `send.called`。
- 怎么改：给 `send()` 补测试：地址错误时应返回 False（或抛异常）；地址正确时确认 `SENT` 里多了一条记录。
- 来源：U5

### A3 · P1 · L5 · 循环依赖：loan.py 和 mailer.py 互相引用

- 是什么：这几个文件互相 import，形成一个环：`src/library/loan/loan.py` → `src/library/notify/mailer.py` → `src/library/loan/loan.py`。
- 影响：改其中一个就可能牵动另一个，测试也没法单独测；启动顺序稍有变化还可能直接报导入错误。
- 位置：`src/library/loan/loan.py`
- 证据：依赖路径：src/library/loan/loan.py → src/library/notify/mailer.py → src/library/loan/loan.py
- 怎么改：把两边共用的部分抽到第三个模块，让依赖只朝一个方向
- 来源：U4

### A4 · P2 · L1 · 缺少 lint 规则：命名规范（ruff N）

- 是什么：项目没有配置「命名规范（ruff N）」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：在 ruff 的 select 里加上 "N"
- 来源：U1

### A5 · P2 · L1 · 缺少 lint 规则：函数太复杂（ruff C90）

- 是什么：项目没有配置「函数太复杂（ruff C90）」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：在 ruff 的 select 里加上 "C90"，并设 max-complexity
- 来源：U1

### A6 · P2 · L1 · 缺少 lint 规则：CI 里跑 ruff

- 是什么：项目没有配置「CI 里跑 ruff」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：在 CI（如 .github/workflows/ci.yml）里加一步 `ruff check .`
- 来源：U1

### A7 · P2 · L1 · 缺少 lint 规则：Python 类型检查（mypy）

- 是什么：项目没有配置「Python 类型检查（mypy）」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：加 [tool.mypy]
- 来源：U1

### A8 · P2 · L1 · 缺少 lint 规则：Python 格式化（black 或 ruff format）

- 是什么：项目没有配置「Python 格式化（black 或 ruff format）」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：加 [tool.black]，或在 CI 跑 `ruff format --check`
- 来源：U1

### A9 · P2 · L4 · send() 的返回值永远是 True，接口说的和做的不一样

- 是什么：`send()` 的说明写“返回是否成功”，但所有路径都返回 True，返回值传不出任何失败信息。
- 影响：以后谁用这个返回值判断发没发，都会得到错误答案；接口看起来可靠，其实不可靠。
- 位置：`src/library/notify/mailer.py` 的 `send()`，第 12–20 行
- 证据：第 17 行成功分支 `return True`，第 20 行失败分支也是 `return True`，整个函数里没有 `return False`。
- 怎么改：失败时返回 False，和说明保持一致。
- 来源：U5

### A10 · P2 · L5 · 脚本报的循环依赖只在类型注解里，运行时并不成立

- 是什么：脚本报 `loan.py` 和 `mailer.py` 互相 import。但 `mailer.py` 引用 `Loan` 的那行写在 `if TYPE_CHECKING:` 下面，程序运行时不会执行，两边在运行时并没有互相导入。
- 影响：报告里“启动顺序稍有变化还可能直接报导入错误”的说法不成立。这个环只是给类型检查器看的。它仍说明 notify 和 loan 彼此认识，改一边要留意另一边的类型；风险比脚本默认的 P1 小，所以降为 P2。
- 位置：`src/library/notify/mailer.py` 的 `renew_notice()`，第 6–7 行
- 证据：第 6–7 行 `if TYPE_CHECKING:` 和 `from library.loan.loan import Loan`；运行时唯一的导入方向是 `src/library/loan/loan.py` 第 5 行 `from library.notify import mailer`。
- 怎么改：`renew_notice()` 改成只接收需要的字段（如 loan_id、due），不再 import `Loan`，这个环就没有了。
- 来源：U7

### A11 · P2 · L6 · 已发通知一直留在内存里，只增不减

- 是什么：`SENT` 是模块级列表，每发一封就 append 一条 `(地址, 正文)`，从来不清空，也不限长度。
- 影响：通知越多，进程占用的内存越大，而且一直回收不掉；长期运行的服务里会慢慢涨。按现在的代码和量，看不出多快会出问题。
- 位置：`src/library/notify/mailer.py` 的 `send()`，第 9 行和第 17 行
- 证据：第 9 行 `SENT: list[tuple[str, str]] = []`；第 17 行 `SENT.append((to, text))`；全项目只有这两处用到 `SENT`。
- 怎么改：不需要的话删掉 `SENT`；需要的话改成有上限的队列，或写到外部存储并定期清理。
- 来源：U6

## 检查进度

| 单位 | 层 | 范围 | 谁查 | 状态 |
|---|---|---|---|---|
| U1 | L1 | 范围内全部文件 | 脚本 | 完成 |
| U2 | L2 | 范围内全部文件 | 脚本 | 完成 |
| U3 | L3 | 范围内模块的说明 | 脚本 | 完成 |
| U4 | L5 | 范围内全部文件 | 脚本 | 完成 |
| U5 | L4 | src/library/notify | 子 agent | 完成 |
| U6 | L6 | src/library/notify | 子 agent | 完成 |
| U7 | L5 | src/library/notify | 子 agent | 完成 |

范围内的文件：`src/library/notify/__init__.py`、`src/library/notify/mailer.py`

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
| ruff | ruff check --output-format=concise … | 0 | 0 |

### U2 · L2 死代码

没有找到 0 引用的代码

### U3 · L3 文档对代码（脚本部分）

范围内没有可核对的说明

没有说明文档的模块：src/library/notify（可以用 x-feat-doc 补）

### U4 · L5 架构审查（脚本部分）

循环依赖：
| 依赖路径 |
|---|
| src/library/loan/loan.py → src/library/notify/mailer.py → src/library/loan/loan.py |

分层（按 .x-code-audit.json）：
没有违反

多处定义的常量（交给子 agent 判断是不是同一件事）：
无

### U5 · L4 模块审查 · src/library/notify

模型：claude-haiku-5-5（主 agent 自己逐单位做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 没问题 | `src/library/notify/mailer.py` 的 `send()` 只负责发和记，`renew_notice()` 只负责拼文案 |
| 对外接口说清楚 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 12–20 行 |
| 错误情况处理清楚 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 14–20 行 |
| 测试真在测 | 有问题 | `tests/test_library.py` 的 `test_renew_sends_mail()`，第 13–16 行 |

### U6 · L6 性能 · src/library/notify

模型：claude-haiku-5-5（主 agent 自己逐单位做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 没问题 | `src/library/notify/mailer.py` 没有循环，`send()` 只做一次 append |
| 没有重复计算 | 没问题 | `renew_notice()` 只拼一句字符串 |
| 数据结构用得合适 | 没问题 | 模块里没有查找操作，只有 append |
| 没有不必要的等待 | 没问题 | 没有 sleep，也没有同步网络调用 |
| 资源用完会释放 | 有问题 | `src/library/notify/mailer.py` 的 `SENT`，第 9 行 |

### U7 · L5 架构审查 · src/library/notify

模型：claude-haiku-5-5（主 agent 自己逐单位做，未派子 agent）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 同一信息只在一处维护 | 没问题 | 脚本报的重复定义为空；`src/library/notify/mailer.py` 没有和别处重复的常量 |
| 模块放对地方 | 没问题 | `src/library/notify/mailer.py` 的 `renew_notice()` 只拼文案，不碰数据访问；`.x-code-audit.json` 里 notify 和 loan 同属一层 |
| 没有绕过既有抽象 | 没问题 | 项目里没有别的通知门面，`src/library/loan/loan.py` 第 27 行调用的就是这里的 `send()` |
| 以前定的约束还守着 | 没法判断 | 项目里没有 `docs/spec/engineering/spec.md`，也没有 spec、tech-design 和“架构：”约束，没有可核对的依据 |
| 没有多余的抽象 | 没问题 | `send()` 和 `renew_notice()` 都有真实调用方（`src/library/loan/loan.py` 第 27 行） |

