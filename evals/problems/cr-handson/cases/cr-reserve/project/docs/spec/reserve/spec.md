# reserve：预约

> spec：reserve
> 主要入口：src/library/reserve.py、src/library/api.py
> 状态：在用

## 关键约束（用户已确认）

| 编号 | 约束与适用范围 | 可观察判据与禁止结果 | 确认依据 / 关联场景 |
|---|---|---|---|
| C1 | 每位读者同时最多预约 3 本 | 已有 3 个有效预约时再预约，抛 ReserveLimitError | 用户 2026-09-01；feat01 |

## feat01: 预约

> 状态：已验收

场景1: 有库存的书不能预约
- GIVEN 书在馆、有可借副本
- WHEN 读者预约这本书
- THEN 拒绝，抛 AvailableError，提示直接借

场景2: 没库存时预约成功
- GIVEN 书的副本都已借出
- WHEN 读者预约
- THEN 生成一条预约

## feat02: 取消预约

> 状态：已验收

场景1: 只能取消自己的预约
- GIVEN 读者 A 登录
- WHEN A 通过接口取消读者 B 的预约
- THEN 拒绝，抛 PermissionError，预约还在
