# 变更记录

| 时间 | 操作 | 内容 |
|------|------|------|
| 2026-07-25 | 开始开发 | 冻结 iteration-7 当前 spec3 契约和 dirty-tree 基线，开始实现独立 validator |
| 2026-07-25 | 核心实现 | 新增 `tools/spec.py`，让 xdev/req3 委托单一 spec3 引擎 |
| 2026-07-25 | 下游同步 | bundled runtime 增加 `spec.py`，更新 manifest、迁移清单和 benchmark 测试 |
| 2026-07-25 | 审查修正 | 修复 failed RAG、no-corpus/RAG 矛盾、空 assumption、fenced 示例、模板占位符和 sidecar 漏报 |
| 2026-07-25 | 完成验证 | 仓库 226 项、iteration-7 48 项、benchmark 4 项通过；综合 reviewer pass |
