# {{title}}

## 判定

- `pipeline_run_id`：`{{pipeline_run_id}}`
- Run 类型：`{{run_kind}}`
- Source Session：`{{source_session_id}}`
- Phase：`{{phases}}`
- 执行终态：{{execution_outcome}}
- 质量门禁：{{quality_gate}}
- accepted delivery：{{accepted_delivery}}
- 下一阶段：{{next_stage}}

{{run_identity_explanation}}

## 质量

| 指标 | 当前 run | Baseline | 可比性 |
|---|---:|---:|---|
| 功能/语义分 | {{semantic_score}} | {{baseline_semantic_score}} | {{quality_comparability}} |
| 结构分 | {{structure_score}} | {{baseline_structure_score}} | {{quality_comparability}} |
| Scenario | {{scenario_count}} | {{baseline_scenario_count}} | 描述性 |

### P0

{{p0_findings}}

### P1

{{p1_findings}}

### 有效设计

{{positive_findings}}

## Token 与耗时

```text
总 Token = Input {{input_tokens}}
          + Output {{output_tokens}}
          + Reasoning {{reasoning_tokens}}
          + Cache Read {{cache_read_tokens}}
          + Cache Write {{cache_write_tokens}}
          = {{total_with_cache}}
```

| 指标 | 数值 |
|---|---:|
| 非缓存读取 Token | {{total_without_cache_read}} |
| 含缓存读取 Token | {{total_with_cache}} |
| 成本 | {{cost_usd}} |
| Prompt → final | {{prompt_to_final_seconds}} 秒 |
| Session lifecycle | {{session_lifecycle_seconds}} 秒 |
| 工具调用 / 失败 | {{tool_calls}} / {{tool_failures}} |
| 用户追加消息 | {{user_followup_messages}} |
| 样本污染 | {{tainted_state}} |

### Phase Token

{{phase_table}}

{{telemetry_comparability_note}}

## 归因与知识

- 最早责任阶段：{{origin_stage}}
- 发现阶段：{{detected_stage}}
- Reason codes：{{reason_codes}}
- 知识条目：{{knowledge_refs}}
- 固定回归 case：{{regression_cases}}

## 下一门禁

{{next_gate}}

## 审计引用

- Manifest：`manifest.json`
- Events：`events.jsonl`
- Telemetry：`telemetry.json`
- Grading：`grading.json`
- 被评产物与 hash：{{artifact_refs}}
