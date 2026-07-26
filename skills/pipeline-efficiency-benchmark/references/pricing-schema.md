# pricing.json schema

每个 run 在 collect 前冻结一份 `pricing.json`。价格来自执行日期可访问的官方模型价格页面；套餐账单证据来自官方套餐说明和本地 provider 记录。

```json
{
  "schema_version": 1,
  "currency": "USD",
  "model": "GLM-5.2",
  "source_url": "https://docs.z.ai/guides/overview/pricing",
  "queried_at": "2026-07-26",
  "rates_per_million_tokens": {
    "uncached_input": 1.4,
    "cached_input": 0.26,
    "cache_write_input": null,
    "output": 4.4
  },
  "cached_input_storage": "limited_time_free",
  "telemetry": {
    "cache_write_tokens": null
  },
  "billing": {
    "mode": "subscription_quota",
    "actual_cash_increment": 0.0,
    "quota_multiplier": 3.0,
    "note": "Supported-tool Coding Plan call during the recorded peak window."
  }
}
```

## 字段规则

- `model` 与 `benchmark-run.json.model` 完全一致。
- 单价统一为每 100 万 Tokens，币种由 `currency` 指定。
- `source_url` 和 `queried_at` 固定价格证据与查询日期。
- `cache_write_input` 保存官方 cache-write 单价；模型未提供该口径时使用 `null`。
- `telemetry.cache_write_tokens` 保存 provider 明确报告的 cache-write Tokens。遥测只提供 cached read 与 uncached input 时使用 `null`，报告同时生成基础 API 等价成本和“全部 uncached 均为 cache write”的上界。
- `billing.actual_cash_increment` 保存本次 run 的边际现金扣款。账单证据不足时使用 `null` 并在 `note` 写明原因。
- `billing.quota_multiplier` 保存套餐额度倍数；普通 API 使用 `null`。

## 计算口径

```text
api_equivalent
= regular_uncached_input × uncached_input_rate
+ cache_write_input × cache_write_input_rate
+ cached_input × cached_input_rate
+ output × output_rate

no_cache_api_equivalent
= all_input × uncached_input_rate
+ output × output_rate

cache_savings
= no_cache_api_equivalent - api_equivalent

quota_equivalent
= api_equivalent × quota_multiplier
```

`cache_write_tokens = null` 时，基础 API 等价成本把 uncached input 按普通单价计算；上界把全部 uncached input 按 cache-write 单价计算。
