# Pipeline Eval 产物契约

本契约约束 `pipeline-data/runs/{pipeline_run_id}/`。事实写入一次，其他文件引用或渲染该事实，减少审计漂移。

## manifest.json

保存运行开始时可冻结的身份：

```json
{
  "schema_version": 1,
  "pipeline_run_id": "prun-uuid-001",
  "run_kind": "evaluation",
  "objective": "评测目标",
  "parent_run_id": null,
  "source": {
    "kind": "mavis_session",
    "id": "mvs_xxx",
    "database": "~/.mavis/sqlite.db",
    "workspace_dir": "/absolute/workspace"
  },
  "task": {
    "path": "/absolute/task.md",
    "sha256": "...",
    "rubric": "/absolute/or/project-relative/rubric.md",
    "rubric_sha256": "...",
    "rubric_exposed_to_executor": false
  },
  "repository": {"sha": "...", "branch": "..."},
  "executor": {
    "model": "provider/model",
    "skills": [{"name": "x-spec3", "sha256": "..."}]
  },
  "pipeline": {
    "phases": ["x-spec3.spec", "x-req3.task", "spec_quality_review"]
  },
  "started_at": "ISO-8601",
  "status_source": "events.jsonl"
}
```

被评产物记录绝对原路径、run 内快照路径和 hash。原路径可变时，快照是审计真源。

## events.jsonl

每行一个 JSON object，至少包含：

```json
{
  "schema_version": 1,
  "event_id": "evt-001",
  "pipeline_run_id": "prun-uuid-001",
  "timestamp": "ISO-8601",
  "type": "stage_attempt_started",
  "stage": "x-spec3.spec",
  "attempt": 1
}
```

规则：

- event_id 在 run 内唯一并按追加顺序递增。
- 重复收集使用原 event_id 幂等处理。
- 更正通过新事件引用 `supersedes_event_id`。
- 常用 type：`run_started`、`run_recognized`、`stage_attempt_started`、`artifact_written`、`stage_attempt_completed`、`telemetry_collected`、`score_deduction_recorded`、`quality_gate_failed`、`quality_gate_passed`、`knowledge_recorded`、`report_written`。

## telemetry.json

```json
{
  "schema_version": 1,
  "pipeline_run_id": "prun-uuid-001",
  "source": {"kind": "mavis_sqlite", "session_id": "mvs_xxx"},
  "model": "provider/model",
  "llm_calls": 1,
  "tokens": {
    "input": 0,
    "output": 0,
    "reasoning": 0,
    "cache_read": 0,
    "cache_write": 0,
    "total_without_cache_read": 0,
    "total_with_cache": 0,
    "cost_usd": null
  },
  "duration": {
    "prompt_to_final_seconds": null,
    "session_lifecycle_seconds": null
  },
  "tools": {"total": 0, "failures": 0},
  "phase_allocation": {"method": "evidence boundary", "phases": []},
  "measurement_notes": []
}
```

公式：

```text
total_without_cache_read = input + output + reasoning + cache_write
total_with_cache = total_without_cache_read + cache_read
```

Provider 口径不同或字段缺失时保留原始分桶，并在 measurement_notes 说明映射。

## grading.json

```json
{
  "schema_version": 1,
  "pipeline_run_id": "prun-uuid-001",
  "rubric": "path/to/rubric.md",
  "rubric_sha256": "...",
  "status": "manual_review_complete",
  "expectations": [
    {
      "id": 1,
      "text": "可判定期望",
      "passed": false,
      "evidence": ["artifact.md:12"],
      "severity": "P0",
      "reason_code": "SPEC_CONTRACT_CONTRADICTION",
      "parent_reason_code": "SPEC_CONTRACT_CONTRADICTION",
      "score_impact": 5
    }
  ],
  "summary": {
    "passed": 0,
    "failed": 1,
    "total": 1,
    "pass_rate": 0.0,
    "score": 0,
    "score_max": 5
  },
  "decision": {
    "execution_outcome": "completed",
    "quality_gate": "failed",
    "accepted_delivery": false,
    "next_stage": "revise_spec"
  },
  "evaluator_gaps": []
}
```

Rubric 含多个独立分组时，允许在 `quality` 中保存分组统计；`summary` 仍提供全部 assertion 的统一计数。

## evaluation-report.md

报告从 manifest、telemetry 和 grading 渲染，事件与知识使用链接下钻。报告中的每个数值都能定位到结构化字段。

## knowledge entry

`pipeline-data/knowledge/entries/{knowledge_id}.json`：

```json
{
  "schema_version": 1,
  "knowledge_id": "pkn-date-slug-001",
  "entry_type": "evaluation_result",
  "status": "pending_confirmation",
  "title": "可检索标题",
  "source": {
    "pipeline_run_id": "prun-uuid-001",
    "stage": "spec_quality_review",
    "attempt": 1
  },
  "reason_codes": [],
  "observations": {},
  "root_cause_hypotheses": [],
  "optimization_targets": [],
  "regression_cases": [],
  "evidence_refs": [],
  "recorded_at": "ISO-8601"
}
```

## 信息归属

- 原始时序事实：events.jsonl。
- 静态身份与版本：manifest.json。
- Token、时间和工具事实：telemetry.json。
- assertion、扣分和门禁：grading.json。
- 人工阅读摘要：evaluation-report.md。
- 跨 run 可复用原因与优化依据：knowledge entry。

`storage_profile: bootstrap-json-v0` 仅用于 pipeline-eval-report 建立前的历史引导 run。该 profile 的必需文件为 `manifest.json` 与 `events.jsonl`；新 run 使用完整契约并写齐五个核心文件。
