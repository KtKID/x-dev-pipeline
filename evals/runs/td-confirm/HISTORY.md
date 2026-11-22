# td-confirm · 运行历史

测什么：tech-design 不需要用户确认，只有会改变使用者看到的结果的取舍才单独问；x-req 不因 tech-design 没被用户看过而停下。题面在 `evals/problems/td-confirm/`，答案与考点在 `evals/answers/td-confirm/`。

每次运行的产物在 `iteration-N/run-M/` 下：`answer.json` 是答题 agent 交的答案，`grading.json` 是当时的评分结果。

| iteration | 结果 | 发生了什么 |
|---|---|---|
| 1 | 6/6 ×2 | 首次运行，为 pipeline-skills feat06 补的验收题 |
| 2 | 4/6、5/6 | x-tech-design 加了架构偏好后复跑。T03 被答成“直接交给 x-req”、T05 被答成 qdev 的选项：题面没说清答题者是 x-req、是不是在 qdev 里 |
| 3 | 6/6 ×2 | T03 题面写明“你现在是 x-req”，T05 写明“主线（不在 x-qdev 里）”，答案不变 |
| 4 | 6/6 ×2 | x-tech-design 改成读 spec 关键约束（含架构约束）后复跑 |
| 5 | 6/6 ×2 | 改名 x-ask-spec，x-tech-design 措辞“探索”改“讨论”后复跑 |
| 6 | 6/6 ×2 | x-tech-design 只读本 spec 约束、不另设回归用例后复跑 |
