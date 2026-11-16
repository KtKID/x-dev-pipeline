# task-acp-editor-bridge · 开发清单

> spec: docs/spec/acp-editor/spec.md
> tech-design: docs/spec/acp-editor/tech-design.md
> spec baseline: ff4a5d3fb04e6bbe7ece2b989537303e5756a6c50408c311c4fbed066d7df942
> tech-design approved baseline: 9c56f3b52d0b2311ea68e74e0e99a9c99ae7a6669cb589afdeec15ae6e943048
> risk: Q3
> 创建: 2026-11-07

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[x] 🟢` 验证通过 / `[!] 🔴` 验证失败

| # | 任务 | 场景回指 | 涉及文件 | 风险 | 状态 |
|---|---|---|---|---|---|
| T1 | 先测试后实现 ACP 行帧解析、版本协商、请求/通知响应和 stdout/stderr 分流；核对 effect dispose 清理（C2；D01；用例 T1、T11、T14；unit + 集成） | feat01 场景1 | packages/acp/src/index.ts, packages/acp/tests/index.spec.ts | None | [ ] ⏳ |
| T2 | 先测试后实现 session slot 原子预留、cwd/空列表校验、创建/恢复前置检查、历史回放及恢复后续问（C1、C8；D02、D03、D05；用例 T2、T3、T12；unit + 集成） | feat01 场景2, 场景3 | packages/acp/src/index.ts, packages/acp/tests/index.spec.ts | 高：会话并发预留和持久化恢复必须保证拒绝请求不启动 Agent 且不跨 cwd 读取 | [ ] ⏳ |
| T3 | 先测试后实现 Agent 正文/思考增量、工具同 ID 状态及 completed/max_tokens/error 结算顺序（C3、C4、C5；D03、D04；用例 T4、T7、T13、T15；unit + 集成） | feat02 场景1, 场景4, feat03 场景1 | packages/acp/src/index.ts, packages/acp/tests/index.spec.ts | 高：并发状态和 flush 先后决定请求结算及已确认历史 | [ ] ⏳ |
| T4 | 先测试后实现 prompt 全量校验与同一会话并发请求拒绝（C2、C3、C6；D01、D04；用例 T5、T6；unit + 集成） | feat02 场景2, 场景3 | packages/acp/src/index.ts, packages/acp/tests/index.spec.ts | 高：无效/忙碌请求不得写入 Agent inbox 或污染共享会话 | [ ] ⏳ |
| T5 | 先测试后实现运行中取消、空闲/未知取消 no-op、取消后继续提问和 stdin EOF 回收（C6、C7；D04；用例 T8、T9、T10；集成 + smoke） | feat03 场景1, 场景2, 场景3 | packages/acp/src/index.ts, packages/acp/tests/index.spec.ts | 高：取消与断开竞态必须停止底层工作并只结算一次 | [ ] ⏳ |

## 影响文件树

```text
task/
└── packages/acp/
    ├── src/index.ts       U  # 新增 stdio ACP bridge、状态管理、Harness 事件映射
    └── tests/index.spec.ts U  # 新增 ACP protocol、生命周期和 Harness 集成测试
```
