# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库性质

这不是应用代码仓库，而是一个 **AI 开发工作流 skill 集合**——为 Claude Code / Codex 提供 `/x-*` 系列 slash command 的 plugin。仓库本身**不包含可运行代码、没有 build、没有测试套件**，所有"产物"都是 markdown skill 文件。

**方案讲解要通俗**: 不要自己乱造词汇，用大白话和用户套路方案，用户偏好费曼学习法，要多使用。
⚠️ **命名陷阱**：仓库叫 `x-dev-pipeline`；仓库内部的 `dev-pipeline/tasks/` 保存历史 task
档案。当前 task 统一位于 `docs/spec/<spec-name>/tasks/<task-name>/`。

## 仓库布局

```
x-dev-pipeline/
├── skills/<name>/SKILL.md            # skill 定义（YAML frontmatter + 正文）
│   └── references/, templates/        # reviewer prompt、报告模板
├── docs/spec/<spec>/tasks/<task>/     # 当前 task 工件
│   ├── dev-checklist.md, diagram.md, dev-report.md
│   └── reports/                       # gate / fix / audit 报告
│       ├── .fix-counter               # 批量修轮数（verify 创建，fix 按轮递增，qa-gate 重置）
│       ├── verify/*.md, qa-gate/*.md  # Gate ①② 报告
│       ├── fix/*.md                   # 修复报告（按触发节点分类）
│       └── audit/*.md                 # 独立巡检报告
├── dev-pipeline/tasks/                # 历史 task 档案；工具不再识别、校验或编排
├── tools/xdev.py                      # 薄 CLI 路由器
├── tools/validator.py, flag.py        # 包校验与 QA issue 事务引擎
├── .claude-plugin/                    # Claude Code marketplace 注册
├── .codex-plugin/, .agents/           # Codex 注册
└── examples/, install.sh, install-codex.ps1
```

## 核心管线

```
x-spec ─→ x-adversarial-risk ─→ x-req ─→ x-dev ─→ x-verify ─→ x-qa-gate ─→ x-fix
(docs/spec/)   双评分+对抗 Scenario    (task/)       验证是否符合spec.md      批量修+增量复审
                                                   命令+smoke/e2e 风险路由：默认 RC 综合 / 高危 R1→R2→R3

```

- x-spec 产出 `docs/spec/<spec-name>/spec.md` 第一版，记录复杂度/重要性、预算和 `initial-spec` Scenario
- x-adversarial-risk 按预算检查第一版；standard 不读错题集，deep/full 才读取自身独立错题集并补 `adversarial-review` Scenario
- x-req 只接收风险状态为 `skipped-standard` 或 `complete` 的新风险契约，产出 `docs/spec/<spec-name>/tasks/<task>/`
- `tools/xdev.py` 只做 CLI 分流；package、task、verify、flag 逻辑分别归各自引擎
- x-plan 已废弃，功能合并到 x-req

独立巡检（不在主流程）：`x-audit-perf` / `x-audit-style` / `x-audit-arch`，由用户手动触发或里程碑后跑。`x-audit-arch` 聚焦架构一致性 + 单一事实源（结构性视角），与 `x-audit-style`（表层规范）、`x-qa-gate` R1（spec 正确性）不重叠，边界见 `skills/x-audit-arch/SKILL.md`。

## skill 间契约（改 skill 前必读）

| 契约 | 内容 |
|------|------|
| Spec 风险门禁 | x-spec 写 `adversarial_risk_version: 3`、复杂度/重要性/平均分/预算、`pending` 状态和 `initial-spec` 来源；x-adversarial-risk 完成对抗检查并写审查记录；x-req 复跑 `risk_contract.py validate-spec` 后才拆解 |
| 风险错题集边界 | `skills/x-adversarial-risk/references/risk-mistakes.md` 只由 x-adversarial-risk 在 deep/full 审查或录入已确认缺口时读取；每项使用唯一 `AR-NNN`，并只保存关键词与 Risk |
| spec 需求包目录 | x-spec 产出 `docs/spec/<spec-name>/`，`docs/spec/README.md` 汇总 spec 导航。x-req 的 README `spec:` 字段指向 `docs/spec/<spec-name>`，一个 task 只归属一个 spec |
| `dev-report.md` schema | x-dev 使用 `skills/x-dev/templates/dev-report-template.md`（含 `risk: default/high` 字段，Gate ② 路由依据）；x-verify 的必跑清单 = dev-report 命令表 + task README Smoke/E2E 用例（manual 用例列入待人工验收）；x-qdev 默认使用 `skills/x-qdev/templates/dev-report.md`，用户指定完整门禁时改用 x-dev schema |
| 测试分层契约 | x-spec 写验证策略；x-req README 显式列 smoke/e2e 验收用例；单元/契约/边界测试由 x-dev 按实际改动补齐，并写入 `dev-report.md` 验证命令清单 |
| `.fix-counter` 共享 | 路径 `dev-pipeline/tasks/<task>/reports/.fix-counter`。语义 = **批量修轮数**（一轮 = 一份 issue 清单的整体修复）。x-verify 首次创建，x-fix 按轮递增，x-qa-gate 在 Gate ② 最终 pass 后重置。**3 轮上限**，三方共享 |
| reviewer 子 agent | x-qa-gate 按 `risk:` 风险路由：默认线 dispatch 一个综合 reviewer RC（`references/rc-unified.md`），高危线串行 dispatch R1/R2/R3；初始 prompt 预算为 10,000 estimated tokens，使用 manifest + 路径 + diff 命令 + completeness gate |
| 一轮列全 | 所有 reviewer 穷尽列出全部问题候选后判定；每条返回 task、severity、loc、msg 和证据，并省略编号；回执包含覆盖声明、完整问题候选和穷尽声明；严重度 P0/P1/P2 唯一定义在 `skills/x-qa-gate/SKILL.md` |
| reviewer 只读 | RC/R1/R2/R3 只输出 review 回执；修改统一走 x-fix |
| issue 登记与状态写权 | 主 agent 逐条调用 `python3 tools/xdev.py flag ... --json`；本轮首条带 `--new-round`。代码分配 `issue-<n>`、写 ledger、把 P0/P1 task 降为 `[!] 🔴`；`recovered:true` 时主 agent 用原参数再次调用。reviewer、子 agent、x-fix 保持 ledger 与状态列原样 |
| x-fix 批量修 + 增量复审 | x-fix 一次修完一轮 issue 清单（P0 全修且各固化一条可复跑反例、P1 修或豁免、P2 登记），产出带 issue ID 的逐条处置表；复审尽量由同一个 reviewer 承接，只看 issue 处置 + fix 增量 diff，熔断条件见 `skills/x-qa-gate/SKILL.md` |
| 门禁回执 | x-verify / x-qa-gate / x-fix 每个节点结束在对话中输出统一回执（P0/P1/P2 计数 + 拦截来源维度 + 处置），零问题也输出；QA Gate issue ledger 由 flag 生成。格式见 `skills/x-qa-gate/SKILL.md`「回执与状态」 |
| x-cr 手动调查 | `skills/x-cr/SKILL.md` 是手动软件正确性调查入口，独立于自动门禁。先读取归属 spec 的“影响边界与不变量”，再登记遗漏候选并做贝叶斯根因调查；task 报告写入 `docs/spec/<spec>/tasks/<task>/reports/cr/`，普通调查写入 `reports/cr/`；x-fix 按稳定 Bn/INV-ID 消费 |
| 状态码 | ⏳ 未开始 / ▶️ 进行中 / 🟡 待验证 / 🔴 验证失败 / 🟢 证据通过 / ✅ 已完成 / ↗️ 已升级。x-dev 最多到 🟢，✅ 由完整 review 升级；x-qdev 按 Q0/Q1 主 agent 或 Q2 综合 reviewer 路线关闭，Q3 使用 ↗️ 并由 full task 负责最终完成 |

## 改 skill 时的注意事项

- **YAML frontmatter 是触发依据**：`description` 里的关键词决定 skill 何时被自动触发。改正文是低风险，**改 description 等于改触发面**——评估全局影响后再改。
- **report 路径不能乱**：每类 fail 写到固定子目录，旧链路（直接 bug fix）走 `reports/fix/fix-report-*.md` / `fix-note-*.md`，新链路（gate 回流）走 `fix-verify-*.md` / `fix-gate-r<轮次>-*.md`（批量修处置表）。两套路径**并存**，不要合并。
- **x-cr 报告交接**：task 内 CR 固定写到 `<task>/reports/cr/`，普通仓库 CR 写到仓库级 `reports/cr/`；`Schema: x-cr-v2`、`不变量覆盖`、`审查结论`、`问题详情` 及 Bn/INV-ID 映射是 x-fix 的消费契约，历史报告继续走兼容解析。
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

prompt 预算 10,000 estimated tokens。保留 reviewer 检查清单（默认线 `rc-unified.md` / 高危线 `r{N}-*.md`）、task root、必读文件路径、diff 命令、evidence 输出路径、`Context Completeness` 要求和一轮列全约束；完整 diff、源码、测试文件通过只读工具按需读取。复审轮追加：上轮带 issue ID 的 review 回执、x-fix 处置表、fix 增量 diff 命令，尽量由同一个 reviewer 承接（机制由执行时 LLM 按环境自行处理）。

## x-spec2 eval 计量边界

- `tools/metrics.py extract` 只读取调用方显式给出的完成态 Codex rollout JSONL，或主 agent 在子 agent 完成通知到达时保存的 `timing.json`；工具不扫描 session 目录。
- rollout 样本必须只有一个 session ID、一个 `turn_context` 和一个 `task_complete`。token 使用完成事件前最后一份 provider 累计快照，duration 使用 `turn_context` 到 `task_complete` 的时间差。
- 子 agent 通知源保留真实 `total_tokens` 与 `duration_ms`；细分 token、起止时间缺失时写 `null`。collector 和 grader 的 token、耗时不计入被测样本。
- executor inputs 与 grader-only inputs 必须在 metadata 中分开声明；重叠或 `rubric_exposed: true` 使样本退出 1。paired 聚合还要求 prompt hash、model、repo SHA 与评分断言完全一致。
- measurement 只保存 prompt 哈希，不复制 prompt、对话、工具参数或文件内容。退出码：0 成功，1 可读但无效的样本/配对，2 参数、IO、JSON 或 schema 错误。


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
