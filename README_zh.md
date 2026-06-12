<p align="center">
  <img src="assets/pic.png" alt="x-dev-pipeline" />
</p>

# x-dev-pipeline

**当前版本：** v0.2.0

> 给 AI 辅助开发一套可记录、可审计、可回顾的工作流框架。

很多时候，AI coding agent 能写出代码，但执行中容易跑偏，做完以后也容易缺少足够清晰的过程信息：

- 为什么这样改
- 改了哪些地方
- 中间做过哪些决策
- 哪些问题已经处理过
- 哪些风险还没有解决

下一次继续接手时，往往只能重新问、重新看、重新梳理。

`x-dev-pipeline` 想解决的，就是这个问题。

它把一次性的对话式开发，变成一套更像工程的过程：先把事情做出来，再把过程留下来，最后还能继续 review、继续修、继续复盘。

> 当前已在 Claude Code 上深度验证，并随仓库提供 Claude Code 与 Codex 插件 manifest。

## 第一次使用，建议先从 `/x-qdev` 开始

如果你是第一次体验这个仓库，建议先走轻量入口。

先试一次 `/x-qdev`：

```bash
/x-qdev 给设置页增加深色模式切换
```

它最适合这些场景：

- 给页面补一个小功能
- 做一次局部优化
- 修改一个小模块
- 补一个交互细节
- 做一个轻量级需求验证

这时候你得到一套更接近真实开发的过程：

1. AI 理解任务范围
2. 创建任务目录
3. 生成任务说明和开发清单
4. 逐项实现并记录关键修改
5. 为后续 review 和 fix 留下可继续使用的产物

典型产物会像这样：

```text
dev-pipeline/tasks/<task-name>/
├── README.md
├── changelog.md
├── dev-report.md
└── reports/
    ├── verify/verify-report-*.md
    ├── qa-gate/qa-gate-report-*.md
    ├── fix/fix-verify-*.md
    ├── fix/fix-r1-spec-*.md
    ├── fix/fix-r2-boundary-*.md
    └── fix/fix-r3-test-*.md
```

这也是 `x-dev-pipeline` 最适合第一次体验的地方：

**先把一个小功能顺利做完，同时把开发过程留痕。**

## 重点是开发稳定性

很多人直接用 AI coding agent 开发时，容易遇到这些问题：

- 需求不大，但过程很乱
- 改动做完了，没有留下清晰记录
- review 靠临场发挥，质量不稳定
- 改完就结束，没有形成修复闭环
- 后续接手时，很难快速知道前面发生过什么

`x-dev-pipeline` 给 AI coding 工作一套更稳定、更可追踪、更像工程的节奏：

**怎么让 AI 按一个更稳定、更可追踪、更像工程的节奏做事。**

## 默认推荐闭环：先做，再审，再修

日常开发里，我最推荐这条路径：

```text
/x-qdev -> /x-verify -> /x-qa-gate -> /x-fix
```

### `/x-qdev`

适合先把一个小功能、小改动、小模块快速落地。

### `/x-verify`

Gate ① 事实验证。读 `dev-report.md` 中的命令清单，复跑后比对 exit code 与关键输出，**只做事实验证**。

### `/x-qa-gate`

Gate ② 质量评审（取代老 `/x-cr`）。串行 dispatch 3 个 opus 子 agent reviewer：R1 spec 符合性 → R2 边界完整性 → R3 测试真实性。

### `/x-fix`

根据 verify / qa-gate 报告继续修复，让评审真正形成闭环；按 4 条回流规则决定回到哪个节点重审。

这条路径特别适合：

- 小功能迭代
- 页面交互补充
- 模块微调
- 局部优化
- 小范围重构

它的重点是让小任务也能拥有工程感。

## 你会得到什么

使用 `x-dev-pipeline`，你得到一组可以继续使用、继续追踪、继续回顾的产物。

典型情况下，你会得到这些内容：

- 任务目录
- 任务说明
- 开发清单
- 变更记录
- 代码审查报告
- 修复报告或轻量修补单

这些产物的意义在于：

- 有记录：知道改了什么
- 可审计：知道为什么这样改
- 可回顾：下次还能接着做
- 可复盘：能回头看决策和问题

这也是这个仓库最核心的价值之一：

**把事情做完，也把开发过程沉淀成真正可追踪的工程资产。**

## 当任务更复杂时，再进入完整链路

`x-dev-pipeline` 同时包含 `/x-qdev` 和完整 spec-to-gate 链路。

对于更复杂的任务，它提供完整开发流程：

```text
x-spec -> x-req -> x-dev -> x-verify -> x-qa-gate -> x-fix
                 ^
              x-qdev
```

独立巡检按需触发，位于主流程之外：

- `/x-audit-perf` 性能巡检（手动 / 大里程碑）
- `/x-audit-style` 规范巡检（手动 / 周期）

你可以这样理解：

### 小任务

直接从 `/x-qdev` 开始，适合快速完成、快速落地。

### 中等任务

从 `/x-req -> /x-dev` 开始，适合需要明确需求和执行计划的开发任务。

### 大任务

走完整链路，适合系统设计、复杂模块、架构级调整。

推荐形态：

- 小事先轻
- 大事再稳
- 收尾一定 review 和 fix

## 各命令分别做什么

### `/x-qdev`

轻量级快速开发入口。适合小功能、局部优化、模块微调，是最推荐的第一次使用方式。

### `/x-verify`

Gate ① 事实验证。读 `dev-pipeline/tasks/<task>/dev-report.md` 中声明的验证命令清单，逐条复跑，对比实际 exit code 与关键输出片段。任一不一致即生成 `reports/verify/verify-report-*.md` 并触发 x-fix。

### `/x-qa-gate`

Gate ② 质量评审（取代老 `/x-cr`）。串行 dispatch 3 个 opus 子 agent reviewer：R1 spec 符合性 → R2 边界完整性 → R3 测试真实性。聚合报告写到 `reports/qa-gate/qa-gate-report-*.md`。

### `/x-cr`（已废弃）

> ⚠️ 自 qa-gate-pipeline 改造起，本 skill 已被 `/x-qa-gate` 取代。调用会自动重定向。详见 `skills/x-cr/SKILL.md` stub。

### `/x-fix`

按 verify / qa-gate / 老 CR 报告修复。在新链路下，按 4 条回流规则决定 fix 完后回到哪个节点重审；fix-attempts 与 verify/qa-gate 共享 6 次上限。

### `/x-audit-perf`（独立巡检）

性能巡检 skill，位于主流程之外。手动或大里程碑触发，输出 `reports/audit/audit-perf-*.md`。

### `/x-audit-style`（独立巡检）

代码规范巡检 skill，位于主流程之外。手动或周期触发，输出 `reports/audit/audit-style-*.md`。

### `/x-req`

需求分析。把一个开发任务整理成更清晰的需求说明。

### `/x-plan`（兼容入口）

已废弃别名，调用会重定向到 `/x-req`。原计划产物现在位于 x-req task README、`dev-checklist.md` 和 `diagram.html`。

### `/x-dev`

按计划执行开发。让开发过程有清单、有状态、有记录。

### `/x-spec`

系统方案规划。适合更大的项目、复杂模块、架构设计或长期演进任务。

## 安装

这个仓库随 v0.2.0 提供两套 host 的插件元数据：

```text
.claude-plugin/plugin.json          # Claude Code 插件 manifest
.claude-plugin/marketplace.json     # Claude Code 本地 marketplace
.codex-plugin/plugin.json           # Codex 插件 manifest
.agents/plugins/marketplace.json    # Codex repo 级 marketplace
```

### 一键安装（推荐）

从 GitHub `main` 分支安装 Claude Code 插件：

```bash
curl -fsSL https://raw.githubusercontent.com/KtKID/x-dev-pipeline/main/install.sh | bash
```

### Claude Code（手动）

```bash
git clone https://github.com/KtKID/x-dev-pipeline.git ~/.claude/plugins/x-dev-pipeline
```

注册本地 marketplace：

```bash
cd ~/.claude/plugins/x-dev-pipeline
claude plugin marketplace add ./.claude-plugin/marketplace.json
```

安装插件：

```bash
claude plugin install x-dev-pipeline@x-dev-pipeline --scope user
```

### Codex

这个仓库现在自带 repo 级 Codex marketplace：`.agents/plugins/marketplace.json`，同时提供 Codex 插件 manifest：`.codex-plugin/plugin.json`。

直接在 Codex 里打开这个仓库，Local 就可以从工作区发现 `x-dev-pipeline`。

克隆到本地插件目录：

```bash
mkdir -p ~/.codex/plugins
git clone https://github.com/KtKID/x-dev-pipeline.git ~/.codex/plugins/x-dev-pipeline
```

Windows 环境可以直接运行下面的脚本，把当前 checkout 同步到 Codex，并刷新用户级 marketplace：

```powershell
./install-codex.ps1
```

目录关系如下：

```text
~/
├── .agents/
│   └── plugins/
│       └── marketplace.json
└── .codex/
    └── plugins/
        └── x-dev-pipeline/
```

Codex 本地插件安装方式是：先维护 `~/.agents/plugins/marketplace.json`，再通过交互式插件目录安装：

```bash
codex
/plugins
```

手动 marketplace 条目：

```json
{
  "name": "local-plugins",
  "interface": {
    "displayName": "Local Plugins"
  },
  "plugins": [
    {
      "name": "x-dev-pipeline",
      "source": {
        "source": "local",
        "path": "./.codex/plugins/x-dev-pipeline"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

参考示例：

```text
examples/codex-marketplace.json
```

这个仓库里的 repo 级 marketplace 使用 `../..`，这样 Codex 可以从 `.agents/plugins/marketplace.json` 解析回插件根目录。

路径规则：

- `source.path` 是相对 `~/.agents/plugins/marketplace.json` 所在根目录解析的
- 对个人 marketplace，官方文档里的常见写法就是 `./.codex/plugins/<plugin-name>`

如果你已经有 `~/.agents/plugins/marketplace.json`，把上面的 `plugins` 条目追加进去并保留已有插件。保存后重启 Codex，然后运行：

```bash
codex
/plugins
```

在插件目录里找到 `x-dev-pipeline` 并安装即可。(可能需要切换本地)

安装完成后，第一次体验建议直接试：

```bash
/x-qdev 给设置页增加深色模式切换
```

## 适合谁

这个仓库特别适合：

- 用 AI coding agent 做日常开发，希望过程更规范的人
- 希望 AI 开发更像工程化协作的人
- 想让每次改动都留下清晰记录的人
- 希望 review 和 fix 形成闭环的人
- 想逐步建立稳定开发节奏的人

## 当前适配边界

这个仓库当前适合接受轻量工作流层的团队和个人。下面这些需求更适合使用其他工具：

- 完全零配置、开箱即用的通用代码助手
- 非常重的企业流程管理平台

## 适配其他开发工具

`x-dev-pipeline` 的工作流设计可以跨 AI coding 工具使用。Claude Code 是当前验证最深的 host，核心理念适用于所有 AI coding agent：

- 小任务应该快速落地
- 每次改动都应该有记录
- 每一步决策都应该能追溯
- review 应该留下书面报告
- 修复应该形成闭环

如果你使用的是其他工具（Cursor、Codex、Windsurf、Cline 等），可以直接告诉 AI：

> "在保持 x-dev-pipeline 工作流不变的情况下，帮我适配到 Cursor（或你使用的工具）。"

AI 会根据目标工具的目录结构和交互方式，自动调整任务目录位置和触发方式，同时保留完整的工作流链路。

> **提示**：当前 skill 中的任务产出目录默认是 `dev-pipeline/tasks/`。适配时 AI 可能会询问你是否要更改为其他路径（如 `.codex/tasks/`），根据你的实际情况确认即可。

## 统一状态标记

所有 skill 共享一套任务状态体系：

| 符号 | 状态 | 说明 |
|------|------|------|
| ⏳ | 未开始 | 等待处理 |
| ▶️ | 进行中 | 正在执行 |
| 🟡 | 待测试 | 开发完成，等待验证 |
| 🔴 | 测试失败 | 需要修复 |
| 🟢 | 测试通过 | 验证通过，等待 review 确认 |
| ✅ | 已完成 | review 确认后标记 |

### 优先级

| 优先级 | 说明 |
|--------|------|
| P0 | 阻塞性问题，必须立即处理 |
| P1 | 重要功能，必须完成 |
| P2 | 优化或增强，可后续处理 |

## 这个仓库的核心理念

目标是让开发：

**复杂工作有结构，简单任务保持轻。**

你可以把它当成一套按任务复杂度自由选择的工作流工具链。

## 路线图

接下来会继续强化这些方向：

- 更丝滑的 `/x-qdev` 首次体验
- 更清晰的任务产物结构
- 更强的 review / fix 闭环
- 更贴近真实项目的使用示例
- 更好的多语言、多技术栈支持
- 更完善的 Claude Code 和 Codex 适配体验
- 更多开发工具的官方适配（Cursor、Windsurf 等）

## License

MIT
