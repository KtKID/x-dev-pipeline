---
name: x-req
description: |
  需求+开发准备 skill（合并原 x-plan）。一次确认，产出 README.md + dev-checklist.md + diagram.md。
  触发场景："帮我处理需求"、"梳理需求"、"开个 task"、"新建任务"、"这个功能怎么做"、
  "帮我拆一下"、"x-req"、"x-plan"（重定向）、用户提供需求文档路径、描述一个预计超过 2 小时的功能。
  与 x-qdev 的区别：x-qdev 适合小改动（1-2 小时内，不需要技术设计）；x-req 适合中等以上任务（需要 DoD + 技术设计 + 清单）。
  与 x-spec 的区别：x-spec 是系统/spec 需求包文档（docs/spec/），x-req 是具体 task 级（dev-pipeline/tasks/）。
---

# x-req 需求+开发准备

一步完成需求理解、技术设计、开发清单产出。用户只确认 1 次。

## 核心定位

x-req 负责：
1. 理解需求，提炼需求要点并与用户确认
2. 关联涉及模块（reference docs/spec/ 需求包文档，如有）
3. 细化技术设计（本 task 的增量决策：数据结构、选型、链路）
4. 定义 DoD（验收清单——怎么算完成）
5. 定义 smoke/e2e 验收用例（README 中显式写出）
6. 记录自动化测试责任：单元/契约/边界测试由 x-dev 按改动补齐并写入 dev-report
7. 生成 dev-checklist.md
8. 生成 diagram.md（可视化）
9. 保存 README.md

x-req 不负责：
- 创建 spec 需求包文档（x-spec 负责，产出到 docs/spec/）
- 代码开发执行（x-dev 负责）
- 变更记录（changelog.md 由 x-dev 维护）

**核心边界**：x-req 回答"做什么 + 怎么做 + 怎么算完成"，然后交给 x-dev 执行。

---

## 目录结构

```
dev-pipeline/tasks/<task-name>/
├── README.md         # 需求 + 技术设计 + DoD（x-req 负责）
├── dev-checklist.md  # 开发清单（x-req 负责）
├── diagram.md        # 模块/组件图（x-req 负责，纯 mermaid）
├── changelog.md      # 变更记录（x-dev 负责）
└── dev-report.md     # 完成报告（x-dev/x-qdev 负责）
```

**task 根目录固定为 `dev-pipeline/tasks/`**

---

## 工作流程

### 1. 理解任务

收到需求后：

1. 理解核心目标
2. **确定归属 spec**：
   - 用户指定了 spec 路径 → 直接使用
   - 用户未指定 → 优先扫描 `docs/spec/` 目录，匹配最相关的 `docs/spec/<spec-name>/`
   - 新目录找不到 → 兼容读取 legacy `docs/*/*` 旧 spec 路径，只引用上下文，不新写旧路径
   - 找不到匹配 → 提示用户："这个任务属于哪个模块/spec？还是需要先跑 x-spec？"
   - 项目没有 `docs/spec/` 目录 → `spec:` 留空，不阻塞，README "涉及模块"段直接写代码路径
3. 如果项目 `docs/spec/` 下有归属 spec → 读取 spec 文档，获取设计上下文
4. **架构归属检查**（开发/编程类任务必做）：
   - 扫描已有架构找模块边界类：有 docs/spec/ 读 spec 的 `02-module-breakdown.md`；没有就扫代码里的 `*Service` / `*Manager` / `*Client` / `*Gateway` / `*Repository` 类
   - 确定本 task 新增/改动的功能归属哪个模块的边界类，外部调用统一走它——**禁止新增散装函数直接被跨模块调用**
   - 找不到合适归属 → 在确认项里建议"新建 `XxxService/Manager`"或"先跑 x-spec 补模块设计"，由用户拍板
   - 边界设计原则与暴露决策规则以 `skills/x-spec/SKILL.md` 的"模块边界设计原则"为正源，此处不复制
5. 如果描述模糊 → 问 1-3 个关键问题（**一次性列出让用户批量答**，不要一个个问）
6. 如果任务明显太大（预计 >10 个 checklist 项、跨多模块架构改造）→ 建议先跑 x-spec

**spec 关联规则**：
- 每个 task 通过 README 头部 `spec:` 字段指向归属 spec（如 `spec: docs/spec/scheduler-cron-parsing`）
- 一个 task 只指向一个 spec；跨 spec 的大任务应拆成多个 task
- `spec:` 为可选字段——没有 docs/spec/ 的项目不阻塞

### 2. 一次确认

把以下内容**一次性**展示给用户（不分两步）：

```markdown
## 确认项

**需求要点**（提炼用户原始需求，大白话 3-7 条，这是后续文档审核的基准）：
1. [要点 1——用户要什么，不是怎么实现]
2. [要点 2]
3. ...

**归属 spec**：`docs/spec/<spec-name>` （或"无，项目未建 spec"）

**核心目标**：[一句话]

**涉及模块**：
- 模块 A：参考 `spec: docs/spec/<spec-name>`，改动 `repo:src/module-a/...`

**架构归属**（开发类任务必填）：
- 新增功能归属 [模块X] 边界类 `XxxService` —— 外部调用统一走它
- （找不到归属时）⚠️ 现有架构无合适边界类，建议：新建 `XxxManager` / 先跑 x-spec 补设计

**技术设计**（如有）：
- 新增数据结构：[简述]
- 关键决策：[选型/方案]

**DoD（怎么算完成）**：
- [ ] 条件 1（可验证）
- [ ] 条件 2

**Smoke / E2E 验收用例**：
- Smoke：[快速验证的启动、配置、主流程 sanity check]
- E2E：[跨前后端 / CLI 到核心模块 / 用户可见完整链路]
- 自动化测试责任：x-dev 必须为改动逻辑补齐单元/契约/边界测试，并在 dev-report 写入验证命令

**开发清单预览**：
| # | 优先级 | 任务 |
|---|--------|------|
| 1 | P0 | ... |
| 2 | P1 | ... |

以上 OK？回 Y 我产出文件。
```

等用户回复 **Y / 改 / 取消**。

### 3. 子 agent 创建 + 审核 + 修复（用户确认后）

用户回 Y 后，**主 agent 不直接写产出文件**：创建派给 agent1，审核由主 agent 亲自做（主 agent 手里有确认过的要点和完整对话上下文，正适合当审核基准的持有者）。agent1 的 prompt 必须自包含（fresh subagent 看不到主对话）。

#### 3.1 agent1（创建者）：产出三个文件

```
Agent({
  description: "x-req 文档创建",
  subagent_type: "general-purpose",
  prompt: <自包含：确认过的需求要点全文 + 确认项全文（归属 spec / 架构归属 /
          技术设计 / DoD / 清单预览）+ 模板路径 skills/x-req/templates/ +
          task 目录路径 dev-pipeline/tasks/<task-name>/>
})
```

agent1 完成时必须按以下模板回报：

```markdown
## Subagent Completion

**Completed by model:** <actual model id>
**Status:** done / blocked / failed

## Files written
- ...

## Notes
- ...
```

在 task 目录下产出 README.md + dev-checklist.md + diagram.md。

#### 3.2 主 agent 审核：出 mini-report

agent1 产出后，**主 agent 亲自读三个产出文件**，对照确认过的需求要点逐条审核（按 P0/P1 分级；**只报告不修改**，修改一律交回 agent1）：

1. **要点覆盖**：确认过的需求要点每条都落进了 README——漏一条 = P0
2. **三文件一致**：README "涉及模块" / dev-checklist 任务 / diagram 节点三者对得上——不一致 = P0
3. **DoD 可验证**：每条 DoD 都能客观判定完成与否——含糊不可测 = P0
4. **Smoke/E2E 明确**：README 写出可执行或可人工验收的 smoke/e2e 用例，且每条能映射到 DoD 或关键风险——缺失 = P0
5. **自动化测试责任明确**：README 写明 x-dev 需补齐单元/契约/边界测试并进入 dev-report 命令清单——缺失 = P1
6. **架构归属落实**：确认过的边界类归属体现在技术设计里——丢失 = P0
7. **规范符合**：模板结构 / 状态符号 / 优先级 / 🔍 标记——不符 = P1

#### 3.3 修复（只修一轮，不复审）

- 审核发现 P0 → 把反馈交回 agent1 修复（优先用 SendMessage 续接 agent1，保留它的创建上下文；环境不支持续接则重新派发，prompt 附审核反馈全文）。**修完不复审**，直接进收尾，推荐进入 x-dev
- 无 P0 → 直接进收尾（P1 在收尾汇报里列给用户参考，不阻塞）

---

## 模板文件

所有模板在 `skills/x-req/templates/` 下，LLM 产出时复制对应模板并填充内容：

| 模板文件 | 对应产出 |
|---------|---------|
| `templates/README.md` | task 需求 + 技术设计 + DoD |
| `templates/dev-checklist.md` | 开发清单 |
| `templates/diagram.md` | 模块/组件图（纯 mermaid） |

---

## diagram.md 产出步骤

1. 复制 `skills/x-req/templates/diagram.md` 到 `dev-pipeline/tasks/<task-name>/diagram.md`
2. 替换标题中的 TASK_NAME 为实际 task 名，保留头部的查看/缩放建议引用块
3. 替换 mermaid 代码块中的占位模块为实际内容
4. 节点 = README.md "涉及模块"列出的模块 + 本 task 新增的组件
5. 节点格式：`ID["名称<br/>P0/P1/P2 · 一句话"]:::p{0|1|2}`
6. 单图节点上限 ~12：超限先压缩同质节点（"×N"）；subgraph 一律按模块划分（一个模块一个框，框线即模块边界），不按技术栈/层次混分
7. 模块清单必须与 README.md 完全一致——diagram 是 README 的只读视图

---

## 状态规范

| 符号 | 状态 | 说明 |
|------|------|------|
| ⏳ | 未开始 | 等待开始 |
| ▶️ | 进行中 | 正在执行 |
| 🟡 | 待测试 | 开发完成，等待验证 |
| 🔴 | 测试失败 | 需要修复 |
| 🟢 | 测试通过 | 验证通过 |
| ✅ | 已完成 | review 确认后标记 |

状态流转：`⏳ → ▶️ → 🟡 → 🟢 → ✅`（失败时 `🟡 → 🔴 → 修复 → 🟡`）

## 优先级规范

| 优先级 | 说明 |
|--------|------|
| P0 | 阻塞性，必须立即做 |
| P1 | 重要，必须完成 |
| P2 | 增强，可后续处理 |

## 质检标记规则

生成 dev-checklist 时，对复杂/关键任务标记 🔍（质检列）：

**必须标记 🔍**：涉及核心业务逻辑、数据持久化/迁移、安全相关、跨模块集成、公共 API 变更。

**不需要标记**：纯 UI 调整、配置项修改、文档更新、简单增删改查。

标记 🔍 的任务在 x-dev 并行执行时需立即做代码审查，审查通过才继续。

---

## 4. 收尾

产出完毕后向用户汇报：
- 创建的 task 目录路径
- 包含文件：README.md + dev-checklist.md + diagram.md
- 审核结论：主 agent 审核发现的 P0（已由 agent1 修复的列"已修复"）+ 遗留 P1（参考项，不阻塞）
- 推荐下一步：`x-dev <task-name>`

---

## 目录命名规范

- **task 目录**：`dev-pipeline/tasks/<task-name>/`
- **task 名称**：URL 友好格式（空格→`-`，斜杠→`-`，特殊字符去除）
- **示例**：`用户登录` → `dev-pipeline/tasks/user-login/`

---

## 职责边界

### x-req 负责
- 理解需求，一次确认
- 产出 README.md（含技术设计 + DoD）
- 产出 dev-checklist.md
- 产出 diagram.md
- 关联 docs/spec/ 需求包文档（如有）

### x-req 不负责
- 创建 spec 需求包文档（x-spec 负责）
- 代码开发执行（x-dev 负责）
- 任务状态更新（x-dev 负责）
- 变更记录（changelog.md 由 x-dev 维护）

---

## 注意事项

- **一次确认**：不走两步，不分"理解确认"和"拆分确认"；需求要点就在确认项顶部，随整体一次确认
- **主 agent 不直接写产出文件**：README / dev-checklist / diagram 一律由 agent1 创建（含修复）；主 agent 负责追问、确认、派发、审核、汇报，审核只报告不动手改
- **不重复 spec 内容**：已有 spec 文档的内容 reference 它，不复制
- **dev-checklist 直接产出**：确认步骤里已预览过，不需要用户单独再确认一次清单
- **diagram.md 必须与 README 一致**——后续模块变化时同步更新
- **如果项目没 docs/spec/ 文档**：`spec:` 留空，README "涉及模块"段直接写代码路径 + 简述，不强制 ref
- **spec 图同步**：创建 task 时如果归属 spec 的 `90-task-map.md` 标为 Phase 2/3 但现在要开发 → 先更新 task-map 状态为"开发中" + 更新 `diagrams.md` 颜色为蓝，告知用户"已同步更新 spec 图"；`diagrams.html` / `architecture.html` 仅作为 legacy spec 包迁移时的只读兼容输入
- **不要跳过确认步骤直接保存**
- **不要进入开发执行**
