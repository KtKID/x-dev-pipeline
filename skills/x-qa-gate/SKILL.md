---
name: x-qa-gate
description: |
  Gate ② 流水线质量门禁 skill。串行 dispatch 3 个子 agent reviewer：R1 契约/spec 正确性（契约优先）→ R2 失败路径/边界正确性（失败优先 + 对抗性检验）→ R3 测试真实性（反自证正确）。任一 reviewer 失败即触发 x-fix 并回到该 reviewer 重审；全部通过任务才算完成。
  自动触发：x-verify 通过后立即触发。
  手动触发：用户要求"质量门禁"、"qa-gate"、"R1/R2/R3 gate"、"跑门禁"。
  手动软件正确性调查、用户已知问题排查、模块/PR correctness review 优先使用 x-cr；流水线 gate 使用 x-qa-gate。
---

# x-qa-gate · Gate ② 质量评审

x-qa-gate 是质量门禁链路的第二层 gate。它前面的 x-verify 已确认"代码能跑"，本 skill 负责回答三个递进问题：

1. **R1：契约和 spec 是否被正确实现？**（契约优先 / spec 正确性 / scope）
2. **R2：失败路径和边界输入下是否仍然正确？**（失败优先 / 边界正确性 / 对抗性检验）
3. **R3：测试是否能从反方向击穿假实现？**（测试真实性 / 反镜像化 / 反自证正确）

R1 和 R2 都是流水线内的正确性检查：R1 查实现是否符合原始 spec 与公开入口契约，R2 查失败路径、边界输入、异常状态和外部依赖失败下是否仍然正确。R3 查测试证据是否可信，重点识别 happy path-only、镜像化测试、自我 mock 和为通过测试写死逻辑。

三个问题必须按顺序回答：R1 先确认目标正确性，R2 再确认边界正确性，R3 最后确认测试证据真实性。

## 质量原则落点

- **契约优先**：R1 抽取公开入口契约并对照实现；R2 使用契约定义边界和副作用检查范围。契约包括输入、输出、错误、空值、状态副作用、幂等性和并发/线程安全要求。
- **失败优先**：R2 从失败路径开始审查，包括非法输入、异常状态、工具超时、权限拒绝、部分失败、环境不一致和外部返回非法数据。
- **对抗性检验**：R1/R2/R3 都要主动寻找能击穿当前实现或证据的输入、状态、依赖失败、权限、缓存、并发和测试过拟合场景。

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
   x-fix 计数 +1               x-fix 计数 +1               x-fix 计数 +1
       │                            │                              │
       ↓                            ↓                              ↓
   按 x-fix 回流规则               同左                            同左
   决定回 R1 还是当前              （见 x-fix SKILL.md）
```

## 硬约束

1. **必须串行**：R1 → R2 → R3 顺序固定，不要并行。
2. **每个 reviewer 必须是独立子 agent**：用 Task 工具 dispatch，传 `subagent_type`。
3. **reviewer 不要修改代码**：reviewer 只输出 mini-report；修改由 x-fix 负责。
4. **聚合保持单一来源**：R1/R2/R3 的检查清单分别由 `references/r1-*.md`、`r2-*.md`、`r3-*.md` 定义；不要在本 SKILL.md 重复检查清单内容。

## Reviewer context 预算

R1/R2/R3 reviewer 子 agent 的初始 prompt 采用预算制：

- 目标上限：10,000 estimated tokens。
- 不要把完整 diff、完整源码、完整测试文件、大段日志放入初始 prompt。
- 大材料保留原路径，或写入 `reports/qa-gate/evidence/<reviewer>-<timestamp>/`；初始 prompt 只传 manifest、路径、hash、行号范围、摘要。

estimated token 采用保守估算：

- Markdown / diff / 代码混合文本按 `4 chars ~= 1 token`。
- 中文较多时按 `2.5 chars ~= 1 token`。
- 任一估算超过 10,000 tokens 时，主 agent 必须压缩为 manifest。

上述预算是 prompt 协议。实际硬限制由当前执行 harness 决定；harness 支持硬限制时使用硬限制，harness 只支持普通 prompt 时，通过 manifest、estimated tokens 和 completeness gate 控制成本。

## Reviewer dispatch 模板（写给主 agent 用）

每次 dispatch 一个 reviewer 子 agent，使用 Task 工具：

```
Agent({
  description: "<reviewer name> review",
  subagent_type: "general-purpose",
  prompt: <reviewer checklist + task manifest + required paths + diff commands + evidence path + context completeness gate + output format>
})
```

prompt 必须包含：
1. 完整的 reviewer 检查清单（来自 `references/r{N}-*.md`）。
2. 当前 task root。
3. 必读文件路径列表：`README.md` / `plan.md` / `dev-checklist.md` / `changelog.md` / `dev-report.md` / 最新 verify report。
4. diff 获取命令：`git diff --stat`、`git diff --name-only`、按需 `git diff -- <file>`。
5. evidence 输出路径：`reports/qa-gate/evidence/<reviewer>-<timestamp>/`。
6. Context Completeness 检查要求。
7. 输出格式约束（mini-report markdown，按严重度列表）。

不要在 prompt 中内联完整代码。子 agent 通过只读工具按需读取文件、diff 和测试内容，大文件按行号范围读取。

## Context Completeness Gate

每个 reviewer mini-report 开头必须包含：

```markdown
## Context Completeness

**Completed by model:** <actual model id>
**Status:** complete / incomplete

**Loaded materials:**
- [ ] reviewer checklist
- [ ] README.md
- [ ] plan.md
- [ ] dev-checklist.md
- [ ] changelog.md
- [ ] dev-report.md
- [ ] verify report
- [ ] git diff stat
- [ ] git diff name-only
- [ ] relevant implementation files
- [ ] relevant test files

当前 reviewer 无需加载的项目写 `N/A`，并在同一行说明原因。

**Missing or truncated materials:**
- none / list items

**Evidence coverage:**
- changed files reviewed: N / M
- implementation files reviewed: N
- test files reviewed: N
- cited evidence count: N
```

判定规则：

- `Status: incomplete` → reviewer 必须给出 `fail`，原因写为 `context incomplete`。
- 必读文件缺失 → `incomplete`。
- diff 文件列表缺失 → `incomplete`。
- reviewer 无法确认关键实现文件内容 → `incomplete`。
- 引用证据少于 3 条且结论为 pass → 主 agent 视为无效报告，重新 dispatch。
- reviewer 报告缺少 `Context Completeness` 或最终 `Status` → 主 agent 视为无效报告，重新 dispatch。

## Context 文件策略

`reports/qa-gate/context/r{N}-context-*.md` 只保存轻量上下文：

- reviewer 名称和时间戳。
- task root。
- checklist 路径。
- required docs 路径。
- changed file list。
- `git diff --stat`。
- verify report 摘要。
- evidence bundle 路径。
- context budget 估算。

context 文件不要保存完整 git diff、完整源码文件、完整测试文件、重复 task 文档全文或大段日志输出。

## 失败回流

参见 `skills/x-fix/SKILL.md` 中的 4 条回流规则。x-qa-gate 把控制权交给 x-fix 后，由 x-fix 决定 fix 完后回到哪个节点（当前 reviewer 还是回 R1）。

## 6 次上限

与 x-verify 共用 `reports/.fix-counter`。每次 reviewer fail 时先检查 counter；counter < 6 时触发 x-fix，由 x-fix 进入修复前 +1；counter >= 6 时停下问用户。

## 报告输出

主 agent 把 3 个 reviewer 的 mini-report 聚合到 `reports/qa-gate/qa-gate-report-YYYYMMDD-HHmmss.md`，模板见 `templates/qa-gate-report-template.md`。

## 下游

- 全部 pass → 任务完成 → fix-counter 重置为 0 → 写 changelog
- 任一 fail → x-fix
