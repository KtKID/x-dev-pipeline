---
name: x-verify
description: |
  Gate ① 事实验证 skill。读取 dev-report.md 中的命令清单和 task README 的 Smoke/E2E 验收用例，逐条复跑，对比实际 exit code 与关键输出片段。任一不一致即拦下，调 x-fix 批量修复。
  本 skill 只做客观事实判断，不做主观代码质量判断。
  自动触发场景：x-dev 完成任务后立即触发。
  x-qdev 仅在用户明确要求完整门禁时触发，并使用 x-dev 的 gate-compatible dev-report 模板。
  手动触发场景：用户要求"验证 dev-report"、"复跑验证命令"、"verify"、"check exit codes"。
  **不信任自我报告**：dev-report 里的"自检结论"不算数，必须自己跑一遍。
---

# x-verify · Gate ① 事实验证

x-verify 是质量门禁链路的第一层 gate。它只做一件事：**把声明的验证真实复跑一遍，看 exit code 与关键输出是否符合声明**。如果不符合，就生成 verify-report 并调用 x-fix 修复。

x-verify **不主观判断代码质量**——那是下游 x-qa-gate 的职责。深度对抗性问题（边界、失败路径、测试真实性）由 Gate ② 的 reviewer 提出假设，x-fix 修复时把反例固化回本层的可复跑清单——x-verify 的用例集会随任务逐轮变厚。

## 输入（两处必跑清单）

1. 当前 task 目录下符合 `skills/x-dev/templates/dev-report-template.md` schema 的 `dev-report.md` 命令清单
2. task README 的 **Smoke / E2E 验收用例表**：执行方式为命令的逐条复跑；执行方式为人工交互的标 `manual`，不复跑但必须列入报告和回执的"待人工验收"

默认由 x-dev 产出；x-qdev 仅在用户显式选择完整门禁时产出该 schema。dev-report 命令清单与 README 用例重复时只跑一次，报告里标注归属。

## 流程

```
读 dev-report 命令表 + README Smoke/E2E 表 → 逐条复跑 → 比对 exit + 关键输出 →
  ├─ 全部一致 → verify-report (status: pass) → 对话回执 → 触发 x-qa-gate
  └─ 任一不一致 → verify-report (status: fail，含全部 fail 项) → 对话回执 → 触发 x-fix
```

## 执行方式

x-verify **必须 dispatch 一个子 agent** 执行命令复跑，主 agent 不直接跑。

```
Agent({
  description: "x-verify 命令复跑",
  subagent_type: "general-purpose",
  prompt: <dev-report.md 全文 + README Smoke/E2E 用例表 + verify-report-template.md 全文 + 本节硬约束 + 比对规则>
})
```

子 agent prompt 必须自包含：dev-report.md 内容、README 用例表、报告模板、硬约束、比对规则。子 agent 完成后返回 verify-report，并在报告顶部填写 `Completed by model`。主 agent 根据 status (pass/fail) 决定触发 x-qa-gate 还是 x-fix。

## 硬约束

1. **不裁剪命令**：两处清单列了 N 条必须跑 N 条，不许跳过任何一条（`manual` 用例除外——标记后列入待人工验收，不算 pass 也不算 fail）。
2. **不主观判断**：只看 exit code 和关键输出片段是否出现。不评价代码风格、不审查逻辑。
3. **不修改命令**：清单写什么命令就跑什么命令，不许"我觉得这条命令应该改成 X"。
4. **真跑，不模拟**：必须用 Bash 工具执行，不允许"看起来应该能跑"就跳过。
5. **fix-attempts 计数**：x-verify 只做上限检查；进入 x-fix 后由 x-fix 按轮递增，与 x-qa-gate 共用 3 轮上限。

## 比对规则

逐条命令按下表比对：

| 字段 | 比对方式 | 不一致处理 |
|------|---------|-----------|
| exit code | 实际 exit == 预期 exit | fail |
| 关键输出片段 | grep 实际 stdout/stderr 含 "关键输出片段" 字面 | fail |

某条 fail 即整体 fail，但仍须**跑完所有命令**后再生成报告（不要短路），把全部 fail 项一次性交给 x-fix 批量修。

## 报告输出

写入 `reports/verify/verify-report-YYYYMMDD-HHmmss.md`，格式见 `templates/verify-report-template.md`。

## 对话回执（强制）

verify 结束必须在对话中输出回执（报告文件只做存档），零 fail 也要报：

```
🛡️ Gate① verify ✅ · 命令 8/8 通过 · smoke/e2e 3/3 通过 · 待人工验收 1 条
```

fail 时列出全部 fail 项和去向：

```
🛡️ Gate① verify ❌ · 命令 6/8 通过 · smoke/e2e 2/3 通过
├─ #3 `cargo test -p x`（exit 1，预期 0）
├─ #7 e2e 用例 S2（缺关键输出 `passed`）
└→ 已交 x-fix 批量修（第 R/3 轮）
```

## 下游

- pass → 触发 x-qa-gate（自动）
- fail → 触发 x-fix（mode: verify-fix），由 x-fix 按轮递增 fix-counter

## 3 轮上限（与 x-qa-gate 共享 fix-counter）

**fix-counter 协议**：

- 路径：`<task>/reports/.fix-counter`，格式：单行 ASCII 整数 + 换行
- 语义：**批量修轮数**（一轮 = 一份 fail 清单的整体修复），不按问题条数计
- **首次创建责任在 x-verify**：进入 x-verify 时，如 `reports/.fix-counter` 不存在 → `mkdir -p reports && echo 0 > reports/.fix-counter`
- 读取时 `c=$(cat reports/.fix-counter)`
- 触发 x-fix 前（命令复跑出现 fail）：先检查 `c`
- counter < 3：生成 fail 报告（含全部 fail 项）并触发 x-fix（mode: verify-fix）；x-fix 进入修复前写回 `echo $((c+1)) > reports/.fix-counter`
- counter >= 3：保持 counter 原值，停下生成 `reports/fix-blocked-report.md` 列出所有积压问题，等用户决策（继续 / 修改需求 / 放弃）

**重置时机**：Gate ② 最终 pass（默认线 RC pass / 高危线 R3 pass）后，由 x-qa-gate `echo 0 > reports/.fix-counter`。x-verify 不负责重置。
