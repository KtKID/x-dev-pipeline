# Performance Audit Report — YYYYMMDD-HHmmss

**审查范围**: <项目根 / 子目录>
**触发原因**: 手动 / 大里程碑

## 总览

| 严重度 | 数量 |
|--------|-----|
| P0 (生产风险) | N |
| P1 (建议优化) | N |
| P2 (信息性) | N |

## P0 问题

### #1 [N+1] src/order_service.ts:42 在 forEach 里查数据库
- 上下文: ...
- 影响: 100 个订单触发 100 次 SQL
- 建议: 用 IN 查询批量取

## P1 问题

### #1 [O(n²)] src/match.ts:88 双层 for + indexOf
...

## P2 问题（信息性）

### #1 [缓存机会] ...

## 后续动作建议

- [ ] 把 P0 问题加入 backlog
- [ ] P1 问题排期
- [ ] P2 仅记录，不必处理
