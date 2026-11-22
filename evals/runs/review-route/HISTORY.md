# review-route · 运行历史

测什么：独立审查按 risk 派几个 lens、问题算哪个 lens 和严重度、架构偏好怎么处理。题面在 `evals/problems/review-route/`，答案与考点在 `evals/answers/review-route/`。

每次运行的产物在 `iteration-N/run-M/` 下：`answer.json` 是答题 agent 交的答案，`grading.json` 是评分结果。分数按当时的题目和答案计算；之后修过的题，老分数不再重算。

| iteration | 结果 | 发生了什么 |
|---|---|---|
| 1 | 12/12 ×2 | 首次运行，为 pipeline-skills feat09、feat10 补的验收题 |
| 2 | 12/12 ×2 | 架构偏好文件取消，改成 spec 关键约束里“架构：”开头的约束；R05、R09–R11 题面和答案随之改，题面改读 spec 模板和 spec-scope |
| 3 | 12/12 ×2 | 改名 x-ask-spec，spec 模板写入时机改成“讨论结束后”后复跑 |
