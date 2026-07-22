# 优化知识生命周期开发契约

读取提供的 `inputs/spec.md`，为“失败与扣分知识库”生成可直接交给开发 agent 的 `task-contract.md`。

产物需要给出目标与范围、记录类型、身份和关联关系、状态所有者、并发写入策略、修订生命周期、实现 checklist、验收用例及可复跑证据。合理假设必须显式写出。

只读取题面和 `inputs/spec.md`。只输出一个非空 `task-contract.md`。不修改代码，不读取其他 spec、eval、rubric 或历史对话。
