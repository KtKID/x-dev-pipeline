# DeepSeek Harness ACP 技术设计复跑

运行编号 `prun-01a1ba64-27ae-7852-8bd9-53515e164c92-001`

Luna high 完成了 V3 技术设计。请求与通知的分流在图上可直接核对。草案评审退回，主要原因是两条会话入口漏掉额外目录校验，以及结算响应早于持久化。

## 同题对照

| 检查 | V2 | V3 |
|---|---|---|
| 请求与通知 | 依赖正文区分，图缺少 `id=0` | 图按字段是否存在分流，T1 断言 `0` 原样回显和通知无响应 |
| 额外目录限制 C1 | 创建图有检查，恢复图和用例缺少对应输入 | 创建、恢复和 T2/T3 都缺少非空额外目录分支 |
| 回包与落盘 | 提议额外等待一次 flush，缺少挂起用例 | 提议收到 `agent/turn-end` 后先回包，再由 loop flush，仍缺挂起用例 |
| 图可解析 | 5/5 | 4/5。断连图的 `Agent.abort(disconnect)` 标签需要引号 |
| 正文散文字符 | 3,331 | 3,197（−4.0%） |
| 全文 Markdown 字符 | 26,348 | 27,777（+5.4%） |
| TypeScript 类型块 | 3 | 1，集中在附录 A |
| 实际 token，扣除缓存读取 | 110,830 | 128,710（+16.1%） |
| 实际 token，含缓存读取 | 715,502 | 1,125,318 |
| 子会话耗时 | 5 分 33 秒 | 6 分 25 秒 |

正文散文字符排除图、代码、表格、标题、元数据和空白。Token 取自子会话日志，覆盖读代码、推理、工具调用之间的模型请求及最终答复。这是各跑一次的观测值。

## 可核对的评审发现

- 请求图明确把有 `id` 的请求与无 `id` 的通知分开。输入错误分支仍把 JSON 无法解析和信封不合法合并，历史设计对前者规定 `-32700`。见 [V3 请求图](artifacts/tech-design.md#stdio-分帧与请求路由)。
- Spec C1 对 `session/new` 和 `session/load` 同时生效。V3 的图、参数类型及 T2/T3 都缺少非空额外目录的拒绝和状态不变断言。见 [V3 会话设计](artifacts/tech-design.md#会话所有权与请求结算)。
- 历史确认稿让 prompt 回包等到 flush 后的 idle，并用 T15 挂起 flush，观察挂起期间是否提前回包。V3 的时序图先回包再 flush，留出已回包但尚未落盘的窗口。V3 的断连设计已找到可复用的公开 `running → idle` 状态变化。见 [V3 时序图](artifacts/tech-design.md#会话所有权与请求结算) 和 [历史确认稿](../prun-01a1b509-7fed-7d41-947f-f1e16955ad5f-001/artifacts/tech-design-approved.md)。
- 断连图第 192 行的 Mermaid 标签解析失败。另四张图通过同一解析器。见 [Mermaid 校验结果](mermaid-validation.json)。

## 本轮边界

使用同一份[已确认 Spec](../prun-01a1b509-7fed-7d41-947f-f1e16955ad5f-001/artifacts/spec-approved.md)、题面、源码和确认记录。输入逐文件比对，变化只有 `x-tech-design` 的 skill 和模板。Luna 子会话从新上下文启动，工作副本中只有公开题面和设计输入，历史稿及评分留在评审侧。子会话与主会话共享宿主文件系统。

本次只执行技术设计，产物仍为待确认草案。对照以 [V2 原稿](../prun-01a1ba4e-490e-7e42-8eb6-fa8b5323d96b-001/artifacts/tech-design.md)、[V3 原稿](artifacts/tech-design.md) 和 [Luna 原始回执](artifacts/luna-receipt.md) 为准。输入、计量和评审依据见 [输入清单](input-manifest.json)、[Token 记录](telemetry.json) 和 [逐项评分](grading.json)。

原稿按字节归档，其中指向 Spec 和确认记录的相对链接沿用运行工作副本中的路径。
