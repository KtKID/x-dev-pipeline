# voice-chain-backend · 开发清单

> spec: docs/spec/voice-chain
> risk: Q3

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | 先建立协议、音频格式与非法输入单元测试，再补齐严格解析、PCM 校验与分块 | SC_01, SC_06, SC_07, SC_09 | 协议公开契约、`J1`、`J6`、`J8` | `fixture/backend/test_voice_chain.py`, `fixture/backend/protocol.py`, `fixture/backend/audio.py` | None | [x] ✅ | None |
| T2 | 实现带会话锁的 HELLO、顺序/幂等分块、续传、完整性校验与原子落盘 | SC_02, SC_03, SC_04, SC_05, SC_13 | 会话隔离与持久化不变量、`J2`、`J3`、`J8` | `fixture/backend/app.py`, `fixture/backend/test_voice_chain.py` | T1 | [x] ✅ | None |
| T3 | 实现配置驱动的 ASR→LLM→TTS 编排、重试/超时映射、ACK 与 PCM 下行 | SC_08, SC_09, SC_10, SC_11, SC_12 | 跨模块失败恢复、`J4`、`J5`、`J7` | `fixture/backend/app.py`, `fixture/backend/http_client.py`, `fixture/backend/test_voice_chain.py` | T1, T2 | [x] ✅ | None |
| T4 | 运行回环 Smoke/E2E，覆盖全链、流水线、续传、并发、故障注入和下行断开 | SC_02, SC_03, SC_04, SC_08, SC_09, SC_11, SC_12, SC_13 | Q3 并发与公开协议事实验证 | `fixture/backend/test_voice_chain.py`, `docs/spec/voice-chain/tasks/voice-chain-backend/dev-report.md` | T3 | [x] ✅ | None |
