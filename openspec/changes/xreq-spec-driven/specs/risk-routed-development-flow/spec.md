# risk-routed-development-flow Delta

## MODIFIED Requirements

### Requirement: Unified risk-routed task flow

活跃 task 流程 SHALL 以 task `dev-checklist.md` 头部的 `risk: Q0|Q1|Q2|Q3` 路由。x-dev SHALL 在实现后运行确定性 verify；Q0/Q1 在 verify 通过后完成交付，Q2 SHALL 进入 RC 综合评审，Q3 SHALL 依次进入 R1、R2、R3。verify 失败、uncovered 或 qa-gate issue SHALL 按现有 fix-counter 与批量修复回流规则进入 x-fix。

#### Scenario: Q1 通过 verify 后交付

- **GIVEN** task checklist 头部声明 `risk: Q1` 且 verify 没有 fail 或 uncovered
- **WHEN** x-dev 收尾
- **THEN** 流程输出完成回执，不创建 qa-gate 路由

#### Scenario: Q3 通过 verify 后进入高风险门禁

- **GIVEN** task checklist 头部声明 `risk: Q3` 且 verify 没有 fail 或 uncovered
- **WHEN** x-dev 收尾
- **THEN** 流程按 R1、R2、R3 的顺序启动 qa-gate 审查

### Requirement: Minimal Gate evidence and confidence discipline

x-verify SHALL 在 verify 全过时只输出对话回执，在失败或 uncovered 时才写失败报告。qa-gate SHALL 按 reviewer 类型读取指定的 diff、dev-report verify 块或测试文件；验收对照对象 SHALL 为归属 `spec.md` 的 Requirement/Scenario，SHALL NOT 读取 README、changelog 或 qdev 专属输入。每个 issue SHALL 提供 `file:line` 与可执行修复建议；只有可指认位置且可复现的 issue 可标记 P0，其他不确定 issue SHALL 降低一级。

#### Scenario: Verify 全过

- **GIVEN** verify 返回退出码 0
- **WHEN** x-verify 执行 Gate ①
- **THEN** 它输出 pass 与 manual 清单，不创建 verify 报告文件

#### Scenario: Reviewer 对照 spec.md 验收

- **GIVEN** task 进入 RC/R1，验收真源在归属 `spec.md`
- **WHEN** reviewer 读取验收对照对象
- **THEN** 它读取归属 `spec.md` 的 Requirement/Scenario，不读取 README

#### Scenario: Reviewer 发现无法复现

- **GIVEN** reviewer 无法提供位置或复现依据
- **WHEN** reviewer 记录 issue
- **THEN** 该 issue 的严重度低于 P0，并含可执行的进一步验证或修复建议
