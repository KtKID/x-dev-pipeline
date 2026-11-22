# feature-check · 运行历史（原 test-integrity）

测什么：便宜的模型只凭 `skills/x-verify-spec/references/feature-check.md`，能不能分出功能有没有漏做、多做，测试是真是假、有没有测到场景要的结果，并且不误报。题面在 `evals/problems/feature-check/`，答案与考点在 `evals/answers/feature-check/`。iteration 1–3 是改名前的 test-integrity，当时只有 13 题、清单在 `skills/x-dev/references/test-integrity.md`。

每次运行的产物在 `iteration-N/run-M/` 下：`answer.json` 是答题 agent 交的答案，`grading.json` 是评分结果。分数按当时的题目和答案计算；之后修过的题，老分数不再重算。

| iteration | 结果 | 发生了什么 |
|---|---|---|
| 1 | 13/13 ×2 | 首次运行，为 pipeline-skills feat11 场景2 补的验收题 |
| 2 | 13/13 ×2 | 冲突检查指出 I01/I08/I04 的分类边界清单没写清，补了“用生产常量照抄公式也算重写”“没 import 项目代码归没调用项目代码”“存储层可以 mock”后复跑 |
| 3 | 13/13 ×2 | xdev integrity 并进 xdev check，清单里“怎么登记”的说法随之改后复跑 |
| 4 | 16/16 ×2 | 改名 feature-check，清单搬到 x-verify-spec 并加功能部分；新增 I14–I16（没测到场景要的结果、漏了要的、做了没要的），加了“同时符合几类报更具体的”优先规则 |
| 5 | 17/17 ×2 | 功能部分加上本轮 C 和 D；新增 I17（本轮 D 要求具名常量，代码写死） |
