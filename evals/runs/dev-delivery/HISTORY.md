# dev-delivery · 运行历史

测什么：看到 xdev coverage / xdev check 的结果后，agent 知不知道下一步；交付不再另写测试报告。题面在 `evals/problems/dev-delivery/`，答案与考点在 `evals/answers/dev-delivery/`。

每次运行的产物在 `iteration-N/run-M/` 下：`answer.json` 是答题 agent 交的答案，`grading.json` 是评分结果。分数按当时的题目和答案计算；之后修过的题，老分数不再重算。

| iteration | 结果 | 发生了什么 |
|---|---|---|
| 1 | 12/13 ×2 | 首次运行。D03（新文件不在报告里）两次都答“按根因修好”：题面没说清是缺测试还是覆盖率范围没配。注：iteration-1 的 grading.json 是选项改名后重算的，D02 用的是旧选项名，所以显示 11/13 |
| 2 | 13/13 ×2 | D03 写明“范围配置没问题，只是还没有测试调用它”；选项“按根因修好再重跑”改名为“修好失败的测试再重跑”，只用于测试失败 |
