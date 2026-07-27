# 幂等重试 Risk Top1

## 基线状态

**污染，禁止进入有效对比结论。** 执行期间的范围过宽检索意外暴露了目标 Skill 的少量元数据；真实向量查询使用 `x-adversarial-risk/scripts/risk_retrieve.py` 完成。

## 查询

```text
关键词：幂等请求、request_id、失败重试、唯一业务副作用、去重标识
Risk：请求在持久化业务结果前失败时，如果系统提前占用 request_id，同一 request_id 的合法重试可能被拒绝；如果未正确复用历史结果，也可能产生重复业务副作用。
TopN：1
```

## 执行事实

- 输入：`retry-spec.md`
- 语料：指定的 `risk-mistakes.md`
- 检索：本地 Qwen Embedding 实时向量计算
- 工具：`x-adversarial-risk/scripts/risk_retrieve.py`
- 依赖：离线 uv 缓存
- 退出码：`0`
- 返回数量：`1`
- Top1 ID：`A-risk-004`

## 命中正文

```text
关键词：幂等请求、失败重试、请求历史、去重标识
Risk：失败请求提前占用幂等标识时，同一标识的后续合法请求可能被错误拒绝或丢失应产生的唯一副作用。
```

## 用途

用该错题检查幂等状态机的占位时机和失败状态：

- 业务结果持久化成功后才能把 `request_id` 固化为已完成。
- 业务结果产生前的失败状态需要允许同一 `request_id` 合法重试。
- 重试完成后只保留一次业务副作用。
