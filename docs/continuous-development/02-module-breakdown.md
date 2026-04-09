# 模块拆分

## 模块总览

| 模块 | 职责 | 依赖 | 状态 | 备注 |
|------|------|------|------|------|
| x-finish | 收尾决策（四选一） | x-dev/x-qdev 执行完毕 | 方案确认 | 可独立开发 |
| x-req-ext | 设计文档输出 + 需求分析 | 无 | 方案确认 | 扩展现有 skill |
| x-drive | 连续开发编排层（任务调度 + checkpoint） | x-finish + x-dev-ext | 探索中 | 核心编排模块 |
| x-dev-ext | subagent 驱动执行模式 | x-finish | 探索中 | 扩展现有 skill |
| session-start hook | 持续上下文注入 | 无 | 探索中 | 配置层，能力待验证 |

---

## 模块详情

### 模块 1：x-finish（收尾决策）<a name="x-finish"></a>

**职责**：在开发任务完成后提供四选一决策，驱动下一轮工作或结束会话。

**包含范围**：
- 四选一选项：继续新工作 / 创建 PR 后继续 / 创建 PR 后暂停 / 直接暂停
- 各选项的完整执行动作（创建 PR、切换分支、清理分支等）
- 与 x-req 的衔接（选"继续新工作"时回到需求分析）
- 自动汇总本次开发产出，写入 changelog.md

**不包含范围**：
- 自动执行 git push（需用户确认）
- 自动创建 release notes
- 处理 merge conflict（交给用户）

**依赖**：无（独立模块，x-dev/x-qdev 完成后触发）

**风险与讨论点**：
- Claude Code CLI 是否支持自动 `gh pr create`？需要验证 `gh` CLI 可用性
- PR 标题和 body 格式是否需要模板？
- 用户在多任务中途想切换上下文时，是否允许跳过 x-finish 直接进入新任务？

**task 建议**：
- 建议 task 名：`x-finish-skill`
- 是否进入 x-req：**是**，可立即开始
- 原因：独立性强，不依赖其他模块

---

### 模块 2：x-req-ext（设计文档输出）<a name="x-req-ext"></a>

**职责**：在 x-req 的需求报告之上增加设计文档输出能力，与 superpowers 的 brainstorming 阶段对齐。

**包含范围**：
- 两步确认后追加第三步：方案设计（2-3 种方案 + trade-off + 推荐）
- 设计文档格式规范（Goals / Non-goals / Design / Risks / Alternatives）
- 设计文档保存路径：`dev-pipeline/tasks/<task-name>/design.md`
- 硬性门控：设计文档未经用户审批，禁止触发 x-plan

**不包含范围**：
- 自动生成代码或伪代码
- 绘制架构图（可用 ASCII diagram）
- 执行技术选型 benchmark

**依赖**：无（扩展现有 skill）

**风险与讨论点**：
- 当前 x-req 输出 README.md，design.md 是否与 README.md 合并（作为章节）还是独立文件？
  - 建议：独立文件 `design.md`，README.md 仅作为需求总览导航
- 设计文档粒度：简单需求是否需要完整 design.md？
  - 建议：x-req 自动判断，简单的进入简化模式，复杂的强制完整设计
- 是否复用 superpowers 的设计文档格式模板？

**task 建议**：
- 建议 task 名：`x-req-design-doc`
- 是否进入 x-req：**是**，可立即开始
- 原因：扩展点明确，不破坏现有 x-req 逻辑

---

### 模块 3：x-drive（连续开发编排层）<a name="x-drive"></a>

**职责**：作为连续开发的主编排器，负责任务调度、checkpoint 汇报、断点恢复，是 superpowers 的 executing-plans + 连续驱动机制的结合体。

**包含范围**：
- **任务调度循环**：读取 plan → 派发 x-dev 执行 → 等待完成 → 循环
- **每小时 checkpoint**：执行满 1 小时后强制向用户汇报进度，格式：
  ```
  ## Checkpoint（HH:MM）
  - 已完成：N/M
  - 当前：<任务名>
  - 阻塞项：无 / <描述>
  ```
- **断点恢复**：读取 dev-checklist.md 中已完成状态，从断点继续
- **subagent 协调**（参见 x-dev-ext）：派发 subagent → 接收结果 → 判定是否继续
- **六类停止条件 + 唤醒机制**：
  | 停止时机 | 触发条件 | 唤醒方式 |
  |----------|----------|----------|
  | implementer 问问题 | NEEDS_CONTEXT | Controller 提供上下文，重新派发（无需人类介入） |
  | implementer 被阻塞 | BLOCKED | Controller 评估：加上下文 / 换更强模型 / 拆分任务 / 上报人类 |
  | implementer 有顾虑 | DONE_WITH_CONCERNS | Controller 读取顾虑，判断是否需要人类介入 |
  | 所有任务完成 | 最后一任务两阶段 review 全部通过 | 自动触发 x-finish |
  | reviewer 发现问题 | x-cr 发现问题 | implementer 修复 → 重新审核（硬编码循环，无人类等待） |
  | 各阶段审批门 | x-req-ext 设计文档 / x-plan 任务清单 | 用户确认后继续下一阶段 |

**不包含范围**：
- 直接写代码（交给 x-dev）
- 管理 git 分支（交给 x-finish）
- 外部 API 调用或 CI/CD 集成

**依赖**：x-finish（收尾决策），x-dev-ext（执行模式）

**风险与讨论点**：
- **checkpoint 频率**：固定 1 小时是否合适？是否需要可配置？
  - 建议：默认 1 小时，通过参数允许用户调整（`/x-drive <task> --interval 30m`）
- **subagent 执行模式**：Claude Code 的 Agent 工具是否支持在一个 session 内调度多个 subagent？
  - 方案 A：使用 `Agent` tool 派发 implementer subagent（类似 superpowers）
  - 方案 B：在 x-dev 内部顺序执行，不使用 subagent（更稳定但无并行）
  - 建议：先实现方案 B，再探索方案 A
- **断点恢复精度**：如果 session 中途崩溃，x-drive 如何判断"最后一个任务真正完成"？
  - 依赖 dev-checklist.md 状态——只有标记为 🟢 及以上的才算完成
- **reviewer 循环不退出**（核心元规则）：reviewer 发现问题时，skill 硬编码了修复循环，**没有人类等待点**
  - 流程：发现问题 → implementer 修复 → 重新派发 reviewer → 再审 → 通过才推进
  - x-cr 的 skill 文本必须明确"此阶段无人类等待窗口"，防止 AI 在 reviewer 有问题时停下来问人类

**task 建议**：
- 建议 task 名：`x-drive-skill`
- 是否进入 x-req：**否**，建议等 x-finish 和 x-req-ext 先完成
- 原因：编排层需要先有明确的执行单元（x-dev）和收尾机制（x-finish）

---

### 模块 4：x-dev-ext（subagent 驱动执行模式）<a name="x-dev-ext"></a>

**职责**：扩展 x-dev，使其支持 subagent 驱动模式，能够在连续开发中派发独立 agent 执行任务。

**包含范围**：
- **模式 A：batch 执行**（默认，顺序执行，与现有 x-dev 一致）
- **模式 B：subagent 驱动**（使用 Agent tool 派发 implementer，完整传递上下文）
  - 传递内容：plan.md 路径 + 任务描述 + design.md（如有）+ 验证步骤
  - implementer 自驱：实现 → 测试 → 提交 → 自审 → 报告（无需 Controller 指令）
  - 完成后返回 Controller（x-drive）
- **implementer 自审清单**（报告前必须逐项检查）：
  - [ ] 改动范围是否精确匹配任务描述？→ 多余改动撤销
  - [ ] 是否有硬编码/魔法数字？
  - [ ] 是否有明显性能问题（循环内查询 N+1 等）？
  - [ ] 错误处理是否完整？
  - [ ] 是否引入新的安全漏洞？
  - [ ] 是否有 TODO/占位符遗留？
  - [ ] 是否符合项目现有的代码风格？
  - [ ] 是否只构建了请求的内容（YAGNI）？
  - [ ] 测试是否覆盖关键路径？
- **implementer 四种状态汇报**（必须返回 Controller）：
  - `DONE`：全部完成，可进入 spec 合规审查
  - `DONE_WITH_CONCERNS`：完成但有顾虑，Controller 评估是否需要人类介入
  - `BLOCKED`：被阻��，Controller 评估：加上下文 / 换更强模型 / 拆分任务 / 上报人类
  - `NEEDS_CONTEXT`：需要更多上下文，Controller 提供后重新派发
- **implementer 纪律约束**：
  - 遇到不确定问题时，**必须停下来提问**，不允许猜测或假设
  - 遇到复杂架构决策时，**必须上报 BLOCKED**，不允许自行决定
  - 自审发现问题，必须**立即修复**，不允许带着问题报告 DONE

**不包含范围**：
- spec 合规审查（由 x-cr 执行，但 x-dev-ext 需要传递 spec 合规判定标准给 implementer）
- 并行派发多个 subagent（同一时刻只派发一个，避免冲突）

**依赖**：x-finish（收尾决策决定了如何推进到下一步）

**风险与讨论点**：
- subagent 上下文污染：每个任务用新的 subagent，上下文干净，不会累积污染
- implementer 遇到不确定问题时，必须向 Controller 申请决策，不自己乱猜
  - 机制：imlementer 遇到阻塞项时输出 `BLOCKED`，x-drive 介入评估
- 模式 B 是否需要用户显式激活（`/x-drive <task> --mode subagent`）还是默认行为？
  - 建议：默认 batch，subagent 模式需显式指定
- **模型选择策略**（新增）：根据任务类型选不同能力的模型
  - 机械性实现任务（1-2 个文件，清晰 spec）→ 最便宜模型
  - 集成与判断任务（多文件协调、调试）→ 标准模型
  - 架构、设计、审核任务 → 最强模型
  - 原则：plan 写得越细，implementer 越能用便宜模型完成任务

**task 建议**：
- 建议 task 名：`x-dev-subagent-mode`
- 是否进入 x-req：**否**，建议和 x-drive 合并开发
- 原因：x-dev-ext 是 x-drive 的执行引擎，两者紧密耦合

---

### 模块 5：session-start hook（持续上下文注入）<a name="session-hook"></a>

**职责**：在每次 session 启动时自动注入上下文，让 AI 知道当前有哪些未完成的任务、最近一次 checkpoint 是什么。

**包含范围**：
- 设计 session-start hook 配置格式（在 CLAUDE.md 或 settings.json 中）
- 注入内容：
  1. 当前项目是否有未完成的 dev-pipeline/tasks？
  2. 最近一次 checkpoint 时间（如有）
  3. 提醒用户"检测到未完成任务，是否继续？"
- 自动检测断点：读取所有 `dev-pipeline/tasks/*/dev-checklist.md`，找出非 ✅ 状态的任务

**不包含范围**：
- 自动恢复执行（必须用户确认）
- 跨 session 的任务队列管理（依赖文件系统）

**依赖**：无（配置层）

**风险与讨论点**：
- **Claude Code hook 能力边界**：`settings.json` 的 `hooks.onStartup` 是否支持注入对话内容？
  - 方案 A：`onStartup` hook 注入一个 system prompt 片段
  - 方案 B：在 CLAUDE.md 根文件中写入"持续开发状态"章节，每次 session 由 AI 自行读取
  - 建议：方案 B 更稳定，不依赖 hook API 能力
- hook 注入的内容量：session-start 时注入过多内容会干扰正常对话
  - 建议：只注入摘要（1-3 行），详细上下文在用户确认继续后按需读取
- **hook 是否在 x-dev-pipeline 的 skill 中配置，还是在用户项目根目录的 CLAUDE.md 中配置？**
  - 建议：在 skill 的 SKILL.md 中描述 hook 配置方式，让用户自行添加到项目 CLAUDE.md

**task 建议**：
- 建议 task 名：`session-hook-design`
- 是否进入 x-req：**否**，建议在 x-drive 完成后探索
- 原因：hook 机制依赖平台，需要先跑通核心流水线再补 hook

---

## 流水线对照：x-dev-pipeline vs Superpowers

```
x-dev-pipeline（目标形态）
─────────────────────────────────────────────────────────
用户需求
   ↓
x-req-ext（需求分析 + 设计文档）→ README.md + design.md
   ↓
x-plan（任务分解）→ plan.md + dev-checklist.md
   ↓
x-drive（连续编排层）
   ├─ batch 模式：x-dev 顺序执行
   └─ subagent 模式：Agent tool 派发 implementer
   ↓
  └─ x-cr spec-review（spec 合规，不信任 implementer 报告）
  └─ x-cr code-review（代码质量）
  └─ 发现问题 → implementer 修复 → 重新审核（无人类等待点）
   ↓
x-finish（收尾决策）→ 四选一
   ↓
选"继续新工作" → 回到 x-req-ext（形成连续循环）
选"创建 PR 后继续" → gh pr create → 回到 x-req-ext

Superpowers（参考）
─────────────────────────────────────────────────────────
用户需求
   ↓
brainstorming → design doc
   ↓
writing-plans → Task Card（TodoWrite）
   ↓
executing-plans（Controller + implementer subagent）
   ↓
  └─ spec-reviewer（spec 合规，独立验证，不信任报告）
  └─ code-quality-reviewer（代码质量）
  └─ 发现问题 → implementer 修复 → 重新审核（无人类等待点）
   ↓
finishing-a-development-branch → 四选一
   ↓
回到 brainstorming（形成连续循环）
```

---

## 附录：元规则（来自 superpowers 核心设计原则）

> **"IF A SKILL APPLIES, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT."**

系统级别的元规则。在任何时机、任何任务下，AI 都不会跳过 skill 检测。

> **skill 文本本身就是程序。** AI 读取 skill 后，没有任何"决定要不要执行"的自由度——流程图箭头、Red Flags 清单、状态机转换，把执行路径锁死。AI 只是忠实地执行文本中的指令。

> **驱动力 = 没有等待人类的设计。** skill 里根本没有"停下来问用户"这个选项，所以 AI 看不到任何需要停下来的理由，就一路跑下去了。

**对 x-dev-pipeline 的影响：**
- x-cr 的 spec-review 阶段必须**独立验证**，不能信任 implementer 的自我报告
- reviewer 循环必须是硬编码的：发现问题 → implementer 修复 → 重新审核 → 通过才推进，**没有人类等待窗口**
- implementer 必须实现四种状态汇报（DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT），不允许沉默产出不确定的工作
- x-drive 的 checkpoint 必须强制执行，不依赖用户主动询问
