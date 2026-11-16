# 给 DeepSeek Harness 增加 ACP 编辑器入口

我想让支持 Agent Client Protocol（ACP）的编辑器通过本地子进程驱动 DeepSeek Harness：创建会话、发送消息、实时看到回复和工具状态、取消正在运行的提示，以及在重启进程后恢复上一段会话。

`task/` 是给定版本的真实 Harness 源码，所有项目修改都在这里做。沿用现有的 agent、工具和会话持久化；以 ACP v1 的 JSON-RPC 2.0 换行分帧走 stdin/stdout，stdout 只承载协议消息。日志可写 stderr。

- `initialize` 协商版本 1，声明可加载会话；提示内容只支持文本。此本地入口无需认证。每个进程只拥有一个会话，`session/new` 和 `session/load` 都要求 `cwd` 为启动目录的绝对路径，MCP 服务留空。非空额外目录、并发第二次创建或加载，以及未知、跨工作目录的加载，返回请求错误。
- `session/prompt` 接受有内容的文本块，按原顺序送进真实 Agent。空提示、混入非文本块或未知会话返回请求错误；被拒绝的请求不提交部分输入。Agent 的正文增量与公开思考增量分流；工具开始与终结状态用同一调用 ID，区分成功和失败。应有的更新先到，再结算该请求。正常结束为 `end_turn`、达到输出上限为 `max_tokens`、模型失败为 RPC 错误。
- 同一个会话只接受一个未完成的 prompt。对正在执行的 prompt 发 `session/cancel` 通知，应取消底层工作，让原请求以 `cancelled` 结算一次；未知或空闲会话的取消不影响正常请求。取消结束后可以继续提问。客户端断开后回收正在运行的工作。
- 会话保存在现有 JSONL 存储中。一次正常完成的会话在新进程中通过同一 ID 加载，先回放历史用户和助手更新，再返回加载成功；加载历史不会再次调用模型，下一轮可以继续。图片、MCP、审批交互、多会话及模型设置超出本题范围。

接入位置为 `task/packages/acp/src/index.ts`：导出 `apply(ctx, { model })`，由 `task/eval-support/start.ts` 提供真实 Harness 服务和离线模型。可自选内部设计。验收入口：在 `task/` 下运行 `node --import tsx eval-support/start.ts`。请保留给定的 `eval-support/`。依赖由运行环境事先准备；使用随包提供的本地源码、依赖和协议摘要。

按 `skills/README.md` 提供的本地 pipeline 执行：规格与技术设计分别提交确认，再拆任务、实现、验证和交付。确认回复由本题操作者提供，收到后记录其覆盖的内容版本。风险复核和修复按实际需要触发。交付代码、可复跑测试、阶段产物和简短回执，链接测试结果与失败或未覆盖范围。
