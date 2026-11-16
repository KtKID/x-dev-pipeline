# 在编辑器创建 DeepSeek 助手会话 · 技术设计

> 功能依据：[spec.md](spec.md) · feat01，本轮基线 SHA256 `c0be21094ab0d67bd4d661190d1642341afee60982ec34be4755a8e664eacb38`；场景与 C1、C2、C8 来自本轮确认 Spec。
> 设计状态：待用户确认 · 草案 v1
> 本轮 feat：feat01「创建会话」；仅覆盖 `session/new`

## 范围与模块边界

| feat | 涉及入口和模块 | 本轮改动边界 |
|---|---|---|
| [feat01](spec.md#feat01-创建会话) · 场景1–5 | Harness `packages/acp/src/index.ts` 的 `apply(ctx, { model })` ACP 入口；`ctx.sessions`、`ctx.agents`/AgentLoop 工厂及已配置的 JSONL 持久化服务 | 在真实 ACP stdio 入口实现初始化后的 `session/new` 请求及进程内会话绑定。复用已有 Agent、Session、存储服务；ACP 层管理每进程单会话的占用与回滚。保持 `session/prompt`、`session/load`、取消和历史回放为各自 feat，不在本轮扩展其行为。Harness 实际 checkout 为 [`deepseek-harness`](../../../../agent/deepseek-harness)；实现路径以 PROMPT 指定的 `task/packages/acp/src/index.ts` 为该题内路径。 |

ACP 传输、JSON-RPC 消息和方法参数以[本地协议摘要](../../../evals/problems/deepseek-acp/eval-support/PROTOCOL.md)为准；真实初始化与服务装配见[固定 Eval 入口](../../../evals/problems/deepseek-acp/eval-support/start.ts)。`stdout` 仅输出协议消息，诊断信息写 `stderr`。

## 必须遵守的技术约束

| 规则 | 适用入口与必须满足的结果 | 依据与状态 |
|---|---|---|
| D01 请求协议与初始化 | `initialize` 协商 protocolVersion 1、声明 `loadSession: true`、`authMethods: []`。初始化完成后 `session/new` 接收 `{cwd, mcpServers: []}`，成功响应为 `{sessionId}`，JSON-RPC 响应 ID 与请求 ID 一致。参数无效返回请求错误；协议流保持一行一消息。 | [PROTOCOL.md](../../../evals/problems/deepseek-acp/eval-support/PROTOCOL.md)、[PROMPT.md](../../../evals/problems/deepseek-acp/PROMPT.md)。协议边界的校验须使用权威 schema/类型定义；若 ACP 包尚无权威 schema，本轮新建单一 schema 并由其推导 TS 类型，避免另写平行 DTO。待实现验证。 |
| D02 作用域与空闲状态 | 创建仅接受启动目录的绝对 `cwd`；`mcpServers` 必填且为空，`additionalDirectories` 可缺省或为空，非空则拒绝。初始化已完成且进程空闲才能开始；进程至多承接一个会话。参数拒绝不占槽位；创建进行中及成功后，第二次创建均返回请求错误，且首个创建/原会话保持有效。 | Spec C1、C2；[PROMPT.md](../../../evals/problems/deepseek-acp/PROMPT.md)。启动目录取 Harness 进程启动时确定的工作目录。待实现验证。 |
| D03 就绪与 ID 绑定 | 创建成功回包前，Agent 与 Session 已在当前进程建立；回包 `sessionId` 等于 `Agent.session.header.id`，并可由 `ctx.sessions.get(sessionId)` 查到该 Session。`Agent.id` 是独立注册标识。新会话为空，不调用模型；成功只承诺当前进程立即可用。 | Spec 场景1、C8；冻结源码 `packages/agent-loop/src/index.ts` 的 `createAgent()` 接受调用方 `sessionId`，`packages/session/src/index.ts` 的 `SessionStore.create()` 建立内存 Session。待在新 ACP 入口验证。 |
| D04 延后保存与数据归属 | 会话事件日志由 `ctx.sessions` 中的 Session 唯一持有；已有 JSONL persistence 监听会话创建/事件并按其既有懒保存策略落盘。创建空会话不主动 flush/创建持久化副本；回包不等待磁盘持久化。首轮成功保存后的可恢复承诺属于 C8 后续交互边界，本轮只验证创建未提前保存。 | Spec C8；冻结源码 `packages/session/src/index.ts`（store 注释说明 persistence 订阅事件/flush/dispose）、`packages/session-persistence-jsonl/src/index.ts`（监听创建与事件，按需核对实际写入时机）。待实现验证；不改变持久化策略。 |
| D05 失败回滚与重试 | 任一创建失败均返回一次错误，释放创建中的占用，并清理本次已创建的临时 Agent/Session 状态；同一进程随后可重试成功。失败结果不返回可用 ID、不留下阻塞单会话槽位或孤立活动 Agent。 | Spec 场景5；冻结源码 `packages/session/src/index.ts` 的 `SessionStore.create()` 将 store 注册置于 Cordis effect 并在 dispose 时移除；`packages/agent-loop/src/index.ts` 的 `createAgent()` 先校验 agent ID 再创建 Session。待实现验证。 |
| D06 模块及规范边界 | ACP adapter 依赖 ACP 协议、Agent/Session 的公开服务契约；不得直接修改 JSONL 文件或复制存储状态。边界校验、状态占用、创建、回滚到响应的链路需可追踪。 | `skills/x-tech-design/references/development-rules.md` R1、R2、R4、R5、R7；固定提交源码核对。代码评审检查依赖方向、协议单一来源、session ID 一致及失败清理。 |

## 验证状态与交接

Smoke T1 在隔离测试子进程中装配真实 Harness 服务并调用真实 `apply`。探针通过公开服务观察进程内的 Agent 和 Session，观察结果走测试夹具的独立通道，stdout 保持协议纯净。沿用给定的 [Eval 启动入口](../../../evals/problems/deepseek-acp/eval-support/start.ts)做纯协议复核。

本轮已核对冻结版源码，所有 T 用例待实现验证。交给 x-req 的 Smoke 编号为 T1。开发交付时将请求与回包、探针和存储观察结果收录到统一测试报告。

## 附录 A：协议、结构与配置

本轮新增/消费的公开 ACP 契约仅为 `session/new`：

- 请求参数：`{ cwd: string, mcpServers: [], additionalDirectories?: [] }`。`cwd` 必须等于进程启动目录且为绝对路径。
- 成功结果：`{ sessionId: string }`。该值等于 `Agent.session.header.id`，并能通过 `ctx.sessions.get(sessionId)` 找到真实 Session；`Agent.id` 是独立的注册标识。
- `mcpServers` 为必填空数组；`additionalDirectories` 可缺省或为空数组，非空时返回参数错误。
- 无效参数、占用中或已有会话、底层创建失败：返回 JSON-RPC 请求错误；错误不得带成功 `result`，失败创建不得占用后续重试位置。
- 当前持久化保证：沿用 Harness 已配置的 JSONL 懒保存；空会话创建不触发显式保存。跨重启恢复不属于本 feat。

参数错误与忙状态的具体错误码沿用 ACP 项目权威定义；如该定义尚未覆盖忙状态，由实现补充符合 JSON-RPC error shape 的请求错误，并保持单一协议 schema。

## 附录 B：测试用例与覆盖矩阵

| 用例、依据及目的 | 准备数据与操作 | 通过条件 | 测试层级、执行入口及状态 |
|---|---|---|---|
| T1 **Smoke** · feat01 场景1、C2、C8。创建真实可用空会话并核对懒保存 | 用临时 `DSH_EVAL_STORAGE` 启动测试夹具，通过 stdio 完成 `initialize` 和合法 `session/new`。探针读取 `ctx.agents.list()`、`ctx.sessions.get(sessionId)` 和 `ctx.sessions.list()`。 | 响应关联原请求 ID。回包中的 `sessionId` 对应唯一 live Session 和绑定它的空闲 Agent，`header.cwd` 等于进程启动目录。模型调用数和已保存会话数均为零。可选 prompt 联调时另查 `session/update.sessionId` 和离线模型的回复。 | 探针 Smoke 和原入口纯协议复核，待实现验证。 |
| T2 · feat01 场景2、C1；无效参数拒绝且不占槽 | 独立子进程分别提交相对 cwd、非启动目录 cwd、非空 `mcpServers`、`additionalDirectories: ["/tmp/other"]`；每次错误后同一进程提交合法请求（`mcpServers: []`，`additionalDirectories` 缺省或空）。 | 每个越界请求返回 JSON-RPC error；随后合法请求成功并满足 T1 的 ID/Session 绑定判据。无效请求不触发持久化、不产生会话占用。 | 真实入口协议测试；待实现验证。 |
| T3 · feat01 场景3、C1；创建期间拒绝重复 | 使首个创建请求可控地保持进行中（可注入延迟创建依赖），首个未完成时发送第二个合法请求。 | 第二请求返回 error；首请求继续成功且只绑定一个唯一 ID，无重复活动会话。 | ACP adapter 并发/真实入口测试；待实现验证。 |
| T4 · feat01 场景4、C1；成功后拒绝再次创建 | 同一真实入口先成功创建，再提交合法 `session/new`；用公开 Agent/Session 探针检查原 ID。 | 第二次返回 error；原回包 ID 仍等于已启动 Agent 的 `session.header.id`，`ctx.sessions.get(id)` 返回原 Session，live Session 数仍为1。 | 真实入口协议测试；待实现验证。 |
| T5 · feat01 场景5；占用已建立后失败并在原进程重试 | 故障注入至少发生在创建槽已占用且临时 Agent 或 Session 已建立之后；同进程触发失败，观察公开 Agent/Session 列表，再解除故障并提交合法创建。 | 首次只有 error、无成功 ID；临时资源从公开列表消失且槽位释放；重试成功，并满足 T1 的 ID/Session 绑定判据。不得留下孤立 Agent、Session 或持久化会话文件。 | ACP 适配器故障注入 + 公开服务探针；待实现验证。 |

覆盖：场景1→T1；场景2→T2；场景3→T3；场景4→T4；场景5→T5；C1→T2–T4；C2、C8→T1。

## 附录 C：设计依据与确认

- [Spec](spec.md)：本轮基线 SHA256 `c0be21094ab0d67bd4d661190d1642341afee60982ec34be4755a8e664eacb38`；feat01、场景1–5、C1/C2/C8。本设计不承接其它 feat。
- [Eval PROMPT](../../../evals/problems/deepseek-acp/PROMPT.md)：本地子进程入口、初始化/会话范围、无认证与离线 Harness 要求。
- [ACP 协议摘要](../../../evals/problems/deepseek-acp/eval-support/PROTOCOL.md)与[固定服务入口](../../../evals/problems/deepseek-acp/eval-support/start.ts)：线上协议字段和 Smoke 入口。
- 冻结 Harness 源码核对：仓库 `/Volumes/machub_app/proj/agent/deepseek-harness`，固定提交 `add59a3336f0ab61c55499418081aab76cb550f8`；路径/符号：`packages/agent-loop/src/index.ts` `AgentLoop.createAgent()`、`resume()`、`start()`；`packages/session/src/index.ts` `SessionStore.create()`、`get()` 及持久化职责注释；`packages/session/src/types.ts` `SessionHeader.cwd`、事件追加的 JSON 可序列化约束；`packages/session-persistence-jsonl/src/index.ts` JSONL 插件。源码已通过 `git show <固定提交>:<路径>` 只读核对。该固定版根目录没有 `task/` 子目录，也没有 ACP adapter；ACP 实现入口按 Eval 题面约定映射到题目交付树 `task/packages/acp/src/index.ts`。本设计不依据该仓库当前 HEAD 的 ACP/存储实现。
- 用户确认依据：本轮明确选择沿用 Eval 懒保存，且创建成功后 ID 在当前进程立即可用；已反映于 Spec C8。创建错误后的回滚边界依据 Spec 场景5及 Eval 范围。
- 待用户确认：D05 将“失败时清理部分资源并释放槽位”作为技术实现边界；验收用例使用一次性创建故障验证原进程重试。其它内部状态结构与资源清理实现由开发模型决定。
