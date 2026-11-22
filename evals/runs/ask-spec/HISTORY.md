# ask-spec · 运行历史

测什么：需求讨论时 agent 会不会主动复述、追问，什么时候才写 spec，超过 5 个 feat 怎么分期。题面在 `evals/problems/ask-spec/`，答案与考点在 `evals/answers/ask-spec/`。

每次运行的产物在 `iteration-N/run-M/` 下：`answer.json` 是答题 agent 交的答案，`grading.json` 是评分结果。分数按当时的题目和答案计算；之后修过的题，老分数不再重算。

| iteration | 结果 | 发生了什么 |
|---|---|---|
| 1 | 12/12 ×2 | 首次运行，为 pipeline-skills feat12 补的验收题 |
| 2 | 12/12 ×2 | x-ask-spec 开始讨论前记时间、写好 spec 后 xdev usage start 后复跑 |
