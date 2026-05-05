---
name: x-fix
description: |
  Bug 修复执行 skill。分两种模式：
  1. 用户直接报告 Bug → 定位根因 → 修复 → 产出 fix-report-*.md 或 fix-note-*.md（无需 CR 报告）
  2. 有 x-cr 的 CR 报告 → 按报告逐条修复 → 回写同一份 `reports/cr/cr-report-*.md` 主档并产出修复记录
  触发方式："x-fix"、"修一下这个 bug"、"这个功能坏了"、"按 CR 报告修复"、
  "把 CR 问题修了"。两种模式互斥：有 CR 报告走模式 2，无报告走模式 1。
---

# x-fix 修复执行框架

## 模式判断（第一步必做）

检查用户是否携带了 CR 报告信息：

- **有 CR 报告**（用户在指令中提供了 `reports/cr/cr-report-*.md` 路径，或提到"按 CR 报告"、"CR 问题"）→ 加载 `references/cr-fix-mode.md` 执行模式 2
- **无 CR 报告**（用户直接描述 bug 或问题现象）→ 加载 `references/bug-fix-mode.md` 执行模式 1

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

## 自动流转规则（连续开发模式）

> 适用场景：x-fix 在连续开发自动循环中被 x-cr 调用时生效（由 x-dev → x-cr → x-fix 链路触发）。
> 用户手动触发 x-fix 修 bug、按 CR 报告修复、或指定修某些问题时，**不启用本节**，仍按模式 1/2 常规流程执行（用户可自由指定修复范围）。

### 1. 触发判定

AI 根据当前对话上下文自主判断是否处于"连续开发模式"：

- **是**（当前对话正在执行 x-cr 的自动修复循环） → 执行本节规则
- **否**（用户直接让 x-fix 修 bug / 修某条 CR 问题 / 挑选问题修复） → 按模式 1（bug-fix）或模式 2（cr-fix-mode）常规流程

不依赖任何命令行参数，AI 根据自身正在执行的上下文路径即可区分。

### 2. 修复范围限定

**在连续开发模式下，只修复 P0 和 P1 问题。**

这与模式 2（cr-fix-mode）的"P0/P1/P1.5/P2 都处理"不同：

| 严重度 | 手动 CR 修复模式 | 连续开发模式 |
|--------|-----------------|-------------|
| P0 | ✅ 必修 | ✅ 必修 |
| P1 | ✅ 必修 | ✅ 必修 |
| P1.5（架构问题） | ✅ 必修 | ⏭ 跳过，记录 `⏭已跳过（自动流转不修架构）` |
| P2 | ✅ 必修 | ⏭ 跳过，记录 `⏭已跳过（自动流转仅修 P0/P1）` |
| P3 | ⏭ 跳过 | ⏭ 跳过 |

**原因**：P1.5 架构级改动往往需要跨文件重构，放入自动循环容易反复试探且难收敛；P2/P3 不阻塞功能，累积到最终汇报由用户人工决策。

### 3. 修复完成后的硬性后续动作

修复完成并更新 CR 报告后，**必须立即执行以下动作，不等待用户确认**：

1. **不得直接返回 x-dev**，必须先让 x-cr 复审同一批文件
2. 调用 x-cr，传入：
   - 原 CR 报告路径（作为本次审查的基线对照）
   - 本次修复涉及的文件列表
   - 任务编号（x-cr 会据此从 `dev-checklist.md` 的"备注"列读取 `[fix:N]` 计数并 +1，计数的权威来源是 dev-checklist.md 而非报告文件）
3. x-cr 复审结果决定下一步：
   - 复审仍有 P0/P1 → x-cr 会再次调用 x-fix（循环继续）
   - 复审通过 → x-cr 通知 x-dev 取下一任务
   - fix_attempts 达到 6 → x-cr 停止循环并汇报

### 4. 单次修复的边界约束

- **不跨任务**：一次 x-fix 调用只处理当前任务的问题，不得修复其他任务范围内的代码
- **不扩大修改**：不得"顺便"重构其他代码、改无关风格、补其他任务的遗漏
- **不吞错**：修复中遇到文件不存在、行号完全错位等异常 → 在报告中标记 `➖无需修复` 并继续下一条，**不允许静默跳过**

### 5. 与模式 2（cr-fix-mode）的关系

连续开发模式复用 `references/cr-fix-mode.md` 的大部分步骤（解析报告、逐条修复、更新报告），区别仅在：

- 修复范围限定为 P0+P1（跳过 P1.5/P2/P3）
- 修复完成后不"提醒用户 git commit"，而是立即调用 x-cr 复审
- 不输出"✅ 修复完成"给用户，而是输出给 x-cr 的机读标记

### 关键约束

- **不等用户确认**：修完直接调用 x-cr，不问"要不要复审"
- **只修 P0/P1**：不在循环内处理架构级或样式级问题
- **不自动 commit**：git 操作仍由用户手动触发
- **不扩大战线**：严格限定在当前任务的问题列表内

---

## 失败回流规则（qa-gate-pipeline 改造）

x-fix 不只服务于 bug 报告与 cr-report，也接收来自 x-verify / x-qua-gate R1/R2/R3 的 fail 触发。fix 完成后，**回到哪个节点重审**按下列优先级匹配（命中即停）：

1. fix 涉及函数签名变化 / 新增/删除公开 API → **必须回 R1**
2. fix 改动了被测代码的核心业务逻辑文件（非测试 / 非配置 / 非注释）→ **必须回 R1**
3. fix 只改测试文件 / 配置 / 文档 / 注释 → **回当前失败节点**
4. 其他不确定情况 → **保守回 R1**

### fix-attempts 6 次共享上限

**fix-counter 文件协议**（与 x-verify / x-qua-gate 共享）：

- 路径：`dev-pipeline/tasks/<task>/reports/.fix-counter`
- 格式：单行 ASCII 整数 + 行尾换行（如 `3\n`）
- 读取：`c=$(cat reports/.fix-counter)`；不存在则视为 0
- 递增（x-fix 的责任）：进入 fix 前 `echo $((c+1)) > reports/.fix-counter`
- 重置（x-qua-gate 在 R3 通过后做）：`echo 0 > reports/.fix-counter`

行为规则：

- 任何 verify / R1 / R2 / R3 fail 触发 x-fix 时，**先把 fix-counter +1 再开始 fix**（避免崩溃后死循环）。
- fix-counter >= 6 → 不进 fix，直接生成 `reports/fix-blocked-report.md`，要求用户决策（继续 / 修改需求 / 放弃）。
- 任务最终通过 x-qua-gate（R3 pass）后，由 x-qua-gate 把 fix-counter 重置为 0。

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
