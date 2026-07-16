---
name: x-qa-gate
description: |
  Gate ② 质量门禁。README risk Q2 走 RC，Q3 串行走 R1、R2、R3；reviewer 一轮列全发现并交 x-fix 批量修复。
---

# x-qa-gate · Gate ②

## 路由

读取 README 唯一的 `risk:` 字段：Q2 使用 RC；Q3 使用 R1→R2→R3；Q0/Q1 被显式调用时按 Q2 处理并在回执说明。Gate ① verify exit 0 是进入条件。

## 事实源

1. 用户原始请求、已确认 spec、既有公开契约。
2. 真实调用方、schema/数据约束、改动前测试契约。
3. README 的需求要点、验收、架构拆分策略、技术设计与 dev-checklist。
4. dev-report verify 块、verify JSON 或失败报告、当前 diff。

## 输入裁剪

| Reviewer | 必读输入 |
|---|---|
| RC | diff + README `验收`/`架构拆分策略` + dev-report |
| R1 | diff + README `需求要点`/`验收` |
| R2 | diff + README `技术设计`/`架构拆分策略` |
| R3 | diff + dev-report verify 块 + 测试文件 |

主 agent 提供文件路径、节名、`git diff --stat`、`git diff --name-only` 和按需 diff 命令。reviewer 按需读取源代码与测试文件，不内联大段材料。

## Review 纪律

- RC 一轮覆盖契约、边界、测试真实性；Q3 严格串行 R1、R2、R3。
- 每个 reviewer 独立、只读、输出 mini-report；x-fix 负责改动。
- 每轮先穷尽检查范围，再给 F1..Fn 清单和“无其他 P0/P1”声明。
- finding 必须给 `file:line`、失败或复现路径、可执行修复建议。
- 可指认位置且可复现的 finding 可定 P0；不确定 finding 降一级。
- P0 或未处置 P1 为 fail；P2 登记且不阻塞。

## 回流

reviewer fail 时把同轮完整清单交 x-fix（`gate-fix`）；修复后复审 F# 与 fix diff。fix 改动扩大到新文件时纳入新文件；公开 API 签名变化时重做相关契约对照。`reports/.fix-counter` 是 verify 与 qa-gate 共享的批量修复轮数，保留三轮上限；Gate ② 最终 pass 写回 0。

## Prompt 模板

```
Agent({
  description: "<RC/R1/R2/R3> review round <N>",
  subagent_type: "general-purpose",
  prompt: <对应 reference + task root + 输入裁剪表指定路径/节 + diff 命令 + 输出格式>
})
```

## 回执与报告

聚合 mini-report 与处置表到 `reports/qa-gate/qa-gate-report-<timestamp>.md`。通过时输出：

```
🛡️ Gate② ✅ · <task> · Q2 RC / Q3 R1→R2→R3 · P0 ×0 · P1 ×0
```

失败回执列出 F#、严重度、位置和 x-fix 去向。最终通过后将 checklist 标为 `[x] ✅`。
