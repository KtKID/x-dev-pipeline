# 本地 ACP v1 协议摘要

本题使用 ACP 的 stdio 传输与单会话子集。每行一个 UTF-8 JSON-RPC 2.0 对象。带 `id` 的请求得到相同 `id` 的单个响应，其中恰有 `result` 或 `error`；通知不带 `id`，也没有响应。消息换行由 JSON 字符串转义。

| 方向 | `method` | `params` / 成功结果 |
| --- | --- | --- |
| Client → Agent | `initialize` | `{protocolVersion: 1, clientCapabilities: {}}` → `{protocolVersion: 1, agentCapabilities: {loadSession: true}, authMethods: []}`；可附加真实支持的能力 |
| Client → Agent | `session/new` | `{cwd, mcpServers: []}` → `{sessionId}` |
| Client → Agent | `session/load` | `{sessionId, cwd, mcpServers: []}` → `{}`；历史通过更新通知回放 |
| Client → Agent | `session/prompt` | `{sessionId, prompt: [{type: "text", text: "hello"}]}` → `{stopReason: "end_turn"}`，另有 `max_tokens` 和 `cancelled` |
| Client → Agent | `session/cancel` | `{sessionId}`，通知 |
| Agent → Client | `session/update` | `{sessionId, update: {...}}`，通知 |

更新中的 `sessionUpdate` 为 `user_message_chunk`、`agent_message_chunk`、`agent_thought_chunk` 时，正文在 `content: {type: "text", text}`；`tool_call` 携带 `toolCallId`、`title` 和状态，`tool_call_update` 用同一个 `toolCallId` 更新 `status`，终态为 `completed` 或 `failed`。无效参数使用 JSON-RPC 参数错误，模型失败用错误响应表示。

离线模型的普通输入会返回 `Reply: <输入>`。`tool <文本>` 会调用真实工具并继续模型回合；`tool fail <文本>` 触发工具失败；`hang <文本>` 发布部分回复后等待取消；`limit <文本>` 达到输出上限；`error <文本>` 模拟提供方失败。存储目录由 `DSH_EVAL_STORAGE` 指定。夹具中的使用量仅为模拟数据。
