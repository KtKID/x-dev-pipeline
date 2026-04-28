# qa-gate-pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 x-dev-pipeline 现有的"x-dev → x-cr → x-fix"单层闭环升级为"x-dev → x-verify → x-qua-gate (R1→R2→R3 串行 opus 子 agent) → x-fix"双层质量门禁链路，并把性能/规范类审查剥离到独立的 x-audit-* 巡检 skill。

**Architecture:** 新增 4 个 skill（x-verify, x-qua-gate, x-audit-perf, x-audit-style），改造 3 个现有 skill（x-dev, x-qdev, x-fix），把 x-cr 转为重定向 stub。x-qua-gate 内部以 Task 工具 dispatch 3 个 opus 子 agent（R1/R2/R3）串行评审，每个 reviewer 子 agent 通过 references/ 下独立 prompt 文件驱动。失败回流走 x-fix，全局 fix-attempts 6 次上限共享。

**Tech Stack:** Markdown skill 文档（带 YAML frontmatter）、Claude Code Task 工具子 agent dispatch、文件系统报告产出（reports/{verify,qa-gate,fix,audit}/*.md）。

---

## Preflight — 执行前必读（fresh AI 必须先看完本段）

> 本段是给"完全没参与设计对话的执行 AI"准备的环境与术语对齐。**T1 之前必读**。

### 0.1 路径与术语约定

- **仓库根（repo-root）** = `/Volumes/machub_app/proj/x-dev-pipeline/`（绝对路径）
- ⚠️ 仓库本身**叫** `x-dev-pipeline`，仓库**内部**还有一个子目录 `dev-pipeline/`（无 x- 前缀）—— 两个名字相似容易混。所有提到 `dev-pipeline/tasks/...` 都是仓库内部的子目录，不是仓库根。
- 当前 task 目录 = `<repo-root>/dev-pipeline/tasks/qa-gate-pipeline/`
- 本 plan 中所有相对路径**默认相对仓库根**（除非另注）
- 所有 git 操作在仓库根执行：`cd /Volumes/machub_app/proj/x-dev-pipeline && git ...`

### 0.2 现状速读（已固化，无需现场跑）

下面是 plan 写作时实测的现状快照（`grep -n "^## " skills/*/SKILL.md`）。fresh AI **不必再跑**这些命令，可直接对照。但建议执行前用一条 `cd <repo-root> && grep -c "^## " skills/x-dev/SKILL.md skills/x-qdev/SKILL.md skills/x-fix/SKILL.md skills/x-cr/SKILL.md` 简单确认结构没漂移。

#### x-dev/SKILL.md 现有 H2（19 段）
关键锚点（按本 plan 用途）：
- `## 自动流转规则（连续开发模式）` (≈line 385) ← **T1 Step 3 推荐插入位置：此段之后**
- `## 连续开发汇报` (≈line 428) ← T1 Step 5 改"自动衔接 x-cr → x-verify"在此附近
- `## 输出要求` (≈line 334)、`## 注意事项` (≈line 374) ← 备选

#### x-qdev/SKILL.md 现有 H2（13 段）
- `## 第五步：代码审查` (≈line 116) ← **T1 Step 5 重点：把"自动衔接 x-cr"改成"自动衔接 x-verify"**
- `## 第六步：收尾` (≈line 160) ← **T1 Step 4 推荐插入位置：此段之前**
- `## 注意事项` (≈line 180) ← 备选

#### x-fix/SKILL.md 现有 H2（9 段）
⚠️ x-fix **没有** "## 两种模式" 段（那是 x-cr 才有的）。x-fix 实际锚点：
- `## 模式判断（第一步必做）` (≈line 13)
- `## 自动流转规则（连续开发模式）` (≈line 81) ← **T7 Step 1 推荐插入位置：此段之后**
- 已有 `## CR 报告修复（模式 2）输出` (≈line 64) ← 必读，T7 改造与之衔接
- 已有 `references/bug-fix-mode.md` 与 `references/cr-fix-mode.md` ← T7 Step 2 新增 `qa-gate-fix-mode.md` 与之同位置

#### x-cr/SKILL.md 现有 H2（5 段，将整体被 stub 替换）
- `## 两种模式` (line 18)、`## 审查流程` (line 31)、`## 全局审查原则` (line 155)、`## x-cr 的边界` (line 167)、`## Reference 文件导航` (line 179)
- T10 Step 1 整体替换为重定向 stub

#### plugin manifest 文件位置
- `.claude-plugin/plugin.json` ✓（存在）
- `.claude-plugin/marketplace.json` ✓（存在）
- `.codex-plugin/` 与 `.agents/` 是否含 manifest 由 T10 Step 4 现场探测

**找锚点的 fallback 规则**：如果上述某 H2 实际行号漂移很大（>20 行）或被改名，按 0.2 末尾的命令做一次 `grep -n` 确认；找不到对应段则**追加到文件末尾**，commit message 注明 "appended at EOF, anchor 'XXX' not found"。

### 0.3 Task / Agent 工具调用约定

本 plan 中所有"dispatch 子 agent"使用 Claude Code 的 **Agent 工具**（在某些版本里别名为 Task）。真实调用语法：

```
Agent(
    description="<3-5 词描述，如 'R1 spec review'>",
    subagent_type="general-purpose",
    model="opus",                    # ✅ 真实工具支持此参数（enum: sonnet/opus/haiku）
    prompt="<完整的自包含 prompt 字符串>"
)
```

**重要**：
1. `model="opus"` 是**真实有效的工具参数**——它覆盖 agent 默认 model。不要怀疑它能不能用。
2. fresh subagent **看不到当前对话上下文**——prompt 必须自包含。把 reviewer 检查清单 + 当前 task 全部相关文件文本 + git diff 文本**全部塞进 prompt**。
3. 如果你的 Claude Code 版本不支持 model 参数（极个别老版本会报错），降级方案：去掉 model 参数 + 在 prompt 开头加一行"你被指派为 opus 模型，请深度推理"。

### 0.4 fix-counter 文件（reports/.fix-counter）

- **路径**：`<task>/reports/.fix-counter`（每个 task 独立计数，不全局共享）
- **格式**：单行 ASCII 整数 + 行尾换行（如 `3\n`）
- **创建责任**：x-verify 第一次执行时检查；不存在则 `mkdir -p reports && echo 0 > reports/.fix-counter`
- **递增责任**：x-fix 进入修复前 `c=$(cat reports/.fix-counter); echo $((c+1)) > reports/.fix-counter`
- **重置责任**：x-qua-gate 在 R3 通过、整体 task 完成时 `echo 0 > reports/.fix-counter`
- **读取约定**：x-verify / x-qua-gate 任意 reviewer / x-fix 都按此协议读写

### 0.5 本仓库自吃狗粮的 verify 命令

⚠️ **重要**：本仓库（x-dev-pipeline）**是 markdown skill 仓库**，没有 npm test / pytest 这类自动化测试。本 task 自己跑 x-verify 时，dev-report.md 的命令清单应填**最小有意义检查**：

```markdown
| 命令 | 工作目录 | 预期 exit | 关键输出片段 |
|------|---------|----------|------------|
| `find skills/x-verify skills/x-qua-gate skills/x-audit-perf skills/x-audit-style -name SKILL.md \| wc -l` | repo-root | 0 | `4` |
| `for f in skills/x-{verify,qua-gate,audit-perf,audit-style}/SKILL.md; do head -1 "$f"; done \| sort -u` | repo-root | 0 | `---` |
| `grep -l "^name:" skills/*/SKILL.md \| wc -l` | repo-root | 0 | (≥9) |
```

即"frontmatter schema 检查 + 文件存在性"。本任务的"测试"以**人工通过 T10 的 e2e smoke 验收**为准。

### 0.6 Skill frontmatter 约定

所有 SKILL.md 顶部 frontmatter **仅两个必填字段**（看现有 7 个 skill 推断的约定）：

```yaml
---
name: <skill 名，与目录名严格一致>
description: |
  <多行 description，含触发关键词与场景描述。中文优先，可混英文关键词>
---
```

**不需要** version / tags / author / model 等其他字段。多写无害但不必要。

### 0.7 Reviewer subagent Tools 约束

T4/T5/T6 dispatch 的 R1/R2/R3 子 agent **必须只用读 + 检索类工具**：

| 允许 | 禁用 |
|------|------|
| Read / Bash（只读命令）/ Grep / Glob / WebFetch | Edit / Write / NotebookEdit |

在每个 reviewer prompt 末尾**显式写明**："你只能使用 Read/Bash/Grep/Glob 工具，禁止 Edit/Write——你的输出是 mini-report 字符串，不是代码改动"。

### 0.8 Reviewer Pass/Fail 统一判定

| Reviewer | Pass 条件 | Fail 条件 |
|----------|----------|----------|
| R1 spec-conformance | P0 列表为空 | P0 列表非空 |
| R2 boundary-coverage | P0 列表为空 | P0 列表非空 |
| R3 test-integrity | P0 列表为空 | P0 列表非空 |

**P1 在所有 reviewer 都不阻塞 status**，仅写入报告供 x-fix 选择性修。

### 0.9 时序约定（避免循环依赖困惑）

- T3 提交 x-qua-gate/SKILL.md 时，`references/r1-*.md` `r2-*.md` `r3-*.md` **还不存在**——这是有意为之（先建框架后填内容）。
- T3 提交后 x-qua-gate 是"占位 skill"，**不能真跑**；T4-T6 全部完成后才完整可用。
- T3 commit message 必须注明 `framework only, references in T4-T6`。
- 类似地 T7 的 x-fix 改造依赖 T2/T3 已落地——T7 之前 T2/T3 必须完成。

### 0.10 Reviewer 输入材料缺失时的稳健性

如果你被 dispatch 为 R1/R2/R3 子 agent，发现主 agent 注入的 prompt **缺失了关键材料**（README.md 内容 / git diff 等）：

- ❌ 不要凭推测下结论
- ❌ 不要尝试自行 Bash 找文件（你不在 task 工作目录的对话上下文里）
- ✅ 立刻输出 mini-report，**Status: ERROR-MATERIAL-MISSING**，列出缺失项
- ✅ 让主 agent 决策——重新 dispatch（带完整材料）或人工干预

---

## File Structure

### 新建 skill 目录
- `skills/x-verify/SKILL.md` — Gate ① 命令复跑 skill 入口
- `skills/x-verify/templates/verify-report-template.md` — 验证报告模板
- `skills/x-qua-gate/SKILL.md` — Gate ② 评审 skill 入口（取代 x-cr）
- `skills/x-qua-gate/references/r1-spec-conformance.md` — R1 reviewer 子 agent prompt
- `skills/x-qua-gate/references/r2-boundary-coverage.md` — R2 reviewer 子 agent prompt
- `skills/x-qua-gate/references/r3-test-integrity.md` — R3 reviewer 子 agent prompt（含反模式规则集）
- `skills/x-qua-gate/templates/qa-gate-report-template.md` — 聚合报告模板
- `skills/x-audit-perf/SKILL.md` — 性能巡检 skill
- `skills/x-audit-perf/templates/audit-perf-template.md` — 性能巡检报告模板
- `skills/x-audit-style/SKILL.md` — 规范巡检 skill
- `skills/x-audit-style/templates/audit-style-template.md` — 规范巡检报告模板

### 修改现有 skill
- `skills/x-dev/SKILL.md` — 加 dev-report.md 输出约束 + 改下游链路
- `skills/x-qdev/SKILL.md` — 加 dev-report.md 输出约束 + 改下游链路
- `skills/x-fix/SKILL.md` — 加节点分类 fix 报告路径 + 4 条回流规则
- `skills/x-fix/references/qa-gate-fix-mode.md` — 新增：x-qua-gate 触发的 fix 模式
- `skills/x-cr/SKILL.md` — 改为重定向 stub

### 模板文件
- `skills/x-dev/templates/dev-report-template.md` — 新增（如 x-dev 已有 templates/ 则加在那儿）

### 项目级文档
- `README.md` / `README_zh.md` — 更新 skill 链路图与目录约定
- `.claude-plugin/plugin.json` — 更新 skill 列表（如有 manifest 文件）

---

## 依赖关系

```
T1 (dev-report schema)
  ↓
T2 (x-verify) ────────────────┐
  ↓                            │
T3 (x-qua-gate 框架)            │
  ↓                            │
T4 (R1) → T5 (R2) → T6 (R3)    │
                  ↓             │
T7 (x-fix 回流改造) ←───────────┘
  ↓
T10 (x-cr stub + 全局文档)

T8 (x-audit-perf) — 独立，任意时机
T9 (x-audit-style) — 独立，任意时机
```

推荐执行顺序：T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10。

---

## Task 1: dev-report.md schema 与 x-dev / x-qdev 输出改造

**Files:**
- Create: `skills/x-dev/templates/dev-report-template.md`
- Modify: `skills/x-dev/SKILL.md` — 加输出 dev-report 的约束段落
- Modify: `skills/x-qdev/SKILL.md` — 同样加输出 dev-report 约束
- Test: `dev-pipeline/tasks/qa-gate-pipeline/_smoke/dev-report-sample.md`（人工构造样例验证 schema）

- [ ] **Step 1: 写 dev-report 模板文件**

创建 `skills/x-dev/templates/dev-report-template.md`，内容：

```markdown
# Dev Report — <task-name> — YYYYMMDD-HHmmss

## 改动文件清单
- <绝对路径或仓库相对路径>
- ...

## 验证命令清单
> ⚠️ **本节是 x-verify 的输入。x-verify 会复跑下表全部命令并对比 exit code 与关键输出。**
> ⚠️ 至少必须包含一条"测试"类命令；项目无测试框架时必须显式写 `no-test-framework: true` 行 + 理由。

| 命令 | 工作目录 | 预期 exit | 关键输出片段（用于 grep 校验） |
|------|---------|----------|------------------------------|
| `npm run build` | 项目根 | 0 | `Compiled successfully` |
| `npm test` | 项目根 | 0 | `Tests: 42 passed` |
| `npm run lint` | 项目根 | 0 | `0 errors` |

## 自检结论
本人（x-dev / x-qdev）已在本机完整运行上述命令，确认全部通过。
本报告由 <skill 名> 于 <UTC 时间戳> 生成。
```

- [ ] **Step 2: 验证模板文件存在并字段完整**

Run: `grep -E "^(## 改动文件清单|## 验证命令清单|## 自检结论)" /Volumes/machub_app/proj/x-dev-pipeline/skills/x-dev/templates/dev-report-template.md | wc -l`
Expected: `3`（三个必填段全部出现）

- [ ] **Step 3: 修改 x-dev SKILL.md，在"任务结束动作"段加输出约束**

锚点（已对照 Preflight 0.2 现状）：
1. **首选**：在 `## 自动流转规则（连续开发模式）` (≈line 385) 之后、`## 连续开发汇报` (≈line 428) 之前插入新段。这位置在语义上最贴——dev-report 是连续开发汇报的产物之一。
2. **兜底**：文件末尾追加（commit message 注明 "appended at EOF, anchor missing"）。

⚠️ 必须用 Edit 工具**插入**，禁止 overwrite 整个文件——其它 17 个 H2 段的内容必须保留。

新增段落（直接复制此段进文件）：

```markdown
## 任务完成时必须输出 dev-report.md

每个任务完成后，**除 changelog.md 之外**，必须额外在 `dev-pipeline/tasks/<task>/` 下写入 `dev-report.md`，模板见 `skills/x-dev/templates/dev-report-template.md`。

dev-report.md 是 x-verify 的唯一输入。规则：
1. 验证命令清单**至少包含一条测试类命令**；项目无测试框架时必须显式声明 `no-test-framework: true` + 理由。
2. 命令必须可在项目根目录直接运行，**不允许依赖 dev 临时设置的环境变量**。
3. 自检结论段必须由 x-dev 自己运行命令后填写，不能空着或写"应该能跑"。
4. 写完 dev-report.md 后，下游自动衔接 x-verify（不再走老 x-cr）。
```

- [ ] **Step 4: 同样修改 x-qdev SKILL.md**

锚点（已对照 Preflight 0.2 现状）：
1. **首选**：在 `## 第六步：收尾` (≈line 160) 之前插入新段（保留原步骤编号体系）。
2. **次选**：在 `## 第七步：提醒提交` (≈line 167) 之前插入。
3. **兜底**：文件末尾追加。

插入与 Step 3 **一字不差的同一段内容**（"任务完成时必须输出 dev-report.md" 全文）。

- [ ] **Step 5: 把 x-dev/x-qdev 的"自动衔接 x-cr"全部改成"自动衔接 x-verify"**

```bash
cd /Volumes/machub_app/proj/x-dev-pipeline
grep -n "x-cr\|cr-report\|代码审查" skills/x-dev/SKILL.md skills/x-qdev/SKILL.md
```

**重点处理位置**（已对照 Preflight 0.2 现状）：
- `skills/x-qdev/SKILL.md` `## 第五步：代码审查` (≈line 116) — 这是 x-qdev 主要触发 x-cr 的地方，**重点改造此段**
- `skills/x-dev/SKILL.md` `## 自动流转规则（连续开发模式）` (≈line 385) 与 `## 连续开发汇报` (≈line 428) — 两段内若有"调 x-cr"等表述

**改造规则**：
- 把"x-dev / x-qdev 完成后**触发 x-cr**"等描述改为"完成后**触发 x-verify**（→ x-verify 通过后自动衔接 x-qa-gate）"
- 概念性提及"代码审查"作为名词时**保留**（如"代码审查环节"），仅修改具体的 skill 链路指向
- `cr-report` 这种产物名同样保留（仅用于历史报告引用），新报告的产物名是 `verify-report` / `qa-gate-report`

- [ ] **Step 6: 构造 smoke 样例验证模板可填写**

Create: `dev-pipeline/tasks/qa-gate-pipeline/_smoke/dev-report-sample.md`
内容：照模板填一份"模拟"dev-report，命令清单含两条假命令（`echo ok` exit 0、`false` exit 1），用于 T2 测 x-verify 的拦截能力。

```markdown
# Dev Report — qa-gate-pipeline-smoke — 20260427-150000

## 改动文件清单
- (smoke test, no real changes)

## 验证命令清单
| 命令 | 工作目录 | 预期 exit | 关键输出片段 |
|------|---------|----------|------------|
| `echo passing-command` | 项目根 | 0 | `passing-command` |
| `false` | 项目根 | 0 | (none) |

## 自检结论
本人（smoke test）已在本机运行上述命令。
```

注意：第二条 `false` 实际 exit 1 但写预期 0——故意制造不一致，让 x-verify (T2) 能拦下。

- [ ] **Step 7: Commit**

```bash
git add skills/x-dev/templates/dev-report-template.md \
        skills/x-dev/SKILL.md \
        skills/x-qdev/SKILL.md \
        dev-pipeline/tasks/qa-gate-pipeline/_smoke/dev-report-sample.md
git commit -m "feat(x-dev,x-qdev): 添加 dev-report.md 输出约束作为 x-verify 输入"
```

---

## Task 2: x-verify skill 实现

**Files:**
- Create: `skills/x-verify/SKILL.md`
- Create: `skills/x-verify/templates/verify-report-template.md`
- Test: 用 T1 的 smoke sample 验证拦截行为

- [ ] **Step 1: 写 x-verify SKILL.md（完整内容，照下面复制）**

```markdown
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

**fix-counter 协议**（详见 plan Preflight 0.4）：

- 路径：`<task>/reports/.fix-counter`，格式：单行 ASCII 整数 + 换行
- **首次创建责任在 x-verify**：进入 x-verify 时，如 `reports/.fix-counter` 不存在 → `mkdir -p reports && echo 0 > reports/.fix-counter`
- 读取时 `c=$(cat reports/.fix-counter)`
- 触发 x-fix 时（命令复跑出现 fail）：先递增 `echo $((c+1)) > reports/.fix-counter` 再交给 x-fix
- counter < 6：递增并触发 x-fix（mode: verify-fix）
- counter >= 6：**不递增**，停下生成 `reports/fix-blocked-report.md` 列出所有积压问题，等用户决策（继续 / 修改需求 / 放弃）

**重置时机**：整个 verify → R1 → R2 → R3 链路全部 pass 时，由 x-qua-gate 在 R3 通过后 `echo 0 > reports/.fix-counter`。x-verify 不负责重置。
```

- [ ] **Step 2: 写 verify-report 模板**

Create: `skills/x-verify/templates/verify-report-template.md`

```markdown
# Verify Report — <task-name> — YYYYMMDD-HHmmss

**Status:** pass / fail
**dev-report 来源:** dev-pipeline/tasks/<task>/dev-report.md
**fix-attempts:** N / 6

## 命令复跑结果

| # | 命令 | 预期 exit | 实际 exit | 预期输出片段 | 输出含此片段? | 结果 |
|---|------|----------|----------|------------|--------------|------|
| 1 | `npm run build` | 0 | 0 | `Compiled successfully` | ✓ | ✅ pass |
| 2 | `npm test` | 0 | 1 | `Tests: 42 passed` | ✗ | ❌ fail |

## 失败命令详情

### 命令 #2: `npm test`
- **stdout 摘录** (前 50 行):
  ```
  ...
  ```
- **stderr 摘录**:
  ```
  ...
  ```

## 下游动作

- [ ] 全部 pass → 触发 x-qua-gate
- [ ] 任一 fail → 触发 x-fix（mode: verify-fix），fix-attempts +1
```

- [ ] **Step 3: 验证 SKILL.md frontmatter 合法**

Run: `head -10 /Volumes/machub_app/proj/x-dev-pipeline/skills/x-verify/SKILL.md`
Expected: 第 1 行是 `---`，第 2 行是 `name: x-verify`，必须以 `---` 闭合 frontmatter。

- [ ] **Step 4: 手动按 SKILL.md 流程执行 smoke sample 验证**

⚠️ "dry-run" 不是某种工具命令——它指**手工按 x-verify SKILL.md 写的流程跑一遍**，验证 SKILL.md 的逻辑能产出正确报告。

具体动作：
1. 读取 T1 Step 6 创建的 `dev-pipeline/tasks/qa-gate-pipeline/_smoke/dev-report-sample.md`
2. 解析里面的命令清单（应有 2 条：`echo passing-command` 和 `false`）
3. 在 Bash 里实际跑两条命令：
   ```bash
   cd /Volumes/machub_app/proj/x-dev-pipeline
   bash -c "echo passing-command"; echo "exit=$?"   # 期望 exit=0，输出含 "passing-command"
   bash -c "false"; echo "exit=$?"                  # 期望 exit=1，但 sample 里写预期是 0
   ```
4. 按 templates/verify-report-template.md 格式手填一份 verify-report，写到 `dev-pipeline/tasks/qa-gate-pipeline/_smoke/verify-report-manual.md`
5. 验证报告内容：

```bash
grep -E "(命令 #2|❌|fail|触发 x-fix)" dev-pipeline/tasks/qa-gate-pipeline/_smoke/verify-report-manual.md
```
Expected: 至少 4 行命中（命令 #2 标 fail、整体 status fail、下游动作含触发 x-fix）。

这一步**只是验证 SKILL.md 的流程描述是否清晰可执行**，不是真触发 x-verify。

- [ ] **Step 5: Commit**

```bash
git add skills/x-verify/
git commit -m "feat(x-verify): 实现 Gate ① 命令复跑事实验证 skill"
```

---

## Task 3: x-qua-gate skill 框架（聚合层）

**Files:**
- Create: `skills/x-qua-gate/SKILL.md`
- Create: `skills/x-qua-gate/templates/qa-gate-report-template.md`

- [ ] **Step 1: 写 x-qua-gate SKILL.md**

```markdown
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
```

- [ ] **Step 2: 写聚合报告模板**

Create: `skills/x-qua-gate/templates/qa-gate-report-template.md`

```markdown
# QA Gate Report — <task-name> — YYYYMMDD-HHmmss

**Status:** pass / R1-fail / R2-fail / R3-fail
**fix-attempts:** N / 6
**verify-report:** reports/verify/verify-report-*.md

## 总览

| Reviewer | 状态 | round |
|----------|-----|-------|
| R1 spec-conformance | ✅ pass / ❌ fail / ⏸ pending | 1 |
| R2 boundary-coverage | ⏸ pending | - |
| R3 test-integrity | ⏸ pending | - |

## R1 spec-conformance 详情

> opus 子 agent 输出（reviewer prompt: references/r1-spec-conformance.md）

[mini-report 内容粘贴在此]

## R2 boundary-coverage 详情

[pending / mini-report]

## R3 test-integrity 详情

[pending / mini-report]

## fix 历史

| 时间 | 触发节点 | fix mode | 回流目标 | round |
|------|---------|---------|---------|-------|
| 2026-04-27 14:23 | R1 | r1-spec-fix | R1 | 1 |
| 2026-04-27 14:35 | R2 | r2-boundary-fix | R1 (业务逻辑改动) | 2 |
```

- [ ] **Step 3: 验证 SKILL.md 与模板存在**

Run: `ls /Volumes/machub_app/proj/x-dev-pipeline/skills/x-qua-gate/`
Expected: 看到 `SKILL.md` `templates/`（references/ 在 T4-T6 加）

- [ ] **Step 4: Commit**

```bash
git add skills/x-qua-gate/SKILL.md skills/x-qua-gate/templates/
git commit -m "feat(x-qua-gate): 实现 Gate ② 评审 skill 框架（reviewer 由后续 task 接力）"
```

---

## Task 4: R1 spec-conformance reviewer

**Files:**
- Create: `skills/x-qua-gate/references/r1-spec-conformance.md`

- [ ] **Step 1: 写 R1 reviewer prompt**

Create: `skills/x-qua-gate/references/r1-spec-conformance.md`

```markdown
# R1 — Spec Conformance Reviewer

> 本文件是 x-qua-gate 在 dispatch R1 子 agent 时塞进 prompt 的"评审手册"。子 agent 必须用 model=opus。

## 你的角色

你是一个独立的 spec 符合性审查员。你**不修改代码**，只输出 mini-report。

## 输入

主 agent 会塞给你以下材料：
1. 当前任务的 README.md（需求文档）
2. 当前任务的 plan.md（实现计划）
3. 当前任务的 dev-checklist.md（任务清单当前状态）
4. 当前任务的 changelog.md（dev 自报改动）
5. 当前 git diff（vs task 起点）

## 检查清单（5 条）

逐条对照需求文档，回答下列问题：

1. **逐条需求实现核查**：README.md 里写的每条要求，git diff 中是否都能找到对应代码？列出"需求 X 没找到对应实现"的所有项。

2. **dev-checklist 一致性**：dev-checklist.md 中标 ✅ / 🟢 的任务，git diff 中是否都能找到对应改动？列出"标完成但 diff 里没改动"的任务编号。

3. **过度实现**：git diff 里是否包含 README.md 没要求的功能？列出多余功能（用户没要的别给）。

4. **偏离 spec**：是否有"README 里写要 X 但代码做了 Y"的情况？列出每处偏离 + 行号。

5. **scope creep**：改动是否影响了任务范围之外的代码？列出 task 边界外的改动文件。

## 严重度

- 任何 1-4 条命中 → **P0**（spec 不符）
- 第 5 条（scope creep） → **P1**

## 输出格式

```markdown
# R1 Spec-Conformance Mini-Report

**Status:** pass / fail

## P0 问题（必修）

### #1 [需求未实现] README 第 X 节要求 Y，代码中未找到对应实现
- 需求原文: "..."
- 期望改动文件: src/...
- 实际 diff: 无
- 建议: 实现 ... 函数

### #2 [偏离 spec] README 要求 X 但代码做了 Y
...

## P1 问题（建议）

### #1 [scope creep] 改动了 task 范围外的文件 src/unrelated.ts
...

## 通过项（已对照）

- [x] 需求 1: ...
- [x] 需求 2: ...
```

## 通过条件

- **Status: pass** ⟺ P0 列表为空
- **Status: fail** ⟺ P0 列表非空
- P1 **不阻塞 status**，但要列出供 x-fix 选择性修

## 工具约束

你只能使用这些工具：**Read / Bash（只读命令）/ Grep / Glob / WebFetch**。
**禁止**使用 Edit / Write / NotebookEdit——你的输出是 mini-report **字符串**，不是代码改动。

## 输入材料缺失时（稳健性）

如果主 agent 注入的 prompt 没塞给你 README.md / plan.md / git diff 等关键材料：
- ❌ 不要凭推测下结论
- ❌ 不要尝试自行 Bash 找文件（你不在 task 工作目录的对话上下文里）
- ✅ 立刻输出 mini-report，**Status: ERROR-MATERIAL-MISSING**，列出缺失项
- ✅ 让主 agent 决策

## 你不该做的事

- ❌ 修改任何代码
- ❌ 评价代码风格 / 性能 / 命名（那不是 R1 的事，是 R2/R3 或 audit 的事）
- ❌ 跑测试或 build（那是 x-verify 已做的事）
- ❌ 给"建议但不重要"的改进意见（你只输出 P0/P1 阻塞性问题）
```

- [ ] **Step 2: 验证文件存在且关键章节完整**

Run: `grep -E "^(## (你的角色|输入|检查清单|严重度|输出格式|通过条件|你不该做的事))" /Volumes/machub_app/proj/x-dev-pipeline/skills/x-qua-gate/references/r1-spec-conformance.md | wc -l`
Expected: `7`

- [ ] **Step 3: Commit**

```bash
git add skills/x-qua-gate/references/r1-spec-conformance.md
git commit -m "feat(x-qua-gate): 添加 R1 spec-conformance reviewer prompt"
```

---

## Task 5: R2 boundary-coverage reviewer

**Files:**
- Create: `skills/x-qua-gate/references/r2-boundary-coverage.md`

- [ ] **Step 1: 写 R2 reviewer prompt**

Create: `skills/x-qua-gate/references/r2-boundary-coverage.md`

```markdown
# R2 — Boundary Coverage Reviewer

> 本文件是 x-qua-gate 在 dispatch R2 子 agent 时塞进 prompt 的"评审手册"。子 agent 必须用 model=opus。

## 你的角色

你是一个独立的边界完整性审查员。R1 已通过（功能本身符合 spec），你的任务是判断这个功能在边界条件下是否还成立。**你不修改代码**，只输出 mini-report。

## 输入

主 agent 会塞给你：
1. 当前任务的 README.md
2. R1 通过后的 git diff
3. 改动涉及的源文件完整内容（不只是 diff，需要整个函数 / 类的上下文判断边界）

## 检查清单（4 类）

### 1. 输入边界

逐个公开函数 / API 入口，检查输入边界是否处理：
- `null` / `undefined` / `None`
- 空字符串 / 空数组 / 空对象
- 超长字符串 / 超大数组
- 0 / 负数 / NaN / Infinity（数值场景）
- Unicode / emoji / RTL 文字 / 控制字符（字符串场景）
- 路径穿越 / 特殊文件名（路径场景）

列出"未处理且会导致 crash / 未定义行为"的边界。

### 2. 状态边界

- 对象未初始化就被使用？
- 部分初始化（一些字段已设、一些未设）？
- 已销毁 / 已关闭的资源被复用？
- 并发竞争（两条 path 同时改一个 state）？

### 3. 错误路径

- 异常分支是否有处理？还是裸抛？
- 是否吞了异常（catch 后空块或只 log 不抛）？
- 错误消息是否含可定位信息（哪个文件 / 哪条记录）？
- 部分失败如何回滚（事务性场景）？

### 4. 边界回归

- 改动了已有函数？原本处理的边界是否仍处理？
- 删了某段防御代码？为什么？是否有新地方接管？

## 严重度

- 输入边界 / 状态边界 → **P0**（生产环境必崩）
- 错误路径吞异常 / 缺错误消息 → **P1**
- 边界回归（破坏原有处理）→ **P0**

## 输出格式

```markdown
# R2 Boundary-Coverage Mini-Report

**Status:** pass / fail

## P0 问题（必修）

### #1 [输入边界] src/foo.ts:42 函数 parseConfig(input) 未处理 null
- 触发条件: 调用方传 null
- 后果: TypeError "Cannot read property 'split' of null"
- 建议: 函数开头加 `if (input == null) throw new InvalidInputError(...)`

### #2 [边界回归] src/bar.ts:88 原本对空数组返回默认值，本次改动后会抛异常
...

## P1 问题（建议）

### #1 [错误路径] src/baz.ts:120 catch 块吞了异常，只 console.log
...
```

## 通过条件

- **Status: pass** ⟺ P0 列表为空
- **Status: fail** ⟺ P0 列表非空
- P1 **不阻塞 status**，但要列出供 x-fix 选择性修

## 工具约束

你只能使用这些工具：**Read / Bash（只读命令）/ Grep / Glob / WebFetch**。
**禁止**使用 Edit / Write / NotebookEdit——你的输出是 mini-report **字符串**，不是代码改动。

## 输入材料缺失时（稳健性）

如果主 agent 注入的 prompt 没塞给你 README.md / 源文件内容 / git diff 等关键材料：
- ❌ 不要凭推测下结论
- ❌ 不要尝试自行 Bash 找文件
- ✅ 立刻输出 mini-report，**Status: ERROR-MATERIAL-MISSING**，列出缺失项
- ✅ 让主 agent 决策

## 你不该做的事

- ❌ 修改任何代码
- ❌ 检查 spec 符合性（那是 R1 的事，已经过了）
- ❌ 检查测试代码（那是 R3 的事）
- ❌ 评价代码风格 / 性能 / 命名（audit 的事）
```

- [ ] **Step 2: 验证文件**

Run: `grep -E "^### [0-9]\. " /Volumes/machub_app/proj/x-dev-pipeline/skills/x-qua-gate/references/r2-boundary-coverage.md | wc -l`
Expected: `4`（4 类边界检查）

- [ ] **Step 3: Commit**

```bash
git add skills/x-qua-gate/references/r2-boundary-coverage.md
git commit -m "feat(x-qua-gate): 添加 R2 boundary-coverage reviewer prompt"
```

---

## Task 6: R3 test-integrity reviewer（含反模式规则集）

**Files:**
- Create: `skills/x-qua-gate/references/r3-test-integrity.md`

- [ ] **Step 1: 写 R3 reviewer prompt**

Create: `skills/x-qua-gate/references/r3-test-integrity.md`

```markdown
# R3 — Test Integrity Reviewer ⭐ 反"测试镜像化" 核心

> 本文件是 x-qua-gate 在 dispatch R3 子 agent 时塞进 prompt 的"评审手册"。子 agent 必须用 model=opus。

## 你的角色

你是一个独立的测试真实性审查员。R1 (spec) 与 R2 (边界) 都已通过——代码功能正确、边界齐全。你的任务是判断**测试是否真的在测当前代码**，而不是镜像化（自己复制业务逻辑到测试里、用业务函数算期望值）。**你不修改代码**，只输出 mini-report。

## 为什么这条最重要

很多 AI 写测试时会犯"测试镜像化"的错——测试代码里复制一遍业务逻辑做断言。这种测试**永远会通过**，因为代码改了它也跟着改；但发现 bug 的能力等于零。R3 就是要拦下这种"假测试"。

### 反模式举例（你必须能识别这些）

```python
# ❌ 反模式 A：测试里 reimplement 业务逻辑
def test_calculate_total():
    cart = Cart()
    cart.add_item("apple", 10)
    cart.add_item("banana", 20)
    # 在测试里"自己算一遍"做断言 — 业务函数改了 total 公式（比如加税），测试不会挂
    assert cart.total == 10 + 20
# ✅ 正确：写死期望值
def test_calculate_total():
    cart = Cart()
    cart.add_item("apple", 10)
    cart.add_item("banana", 20)
    assert cart.total == 30  # 业务函数改了，测试一定要更新

# ❌ 反模式 B：测试里复制 workflow 步骤
def test_workflow():
    step1 = do_step_a()
    step2 = do_step_b(step1)
    step3 = do_step_c(step2)
    assert step3 == "expected"
# ✅ 正确：调顶层入口
def test_workflow():
    result = workflow.execute()
    assert result == "expected"

# ❌ 反模式 C：mock 掉被测对象自己
def test_user_service():
    service = UserService()
    service.create_user = Mock(return_value=fake_user)  # 你 mock 了被测函数！
    result = service.create_user("alice")
    assert result == fake_user  # 测了个寂寞
```

## 输入

主 agent 会塞给你：
1. 当前任务的 README.md
2. R2 通过后的 git diff（重点关注测试文件 vs 业务文件改动比）
3. 测试文件完整内容
4. 被测代码完整内容
5. 测试运行命令（来自 dev-report.md）

## 检查清单（5 条）

### 1. import 检查

测试文件是否真的 import 了被测代码？
- 用 `grep "import" tests/...` 看 import 链
- 如果测试只 import 了 mock 库 / 第三方库，没 import 项目代码 → P0
- 如果 import 了被测代码但只用一次 → 可疑

### 2. 顶层 API 调用

测试是否调用被测代码的入口函数 / 顶层 API？
- 如果测试把被测代码的步骤手动复制了一遍 → P0（反模式 B）
- 应该看到测试函数体里有"调入口 → 拿结果 → 断言"三段式

### 3. 断言契约性

断言值是写死的期望，还是又用业务函数算了一遍？
- `assert result == 30`（写死）→ ✅
- `assert result == calculate_expected(input)`（再调一次业务）→ P0（反模式 A）
- `assert result == sum(prices)`（在测试里 reimplement 业务逻辑）→ P0

### 4. mock 边界

被 mock 的对象是不是被测代码自己（自我 mock）？
- mock 外部依赖（数据库 / HTTP / 文件系统）→ ✅
- mock 被测函数本身 → P0（反模式 C）
- mock 范围超过 50% 测试对象 → P1（过度 mock）

### 5. 改动覆盖

本次 dev 改了哪些函数？测试是否真的触发了它们？
- 用 `git diff --name-only` 拿到改动文件
- 对每个改动函数：grep 测试文件，看是否有调用
- 如果改动函数 100% 没被任何测试调用 → P0

## 严重度

- 反模式 A/B/C → **P0**（测试无意义）
- 改动函数无测试覆盖 → **P0**
- 过度 mock → **P1**

## 输出格式

```markdown
# R3 Test-Integrity Mini-Report

**Status:** pass / fail

## P0 问题（必修）

### #1 [反模式 A] tests/cart.test.ts:42 用 reduce 在测试里 reimplement total 公式
- 测试代码:
  ```ts
  assert(cart.total === items.reduce((s, i) => s + i.price, 0))
  ```
- 问题: 业务函数改了 total 公式（比如加税）测试不会挂
- 建议: 改写死值 `assert(cart.total === 30)`

### #2 [反模式 C] tests/user.test.ts:88 mock 掉了被测函数 createUser
...

### #3 [改动无覆盖] src/payment.ts:120 函数 refund() 本次改动但无测试触发
...

## P1 问题（建议）

### #1 [过度 mock] tests/order.test.ts mock 了 8/10 依赖
...
```

## 通过条件

- **Status: pass** ⟺ P0 列表为空
- **Status: fail** ⟺ P0 列表非空
- P1 **不阻塞 status**，但要列出供 x-fix 选择性修

## 工具约束

你只能使用这些工具：**Read / Bash（只读命令）/ Grep / Glob / WebFetch**。
**禁止**使用 Edit / Write / NotebookEdit——你的输出是 mini-report **字符串**，不是代码改动。
你**可以**用 Bash 跑只读命令（如 `git diff`, `grep -r`）来辅助分析，但不要执行测试或写文件。

## 输入材料缺失时（稳健性）

如果主 agent 注入的 prompt 没塞给你 README.md / 测试文件内容 / 被测代码内容 / git diff 等关键材料：
- ❌ 不要凭推测下结论
- ❌ 不要尝试自行 Bash 找文件
- ✅ 立刻输出 mini-report，**Status: ERROR-MATERIAL-MISSING**，列出缺失项
- ✅ 让主 agent 决策

## 你不该做的事

- ❌ 修改任何代码（业务或测试）
- ❌ 重新跑测试（x-verify 已做）
- ❌ 检查 spec 符合性 / 边界完整性（R1/R2 已做）
- ❌ 评价代码风格 / 性能（audit 的事）
```

- [ ] **Step 2: 验证反模式举例齐全**

Run: `grep -c "反模式 [ABC]" /Volumes/machub_app/proj/x-dev-pipeline/skills/x-qua-gate/references/r3-test-integrity.md`
Expected: `>=6`（每个反模式至少出现 2 次：举例 + 检查清单引用）

- [ ] **Step 3: Commit**

```bash
git add skills/x-qua-gate/references/r3-test-integrity.md
git commit -m "feat(x-qua-gate): 添加 R3 test-integrity reviewer prompt（反测试镜像化）"
```

---

## Task 7: x-fix 失败回流改造

**Files:**
- Modify: `skills/x-fix/SKILL.md` — 加 4 条回流规则 + fix-counter 共享逻辑
- Create: `skills/x-fix/references/qa-gate-fix-mode.md` — qa-gate fail 触发的 fix 子模式

- [ ] **Step 1: 在 x-fix/SKILL.md 加"回流规则"段落**

锚点选择（已对照 Preflight 0.2 现状）：
1. **首选**：在 `## 自动流转规则（连续开发模式）` (≈line 81) 之后插入新段。这是与本次改造语义最贴的位置——把 verify/qa-gate 触发的回流规则放在原"自动流转规则"段附近，便于读者对照。
2. **次选**：在 `## CR 报告修复（模式 2）输出` (≈line 64) 之后。
3. **兜底**：文件末尾追加（commit message 注明 "appended at EOF, anchor missing"）。

⚠️ x-fix **没有** "两种模式" 段（那是 x-cr 的）。不要找这个名字。
⚠️ 必须用 Edit 工具**插入**新段，**不要 overwrite 整个文件**——会破坏 line 13/64/81 这三段已有内容。

插入内容：

```markdown
## 失败回流规则（qa-gate-pipeline 改造）

x-fix 不只服务于 bug 报告与 cr-report，也接收来自 x-verify / x-qua-gate R1/R2/R3 的 fail 触发。fix 完成后，**回到哪个节点重审**按下列优先级匹配（命中即停）：

1. fix 涉及函数签名变化 / 新增/删除公开 API → **必须回 R1**
2. fix 改动了被测代码的核心业务逻辑文件（非测试 / 非配置 / 非注释）→ **必须回 R1**
3. fix 只改测试文件 / 配置 / 文档 / 注释 → **回当前失败节点**
4. 其他不确定情况 → **保守回 R1**

### fix-attempts 6 次共享上限

读取 `dev-pipeline/tasks/<task>/reports/.fix-counter`（不存在则视为 0）。

- 任何 verify / R1 / R2 / R3 fail 触发 x-fix 时，**先把 counter +1 再开始 fix**（避免崩溃后死循环）。
- counter >= 6 → 不进 fix，直接生成 `reports/fix-blocked-report.md`，要求用户决策（继续 / 修改需求 / 放弃）。
- 任务最终通过 x-qua-gate（R3 pass）后，由 x-qua-gate 把 counter 重置为 0。

### fix 报告路径分类

按触发节点分别写到不同子目录：

| 触发节点 | fix 报告路径 |
|---------|-------------|
| x-verify fail | `reports/fix/fix-verify-YYYYMMDD-HHmmss.md` |
| R1 fail | `reports/fix/fix-r1-spec-YYYYMMDD-HHmmss.md` |
| R2 fail | `reports/fix/fix-r2-boundary-YYYYMMDD-HHmmss.md` |
| R3 fail | `reports/fix/fix-r3-test-YYYYMMDD-HHmmss.md` |

旧路径 `reports/fix/fix-report-*.md` 与 `fix-note-*.md` 仍保留，**只用于直接 bug fix 模式**（用户报告 bug 走原流程）。
```

- [ ] **Step 2: 创建 qa-gate-fix-mode.md**

Create: `skills/x-fix/references/qa-gate-fix-mode.md`

```markdown
# x-fix · qa-gate-fix-mode

> 当 x-fix 由 x-verify 或 x-qua-gate 的 R1/R2/R3 触发时，进入本模式。

## 输入识别

- 入参里包含 `verify-report-*.md` 路径 → mode: verify-fix
- 入参里包含 `qa-gate-report-*.md` 中 R1 fail → mode: r1-spec-fix
- 入参里包含 R2 fail → mode: r2-boundary-fix
- 入参里包含 R3 fail → mode: r3-test-fix

## 通用流程

1. 读 fix-counter，counter >= 6 → 生成 fix-blocked-report.md，停。
2. counter +1，写回 .fix-counter。
3. 读对应 fail 报告中的具体问题列表（P0 必修、P1 选修、P2 跳过）。
4. 逐条修复。
5. 按 SKILL.md 4 条规则判定回流目标，写回流标签到 fix 报告 footer。
6. 写 fix 报告到对应路径（见 SKILL.md 路径表）。
7. 把控制权交给主 agent，由主 agent 触发回流目标节点（x-verify / R1 / R2 / R3）。

## mode 特殊规则

### verify-fix
- 只修让命令 fail 的代码（编译错误 / 测试 fail / lint error）。
- 修完触发回流：默认回 x-verify 重新复跑命令。
- **注意**：不要去改 dev-report.md 里的命令清单或预期 exit！那会绕过验证。

### r1-spec-fix
- 修 spec 不符问题（缺实现 / 偏离 / 多余功能）。
- 修完触发回流：回 R1 重审。

### r2-boundary-fix
- 加边界处理代码（null check / 异常处理 / 错误消息）。
- 修完按 4 条规则判：如改了核心业务函数 → 回 R1；只加防御代码 → 回 R2。

### r3-test-fix
- **只改测试代码**，不动业务代码（如果业务代码有问题应该是 R1/R2 拦下）。
- 修完触发回流：回 R3 重审。
- 警告：如果发现"测试改不对是因为业务代码本身有问题"，停下提示用户——这是 R1/R2 的漏检，要回前面节点。
```

- [ ] **Step 3: 验证 SKILL.md 包含新加的回流规则与 fix-counter 协议**

用**精准字符串匹配**避免命中老内容：

```bash
cd /Volumes/machub_app/proj/x-dev-pipeline
echo "=== 4 条回流规则 ==="
grep -c "必须回 R1\|回当前失败节点\|保守回 R1" skills/x-fix/SKILL.md
# Expected: >=4

echo "=== fix-counter 协议 ==="
grep -c "fix-counter\|reports/.fix-counter" skills/x-fix/SKILL.md
# Expected: >=3

echo "=== 新模式文件 ==="
test -f skills/x-fix/references/qa-gate-fix-mode.md && echo "OK"
# Expected: OK
```

- [ ] **Step 4: Commit**

```bash
git add skills/x-fix/SKILL.md skills/x-fix/references/qa-gate-fix-mode.md
git commit -m "feat(x-fix): 加入失败回流规则与 fix-counter 共享上限"
```

---

## Task 8: x-audit-perf skill（独立巡检）

**Files:**
- Create: `skills/x-audit-perf/SKILL.md`
- Create: `skills/x-audit-perf/templates/audit-perf-template.md`

- [ ] **Step 1: 写 x-audit-perf SKILL.md**

```markdown
---
name: x-audit-perf
description: |
  独立性能巡检 skill。不在 x-dev → x-verify → x-qua-gate 主流程内，由用户手动触发或在大里程碑后调用。
  调 opus 子 agent 做全项目视角的性能审查：N² 嵌套、不必要循环、大对象拷贝、同步阻塞、数据库 N+1、缓存失效、不必要的 await。
  触发：用户说"性能巡检"、"audit perf"、"看看有没有性能问题"、"perf review"，或大版本发布前。
---

# x-audit-perf · 性能巡检

x-audit-perf 是独立巡检 skill，**不在 x-dev → x-verify → x-qua-gate 主流程内**。它由用户手动触发或大里程碑后调用，做全项目视角的性能审查。

## 为什么独立

性能问题通常需要**全局视角**才有意义——单个任务级别揪 N² 是过度工程，得看整个调用链；缓存失效要看跨服务流。塞进每个任务的 gate 是噪音，所以剥离出来。

## 流程

1. 用户触发（手动调用 / 大里程碑）。
2. dispatch 一个 opus 子 agent，prompt 包含本 SKILL.md 的检查清单 + 项目代码。
3. 子 agent 输出 audit-perf 报告。
4. 写到 `reports/audit/audit-perf-YYYYMMDD-HHmmss.md`。
5. 不自动触发 x-fix——由用户决定哪些问题进入 backlog。

## 子 agent dispatch

```
Agent({
  description: "Performance audit",
  subagent_type: "general-purpose",
  model: "opus",
  prompt: <本 SKILL.md 的"检查清单"段 + 项目代码 + 输出格式>
})
```

## 检查清单

### 1. 算法复杂度
- 嵌套循环：O(n²) 以上是否必要？能否用 hash / index 降到 O(n)?
- 在循环内做 I/O / 重复扫描数据？
- 排序 / 查找算法选择是否合理？

### 2. 数据结构使用
- 用 list 做频繁查找（应该用 set / dict）？
- 大对象拷贝（应传引用 / 用 slice）？
- 频繁字符串拼接（应用 builder / join）？

### 3. I/O 模式
- 同步阻塞 I/O 在异步上下文中？
- 数据库 N+1（在循环里查数据库）？
- 文件 / 网络请求未批量化？

### 4. 缓存与状态
- 重复计算未缓存（纯函数 expensive call）？
- 缓存失效策略缺失或过激进？
- 内存泄漏（持有不必要的引用）？

### 5. 并发与并行
- 不必要的 await / lock 串行化？
- 临界区过大？
- 能并行的串行执行了？

## 输出

写入 `reports/audit/audit-perf-YYYYMMDD-HHmmss.md`，模板见 `templates/audit-perf-template.md`。

## 不在范围

- 单任务级别的 perf 审查（应在 x-qua-gate R2 boundary 里捎带 P1 即可）
- 微优化（编译器能搞定的事）
- 硬件相关（CPU 缓存、SIMD 等，不在 AI 评审范围）
```

- [ ] **Step 2: 写 audit-perf 模板**

Create: `skills/x-audit-perf/templates/audit-perf-template.md`

```markdown
# Performance Audit Report — YYYYMMDD-HHmmss

**审查范围**: <项目根 / 子目录>
**触发原因**: 手动 / 大里程碑

## 总览

| 严重度 | 数量 |
|--------|-----|
| P0 (生产风险) | N |
| P1 (建议优化) | N |
| P2 (信息性) | N |

## P0 问题

### #1 [N+1] src/order_service.ts:42 在 forEach 里查数据库
- 上下文: ...
- 影响: 100 个订单触发 100 次 SQL
- 建议: 用 IN 查询批量取

## P1 问题

### #1 [O(n²)] src/match.ts:88 双层 for + indexOf
...

## P2 问题（信息性）

### #1 [缓存机会] ...

## 后续动作建议

- [ ] 把 P0 问题加入 backlog
- [ ] P1 问题排期
- [ ] P2 仅记录，不必处理
```

- [ ] **Step 3: 验证文件**

Run: `head -10 /Volumes/machub_app/proj/x-dev-pipeline/skills/x-audit-perf/SKILL.md`
Expected: 第 1 行 `---`，第 2 行 `name: x-audit-perf`。

- [ ] **Step 4: Commit**

```bash
git add skills/x-audit-perf/
git commit -m "feat(x-audit-perf): 新增独立性能巡检 skill"
```

---

## Task 9: x-audit-style skill（独立巡检）

**Files:**
- Create: `skills/x-audit-style/SKILL.md`
- Create: `skills/x-audit-style/templates/audit-style-template.md`

- [ ] **Step 1: 写 x-audit-style SKILL.md**

```markdown
---
name: x-audit-style
description: |
  独立代码规范巡检 skill。不在 x-dev → x-verify → x-qua-gate 主流程内，由用户手动触发或周期性调用。
  调 opus 子 agent 做全项目视角的规范审查：命名一致性、复用机会、magic number、函数长度、文件大小、注释合理性、死代码。
  触发：用户说"规范巡检"、"audit style"、"代码规范检查"、"style review"。
---

# x-audit-style · 代码规范巡检

x-audit-style 是独立巡检 skill，不在主流程内。做全项目视角的代码规范审查。

## 为什么独立

规范问题需要**全局视角**才有意义——单文件命名好但和邻居命名风格不一致，单看局部最优；单任务级别揪命名是过度审查。剥离出来周期巡检更合适。

## 流程

1. 用户触发（手动调用 / 周期性）。
2. dispatch opus 子 agent。
3. 输出 audit-style 报告到 `reports/audit/audit-style-YYYYMMDD-HHmmss.md`。
4. 不自动触发 x-fix——由用户决定。

## 子 agent dispatch

```
Agent({
  description: "Style audit",
  subagent_type: "general-purpose",
  model: "opus",
  prompt: <本 SKILL.md 的"检查清单"段 + 项目代码 + 输出格式>
})
```

## 检查清单

### 1. 命名一致性
- 函数 / 变量命名风格是否项目内统一？（snake_case / camelCase）
- 同概念是否多个名字（比如 user / account / member 混用）？
- 缩写是否一致（id / ID / Id）？

### 2. 复用机会
- 同样的代码在多处出现？提取函数。
- 类似但不完全一样的代码？考虑参数化。
- 多处用同一组 magic number？提取常量。

### 3. magic number / magic string
- 数字 / 字符串字面量没有名字？
- 配置值硬编码在代码里？

### 4. 函数 / 文件大小
- 函数超过 50 行？
- 文件超过 500 行？
- 一个类承担超过 3 件事？

### 5. 注释合理性
- 注释解释 WHAT（应该删，由代码说话）？
- 注释解释 WHY（保留，特别是非显而易见的设计决策）？
- 注释引用过期信息（"used by X"，但 X 已不存在）？

### 6. 死代码
- 未被引用的函数 / 变量 / import？
- 注释掉的代码（应删除，git 已记历史）？
- 永远走不到的分支（unreachable code）？

## 输出

写入 `reports/audit/audit-style-YYYYMMDD-HHmmss.md`，模板见 `templates/audit-style-template.md`。

## 不在范围

- 单任务级别的 style 审查（小范围 lint 工具搞定）
- 自动可修复的（lint 工具 --fix 即可）
- 主观偏好争议（用 lint config 决定，不靠 AI 评审）
```

- [ ] **Step 2: 写 audit-style 模板**

Create: `skills/x-audit-style/templates/audit-style-template.md`

```markdown
# Style Audit Report — YYYYMMDD-HHmmss

**审查范围**: <项目根 / 子目录>
**触发原因**: 手动 / 周期性

## 总览

| 严重度 | 数量 |
|--------|-----|
| P1 (强烈建议) | N |
| P2 (建议) | N |
| P3 (信息性) | N |

## P1 问题

### #1 [复用] src/foo.ts 与 src/bar.ts 有 30 行近乎重复代码
- 位置: foo.ts:42-72, bar.ts:88-118
- 建议: 提取到 src/utils/calc.ts

## P2 问题

### #1 [magic number] src/config.ts:15 用 86400 表示一天秒数
...

## P3 问题（信息性）

### #1 [死代码] src/legacy.ts:42 函数 oldHelper() 0 引用
...

## 后续动作建议

- [ ] P1 问题加入 backlog
- [ ] P2 视情况批量整理
- [ ] P3 顺便清理或忽略
```

- [ ] **Step 3: 验证文件**

Run: `grep -c "^### [0-9]\. " /Volumes/machub_app/proj/x-dev-pipeline/skills/x-audit-style/SKILL.md`
Expected: `6`

- [ ] **Step 4: Commit**

```bash
git add skills/x-audit-style/
git commit -m "feat(x-audit-style): 新增独立代码规范巡检 skill"
```

---

## Task 10: 老 x-cr 重定向 + 全局文档更新

**Files:**
- Modify: `skills/x-cr/SKILL.md` — 改为重定向 stub
- Modify: `README.md` — 更新链路图与 skill 列表
- Modify: `README_zh.md` — 同上
- Modify: `.claude-plugin/plugin.json`（如存在）— 更新 skill 列表
- Modify: `.codex-plugin/`（如存在 manifest）— 同上

- [ ] **Step 1: 把 x-cr/SKILL.md 改为重定向 stub**

Replace `skills/x-cr/SKILL.md` 内容为：

```markdown
---
name: x-cr
description: |
  ⚠️ 已废弃：本 skill 已被 x-qua-gate 取代。请改用 x-qua-gate。
  保留触发关键词以兼容老调用：review、code review、代码审查、检查一下、看看有没有问题、帮我 review、PR 前检查、合并前检查、提交前检查、代码审计。
  当前调用会被自动重定向到 x-qua-gate。
---

# x-cr ⚠️ 已废弃 → 重定向到 x-qua-gate

本 skill 自 qa-gate-pipeline 改造（2026-04-27）起已被 **x-qua-gate** 取代。

## 调用本 skill 时怎么办

立刻**改用 x-qua-gate**——它做了 x-cr 原本的所有事，并把检查拆成 3 个独立 reviewer（spec / 边界 / 测试真实性），用 opus 子 agent 串行评审。

## 旧 cr-report 路径

历史 cr-report 仍在 `reports/cr/cr-report-*.md`，**不会删除**，但新报告写到 `reports/qa-gate/qa-gate-report-*.md`。

## references/ 旧文件

`references/auto-loop-mode.md` 等旧文件保留作历史参考，不再生效。新逻辑见 `skills/x-qua-gate/SKILL.md` 与 `skills/x-fix/references/qa-gate-fix-mode.md`。
```

- [ ] **Step 2: 更新 README_zh.md 链路图（精确替换）**

README_zh.md 现状有两处链路描述需要替换（已对照实际行号）：

**替换点 ①**（≈line 86 附近，"轻路径"链路）：

old_string（保留缩进与代码块）：
```
/x-qdev -> /x-cr -> /x-fix
```
new_string：
```
/x-qdev -> /x-verify -> /x-qua-gate -> /x-fix
```

**替换点 ②**（≈line 142 附近，"完整链路"段）：

old_string：
```
x-spec -> x-req -> x-plan -> x-dev -> x-cr -> x-fix
```
new_string：
```
x-spec -> x-req -> x-plan -> x-dev -> x-verify -> x-qua-gate -> x-fix
```

**替换点 ③**（在两处链路描述附近，新增一段"独立巡检"说明）：

在替换点 ② 所在段之后，append 一段：
```
独立巡检（不在主流程内，按需触发）：
- /x-audit-perf 性能巡检（手动 / 大里程碑）
- /x-audit-style 规范巡检（手动 / 周期）
```

**替换点 ④**（≈line 93/97/173/177 的 `/x-cr` 介绍小节）：

把"`### \`/x-cr\`` ... 描述"段改成：
```
### `/x-cr`（已废弃）
> ⚠️ 自 qa-gate-pipeline 改造起，本 skill 已被 `/x-qua-gate` 取代。调用会自动重定向。详见 skills/x-cr/SKILL.md stub。
```

新增 `/x-verify`、`/x-qua-gate`、`/x-audit-perf`、`/x-audit-style` 各自小节（每节 2-3 行简介，参见各 SKILL.md description 字段直接复用）。

- [ ] **Step 3: 更新 README.md（英文）**

英文 README 的链路描述用同样方式替换（搜 `/x-cr` 字样定位）。如果 README.md 没有链路图段，**跳过此 Step**（在 commit message 注明 "skipped, no chain in README.md"）。

- [ ] **Step 4: 检查 plugin manifest**

Run: `find /Volumes/machub_app/proj/x-dev-pipeline/.claude-plugin /Volumes/machub_app/proj/x-dev-pipeline/.codex-plugin /Volumes/machub_app/proj/x-dev-pipeline/.agents -name "*.json" -o -name "manifest.*" 2>/dev/null`

对每个找到的 manifest 文件：
- Read 它
- 看它是否列了 skill 名单
- 如果列了，加上 `x-verify`、`x-qua-gate`、`x-audit-perf`、`x-audit-style`
- 处理 `x-cr` 的 deprecated 标记：
  - 先看 manifest 现有 schema 是否含 `deprecated` / `disabled` / `tags` 等字段
  - **schema 支持** → 加 `"deprecated": true`
  - **schema 不支持** → 不动 manifest 字段，只在 description 字段开头加 "⚠️ DEPRECATED · 已被 x-qua-gate 取代 ·" 前缀
  - **完全无法表达** → 跳过 manifest 修改，仅靠 SKILL.md 文件本身的 stub 内容做重定向

- [ ] **Step 5: 准备 e2e smoke 脚手架（AI 不真跑闭环）**

⚠️ **重要**：实现 AI **不能在本 plan 执行的子任务里嵌套调用真 x-dev / x-verify / x-qua-gate**——这些 skill 在 T1-T9 完成后才齐备，且需要新会话或用户主动触发才能干净跑。本步骤只**准备脚手架**，由用户后续在新会话里人工触发。

```bash
cd /Volumes/machub_app/proj/x-dev-pipeline
mkdir -p dev-pipeline/tasks/_e2e-smoke/
```

创建 5 个 smoke case 子目录（仅写需求 README.md，不写代码）：

```bash
for case in 01-positive 02-verify-fail 03-r1-fail 04-r2-fail 05-r3-fail; do
  mkdir -p dev-pipeline/tasks/_e2e-smoke/$case
done
```

**Case 01-positive** — 端到端正向通过用例：
写 `dev-pipeline/tasks/_e2e-smoke/01-positive/README.md`：
```markdown
# 01-positive: e2e 正向用例
需求：在仓库根创建 dev-pipeline/tasks/_e2e-smoke/01-positive/output.txt，内容单行 "ok"。
预期：x-dev → x-verify → R1 → R2 → R3 全 pass，fix-counter 始终为 0。
```

**Case 02-verify-fail** — x-verify 拦截：
写 `02-verify-fail/README.md`：
```markdown
# 02-verify-fail: 故意写错 dev-report 预期 exit
需求：同 01-positive。
人工注入：完成 dev 阶段后，手工编辑 dev-report.md，把某条命令的"预期 exit"从 0 改成 99。
预期：x-verify 拦下，生成 status: fail 的 verify-report，fix-counter +1。
```

**Case 03-r1-fail** — R1 拦截：
写 `03-r1-fail/README.md`：
```markdown
# 03-r1-fail: 故意漏实现需求
需求：在仓库根创建 a.txt（内容 "A"）和 b.txt（内容 "B"）两个文件。
人工注入：让 dev 只创建 a.txt，不创建 b.txt。
预期：x-verify pass（命令清单跑通），R1 拦下"需求 b.txt 未实现"，fix-counter +1。
```

**Case 04-r2-fail** — R2 拦截：
写 `04-r2-fail/README.md`：
```markdown
# 04-r2-fail: 故意不处理边界
需求：写一个函数 normalize(s) 把字符串去空格转小写。
人工注入：让 dev 实现时不处理 null 输入（直接 s.trim() 会 NPE）。
预期：x-verify pass，R1 pass，R2 拦下"未处理 null 输入"，fix-counter +1。
```

**Case 05-r3-fail** — R3 拦截（反测试镜像化）：
写 `05-r3-fail/README.md`：
```markdown
# 05-r3-fail: 故意写"测试镜像化"代码
需求：写 calculateTotal(items) 函数 + 单元测试。
人工注入：让 dev 在测试里用 reduce 复制业务公式做断言，而不是写死期望值。
预期：x-verify/R1/R2 全 pass，R3 拦下"反模式 A 测试镜像化"，fix-counter +1。
```

⚠️ 这 5 个 case 只写 README.md（需求文档），**不写实现代码**，留给用户在新会话里逐个触发 x-qdev 走完整链路验证。

- [ ] **Step 6: 在 dev-checklist 里登记 e2e 验收为"待用户人工触发"**

修改 `dev-pipeline/tasks/qa-gate-pipeline/dev-checklist.md` 中的"验收联通测试"段，把 5 个 checkbox 改为：

```markdown
## 验收联通测试（须用户在新会话人工触发）

⚠️ AI 实现只准备 5 个 case 的 README.md 脚手架（位于 `dev-pipeline/tasks/_e2e-smoke/`），实际触发跑链路必须由用户在新会话执行。

- [ ] Case 01-positive: 端到端正向通过 — 用户跑过且 reports/.fix-counter 为 0
- [ ] Case 02-verify-fail: x-verify 拦下 — 用户确认 verify-report status: fail
- [ ] Case 03-r1-fail: R1 拦下 — 用户确认 qa-gate-report R1 fail
- [ ] Case 04-r2-fail: R2 拦下 — 用户确认 qa-gate-report R2 fail
- [ ] Case 05-r3-fail: R3 拦下 — 用户确认 qa-gate-report R3 fail
```

**在收到用户全部 5 项确认前，本 task 不能进 ✅ 状态**。在 changelog.md 里也写明"待用户 e2e 验收"。

- [ ] **Step 7: Commit**

```bash
git add skills/x-cr/SKILL.md README.md README_zh.md \
        .claude-plugin/ .codex-plugin/ .agents/ \
        dev-pipeline/tasks/_e2e-smoke/
git commit -m "feat(x-cr): 改为重定向 stub + 更新全局链路文档 + e2e smoke"
```

- [ ] **Step 8: 把 qa-gate-pipeline 任务自身关闭**

更新 `dev-pipeline/tasks/qa-gate-pipeline/dev-checklist.md`，把全部任务标 ✅。
写 `dev-pipeline/tasks/qa-gate-pipeline/changelog.md` 总结落地内容。

```bash
git add dev-pipeline/tasks/qa-gate-pipeline/
git commit -m "chore(qa-gate-pipeline): 任务关闭，pipeline 改造完成"
```

---

## Self-Review (内部 checklist，非用户 review)

### Spec coverage
- [x] T1 → 设计文档 4.1 节 dev-report schema
- [x] T2 → 4.2 节 x-verify
- [x] T3 → 4.3 节 x-qua-gate 框架
- [x] T4-T6 → 4.3 节 R1/R2/R3 reviewer
- [x] T7 → 4.4 节 x-fix 回流改造
- [x] T8 → 4.5 节 x-audit-perf
- [x] T9 → 4.6 节 x-audit-style
- [x] T10 → 第 6 节兼容性迁移 + 第 9 节验收标准

### 已知盲点
- "dev-report 漏报命令"无法靠 verify 拦下（设计文档第 9 节已显式列出，未来可加 cross-check）。

### Type consistency
- 所有 skill 名前后一致：x-verify / x-qua-gate / x-audit-perf / x-audit-style
- fix-counter 路径一致：`reports/.fix-counter`
- 报告路径前后一致：reports/{verify,qa-gate,fix,audit}/*-YYYYMMDD-HHmmss.md
- reviewer 编号一致：R1 spec-conformance / R2 boundary-coverage / R3 test-integrity

### 风险点
- T7 的 x-fix 改造可能与现有 bug-fix-mode / cr-fix-mode 冲突——执行 T7 时必须先读 references/ 下两个旧 mode 文件，确保新增的 qa-gate-fix-mode 不破坏老路径。
- T10 的 manifest 更新依赖具体 plugin schema，可能需要在执行时根据实际 schema 调整。
