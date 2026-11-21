# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库性质

这是一个 **AI 开发工作流 skill 集合**，为 Claude Code / Codex 提供 `/x-*` 系列命令，并维护 Python/Go 确定性工具及相应测试。

**方案讲解要通俗**: 不要自己乱造词汇，用大白话和用户套路方案，用户偏好费曼学习法，要多使用。
⚠️ **命名陷阱**：仓库叫 `x-dev-pipeline`；仓库内部的 `dev-pipeline/tasks/` 保存历史 task
档案。当前 task 统一位于 `docs/spec/<spec-name>/tasks/<task-name>/`。

## 仓库布局

```
x-dev-pipeline/
├── skills/<name>/SKILL.md            # skill 定义（YAML frontmatter + 正文）
│   └── references/, templates/        # reviewer prompt、报告模板
├── docs/spec/<spec>/tasks/<task>/     # 当前 task 工件
│   ├── dev-checklist.md, dev-report.md   # diagram.md 只在旧 spec_version: 3 包里有
│   └── reports/                       # gate / fix / audit 报告
│       ├── .fix-counter               # 批量修轮数（x-fix 按轮递增，不存在视为 0；Q2/Q3 由 x-qa-gate、Q0/Q1 由主 agent 在最终通过后重置）
│       ├── qa-gate/*.md               # 质量审查 issue ledger（flag 生成）；verify/*.md 只在旧包里有
│       ├── fix/*.md                   # 修复报告（按触发节点分类）
│       └── audit/*.md                 # 独立巡检报告
├── reports/<task-name>/<batch-id>/   # 当次代码基线的统一测试产物
│   ├── test-report.md                # 用例明细、改动覆盖率、未覆盖位置与验收结论
│   └── evidence/                    # 集中执行记录、原始覆盖数据与专项附件
├── dev-pipeline/tasks/                # 历史 task 档案；工具不再识别、校验或编排
├── skills/x-dev/scripts/xdev.py       # 薄 CLI 路由器
├── skills/x-spec/scripts/             # spec 与包校验引擎
├── skills/x-req/scripts/              # task 引擎：checklist_engine.py（当前格式）、req.py（旧 v3 包）
├── skills/x-verify-spec/scripts/           # Gate ① 引擎
├── skills/x-qa-gate/scripts/          # QA issue 事务引擎
├── .claude-plugin/                    # Claude Code marketplace 注册
├── .codex-plugin/, .agents/           # Codex 注册
└── examples/, install.sh, install-codex.ps1
```

## 核心管线

```
x-explore-for-spec → x-tech-design → x-req → x-dev → x-verify-spec → x-qa-gate
探索与增量 spec        技术设计        task     实现      交付对账         质量审查
需求风险复核按需调用 x-adversarial-risk；技术验收调用 x-verify-tech；问题修复交 x-fix。

```

- x-explore-for-spec 合并原 x-explore 与 x-spec：每次核对目标、现状、范围、约束与验收，逐批把已确认且有价值的结论写入所属 spec（归属见 `skills/x-explore-for-spec/references/spec-scope.md`），已有明确答案直接采用。
- x-tech-design 与 x-req 只承接本轮选中的已确认场景，该 spec 其他计划项保持原状态；一个 feat 可以分批交付，3 feat / 10 场景是单轮审阅建议。
- x-adversarial-risk 按适用预算复核需求；带风险版本标记的旧契约沿用相应风险门禁。
- `skills/x-dev/scripts/xdev.py` 只做 CLI 分流：当前格式 task 的 scaffold/validate/status/graph/impact/baseline 归 `skills/x-req/scripts/checklist_engine.py`；声明 `spec_version: 3` 的旧包归 req.py / validator.py / verify.py；flag 归 x-qa-gate。`cli/` 下的 Go 版本保留不删：计划以后做成“agent 调一个命令就能初始化这套管线、安装必需 skill”的工具，目前暂停维护，行为停在旧引擎，skill 不调用它
- x-req 给任务行分并行组和依赖；并行组 ≥2 时 x-dev 按 `skills/x-dev/references/parallel-dev.md` 派给工人子 agent，另派验收 agent，主 agent 按依赖顺序合并
- x-plan 已废弃，功能合并到 x-req
- 当前需求模板位于 `skills/x-explore-for-spec/templates/spec.md`。`skills/x-spec/scripts/` 保留给现有 CLI 和历史 v3 契约使用。

独立巡检（不在主流程）：`x-audit-perf` / `x-audit-style` / `x-audit-arch`，由用户手动触发或里程碑后跑。`x-audit-arch` 聚焦架构一致性 + 单一事实源（结构性视角），与 `x-audit-style`（表层规范）、`x-qa-gate` 的 q1-intent（spec 正确性）不重叠，边界见 `skills/x-audit-arch/SKILL.md`。

## skill 间契约（改 skill 前必读）

| 契约 | 内容 |
|------|------|
| Spec 风险门禁 | 带 `adversarial_risk_version: 3` 的旧契约继续保留分数、预算、审查状态和来源；x-adversarial-risk 更新审查记录，x-req 按对应风险门禁核对。当前 spec 由 x-explore-for-spec 增量维护 |
| 风险错题集边界 | `skills/x-adversarial-risk/references/risk-mistakes.md` 只由 x-adversarial-risk 在 deep/full 审查或录入已确认缺口时读取；每项使用唯一 `AR-NNN`，并只保存关键词与 Risk |
| spec 需求包目录 | 一份 spec 管一块数据，长期维护在 `docs/spec/<spec名>/spec.md`，划分规则见 `skills/x-explore-for-spec/references/spec-scope.md`。x-explore-for-spec 局部更新已确认行为，保留稳定编号、有效历史内容及关键约束；本轮场景、待开发 feat 和待决项分别表达。task 归属主场景所在的 spec（规则同见 spec-scope），本轮承接范围单独记录 |
| 交付记录与核查 | x-dev 的 dev-report 与 x-qdev 的⑤保存交付摘要、状态及唯一测试报告入口；当次代码基线的用例明细、改动行/相关分支覆盖率、未覆盖位置和验收结论统一维护在 `reports/<task-name>/<batch-id>/test-report.md`，原始证据集中放同目录 `evidence/`。共用约定与模板位于 `skills/x-dev/references/test-reporting.md`、`skills/x-dev/templates/test-report.md`。两类 verify/QA 返回增量回执，由主 agent 收录；技术验收的独立执行按编号区分。qdev 保持五段 task，功能正文和 changelog 归属 spec/模块说明，双向回链与新增/修改/删除及用例责任继续核对。task 建在主场景所属 spec 的 `tasks/` 下，归属判断见 spec-scope；task 头部填写所属 spec、状态、执行者、创建四行 |
| qdev 执行授权 | 用户本轮明确要求即小任务范围内的执行授权。qdev 唯一停点：spec 增量（归属表、场景原文、改法）写完后给用户确认；只记变更、不写场景的改动不停（情况见 spec-scope 第 6–8 步）。确认后连续完成技术设计、实现、文档同步与公共验收。新建 spec、场景跨 2 份及以上 spec 或源码文件超过 3 个时调 x-tech-design（不单独停），否则在 task ②简写。是否转主线按 `skills/x-qdev/references/risk-rules.md` 逐条判断。实质性歧义和超出授权的关键事项集中澄清 |
| 需求变化同步 | spec 的场景或 C 变了，按 `skills/x-tech-design/references/change-sync.md` 顺着编号找引用它的 D、T、任务行和测试，逐项改、新增、退役、重开或重跑，没被引用的不动。D 表必须有“回指场景 / C”列；checklist 头部记录拆解基线，x-dev 开工前比较，未同步的行不开工。tech-design 不需要用户确认，只有需要用户拍板的取舍单独问 |
| 测试分层契约 | x-explore-for-spec 明确验收场景，x-tech-design 定义验证用例；x-req 分配本轮场景/用例与任务责任，x-dev 补齐单元/契约/边界测试。测试执行与当次改动覆盖率集中到统一测试报告，命令、基线和原始数据集中在附件；旧 v3 verify 块保留原消费位置 |
| `.fix-counter` 共享 | 路径 `docs/spec/<spec>/tasks/<task>/reports/.fix-counter`（历史 task 在原位置）。语义 = **批量修轮数**（一轮 = 一份 issue 清单的整体修复）。不存在视为 0，x-fix 进入每轮前递增；risk Q2/Q3 由 x-qa-gate 最终通过后重置，Q0/Q1 由主 agent 在升 ✅ 时重置；x-verify-spec 只读不写。**3 轮上限**。多 agent 协作时各组验收轮数另计，见 `skills/x-dev/references/parallel-dev.md` |
| reviewer 子 agent | x-qa-gate 按 checklist 头部 `risk:` 路由：Q0/Q1 不派 reviewer；Q2 派一个精简 tri-lens reviewer，Q3 派一个完整 tri-lens reviewer（q1-intent、q2-correctness、q3-evidence）。路由与输入以 `skills/x-qa-gate/SKILL.md` 为准 |
| 一轮列全 | 所有 reviewer 穷尽列出全部问题候选后判定；每条的固定字段以 `skills/x-qa-gate/SKILL.md` 为准（含 lens、task、severity、loc、msg 和证据），并省略编号；回执包含覆盖声明、完整问题候选和穷尽声明；严重度 P0/P1/P2 唯一定义在 `skills/x-qa-gate/SKILL.md` |
| reviewer 只读 | reviewer 只输出 review 回执；修改统一走 x-fix |
| issue 登记与状态写权 | 主 agent 串行逐条调用 `python3 skills/x-dev/scripts/xdev.py flag ... --json`；本轮首条带 `--new-round`。代码分配 `issue-<n>`、写 ledger、把 P0/P1 task 降为 `[!] 🔴`；每个 task 长期只保留一份 `dev-checklist.md`，内容无变化时跳过 checklist 临时文件，实际变更使用固定临时路径并在提交或恢复后清理；`recovered:true` 时主 agent 用原参数再次调用。reviewer、子 agent、x-fix 保持 ledger 与状态列原样 |
| x-fix 批量修 + 关闭问题 | x-fix 一次修完一轮 issue 清单（P0 全修且各固化一条可复跑反例、P1 修或豁免、P2 登记），产出带 issue ID 的逐条处置表；主 agent 用每条 issue 的聚焦反例加本 task 全量测试和既有回归关闭问题，不发回原 reviewer；fix 扩大到新文件或改公开 API 时另派一个裁剪 reviewer。规则见 `skills/x-qa-gate/SKILL.md`「回流」 |
| 门禁回执 | x-verify-spec / x-verify-tech / x-qa-gate / x-fix 每个节点结束都在对话中输出回执，零问题也输出；格式以各 skill 的「回执」一节为准。QA Gate issue ledger 由 flag 生成 |
| x-cr 手动调查 | `skills/x-cr/SKILL.md` 是手动软件正确性调查入口，独立于自动门禁。先读取归属 spec 的“影响边界与不变量”，再登记遗漏候选并做贝叶斯根因调查；task 报告写入 `docs/spec/<spec>/tasks/<task>/reports/cr/`，普通调查写入 `reports/cr/`；x-fix 按稳定 Bn/INV-ID 消费 |
| 状态码 | ⏳ 未开始 / ▶️ 进行中 / 🟡 待验证 / 🔴 验证失败 / 🟢 证据通过 / ✅ 已完成 / ↗️ 已升级。x-dev 最多到 🟢；✅ 由主 agent 升级：risk Q2/Q3 在 x-qa-gate 通过后，Q0/Q1 在 x-verify-spec 与 x-verify-tech 都通过后；x-qdev 先做单文档自检，再接入 x-verify-spec 对账与 x-verify-tech 局部设计验收，记录真实回执后交付；按 `skills/x-qdev/references/risk-rules.md` 有一条答“是”时停下交接、转完整主线 |

## 改 skill 时的注意事项

- **改 skill 行为要记进 spec**：使用者能观察到的 skill 行为变化，写进 `docs/spec/pipeline-skills/spec.md`（新增或修改场景），并写明用哪组 eval 或测试验收；验收题登记在 `evals/answers/INDEX.md`。只改措辞、不改行为的不用记。
- **YAML frontmatter 是触发依据**：`description` 里的关键词决定 skill 何时被自动触发。改正文是低风险，**改 description 等于改触发面**——评估全局影响后再改。
- **report 路径不能乱**：每类 fail 写到固定子目录，旧链路（直接 bug fix）走 `reports/fix/fix-report-*.md` / `fix-note-*.md`，新链路（gate 回流）走 `fix-verify-spec-*.md` / `fix-gate-r<轮次>-*.md`（批量修处置表）。两套路径**并存**，不要合并。
- **x-cr 报告交接**：task 内 CR 固定写到 `<task>/reports/cr/`，普通仓库 CR 写到仓库级 `reports/cr/`；`Schema: x-cr-v2`、`不变量覆盖`、`审查结论`、`问题详情` 及 Bn/INV-ID 映射是 x-fix 的消费契约，历史报告继续走兼容解析。
- **manifest 不显式列 skill**：`.claude-plugin/plugin.json` / `.codex-plugin/plugin.json` 都靠 `./skills/` 目录自动发现，新增 skill 不必改 manifest 字段，除非要更新 `defaultPrompt` 示例。
- **reference 文件保留制**：`skills/x-cr/references/auto-loop-mode.md` 之类的旧 reference **保留**作历史参考，不要删；新逻辑放到 x-qa-gate / x-fix 的 references。

## 子 agent dispatch 模板

- reviewer：用 `skills/x-qa-gate/SKILL.md`「Prompt 模板」，按 Q2 / Q3 给 tri-lens 输入。
- 多 agent 协作开发的工人与验收 agent：用 `skills/x-dev/references/parallel-dev.md` 的派工单和回执格式。

## x-spec2 eval 计量边界

- `skills/pipeline-efficiency-benchmark/scripts/metrics.py extract` 只读取调用方显式给出的完成态 Codex rollout JSONL，或主 agent 在子 agent 完成通知到达时保存的 `timing.json`；工具不扫描 session 目录。
- rollout 样本必须只有一个 session ID、一个 `turn_context` 和一个 `task_complete`。token 使用完成事件前最后一份 provider 累计快照，duration 使用 `turn_context` 到 `task_complete` 的时间差。
- 子 agent 通知源保留真实 `total_tokens` 与 `duration_ms`；细分 token、起止时间缺失时写 `null`。collector 和 grader 的 token、耗时不计入被测样本。
- executor inputs 与 grader-only inputs 必须在 metadata 中分开声明；重叠或 `rubric_exposed: true` 使样本退出 1。paired 聚合还要求 prompt hash、model、repo SHA 与评分断言完全一致。
- measurement 只保存 prompt 哈希，不复制 prompt、对话、工具参数或文件内容。退出码：0 成功，1 可读但无效的样本/配对，2 参数、IO、JSON 或 schema 错误。


## 常用维护操作

```bash
# 看仓库结构总览
grep -n "^## " skills/*/SKILL.md

# 列当前 task（dev-pipeline/tasks/ 是历史档案）
find docs/spec -mindepth 3 -maxdepth 3 -path '*/tasks/*' -type d

# 安装到本地 Claude Code 做联调
claude plugin install x-dev-pipeline@x-dev-pipeline --scope user

# 同步当前改动到 Codex（macOS/Linux 自行 git pull；Windows 用脚本）
./install-codex.ps1
```

确定性工具测试位于 `test/`、`cli/` 及相应 skill 的 `tests/`。技能行为通过隔离任务验证；修改 `skills/x-dev/` 时按 `evals/README.md` 执行交付冒烟测试。

## 历史改造记录

（历史记录，描述的是当时的设计；现行 reviewer 派法以 `skills/x-qa-gate/SKILL.md` 为准。）`dev-pipeline/tasks/qa-gate-pipeline/` 曾是主线改造任务（v0.2 双层 gate 架构）：把老 `x-cr` 单层闭环升级为 `x-verify-spec` (事实) + `x-qa-gate` (R1/R2/R3 评审) 双层 gate，并把 perf/style 剥离成独立 audit。代码改动已落地，**待用户在新会话跑完 5 个 e2e smoke case 才能升 ✅**。看 `dev-pipeline/tasks/qa-gate-pipeline/changelog.md` 了解最新决策。
