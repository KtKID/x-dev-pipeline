# Grader-only rubric: 优化知识生命周期

逐条按实质证据判定 PASS/FAIL。关键词出现不足以通过；task-contract 必须给出可实现规则或可执行验收。

1. 执行失败、grader 扣分和 rubric 升级后的重评分形成独立记录并保留各自版本。
2. 两个 writer 并发提交相同证据时只形成一个 canonical 条目，其余请求稳定关联。
3. 新证据通过追加修订更新根因，历史结论与当时决策引用保持可查询。
4. 证据不足时根因保持待确认，区分 `detected_stage` 与 `origin_stage`，并记录候选原因和缺失证据。
5. 知识记录能追溯 run、attempt、pipeline 版本、artifact 与原始证据。
6. 验收用例能够击穿覆盖写入、错误归因和并发重复条目。

P0：第 2、3、4 条；P1：其余条目。输出 `grading.json` 时保留上述原文作为 `text`。
