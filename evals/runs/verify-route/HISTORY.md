# verify-route · 运行历史（原 review-route）

测什么：开发后的验收怎么走（哪种 risk 做不做功能检查、问题算什么严重度、哪些不在每个任务里查、回执存几份、修完怎么关闭），以及架构约束怎么处理。题面在 `evals/problems/verify-route/`，答案与考点在 `evals/answers/verify-route/`。iteration 1–3 是改名前的 review-route（按 risk 派 lens 的独立审查），题目已整体换掉，老分数不再适用。

每次运行的产物在 `iteration-N/run-M/` 下：`answer.json` 是答题 agent 交的答案，`grading.json` 是评分结果。分数按当时的题目和答案计算；之后修过的题，老分数不再重算。

| iteration | 结果 | 发生了什么 |
|---|---|---|
| 1 | 12/12 ×2 | 首次运行，为 pipeline-skills feat09、feat10 补的验收题 |
| 2 | 12/12 ×2 | 架构偏好文件取消，改成 spec 关键约束里“架构：”开头的约束；R05、R09–R11 题面和答案随之改，题面改读 spec 模板和 spec-scope |
| 3 | 12/12 ×2 | 改名 x-ask-spec，spec 模板写入时机改成“讨论结束后”后复跑 |
| 4 | 18/18 ×2 | x-qa-gate 并进 x-verify-spec，题目整体换成验收路由（V01–V18）；冲突检查后补了 FEATURE_CHECK_OPEN、COVERAGE_STALE 后重做功能检查等规则 |
| 5 | 20/20 ×2 | 范围收窄到本轮 spec 和 tech-design：V15 改成本轮没提的开发规范、V16 改成本 spec 的约束；新增 V19（本轮 D 没落实）、V20（本轮用户定的架构约束被违反） |
| 6 | 21/22、22/22 | 严重度加正例反例，新增 V21（测试没测到设计写的结果，代码碰巧对 → P1）、V22（只是写法可简洁 → P2）；V13 改成明确的 P2。错 V12：feature-check.md 和 SKILL.md 对“修完要不要再跑覆盖率”说法不一，已统一 |
| 7 | 22/22、21/22 | 统一后复跑；错 V12：选项里没有“只重做功能检查”这一项，补上 |
| 8 | 22/22、21/22 | 补选项后复跑，V12 两次都对；错 V04：理由写的是“不做功能检查”，却选了 V09 的选项，属模型选错，规则本身清楚，不改 |
