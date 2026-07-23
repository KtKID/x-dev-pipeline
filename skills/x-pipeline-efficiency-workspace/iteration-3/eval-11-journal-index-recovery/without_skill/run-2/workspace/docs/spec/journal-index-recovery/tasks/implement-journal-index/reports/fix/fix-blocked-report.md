# Gate ② 修复熔断报告

> status: blocked
> fix-attempts: 3 / 3
> trigger: round 4 q3-evidence incremental review

## 未解除问题

| Issue | 严重度 | task | 位置 | 当前事实 |
|---|---|---|---|---|
| issue-10 | P1 | T1,T2,T6 | `fixture/backend/tests/test_journal.py:142` | 实现以 `type(...) is int` 拒绝 float；现有严格类型矩阵未显式加入 `seq=1.0/1.5`、`expected_version=0.0/1.5` 与 float CRC 样本 |

## 审查漂移记录

- Round 1 要求覆盖 seq/expected_version/key/request_id 类型、字段集合与 op。
- Round 2 扩展为七个落盘字段逐字段缺失/重复、完整 CRC 类型矩阵与 JSON 顺序。
- Round 3 扩展为六个 payload 字段 JSON 类型矩阵；本轮已补 null/bool/number/string/array/object，其中数值样本使用整数边界。
- Round 4 在上述处置后继续扩展同一 issue 的 candidate 检查面，新增 JSON 浮点数特例。
- frozen x-fix 规定三轮共享上限；counter 已达 3，本轮不进入第 4 次修复。

## 已通过事实

- issue-1、issue-2、issue-5、issue-6、issue-11 至 issue-15 已由 fresh incremental reviewers 判定 resolved。
- 全量 unittest：14/14 pass，ResourceWarning 按 error 处理。
- Gate①：pass 14、fail 0、manual 0、uncovered 0。

## 所需决策

- 继续：显式授权第 4 轮，仅补浮点 codec/log 分类反例并复审 issue-10。
- 修改门禁：将已由实现严格拒绝、仅缺穷举证据的 issue-10 降为 P2。
- 接受当前交付：保留 Gate① 全绿与 Gate② 熔断事实。
