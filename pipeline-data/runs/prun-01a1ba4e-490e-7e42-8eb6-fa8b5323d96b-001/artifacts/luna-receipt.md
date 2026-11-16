技术设计草稿已写入 [`tech-design.md`](/private/tmp/dsh-acp-tech-replay.fai1bp7a/workspace/task/docs/spec/acp-editor/tech-design.md)，大小 44,364 字节。覆盖了结构与数据归属、会话和 prompt 生命周期、协议字段、验证安排及全部 Spec 场景的用例索引；状态标为“待用户确认”。

自检确认 Spec 哈希仍为 `ff4a5d3f…d7df942`，Spec 未改动。本轮未运行测试、未改源码。

待确认事项包括：R2 要求 Zod，但仓库未提供该依赖；prompt 响应前重复等待 `session/flush` 的行为与失败语义；EOF 清理时 Agent/Session 的 disposer 归属；以及本地协议摘要未覆盖的完整 ACP 字段细节。
