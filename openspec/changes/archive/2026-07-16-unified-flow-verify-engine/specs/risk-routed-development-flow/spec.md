## ADDED Requirements

### Requirement: Unified risk-routed task flow
活跃 task 流程 SHALL 以 README `risk: Q0|Q1|Q2|Q3` 路由。x-dev SHALL 在实现后运行确定性 verify；Q0/Q1 在 verify 通过后完成交付，Q2 SHALL 进入 RC 综合评审，Q3 SHALL 依次进入 R1、R2、R3。verify 失败、uncovered 或 qa-gate finding SHALL 按现有 fix-counter 与批量修复回流规则进入 x-fix。

#### Scenario: Q1 通过 verify 后交付
- **GIVEN** task README 声明 `risk: Q1` 且 verify 没有 fail 或 uncovered
- **WHEN** x-dev 收尾
- **THEN** 流程输出完成回执，不创建 qa-gate 路由

#### Scenario: Q3 通过 verify 后进入高风险门禁
- **GIVEN** task README 声明 `risk: Q3` 且 verify 没有 fail 或 uncovered
- **WHEN** x-dev 收尾
- **THEN** 流程按 R1、R2、R3 的顺序启动 qa-gate 审查

### Requirement: Minimal Gate evidence and confidence discipline
x-verify SHALL 在 verify 全过时只输出对话回执，在失败或 uncovered 时才写失败报告。qa-gate SHALL 按 reviewer 类型读取指定的 diff、README 节、dev-report verify 块或测试文件，不读取 changelog 或 qdev 专属输入。每个 finding SHALL 提供 `file:line` 与可执行修复建议；只有可指认位置且可复现的 finding 可以标记 P0，其他不确定 finding SHALL 降低一级。

#### Scenario: Verify 全过
- **GIVEN** verify 返回退出码 0
- **WHEN** x-verify 执行 Gate ①
- **THEN** 它输出 pass 与 manual 清单，不创建 verify 报告文件

#### Scenario: Reviewer 发现无法复现
- **GIVEN** reviewer 无法提供位置或复现依据
- **WHEN** reviewer 记录 finding
- **THEN** 该 finding 的严重度低于 P0，并包含可执行的进一步验证或修复建议

### Requirement: Retire parallel qdev and x-plan routes
活跃插件 SHALL 不再包含 `x-qdev` 或 `x-plan` skill 目录，也不再在 skills、安装输出、插件 manifest 或 README 中引用它们。小型任务 SHALL 由 x-req 定级为 Q0/Q1 后进入统一 task 流程；历史 task 与归档 change 保持原文。

#### Scenario: 新小任务使用统一入口
- **GIVEN** 用户提出单模块低风险小任务
- **WHEN** 活跃文档或 skill 路由描述下一步
- **THEN** 它指向 x-req 的 Q0/Q1 定级与 x-dev 续接

#### Scenario: 活跃发布面无遗留入口
- **GIVEN** 删除完成
- **WHEN** 在活跃 skills、README、install.sh 与 plugin manifest 搜索 `qdev` 或 `x-plan`
- **THEN** 搜索不返回匹配项
