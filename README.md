# x-dev-pipeline

> Version: 0.1.2

Claude Code 开发工作流插件。提供从系统方案规划、需求分析、计划生成、开发执行到代码审查、问题修复的完整链路，以及轻量级快速开发入口。

## 安装

### 安装

```bash
# 1. 克隆或复制项目到 plugins 目录
git clone https://github.com/KtKID/x-dev-pipeline.git ~/.claude/plugins/x-dev-pipeline
# 或本地开发：cp -r /path/to/x-dev-pipeline ~/.claude/plugins/x-dev-pipeline

# 2. 进入插件目录，注册本地 marketplace
cd ~/.claude/plugins/x-dev-pipeline
claude plugin marketplace add ./.claude-plugin/marketplace.json

# 3. 安装插件
claude plugin install x-dev-pipeline@x-dev-pipeline --scope user
```

## 工作流总览

```
x-spec（系统方案）→ x-req（需求分析）→ x-plan（计划生成）→ x-dev（开发执行）→ x-cr（代码审查）→ x-fix（问题修复）
                                                     ↑
                                                x-qdev（快速开发，跳过 spec/req/plan）
```

复杂系统建议先走 x-spec，再进入 x-req/x-plan/x-dev；普通复杂功能可直接从 x-req 开始；x-qdev 适合小功能、bug 修复等快速场景。

## Skills 说明

### /x-spec — 系统方案规划

**触发词**：`x-spec <系统名称>`、"先做方案设计"、"帮我梳理整体方案"、"这个系统该怎么拆"

**做什么**：将模糊想法整理为系统方案导航 → 模块拆分 → task 映射，判断哪些模块可进入 `x-req`

**适用场景**：复杂系统、跨模块功能、架构级改造、需要先讨论完整方案再拆 task 的场景

**产出文件**：
- `docs/<system-name>/README.md` — 系统导航（已有同名目录则作为补充：`docs/<system-name>/spec-*.md`）
- `docs/<system-name>/02-模块拆分.md` — 模块职责与边界
- `docs/<system-name>/90-task-map.md` — 模块到 task 的映射
- 按需补充 `01-目标与边界.md`、`03-核心流程.md`、`04-数据与状态.md`、`05-验证与演进.md`

**目录查找逻辑**：先查 `docs/` 下有无同名目录，有则作为补充文档保存；无则询问用户是否创建独立目录

---

### /x-req — 需求分析

**触发词**：`x-req <功能描述>`、"帮我处理需求"、"梳理需求"、"需求分析"

**做什么**：理解需求 → 两步确认（理解确认 + 模块拆分确认）→ 输出完整需求报告到 `README.md`

**产出文件**：
- `.claude/tasks/<task-name>/README.md` — 完整需求报告 + 状态追踪

---

### /x-plan — 计划生成

**触发词**：`x-plan <功能名称>`

**做什么**：基于 `README.md` 中的需求报告制定开发策略 → 生成开发清单 → 确认优先级

**产出文件**：
- `.claude/tasks/<task-name>/plan.md` — 开发计划
- `.claude/tasks/<task-name>/开发清单.md` — 按优先级排列的任务表

**前置要求**：必须先有包含完整需求报告的 `README.md`

---

### /x-dev — 开发执行

**触发词**：`x-dev <功能名称>`

**做什么**：读取计划文件 → 按清单逐项开发 → 更新任务状态 → 记录变更

**产出文件**：
- `.claude/tasks/<task-name>/变更记录.md` — 关键变更记录
- 更新 `开发清单.md` 中的任务状态

**前置要求**：必须先有 `README.md` + `plan.md` + `开发清单.md`

---

### /x-qdev — 轻量级快速开发

**触发词**：`x-qdev <功能名称>`、"快速开发"、"小功能"

**做什么**：跳过 req/plan → 直接创建任务目录和清单 → 逐项开发 → 自带快速 review

**适用场景**：小功能、bug 修复、一两小时内能完成的改动

**产出文件**：
- `.claude/tasks/<task-name>/README.md` — 说明 + 开发清单
- `.claude/tasks/<task-name>/变更记录.md` — 变更记录

---

### /x-cr — 代码审查

**触发词**：`x-cr`、"代码审查"、"code review"、"帮我 review"

**做什么**：识别语言 → 执行通用检查（P0-P3）→ 加载语言专项配置 → 输出结构化报告

**支持语言专项配置**：
- TypeScript（`.ts`, `.tsx`）
- JavaScript（`.js`, `.jsx`）
- C#（`.cs`）

**产出文件**：
- `cr-report-YYYYMMDD-HHmmss.md` — 审查报告

**审查维度**：
| 等级 | 关注点 |
|------|--------|
| P0 | 功能正确性 / 致命缺陷 |
| P1 | 稳定性 / 安全性 / 数据风险 |
| P1.5 | 架构设计 / SOLID 原则 |
| P2 | 可维护性 / 可读性 / 测试质量 |
| P3 | 优化建议 / 边界增强 |

---

### /x-fix — 问题修复

**触发词**：`x-fix`、"修一下这个 bug"、"这个功能坏了"、"按 CR 报告修复"

**做什么**：分两种模式，互斥执行
- **用户直接报 bug**（无 CR 报告）：定位根因 → 修复 → 产出 `docs/fixes/<bug-name>/fix-report.md`
- **有 CR 报告**：定位报告 → 解析问题清单 → 逐条修复 → 更新报告状态

**产出文件**：
- `docs/fixes/<bug-name>/fix-report.md`（用户报 bug 模式）
- 更新 `cr-report-*.md` 状态（CR 报告模式）

## 目录结构

### 插件结构

```
~/.claude/plugins/x-dev-pipeline/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/
│   ├── x-spec/SKILL.md
│   ├── x-req/SKILL.md
│   ├── x-plan/SKILL.md
│   ├── x-dev/SKILL.md
│   ├── x-qdev/SKILL.md
│   ├── x-cr/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── lang-js.md
│   │       ├── lang-ts.md
│   │       └── lang-csharp.md
│   └── x-fix/
│       ├── SKILL.md
│       ├── references/
│       │   ├── bug-fix-mode.md
│       │   └── cr-fix-mode.md
│       └── templates/
│           └── fix-report-template.md
├── README.md
└── package.json
```

### 任务目录结构

每个功能的开发过程产生的文件统一放在：

```
.claude/tasks/<task-name>/
├── README.md      — 完整需求报告 + 状态追踪（x-req 创建）
├── plan.md        — 开发计划（x-plan 产出）
├── 开发清单.md     — 任务清单（x-plan 产出）
├── 变更记录.md     — 变更日志（x-dev 维护）
└── cr-report-*.md — 审查报告（x-cr 产出）
```

## 状态标记体系

所有 skill 共享统一的任务状态：

| 符号 | 状态 | 说明 |
|------|------|------|
| ⏳ | 未开始 | 等待处理 |
| ▶️ | 进行中 | 正在执行 |
| 🟡 | 待测试 | 开发完成，等待验证 |
| 🔴 | 测试失败 | 需要修复 |
| 🟢 | 测试通过 | 验证通过，等待 review 确认 |
| ✅ | 已完成 | review 确认后标记 |

## 优先级规范

| 优先级 | 说明 |
|--------|------|
| P0 | 阻塞性问题，必须立即处理 |
| P1 | 重要功能，必须完成 |
| P2 | 优化或增强，可后续处理 |

## 已知限制

- 语言专项配置目前仅覆盖 TypeScript、JavaScript、C#，其他语言（Python/Java/Go/Rust）仅执行通用检查
- x-dev 不会自动标记任务为"已完成"，需 review 确认后更新
- 任务目录固定在 `.claude/tasks/` 下，不支持自定义路径
