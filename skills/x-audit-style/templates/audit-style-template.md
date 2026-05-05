# Style Audit Report — YYYYMMDD-HHmmss

**审查范围**: <项目根 / 子目录>
**触发原因**: 手动 / 周期性

## 总览

| 严重度 | 数量 |
|--------|-----|
| P1 (强烈建议) | N |
| P2 (建议) | N |
| P3 (信息性) | N |

## P1 问题

### #1 [复用] src/foo.ts 与 src/bar.ts 有 30 行近乎重复代码
- 位置: foo.ts:42-72, bar.ts:88-118
- 建议: 提取到 src/utils/calc.ts

## P2 问题

### #1 [magic number] src/config.ts:15 用 86400 表示一天秒数
...

## P3 问题（信息性）

### #1 [死代码] src/legacy.ts:42 函数 oldHelper() 0 引用
...

## 后续动作建议

- [ ] P1 问题加入 backlog
- [ ] P2 视情况批量整理
- [ ] P3 顺便清理或忽略
