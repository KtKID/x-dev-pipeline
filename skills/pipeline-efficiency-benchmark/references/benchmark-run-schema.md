# benchmark-run.json schema

`normalize_run.py` 生成以下稳定结构：

```json
{
  "schema_version": 2,
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
  "cost": {
    "status": "priced",
    "currency": "USD",
    "pricing": {
      "model": "gpt-5.6-terra",
      "source_url": "https://<official-pricing-page>",
      "queried_at": "YYYY-MM-DD",
      "rates_per_million_tokens": {
        "uncached_input": 0,
        "cached_input": 0,
        "cache_write_input": null,
        "output": 0
      },
      "cached_input_storage": "unknown",
      "cache_write_tokens": null
    },
    "calculation": {
      "uncached_input": 0,
      "cached_input": 0,
      "cache_write_input": null,
      "output": 0,
      "api_equivalent": 0,
      "cache_write_upper_bound": 0,
      "no_cache_api_equivalent": 0,
      "cache_savings": 0,
      "cache_savings_pct": 0
    },
    "billing": {
      "mode": "unknown",
      "actual_cash_increment": null,
      "quota_multiplier": null,
      "quota_equivalent": null,
      "note": "账单证据说明"
    },
    "unknown_reason": null
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
- `cost.status=priced` 时必须保存官方价格来源、查询日期、单价和可复算金额。
- `cost.status=unknown` 时必须保存 `unknown_reason`；横向报告仍显示金额行。
- API 等价成本用于统一 Token 价格口径；实际现金增量与套餐额度等价金额分别保存在 `billing`。
- 同币种、同 scope 的金额可以计算算术变化；跨模型或 reasoning 的金额变化标为背景值。
- `full` 与 `spec_risk` 使用独立评分列。
- 历史重评分应作为 `full` 输入，原始旧评分保留在原 grading 文件。
