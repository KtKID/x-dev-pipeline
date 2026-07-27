# Iteration 6 pipeline skill snapshot

执行顺序：

1. `x-spec3`
2. `x-adversarial-risk`
3. `x-req3`
4. `x-dev`
5. `x-verify`
6. `x-qa-gate`
7. `x-fix`

本迭代冻结 iteration-5 的七个执行技能，并把对抗审查压缩为四轮：一次读取、一次集中修改、一次验证、一次回执。

对抗审查的读取轮次由一个批量工具调用组成，同时取得 `x-adversarial-risk/SKILL.md`、目标 Spec 和五张通用风险短卡。复杂度与重要性决定单轮候选搜索深度，Scenario 数量由实际区分缺口决定。

真实 eval 的运行时验收读取 session JSONL，要求对抗阶段满足：

- 工具调用共 3 次：批量读取、集中 patch、聚合 `validate-review`。
- 模型推理共 4 轮：读取决策、修改决策、验证决策、最终回执。
- 读取调用同时包含 skill、Spec 和示例，后续没有额外读取或探测。
