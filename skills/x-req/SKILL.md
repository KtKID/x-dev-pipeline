---
name: x-req
description: |
  需求+开发准备 skill（合并原 x-plan）。一次确认，产出 README.md + dev-checklist.md + diagram.html。
  触发场景："帮我处理需求"、"梳理需求"、"开个 task"、"新建任务"、"这个功能怎么做"、
  "帮我拆一下"、"x-req"、"x-plan"（重定向）、用户提供需求文档路径、描述一个预计超过 2 小时的功能。
  与 x-qdev 的区别：x-qdev 适合小改动（1-2 小时内，不需要技术设计）；x-req 适合中等以上任务（需要 DoD + 技术设计 + 清单）。
  与 x-spec 的区别：x-spec 是系统/模块级文档（docs/），x-req 是具体 task 级（dev-pipeline/tasks/）。
---

# x-req 需求+开发准备

一步完成需求理解、技术设计、开发清单产出。用户只确认 1 次。

## 核心定位

x-req 负责：
1. 理解需求，确定核心目标
2. 关联涉及模块（reference docs/ 模块文档，如有）
3. 细化技术设计（本 task 的增量决策：数据结构、选型、链路）
4. 定义 DoD（验收清单——怎么算完成）
5. 生成 dev-checklist.md
6. 生成 diagram.html（可视化）
7. 保存 README.md

x-req 不负责：
- 创建模块级文档（x-spec 负责，产出到 docs/）
- 代码开发执行（x-dev 负责）
- 变更记录（changelog.md 由 x-dev 维护）

**核心边界**：x-req 回答"做什么 + 怎么做 + 怎么算完成"，然后交给 x-dev 执行。

---

## 目录结构

```
dev-pipeline/tasks/<task-name>/
├── README.md         # 需求 + 技术设计 + DoD（x-req 负责）
├── dev-checklist.md  # 开发清单（x-req 负责）
├── diagram.html      # 模块/组件图（x-req 负责，浏览器双击打开）
├── changelog.md      # 变更记录（x-dev 负责）
└── dev-report.md     # 完成报告（x-dev/x-qdev 负责）
```

**task 根目录固定为 `dev-pipeline/tasks/`**

---

## 工作流程

### 1. 理解任务

收到需求后：

1. 理解核心目标
2. 如果项目 `docs/` 下有相关模块文档 → 读取，获取模块设计上下文
3. 如果描述模糊 → 问 1-3 个关键问题（**一次性列出让用户批量答**，不要一个个问）
4. 如果任务明显太大（预计 >10 个 checklist 项、跨多模块架构改造）→ 建议先跑 x-spec 建立模块文档

**文档关联规则**：
- 如果用户通过文档路径或方案文档发起需求，自动关联到 README "涉及模块"段
- 如果项目已有 `docs/<system>/` 模块文档，自动 reference 相关模块文件
- 找不到相关模块文档也不阻塞——直接在 README 里简述涉及的代码模块

### 2. 一次确认

把以下内容**一次性**展示给用户（不分两步）：

```markdown
## 确认项

**核心目标**：[一句话]

**涉及模块**：
- [模块 A](ref路径) — 改动 XXX 部分

**技术设计**（如有）：
- 新增数据结构：[简述]
- 关键决策：[选型/方案]

**DoD（怎么算完成）**：
- [ ] 条件 1（可验证）
- [ ] 条件 2

**开发清单预览**：
| # | 优先级 | 任务 |
|---|--------|------|
| 1 | P0 | ... |
| 2 | P1 | ... |

以上 OK？回 Y 我产出文件。
```

等用户回复 **Y / 改 / 取消**。

### 3. 产出三个文件

用户确认后，在 `dev-pipeline/tasks/<task-name>/` 下产出 README.md + dev-checklist.md + diagram.html。

---

## 模板文件

所有模板在 `skills/x-req/templates/` 下，LLM 产出时复制对应模板并填充内容：

| 模板文件 | 对应产出 |
|---------|---------|
| `templates/README.md` | task 需求 + 技术设计 + DoD |
| `templates/dev-checklist.md` | 开发清单 |
| `templates/diagram-template.html` | 模块/组件图（苹果风 mermaid） |

---

## diagram.html 产出步骤

1. 复制 `skills/x-req/templates/diagram-template.html` 到 `dev-pipeline/tasks/<task-name>/diagram.html`
2. 替换 `<title>` 与 `<h1>` 中的 `<!-- TASK_NAME -->` 为实际 task 名
3. 替换 `<pre class="mermaid">` 块中的占位模块为实际内容
4. 节点 = README.md "涉及模块"列出的模块 + 本 task 新增的组件
5. 节点格式：`ID["名称<br/>P0/P1/P2 · 一句话"]:::p{0|1|2}`
6. 超 10 个节点用 subgraph 分组；同质重复节点压成 "×N"
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
- 包含文件：README.md + dev-checklist.md + diagram.html
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
- 产出 diagram.html
- 关联 docs/ 模块文档（如有）

### x-req 不负责
- 创建模块级文档（x-spec 负责）
- 代码开发执行（x-dev 负责）
- 任务状态更新（x-dev 负责）
- 变更记录（changelog.md 由 x-dev 维护）

---

## 注意事项

- **一次确认**：不走两步，不分"理解确认"和"拆分确认"
- **不重复 docs/**：已有模块文档的内容 reference 它，不复制
- **dev-checklist 直接产出**：确认步骤里已预览过，不需要用户单独再确认一次清单
- **diagram.html 必须与 README 一致**——后续模块变化时同步更新
- **如果项目没 docs/ 模块文档**：README "涉及模块"段直接写代码路径 + 简述，不强制 ref
- **不要跳过确认步骤直接保存**
- **不要进入开发执行**
