# 运行账本开发契约

读取提供的 `inputs/spec.md`，为“运行账本与版本绑定”生成可直接交给开发 agent 的 `task-contract.md`。

产物需要给出目标与范围、数据和状态契约、状态所有者、实现 checklist、验收用例及可复跑证据。重点处理生产环境中的重复请求、时序变化、失败恢复和版本一致性。合理假设必须显式写出。

只读取题面和 `inputs/spec.md`。只输出一个非空 `task-contract.md`。不修改代码，不读取其他 spec、eval、rubric 或历史对话。
