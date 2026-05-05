---
name: x-dev
description: |
  开发任务执行 skill。基于现有功能计划目录执行开发任务，
  读取 dev-pipeline/tasks/<功能名称>/README.md、dev-checklist.md、changelog.md，
  按开发清单中的未完成任务进行实现、修复、测试，并回写任务状态与变更记录。
  当开发清单中存在多个无依赖关系的待处理任务时，自动创建子 agent 并行开发以提升效率。
  触发方式：用户输入 "x-dev <功能名称>" 或提供现有功能目录路径。
---

# x-dev 开发任务执行

## 核心定位

x-dev 是执行型 skill，只负责基于现有计划目录执行开发任务。

x-dev 负责：
1. 读取现有功能目录
2. 读取 README.md（需求 + 技术设计 + DoD）、dev-checklist.md、changelog.md
3. 根据开发清单执行开发、修复和测试
4. 更新开发清单中的任务状态
5. 更新changelog.md
6. 在必要时向用户汇报进度、风险和阻塞项

x-dev 不负责：
- 创建 task 目录和文件（README.md / dev-checklist.md 由 x-req 负责）
- 自动提交 git，除非用户明确要求

---

## 输入格式

```text
x-dev <功能名称>
````

或

```text
x-dev <功能目录路径>
```

输入可以是：

* 功能名称，例如：`x-dev 设备 Token 认证`
* 现有目录路径，例如：`x-dev dev-pipeline/tasks/设备 Token 认证`

---

## 目录要求

x-dev 默认基于以下目录结构工作：

```text
dev-pipeline/tasks/<task>/
├── README.md              # 需求 + 技术设计 + DoD（x-req 负责）
├── dev-checklist.md       # 开发清单（x-req 负责）
├── diagram.html           # 模块/组件图（x-req 负责）
├── changelog.md           # 关键变更（x-dev 负责）
├── dev-report.md          # 完成报告（x-dev 负责，gate 输入）
├── plan.md                # [可选/历史] 旧 task 可能有
└── reports/               # gate 产出目录（全部在 task 目录下）
    ├── .fix-counter        # fix 次数计数器（x-verify 创建，x-fix 递增，x-qa-gate 重置）
    ├── verify/             # Gate ① 报告
    │   └── verify-report-YYYYMMDD-HHmmss.md
    ├── qa-gate/            # Gate ② 报告
    │   └── qa-gate-report-YYYYMMDD-HHmmss.md
    ├── fix/                # 修复报告（按触发节点分类）
    │   ├── fix-verify-*.md     # x-verify fail 触发
    │   ├── fix-r1-spec-*.md    # R1 fail 触发
    │   ├── fix-r2-boundary-*.md # R2 fail 触发
    │   ├── fix-r3-test-*.md    # R3 fail 触发
    │   ├── fix-report-*.md     # 直接 bug fix 模式
    │   └── fix-note-*.md       # 单点修补
    └── audit/              # 独立巡检（手动触发）
        ├── audit-perf-*.md
        └── audit-style-*.md
```

> **所有 `reports/` 路径都是相对 task 目录**（即 `dev-pipeline/tasks/<task>/reports/`），不是项目根目录。x-verify / x-qa-gate / x-fix / x-audit 写报告时必须确认在 task 目录下操作。

处理规则：

1. 优先按用户提供的目录路径读取
2. 如果用户提供的是功能名称，则查找 `dev-pipeline/tasks/<功能名称>/`
3. 必须确认以下文件存在：

   * `README.md`（含需求 + 技术设计 + DoD）
   * `dev-checklist.md`
   * `changelog.md`（不存在则创建空文件）
4. `plan.md` 不再必需——新 task 不产出；旧 task 如有则仍可读取
5. `reports/` 目录在首次 gate 执行时自动创建，不需要预创建
6. 如果目录或关键文件缺失，停止执行，提示用户先通过 x-req 补齐

---

## 执行流程

1. 解析输入，定位功能目录
2. 读取 `README.md`，理解核心目标、技术设计、DoD
3. **如果 README.md "涉及模块" 段引用了 docs/ 模块文档 → 跟读该模块文档**，获取接口/数据结构/架构上下文。同时检查：该模块在 `architecture.html` 的颜色是否为当前阶段（蓝）？如果不一致（还是橙/灰）→ 先更新为蓝再开发
4. 如果存在 `plan.md`（历史 task）→ 读取了解开发策略（新 task 无此文件则跳过）
5. 读取 `dev-checklist.md`，识别任务编号、任务标题、状态、备注
6. 读取 `changelog.md`，了解已有决策、历史修改和已知问题
7. 选择状态不是”已完成”的任务作为执行对象，按 P0→P1→P2 顺序执行
8. **并行判断**：同一优先级内，将无依赖的任务分组为可并行批次（见”并行开发”章节）
9. 可并行任务通过子 agent 同时开发；有依赖的任务串行执行
10. 根据执行结果更新开发清单状态
11. 在 `changelog.md` 中记录关键修改、失败原因、修复动作和完成情况
12. 向用户汇报当前完成情况、未完成项和阻塞项

---

## 并行开发（默认优先）

> **核心原则：能并行就并行，不要串行等待。** 并行是默认行为，串行是例外——只有明确存在依赖关系时才串行。

同一优先级内有 2+ 个无依赖的待处理任务时，**必须**用 Agent 工具派 opus 子 agent 并行开发。不允许"为了简单"而串行执行可并行任务。

**依赖判断**（满足任一 → 串行；全不满足 → 并行）：
- 备注列标注"依赖 #N"
- README.md "涉及模块"声明模块间有依赖
- 两任务改同一文件同一区域（写冲突风险）

**子 agent dispatch 模板**：

```
Agent({
  description: "x-dev #N <任务标题>",
  subagent_type: "general-purpose",
  model: "opus",
  prompt: <功能目录路径 + 任务编号/描述 + README 技术设计段 + 涉及模块文档（如有）>
})
```

**硬规则**：
- **必须 `model: "opus"`**——不允许用默认模型或 haiku
- **必须同一条消息发出所有 Agent 调用**（真正并行，不是伪并行）
- 每个子 agent prompt **必须自包含**：包含 README 技术设计段 + DoD 相关条目 + 涉及模块的接口定义
- 子 agent **只改自己任务的代码，不更新 dev-checklist.md 和 changelog.md**（主流程统一更新，避免写冲突）
- 某个子 agent 失败不阻塞其他任务，失败任务回到待处理队列

**结果收集**：所有子 agent 返回后，主流程统一更新状态和 changelog，再逐个进入 x-verify → x-qa-gate 流程。

**质检标记 🔍**：dev-checklist 质检列标记 🔍 的任务，子 agent 完成后必须立即创建质检 agent 审查，审查通过才继续。未标记的任务走常规流程。

**不并行的例外**（仅以下情况）：
- 仅 1 个待处理任务
- 所有任务形成依赖链（#1→#2→#3）
- 用户明确指定只处理某项任务（如"x-dev #3"）

---

## 执行规则与状态规范

详细的状态定义、清单解析规则、更新步骤（含示例）、变更记录格式见 `references/execution-rules.md`。

核心要点：
- 状态流转：`⏳ → ▶️ → 🟡 → 🟢`（x-dev 最多到 🟢，✅ 由 review 确认）
- 每完成一个阶段**立即**更新 dev-checklist.md + changelog.md
- 严格按优先级执行（P0 > P1 > P2）

---

## README.md 使用规则

执行前必须先阅读 `README.md`，重点关注：

* **核心目标**：这个 task 要做什么
* **涉及模块**：改动哪些模块（有 ref 链接则跟读 docs/ 模块文档）
* **技术设计**：数据结构、关键链路、技术选型
* **DoD**：怎么算完成——每个验收条件都要满足

执行过程中不得偏离 README.md 定义的目标和 DoD。
如果发现任务与 DoD 冲突或超出"涉及模块"范围，应先提示用户，而不是擅自扩展。

---

## 输出要求

每次执行后，输出内容应尽量包含：

1. 当前处理的任务编号和标题
2. 已完成的修改
3. 当前任务状态变化
4. 测试结果
5. 是否已写入开发清单和变更记录
6. 剩余未完成任务
7. 风险或阻塞项

---

## 异常处理

### 找不到目录

如果找不到目标功能目录：

* 明确提示未找到对应 `dev-pipeline/tasks/<功能名称>/`
* 提示用户先通过 x-req 创建 task 目录或提供正确路径

### 缺少计划文件

如果缺少 `README.md` 或 `dev-checklist.md`：

* 不继续执行开发
* 明确指出缺少哪些文件
* 提示用户先通过 x-req 补齐计划文件

### 开发清单格式不合法

如果 `dev-checklist.md` 中没有标准表格或缺少状态列：

* 提示开发清单格式不符合要求
* 要求用户先修正文档，再继续执行

---

## 注意事项

* 不负责创建计划，只消费已有计划
* 不得跳过 README.md 直接开发
* 不得忽略开发清单状态直接执行
* 不得将”测试通过”直接视为”已完成”
* 更新状态时必须同步更新变更记录
* 若用户未明确要求，不自动执行 git 提交

---

## 质量门禁（每个任务必须走，无例外）

> **不管是连续开发整个 task 还是只做一个子任务（x-dev #3），gate 都必须走。**
> 即使 x-dev 自信”这次改动很简单不会有问题”，也必须先走 gate。

### 1. 写 dev-report.md

每个任务完成（🟢 测试通过）后，必须在 `dev-pipeline/tasks/<task>/` 下写入 `dev-report.md`，模板见 `skills/x-dev/templates/dev-report-template.md`。

规则：
1. 验证命令清单**至少包含一条测试类命令**；项目无测试框架时必须显式声明 `no-test-framework: true` + 理由。
2. 命令必须可在项目根目录直接运行，不允许依赖临时环境变量。
3. 自检结论段必须由 x-dev 自己运行命令后填写，不能空着或写”应该能跑”。

### 2. x-verify（Gate ① 事实验证）

写完 dev-report.md 后**立即**触发 x-verify：
- 复跑 dev-report.md 中的命令清单，对比 exit code + 关键输出
- 不主观判断代码质量，只看”能不能跑通”

### 3. x-qa-gate（Gate ② 质量评审）

x-verify 通过后**立即**触发 x-qa-gate：
- 串行 dispatch 3 个 opus 子 agent：R1 spec 符合性 → R2 边界完整性 → R3 测试真实性
- 全部 reviewer pass → 任务状态改为 ✅ 已完成

### 4. 失败回流

- 任一 gate fail → 进入 x-fix 修复，按 4 条回流规则回到对应节点重审
- fix-attempts 6 次上限共享（x-verify + x-qa-gate），超限停下问用户

---

## 连续开发模式（多任务自动推进）

> 适用场景：用户以 `x-dev <功能名称>` 触发、意图一次性连续推进整个 task 时生效。
> 用户只想处理某一项（如”x-dev #3”）时不启用——走完 gate 后停下。

gate 通过后（任务 ✅），自动执行：

1. **取下一个任务**：按 P0 → P1 → P2 选 dev-checklist 中 ⏳ 未开始的下一项
2. **开始开发**：回到执行流程第 1 步
3. **所有任务 ✅** → 输出最终汇报

### 停止条件

| 条件 | 动作 |
|------|------|
| 所有任务 ✅ | 输出最终汇报 |
| fix-attempts ≥ 6 次仍有 P0/P1 | 停下，列出剩余问题 |
| 任务与 README DoD 冲突 | 停下确认，不擅自改需求 |
| 环境异常 / 依赖缺失 | 停下上报 |

### 最终汇报

```markdown
## 开发汇报

- task：<task 名>
- 完成：N / M
- 修改文件：<列出>
- 未完成（如有）：
  - #Y：修复 K 次仍有问题，需手动介入
```

### 关键约束

- 不等用户确认：完成任务直接进 gate
- 不跳过 gate：任何任务都走
- 不自动 commit：git 操作由用户手动触发
- 不吞错误：停止条件触发时完整汇报
