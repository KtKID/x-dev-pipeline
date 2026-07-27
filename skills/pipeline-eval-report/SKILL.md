---
name: pipeline-eval-report
description: |
  项目级 pipeline eval 分析与报告 skill。每当用户要求评审 Agent 或模型根据题目生成的 spec、req、dev、verify、QA 产物，查看 Mavis Token/耗时，按答案或 rubric 评分，判断一次行为是否属于 pipeline run，生成或更新 pipeline_run_id、事件账本、扣分知识和 evaluation-report 时使用。也用于现有 run 重评分、失败归因、跨模型或版本比较，以及把评测关键点写入 pipeline-data 知识库。
metadata:
  compatibility: Requires Python 3, readable task and candidate artifacts, and a readable Mavis SQLite database when runtime telemetry is requested.
---

# Pipeline Eval Report

把一次真实 pipeline 执行转成可复核的质量、成本和归因证据。正确性门禁先判断产物能否指导下游正确完成任务；Token、耗时和文档体积随后用于比较效率。

## 产物

每个评测 run 写入 `pipeline-data/runs/{pipeline_run_id}/`：

- `manifest.json`：任务、版本、执行器、输入与被评产物的静态身份。
- `events.jsonl`：追加式阶段事实、评分、门禁和知识事件。
- `telemetry.json`：模型调用、Token、费用、耗时、工具和 phase 归属。
- `grading.json`：rubric 分项结果、P0/P1/P2 扣分及证据。
- `evaluation-report.md`：面向人的精简结论。

历史引导 run 使用 `storage_profile: bootstrap-json-v0`，只保留 `manifest.json` 与 `events.jsonl` 作为进化账本。新建评测 run 一律写齐上述五个核心文件；validator 对 bootstrap profile 执行只读兼容校验。

关键失败、扣分和优化依据写入 `pipeline-data/knowledge/entries/{knowledge_id}.json`。完整字段和一致性规则见 `references/artifact-contract.md`；报告渲染前读取 `assets/evaluation-report-template.md`。

## 最短路径

1. 先判定 run 身份并创建或续用 `pipeline_run_id`。
2. 冻结题面、rubric、skill 和候选产物的路径、版本与 SHA-256。
3. 从 Mavis 或其他 provider 真源提取完整执行遥测。
4. 按 rubric 逐项检查语义，记录可定位证据。
5. 应用正确性门禁，定位问题最早进入 pipeline 的阶段。
6. 写五类 run 产物和知识条目。
7. 运行 `scripts/validate_run.py`，通过后交付报告路径与结论。

## 1. 判定 pipeline run

将以下行为登记为 pipeline run：

- 生产任务、评测任务、修复任务或回放任务触发了一个或多个 pipeline phase。
- 外部 Agent 已经生成 spec、req、代码或验证产物，当前工作负责追认、评审或补齐遥测。
- 同一用户目标由 `x-spec3 → x-req3` 等多个 skill 连续完成；它们属于一个 run 内的多个 phase。

身份规则：

- 一个用户任务对应一个 `pipeline_run_id`。
- 同一任务的反馈、修订、重评分和修复继续使用原 run，并增加 `stage_attempt`。
- 同题目的独立重放使用新 run，并通过 `parent_run_id`、`baseline_run_id` 或 comparison 字段关联。
- Mavis Session、Codex rollout 等 provider ID 保存为 `source_session_id`；pipeline_run_id 负责跨执行器关联事件、报告和知识。
- 追认历史执行时，先按 source ID、任务 hash 和 workspace 搜索已有 manifest，复用匹配 run。

新 ID 使用 `prun-{uuid}-{sequence}`。Mavis ID 具有 32 位 UUID 十六进制主体时，可以插入标准 UUID 连字符形成稳定映射；同一 source 始终得到同一候选 ID，最终仍需检查仓库内唯一性。

在分析前写 `run_started` 或 `run_recognized` 事件。后续事实按发生顺序追加，历史事件保持原文。

## 2. 建立证据边界

完整读取并区分：

- 题面或用户需求：定义目标行为和范围。
- evaluator-only 答案、rubric、隐藏 Harness：定义评分与反例，只供评审阶段读取。
- 候选产物：spec、req、代码、测试、verify 或 QA 证据。
- 运行事实：Session、工具调用、命令退出码、测试结果、Token 与耗时。
- pipeline 版本：skill、模板、validator、模型和仓库 SHA。

执行器与 grader 保持信息隔离。报告记录 rubric 是否对执行器隐藏。可变或仓库外的文本产物复制到 run 的 `artifacts/` 后再评分；大型产物记录不可变存储引用和 SHA-256。

评审只写有证据的结论。外部答案与题面冲突时，把冲突记录为 evaluator gap，并保留两份 hash。

## 3. 提取遥测

Mavis 默认数据库为 `~/.mavis/sqlite.db`。优先使用已验证的提取器：

```bash
python3 /Volumes/machub_app/proj/x-evals/tools/mavis_eval.py sessions \
  --db ~/.mavis/sqlite.db --workspace /absolute/workspace --limit 20

python3 /Volumes/machub_app/proj/x-evals/tools/mavis_eval.py metrics \
  --db ~/.mavis/sqlite.db --session-id mvs_xxx --format json
```

选择 session 时交叉核对 workspace、标题、模型、任务首条消息、产物写入时间和文件 mtime。记录其他候选及排除理由。

统一保存：

- Input、Output、Reasoning、Cache Read、Cache Write。
- `total_with_cache` 为五项之和；`total_without_cache_read` 单列。
- `prompt_to_final_seconds` 作为用户等待耗时；session lifecycle 作为诊断值。
- 工具调用、工具失败、用户追加消息和子 session 归属。
- grader、collector 和 analyzer Token 归入 `evolution_eval_tokens`，与 executor 分列。

Phase 切分只采用可定位边界，例如阶段启动消息、skill 调用或产物写入事件。`telemetry.json` 写明切分方法；完整 session 总量保持权威。跨 provider 或不同阶段范围的 Token/耗时比较标为描述性观察。

运行时无法提供指标时保存 `null`、缺失原因和已检查的数据源。

## 4. 按 rubric 评审

rubric 已存在时逐条使用。只有答案文档时，先把答案转成编号、可判定的 assertions，并记录 rubric hash 与版本，再开始查看候选产物。

每条 assertion 保存：

- `text`：期望行为。
- `passed`：布尔值。
- `evidence`：文件、行号、测试或事件。
- `reason_code`：失败时的稳定分类。
- `severity`：P0、P1 或 P2。
- `score_impact`：扣分或门禁影响。

评分原则：

- 关键词出现只证明文档提及，完整可执行断言证明通过。
- GIVEN、WHEN、THEN 必须联合可满足。输入同时触发另一条强制错误时，该 Scenario 不能证明成功路径。
- 题面未定义类型转换、默认值、顺序或协议时，候选应保持输入语义并把选择标为待确认。
- 边界类别需要具体反例，例如三层递归、不同 map 插入顺序、嵌套 map/slice 所有权和并发交错。
- 上游错误被 req 或 dev 忠实传播时，分别记录“交接成功”和“语义错误来自上游”。
- rubric 本身的复合断言、歧义或错误进入 evaluator gap，保持与候选扣分分离。

P0 表示会指导下游违反任务硬契约、造成错误放行或破坏关键不变量；P1 表示高价值边界缺口；P2 表示局部证据或可维护性问题。具体规则见 `references/grading-guide.md`。

## 5. 门禁与归因

分别保存执行终态与质量终态：

- `execution_outcome` 表示 Agent、命令和产物是否完成。
- `quality_gate` 表示产物能否进入下一阶段。
- `accepted_delivery` 只在意图、正确性和风险门禁全部通过时为 true。

任一 P0 或关键不变量断言失败时，质量门禁失败，并在进入 dev、扩大回放或晋级之前停止。该 run 已消耗的 Token 保持计入总消耗，accepted 分母保持 0。

归因定位问题最早进入证据链的阶段，同时记录发现阶段。优先使用稳定 reason code：

- `SPEC_INTENT_GAP`、`SPEC_BOUNDARY_ERROR`、`SPEC_CONTRACT_CONTRADICTION`
- `REQ_DECOMPOSITION_GAP`、`CONTRACT_DRIFT`
- `DEV_IMPLEMENTATION_DEFECT`
- `VERIFY_COVERAGE_GAP`、`VERIFY_FALSE_PASS`
- `QA_FALSE_ACCEPT`、`QA_FALSE_BLOCK`
- `ROUTER_UNDER_REVIEW`、`ROUTER_OVER_REVIEW`
- `CONTEXT_BLOAT`

任务特有子类可以追加更精确代码，例如 `SCENARIO_SCHEMA_CONTRADICTION`，并通过 `parent_reason_code` 关联通用类。

## 6. 写入知识库

失败事实和 grader 扣分事实独立保存；同一根因可以被多条 deduction 引用。一个知识条目聚合一个独立根因簇，避免把同义措辞拆成多条。

知识条目至少包含：

- `knowledge_id`、`pipeline_run_id`、阶段和 attempt。
- reason codes、期望、实际、严重度和证据引用。
- 根因状态：`observed`、`hypothesis`、`confirmed` 或 `superseded`。
- 受影响产物、修复建议、最小回归 case 和 Token 影响。
- 后续修订与回放结果。

用户确认前使用 `pending_confirmation`；后续证据通过新事件和修订字段演进。

## 7. 生成报告

按照 `assets/evaluation-report-template.md` 生成短报告。正文只保留会改变门禁、修复或优化决策的信息；详细 assertions、原始遥测和事件通过链接下钻。

报告必须回答：

1. 这是否是一条 pipeline run，ID 和 phase 是什么。
2. 执行是否完成，质量是否通过，能否进入下一阶段。
3. 主要 P0/P1、证据和最早责任阶段是什么。
4. Token、耗时、费用和污染状态是什么。
5. 与 baseline 是否可比，差异能否归因于 skill。
6. 哪些关键点已进入知识库，下一门禁是什么。

## 8. 完成验证

运行：

```bash
python3 skills/pipeline-eval-report/scripts/validate_run.py \
  pipeline-data/runs/{pipeline_run_id}
```

确认：

- 五类 run 产物存在且 JSON/JSONL 可解析。
- 所有文件、事件和知识引用使用同一个 pipeline_run_id。
- Token 分桶加总与 phase 汇总一致。
- grading 分数与 assertion 统计一致。
- P0、quality gate 和 accepted delivery 状态一致。
- 报告数值来自结构化产物，证据路径可定位。
- 工作树中只包含本次授权范围内的新增或修改。

最终回复给出报告、事件账本、grading、telemetry 和知识条目的绝对路径，并报告 validator 结果。
