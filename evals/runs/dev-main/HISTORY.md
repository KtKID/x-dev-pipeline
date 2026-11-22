# dev-main · 运行历史

测什么：主 agent 在多 agent 协作里的下一步。题面在 `evals/problems/dev-main/`，答案与考点在 `evals/answers/dev-main/`。

每次运行的产物在 `iteration-N/run-M/` 下：`answer.json` 是答题 agent 交的答案，`grading.json` 是当时的评分结果。分数按当时的题目和答案计算；之后修过的题，老分数不再重算。

| iteration | 结果 | 发生了什么 |
|---|---|---|
| 9 | 13/13 ×2 | 首次运行，可能偏简单 |
| 10 | 14/14 ×2 | 改成新核对流程：每组主 agent 自己跑覆盖率核对（M01、M02），整体先跑覆盖率和 xdev check（M08），新增 M14（Q1 也交 x-qa-gate） |
| 11 | 14/14 ×2 | 全部合并后整体跑覆盖率，再交 x-verify-spec 验收；M08/M09/M12/M14 随之改 |
| 12 | 14/14 ×2 | 同上 |
