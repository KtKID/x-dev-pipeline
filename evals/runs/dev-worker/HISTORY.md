# dev-worker · 运行历史

测什么：工人子 agent 遇到越界情况怎么做。题面在 `evals/problems/dev-worker/`，答案与考点在 `evals/answers/dev-worker/`。

每次运行的产物在 `iteration-N/run-M/` 下：`answer.json` 是答题 agent 交的答案，`grading.json` 是当时的评分结果。分数按当时的题目和答案计算；之后修过的题，老分数不再重算。

| iteration | 结果 | 发生了什么 |
|---|---|---|
| 9 | 10/10 ×2 | 首次运行，可能偏简单 |
| 10 | 10/10 ×2 | parallel-dev 改成新核对流程后复跑 |
| 11 | 12/12 ×2 | 新增 W11（只满足约束、场景没做）、W12（没读场景就动手）：约束只是任务的一部分 |
