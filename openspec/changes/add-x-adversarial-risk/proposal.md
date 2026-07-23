## Why

现有 Spec 风险检查依赖通用模型自审，固定评分器能够给出相同分数，却可能漏掉 compact 崩溃窗口、语义一致性和逻辑损坏分类等真实缺口。需要在 Spec 交给 x-req3 前增加独立、按风险预算执行且可持续吸收已确认缺口的对抗性检查。

## What Changes

- 新增 `x-adversarial-risk` skill：读取已生成的 Spec，按复杂度与重要性评分选择标准、深度或全面对抗预算，并把可复现风险补成 Scenario。
- 扩展新生成的 x-spec3 文档：记录复杂度分、重要性分、平均分、预算等级和审查状态；每个 Scenario 标记来自第一版或对抗性审查。
- 新增独立错题集，只允许 `x-adversarial-risk` 在对抗性检查或录入已确认缺口时读取；每个 issue 固定记录动作、数据和场景三个维度。
- 以本轮 journal recovery 评估发现的持久化完整性问题作为首批错题，并记录被破坏不变量、最小反例、应补 Scenario 和证据来源。
- 新增标准库校验脚本及回归测试，机械检查评分计算、预算升级、审查状态、Scenario 来源和错题集结构。
- x-req3 对采用新风险契约的 Spec 检查审查状态，`pending` 状态保持草案并阻断任务拆解；存量 Spec 保持兼容。

## Capabilities

### New Capabilities

- `adversarial-spec-risk-review`: 定义 Spec 风险评分、动态审查预算、错题集渐进加载、对抗性 Scenario 来源追溯和 x-req3 交接门禁。

### Modified Capabilities

无。

## Impact

- 新增：`skills/x-adversarial-risk/`、风险契约校验脚本、测试 fixture 与回归测试。
- 修改：`skills/x-spec3/SKILL.md`、`skills/x-spec3/templates/spec.md`、`skills/x-req3/SKILL.md` 及主流程文档。
- 运行时只依赖本地 Markdown 与 Python 标准库，不引入网络、外部服务或第三方包。
- 新契约通过显式风险版本标记生效；未带标记的存量 Spec 继续按原契约使用。
