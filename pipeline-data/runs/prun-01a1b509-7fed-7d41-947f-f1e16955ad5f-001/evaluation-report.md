# DeepSeek Harness ACP Luna 单次试跑

Run `prun-01a1b509-7fed-7d41-947f-f1e16955ad5f-001`。执行者和 Q3 reviewer 均使用 GPT-6 Luna / high。范围为当前工作区的 pipeline 候选版，从 Spec、Tech Design、Req、Dev 走到 Verify，再按评测操作者要求完成 Q3 旁路和聚焦修复。Spec 和设计在评测操作者复核后分别按内容哈希确认。

## 功能与门禁

| 项目 | 结果 |
| --- | --- |
| 独立 ACP 协议测试 | 8/8 |
| 候选方 ACP 集成测试 | 17/17（E020） |
| 上游 Session 回归 | 20/20（E013） |
| 实现覆盖率 | 行 94.28%，分支 81.95% |
| 本题量表 | 95/100 |
| 正式 QA | Verify Spec 未完成，未放行 |

第一次红灯在模块导入时就失败了，之后新增行为也缺少有效的实现前失败记录。试跑保留了这个证据缺口，并在正式门禁阻断后单独跑了 Q3。旁路 reviewer 对取消通知的判断被运行复现证伪，通知无响应的断言已补上。完整的项目 strict TypeScript 检查仍缺通过证据。见[测试报告](/private/tmp/dsh-acp-luna.6lv2ym/candidate/workspace/task/reports/task-acp-editor-bridge/20261107-01/test-report.md)、[旁路审查](/private/tmp/dsh-acp-luna.6lv2ym/candidate/workspace/task/reports/task-acp-editor-bridge/20261107-01/evidence/Q3-bypass-review.md)、[修复记录](/private/tmp/dsh-acp-luna.6lv2ym/candidate/workspace/task/reports/fix/fix-gate-r1-20261107-090136.md)。

## Token

| 消耗 | Tokens |
| --- | ---: |
| 全部输入与输出 | 28,347,296 |
| 缓存读取输入 | 27,559,808 |
| 扣除缓存读取后的输入与输出 | 787,488 |
| Luna 主执行会话合计 | 27,977,325 |
| Q3 reviewer 合计 | 369,971 |

执行树墙钟时间 64 分 40 秒。按独立模型响应去重并对账，包含上下文压缩开销。用量统计涵盖主执行与 Q3 reviewer，操作者与隐藏评分的消耗本轮未量化。成本未估算。当前只有候选样本，且 Verify 阶段补入本地 Vitest，暂时没有版本间的 token 降幅或因果归因。

## 审计链接

候选仅收到单独工作区和公开材料，未继承操作者会话。执行工具仍共用宿主的文件读取权限，边界靠工作区约束与日志检查。本轮日志未命中隐藏材料路径或文件名。完整文件读取隔离尚未建立。

- [原始最终回执](candidate-receipt.md)
- [独立评分](wire-grading.json) · [协议帧证据](wire-evidence.json) · [评分时的文件哈希](graded-files.sha256)
- [用量明细](telemetry.json) · [阶段事件](events.jsonl) · [综合评分](grading.json)
- [Spec](/private/tmp/dsh-acp-luna.6lv2ym/candidate/workspace/task/docs/spec/acp-editor/spec.md) · [Tech Design](/private/tmp/dsh-acp-luna.6lv2ym/candidate/workspace/task/docs/spec/acp-editor/tech-design.md) · [Req 清单](/private/tmp/dsh-acp-luna.6lv2ym/candidate/workspace/task/docs/spec/acp-editor/tasks/task-acp-editor-bridge/dev-checklist.md) · [实现](/private/tmp/dsh-acp-luna.6lv2ym/candidate/workspace/task/packages/acp/src/index.ts)
