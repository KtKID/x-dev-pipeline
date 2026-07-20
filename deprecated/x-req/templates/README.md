# <task-name>

<!--
x-req README 模板填写规则：
- 先写 risk: Q0|Q1|Q2|Q3。Q0/Q1 只保留核心目标和验收；Q2/Q3 保留完整章节。
- 验收是 DoD 的唯一事实源：每个 Requirement 至少一个 Scenario；Scenario 有 WHEN、THEN、验证: auto|manual。
- 验证: auto 的场景必须由 dev-report.md 一个 auto verify 块以 scenario: 精确回指。
- 自动化测试责任固定在验收节内；x-dev 在 dev-report.md 写真实 verify 块。
- 需求、模块、架构和技术设计只写本 task 增量，引用已有 spec，不复制背景。
-->

> 创建时间：YYYY-MM-DD
> 类型：功能 / 修复 / 优化 / 重构
> spec: <有归属 spec 填 docs/spec/<spec-name>；项目未建 docs/spec 则留空>

risk: <Q0|Q1|Q2|Q3>

## 核心目标

[一句话说明这个 task 要做什么、为什么做]

## 需求要点

1. [确认过的需求要点 1]
2. [确认过的需求要点 2]

## 涉及模块

- 模块名：参考 `spec: docs/spec/<spec-name>`，改动 `repo:src/module/...`

## 架构拆分策略

| 维度 | 结论 |
|------|------|
| 主边界 | [主模块 / 边界类 / 外部入口] |
| 公开契约 | [输入 / 输出 / 错误 / 状态副作用] |
| 数据流 | [上游 → 边界层 → 核心模块 → 下游] |
| 风险与依赖 | [risk 理由、任务依赖顺序] |

## 技术设计

- 架构归属：[XxxService / XxxManager / XxxRepository]
- 外部入口：[统一进入的函数 / 命令 / API]
- 事实源：[schema / config / prompt / API contract / spec]
- 失败路径：[错误、降级、停止或恢复策略]

## 验收

### Requirement: <行为域名>

<一句话需求描述，使用 SHALL/MUST 表达可验证行为。>

#### Scenario: <场景名>

- **GIVEN** <前置状态；可省略>
- **WHEN** <触发条件>
- **THEN** <可观察结果>
- 验证: auto

### 自动化测试责任

- x-dev 必须补齐改动逻辑的单元、契约、边界测试，并在 `dev-report.md` 写入对应 verify 块。

## 文件导航

- [开发清单](./dev-checklist.md)
- 模块/组件图：`diagram.md`（可选产物，存在时查看）
