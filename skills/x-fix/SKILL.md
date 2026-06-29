---
name: x-fix
description: |
  Bug 修复执行 skill。分三种入口：
  1. 用户直接报告 Bug → 定位根因 → 修复 → 产出 fix-report-*.md 或 fix-note-*.md（无需 CR 报告）
  2. 有 x-cr 的 CR 报告 → 按报告逐条修复 → 回写同一份 `reports/cr/cr-report-*.md` 主档并产出修复记录
  3. 有 x-verify / x-qa-gate fail 报告 → 直接按失败报告修复，并按回流规则重审
  触发方式："x-fix"、"修一下这个 bug"、"这个功能坏了"、
  "按 CR 报告修复"、"把 CR 问题修了"。
---

# x-fix 修复执行框架

## 模式判断（第一步必做）

按输入来源选择模式：

- **有 x-verify / x-qa-gate fail 报告**（包含 `verify-report-*.md`、`qa-gate-report-*.md`、R1/R2/R3 fail）→ 加载 `references/qa-gate-fix-mode.md`
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
- x-verify / x-qa-gate 报告来自自动门禁，x-fix 按 `references/qa-gate-fix-mode.md` 修复，并由回流规则决定回 R1、R2、R3 或 verify。
- 当前自动链路是 `x-dev / x-qdev -> x-verify -> x-qa-gate -> x-fix`。
- 历史 `x-dev -> x-cr -> x-fix` 自动循环已退出主流程。需要再次调查 CR 修复结果时，由用户明确触发 x-cr 复查。

### 单次修复的边界约束

- **不跨任务**：一次 x-fix 调用只处理当前任务的问题，不得修复其他任务范围内的代码
- **不扩大修改**：不得"顺便"重构其他代码、改无关风格、补其他任务的遗漏
- **不吞错**：修复中遇到文件不存在、行号完全错位等异常 → 在报告中标记 `➖无需修复` 并继续下一条，**不允许静默跳过**

---

## 失败回流规则（qa-gate-pipeline 改造）

x-fix 不只服务于 bug 报告与 cr-report，也接收来自 x-verify / x-qa-gate R1/R2/R3 的 fail 触发。fix 完成后，**回到哪个节点重审**按下列优先级匹配（命中即停）：

1. fix 涉及函数签名变化 / 新增/删除公开 API → **必须回 R1**
2. fix 改动了被测代码的核心业务逻辑文件（非测试 / 非配置 / 非注释）→ **必须回 R1**
3. fix 只改测试文件 / 配置 / 文档 / 注释 → **回当前失败节点**
4. 其他不确定情况 → **保守回 R1**

### fix-attempts 6 次共享上限

**fix-counter 文件协议**（与 x-verify / x-qa-gate 共享）：

- 路径：`dev-pipeline/tasks/<task>/reports/.fix-counter`
- 格式：单行 ASCII 整数 + 行尾换行（如 `3\n`）
- 读取：`c=$(cat reports/.fix-counter)`；不存在则视为 0
- 递增（x-fix 的责任）：进入 fix 前 `echo $((c+1)) > reports/.fix-counter`
- 重置（x-qa-gate 在 R3 通过后做）：`echo 0 > reports/.fix-counter`

行为规则：

- 任何 verify / R1 / R2 / R3 fail 触发 x-fix 时，**先把 fix-counter +1 再开始 fix**（避免崩溃后死循环）。
- fix-counter >= 6 → 不进 fix，直接生成 `reports/fix-blocked-report.md`，要求用户决策（继续 / 修改需求 / 放弃）。
- 任务最终通过 x-qa-gate（R3 pass）后，由 x-qa-gate 把 fix-counter 重置为 0。

### fix 报告路径分类

按触发节点分别写到不同子目录：

| 触发节点 | fix 报告路径 |
|---------|-------------|
| x-verify fail | `reports/fix/fix-verify-YYYYMMDD-HHmmss.md` |
| R1 fail | `reports/fix/fix-r1-spec-YYYYMMDD-HHmmss.md` |
| R2 fail | `reports/fix/fix-r2-boundary-YYYYMMDD-HHmmss.md` |
| R3 fail | `reports/fix/fix-r3-test-YYYYMMDD-HHmmss.md` |

旧路径 `reports/fix/fix-report-*.md` 与 `fix-note-*.md` 仍保留，**只用于直接 bug fix 模式**（用户报告 bug 走原流程）。

### 子模式

详见 `references/qa-gate-fix-mode.md`，定义 verify-fix / r1-spec-fix / r2-boundary-fix / r3-test-fix 四种子模式的输入识别与特殊规则。
