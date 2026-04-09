# 持续开发驱动机制

> ⚠️ **当前主方案已替换为 [00-simplified-plan.md](./00-simplified-plan.md)**（2026-04-09）
> 本 README 及 `02-module-breakdown.md` / `90-task-map.md` 描述的是 v1 完整版方案，作为历史参考保留。
> 简化原因与取舍见 00-simplified-plan.md 的「为什么不做 v1 完整版」章节。

> 状态：历史版本（v1）
> 目标：将 superpowers 的连续开发驱动机制移植到 x-dev-pipeline 项目

## 系统目标

在 x-dev-pipeline 中建立一套可持续数小时运行的开发驱动机制，核心能力包括：
1. 阶段流水线自动推进（设计 → 计划 → 执行 → 审查 → 收尾）
2. 多任务连续执行，支持中途 session 断开后从断点恢复
3. 每小时强制 checkpoint，用户可随时叫停或继续

## 范围边界

**包含**：
- 新增 `x-finish` skill（收尾决策，四选一）
- 新增 `x-drive` skill（连续开发编排层，负责任务调度 + checkpoint + 断点恢复）
- 扩展 `x-req`（增加设计文档输出能力）
- 扩展 `x-dev`（增加 subagent 驱动执行模式）
- 新增 session-start hook 配置（持续上下文注入）
- checkpoint 机制设计

**不包含**：
- 修改已有的 x-plan / x-cr / x-fix / x-qdev 核心逻辑
- 创建独立的 subagent 执行框架（复用的 x-dev 子能力）
- 实现跨设备同步（TodoWrite 依赖 Claude Code 持久化）

## 模块导航

| 模块 | 状态 | 文档 | 可否进 x-req | 说明 |
|------|------|------|-------------|------|
| x-finish（收尾决策） | 方案确认 | `./02-module-breakdown.md#x-finish` | 是 | 新增 skill；独立性强，无前置依赖 |
| x-req 扩展（设计文档） | 方案确认 | `./02-module-breakdown.md#x-req-ext` | 是 | 扩展现有 skill；扩展点清晰 |
| x-drive（连续编排层） | 方案确认 | `./02-module-breakdown.md#x-drive` | 否 | 方案细化：六类停止条件 + 唤醒机制 + reviewer 硬编码循环 |
| x-dev-ext（subagent 驱动） | 方案确认 | `./02-module-breakdown.md#x-dev-ext` | 否 | 新增：implementer 四状态机 + 模型选择策略 |
| session-start hook | 探索中 | `./02-module-breakdown.md#session-hook` | 否 | 需要验证 Claude Code hook 能力 |

## 新增元规则（来自 superpowers 核心设计）

> **"IF A SKILL APPLIES, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT."**
> **skill 文本本身就是程序。驱动力 = 没有等待人类的设计。**

影响：
- x-cr spec-review 阶段必须**独立验证**，不能信任 implementer 自我报告
- reviewer 循环硬编码：发现问题 → implementer 修复 → 重新审核 → **无人类等待窗口**
- implementer 必须实现四种状态汇报（DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT）
- x-drive checkpoint 强制执行，不依赖用户主动询问

## 文档导航

- [模块拆分](./02-module-breakdown.md)
- [Task 映射](./90-task-map.md)

## 当前建议

1. **优先级 1（可立即进入 x-req）**：`x-finish` skill + `x-req-ext` 扩展——可并行开发
2. **优先级 2（等第一批完成后）**：`x-drive` + `x-dev-ext` 合并开发
3. **优先级 3（探索中）**：session-start hook——用 CLAUDE.md 手动配置替代方案
