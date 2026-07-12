---
name: x-qa-gate
description: |
  Gate ② 流水线质量门禁 skill。按风险路由评审：默认线 dispatch 一个综合 reviewer（RC），一轮列全 spec 契约、边界失败路径、测试真实性三类问题；高危改动（鉴权/不可逆写入/公开 API/并发等）走高危线，串行 dispatch R1 契约/spec 正确性 → R2 失败路径/边界正确性 → R3 测试真实性。评审 fail 输出完整发现清单交 x-fix 一次批量修复，修复后增量复审（尽量同一个 reviewer）；全部通过任务才算完成，并在对话中输出门禁回执。
  自动触发：x-verify 通过后立即触发。
  手动触发：用户要求"质量门禁"、"qa-gate"、"R1/R2/R3 gate"、"跑门禁"。
  手动软件正确性调查、用户已知问题排查、模块/PR correctness review 优先使用 x-cr；流水线 gate 使用 x-qa-gate。
---

# x-qa-gate · Gate ② 质量评审

x-qa-gate 是质量门禁链路的第二层 gate。它前面的 x-verify 已确认"代码能跑"，本 skill 回答"做得对吗"，覆盖三个正确性维度：

1. **spec 契约**：契约和 spec 是否被正确实现？（契约优先 / scope）
2. **边界失败路径**：失败路径和边界输入下是否仍然正确？（失败优先 / 对抗性检验）
3. **测试真实性**：测试是否能从反方向击穿假实现？（反镜像化 / 反自证正确）

三个维度不变，执行结构是**一轮列全 → 批量修 → 增量复审**：reviewer 一次穷尽列出全部发现，x-fix 一次修完，复审只看增量。禁止逐问题打回循环。

## 质量原则落点

- **契约优先**：先抽取公开入口契约（输入、输出、错误、空值、状态副作用、幂等性、并发/线程安全）再对照实现。
- **失败优先**：从失败路径开始审查——非法输入、异常状态、工具超时、权限拒绝、部分失败、环境不一致、外部返回非法数据。
- **对抗性检验**：主动寻找能击穿当前实现或证据的输入、状态、依赖失败、权限、缓存、并发和测试过拟合场景。

## 严重度定义（唯一真源）

| 级别 | 定义 | 处置 |
|------|------|------|
| **P0** | spec/契约违背、安全问题、数据错误、e2e/验收失败 | 必修，阻塞 |
| **P1** | 边界缺陷、失败路径缺失、测试造假、scope creep | 默认修；可带理由豁免，未处置的 P1 阻塞 |
| **P2** | 建议级改进 | 登记不修，不阻塞 |

reviewer 判定：**fail** ⟺ 存在 P0 或未处置的 P1；**pass** ⟺ P0 为空且每条 P1 已修复/已豁免/已升级。所有 reviewer 手册引用本定义，不得另立分级。

## 输入

- 当前 task 目录下的 `dev-report.md`（命令清单 + 改动文件清单 + 风险等级声明）
- 当前 task 目录下的任务文档：完整任务使用 `README.md` / `plan.md` / `dev-checklist.md` / `changelog.md`；qdev 显式完整门禁使用含原始请求和内嵌清单的 `README.md` / `changelog.md`
- 最新 verify report
- 当前 git diff（与 task 起点对比）

### 事实源优先级

reviewer 按以下顺序处理冲突：

1. 用户原始请求、用户确认过的 spec 和既有公开契约。
2. 真实调用方、数据/schema 约束和改动前已有测试契约。
3. task README、plan、dev-checklist 中的派生设计和执行拆分。
4. changelog、dev-report 和 agent 自检结论。

派生文档扩展了用户原始请求时，reviewer 把扩展项标为假设或 scope 风险，并回到更高优先级事实源判断。

## 风险路由

进入 Gate ② 先定路线。x-dev 在 `dev-report.md` 声明 `risk: default | high`；未声明时由主 agent 按同一判据现场判定并记入 qa-gate 报告。

| 路线 | 触发条件 | 评审形态 |
|------|----------|----------|
| **高危线** | 鉴权/权限/加密；不可逆数据写入/迁移；公开 API/协议/schema 变更；并发/状态机/缓存一致性；用户显式要求三段评审 | R1 → R2 → R3 串行三个分维度 reviewer |
| **默认线** | 其余全部 | 一个综合 reviewer RC（手册 `references/rc-unified.md`） |

两条路线共用同一套执行结构：一轮列全、批量修、增量复审、按轮计数。

## 流程

**默认线：**

```
RC 综合评审（一轮列全）─ pass ─→ ✅
      │ fail（发现清单 F1..Fn）
      ↓
x-fix 批量修（一次修完本轮全部，counter +1）
      ↓
增量复审（尽量同一个 reviewer）─ pass → ✅
      │ fail → 熔断判定（见「增量复审」）
```

**高危线：**

```
R1 ─ pass → R2 ─ pass → R3 ─ pass → ✅
 └ fail（F1..Fn）→ x-fix 批量修 → 增量复审当前段 → pass 后进下一段
```

高危线段间不回跳：R2 fail 修完只增量复审 R2（含定点契约检查），不重跑 R1。

## 一轮列全（reviewer 硬约束）

1. **先穷尽后判定**：审完全部改动文件和全部检查维度才允许写报告，禁止发现一个足以 fail 的问题就交卷。
2. **三件套输出**：mini-report 必须含覆盖声明（改动文件已审 N/M + 各维度结论）、发现清单（F1..Fn 编号 + 严重度 + 位置 + 失败场景 + 建议）、穷尽声明（"除上表外无其他 P0/P1"）。
3. **漏检追责**：复审轮出现初审就该看到的同文件同维度新问题 → 主 agent 在回执标 `漏检 ×N`，作为 reviewer 质量信号。

## 增量复审

fix 完成后**不做全量重审**，不使用"回 R1"回流：

- **尽量由同一个 reviewer 承接复审**，具体机制由执行时的 LLM 按当前环境能力自行处理；无法续接时新 dispatch，输入 = 上轮 mini-report + x-fix 处置表 + fix 增量 diff（`git diff <fix 前基点>..HEAD`）。mini-report 的发现清单与覆盖声明就是为重建上下文设计的压缩快照。
- **复审范围** = 逐条验证 F# 是否修好 + fix diff 触碰文件是否引入新问题。
- **三条熔断**（防增量遮蔽大问题）：
  1. fix 改动超出上轮发现涉及的文件集 → 复审范围扩大到新触碰文件；
  2. fix 改了公开 API 签名 → 对该 API 定点重做契约对照（不全量重跑 R1）；
  3. 连续 2 轮复审仍出新 P0 → 升级一次全量重审，或停下问用户。

## 硬约束

1. **高危线必须串行**：R1 → R2 → R3 顺序固定，不要并行；默认线只派一个 RC。
2. **每个 reviewer 必须是独立子 agent**：用 Task 工具 dispatch，传 `subagent_type`。
3. **reviewer 不要修改代码**：reviewer 只输出 mini-report；修改由 x-fix 负责。
4. **聚合保持单一来源**：检查清单由 `references/rc-unified.md`、`r1-*.md`、`r2-*.md`、`r3-*.md` 定义；严重度分级由本文件「严重度定义」定义；不要在别处重复。

## Reviewer context 预算

reviewer 子 agent 的初始 prompt 采用预算制：

- 目标上限：10,000 estimated tokens。
- 不要把完整 diff、完整源码、完整测试文件、大段日志放入初始 prompt。
- 大材料保留原路径，或写入 `reports/qa-gate/evidence/<reviewer>-<timestamp>/`；初始 prompt 只传 manifest、路径、hash、行号范围、摘要。

estimated token 采用保守估算：Markdown / diff / 代码混合文本按 `4 chars ~= 1 token`，中文较多时按 `2.5 chars ~= 1 token`；任一估算超限时主 agent 必须压缩为 manifest。上述预算是 prompt 协议，实际硬限制由当前执行 harness 决定。

## Reviewer dispatch 模板（写给主 agent 用）

```
Agent({
  description: "<RC/R1/R2/R3> review round <N>",
  subagent_type: "general-purpose",
  prompt: <reviewer checklist + task manifest + required paths + diff commands + evidence path + context completeness gate + 一轮列全约束 + 输出格式>
})
```

prompt 必须包含：

1. 完整的 reviewer 检查清单：默认线用 `references/rc-unified.md`，高危线用对应 `references/r{N}-*.md`。
2. 当前 task root。
3. 当前路线必读文件路径列表。完整任务读取 `README.md` / `plan.md` / `dev-checklist.md` / `changelog.md` / `dev-report.md` / 最新 verify report；qdev 显式完整门禁把独立 `plan.md` / `dev-checklist.md` 标为 `N/A`，使用 README 内嵌 DoD/清单。
4. diff 获取命令：`git diff --stat`、`git diff --name-only`、按需 `git diff -- <file>`。
5. evidence 输出路径：`reports/qa-gate/evidence/<reviewer>-<timestamp>/`。
6. Context Completeness 检查要求。
7. 输出格式约束（mini-report markdown，含覆盖声明 / 发现清单 / 穷尽声明）。

复审轮追加：上轮 mini-report 路径、x-fix 处置表路径、fix 增量 diff 命令。不要在 prompt 中内联完整代码；子 agent 通过只读工具按需读取。

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
- 当前任务路线要求的文件缺失 → `incomplete`；路线未产出的文件标记 `N/A` 并说明替代事实源。
- diff 文件列表缺失 → `incomplete`。
- reviewer 无法确认关键实现文件内容 → `incomplete`。
- 引用证据少于 3 条且结论为 pass → 主 agent 视为无效报告，重新 dispatch。
- reviewer 报告缺少 `Context Completeness`、覆盖声明或穷尽声明 → 主 agent 视为无效报告，重新 dispatch。

## Context 文件策略

`reports/qa-gate/context/<reviewer>-context-*.md` 只保存轻量上下文：reviewer 名称和时间戳、task root、checklist 路径、required docs 路径、changed file list、`git diff --stat`、verify report 摘要、evidence bundle 路径、context budget 估算。

context 文件不要保存完整 git diff、完整源码文件、完整测试文件、重复 task 文档全文或大段日志输出。

## 失败交接

reviewer fail 后，主 agent 把**完整发现清单**（不是单个问题）交给 x-fix（mode: gate-fix），由 x-fix 一次批量修复并产出逐条处置表，然后回到本 skill 做增量复审。x-fix 不再自行判定回流目标。详见 `skills/x-fix/SKILL.md`。

## 3 轮上限（与 x-verify 共享 fix-counter）

- `reports/.fix-counter` 语义：**批量修轮数**（一轮 = 一份发现清单的整体修复），不是问题条数。
- 任何 reviewer fail 触发 x-fix 前先检查 counter：counter < 3 → 触发 x-fix（由 x-fix 进入修复前 +1）；counter >= 3 → 停下生成 `reports/fix-blocked-report.md`，列出积压问题等用户决策（继续 / 修改需求 / 放弃）。
- **重置时机**：Gate ② 最终 pass（默认线 RC pass / 高危线 R3 pass）后，由本 skill `echo 0 > reports/.fix-counter`。

## 门禁回执（强制对话输出）

每轮评审结束和任务通关时，主 agent 必须在**对话中**输出回执；报告文件只做存档。通关时输出累计台账：

```
🛡️ 门禁回执 · <task> · Gate① ✅ · Gate② ✅（N 轮 · 默认线/高危线）
累计发现：P0 ×a · P1 ×b · P2 ×c · 漏检 ×d
├─ F1 P0 <一句话问题> ← <RC-Q3/R2 等维度> → ✅ 已修
├─ F2 P1 <一句话问题> ← <维度> → ➖ 豁免（理由）
└─ F3 P2 <一句话问题> ← <维度> → 📝 登记
修复轮次 N/3 · e2e 反例新增 M 条 · 存档：reports/qa-gate/qa-gate-report-*.md
```

规则：**零发现也要报**（`P0 ×0 · P1 ×0` 证明审过且干净）；每条发现必须标注拦截来源维度——这些数据攒起来就是各层拦截率的实测依据。

## 报告输出

主 agent 把各 reviewer 的 mini-report 和逐轮处置聚合到 `reports/qa-gate/qa-gate-report-YYYYMMDD-HHmmss.md`，模板见 `templates/qa-gate-report-template.md`。

## 下游

- 全部 pass → 任务完成 → fix-counter 重置为 0 → 写 changelog → 输出通关回执
- 任一 fail → x-fix（mode: gate-fix，带完整发现清单）→ 增量复审
