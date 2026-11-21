---
name: x-fix
description: |
  Bug 修复执行 skill。分三种入口：
  1. 用户直接报告 Bug → 定位根因 → 修复 → 产出 fix-report-*.md 或 fix-note-*.md（无需 CR 报告）
  2. 有 x-cr 的 CR 报告 → 按稳定 Bn/INV-ID 逐条修复 → 回写同一份 task 内或仓库级 `reports/cr/cr-report-*.md` 主档并产出修复记录
  3. 有 xdev check / x-verify-spec 不通过回执、x-qa-gate 问题清单 → 按清单一次批量修复，处置写进 checklist「问题与处置」，交回主 agent 关闭
  触发方式："x-fix"、"修一下这个 bug"、"这个功能坏了"、
  "按 CR 报告修复"、"把 CR 问题修了"。
---

# x-fix 修复执行框架

修复验证遵循 [证据约定](../x-dev/references/test-reporting.md)：task 内的修复沿用该 task 的代码基线、用例对应表和证据目录，修完重跑 `xdev coverage`（全量测试 + 改动行覆盖率 100%）和 `xdev check`；直接 bug 修复在 `reports/fix/` 写修复报告，测试结果写在报告里，原始输出放同名证据目录。

## 模式判断（第一步必做）

按输入来源选择模式：

- **有 xdev check / x-verify-spec 不通过回执、x-qa-gate 问题清单**（`xdev check` 列出的问题；旧契约包的 `verify-report-*.md`；或 x-qa-gate 问题映射与 `issue-<n>`）→ 加载 `references/qa-gate-fix-mode.md`
- **有 x-cr CR 报告**（用户提供 task 内/仓库级 `reports/cr/cr-report-*.md`，或提到"按 CR 报告"、"CR 问题"）→ 加载 `references/cr-fix-mode.md`
- **用户直接描述 bug 或问题现象** → 加载 `references/bug-fix-mode.md`

---

## 修复报告模板（模式 1 产出物）

直接 bug 修复（模式 1）和 CR 驱动修复（模式 2）完成后，必须在 `reports/fix/` 产出报告或修补单；门禁回流（模式 3）不写这里，处置写进 checklist「问题与处置」：

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

[实际运行的测试命令与结果、新增的反例测试、未决项；原始输出放 reports/fix/<报告名>-evidence/]
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
- P2 待确认或补证：X 条
- 已跳过（历史 P3）：X 条
- 修改文件：X 个（列出文件路径）
```

输出末尾追加：`📄 报告已更新：<完整文件路径>`

---

## x-cr / x-qa-gate 边界

- x-cr 报告来自手动软件正确性调查，x-fix 按稳定 Bn/INV-ID 修复，并回写同一份 task 内或仓库级 CR 报告。
- `xdev check` / x-qa-gate 的问题清单来自自动门禁，x-fix 按 `references/qa-gate-fix-mode.md` 一次批量修复本轮清单，修完交回主 agent：`xdev check` 的问题由主 agent 重跑 `xdev check` 关闭，x-qa-gate 的问题按其「回流」关闭（不发回原 reviewer）。
- 当前自动门禁链路是 `x-dev -> xdev check（x-verify-spec）-> x-qa-gate（Q1–Q3）-> x-fix`。
- dev-checklist 头部 `risk: Q0` 在 `xdev check` 通过后交付；Q1–Q3 进入 x-qa-gate 对应深度的 reviewer。
- 手动正确性调查和 CR 复查由用户明确触发 x-cr。

### 单次修复的边界约束

- **不跨任务**：一次 x-fix 调用只处理当前任务的问题，不得修复其他任务范围内的代码
- **不扩大修改**：不得"顺便"重构其他代码、改无关风格、补其他任务的遗漏
- **不吞错**：修复中遇到文件不存在、行号完全错位等异常 → 在报告中标记 `➖无需修复` 并继续下一条，**不允许静默跳过**

---

## Gate 回流：批量修 + 主 agent 关闭

x-fix 同时接收 bug 报告、cr-report，以及 `xdev check` 不通过回执、x-qa-gate reviewer 的问题清单。执行结构是**一次批量修完本轮全部问题，交回主 agent 关闭**；x-qa-gate 问题的关闭方式与三轮上限见 `skills/x-qa-gate/SKILL.md`「回流」。

### 批量修协议

1. 输入 = 主 agent 提供的**完整问题清单**：x-qa-gate 的 issue 映射（每条含 `issue-<n>`、lens、task、severity、loc、msg 和 reviewer 证据）；`xdev check` 列出的问题，主 agent 按顺序编号 V1、V2…；或旧契约包 verify 报告的全部 fail 命令。
2. 按严重度处置：P0 全修；P1 逐条修复或写豁免理由；P2 只登记不修。
3. **每修一个 P0 必须留一条可复跑反例**（单元/集成测试断言或 verify 脚本步骤），防止回归。
4. 修复触及配置、CLI、公开 API、协议/schema 或落盘布局时，先列出修复前已接受的最小输入样本。新增配置字段默认保持可选并提供兼容默认值；spec 明确要求破坏性迁移时，把迁移命令和验收写入处置表。
5. 修完自跑验证：每条问题的聚焦反例 + `xdev coverage`（本 task 全量测试与既有回归、改动行覆盖率仍 100%）；旧契约包为原完整入口 verify。`xdev check` 由主 agent 在把行改回 🟢 后运行（见 x-qa-gate「回流」）。新增的反例测试登记进用例对应表。原始样本必须保持原样参与复跑，禁止只用修复后扩展过的 fixture 证明兼容性。
6. 证据全绿后在 checklist「问题与处置」（qdev 为⑤的同名节）逐条写处置（见下），按下面「回执」一节输出回执，控制权交回主 agent 关闭问题。
7. 修复过程保持 dev-checklist 状态单元格与 issue ledger 原样；状态升钩由主 agent 关闭问题后完成。

### 回执

```text
🔧 x-fix 完成 · <task> · 第 N 轮 · 来源 <x-qa-gate / xdev check / 旧包 verify> · 已修 P0 ×a、P1 ×b · 豁免 ×c · 登记 P2 ×d · 退回主 agent ×e
```

其后列出每条的聚焦反例测试和 `xdev coverage` 的结果，以及退回主 agent 的条目（编号、原因、应交给谁）。

### fix-attempts 3 轮共享上限

**fix-counter 文件协议**（交付核对与独立审查阶段共享；`xdev check` 只读不写）：

- 路径：`docs/spec/<spec>/tasks/<task>/reports/.fix-counter`（qdev 单文档用 `tasks/<task>-evidence/.fix-counter`；历史 task 在原位置）
- 格式：单行 ASCII 整数 + 行尾换行（如 `2\n`）
- 语义：**批量修轮数**（一轮 = 一份 issue 清单的整体修复），不按问题条数计
- 读取：`c=$(cat reports/.fix-counter)`；不存在则视为 0
- 递增（x-fix 的责任）：进入本轮批量修前 `echo $((c+1)) > reports/.fix-counter`（先 +1 再修，避免崩溃后死循环）
- counter >= 3 → 不进 fix，直接生成 `reports/fix-blocked-report.md` 列出积压问题，要求用户决策（继续 / 修改需求 / 放弃）
- 重置：risk Q1–Q3 由主 agent 在 x-qa-gate 最终通过后写回 0；risk Q0 由主 agent 在 `xdev check` 通过、行升 ✅ 时写回 0：`echo 0 > reports/.fix-counter`
- 多 agent 协作时，各并行组开发阶段的核对轮数另计（见 `skills/x-dev/references/parallel-dev.md`），不写这个文件

### 处置记录

门禁回流不另写 fix 报告，处置直接写进 checklist「问题与处置」（qdev 为⑤的同名节），每条一行：

```markdown
- issue-1 · P0 · ✅ 已修：扩展 SQLSTATE 分类 · 反例 tests/test_classify.py::test_sqlstate_retry
- issue-2 · P1 · ➖ 豁免：<理由>
- issue-3 · P2 · 📝 登记，不修
- V1 · ✅ 已修：src/loan/renew.py:12-14 没覆盖，补 tests/test_renew.py::test_renew_edge
```

历史 task 里的 `reports/fix/fix-verify-spec-*.md`、`fix-gate-r*.md` 保留原样，不再新建。
`reports/fix/fix-report-*.md` 与 `fix-note-*.md` **只用于直接 bug fix 模式**（用户报告 bug 走原流程）。

### 子模式

详见 `references/qa-gate-fix-mode.md`，定义 verify-fix / gate-fix 两种子模式的输入识别与特殊规则。
