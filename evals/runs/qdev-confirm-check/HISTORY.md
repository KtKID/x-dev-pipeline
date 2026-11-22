# qdev-confirm-check · 运行历史

测什么：qdev 对账：x-verify-spec 能否发现改了场景却没记用户确认。题面在 `evals/problems/qdev-confirm-check/`，答案与考点在 `evals/answers/qdev-confirm-check/`。

每次运行的产物在 `iteration-N/run-M/` 下：`answer.json` 是答题 agent 交的答案，`grading.json` 是当时的评分结果。分数按当时的题目和答案计算；之后修过的题，老分数不再重算。

| iteration | 结果 | 发生了什么 |
|---|---|---|
| 4 | 6/6 ×2 | 首次运行 |
| 5 | 6/6 ×2 | 规则搬到 x-verify-spec 做法第 3 步，结论改用“核对通过 / 未完成 / 不通过”后复跑 |
| 6 | 6/6 ×2 | 确认规则扩到“改了场景或约束（含 engineering 的约束）”后复跑 |
| 7 | 6/6 ×2 | x-qa-gate 并进 x-verify-spec 后复跑；人工检查挪到“做法”第 4 步，单项结论仍叫核对通过 / 未完成 / 不通过 |
