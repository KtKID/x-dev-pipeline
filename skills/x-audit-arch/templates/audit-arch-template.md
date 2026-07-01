# Architecture Audit Report — YYYYMMDD-HHmmss

**Completed by model:** <actual model id>
**审查范围**: <项目根 / 子目录 / 指定模块>
**触发原因**: 手动 / 大里程碑 / 重构后

## 总览

| 严重度 | 数量 |
|--------|-----|
| P1 (架构债，强烈建议修) | N |
| P2 (建议修) | N |
| P3 (信息性) | N |

> 主线分布（便于用户快速定位最关心的两条）：
>
> | 维度 | P1 | P2 | P3 |
> |------|----|----|----|
> | 架构一致性 | N | N | N |
> | 单一事实源 | N | N | N |
> | 抽象合理性 | N | N | N |
> | 契约清晰度 | N | N | N |
> | 依赖健康 | N | N | N |

## P1 问题（架构债，强烈建议修）

### #1 [单一事实源·已漂移] 订单状态枚举在 3 处各定义一份且值已不一致
- 副本位置:
  - `src/order/status.py:12` → `{PENDING, PAID, SHIPPED}`
  - `src/api/schema.ts:30` → `{pending, paid, shipped, refunded}`（多了 refunded）
  - `docs/api.md:88` → 仍写 3 个状态
- 漂移证据: TS 侧已新增 `refunded`，Python 与文档未同步，调用方按文档传值会被拒
- 当前在哪 / 应该在哪: 应以一个权威源（建议 `src/order/status.py`）为准，TS/文档派生或校验同步
- 影响维度: 单一事实源

### #2 [架构一致性·破坏分层] 数据访问层反向依赖表现层
- 依赖路径: `src/repo/user_repo.py` → import `src/web/session.py`
- 当前在哪 / 应该在哪: 会话信息应由上层注入，repo 不应感知 web 层
- 影响维度: 架构一致性

## P2 问题（建议修）

### #1 [架构一致性·模块归属] 业务规则写进了工具层
- 位置: `src/utils/format.py:55` 含订单折扣计算逻辑
- 当前在哪 / 应该在哪: 折扣是领域规则，应在 `src/order/` 而非通用 utils
- 影响维度: 架构一致性

### #2 [契约清晰度] 公开接口大量裸 dict 传递
- 位置: `src/service/agent_loader.py:load()` 返回 `dict`，调用方各自猜字段
- 建议: 收敛为 `AgentConfig` 数据类，契约显式化
- 影响维度: 契约清晰度

## P3 问题（信息性）

### #1 [抽象合理性] 只有一个实现的策略接口
- 位置: `src/strategy/base.py` + 唯一实现 `default.py`
- 判据「删了谁会坏」: 无第二实现、无扩展计划 → 可内联
- 影响维度: 抽象合理性

## 后续动作建议

- [ ] P1 架构债加入 backlog，优先处理已漂移的单一事实源问题
- [ ] P2 结构问题排期，结合下次相关模块改动一并收敛
- [ ] P3 仅记录，视情况顺手清理
- [ ] 结构性改动须经人类裁决后再走 x-fix，本报告不自动触发修复
