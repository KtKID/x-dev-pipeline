// Package req 实现 skills/x-req/scripts/req.py 的等价逻辑：x-req 的自包含确定性 task 引擎。
//
// # 职责
//
// 输入是 docs/spec/<spec>/spec.md 单文件 spec 包，task 位于
// docs/spec/<spec>/tasks/<task>/。本包负责：
//
//   - scaffold：按模板生成 task 骨架（dev-checklist.md、可选 diagram.md）
//   - instructions：返回产物的填写说明与模板
//   - validate：R3Q0-R3Q10 机械校验（spec 指针、风险、Scenario 覆盖、依赖、diagram 一致性等）
//   - status / graph：任务状态进度 + 依赖拓扑排序（Kahn 算法 + 环检测 + 并行批次）
//
// # 设计约束
//
//   - 纯确定性、零外部依赖；不调 LLM、不写代码。
//   - 规则码（R3Q0-R3Q10）与中文错误信息逐字保留，以便与
//     test/test_req_engine.py 对拍，且 SKILL.md 的 agent 路由依赖这些字符串。
//   - 模板文件通过 go:embed 内嵌（templates/dev-checklist.md、templates/diagram.md），
//     等价于 Python 版通过 SKILL_ROOT/templates/ 读取。
package req
