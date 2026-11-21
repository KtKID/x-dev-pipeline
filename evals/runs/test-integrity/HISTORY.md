# test-integrity · 运行历史

测什么：最便宜的模型只凭 `skills/x-dev/references/test-integrity.md` 的清单，能不能分出真测试和假测试，并且不误报。题面在 `evals/problems/test-integrity/`，答案与考点在 `evals/answers/test-integrity/`。

每次运行的产物在 `iteration-N/run-M/` 下：`answer.json` 是答题 agent 交的答案，`grading.json` 是评分结果。分数按当时的题目和答案计算；之后修过的题，老分数不再重算。

| iteration | 结果 | 发生了什么 |
|---|---|---|
| 1 | 13/13 ×2 | 首次运行，为 pipeline-skills feat11 场景2 补的验收题 |
| 2 | 13/13 ×2 | 冲突检查指出 I01/I08/I04 的分类边界清单没写清，补了“用生产常量照抄公式也算重写”“没 import 项目代码归没调用项目代码”“存储层可以 mock”后复跑 |
