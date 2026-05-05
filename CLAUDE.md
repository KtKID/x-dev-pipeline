# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库性质

这不是应用代码仓库，而是一个 **AI 开发工作流 skill 集合**——为 Claude Code / Codex 提供 `/x-*` 系列 slash command 的 plugin。仓库本身**不包含可运行代码、没有 build、没有测试套件**，所有"产物"都是 markdown skill 文件。

⚠️ **命名陷阱**：仓库叫 `x-dev-pipeline`，仓库内部有一个子目录叫 `dev-pipeline/`（无 `x-` 前缀），它是 task 工件的输出目录。两者不是同一个东西。

## 仓库布局

```
x-dev-pipeline/
├── skills/<name>/SKILL.md            # skill 定义（YAML frontmatter + 正文）
│   └── references/, templates/        # reviewer prompt、报告模板
├── dev-pipeline/tasks/<task>/         # 用 skill 时产出的 task 工件
│   ├── README.md, plan.md, dev-checklist.md, changelog.md, dev-report.md
│   └── reports/{verify,qa-gate,fix,audit}/  # 各 gate 的报告 + .fix-counter
├── .claude-plugin/                    # Claude Code marketplace 注册
├── .codex-plugin/, .agents/           # Codex 注册
└── examples/, install.sh, install-codex.ps1
```

## 核心管线

```
x-spec ─→ x-req ─→ x-dev ──┐
(docs/)    (task/)    ↑     │
                   x-qdev ──┤      (轻量入口，自包含)
                            ↓
                       x-verify (Gate ① 命令复跑)
                            ↓
                       x-qua-gate (Gate ② R1→R2→R3 串行 opus 子 agent)
                            ↓ fail
                          x-fix ──→ 按 4 条规则回流到对应节点
```

- x-spec 产出 `docs/<system>/`（模块级文档包，独立可传递）
- x-req 产出 `dev-pipeline/tasks/<task>/`（README + dev-checklist + diagram.html，一步到位）
- x-plan 已废弃，功能合并到 x-req

独立巡检（不在主流程）：`x-audit-perf` / `x-audit-style`，由用户手动触发或里程碑后跑。

## skill 间契约（改 skill 前必读）

| 契约 | 内容 |
|------|------|
| `dev-report.md` schema | x-dev/x-qdev 输出，是 x-verify 的**唯一输入**。必须含验证命令清单（至少 1 条测试类）+ 改动文件清单 + 自检结论。模板：`skills/x-dev/templates/dev-report-template.md` |
| `.fix-counter` 共享 | 路径 `dev-pipeline/tasks/<task>/reports/.fix-counter`。x-verify 首次创建，x-fix 递增，x-qua-gate 在 R3 通过后重置。**6 次上限**，三方共享 |
| reviewer 必须 opus | x-qua-gate 通过 Agent 工具 dispatch R1/R2/R3，**必须传 `model="opus"`**；prompt 必须自包含（fresh subagent 看不到主对话） |
| reviewer 不写代码 | R1/R2/R3 只输出 mini-report，禁用 Edit/Write；修改一律走 x-fix |
| x-fix 回流 4 条规则 | 改函数签名/公开 API → R1；改业务核心 → R1；只改测试/配置/文档 → 当前节点；不确定 → R1。详见 `skills/x-fix/SKILL.md` |
| x-cr 已废弃 | `skills/x-cr/SKILL.md` 仅保留为重定向 stub。**不要往里加新逻辑**，新逻辑写到 x-qua-gate |
| 状态码 | ⏳ 未开始 / ▶️ 进行中 / 🟡 待测试 / 🔴 测试失败 / 🟢 测试通过 / ✅ 已完成。x-dev 最多到 🟢，✅ 由 review 通过后升级 |

## 改 skill 时的注意事项

- **YAML frontmatter 是触发依据**：`description` 里的关键词决定 skill 何时被自动触发。改正文是低风险，**改 description 等于改触发面**——评估全局影响后再改。
- **report 路径不能乱**：每类 fail 写到固定子目录，旧链路（直接 bug fix）走 `reports/fix/fix-report-*.md` / `fix-note-*.md`，新链路（gate 回流）走 `fix-{verify,r1-spec,r2-boundary,r3-test}-*.md`。两套路径**并存**，不要合并。
- **manifest 不显式列 skill**：`.claude-plugin/plugin.json` / `.codex-plugin/plugin.json` 都靠 `./skills/` 目录自动发现，新增 skill 不必改 manifest 字段，除非要更新 `defaultPrompt` 示例。
- **reference 文件保留制**：`skills/x-cr/references/auto-loop-mode.md` 之类的旧 reference **保留**作历史参考，不要删；新逻辑放到 x-qua-gate / x-fix 的 references。

## 子 agent dispatch 模板（reviewer 用）

```
Agent({
  description: "<R1/R2/R3> <name>",
  subagent_type: "general-purpose",
  model: "opus",
  prompt: <references/r{N}-*.md 全文 + task 上下文 + git diff，全部塞进 prompt>
})
```

prompt 自包含三件事：reviewer 检查清单、当前 task 的 README/plan/checklist 全文、git diff 输出。

## 常用维护操作

```bash
# 看仓库结构总览
grep -n "^## " skills/*/SKILL.md

# 列已有 task
ls dev-pipeline/tasks/

# 安装到本地 Claude Code 做联调
claude plugin install x-dev-pipeline@x-dev-pipeline --scope user

# 同步当前改动到 Codex（macOS/Linux 自行 git pull；Windows 用脚本）
./install-codex.ps1
```

仓库本身没有 lint / test / build——所有"质量"靠 skill 文档之间的契约 + 用户跑 `_e2e-smoke/` 五个用例做端到端验收。

## 用户当前正在做的改造

`dev-pipeline/tasks/qa-gate-pipeline/` 是当前主线改造任务（v0.2 双层 gate 架构）：把老 `x-cr` 单层闭环升级为 `x-verify` (事实) + `x-qua-gate` (R1/R2/R3 评审) 双层 gate，并把 perf/style 剥离成独立 audit。代码改动已落地，**待用户在新会话跑完 5 个 e2e smoke case 才能升 ✅**。看 `dev-pipeline/tasks/qa-gate-pipeline/changelog.md` 了解最新决策。
