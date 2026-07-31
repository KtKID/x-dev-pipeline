# Correctness Review 报告

> Schema: x-cr-v2
> Mode: module-review

## 不变量覆盖

| INV-ID | 来源类型 | 不变量 | 最小反例 | 结论 | 关联问题 |
|--------|----------|--------|----------|------|----------|
| INV-SPEC-01 | spec 声明 | 请求 token 必须有效 | 使用合法 token | 保持 | - |
| INV-CAND-01 | 补充候选 | 服务端从可信状态推导或校验 role、tenant_id 和 owner_id | 合法 token 携带伪造 `role=admin` 与其他 `tenant_id` | 破坏 | B1 |

补充候选与 spec 关系：`INV-CAND-01` 属于 spec 缺口。

触达路径：request JSON → token authentication → controller → query filter → data response。

## 贝叶斯根因调查

| H | 关联 INV-ID | 证据 | 更新后置信度 |
|---|-------------|------|--------------|
| H1：controller 信任客户端授权字段 | INV-CAND-01 | 查询条件直接使用 role/tenant_id | 已确认 |
| H2：authentication 只校验 token 有效性 | INV-CAND-01 | spec 与题面均只提供 token 检查 | 高 |
| H3：data layer 存在服务端租户过滤 | INV-CAND-01 | 题面未提供该 guard | 中 |

## 审查结论

| ID | 状态 | INV-ID | 检查项 | 严重度 | 置信度 | 根因分类 | 描述 |
|----|------|--------|--------|----------|--------|----------|------|
| B1 | ❌ | INV-CAND-01 | 服务端信任边界 | P0 | 高 | spec 缺口 + 实现过程偏移 | 客户端可改变授权主体和数据查询范围 |

## 问题详情

### B1: 客户端字段可改变服务端授权主体

服务端需要从已认证会话和服务端数据推导 role、tenant_id 与 owner_id，并在数据访问前完成授权。回归测试固定使用合法 token 篡改三个字段，断言请求被拒绝或伪造字段被忽略且无越权副作用。
