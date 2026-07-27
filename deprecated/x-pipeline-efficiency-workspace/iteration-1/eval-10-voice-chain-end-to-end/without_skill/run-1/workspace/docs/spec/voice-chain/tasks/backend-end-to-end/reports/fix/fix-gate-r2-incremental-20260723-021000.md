# Gate R2 增量修复 — 20260723-021000

| # | 严重度 | 处置 | 说明 | 反例/验证 |
|---|---|---|---|---|
| issue-10 | P1 | ✅ 已修 | HTTP 客户端解析非 200 状态后立即返回策略层；响应 framing 与大小校验只约束 200 成功体，5xx 始终进入配置化重试 | `test_http_client.HttpClientTests.test_malformed_5xx_body_still_obeys_retry_policy` |

修改范围：`fixture/backend/http_client.py`、`fixture/backend/test_http_client.py`。重试次数与错误映射公开契约保持不变。
