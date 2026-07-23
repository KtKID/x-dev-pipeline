# backend · 开发清单

> spec: docs/spec/voice-chain
> risk: Q3

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | 完成流式协议边界、设备 WAV 格式校验与 PCM 分块单元测试 | SC_03, SC_04, SC_05, SC_12, SC_13 | 协议公开契约与播放格式不变量，J4/J5/J6 | `fixture/backend/protocol.py`, `fixture/backend/audio.py`, `fixture/backend/tests/test_voice_chain.py` | None | [!] 🔴 | None |
| T2 | 完成上游 HTTP 超时、状态分类与有限 5xx 重试测试 | SC_08, SC_09, SC_10 | 有限应答与精确重试不变量，J3 | `fixture/backend/http_client.py`, `fixture/backend/app.py`, `fixture/backend/tests/test_voice_chain.py` | T1 | [!] 🔴 | None |
| T3 | 完成会话上传、摘要校验、编排落盘、ACK 与 PCM 下发 | SC_01, SC_06, SC_07, SC_13 | 会话状态、文件归属和 ACK 时序不变量，J1/J2/J5/J6 | `fixture/backend/app.py`, `fixture/backend/tests/test_voice_chain.py` | T2 | [!] 🔴 | None |
| T4 | 完成断线续传、多设备并发和下发断连的跨进程 E2E 验证 | SC_02, SC_11, SC_14 | 并发竞态、连接资源与跨会话隔离不变量，SC_02/SC_11/SC_14 | `fixture/backend/app.py`, `fixture/backend/tests/test_voice_chain.py` | T3 | [!] 🔴 | None |
| T5 | 汇总全部 Scenario 的可复跑 Gate① 证据 | SC_01, SC_02, SC_03, SC_04, SC_05, SC_06, SC_07, SC_08, SC_09, SC_10, SC_11, SC_12, SC_13, SC_14 | 完整行为覆盖与事实证据 | `docs/spec/voice-chain/tasks/backend/dev-report.md` | T4 | [!] 🔴 | None |
