# CR 报告：task-fine-calc 未提交改动的正确性检查

> 时间：2026-11-23 04:13
> 模式：检查代码
> 范围：当前 git 未提交改动（`src/library/fine.py`、`src/library/loan.py`）
> spec：docs/spec/fine/spec.md，docs/spec/fine/tech-design.md（loan 的 spec 也读了，只关联续借部分）

## 范围

- 现象或检查目标：检查 task-fine-calc 的未提交代码是否正确（calc_fine 按天计罚；续借日志补借阅编号）
- 期望：spec fine 的 C1（罚款不能为负）、feat01 场景1/场景2、tech-design D01（金额用分的整数）；spec 没写的，按代码明显该守的规则判
- 实际：跑 `python3 -m pytest -q`，2 个测试通过。手动试 calc_fine：同一天还书返回 0，提前 1 天还书返回 -50，提前 5 天还书返回 -250。
- 看了哪些代码：
  - `src/library/fine.py` 的 `calc_fine()`
  - `src/library/loan.py` 的 `renew()`
  - `tests/test_basic.py`
  - `docs/spec/fine/spec.md`、`docs/spec/fine/tech-design.md`、`docs/spec/loan/spec.md`
  - `src/library/member.py`、`src/library/__init__.py`（确认无其它调用方）

## 规则表

| 编号 | 规则 | 来源 | 最小反例 | 结论 | 问题 |
|---|---|---|---|---|---|
| fine:C1 | 任何还书情况下 calc_fine() 返回值 >= 0 | spec.md 关键约束 C1 | GIVEN 到期日 2026-11-01 WHEN 2026-10-31 还书 THEN 返回 -50，违反 >= 0 | 被打破 | B1 |
| fine:feat01-场景1 | 逾期 N 天罚 N × 50 分 | spec.md feat01 场景1 | GIVEN 到期日 2026-11-01 WHEN 2026-11-04 还书 THEN 返回 150 | 守住了 | - |
| fine:feat01-场景2 | 当天或之前还书，罚款为 0 | spec.md feat01 场景2 | GIVEN 到期日 2026-11-01 WHEN 2026-10-31 还书 THEN 返回 -50，应为 0 | 被打破 | B1 |
| fine:D01 | calc_fine() 返回 int，单位分 | tech-design.md D01 | 任意输入：返回值是 int（tmp2 为 int，乘 PER_DAY 仍是 int） | 守住了 | - |
| 新1 | 续借失败时，借阅记录不能被改了一半（renew_count 已加但异常抛出） | spec 没写；`src/library/loan.py` 的 `renew()` 第 14–15 行 | GIVEN 借阅记录没有 "id" 字段 WHEN renew() 续借 THEN 抛 KeyError，且 renew_count 已从 0 变为 1 | 没法验证 | B2 |

## 问题

| ID | 严重度 | 状态 | 位置 | 一句话 |
|---|---|---|---|---|
| B1 | P1 | 待修 | `src/library/fine.py` 的 `calc_fine()`，第 9–10 行 | 提前还书时没有判断，直接用负的天数算罚款，返回负数 |
| B2 | P2 | 待修 | `src/library/loan.py` 的 `renew()`，第 14–15 行 | 日志行新读 loan["id"]，借阅记录缺 id 时抛错且计数已加，缺 spec 规则和调用方证据 |

### B1: 提前还书返回负罚款

- 规则：fine:C1、fine:feat01-场景2
- 位置：`src/library/fine.py` 的 `calc_fine()`，第 9–10 行
- 反例：GIVEN 到期日 2026-11-01 WHEN 2026-10-31 还书 THEN 应返回 0，实际返回 -50。到期日前 5 天还书实际返回 -250。
- 证据：代码路径：入口 `calc_fine(due, returned)` → 直接计算 `(returned - due).days` → 乘 PER_DAY 返回，中间没有 `max(0, ...)` 或早退判断。跑过 `PYTHONPATH=src python3 -c ...`：同一天返回 0，提前 1 天返回 -50，提前 5 天返回 -250。现有测试只测了逾期 3 天（150），没测提前还书，所以测试没抓住这个错。
- 影响：任何提前还书的读者，只要走到罚款计算，都会得到负数。罚款数字错，依赖它的账务会少收或倒付钱。
- 怎么改：在 `calc_fine()` 里先判断 `returned <= due` 时直接返回 0，再算逾期天数乘 PER_DAY。补一条测试：到期日前还书，断言结果为 0。

### B2: renew() 的日志依赖 loan["id"]，失败时计数已改

- 规则：新1
- 位置：`src/library/loan.py` 的 `renew()`，第 14–15 行
- 反例：GIVEN 借阅记录 `{"renew_count": 0}`（没有 id） WHEN renew() THEN 抛 KeyError，且记录变成 `{"renew_count": 1}`，计数已加但续借没成功。
- 证据：跑过上面的反例，结果是 `raised KeyError 'id'`，`state after {'renew_count': 1}`。仓库里没有其它调用 renew() 的代码（`src/library/member.py`、`src/library/__init__.py` 均无），所以不知道真实借阅记录是否总带 id，无法判断线上会不会走到。loan spec 只写了上限 2 次，没写日志或字段要求。
- 影响：如果真实数据里有不带 id 的记录，续借会报错，而且计数已被改掉，下次再续借就少一次机会。
- 怎么改：先确认借阅记录一定有 id 字段，确认后可以接受现状；或者把日志放到计数加之前，或用 `loan.get("id")` 避免 KeyError。补 spec 规则：借阅记录必须带 id，续借失败时 renew_count 不变。

## 原因排查

不适用：查的是检查代码，不是已知问题，原因一眼可见，本节删除。

## 结论

- 最严重的问题：B1，calc_fine() 提前还书返回负罚款，违反 fine:C1 和 fine:feat01-场景2。
- spec 要补的规则：新1 续借失败不留半截（借阅记录必须带 id，失败时 renew_count 不变）。请用户确认后补进 spec（本次不改 spec）。另外建议在 `fine` spec 里补一条“提前还书不罚，罚款不为负”的 C 约束，并给 feat01 加一条提前还书的场景测试。
