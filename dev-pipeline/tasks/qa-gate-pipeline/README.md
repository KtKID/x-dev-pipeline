# qa-gate-pipeline · 开发-质检-优化自动化门禁链路

**创建日期**: 2026-04-27
**类型**: 系统改造（pipeline 架构升级）
**影响范围**: skills/ 下 7 个 skill，dev-pipeline/tasks 任务流程，reports 产出格式

---

## 1. 背景与动机

现状：`x-dev-pipeline` 已实现 `x-dev → x-cr → x-fix` 的自动闭环，但有以下不足：

1. **x-cr 一锅烩**：把"代码能不能跑"（事实）和"代码质量好不好"（评审）混在同一个 skill 里。代码跑不起来时再做 P2/P3 评审是浪费；评审 fail 时和验证 fail 时修复路径性质不同，混在一起难分轻重。
2. **审查是一次性、单线程**：x-cr 一次输出一份报告。spec 错了和测试镜像化之类的根本问题被 P2/P3 噪音淹没。
3. **不信任自我报告"半到位"**：x-cr 现在确实独立判断，但验证命令的"曾经跑过"靠 x-dev 自报，没有外部仲裁。
4. **性能 / 规范类问题与功能问题搅在一起**：单个任务级别揪 N²、揪命名属于过度工程；这些是全局视角才有意义的事，不该卡每个任务。

## 2. 设计目标

把"开发→质检→优化"重新分层：

- **开发**：x-dev / x-qdev 不变骨架，但**输出格式约束**——必须自报"我跑了哪些验证命令"。
- **质检（强门禁）**：拆成两层 gate
  - `x-verify` → 复跑 dev 自报命令，做**事实验证**（不主观判断）。
  - `x-qua-gate` → 3 个 reviewer 子 agent **串行**评审，做**质量评审**。**取代老 x-cr**。
- **优化（独立巡检）**：性能、规范从主流程剥离，变成独立 skill `x-audit-perf` / `x-audit-style`，手动或周期触发。

## 3. 总览架构

```
┌──────────────────────────────────┐
│ x-dev / x-qdev                   │  开发节点（修改：输出 dev-report.md）
│  · 实现代码                       │
│  · 跑验证命令（build/test/lint）  │
│  · 输出 dev-report.md：           │
│    "我跑了 X/Y/Z 命令，都过了"    │
└──────────┬───────────────────────┘
           ↓
┌──────────────────────────────────┐
│ x-verify  (新 skill)             │  Gate ① 事实验证
│  · 读 dev-report 里的命令清单    │  · 不信任自我报告
│  · 复跑 → 看 exit code           │  · 主流程使用主 agent，无需 opus 子 agent
│  · 任一不一致 → 回 x-fix          │
└──────────┬───────────────────────┘
           ↓ 通过
┌──────────────────────────────────┐
│ x-qua-gate (新 skill，取代 x-cr) │  Gate ② 质量评审
│                                  │
│  R1 spec-conformance  [P0]       │  ← opus 子 agent
│   ├─ fail → x-fix → 回 R1        │
│   └─ pass ↓                      │
│                                  │
│  R2 boundary-coverage [P0/P1]    │  ← opus 子 agent
│   ├─ fail → x-fix → 回 R2        │
│   └─ pass ↓                      │
│                                  │
│  R3 test-integrity    [P0]       │  ← opus 子 agent
│   ├─ fail → x-fix → 回 R3        │
│   └─ pass ✅                     │
└──────────┬───────────────────────┘
           ↓
       ✅ 任务完成

═══════════════════════════════════
【独立巡检 skill — 不在主流程】
  x-audit-perf   性能巡检（手动 / 大里程碑触发）
  x-audit-style  规范巡检（手动 / 周期触发）
═══════════════════════════════════
```

## 4. 组件详细设计

### 4.1 x-dev / x-qdev — 输出格式约束

**改动**：在 changelog.md 之外，每次任务完成必须额外输出 `dev-report.md`，作为 x-verify 的输入。

**dev-report.md 必填字段**：

```markdown
# Dev Report — <task-name> — YYYYMMDD-HHmmss

## 改动文件清单
- src/foo.ts
- tests/foo.test.ts

## 验证命令清单（必填，x-verify 会复跑）
| 命令 | 预期 exit | 关键输出片段 |
|------|----------|-------------|
| `npm run build` | 0 | `Compiled successfully` |
| `npm test` | 0 | `Tests: 42 passed` |
| `npm run lint` | 0 | `0 errors` |

## 自检结论
本人（x-dev）已运行上述全部命令并确认通过。
```

**纪律**：
- 至少必须包含一条"测试"类命令；如项目无测试框架，必须显式声明 `no-test-framework: true` + 理由（让 verify 跳过）。
- 命令必须可在项目根目录直接运行，不允许依赖 dev 临时设置的环境变量。

### 4.2 x-verify — Gate ① 事实验证（新 skill）

**职责**：唯一一件事——读 dev-report 的命令清单，复跑，看 exit code 和关键输出。

**纪律**（写入 SKILL.md 强制条款）：
1. **不主观判断代码质量**——只看命令是否 exit 0、关键输出片段是否出现。
2. **不裁剪命令**——dev 报告了 5 条命令必须跑 5 条，不许省略。
3. **不信任 dev 的"自检结论"**——必须自己跑。
4. **任一命令不一致** → 生成 `reports/verify/verify-report-*.md`，调 x-fix（修复模式：fix verification failure），fix-attempts +1。
5. **6 次上限共享**：与 x-qua-gate 共用 fix-attempts 计数；超 6 次停下问用户。

**输出**：`reports/verify/verify-report-YYYYMMDD-HHmmss.md`，记录每条命令的实际 exit + 输出。

**实现**：主 agent 直接执行；不需要 opus 子 agent（无判断成分）。

### 4.3 x-qua-gate — Gate ② 质量评审（新 skill，取代 x-cr）

**核心机制**：3 个 reviewer **串行**跑（不是并行），每个 reviewer 是**独立 Task 子 agent，model 强制 opus**。

#### 为什么串行不是并行
- R1 (spec) fail → 功能本身错了 → R2/R3 在错代码上做审查无意义
- R2 (boundary) fail → 边界漏了 → R3 测试在漏边界的代码上验证也无意义
- 每个上游 reviewer 是下游的"地基"

#### Reviewer 设计

##### R1. spec-conformance（功能符合性）

**触发**：x-verify 通过后立即跑。

**输入给子 agent**：
- task 的 README.md（需求）
- plan.md（计划）
- dev-checklist.md（任务清单当前状态）
- changelog.md（dev 自报改动）
- 实际 git diff

**子 agent 检查清单**：
1. 需求文档里写的每条要求，代码里是否都实现了？逐条对照。
2. 计划里 dev-checklist 标 ✅ 的任务，git diff 里能找到对应改动吗？
3. 有没有"实现了但需求没要求"的多余功能？
4. 有没有"需求里有但 dev-checklist 漏了"的偏离？
5. 改动是否影响了任务范围之外的代码（scope creep）？

**输出**：mini-report，列出 P0 级 spec 不符问题。

**fail 处理**：调 x-fix（CR 报告模式），fix 完回 R1 重审。

##### R2. boundary-coverage（边界完整性）

**前置**：R1 通过。

**输入给子 agent**：R1 通过后的代码 diff + task README。

**子 agent 检查清单**：
1. 输入边界：null / 空字符串 / 超长 / 0 / 负数 / Unicode / 特殊字符
2. 状态边界：未初始化 / 部分初始化 / 已销毁 / 并发竞争
3. 错误路径：异常分支是否有处理？是否吞了异常？
4. 边界回归：如果改动了已有函数，原边界处理是否被破坏？

**输出**：mini-report，按 P0/P1 列出漏掉的 case。

**fail 处理**：调 x-fix，fix 完回 R2 重审。

##### R3. test-integrity（测试真实性）⭐ 反 anti-pattern 核心

**前置**：R2 通过。

**输入给子 agent**：测试文件 diff + 被测代码 diff。

**子 agent 检查清单**（反"测试镜像化"为核心目的）：
1. **import 检查**：测试文件是否真的 import 了被测代码？还是只在测试里 reimplement 了一遍？
2. **顶层 API 调用**：测试是否调用被测代码的入口函数 / 顶层 API？还是把被测代码的步骤复制到测试里再断言？
3. **断言契约性**：断言值是写死的期望（`assert total == 30`）还是又用业务函数算了一遍（`assert total == price1 + price2`）？后者代码逻辑改了测试不会挂。
4. **mock 边界**：被 mock 的对象是不是被测代码自己（自我 mock）？mock 是否过度——把核心业务都 mock 掉了？
5. **改动覆盖**：本次 dev 改了哪些函数？测试是否真触发了它们？（用 grep 验证测试文件 import + 调用链）

**反模式举例**（写入 SKILL.md 作为参考）：

```python
# ❌ 测试镜像化
def test_workflow():
    step1 = do_thing_a()                    # 自己复制流程
    step2 = do_thing_b(step1)
    assert step2 == "expected"              # 真正的 workflow 改了顺序，测试不挂

# ✅ 真测代码
def test_workflow():
    result = workflow.execute()             # 调入口
    assert result == "expected"             # 输出契约
```

**输出**：mini-report，按 P0 列出测试不真实问题。

**fail 处理**：调 x-fix（fix 测试代码，不动业务代码），fix 完回 R3 重审。

#### x-qua-gate 输出聚合

3 个 mini-report 聚合到一份 `reports/qa-gate/qa-gate-report-YYYYMMDD-HHmmss.md`：

```markdown
# QA Gate Report — <task> — YYYYMMDD-HHmmss

## 总结
- R1 spec-conformance:   ✅ pass / ❌ fail (round 2)
- R2 boundary-coverage:  ✅ pass / ⏸ pending (R1 未过)
- R3 test-integrity:     ⏸ pending

## R1 详情
[opus subagent mini-report]

## R2 详情
[pending / mini-report]

## R3 详情
[pending / mini-report]

## fix 历史
- 2026-04-27 14:23 R1 fail → x-fix attempt 1 → R1 pass
- 2026-04-27 14:35 R2 fail → x-fix attempt 2 → R2 pass
```

### 4.4 x-fix — 失败回流逻辑（方案 X）

**改动**：x-fix 接收来自 verify / R1 / R2 / R3 的 fail 报告，按"只回当前节点"原则修。

**新规则**：
1. 修复完成后**只回到失败节点**重审，不从头走（除非 fix 涉及核心业务逻辑大改，由 x-fix 自己判断后选择回 R1）。
2. **fix-attempts 计数 task 内共享**：每个 task 有独立计数器（`<task>/reports/.fix-counter`），**当前 task** 内 verify + R1 + R2 + R3 共用 6 次上限。每次 fail 触发 x-fix 都 +1。不同 task 之间不串。
3. 超 6 次上限 → 停下生成 `fix-blocked-report.md` 给用户决策（继续 / 修改需求 / 放弃）。
4. **fix 报告路径按节点分类**：
   - verify fail → `reports/fix/fix-verify-*.md`
   - R1 fail → `reports/fix/fix-r1-spec-*.md`
   - R2 fail → `reports/fix/fix-r2-boundary-*.md`
   - R3 fail → `reports/fix/fix-r3-test-*.md`

**判断"是否要回 R1"的明确规则**（写入 x-fix SKILL.md，按优先级从上到下匹配，命中即停）：
1. fix 涉及函数签名变化 / 新增/删除公开 API → **必须回 R1**
2. fix 改动了被测代码的核心业务逻辑文件（非测试 / 非配置 / 非注释）→ **必须回 R1**
3. fix 只改测试文件 / 配置 / 文档 / 注释 → **回当前失败节点**
4. 其他不确定情况 → **保守回 R1**

### 4.5 x-audit-perf（新 skill，独立巡检）

**定位**：不在主流程，手动或周期触发。

**职责**：全项目视角的性能审查——N²、不必要循环、大对象拷贝、同步阻塞、数据库 N+1、缓存失效。

**输出**：`reports/audit/audit-perf-YYYYMMDD.md`。

**子 agent**：opus，单独 Task。

**触发约定**：用户主动调用 `x-audit-perf` 或在大里程碑后建议触发，**不进 x-dev 闭环**。

### 4.6 x-audit-style（新 skill，独立巡检）

**定位**：不在主流程，手动或周期触发。

**职责**：全项目视角的代码规范——命名一致性、复用机会、magic number、函数长度、文件大小、注释合理性、死代码。

**输出**：`reports/audit/audit-style-YYYYMMDD.md`。

**子 agent**：opus，单独 Task。

## 5. 失败回流总流程图

```
任意节点 fail
   ↓
[fix-attempts < 6?]
   ├─ no → 停下，生成 fix-blocked-report.md，问用户
   └─ yes ↓
       fix-attempts += 1（先 +1，避免崩溃后死循环）
            ↓
        x-fix 修复
            ↓
       按 4.4 节规则判定回流目标：
        ├─ 改动只涉及测试/配置/注释 → 回当前节点重审
        └─ 改动涉及业务逻辑/签名变化/不确定 → 回 R1 重审
```

## 6. 兼容性与迁移

### 老 x-cr 处理
- `skills/x-cr/SKILL.md` 改为**重定向 stub**：内容只剩一句话 + 跳转到 x-qua-gate。
- 老的 `reports/cr/cr-report-*.md` 路径**保留**（不重命名历史报告），新报告写到 `reports/qa-gate/`。
- 文档（README_zh.md / README.md）更新所有指向 x-cr 的链接到 x-qua-gate。

### 任务目录扩展
新增 `reports/` 子目录结构：
```
reports/
├── verify/verify-report-*.md          ← 新
├── qa-gate/qa-gate-report-*.md        ← 新（取代 cr/）
├── cr/cr-report-*.md                  ← 保留旧报告，不再写新的
├── fix/fix-verify-*.md                ← 新
├── fix/fix-r1-spec-*.md               ← 新
├── fix/fix-r2-boundary-*.md           ← 新
├── fix/fix-r3-test-*.md               ← 新
├── fix/fix-report-*.md                ← 兼容旧路径（直接 bug fix 模式仍用）
├── fix/fix-note-*.md                  ← 兼容旧路径
└── audit/audit-{perf,style}-*.md      ← 新
```

### x-qdev 改动
x-qdev 也走完整 verify → qua-gate 流程（不能跳过）；只是它的 dev-report 命令清单可能短（小功能）。

### x-dev 并行 subagent
现有 x-dev 的"多无依赖任务并行子 agent"机制保留，每个并行子 agent 完成后各自输出 dev-report，verify 和 qua-gate 串行处理它们。

## 7. 不在本次范围内的事

- 不引入 superpowers 风格的 TDD 红绿强制（保持渐进，不破坏现有 x-qdev 体感）。
- 不引入 systematic-debugging 的 4-phase 调试 skill（x-fix 内部启发式已够用）。
- 不重写 x-spec / x-req / x-plan（前置阶段不动）。
- 不实现 hooks 自动触发（保持 skill chaining 由 AI 主导，不引 settings.json hooks）。
- 不做 IDE 集成（VS Code / JetBrains 插件超出范围）。

## 8. 接下来怎么做

本设计文档（README.md）通过 user review 后：
1. 进入 `writing-plans` skill，生成 `plan.md` 和 `dev-checklist.md`。
2. dev-checklist 拆分为可独立交付的小任务：
   - T1. dev-report.md schema 与 x-dev 输出改造
   - T2. x-verify skill 实现
   - T3. x-qua-gate skill 框架（聚合层）
   - T4. R1 spec-conformance reviewer
   - T5. R2 boundary-coverage reviewer
   - T6. R3 test-integrity reviewer（含反模式规则集）
   - T7. x-fix 失败回流逻辑（按节点分类 fix 报告）
   - T8. x-audit-perf skill
   - T9. x-audit-style skill
   - T10. 老 x-cr 重定向 stub + 文档更新
3. 每个 task 自己也走完整 verify + qua-gate 流程（吃自己的狗粮）。

## 9. 验收标准

本次改造完成的判定：
- [ ] 7 个新/改 skill 全部落地（x-dev/x-qdev/x-verify/x-qua-gate/x-fix/x-audit-perf/x-audit-style）
- [ ] 用一个真实小功能跑通 dev → verify → qua-gate → ✅ 闭环
- [ ] 故意引入 spec 偏离，验证 R1 能拦下
- [ ] 故意写"测试镜像化"代码，验证 R3 能拦下
- [ ] 故意把 dev-report 里某条命令的预期 exit 写错，验证 x-verify 复跑后能拦下不一致
- [ ] 触发 6 次 fix 上限，验证停下问用户

**已知盲点（不在本次解决）**：dev-report 完全漏报某条命令（dev 没跑某个验证），verify 没法察觉——因为 verify 只复跑 dev 自报的命令。这是"自报清单"机制的固有限制。后续可考虑加白名单（package.json 推断出"应该跑的命令"作为最小集合 cross-check），但本次不做。
- [ ] 老 x-cr 调用能正确重定向到 x-qua-gate
