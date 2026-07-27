# Changelog

| 时间 | 操作 | 内容 |
|---|---|---|
| 2026-07-24 | 版本隔离 | 将 iteration-6 的全部 skills 原样复制到 iteration-7，并把 iteration-6 固定为只读基线。 |
| 2026-07-24 | 开始开发 | 按 OpenSpec tasks 2.1 至 4.5 实现最小错题格式、离线 parser、向量召回 CLI 和 skill 接入。 |
| 2026-07-24 | 模型边界 | Embedding 后端改为延迟加载和 `local_files_only=True`；模型下载与真实 Smoke 交给用户后续完成。 |
| 2026-07-24 | 测试通过 | iteration-7 的 parser、CLI、来源兼容和 skill 接入共 25 个离线测试通过。 |
| 2026-07-24 | 验证准备 | 生成 dev-report，进入 Gate ① 事实复跑与 Gate ② 默认线综合评审。 |
| 2026-07-24 | Gate ① 通过 | 独立验证 agent 原样复跑 dev-report 六条命令，6/6 通过；真实模型 Smoke 保留为 manual。 |
| 2026-07-24 | Gate ② 第 1 轮 | RC 发现参数解析 JSON 契约、x-req3 轮次描述和失败路径测试覆盖问题，进入第 1/3 轮批量修复。 |
| 2026-07-24 | 批量修复 | 接管 argparse 错误输出、统一 x-req3 五轮交接，并把离线测试扩展到 34 个。 |
| 2026-07-24 | Gate ② 通过 | 同一 RC reviewer 增量复审确认 F1-F3 已修、无新增 P0/P1；fix-counter 重置为 0。 |
| 2026-07-24 | 模型确定 | 默认模型切换为 `Qwen/Qwen3-Embedding-0.6B`；查询使用 `query` prompt，错题按普通文档编码。 |
| 2026-07-24 | 模型下载 | 固定 revision `97b0c614...` 下载到 iteration-7 独立目录；权重长度与 SHA-256 均通过校验。 |
| 2026-07-24 | 真实 Smoke | uv 隔离环境成功加载本地模型，已知日志恢复查询 Top1 返回 `A-risk-003`；离线测试扩展到 37 个。 |
| 2026-07-24 | Gate ② 增量复审 | RC 确认 Qwen 模型增量无 P0/P1，并登记 F5 P2 文档状态同步。 |
| 2026-07-24 | F5 同步 | proposal 与 design 更新为模型已下载、已校验并通过真实 Top1 Smoke。 |
| 2026-07-24 | Gate ② 通关 | 同一 RC 定点确认 F5 已关闭、无新增发现；Gate① 8/8、Gate② pass、fix-counter 为 0。 |
