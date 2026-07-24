# benchmark-run.json schema

`normalize_run.py` 生成以下稳定结构：

```json
{
  "schema_version": 1,
  "run_id": "baseline",
  "label": "Frozen baseline",
  "iteration": "4",
  "scope": "full_pipeline",
  "model": "gpt-5.6-terra",
  "reasoning_effort": "xhigh",
  "usage": {
    "convention": "cached_input_is_subset_of_input",
    "input_tokens": 0,
    "cached_input_tokens": 0,
    "uncached_input_tokens": 0,
    "output_tokens": 0,
    "reasoning_output_tokens": 0,
    "total_tokens": 0,
    "effective_tokens": 0,
    "cached_share_of_input_pct": 0
  },
  "duration": {
    "main_active_seconds": null,
    "nested_reviewer_seconds": null,
    "executor_time_sum_seconds": null
  },
  "calls": {
    "tool_calls": null,
    "llm_calls": null,
    "failed_commands": null
  },
  "scores": {
    "full": null,
    "spec_risk": null
  },
  "phases": [],
  "measurement": {}
}
```

## 比较规则

- `scope` 相同才能计算总量降幅。
- `usage.convention` 相同才能计算 Token 降幅。
- `null` 表示原始遥测未保存该指标；比较报告保留缺失值。
- `full` 与 `spec_risk` 使用独立评分列。
- 历史重评分应作为 `full` 输入，原始旧评分保留在原 grading 文件。
