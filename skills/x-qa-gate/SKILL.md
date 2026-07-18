---
name: x-qa-gate
description: |
  Gate ② 质量门禁。README risk Q2 走 RC，Q3 串行走 R1、R2、R3；reviewer 一轮列全问题候选，主 agent 通过 xdev flag 登记 issue 并交 x-fix 批量修复。
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

主 agent 提供文件路径、节名、`git diff --stat`、`git diff --name-only` 和按需 diff 命令。reviewer 按需读取源代码与测试文件。

## Review 纪律

- RC 一轮覆盖契约、边界、测试真实性；Q3 严格串行 R1、R2、R3。
- 每个 reviewer 独立、只读，只返回 review 回执；x-fix 负责改动。
- 每轮穷尽检查范围后一次返回全部问题候选，并声明“已检查范围内无其他 P0/P1”。
- 每条候选固定提供 `task`、`severity`、`loc`、`msg`；`task` 可为 `T2,T3`，`severity` 为 P0/P1/P2，`loc` 为 `file:line`，`msg` 为单条问题描述。
- reviewer 省略 issue ID。主 agent 调用 `flag` 后使用其 JSON `issue` 字段建立编号映射。
- P0 需要位置与可复现依据；证据不完整时降级。P0 或未处置 P1 使本轮 fail；P2 登记且保持非阻塞。

## issue 登记

主 agent 按 reviewer 返回顺序逐条执行：

```text
python3 tools/xdev.py flag <task-dir> --task T2,T3 --severity P0 \
    --loc src/a.py:10 --msg "空输入未处理" [--new-round] --json
```

1. 本轮第一条候选添加 `--new-round`；后续候选追加到同一 ledger。
2. 保存 JSON 返回的 `issue`、`downgraded`、`report`、`recovered`，把 issue ID 回填到交给 x-fix 的问题映射。
3. `recovered:true` 表示命令完成了上一笔 pending 事务；主 agent 使用原参数再次调用，完成本条候选登记。
4. `flag` 是 issue ledger 与 P0/P1 checklist 降级的唯一写入口。reviewer、子 agent 与 x-fix 保持这两处原样。
5. 本轮无问题时省略 ledger 创建，直接进入 Gate pass 回执。

## 回流

本轮存在 P0/P1 时，主 agent 把带 `issue-<n>` 的完整问题映射交给 x-fix `gate-fix`。修复后复审对应 issue 与 fix diff；fix 扩大到新文件时纳入新文件，公开 API 签名变化时重做相关契约对照。`reports/.fix-counter` 是 verify 与 qa-gate 共享的批量修复轮数，保留三轮上限；Gate ② 最终 pass 写回 0。

## Prompt 模板

```text
Agent({
  description: "<RC/R1/R2/R3> review round <N>",
  subagent_type: "general-purpose",
  prompt: <对应 reference + task root + 输入裁剪表指定路径/节 + diff 命令 + 输出格式>
})
```

## 回执与状态

问题 ledger 由 `flag` 写入 `reports/qa-gate/qa-gate-report-<timestamp>[-NN].md`。通过时输出：

```text
🛡️ Gate② ✅ · <task> · Q2 RC / Q3 R1→R2→R3 · P0 ×0 · P1 ×0
```

失败回执列出 issue ID、严重度、task、位置和 x-fix 去向。最终通过后，主 agent 亲自确认复审结果并把已解除阻塞的 checklist 状态升为 `[x] ✅`。
