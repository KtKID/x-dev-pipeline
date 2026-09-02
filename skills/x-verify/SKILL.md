---
name: x-verify
description: |
  Gate ① 交付对账 skill。task 开发完成后使用：以 spec 场景为事实源，对账 dev-checklist 的场景回指、行状态与 dev-report 结论，全部一致给回执，不一致按来源分诊。触发：x-dev 交付、用户要求 verify 或复核某个 task。
---

# x-verify · Gate ①

## 定位与边界

验证对象是**单个 task 的交付证据链**：`dev-checklist.md`（req 产物）与 `dev-report.md`（dev 产物）两份文档的对账，spec 场景只作为回指的事实源，不重新评审 spec 本身——spec 质量归 x-spec 与 x-req 就绪检查。不重跑测试：x-dev 已真实运行测试，verify 只核对结论与证据是否一致、覆盖是否闭合。代码质量由 x-qa-gate 处理。

## 对账项

按顺序检查，先结构后内容：

1. **结构**：task 目录 `docs/spec/<spec-name>/tasks/<task-name>/` 下 dev-checklist.md 与 dev-report.md 齐全；spec.md 存在且 v6 结构完整（标题 + 概述 + feat 列表）。
2. **回指有效**：checklist 每行"场景回指"列的 `featNN 场景M`（含逗号分隔与 `场景1-3` 区间写法）都真实存在于 spec；`None` 行保持最少。悬空回指是拆解问题。
3. **影响树一致**：checklist 影响文件树与「涉及文件」列一一对应——树上没有表外文件，表内文件（glob 计目录节点）都在树上，标记只用 U/M/D。
4. **行状态闭合**：全部任务行为 `[x] 🟢`，无 ⏳ / ▶️ / 🔴 残留。
5. **高风险行**：风险列为 `高:` 的行，dev-report 结果节必须声明其真实链路验证（smoke 或以上）。
6. **结论一致**：dev-report 结果节与 checklist 对得上——声称全绿则 checklist 确实无 🔴；存在 🔴 或回归失败时，未决节逐行对应（行号 + 摘要 + 已尝试动作），不得漏记或多记。

## 分诊

发现问题按来源退回，不递增 fix-counter：

- spec.md 缺失或 v6 结构不完整 → 退回 x-spec。
- checklist 表头不可解析、回指悬空、`None` 行过多、影响文件树缺失或与「涉及文件」列不一致 → 退回 x-req。
- dev-report 缺失、格式不符模板、结论与 checklist 状态矛盾、高风险行缺真实链路声明 → 退回 x-dev。
- checklist 有 🔴 残留或回归失败且已在未决节如实记录 → 这是已知失败而非文档问题；交 x-fix 处理，或如实报告阻塞等用户决定。

## 约束

- 只报告事实与一致性结论，不评判实现质量、不改任何文档。
- 一次跑完全部对账项后交付完整问题清单，不逐项挤牙膏。
- 全部通过时不写报告文件，只输出回执；有问题时把完整清单交对应 skill 或 x-fix。

## 回执

```
🛡️ Gate① verify ✅ · <task-name> · 行 N/N 🟢 · 回指场景 M/M 有效 · 影响树一致 · 高风险行 K（已声明）· 结论一致
🛡️ Gate① verify ❌ · <task-name> · 问题 N 项 → 退回 <x-spec / x-req / x-dev / x-fix>
```
