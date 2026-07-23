# backend-end-to-end · 开发清单

> spec: docs/spec/voice-chain
> risk: Q3

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | 完成流式帧解码错误关联信息与协议单元测试 | SC_03, SC_04, SC_05 | 公开线协议不变量 / `J1` | `fixture/backend/protocol.py`, `fixture/backend/test_protocol.py` | None | [!] 🔴 | None |
| T2 | 实现线程安全的上传会话、续传、序列与完整性校验、安全原子落盘 | SC_02, SC_06, SC_12, SC_13 | 并发、持久化与路径安全 / `J2`, `J5`, `J7` | `fixture/backend/app.py`, `fixture/backend/config.json`, `fixture/backend/test_app.py` | T1 | [!] 🔴 | None |
| T3 | 实现 ASR→LLM→TTS 顺序编排、配置化超时/5xx 重试及错误映射 | SC_08, SC_09 | 失败恢复与有限应答 / `J3` | `fixture/backend/app.py`, `fixture/backend/http_client.py`, `fixture/backend/test_app.py` | T2 | [!] 🔴 | None |
| T4 | 实现严格 WAV 校验、PCM 下行分块和可校验 TTS_END，隔离下行断连 | SC_01, SC_07, SC_10 | 设备播放契约与 socket 资源生命周期 / `J4` | `fixture/backend/audio.py`, `fixture/backend/app.py`, `fixture/backend/test_audio.py`, `fixture/backend/test_app.py` | T3 | [!] 🔴 | None |
| T5 | 建立并复跑单进程、跨进程、并发、续传、协议坏帧及上游故障验证 | SC_01, SC_02, SC_03, SC_04, SC_05, SC_06, SC_07, SC_08, SC_09, SC_10, SC_11, SC_12, SC_13 | Q3 全链公开契约与并发隔离 | `fixture/backend/test_*.py`, `fixture/backend/e2e_test.py`, `docs/spec/voice-chain/tasks/backend-end-to-end/dev-report.md` | T1, T2, T3, T4 | [!] 🔴 | None |
