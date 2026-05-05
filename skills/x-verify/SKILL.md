---
name: x-verify
description: |
  Gate ① 事实验证 skill。读取 dev-report.md 中的命令清单，逐条复跑，对比实际 exit code 与关键输出片段。任一不一致即拦下，调 x-fix 修复。
  本 skill 只做客观事实判断，不做主观代码质量判断。
  自动触发场景：x-dev / x-qdev 完成任务后立即触发。
  手动触发场景：用户要求"验证 dev-report"、"复跑验证命令"、"verify"、"check exit codes"。
  **不信任自我报告**：dev-report 里的"自检结论"不算数，必须自己跑一遍。
---

# x-verify · Gate ① 事实验证

x-verify 是质量门禁链路的第一层 gate。它只做一件事：**读 dev-report.md 中声明的验证命令清单，逐条复跑，看 exit code 与关键输出是否符合声明**。如果不符合，就生成 verify-report 并调用 x-fix 修复。

x-verify **不主观判断代码质量**——那是下游 x-qua-gate 的职责。

## 输入

- 当前 task 目录下的 `dev-report.md`（由 x-dev / x-qdev 产出）

## 流程

```
读 dev-report.md → 解析命令表 → 逐条复跑 → 比对 exit + 关键输出 →
  ├─ 全部一致 → 生成 verify-report (status: pass) → 触发 x-qua-gate
  └─ 任一不一致 → 生成 verify-report (status: fail) → 触发 x-fix
```

## 硬约束

1. **不裁剪命令**：dev-report 列了 N 条必须跑 N 条，不许跳过任何一条。
2. **不主观判断**：只看 exit code 和关键输出片段是否出现。不评价代码风格、不审查逻辑。
3. **不修改命令**：dev-report 写什么命令就跑什么命令，不许"我觉得这条命令应该改成 X"。
4. **真跑，不模拟**：必须用 Bash 工具执行，不允许"看起来应该能跑"就跳过。
5. **fix-attempts 计数**：每次拦下并触发 x-fix 都算 1 次，与 x-qua-gate 共用 6 次上限。

## 比对规则

逐条命令按下表比对：

| 字段 | 比对方式 | 不一致处理 |
|------|---------|-----------|
| exit code | 实际 exit == 预期 exit | fail |
| 关键输出片段 | grep 实际 stdout/stderr 含 "关键输出片段" 字面 | fail |

某条 fail 即整体 fail，但仍须**跑完所有命令**后再生成报告（不要短路），方便一次性反馈给 x-fix。

## 报告输出

写入 `reports/verify/verify-report-YYYYMMDD-HHmmss.md`，格式见 `templates/verify-report-template.md`。

## 下游

- pass → 触发 x-qua-gate（自动）
- fail → 触发 x-fix（mode: verify-fix），fix-attempts +1

## 6 次上限（与 x-qua-gate 共享 fix-counter）

**fix-counter 协议**：

- 路径：`<task>/reports/.fix-counter`，格式：单行 ASCII 整数 + 换行
- **首次创建责任在 x-verify**：进入 x-verify 时，如 `reports/.fix-counter` 不存在 → `mkdir -p reports && echo 0 > reports/.fix-counter`
- 读取时 `c=$(cat reports/.fix-counter)`
- 触发 x-fix 时（命令复跑出现 fail）：先递增 `echo $((c+1)) > reports/.fix-counter` 再交给 x-fix
- counter < 6：递增并触发 x-fix（mode: verify-fix）
- counter >= 6：**不递增**，停下生成 `reports/fix-blocked-report.md` 列出所有积压问题，等用户决策（继续 / 修改需求 / 放弃）

**重置时机**：整个 verify → R1 → R2 → R3 链路全部 pass 时，由 x-qua-gate 在 R3 通过后 `echo 0 > reports/.fix-counter`。x-verify 不负责重置。
