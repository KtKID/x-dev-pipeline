# change-sync · 运行历史

测什么：需求变化同步：spec 变了，D、T、任务行、测试怎么动。题面在 `evals/problems/change-sync/`，答案与考点在 `evals/answers/change-sync/`。

每次运行的产物在 `iteration-N/run-M/` 下：`answer.json` 是答题 agent 交的答案，`grading.json` 是当时的评分结果。分数按当时的题目和答案计算；之后修过的题，老分数不再重算。

| iteration | 结果 | 发生了什么 |
|---|---|---|
| 4 | 7/7、6/7 | C02 一次判 D01 要改：fixture 里 D01 写死了"第 6 本"，判得对，是题目错。D01 改成"不会因为并发超过上限" |
| 5 | 7/7 ×2 | 修题后复跑 |
