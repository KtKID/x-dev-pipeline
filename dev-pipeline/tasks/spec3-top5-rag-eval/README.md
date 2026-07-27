# Spec3 Top5 RAG 评估

> 创建时间：2026-07-24
> 类型：优化
> 风险等级：Q1
> 审查路线：主 agent 闭环

## 用户原始请求

> 我觉得能不能每次都查，这个无所谓泄露，但是我希望改成rag返回top5，这个成本先跑再看，然后分数我还不想改变。然后先跑任务再看，你觉得呢？

## 任务说明

保持 iteration-7 现有复杂度、重要性、平均分和 standard/deep/full 路由不变。把 x-spec3 交接给 x-adversarial-risk 时的默认 RAG 召回数量从 Top1 调整为 Top5，更新对应契约测试，并完整运行现有 journal-index-recovery spec-risk 任务，记录真实成本和产物变化。

## 明示假设

| 编号 | 假设 | 依据 | 影响 |
|---|---|---|---|
| A1 | Top5 只调整 x-spec3 → x-adversarial-risk 的调用参数；通用 x-dev-rag-call 默认值继续为 Top1 | 用户讨论范围聚焦 spec3；通用召回 skill 支持调用方显式指定 TopN | 假设错误时会遗漏通用默认值调整 |
| A2 | 本轮保留现有 full 预算的独立故障假设规则 | 用户明确要求评分暂时不变，本轮目标是观察 Top5 成本 | Top5 与独立假设可能共同增加推理成本，该结果进入评估 |

## 涉及模块

- `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-spec3/SKILL.md` — 对抗审查交接参数
- `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/SKILL.md` — 召回数量与回执契约
- `skills/x-pipeline-efficiency-workspace/iteration-7/tests/test_adversarial_risk.py` — Top5 集成契约
- `skills/x-pipeline-efficiency-workspace/iteration-7/eval-11-journal-index-recovery-spec-risk/` — 完整任务运行与成本产物

## DoD 与证据

| 编号 | DoD | 来源 | 证据计划 | 最终证据 | 状态 |
|---|---|---|---|---|---|
| D1 | 所有评分预算都执行 Top5 风险召回；standard 保持零 Scenario 扩张 | 用户原始请求 | Skill 文本检查与集成契约测试 | x-spec3 明确所有预算执行 Top5；x-adversarial-risk 使用 `--top-n 5`；集成契约测试通过 | ✅ |
| D2 | 复杂度、重要性、平均分和预算映射保持原值 | 用户原始请求 | scoped diff 与完整任务 run-summary | 评分代码与阈值文件零改动；run-summary 仍为 `5 / 1 / 3.0 / full` | ✅ |
| D3 | iteration-7 定向与完整测试通过 | 既有测试契约 | unittest discover | `Ran 46 tests ... OK` | ✅ |
| D4 | 完整 spec-risk 任务产生 token、耗时、Top5 命中和 Scenario 变化证据 | 用户原始请求 | 隔离 Codex run、固定 grader 与运行分析 | 冻结 initial Spec 的当前 session replay 完成；run-summary 记录 Top5、53.188 秒 token 切片及 Scenario 差异；外部隔离 turn 等待显式数据发送授权 | ✅ |

## 风险判断

- 风险等级：Q1
- 触发因素：iteration-7 实验性 skill 的局部行为参数变化；既有真实模型 Smoke、单元测试和固定 grader 可复用。
- 升级条件：Top5 需要修改评分公式、风险来源 schema、validator 或 x-req3 公开交接协议。

## 任务起点基线

- `git status --short`：共享工作区已有多项无关修改；iteration-7 目标 skill 文件为 tracked 且 clean。
- 起点 changed paths：目标文件无 tracked diff。
- 起点 untracked paths：iteration-7 下仅有 Python `__pycache__/`；另有本任务外 OpenSpec 与 CR 报告。
- 与预期任务文件重叠：无。
- 重叠文件初始 diff 摘要或 hash：
  - `x-spec3/SKILL.md`：`76a0cb89d69bdc8fd7b8b1ec75d5e88534d3067e07a2bc2adf555424eca85a5b`
  - `x-adversarial-risk/SKILL.md`：`04ba6aab0156951b344ab074eaeb198de6894a3835942cdb5e7769416354d3a9`
  - `test_adversarial_risk.py`：`9403f2ad2139f5f255bfdf93459fe5c63d8eaa4a6ebde49a4d0a951b00d1141e`
- 用户既有改动保护策略：只修改上述三个 tracked 文件并新建独立 run 目录与 qdev 记录。

## 开发清单

| 编号 | 优先级 | 状态 | 任务 | 备注 |
|---|---|---|---|---|
| #1 | P0 | ✅ 已完成 | 把 spec 风险召回契约调整为 Top5 | 对应 D1、D2 |
| #2 | P1 | ✅ 已完成 | 更新 Top5 集成契约测试并运行 iteration-7 测试 | 对应 D3 |
| #3 | P1 | ✅ 已完成 | 运行 journal-index-recovery spec-risk 冻结初稿 replay 并分析成本 | 对应 D4 |

## 预期涉及文件

- `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-spec3/SKILL.md`
- `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/SKILL.md`
- `skills/x-pipeline-efficiency-workspace/iteration-7/tests/test_adversarial_risk.py`
- `skills/x-pipeline-efficiency-workspace/iteration-7/eval-11-journal-index-recovery-spec-risk/top5/run-1/`

## 实际涉及文件

- `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-spec3/SKILL.md` — 交接改为 Top5。
- `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/SKILL.md` — Top5 查询、结果处理与回执契约。
- `skills/x-pipeline-efficiency-workspace/iteration-7/skills/README.md` — 流程概览同步 Top5。
- `skills/x-pipeline-efficiency-workspace/iteration-7/tests/test_adversarial_risk.py` — Top5 集成断言。
- `skills/x-pipeline-efficiency-workspace/iteration-7/eval-11-journal-index-recovery-spec-risk/top5/run-1/` — 运行输入、产物和成本证据。
- `dev-pipeline/tasks/spec3-top5-rag-eval/` — qdev 任务记录。
