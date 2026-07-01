---
name: x-req
description: |
  需求+开发准备 skill（合并原 x-plan）。一次确认，产出架构设计驱动的 README.md + dev-checklist.md + diagram.md。
  触发场景："帮我处理需求"、"梳理需求"、"开个 task"、"新建任务"、"这个功能怎么做"、
  "帮我拆一下"、"x-req"、"x-plan"（重定向）、用户提供需求文档路径、描述一个预计超过 2 小时的功能。
  与 x-qdev 的区别：x-qdev 适合小改动（1-2 小时内，不需要技术设计）；x-req 适合中等以上任务（需要 DoD + 架构设计 + 架构驱动开发清单）。
  与 x-spec 的区别：x-spec 是系统/spec 需求包文档（docs/spec/），x-req 是具体 task 级（dev-pipeline/tasks/）。
---

# x-req 需求+开发准备

一步完成需求理解、架构设计、开发清单产出。用户只确认 1 次。

## 核心定位

x-req 负责：
1. 理解需求，提炼需求要点并与用户确认
2. 关联涉及模块（reference docs/spec/ 需求包文档，如有）
3. 做架构归属和契约设计（边界类、外部入口、输入输出、错误、状态副作用）
4. 从架构设计拆分开发任务（模块边界、契约、数据流、风险、依赖顺序）
5. 细化技术设计（本 task 的增量决策：数据结构、选型、链路）
6. 定义 DoD（验收清单——怎么算完成）
7. 定义 smoke/e2e 验收用例（README 中显式写出）
8. 记录自动化测试责任：单元/契约/边界测试由 x-dev 按改动补齐并写入 dev-report
9. 生成 dev-checklist.md
10. 生成 diagram.md（可视化）
11. 保存 README.md

x-req 不负责：
- 创建 spec 需求包文档（x-spec 负责，产出到 docs/spec/）
- 代码开发执行（x-dev 负责）

**核心边界**：x-req 回答"做什么 + 架构上怎么切 + 怎么算完成"，然后交给 x-dev 执行。

---

## 目录结构

```
dev-pipeline/tasks/<task-name>/
├── README.md         # 需求 + 技术设计 + DoD（x-req 负责）
├── dev-checklist.md  # 开发清单（x-req 负责）
├── diagram.md        # 模块/组件图（x-req 负责，纯 mermaid）
├── changelog.md      # 变更记录（x-req 产出初始文件，x-dev 后续追加）
└── dev-report.md     # 完成报告（x-dev/x-qdev 负责）
```

**task 根目录固定为 `dev-pipeline/tasks/`**

---

## 工作流程

### 0. 判断新建 vs 更新

收到需求后，先判断 task 目录 `dev-pipeline/tasks/<task-name>/` 是否已存在：

- **不存在（新建）** → 进入步骤 1 走标准创建流程
- **已存在（更新）** → 进入更新模式：
  1. 读取已有 README.md / dev-checklist.md / diagram.md / changelog.md，理解现状
  2. 识别本次变更项（需求增改、模块调整、清单增删），与用户对齐
  3. 一次确认里明确「变更前后 diff」：改了哪些要点 / 模块 / 任务 / DoD，而非全量重列
  4. 用户确认 Y 后，agent1 在已有文件上**原地更新**（不另起目录），changelog 追加一条更新记录
  5. 审核对照「变更前 diff」逐条核验，而非全量重审

### 1. 理解任务

收到需求后：

1. 理解核心目标
2. **确定归属 spec**：
   - 用户指定了 spec 路径 → 直接使用
   - 用户未指定 → 优先扫描 `docs/spec/` 目录，匹配最相关的 `docs/spec/<spec-name>/`
   - 新目录找不到 → 兼容读取 legacy `docs/*/*` 旧 spec 路径，只引用上下文，不新写旧路径
   - 找不到匹配 → 提示用户："这个任务属于哪个模块/spec？还是需要先跑 x-spec？"
   - 项目没有 `docs/spec/` 目录 → **提示用户**：本项目无 docs/spec/，x-req 面向较大功能开发，建议先跑 x-spec 产出方案（区别于 x-qdev 的轻量小改）；用户确认不需要 spec 则 `spec:` 留空继续，README "涉及模块"段直接写代码路径
3. 如果项目 `docs/spec/` 下有归属 spec → 读取 spec 文档，获取设计上下文
4. **架构归属检查**：
   - 扫描已有架构找模块边界类：有 docs/spec/ 读 spec 的 `02-module-breakdown.md`；没有就扫代码里的 `*Service` / `*Manager` / `*Client` / `*Gateway` / `*Repository` 类
   - 确定本 task 新增/改动的功能归属哪个模块的边界类，外部调用统一走它——**禁止新增散装函数直接被跨模块调用**
   - 找不到合适归属 → 在确认项里建议"新建 `XxxService/Manager`"或"先跑 x-spec 补模块设计"，由用户拍板
   - 边界设计原则与暴露决策规则以 `skills/x-spec/SKILL.md` 的"模块边界设计原则"为正源，此处不复制
5. **架构驱动拆分**：
   - 开发清单由架构设计推导：模块边界、公开契约、数据流、风险层级、依赖顺序。
   - 先锁主边界类和外部入口，再拆公开契约/schema/state、核心实现、适配层/持久化/UI 集成、验证闭环。
   - 每个 checklist 任务都要能独立交付和独立 review；备注列写清 `模块/边界`、`契约或数据流`、`依赖 #N`。
   - P0 优先放契约、边界入口、核心状态和阻塞链路；P1 放适配层、UI/CLI/API 集成和主要验证；P2 放文档、体验增强和非阻塞优化。
   - 涉及核心业务逻辑、数据持久化/迁移、安全相关、跨模块集成、公共 API 变更的任务标记 🔍。
   - 同一优先级任务按依赖关系分组：共享契约或同一区域写入的任务串行；边界清晰且无写冲突的任务可并行交给 x-dev 子 agent。
6. 如果描述模糊 → 问 1-3 个关键问题（**一次性列出让用户批量答**，不要一个个问）
7. 如果任务明显太大（预计 >10 个 checklist 项、跨多模块架构改造）→ 建议用户先跑 x-spec。**用户同意 → x-req 暂停退出**；x-spec 产出 spec 后，用户重新发起 x-req，此时步骤 1 能匹配到该 spec 继续走流程。用户拒绝则按现有规模继续。

**spec 关联规则**：
- 每个 task 通过 README 头部 `spec:` 字段指向归属 spec（如 `spec: docs/spec/scheduler-cron-parsing`）
- 一个 task 只指向一个 spec；跨 spec 的大任务应拆成多个 task
- `spec:` 为可选字段——无 docs/spec/ 时的处理见步骤 1

### 2. 一次确认

按 `skills/x-req/templates/confirmation.md` 的结构，把确认项**一次性**展示给用户。需求要点用大白话提炼 3-7 条，架构拆分策略必须说明模块边界、契约、依赖顺序和风险层级，作为后续文档审核基准。

等用户回复 **Y / 改 / 取消**。

### 3. 子 agent 创建 + 审核 + 修复（用户确认后）

用户回 Y 后，**主 agent 不直接写产出文件**：创建派给 agent1，审核由主 agent 亲自做（主 agent 手里有确认过的要点和完整对话上下文，正适合当审核基准的持有者）。agent1 的 prompt 必须自包含（fresh subagent 看不到主对话）。

#### 3.1 agent1（创建者）：产出四个文件

```
Agent({
  description: "x-req 文档创建",
  subagent_type: "general-purpose",
  prompt: <自包含：确认过的需求要点全文 + 确认项全文（归属 spec / 架构归属 /
          架构拆分策略 / 技术设计 / DoD / 清单预览）+ 模板路径 skills/x-req/templates/（要求读取
          README.md / dev-checklist.md / diagram.md / changelog.md / subagent-completion.md）+
          task 目录路径 dev-pipeline/tasks/<task-name>/>
})
```

agent1 完成时必须按 `skills/x-req/templates/subagent-completion.md` 的结构回报。

在 task 目录下产出 README.md + dev-checklist.md + diagram.md + changelog.md。

#### 3.2 主 agent 审核：出 mini-report

agent1 产出后，**主 agent 亲自读产出文件**，对照确认过的需求要点逐条审核（按 P0/P1 分级；**只报告不修改**，修改一律交回 agent1）。审核聚焦 README / dev-checklist / diagram 三件套，changelog 只查初始记录是否生成：

1. **要点覆盖**：确认过的需求要点每条都落进了 README——漏一条 = P0
2. **三文件一致**：README "涉及模块" / dev-checklist 任务 / diagram 节点三者对得上——不一致 = P0
3. **DoD 可验证**：每条 DoD 都能客观判定完成与否——含糊不可测 = P0
4. **Smoke/E2E 明确**：README 写出可执行或可人工验收的 smoke/e2e 用例，且每条能映射到 DoD 或关键风险——缺失 = P0
5. **自动化测试责任明确**：README 写明 x-dev 需补齐单元/契约/边界测试并进入 dev-report 命令清单——缺失 = P1
6. **架构归属落实**：确认过的边界类归属体现在技术设计里——丢失 = P0
7. **架构拆分可执行**：dev-checklist 任务能从 README 架构拆分策略追溯到模块边界、契约、依赖顺序和风险层级——缺失 = P0
8. **规范符合**：模板结构 / 状态符号 / 优先级 / 🔍 标记——不符 = P1

#### 3.3 修复（只修一轮，不复审）

- 审核发现 P0 → 把反馈交回 agent1 修复（优先用 SendMessage 续接 agent1，保留它的创建上下文；环境不支持续接则重新派发，prompt 附审核反馈全文）。**修完不复审**，直接进入步骤 4 收尾，推荐进入 x-dev
- 无 P0 → 直接进入步骤 4 收尾（P1 在收尾汇报里列给用户参考，不阻塞）

---

## 模板文件

所有模板在 `skills/x-req/templates/` 下，LLM 使用对应模板填充；文件产出类模板复制到 task 目录：

| 模板文件 | 对应产出 |
|---------|---------|
| `templates/confirmation.md` | 一次确认消息 |
| `templates/README.md` | task 需求 + 技术设计 + DoD |
| `templates/dev-checklist.md` | 开发清单 |
| `templates/diagram.md` | 模块/组件图（纯 mermaid） |
| `templates/changelog.md` | 初始变更记录（后续由 x-dev 追加） |
| `templates/subagent-completion.md` | agent1 完成回报 |

---

## README.md 产出规则

复制 `skills/x-req/templates/README.md` 到 task 目录并填充。确认过的需求要点、归属 spec、涉及模块、架构归属、架构拆分策略、DoD、Smoke/E2E、自动化测试责任都要落进 README。

---

## dev-checklist.md 产出规则

复制 `skills/x-req/templates/dev-checklist.md` 到 task 目录并填充。保持标准表格列名；状态、优先级、质检列枚举和标记规则写在模板注释中；确认步骤里的清单预览要与最终 checklist 对齐；备注列必须写入模块边界、契约或数据流依据、依赖关系。

---

## diagram.md 产出规则

复制 `skills/x-req/templates/diagram.md` 到 task 目录并填充。节点格式、subgraph 边界、节点上限、README 模块和架构单元一致性等规则写在模板注释中；README.md 是文字事实源，diagram.md 是架构拆分的只读视图。


---

### 4. 收尾

产出完毕后向用户汇报：
- 创建的 task 目录路径
- 包含文件：README.md + dev-checklist.md + diagram.md + changelog.md
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
- 产出 README.md（含架构设计 + 架构拆分策略 + DoD）
- 产出 dev-checklist.md
- 产出 diagram.md
- 产出 changelog.md（初始文件 + 一条"创建 task"记录）
- 关联 docs/spec/ 需求包文档（如有）

### x-req 不负责
- 创建 spec 需求包文档（x-spec 负责）
- 代码开发执行（x-dev 负责）
- 任务状态更新（x-dev 负责）
- changelog 后续记录追加（x-dev 负责，x-req 只产出初始文件）

---

## 注意事项

- **一次确认**：不走两步，不分"理解确认"和"拆分确认"；需求要点就在确认项顶部，随整体一次确认
- **主 agent 不直接写产出文件**：README / dev-checklist / diagram 一律由 agent1 创建（含修复）；主 agent 负责追问、确认、派发、审核、汇报，审核只报告不动手改
- **不重复 spec 内容**：已有 spec 文档的内容 reference 它，不复制
- **dev-checklist 直接产出**：确认步骤里已预览过，不需要用户单独再确认一次清单
- **diagram.md 必须与 README 一致**——后续模块变化时同步更新
- **spec 图同步**：创建 task 时如果归属 spec 的 `90-task-map.md` 标为 Phase 2/3 但现在要开发 → 先更新 task-map 状态为"开发中" + 更新 `diagrams.md` 颜色为蓝，告知用户"已同步更新 spec 图"；`diagrams.html` / `architecture.html` 仅作为 legacy spec 包迁移时的只读兼容输入
- **不要跳过确认步骤直接保存**
- **不要进入开发执行**
