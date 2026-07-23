# end-to-end · 开发清单

> spec: docs/spec/voice-chain
> risk: Q3

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | 用单元测试锁定流式帧解码、错误映射、WAV 格式校验和 PCM 分块/摘要契约，并补齐协议与音频工具 | SC_02, SC_03, SC_08 | wire CRC/长度不变量；J3 | `fixture/backend/protocol.py`, `fixture/backend/audio.py`, `fixture/backend/test_voice_chain.py` | None | [x] ✅ | issue-1, issue-2, issue-5 (round 3) |
| T2 | 实现线程安全的进程内会话、标识校验、连续块接收、幂等 ACK、恢复和 AUDIO_END 完整性门禁 | SC_01, SC_05 | 会话隔离与路径安全不变量；J1/J5/J6 | `fixture/backend/app.py`, `fixture/backend/test_voice_chain.py` | T1 | [x] ✅ | issue-3 (round 3) |
| T3 | 实现配置驱动的 ASR→LLM→TTS 调用、5xx 重试、timeout/4xx/连接失败分类和原子会话落盘 | SC_06, SC_07 | 上游有限应答与原始文件不变量；J2/J4 | `fixture/backend/http_client.py`, `fixture/backend/app.py`, `fixture/backend/test_voice_chain.py` | T2 | [x] ✅ | issue-4 (round 3) |
| T4 | 实现 ACK 后 PCM 下行、TTS_END 完整性元数据、续传后的全链闭环和断开连接隔离 | SC_04, SC_09, SC_11 | 公开帧时序与资源生命周期；J3/J4 | `fixture/backend/app.py`, `fixture/backend/test_voice_chain.py` | T3 | [x] ✅ | None |
| T5 | 建立自包含回环 E2E，覆盖两素材成功链、断线续传、上游故障和双会话并发隔离 | SC_04, SC_06, SC_07, SC_09, SC_10, SC_11 | 并发、失败恢复和真实跨进程链路 | `fixture/backend/test_e2e.py` | T4 | [x] ✅ | issue-6, issue-7, issue-8, issue-9 (round 3) |
| T6 | 复跑全部自动 verify、Smoke/E2E，记录命令、退出码、关键证据和剩余风险 | SC_01, SC_02, SC_03, SC_04, SC_05, SC_06, SC_07, SC_08, SC_09, SC_10, SC_11 | 全部 Scenario 验证责任 | `docs/spec/voice-chain/tasks/end-to-end/dev-report.md` | T5 | [x] ✅ | None |
