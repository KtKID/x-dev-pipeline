<p align="center">
  <img src="assets/pic.png" alt="x-dev-pipeline" />
</p>

# x-dev-pipeline

[English](./README.md)

**当前版本：** v0.5.0

> 给 AI coding agent 一套可审计的开发工作流：需求契约、实现证据、确定性验证、按风险评审。

`x-dev-pipeline` 让 README 承载需求和验收场景，dev-report 承载可执行证据，git history 承载仓库改动。每个 task 走同一条风险路由。

## 第一次使用：`/x-req`

所有任务从 `/x-req` 进入。它定级 Q0–Q3、创建精简 task 包，并续接 x-dev。

```text
/x-req 给设置页增加深色模式切换
```

首次体验通常是 Q1：x-req 记录低风险依据并生成 task，x-dev 实现，`xdev.py verify` 复跑声明的验证证据。

```text
dev-pipeline/tasks/<task-name>/
├── README.md            # risk、架构、验收 Scenario
├── dev-checklist.md     # 带依赖的执行状态
├── diagram.md           # 可选
└── dev-report.md        # x-dev 创建，含 fenced verify 块
```

## 一条风险路由

```text
用户请求 → x-req → x-dev → xdev.py verify
                              ├─ Q0 / Q1 → 交付回执
                              ├─ Q2 → x-qa-gate RC
                              └─ Q3 → x-qa-gate R1 → R2 → R3
                                           │
                              问题候选 → xdev.py flag → x-fix → 增量复审
                                             │
                                  issue ledger + `[!] 🔴`
```

| risk | 典型范围 | verify 通过后的路径 |
|------|----------|---------------------|
| Q0 | 单文件且没有行为分支变化 | 交付回执 |
| Q1 | 局部功能或修复，没有跨模块契约变化 | 交付回执 |
| Q2 | 新功能、多文件、契约或状态变化 | RC 综合评审 |
| Q3 | 安全、不可逆写入、公开 API/schema、并发或状态机变化 | R1 → R2 → R3 |

用户可显式指定 risk。Q0/Q1 直接准备并执行；Q2/Q3 在写 task 文件前展示一次确认。

## Spec 对抗性风险门禁

spec 包在 task 拆解前经过独立风险门禁：

```text
用户请求 → x-spec → x-adversarial-risk → x-req → x-dev
                   双评分 + 初版测试       对抗性测试
```

x-spec 分别记录 1–5 的复杂度和重要性，并把第一版 Scenario 标记为 `initial-spec`。插件在 x-adversarial-risk skill 目录内提供默认的丰富字段错题集，也接受调用方显式路径覆盖默认值。所有预算执行一次 Top5 召回；deep/full 使用适用的命中追加带 `adversarial-review` 来源的反例 Scenario。带风险版本标记的 Spec 审查状态仍为 pending 时，x-req 阻断任务拆解。

## 验收与证据

README 的验收使用 Requirement/Scenario：

```markdown
### Requirement: 主题设置

#### Scenario: 切换后重载仍保留
- **WHEN** 用户启用深色模式并刷新页面
- **THEN** 页面保持深色模式
- 验证: auto
```

每个 `验证: auto` Scenario 在 `dev-report.md` 有一个回指它的 verify 块：

````markdown
```verify
id: S1
scenario: 切换后重载仍保留
cmd: npm test -- theme-setting
expect_exit: 0
expect_contains: passed
```
````

`python3 tools/xdev.py verify <task-dir> --json` 会复跑 auto 块、比较 exit 和输出片段、列出 manual 步骤，并报告缺少证据回指的自动场景。退出码 0 表示自动事实通过；1 表示命令或覆盖失败；2 表示输入、路径或格式错误。

## 命令

| 命令 | 职责 |
|------|------|
| `/x-req` | 定级 Q0–Q3，创建或更新 task 包 |
| `/x-dev` | 实现 checklist，并写 verify 证据 |
| `/x-verify` | 执行确定性 Gate ①，诊断失败事实 |
| `/x-qa-gate` | 执行 Gate ②：Q2 用 RC，Q3 用 R1/R2/R3 |
| `/x-fix` | 批量修复 verify、gate 或 CR 发现 |
| `/x-cr` | 调查已知正确性问题、模块、diff 或 PR |
| `/x-spec` | 产出系统级架构与 task 映射 |
| `/x-adversarial-risk` | 推翻 Spec 风险假设并补充可追溯反例 Scenario |
| `/x-multi-llm-align` | 对齐协议、数据结构或流程 |
| `/x-audit-perf` | 独立性能巡检 |
| `/x-audit-style` | 独立规范巡检 |
| `/x-audit-arch` | 独立架构巡检 |

## 确定性引擎

`tools/xdev.py` 是机械规则的薄 CLI 入口；包校验由 `tools/validator.py` 负责，spec task
规划由 `tools/req.py` 负责，验证由 `tools/verify.py` 负责，QA issue 事务由
`tools/flag.py` 负责：

```text
validate [pkg...]                 校验 spec、change、task 契约
status <task-dir> [--json]        解析 checklist 进度
graph <task-dir> [--json]         计算 ready task 与并行批次
instructions <artifact> --task    返回 task 产物填写规则
scaffold <task-dir>               只创建缺失 task 产物
verify <task-dir> [--json]        执行证据并对账 Scenario
flag <task-dir> --task T2,T3 --severity P0 --loc src/a.py:10 --msg "..." [--new-round] [--json]
```

task 命令只接收 `docs/spec/<spec-name>/tasks/<task-name>/`。历史
`dev-pipeline/tasks/` 目录继续作为可读档案保留，不再获得运行时校验或编排支持。

## x-spec2 pilot 计量

`tools/metrics.py` 从一个显式 Codex rollout JSONL，或保存后的子 agent 完成通知中记录一次 x-spec2 eval。最小 measurement 包含执行来源 ID、模型、仓库 SHA、prompt 哈希、耗时、provider 返回的真实总 token，以及独立 grader 给出的断言通过率。

```bash
python3 tools/metrics.py extract \
  --timing <run-dir>/timing.json \
  --metadata <run-dir>/eval_metadata.json \
  --grading <run-dir>/grading.json \
  --output <run-dir>/measurement.json

python3 tools/metrics.py aggregate-spec2 skills/x-spec2-workspace/iteration-2
```

退出码 0 表示提取或聚合成功；1 表示可读取的样本违反 fresh-session、rubric 隔离或 paired 可比性边界；2 表示参数、IO、JSON 或 schema 错误。单个 paired run 标记为 `pilot: true`，它用于证明测量流程成立，稳定效果判断需要更多题目与重复运行。

## 报告与回流

- Gate ① 全过只输出回执；失败生成 `reports/verify/verify-report-*.md`，交 x-fix。
- Gate ② reviewer 返回未编号的 task/severity/loc/msg 问题候选。主 agent 逐条调用 `xdev.py flag`，由代码分配 `issue-<n>` 并写入 `reports/qa-gate/qa-gate-report-*.md`。
- `flag` 通过持久事务标记协调 issue ledger 与 checklist。P0/P1 目标降为 `[!] 🔴`，P2 保持全部 task 状态；pending 事务恢复返回 `recovered:true`，调用方随后重试本条新 issue。
- x-fix 一次处理完整 issue 清单，并保持 ledger 与 checklist 状态单元格原样；增量复审通过后由主 agent 升钩。verify 与 Gate ② 共享既有三轮 fix-counter。
- manual 验收步骤持续显示在 verify 回执，直到用户确认。

## 安装

仓库同时提供 Claude Code 与 Codex 的 manifest：

```text
.claude-plugin/plugin.json
.claude-plugin/marketplace.json
.codex-plugin/plugin.json
.agents/plugins/marketplace.json
```

Claude Code：

```bash
git clone https://github.com/KtKID/x-dev-pipeline.git ~/.claude/plugins/x-dev-pipeline
claude plugin marketplace add ~/.claude/plugins/x-dev-pipeline/.claude-plugin/marketplace.json
claude plugin install x-dev-pipeline@x-dev-pipeline --scope user
```

Codex：把 `.agents/plugins/marketplace.json` 中的仓库条目加入 marketplace，重启 Codex 后从本地插件目录安装 `x-dev-pipeline`。

## 状态标记

| 标记 | 含义 |
|------|------|
| `[ ] ⏳` | 未开始 |
| `[ ] ▶️` | 进行中 |
| `[ ] 🟡` | 等待声明验证 |
| `[!] 🔴` | 验证失败 |
| `[x] 🟢` | 验证通过 |
| `[x] ✅` | risk 路径完成 |

## License

MIT
