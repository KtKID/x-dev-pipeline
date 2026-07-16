---
name: x-fix
description: |
  Bug 修复执行 skill。分三种入口：
  1. 用户直接报告 Bug → 定位根因 → 修复 → 产出 fix-report-*.md 或 fix-note-*.md（无需 CR 报告）
  2. 有 x-cr 的 CR 报告 → 按报告逐条修复 → 回写同一份 `reports/cr/cr-report-*.md` 主档并产出修复记录
  3. 有 x-verify / x-qa-gate fail 报告 → 按发现清单一次批量修复，产出逐条处置表，交回 gate 增量复审
  触发方式："x-fix"、"修一下这个 bug"、"这个功能坏了"、
  "按 CR 报告修复"、"把 CR 问题修了"。
---

# x-fix 修复执行框架

## 模式判断（第一步必做）

按输入来源选择模式：

- **有 x-verify / x-qa-gate fail 报告**（包含 `verify-report-*.md`，或 RC/R1/R2/R3 reviewer mini-report 发现清单）→ 加载 `references/qa-gate-fix-mode.md`
- **有 x-cr CR 报告**（用户在指令中提供了 `reports/cr/cr-report-*.md` 路径，或提到"按 CR 报告"、"CR 问题"）→ 加载 `references/cr-fix-mode.md`
- **用户直接描述 bug 或问题现象** → 加载 `references/bug-fix-mode.md`

---

## 修复报告模板（模式 1 产出物）

所有修复完成后，必须在 `reports/fix/` 产出报告或修补单：

- `reports/fix/fix-report-YYYYMMDD-HHmmss.md`：CR 驱动、跨文件、需要完整闭环的修复
- `reports/fix/fix-note-YYYYMMDD-HHmmss.md`：人工发现的单点小修补

```markdown
# [Bug 名称] 修复报告

> 修复时间：YYYY-MM-DD HH:mm
> 修复人：Claude (x-fix)

## Bug 描述

[用户描述的问题现象]

## 根因分析

[定位到的根本原因]

## 修复方案

[具体如何修复]

## 修改文件

| 文件 | 修改内容 |
|------|----------|
| `src/xxx.ts` | [描述改动] |

## 测试验证

[验证方式：无/本地测试/用例说明]
```

报告路径统一写入 `reports/fix/`，文件类型由修复范围决定。

如果是单点人工修补，优先写 `fix-note-YYYYMMDD-HHmmss.md`；如果是完整 bug 修复或 CR 驱动修复，优先写 `fix-report-YYYYMMDD-HHmmss.md`。

---

## CR 报告修复（模式 2）输出

执行完 `references/cr-fix-mode.md` 的流程后，在对话中输出：

```
✅ 修复完成

- 已修复：X 条
- 无需修复（误报）：X 条
- 已跳过（P3）：X 条
- 修改文件：X 个（列出文件路径）
```

输出末尾追加：`📄 报告已更新：<完整文件路径>`

---

## x-cr / x-qa-gate 边界

- x-cr 报告来自手动软件正确性调查，x-fix 按 `references/cr-fix-mode.md` 修复并回写同一份 `reports/cr/cr-report-*.md`。
- x-verify / x-qa-gate 报告来自自动门禁，x-fix 按 `references/qa-gate-fix-mode.md` 一次批量修复本轮发现清单，修完交回触发 gate 做增量复审。
- 当前自动门禁链路是 `x-dev -> x-verify -> x-qa-gate -> x-fix`。
- README `risk: Q0/Q1` 在 verify 通过后交付；Q2 进入 RC；Q3 进入 R1→R2→R3。
- 手动正确性调查和 CR 复查由用户明确触发 x-cr。

### 单次修复的边界约束

- **不跨任务**：一次 x-fix 调用只处理当前任务的问题，不得修复其他任务范围内的代码
- **不扩大修改**：不得"顺便"重构其他代码、改无关风格、补其他任务的遗漏
- **不吞错**：修复中遇到文件不存在、行号完全错位等异常 → 在报告中标记 `➖无需修复` 并继续下一条，**不允许静默跳过**

---

## Gate 回流：批量修 + 增量复审

x-fix 不只服务于 bug 报告与 cr-report，也接收来自 x-verify / x-qa-gate reviewer（RC/R1/R2/R3）的 fail 触发。执行结构是**一次批量修完本轮全部发现，交回 gate 做增量复审**；x-fix 不再自行判定回流目标（旧"回 R1"规则已废除，增量复审与熔断逻辑见 `skills/x-qa-gate/SKILL.md`「增量复审」）。

### 批量修协议

1. 输入 = reviewer mini-report 的**完整发现清单**（F1..Fn）或 verify 报告的全部 fail 命令。
2. 按严重度处置：P0 全修；P1 逐条修复或写豁免理由；P2 只登记不修。
3. **每修一个 P0 必须留一条可复跑反例**（单元/集成测试断言或 verify 脚本步骤），防止回归。
4. 修完自跑受影响验证（相关测试 + dev-report 命令中受影响条目），不许带着红灯交回复审。
5. 产出逐条处置表（见下），控制权交回主 agent 触发增量复审。

### fix-attempts 3 轮共享上限

**fix-counter 文件协议**（与 x-verify / x-qa-gate 共享）：

- 路径：`dev-pipeline/tasks/<task>/reports/.fix-counter`
- 格式：单行 ASCII 整数 + 行尾换行（如 `2\n`）
- 语义：**批量修轮数**（一轮 = 一份发现清单的整体修复），不按问题条数计
- 读取：`c=$(cat reports/.fix-counter)`；不存在则视为 0
- 递增（x-fix 的责任）：进入本轮批量修前 `echo $((c+1)) > reports/.fix-counter`（先 +1 再修，避免崩溃后死循环）
- counter >= 3 → 不进 fix，直接生成 `reports/fix-blocked-report.md` 列出积压问题，要求用户决策（继续 / 修改需求 / 放弃）
- 重置（x-qa-gate 在 Gate ② 最终 pass 后做）：`echo 0 > reports/.fix-counter`

### fix 报告路径与处置表

| 触发节点 | fix 报告路径 |
|---------|-------------|
| x-verify fail | `reports/fix/fix-verify-YYYYMMDD-HHmmss.md` |
| Gate ② reviewer fail（RC/R1/R2/R3）| `reports/fix/fix-gate-r<轮次>-YYYYMMDD-HHmmss.md` |

报告核心是逐条处置表：

```markdown
| # | 严重度 | 处置 | 说明 | 反例/验证 |
|---|--------|------|------|-----------|
| F1 | P0 | ✅ 已修 | 扩展 SQLSTATE 分类 | `cargo test -p x classify_` 新增断言 |
| F2 | P1 | ➖ 豁免 | 理由：... | — |
| F3 | P2 | 📝 登记 | 不修 | — |
```

旧路径 `reports/fix/fix-report-*.md` 与 `fix-note-*.md` 仍保留，**只用于直接 bug fix 模式**（用户报告 bug 走原流程）。

### 子模式

详见 `references/qa-gate-fix-mode.md`，定义 verify-fix / gate-fix 两种子模式的输入识别与特殊规则。
