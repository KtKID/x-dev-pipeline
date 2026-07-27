# Dev Report — end-to-end — 20260722-192826

## 改动文件清单

- `fixture/backend/app.py`
- `fixture/backend/audio.py`
- `fixture/backend/http_client.py`
- `fixture/backend/protocol.py`
- `fixture/backend/test_voice_chain.py`
- `fixture/backend/test_e2e.py`
- `docs/spec/voice-chain/spec.md`
- `docs/spec/voice-chain/tasks/end-to-end/dev-checklist.md`
- `docs/spec/voice-chain/tasks/end-to-end/diagram.md`

## 验证证据

unit：11 个测试覆盖流式协议、非法帧、会话断点与完整性、路径安全、上游次数/错误分类、音频格式和 ACK/下行顺序。

smoke：真实启动 `app.py`、mock services 和原始 `device_sim.py` CLI，验证 weather ACK、9 个 PCM 块、TTS_END 摘要及三份字节级产物。

e2e：5 个跨进程/回环网络测试覆盖 device CLI、断线续传、单次 5xx 恢复、timeout、4xx、并发双会话及下行 RST 后存活。

```verify
id: S01
scenario: SC_01
cmd: python3 -m unittest -v test_voice_chain.SessionTests.test_contiguous_resume_and_idempotent_replay test_voice_chain.SessionTests.test_hello_identifier_is_path_safe
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S02
scenario: SC_02
cmd: python3 -m unittest -v test_voice_chain.ProtocolTests.test_fragmented_and_coalesced_frames test_voice_chain.ConnectionTests.test_ack_precedes_playable_chunks_and_integrity_end
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S03
scenario: SC_03
cmd: python3 -m unittest -v test_voice_chain.ProtocolTests.test_protocol_errors test_voice_chain.ConnectionTests.test_valid_chunk_before_bad_frame_is_retained_for_resume test_voice_chain.ConnectionTests.test_two_bad_magic_bytes_get_immediate_error test_voice_chain.ConnectionTests.test_payload_too_large_reports_seq_closes_and_retains_prefix
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S04
scenario: SC_04
cmd: python3 -m unittest -v test_e2e.VoiceChainE2E.test_disconnect_resume_completes_full_chain
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S05
scenario: SC_05
cmd: python3 -m unittest -v test_voice_chain.SessionTests.test_rejects_gap_replay_change_count_and_digest test_voice_chain.ConnectionTests.test_integrity_errors_close_without_upstream_calls
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S06
scenario: SC_06
cmd: python3 -m unittest -v test_e2e.VoiceChainE2E.test_5xx_retry_timeout_and_4xx_error test_voice_chain.OrchestrationTests.test_5xx_exhaustion_and_4xx_have_exact_attempt_counts test_voice_chain.OrchestrationTests.test_incomplete_http_response_maps_to_upstream_error
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S07
scenario: SC_07
cmd: python3 -m unittest -v test_e2e.VoiceChainE2E.test_device_sim_cli_smoke
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S08
scenario: SC_08
cmd: python3 -m unittest -v test_voice_chain.AudioTests
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S09
scenario: SC_09
cmd: python3 -m unittest -v test_voice_chain.ConnectionTests.test_ack_precedes_playable_chunks_and_integrity_end
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S10
scenario: SC_10
cmd: python3 -m unittest -v test_e2e.VoiceChainE2E.test_success_files_and_concurrent_isolation
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S11
scenario: SC_11
cmd: python3 -m unittest -v test_e2e.VoiceChainE2E.test_downlink_disconnect_keeps_backend_available test_voice_chain.ConnectionTests.test_downlink_send_failure_does_not_interrupt_concurrent_session
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

### 固定启动契约 Smoke 实测

- mock：`python3 ../mock-services/mock_services.py --port 9100`
- backend：`python3 app.py --port 9000 --config config.json`
- device：`python3 ../device-sim/device_sim.py --server 127.0.0.1:9000 --wav ../assets/ask_weather.wav --out /tmp/voice-chain-fixed-smoke`
- 退出码：device `0`；服务在验证后由 SIGINT 正常停止。
- ACK：`{"ok":true,"text":"今天天气怎么样","reply":"今天晴，气温二十六度"}`。
- 下行：9 块、26656 字节；PCM sha256 `af253a81e48f81c3374d763c46541cfddc163747a80c57f2d028e14dfc55ccdf`。
- 字节校验：upload 等于 `ask_weather.wav`；reply 等于 `tts_weather.wav`；device payload 等于该 WAV 的 PCM data chunk。

## 自检结论

本人（x-dev）已在本机运行全部 unit、smoke 和 e2e auto verify 命令，并确认结果与本报告一致。
本报告由 x-dev 于 2026-07-22T19:28:26Z 生成。
