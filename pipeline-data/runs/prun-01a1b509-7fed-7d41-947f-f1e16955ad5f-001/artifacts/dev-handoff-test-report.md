# task-acp-editor-bridge · 代码改动测试报告

> 任务记录：[dev-checklist.md](../../../../docs/spec/acp-editor/tasks/task-acp-editor-bridge/dev-checklist.md)
> 批次：20261107-01
> 比较基线：本地 Git `358e455`（eval-baseline、无 remote）；本批交付代码为 baseline 加当前 ACP bridge 与测试文件。
> 已确认需求基线：Spec `ff4a5d3fb04e6bbe7ece2b989537303e5756a6c50408c311c4fbed066d7df942`。Tech Design 批准内容基线 `9c56f3b52d0b2311ea68e74e0e99a9c99ae7a6669cb589afdeec15ae6e943048`；当前文件另有确认来源记录元数据。T1–T15 主定义见 `docs/spec/acp-editor/tech-design.md`。

## 本次结果

- 范围：新建 `packages/acp/src/index.ts` bridge 与 `packages/acp/tests/index.spec.ts` 集成测试；`eval-support/` 初始文件 SHA-256 在末尾复核，文件内容保持一致。
- 最终 ACP 验证 E007：Node 24.14.0、离线 tsx、真实 `eval-support/start.ts` 子进程，15 项通过、失败 0、跳过 0。E001 保留实现前有效红灯，原因是指定 bridge 文件缺失。
- E004 曾在测试后附加 zsh `PIPESTATUS` 断言命令上失败（测试 runner 输出 15/15 通过）；E005 使用直接退出码采集，退出码 0。
- 项目既有 session 回归尝试 E006 退出 1，原因是离线工作区缺少 `vitest` 包，测试文件未启动。TypeScript 静态类型检查未执行：工作区提供 tsx，不含 typescript / tsc。此限制不影响 E005 的 Node 运行时与真实 Harness 子进程链路证据。

## 用例明细

| 用例 | 准备与操作 | 预期和实际观察 | 结果与证据 |
|---|---|---|---|
| T1 / T11 / T14 | 真实子进程 initialize 支持版本、合法不支持版本、格式错误版本；发送畸形 JSON、未知 method 请求和通知；解析 stdout。 | 合法版本协商返回 1；格式错误 -32602；parse error -32700；未知 method -32601；notification 无响应；stdout 仅有可解析协议对象。 | 通过 E007；`packages/acp/tests/index.spec.ts` 前 3 项。E001 是实现前缺模块红灯。 |
| T2 / T12 | 相对 cwd、异工作目录、非空 MCP、非空额外目录、unknown load、JSONL cwd 篡改、双 valid new、双 load 重叠及已占槽位请求。 | 非法参数 -32602；首次无效操作不占槽；同进程并发只允许一个槽位；load 的元信息 cwd 不匹配时拒绝；成功操作保留会话。 | 通过 E007；第 4–8 项，真实 AgentRegistry 和 JSONL backend。 |
| T3 | 进程 A 完成 prompt；进程 B 同 ID load，观察 replay 和 generate 次数；续接 prompt 后立即读取 JSONL。 | 历史用户/思考/body 增量先于 load result；load 不调用模型；续问调用模型一次；收到 prompt response 时 JSONL 已含 `turn/end`。 | 通过 E007；第 7 项，双进程真实持久化恢复。 |
| T4 / T13 | 两个文本块顺序输入；`tool echo` 与 `tool fail` 走真实工具注册与执行；收集 update 和 prompt response。 | 用户块按顺序更新；body 分段送达、thought 独立；工具状态使用同 `toolCallId`，分别 completed/failed；工具失败后模型继续到 end_turn；所有流更新先于响应。 | 通过 E007；第 9–10 项。离线模型固定 chunk 形状。 |
| T5 / T6 | 空数组、空文本、文本后跟图片、unknown session；hang prompt 后提交第二 prompt，再取消首条。 | 无效 prompt -32602，不产生部分入队；活动期间第二 prompt -32602，事件日志没有第二条输入。 | 通过 E007；第 12 项，真实离线 fixture event log。 |
| T7 | normal、`limit`、`error` 三类提示，检查响应与此前 updates。 | normal 为 end_turn；输出上限为 max_tokens；模型失败为 RPC error；错误前已发送的流更新保留。 | 通过 E007；第 11 项。 |
| T8 / T9 | 活动 hang 通知取消两次；后续正常 prompt；另测未知及空闲会话取消。 | 活动 prompt 只以 cancelled 响应一次，底层 aborted 事件一次；取消后可继续；未知/空闲取消无响应且会话可用。 | 通过 E007；第 13–14 项。 |
| T10 | hang prompt 发出增量后关闭 stdin，等待子进程退出并读取 fixture event。 | EOF 触发底层 abort；子进程等待回收后退出；stdout 无畸形行或断开后协议写入。 | 通过 E007；第 15 项，等待上限 3 秒。 |
| T15 | 发送正常 prompt，响应前后检查真实 JSONL 日志。 | 结算响应前持久化包含 `turn/end`。 | 通过 E007；T3 恢复测试在收到续问响应后读取 JSONL。 |

**场景与约束映射**：feat01 场景1→T1；场景2→T2；场景3→T3。feat02 场景1→T4/T13/T15；场景2→T5；场景3→T6。feat02 场景4与 feat03 场景1→T7/T8；feat03 场景2→T9；场景3→T10。C1–C8 依 checklist 行分配由以上用例对应，分配与主定义见 checklist / Tech Design 附录 B。

## 改动覆盖率

命令：`/opt/homebrew/opt/node@24/bin/node --experimental-test-coverage --test-coverage-include=packages/acp/src/index.ts --import tsx --test packages/acp/tests/index.spec.ts`。执行编号 E007；Node 内建覆盖采集映射回 TypeScript 源路径。最终执行编号 E007。`index.ts` 是新增文件，因此全文件数据也是该实现文件改动可执行代码的覆盖率。覆盖数据及完整原始输出见 `evidence/coverage/E007/` 和 `evidence/E007-raw.txt`。

| 文件 | line | branch | function | 未覆盖源码行 |
|---|---:|---:|---:|---|
| `packages/acp/src/index.ts` | 93.54% | 81.20% | 93.18% | 58–62、72、89、100–103、138–141、161–165、171、174–175、248–249、263–264、268、317–319、341–343、361 |
| `packages/acp/tests/index.spec.ts` | 排除 | 排除 | 排除 | 测试代码是验证夹具，不计入业务改动覆盖率；断言由 Node runner 实际执行。 |

相关分支覆盖采用 Node 全文件分支统计，新增源文件等于改动范围。未覆盖位置主要为 schema/错误格式防线、生命周期失败及替代分支；正常路径、规定的协议拒绝、工具成功/失败、取消和 EOF 路径已有运行证据。未达到全分支覆盖的分支在本报告保留，不作为需求未覆盖的替代判断。

## 执行证据

- E001：实现前 red；命令、cwd、基线、错误输出见 `evidence/execution.log`。
- E002/E003：开发中 T1 与 T1–T3 结果；见 `evidence/execution.log`。
- E004：coverage runner 15/15 通过；zsh 后置 `PIPESTATUS` 检查语法失败，原始 stdout 在 `evidence/E004-raw.txt`。原生数据写入 `evidence/coverage/E004/`。
- E005：最终 coverage + ACP test；Node 退出码 0，15/15 通过；完整输出 `evidence/E007-raw.txt`，原生 coverage JSON `evidence/coverage/E007/`。
- E006：尝试既有 session suite：`/opt/homebrew/opt/node@24/bin/node --import tsx --test packages/session/tests/session.spec.ts`；cwd `task/`；退出码 1，启动时 `ERR_MODULE_NOT_FOUND: Cannot find package 'vitest'`。原始完整错误须由本段命令复现；本次无网络安装。
- 静默检查：`git diff --check`，退出码 0，标准输出/错误输出为空；结果见 `evidence/execution.log` 最终收尾记录。

## 验收结论与限制

- x-dev：5/5 行 🟢；ACP 15/15 通过。高风险 T2–T5 均通过真实 Harness 子进程与实际 JSONL/fixture 路径验证。
- x-verify-spec、x-verify-tech、x-qa-gate：待执行，回执在阶段结束后追加。
- 既有 Vitest 回归因依赖缺失未执行；静态类型检查未执行。离线环境不允许增加包或联网安装。

## 附件

- 原始命令和早期执行记录：[`evidence/execution.log`](evidence/execution.log)
- 最终 ACP 输出：[`evidence/E007-raw.txt`](evidence/E007-raw.txt)
- 覆盖率原始 JSON：`evidence/coverage/E007/`
- 初始 `eval-support/PROTOCOL.md` SHA-256 `3121d4004c824a1816f0a42030df9196aff15261067ca9681775b07631e14038`；`eval-support/start.ts` SHA-256 `08d3ec3c22cec68d0b291ecb6d43e86321c8e122dfb33c808dc6be02371d4551`。交付末尾核验结果见 execution.log。
