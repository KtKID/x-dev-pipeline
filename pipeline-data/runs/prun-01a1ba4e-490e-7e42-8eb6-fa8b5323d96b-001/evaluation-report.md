# ACP 技术设计新旧对比

Run `prun-01a1ba4e-490e-7e42-8eb6-fa8b5323d96b-001`。GPT‑6 Luna / high 在新会话里只执行新版 `x-tech-design`。已确认 Spec SHA-256 为 `ff4a5d3fb04e6bbe7ece2b989537303e5756a6c50408c311c4fbed066d7df942`，起始源码逐文件匹配上轮。候选工作区仅新增技术设计草案。本次对比历史确认稿和新草稿，旧稿经过上轮人工修订，结果用于看文档差异。

**新版图和结构定义有改善，篇幅变化有限，当前草稿仍有影响交接的设计缺口。**

| 维度 | 旧确认稿 | 新草稿 |
| --- | ---: | ---: |
| 正文段落和列表字符 | 3,646 | 3,331（少 8.6%） |
| 全文 Markdown 字符 | 27,589 | 26,348（少 4.5%） |
| 全文行数 | 439 | 484 |
| Mermaid 图通过语法解析 | 2/3 | 5/5 |
| 带中文注释的类型代码块 | 0 | 3 |
| Spec 场景在矩阵中列出 | 10/10 | 10/10 |
| 独立编号用例主定义 | 15 | 8 |

正文字符统计到第一个附录为止，排除空白、标题、元数据、表格与围栏代码块。用例条数可受合并方式影响，逐场景列出也需要核对具体判据。

- **请求帧仍有关键分流藏在文字里。** 新稿把读帧、写回和 EOF 放进时序图，JSON-RPC 请求与通知仍共用一个图中分支。省略 `id` 与 `id: 0` 缺少图上的对照，解析失败和参数失败也合在一条路径，正文才补充 `id: null`。会话占槽图后仍有两段文字重述流程。[旧协议处理](/Volumes/machub_app/proj/x-dev-pipeline/pipeline-data/runs/prun-01a1b509-7fed-7d41-947f-f1e16955ad5f-001/artifacts/tech-design-approved.md:45) · [新帧处理](/private/tmp/dsh-acp-tech-replay.fai1bp7a/workspace/task/docs/spec/acp-editor/tech-design.md:111)
- **类型比字段表直观。** 新稿给出 `BridgeState`、`ActivePrompt`、JSON-RPC 帧和更新类型。各方法的完整 schema 仍留给实现，`SessionSlot` 在主文与附录各定义一次。[桥接类型](/private/tmp/dsh-acp-tech-replay.fai1bp7a/workspace/task/docs/spec/acp-editor/tech-design.md:78) · [协议结构](/private/tmp/dsh-acp-tech-replay.fai1bp7a/workspace/task/docs/spec/acp-editor/tech-design.md:235)
- **已确认的目录约束丢了一支。** 旧稿要求 `session/new` 和 `session/load` 都拒绝非空额外目录。新稿的图只在 new 分支检查，load 参数表和测试输入也漏掉这一项。T2 的禁止结果有提及，缺少对应输入，仍无法照文档验收。[旧规则](/Volumes/machub_app/proj/x-dev-pipeline/pipeline-data/runs/prun-01a1b509-7fed-7d41-947f-f1e16955ad5f-001/artifacts/tech-design-approved.md:57) · [新占槽图](/private/tmp/dsh-acp-tech-replay.fai1bp7a/workspace/task/docs/spec/acp-editor/tech-design.md:53) · [新测试 T2](/private/tmp/dsh-acp-tech-replay.fai1bp7a/workspace/task/docs/spec/acp-editor/tech-design.md:314)
- **持久化方案发生了变化。** 旧稿等 Agent 变为 idle，并用 T15 刻意挂起 flush 验证响应顺序。新稿提出由桥接再发起一次 flush，失败语义仍待定。新用例检查更新先于响应，缺少 flush 被挂起时必须保持无响应的判据。EOF 清理里使用的 Agent done 也未落到公开 Agent 接口。[旧 T15](/Volumes/machub_app/proj/x-dev-pipeline/pipeline-data/runs/prun-01a1b509-7fed-7d41-947f-f1e16955ad5f-001/artifacts/tech-design-approved.md:352) · [新持久化顺序](/private/tmp/dsh-acp-tech-replay.fai1bp7a/workspace/task/docs/spec/acp-editor/tech-design.md:154) · [新待决事项](/private/tmp/dsh-acp-tech-replay.fai1bp7a/workspace/task/docs/spec/acp-editor/tech-design.md:479) · [Agent 接口](/private/tmp/dsh-acp-tech-replay.fai1bp7a/workspace/task/packages/agent/src/types.ts:46)

新稿保持待确认。此次未执行 Req、Dev 或实现测试。新稿生成耗时 333 秒，记录 715,502 token，扣除缓存读取后 110,830。历史旧稿运行的上下文与反馈次数不同，阶段用量不做降幅对比。

[旧确认稿](/Volumes/machub_app/proj/x-dev-pipeline/pipeline-data/runs/prun-01a1b509-7fed-7d41-947f-f1e16955ad5f-001/artifacts/tech-design-approved.md) · [Luna 新草稿](/private/tmp/dsh-acp-tech-replay.fai1bp7a/workspace/task/docs/spec/acp-editor/tech-design.md) · [归档原稿](artifacts/tech-design.md) · [Mermaid 检查](mermaid-validation.json) · [统计明细](comparison-metrics.json)
