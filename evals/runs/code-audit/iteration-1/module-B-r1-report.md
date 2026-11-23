# 代码巡检报告 · c49ec658
<!-- x-code-audit:{"files": ["src/library/notify/__init__.py", "src/library/notify/mailer.py"], "modules": ["src/library/notify"], "doc_modules": ["src/library/notify"], "prev": null} -->

> 检查 ID：c49ec658
> 开始时间：2026-11-23 08:28
> 状态：完成
> 代码版本：0e6b090
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
| L3 文档对代码 | 没问题 | 0（notify 没有 readme，没有可核对的说明） |
| L4 模块审查 | 有问题 | 3 |
| L5 架构审查 | 有问题 | 2 |
| L6 性能 | 有问题 | 1 |

最严重的问题：A1（P0），`send()` 只把邮件记进内存列表 `SENT`，从不真正发出，续借通知实际上没有送达，而且没有任何报错。另外 `send()` 吞掉所有异常并返回成功（A2，P1）。L5 的 A4（P1）是脚本报的循环依赖，但它来自 `TYPE_CHECKING` 下的类型导入，运行时并不成环。

## 问题

### A1 · P0 · L4 · notify 的发送函数不发任何邮件

- 是什么：`send()` 只把 `(收件人, 正文)` 追加到模块里的列表 `SENT`（第 17 行）就返回 True。整个项目里没有任何代码读取 `SENT`，也没有调用真正的邮件服务（grep 过 smtp、sendmail，都没有）。
- 影响：读者续借成功后，系统以为已经发了通知，但邮件从来不会出去。读者看不到“新到期日”，也没有任何报错。`loan/readme.md` 写的“收到一封通知邮件”不成立。这属于正常使用就会让用户看到错误结果。
- 位置：`src/library/notify/mailer.py` 的 `send()`，第 17 行
- 证据：调用方 `src/library/loan/loan.py` 的 `renew()` 第 27 行调用它；`mailer.py` 第 9 行 `SENT: list[tuple[str, str]] = []`，第 17 行 `SENT.append((to, text))`；全项目 grep `SENT` 只出现在这一个文件里，`smtp`、`sendmail` 无结果。注意：这条属于正确性问题，一般该交 x-cr 深查；巡检顺手发现，照实报。
- 来源：U5

### A2 · P1 · L4 · 发送失败被吞掉，返回成功

- 是什么：`send()` 第 14–20 行用 `except Exception: return True` 把所有异常都吞掉，并且返回 True。收件人地址格式不对时，第 16 行主动抛出的 `ValueError` 也被这里吞掉，函数照样返回 True。
- 影响：收件人地址不合法时，续借照常成功，调用方（`renew()` 第 27 行没有检查返回值）完全不知道通知没发出。以后遇到真实的发送异常，也会被当成“发送成功”，没有日志，没人能发现。
- 位置：`src/library/notify/mailer.py` 的 `send()`，第 14–20 行
- 证据：第 19–20 行 `except Exception:` / `return True`；第 15–16 行 `if "@" not in to: raise ValueError("bad address")`，被第 19 行捕获。文档字符串第 13 行写的是“返回是否成功”，实际从不返回 False。
- 来源：U5

### A3 · P1 · L4 · 测试只断言 mock 被调用，测不出上面两个问题

- 是什么：`tests/test_library.py` 的 `test_renew_sends_mail()` 把 `mailer.send` 整个 mock 掉，只断言 `send.called`。它不检查发出的收件人、正文，也不看返回值。`notify` 模块自己没有任何测试。
- 影响：测试一直是绿的，但发送函数不发邮件、吞错误的问题都不会被发现。以后改坏发送逻辑，测试也不会报警。
- 位置：`tests/test_library.py` 的 `test_renew_sends_mail()`，第 13–16 行
- 证据：第 14 行 `mock.patch.object(loan_mod.mailer, "send")`，第 16 行 `assert send.called`；全仓库没有针对 `mailer.send` 或 `SENT` 的测试。
- 来源：U5

### A4 · P1 · L5 · 循环依赖：loan.py 和 mailer.py 互相引用

- 是什么：这几个文件互相 import，形成一个环：`src/library/loan/loan.py` → `src/library/notify/mailer.py` → `src/library/loan/loan.py`。
- 影响：改其中一个就可能牵动另一个，测试也没法单独测；启动顺序稍有变化还可能直接报导入错误。
- 位置：`src/library/loan/loan.py`
- 证据：依赖路径：src/library/loan/loan.py → src/library/notify/mailer.py → src/library/loan/loan.py
- 怎么改：把两边共用的部分抽到第三个模块，让依赖只朝一个方向
- 来源：U4

### A5 · P2 · L1 · 缺少 lint 规则：命名规范（ruff N）

- 是什么：项目没有配置「命名规范（ruff N）」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：在 ruff 的 select 里加上 "N"
- 来源：U1

### A6 · P2 · L1 · 缺少 lint 规则：函数太复杂（ruff C90）

- 是什么：项目没有配置「函数太复杂（ruff C90）」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：在 ruff 的 select 里加上 "C90"，并设 max-complexity
- 来源：U1

### A7 · P2 · L1 · 缺少 lint 规则：CI 里跑 ruff

- 是什么：项目没有配置「CI 里跑 ruff」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：在 CI（如 .github/workflows/ci.yml）里加一步 `ruff check .`
- 来源：U1

### A8 · P2 · L1 · 缺少 lint 规则：Python 类型检查（mypy）

- 是什么：项目没有配置「Python 类型检查（mypy）」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：加 [tool.mypy]
- 来源：U1

### A9 · P2 · L1 · 缺少 lint 规则：Python 格式化（black 或 ruff format）

- 是什么：项目没有配置「Python 格式化（black 或 ruff format）」这条检查。
- 影响：这类问题现在没有工具把关，只能靠人看，迟早会混进代码。
- 位置：`pyproject.toml`
- 证据：在 `pyproject.toml` 里找不到这条配置
- 怎么改：加 [tool.black]，或在 CI 跑 `ruff format --check`
- 来源：U1

### A10 · P2 · L5 · 续借的通知文字放在通知模块里

- 是什么：`renew_notice(loan: Loan)` 专门为续借拼“借阅 X 已续借，新到期日 Y”这句话，它认识 `Loan` 这个续借业务的对象。通知模块本来应该只负责“把一段文字发给某个地址”，不该知道续借的业务内容。
- 影响：以后续借文案要改、或者再加逾期、罚款的通知，都得去改通知模块，而不是改借阅模块，两边的职责会越来越纠缠。目前规模小，影响有限。
- 位置：`src/library/notify/mailer.py` 的 `renew_notice()`，第 23–24 行；它的参数类型来自第 6–7 行 `if TYPE_CHECKING:` 下的 `from library.loan.loan import Loan`
- 证据：第 23 行 `def renew_notice(loan: Loan) -> str:`，第 24 行 `return f"借阅 {loan.loan_id} 已续借，新到期日 {loan.due}"`；通知模块因此依赖借阅模块的类型。脚本报出的 `loan.py ↔ mailer.py` 循环（见主报告 A1）就来自第 6–7 行这条类型导入，它只在类型检查时生效，运行时并不形成循环。
- 来源：U7

### A11 · P2 · L6 · 发送记录只增不减，长期运行会一直涨内存

- 是什么：模块级列表 `SENT` 每发一封通知就追加一条，没有任何地方清理、限长或持久化。
- 影响：服务长期运行、通知量一直增加时，进程占用的内存会一直涨，不会自己回落。现在通知量小，几个月内不会出事，但会慢慢变坏。注意：这个列表本身是“假发送”（见 U5 的 P0），真正接上邮件服务后，这里要么改成发完即丢，要么改成有上限的队列。
- 位置：`src/library/notify/mailer.py` 第 9 行 `SENT` 的定义，第 17 行 `SENT.append((to, text))`
- 证据：`SENT` 在全项目只有 `mailer.py` 第 9 行定义、第 17 行追加，没有任何清空或取出的代码（grep `SENT` 的结果见 U5）。
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

模型：claude-haiku-5-5（主 agent 自己做，环境没有派子 agent 的工具）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 职责单一 | 没问题 | `src/library/notify/mailer.py` 的 `send()`、`renew_notice()`，只管发通知和拼通知文字 |
| 对外接口说清楚 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 12–13 行：文档写“返回是否成功”，但第 20 行 `except` 分支也返回 True，实际永远返回 True |
| 错误情况处理清楚 | 有问题 | `src/library/notify/mailer.py` 的 `send()`，第 14–20 行 |
| 测试真在测 | 有问题 | `tests/test_library.py` 的 `test_renew_sends_mail()`，第 13–16 行 |

### U6 · L6 性能 · src/library/notify

模型：claude-haiku-5-5（主 agent 自己做，环境没有派子 agent 的工具）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 循环里没有查库或调接口 | 没问题 | `src/library/notify/mailer.py` 全文没有循环，也没有查库或调接口 |
| 没有重复计算 | 没问题 | `src/library/notify/mailer.py` 的 `send()`、`renew_notice()` 没有重复计算 |
| 数据结构用得合适 | 没问题 | `src/library/notify/mailer.py` 没有大量查找 |
| 没有不必要的等待 | 没问题 | `src/library/notify/mailer.py` 没有异步代码，也没有阻塞等待 |
| 资源用完会释放 | 有问题 | `src/library/notify/mailer.py` 第 9 行 `SENT` 列表，第 17 行 `SENT.append(...)` |

### U7 · L5 架构审查 · src/library/notify

模型：claude-haiku-5-5（主 agent 自己做，环境没有派子 agent 的工具）

| 检查项 | 结论 | 位置 |
|---|---|---|
| 同一信息只在一处维护 | 没问题 | 脚本的重复定义结果为“无”；`src/library/notify/mailer.py` 里没有和其他模块重复的常量或文案 |
| 模块放对地方 | 有问题 | `src/library/notify/mailer.py` 的 `renew_notice()`，第 23–24 行 |
| 没有绕过既有抽象 | 没问题 | `src/library/loan/loan.py` 第 27 行通过 `mailer.send()` 发通知，没有另造发送路径 |
| 以前定的约束还守着 | 没法判断 | 项目副本里没有 `docs/spec/` 目录（engineering 约束、各 spec 的“架构：”约束、D 规则都找不到）；`src/library/loan/readme.md` 的 spec 索引指向的 `docs/spec/loan/spec.md` 也不在副本里，无法核对 |
| 没有多余的抽象 | 没问题 | `src/library/notify/mailer.py` 的两个函数都有实际的调用方（`send()` 被 `loan.py` 第 27 行调用，`renew_notice()` 同一行调用） |

