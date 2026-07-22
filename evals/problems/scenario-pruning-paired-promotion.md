# 配对评测与候选晋级开发契约

读取提供的 `inputs/spec.md`，为“可比评测、候选决策与生产晋级”生成可直接交给开发 agent 的 `task-contract.md`。

产物需要给出目标与范围、评测 manifest、状态和版本前置条件、晋级与拒绝规则、实现 checklist、验收用例及可复跑证据。重点处理运行期间状态变化和并发决策。合理假设必须显式写出。

只读取题面和 `inputs/spec.md`。只输出一个非空 `task-contract.md`。不修改代码，不读取其他 spec、eval、rubric 或历史对话。
