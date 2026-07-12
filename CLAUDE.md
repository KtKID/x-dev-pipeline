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
│   ├── README.md, changelog.md, dev-report.md              # qdev 轻量任务
│   ├── dev-checklist.md, diagram.md                        # 完整任务按需存在
│   └── reports/                       # gate 报告（全部在 task 目录下）
│       ├── .fix-counter               # 批量修轮数（verify 创建，fix 按轮递增，qa-gate 重置）
│       ├── verify/*.md, qa-gate/*.md  # Gate ①② 报告
│       ├── fix/*.md                   # 修复报告（按触发节点分类）
│       └── audit/*.md                 # 独立巡检报告
├── .claude-plugin/                    # Claude Code marketplace 注册
├── .codex-plugin/, .agents/           # Codex 注册
└── examples/, install.sh, install-codex.ps1
```

## 核心管线

```
x-spec ─→ x-req ─→ x-dev ─→ x-verify ─→ x-qa-gate ─→ x-fix
(docs/spec/) (task/)         Gate ①       Gate ②       批量修+增量复审
                             命令+smoke/e2e 风险路由：默认 RC 综合 / 高危 R1→R2→R3

x-qdev ─→ 定向验证 ─→ DoD 证据闭环 ─→ ✅
                         ├─ Q2：一个综合 reviewer
                         └─ Q3：升级 x-req → x-dev 完整流程
```

- x-spec 产出 `docs/spec/<spec-name>/` 独立需求包，`docs/spec/README.md` 做索引，迭代原地更新
- x-req 产出 `dev-pipeline/tasks/<task>/`（README 含 `spec:` 字段指向归属 spec，一步到位）
- x-plan 已废弃，功能合并到 x-req

独立巡检（不在主流程）：`x-audit-perf` / `x-audit-style` / `x-audit-arch`，由用户手动触发或里程碑后跑。`x-audit-arch` 聚焦架构一致性 + 单一事实源（结构性视角），与 `x-audit-style`（表层规范）、`x-qa-gate` R1（spec 正确性）不重叠，边界见 `skills/x-audit-arch/SKILL.md`。

## skill 间契约（改 skill 前必读）

| 契约 | 内容 |
|------|------|
| spec 需求包目录 | x-spec 产出 `docs/spec/<spec-name>/`，`docs/spec/README.md` 汇总 spec 导航，spec 目录含 7 文件。x-req 的 README `spec:` 字段指向 `docs/spec/<spec-name>`，一个 task 只归属一个 spec |
| `dev-report.md` schema | x-dev 使用 `skills/x-dev/templates/dev-report-template.md`（含 `risk: default/high` 字段，Gate ② 路由依据）；x-verify 的必跑清单 = dev-report 命令表 + task README Smoke/E2E 用例（manual 用例列入待人工验收）；x-qdev 默认使用 `skills/x-qdev/templates/dev-report.md`，用户指定完整门禁时改用 x-dev schema |
| 测试分层契约 | x-spec 写验证策略；x-req README 显式列 smoke/e2e 验收用例；单元/契约/边界测试由 x-dev 按实际改动补齐，并写入 `dev-report.md` 验证命令清单 |
| `.fix-counter` 共享 | 路径 `dev-pipeline/tasks/<task>/reports/.fix-counter`。语义 = **批量修轮数**（一轮 = 一份发现清单的整体修复）。x-verify 首次创建，x-fix 按轮递增，x-qa-gate 在 Gate ② 最终 pass 后重置。**3 轮上限**，三方共享 |
| reviewer 子 agent | x-qa-gate 按 `risk:` 风险路由：默认线 dispatch 一个综合 reviewer RC（`references/rc-unified.md`），高危线串行 dispatch R1/R2/R3；初始 prompt 预算为 10,000 estimated tokens，使用 manifest + 路径 + diff 命令 + completeness gate；mini-report 填写 `Completed by model` |
| 一轮列全 | 所有 reviewer 必须穷尽列出全部发现（F1..Fn 编号）后才判定，禁止发现一个就交卷；mini-report 必含覆盖声明 + 发现清单 + 穷尽声明；严重度 P0/P1/P2 唯一定义在 `skills/x-qa-gate/SKILL.md` |
| reviewer 不写代码 | RC/R1/R2/R3 只输出 mini-report，禁用 Edit/Write；修改一律走 x-fix |
| x-fix 批量修 + 增量复审 | x-fix 一次修完一轮发现清单（P0 全修且各固化一条可复跑反例、P1 修或豁免、P2 登记），产出逐条处置表；复审尽量由同一个 reviewer 承接、只看 F# 处置 + fix 增量 diff，熔断条件见 `skills/x-qa-gate/SKILL.md`。旧"回 R1"4 条规则已废除 |
| 门禁回执 | x-verify / x-qa-gate / x-fix 每个节点结束必须在对话中输出统一回执（P0/P1/P2 计数 + 拦截来源维度 + 处置），零发现也要报；报告文件只做存档。格式见 `skills/x-qa-gate/SKILL.md`「门禁回执」 |
| x-cr 手动调查 | `skills/x-cr/SKILL.md` 是手动软件正确性调查入口，独立于自动门禁；流水线 gate 逻辑写到 x-qa-gate |
| 状态码 | ⏳ 未开始 / ▶️ 进行中 / 🟡 待验证 / 🔴 验证失败 / 🟢 证据通过 / ✅ 已完成 / ↗️ 已升级。x-dev 最多到 🟢，✅ 由完整 review 升级；x-qdev 按 Q0/Q1 主 agent 或 Q2 综合 reviewer 路线关闭，Q3 使用 ↗️ 并由 full task 负责最终完成 |

## 改 skill 时的注意事项

- **YAML frontmatter 是触发依据**：`description` 里的关键词决定 skill 何时被自动触发。改正文是低风险，**改 description 等于改触发面**——评估全局影响后再改。
- **report 路径不能乱**：每类 fail 写到固定子目录，旧链路（直接 bug fix）走 `reports/fix/fix-report-*.md` / `fix-note-*.md`，新链路（gate 回流）走 `fix-verify-*.md` / `fix-gate-r<轮次>-*.md`（批量修处置表）。两套路径**并存**，不要合并。
- **manifest 不显式列 skill**：`.claude-plugin/plugin.json` / `.codex-plugin/plugin.json` 都靠 `./skills/` 目录自动发现，新增 skill 不必改 manifest 字段，除非要更新 `defaultPrompt` 示例。
- **reference 文件保留制**：`skills/x-cr/references/auto-loop-mode.md` 之类的旧 reference **保留**作历史参考，不要删；新逻辑放到 x-qa-gate / x-fix 的 references。

## 子 agent dispatch 模板（reviewer 用）

```
Agent({
  description: "<RC/R1/R2/R3> review round <N>",
  subagent_type: "general-purpose",
  prompt: <reviewer checklist + task manifest + required paths + diff commands + evidence path + context completeness gate + 一轮列全约束 + output format>
})
```

prompt 预算 10,000 estimated tokens。保留 reviewer 检查清单（默认线 `rc-unified.md` / 高危线 `r{N}-*.md`）、task root、必读文件路径、diff 命令、evidence 输出路径、`Context Completeness` 要求和一轮列全约束；完整 diff、源码、测试文件通过只读工具按需读取。复审轮追加：上轮 mini-report、x-fix 处置表、fix 增量 diff 命令，尽量由同一个 reviewer 承接（机制由执行时 LLM 按环境自行处理）。

x-qdev 的 Q2 只派一个综合 reviewer，输入锚定已脱敏的用户原始请求、明示假设、DoD 证据矩阵、diff 命令和相关实现/测试路径。Q0/Q1 由主 agent 完成，Q3 升级完整流程。

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

`dev-pipeline/tasks/qa-gate-pipeline/` 是当前主线改造任务（v0.2 双层 gate 架构）：把老 `x-cr` 单层闭环升级为 `x-verify` (事实) + `x-qa-gate` (R1/R2/R3 评审) 双层 gate，并把 perf/style 剥离成独立 audit。代码改动已落地，**待用户在新会话跑完 5 个 e2e smoke case 才能升 ✅**。看 `dev-pipeline/tasks/qa-gate-pipeline/changelog.md` 了解最新决策。
