---
name: x-qua-gate
description: |
  Gate ② 质量评审 skill（取代 x-cr）。串行 dispatch 3 个 opus 子 agent reviewer：R1 spec 符合性 → R2 边界完整性 → R3 测试真实性。任一 reviewer 失败即触发 x-fix 并回到该 reviewer 重审；全部通过任务才算完成。
  自动触发：x-verify 通过后立即触发。
  手动触发：用户要求"质量门禁"、"qa-gate"、"代码评审"、"review"。
  本 skill **取代老 x-cr**——老的 x-cr 入口仍能调用，但会重定向到本 skill。
  reviewer 子 agent **必须用 model=opus**（写入 dispatch 模板）。
---

# x-qua-gate · Gate ② 质量评审

x-qua-gate 是质量门禁链路的第二层 gate。它前面的 x-verify 已确认"代码能跑"，本 skill 负责回答三个递进问题：

1. **R1：你做的真的是计划要的吗？**（spec 符合性）
2. **R2：你考虑了所有边界吗？**（边界完整性）
3. **R3：你的测试真的在测代码吗？**（测试真实性 / 反镜像化）

三个问题必须按顺序回答——R1 没过谈 R2 没意义（功能错了边界查的也是错代码）；R2 没过谈 R3 没意义（边界漏了测试通过也是侥幸）。

## 输入

- 当前 task 目录下的 `dev-report.md`（命令清单 + 改动文件清单）
- 当前 task 目录下的 `README.md` / `plan.md` / `dev-checklist.md` / `changelog.md`
- 当前 git diff（与 task 起点对比）

## 流程

```
R1 spec-conformance ─ pass ─→ R2 boundary-coverage ─ pass ─→ R3 test-integrity ─ pass ─→ ✅
       │                            │                              │
       ↓ fail                       ↓ fail                         ↓ fail
   触发 x-fix                    触发 x-fix                    触发 x-fix
   (mode: r1-spec-fix)          (mode: r2-boundary-fix)      (mode: r3-test-fix)
   fix-attempts +1              fix-attempts +1              fix-attempts +1
       │                            │                              │
       ↓                            ↓                              ↓
   按 x-fix 回流规则               同左                            同左
   决定回 R1 还是当前              （见 x-fix SKILL.md）
```

## 硬约束

1. **必须串行**：R1 → R2 → R3 顺序固定，不允许并行（否则修了个寂寞）。
2. **每个 reviewer 必须是独立 opus 子 agent**：用 Task 工具 dispatch，传 `subagent_type` 与 `model=opus`。
3. **reviewer 不修改代码**：reviewer 只输出 mini-report；修改由 x-fix 负责。
4. **聚合不内核重复**：R1/R2/R3 的检查清单分别由 `references/r1-*.md`、`r2-*.md`、`r3-*.md` 定义；本 SKILL.md 不重复检查清单内容。

## Reviewer dispatch 模板（写给主 agent 用）

每次 dispatch 一个 reviewer 子 agent，使用 Task 工具：

```
Agent({
  description: "<reviewer name> review",
  subagent_type: "general-purpose",
  model: "opus",          # 强制 opus
  prompt: <把 references/r{N}-*.md 内容 + 当前 task 上下文 + git diff 全部塞进 prompt>
})
```

prompt 必须包含：
1. 完整的 reviewer 检查清单（来自 references/r{N}-*.md）
2. 当前 task 的 README.md / plan.md / dev-checklist.md 全文
3. git diff 输出
4. 输出格式约束（mini-report markdown，按严重度列表）

## 失败回流

参见 `skills/x-fix/SKILL.md` 中的 4 条回流规则。x-qua-gate 把控制权交给 x-fix 后，由 x-fix 决定 fix 完后回到哪个节点（当前 reviewer 还是回 R1）。

## 6 次上限

与 x-verify 共用 `reports/.fix-counter`。每次 reviewer fail 触发 x-fix 都 +1，超 6 次停下问用户。

## 报告输出

主 agent 把 3 个 reviewer 的 mini-report 聚合到 `reports/qa-gate/qa-gate-report-YYYYMMDD-HHmmss.md`，模板见 `templates/qa-gate-report-template.md`。

## 下游

- 全部 pass → 任务完成 → fix-counter 重置为 0 → 写 changelog
- 任一 fail → x-fix
