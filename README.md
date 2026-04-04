# x-dev-pipeline

> Version: 0.1.0

Claude Code 开发工作流插件。提供结构化的需求分析、计划生成、开发执行、代码审查、问题修复完整链路，以及轻量级快速开发入口。

## 安装

### 方式一：从 GitHub 安装（推荐）

```bash
git clone https://github.com/KtKID/x-dev-pipeline.git ~/.claude/plugins/x-dev-pipeline
```

### 方式二：本地 Marketplace

```bash
claude plugin marketplace add ~/.claude/plugins/x-dev-pipeline/.claude-plugin/marketplace.json
claude plugin install x-dev-pipeline@x-local --scope user
```

## 工作流总览

```
x-req（需求分析）→ x-plan（计划生成）→ x-dev（开发执行）→ x-cr（代码审查）→ x-fix（问题修复）
                                          ↑
                                     x-qdev（快速开发，跳过 req/plan）
```

完整流程适合复杂功能开发；x-qdev 适合小功能、bug 修复等快速场景。

## Skills 说明

### /x-req — 需求分析

**触发词**：`x-req <功能描述>`、"帮我处理需求"、"梳理需求"、"需求分析"

**做什么**：理解需求 → 两步确认（理解确认 + 模块拆分确认）→ 输出 `req.md`

**产出文件**：
- `.claude/tasks/<task-name>/README.md` — 任务摘要
- `.claude/tasks/<task-name>/req.md` — 需求分析结果

---

### /x-plan — 计划生成

**触发词**：`x-plan <功能名称>`

**做什么**：基于 `req.md` 制定开发策略 → 生成开发清单 → 确认优先级

**产出文件**：
- `.claude/tasks/<task-name>/plan.md` — 开发计划
- `.claude/tasks/<task-name>/开发清单.md` — 按优先级排列的任务表

**前置要求**：必须先有 `req.md`

---

### /x-dev — 开发执行

**触发词**：`x-dev <功能名称>`

**做什么**：读取计划文件 → 按清单逐项开发 → 更新任务状态 → 记录变更

**产出文件**：
- `.claude/tasks/<task-name>/变更记录.md` — 关键变更记录
- 更新 `开发清单.md` 中的任务状态

**前置要求**：必须先有 `req.md` + `plan.md` + `开发清单.md`

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

### /x-fix — CR 报告修复

**触发词**：`x-fix`、"按 CR 报告修复"、"修一下 CR 的问题"、"fix the CR issues"

**做什么**：定位 CR 报告 → 解析问题清单 → 逐条判断并修复 → 更新报告状态

**前置要求**：必须先有 x-cr 生成的 `cr-report-*.md`

**处理规则**：
- P0/P1/P1.5/P2：必须处理
- P3：默认跳过，除非用户指定

## 目录结构

### 插件结构

```
~/.claude/plugins/x-dev-pipeline/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/
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
│   └── x-fix/SKILL.md
├── README.md
└── package.json
```

### 任务目录结构

每个功能的开发过程产生的文件统一放在：

```
.claude/tasks/<task-name>/
├── README.md      — 任务摘要（x-req 创建）
├── req.md         — 需求分析（x-req 产出）
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
