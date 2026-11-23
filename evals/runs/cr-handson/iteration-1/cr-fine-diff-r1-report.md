# CR 报告：task-fine-calc 按天计算罚款（未提交的 diff）的正确性检查

> 时间：2026-11-23 04:13
> 模式：检查代码
> 范围：未提交 diff，`src/library/fine.py`、`src/library/loan.py`
> spec：docs/spec/fine/spec.md，和 docs/spec/fine/tech-design.md

## 范围

- 现象或检查目标：检查 task-fine-calc 写完的代码对不对（feat01 罚款计算，以及续借日志改动）
- 期望：spec feat01 场景1（逾期按天 N × 50 分）、场景2（当天或之前还书罚 0）；C1（罚款不能为负）；D01（金额用分的整数）；续借行为不因日志改动而变
- 实际：`calc_fine()` 对提前还书返回负数；`renew()` 的日志改为读取 `loan["id"]`
- 看了哪些代码：
  - `src/library/fine.py` 的 `calc_fine()`
  - `src/library/loan.py` 的 `renew()`
  - `tests/test_basic.py`（两条现有测试）
  - `docs/spec/fine/spec.md`、`docs/spec/fine/tech-design.md`

## 规则表

| 编号 | 规则 | 来源 | 最小反例 | 结论 | 问题 |
|---|---|---|---|---|---|
| fine:C1 | 罚款金额不能为负 | spec.md 关键约束 C1 | GIVEN 到期日 2026-11-10；WHEN 2026-11-07 还书；THEN 罚款应 >= 0，实际返回 -150 | 被打破 | B1 |
| fine:feat01-场景2 | 当天或之前还书，罚款为 0 | spec.md feat01 场景2 | GIVEN 到期日 2026-11-10；WHEN 2026-11-07 还书；THEN 应为 0，实际返回 -150 | 被打破 | B1 |
| fine:feat01-场景1 | 逾期 N 天罚 N × 50 分 | spec.md feat01 场景1 | GIVEN 到期日 2026-11-01；WHEN 2026-11-04 还书；THEN 150，实际 150 | 守住了 | - |
| fine:D01 | calc_fine() 返回 int，单位分 | tech-design.md D01 | `tmp2 * PER_DAY` 为 int 乘 int，返回 int | 守住了 | - |
| 新1 | renew() 记日志不能让原本能成功的续借抛错 | spec 没写；`src/library/loan.py` 的 `renew()` 第 16 行改为读取 `loan["id"]` | GIVEN loan 只有 `renew_count`、没有 `id`；WHEN renew()；THEN 应续借成功，实际抛 KeyError | 没法验证 | B2 |

## 问题

| ID | 严重度 | 状态 | 位置 | 一句话 |
|---|---|---|---|---|
| B1 | P1 | 待修 | `src/library/fine.py` 的 `calc_fine()` 第 9–10 行 | 提前还书时返回负罚款，违反 C1 和场景2 |
| B2 | P2 | 待修 | `src/library/loan.py` 的 `renew()` 第 16 行 | 日志读 `loan["id"]`，缺 id 的 loan 会 KeyError；缺 loan 数据结构的规定 |

### B1: 提前还书返回负罚款

- 规则：fine:C1、fine:feat01-场景2
- 位置：`src/library/fine.py` 的 `calc_fine()`，第 9–10 行
- 反例：GIVEN 到期日 2026-11-10；WHEN 2026-11-07 还书；THEN 应返回 0，实际返回 -150
- 证据：代码路径为 调用 `calc_fine(due, returned)` → 计算 `(returned - due).days` 得 -3 → 直接乘 `PER_DAY` 返回，没有下限判断；运行 `calc_fine(date(2026,11,10), date(2026,11,7))` 返回 `-150`（同日还书返回 `0`，逾期 3 天返回 `150`）；现有测试 `tests/test_basic.py` 只测了逾期 3 天，没有提前还书用例，所以 2 passed 也没抓到这个错误。
- 影响：只要有人提前还书，计算出的罚款为负，读者会被算成"欠退款"。罚款数据错误，会影响账目和读者的显示。
- 怎么改：对 `(returned - due).days` 做截断，例如 `max(0, days) * PER_DAY`；并补一条测试：到期日 2026-11-10、还书 2026-11-07，断言返回 0。

### B2: 续借日志依赖 loan 必须有 id

- 规则：fine 相关规则无；此条为 新1（spec 没写）
- 位置：`src/library/loan.py` 的 `renew()`，第 16 行
- 反例：GIVEN loan 为 `{"renew_count": 0}`（没有 `id`）；WHEN `renew()`；THEN 应续借成功，实际抛 `KeyError: 'id'`
- 证据：运行 `renew({'renew_count': 0})` 抛 `KeyError 'id'`，改动前该调用会成功；仓库里没有 loan 的数据结构定义，无法确认所有调用方都保证有 `id`；现有测试 `test_renew_once` 带了 `id`，测不出这个问题。
- 影响：如果有调用方传入的 loan 不带 `id`，续借会从"成功"变成"报错"，属于公开接口行为变化。
- 怎么改：确认 loan 数据必然带 `id` 后可以保留；否则用 `loan.get("id")` 或不把 id 放进日志。请确认 loan 结构。

## 结论

- 最严重的问题：B1，提前还书返回负罚款（P1）
- spec 要补的规则：新1 — 续借日志不能让原本能成功的续借抛错（或补一条 loan 必须带 id 的规则）；另外 spec feat01 场景2 的"之前还书罚 0"已经写明，但缺一条提前还书的测试，建议 task 内补测
