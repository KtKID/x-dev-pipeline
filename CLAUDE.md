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
│   └── references/, templates/        # 规则细节、模板
├── docs/spec/<spec>/                  # 一份 spec 管一块数据：spec.md、tech-design.md
│   └── tasks/<task>/                  # 当前 task
│       ├── dev-checklist.md           # 唯一交付文件：任务表 + 末尾「结果」（用例对应、覆盖率、问题与处置）
│       ├── evidence/                  # 原始输出：测试日志、coverage.json、截图、人工验证记录
│       └── reports/                   # .fix-counter、qa-gate issue ledger、cr 报告
├── docs/architecture.md               # 项目架构偏好（有就用，模板在 x-tech-design/templates/）
├── dev-pipeline/tasks/                # 历史 task 档案；工具不再识别、校验或编排
├── skills/x-dev/scripts/xdev.py       # 薄 CLI 路由器；delivery.py 做 start/coverage/check
├── skills/x-req/scripts/              # checklist_engine.py（当前格式）、req.py（旧 v3 包）
├── skills/x-spec/scripts/、x-verify-spec/scripts/   # 旧 v3 包的校验与 verify 引擎
├── skills/x-qa-gate/scripts/          # QA issue 事务引擎（flag）
├── .claude-plugin/、.codex-plugin/、.agents/    # 插件注册
└── evals/、test/、cli/、examples/
```

## 核心管线

```
x-explore-for-spec → x-tech-design → x-req → x-dev ──→ 真实性检查 ──→ xdev check ──→ x-qa-gate ──→ ✅
探索与增量 spec        技术设计        task     实现+覆盖率  轻量子 agent    机械核对       一次独立审查
                                                     查假测试      （x-verify-spec）  （Q0 跳过）
小改动：x-qdev 一个 agent 走完，同样用 xdev start / coverage / check。问题修复交 x-fix。
```

- 能用脚本判断的都交给 `xdev`：结构与编号（validate）、需求变化（impact）、派工顺序（graph）、代码基线（start）、改动行覆盖率 100%（coverage）、交付核对（check，也读测试真实性检查的回执）。agent 只做脚本判断不了的事。
- 独立审查只有一次：x-qa-gate 按 risk 派一个 reviewer（Q0 不派）。四个 lens 是需求对齐、边界、测试是否证明了场景、设计与架构偏好；Q1 做其中三个（不含边界），Q2/Q3 四个都做。x-verify-tech 是 q4-design lens 的方法来源，也可以单独调用。
- `cli/` 下的 Go 版本保留不删：计划以后做成“agent 调一个命令就能初始化这套管线、安装必需 skill”的工具，目前暂停维护，行为停在旧引擎，skill 不调用它。
- x-plan 已废弃，功能合并到 x-req。

独立巡检（不在主流程）：`x-audit-perf` / `x-audit-style` / `x-audit-arch`，由用户手动触发或里程碑后跑；`x-cr` 是手动正确性调查。

## skill 间契约（改 skill 前必读）

每条规则只在一个地方写全，这里只指路。改规则时改源头，不在这里复述。

| 规则 | 唯一来源 |
|---|---|
| spec 归谁管、加到已有还是新建、跨 spec 怎么放 | `skills/x-explore-for-spec/references/spec-scope.md` |
| 需求变了怎么同步 D / T / 任务行 / 测试 | `skills/x-tech-design/references/change-sync.md` |
| qdev 什么时候转主线 | `skills/x-qdev/references/risk-rules.md` |
| qdev 唯一停点（spec 增量给用户确认）与执行授权 | `skills/x-qdev/SKILL.md` 第 1 节 |
| 并行组、依赖、risk Q0–Q3 怎么算 | `skills/x-req/SKILL.md`，`xdev validate` 核对 |
| 多 agent 协作：派工单、工人规则、每组核对、合并 | `skills/x-dev/references/parallel-dev.md` |
| 结果与证据写在哪、覆盖率怎么跑、Web 验收 | `skills/x-dev/references/test-reporting.md` |
| 测试是硬规则（全量全绿、改动行 100%）、测试真实性检查（轻量子 agent 查假测试） | `skills/x-dev/SKILL.md`「测试是硬规则」、`skills/x-dev/references/test-integrity.md` |
| 交付核对的每条规则 | `skills/x-dev/scripts/delivery.py`（说明见 `skills/x-verify-spec/SKILL.md`） |
| 审查路由、lens、严重度 P0/P1/P2、issue 登记、回流关闭 | `skills/x-qa-gate/SKILL.md` |
| 批量修复、`.fix-counter` 3 轮上限、处置记录 | `skills/x-fix/SKILL.md` |
| 状态码与写权 | `skills/x-dev/references/execution-rules.md` |
| 架构偏好怎么写、谁用 | `skills/x-tech-design/templates/architecture-preferences.md` |
| 风险错题集边界 | `skills/x-adversarial-risk/references/risk-mistakes.md`（只由 x-adversarial-risk 读取） |
| x-cr 报告交接（`Schema: x-cr-v2`、Bn/INV-ID） | `skills/x-cr/SKILL.md` |
| 带 `spec_version: 3` / `adversarial_risk_version: 3` 的旧契约 | 原 req.py / verify.py / validator.py 与 x-adversarial-risk，行为不变 |

## 改 skill 时的注意事项

- **改 skill 行为要记进 spec**：使用者能观察到的 skill 行为变化，写进 `docs/spec/pipeline-skills/spec.md`（新增或修改场景），并写明用哪组 eval 或测试验收；验收题登记在 `evals/answers/INDEX.md`。只改措辞、不改行为的不用记。
- **YAML frontmatter 是触发依据**：`description` 里的关键词决定 skill 何时被自动触发。改正文是低风险，**改 description 等于改触发面**——评估全局影响后再改。
- **产物不要变多**：task 只有一份交付文件 `dev-checklist.md`（qdev 是 task `.md`），原始输出放 `evidence/`。门禁回流的处置写进 checklist「问题与处置」；`reports/fix/fix-report-*.md` / `fix-note-*.md` 只用于直接 bug 修复和 CR 驱动修复。历史 task 里的 dev-report、test-report、`fix-verify-spec-*`、`fix-gate-r*` 保留原样，不再新建。
- **x-cr 报告交接**：task 内 CR 固定写到 `<task>/reports/cr/`，普通仓库 CR 写到仓库级 `reports/cr/`；`Schema: x-cr-v2`、`不变量覆盖`、`审查结论`、`问题详情` 及 Bn/INV-ID 映射是 x-fix 的消费契约，历史报告继续走兼容解析。
- **manifest 不显式列 skill**：`.claude-plugin/plugin.json` / `.codex-plugin/plugin.json` 都靠 `./skills/` 目录自动发现，新增 skill 不必改 manifest 字段，除非要更新 `defaultPrompt` 示例。
- **reference 文件保留制**：`skills/x-cr/references/auto-loop-mode.md` 之类的旧 reference **保留**作历史参考，不要删；新逻辑放到 x-qa-gate / x-fix 的 references。

## 子 agent dispatch 模板

- reviewer：按 `skills/x-qa-gate/SKILL.md` 的「输入」和「调度纪律」组装一次性 prompt。
- 多 agent 协作开发的工人：用 `skills/x-dev/references/parallel-dev.md` 的派工单和回执格式。

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
