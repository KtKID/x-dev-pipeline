# Grader-only rubric: 阶段契约与风险路由

逐条按实质证据判定 PASS/FAIL。关键词出现不足以通过；task-contract 必须给出可实现规则或可执行验收。

1. 每个阶段字段定义唯一 producer、consumer 和有效来源，风险、Requirement、Scenario 与报告路径语义一致。
2. consumer 读取退役字段或旧路径时产生可定位 `CONTRACT_DRIFT` 并阻止版本进入 baseline。
3. 公开契约、共享状态、并发或不可逆操作进入完整 spec/task/verify/独立审查路径。
4. 低风险轻量路径保留影子 QA，发现 P0/P1 后形成知识并提高同类任务风险权重。
5. 路由策略有独立版本，run 记录决策输入、profile 和策略版本，可通过历史错误放行率校准。
6. 验收同时覆盖合法新契约、旧字段漂移和路由低估三类反例。

P0：第 1、2、4 条；P1：其余条目。输出 `grading.json` 时保留上述原文作为 `text`。
