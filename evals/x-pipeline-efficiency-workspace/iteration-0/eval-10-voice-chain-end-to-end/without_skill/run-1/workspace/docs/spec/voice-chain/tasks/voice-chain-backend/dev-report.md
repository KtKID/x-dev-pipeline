# Dev Report — voice-chain-backend — 20260722-165115

## 改动文件清单

- `fixture/backend/app.py`
- `fixture/backend/audio.py`
- `fixture/backend/http_client.py`
- `fixture/backend/protocol.py`
- `fixture/backend/test_voice_chain.py`
- `docs/spec/voice-chain/spec.md`
- `docs/spec/voice-chain/tasks/voice-chain-backend/dev-checklist.md`
- `docs/spec/voice-chain/tasks/voice-chain-backend/diagram.md`

## 验证证据

```verify
id: S01
scenario: SC_01
cmd: python3 -m unittest -v test_voice_chain.ProtocolAndAudioTests.test_protocol_matches_fixed_wire_golden test_voice_chain.ProtocolAndAudioTests.test_streaming_decoder_handles_arbitrary_splits_and_sticky_frames
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S02
scenario: SC_02
cmd: python3 -m unittest -v test_voice_chain.VoiceChainE2ETests.test_success_pipeline_ack_files_and_downlink_integrity
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S03
scenario: SC_03
cmd: python3 -m unittest -v test_voice_chain.VoiceChainE2ETests.test_disconnect_resume_then_full_chain
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S04
scenario: SC_04
cmd: python3 -m unittest -v test_voice_chain.VoiceChainE2ETests.test_success_pipeline_ack_files_and_downlink_integrity
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S05
scenario: SC_05
cmd: python3 -m unittest -v test_voice_chain.ConnectionIsolationUnitTests.test_missing_chunk_returns_related_error_and_skips_upstream test_voice_chain.VoiceChainE2ETests.test_integrity_and_wire_errors_return_error
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S06
scenario: SC_06
cmd: python3 -m unittest -v test_voice_chain.ProtocolAndAudioTests.test_protocol_errors_preserve_defined_codes test_voice_chain.VoiceChainE2ETests.test_integrity_and_wire_errors_return_error
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S07
scenario: SC_07
cmd: python3 -m unittest -v test_voice_chain.VoiceChainE2ETests.test_unsafe_session_gap_and_cross_device_takeover_are_rejected
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S08
scenario: SC_08
cmd: python3 -m unittest -v test_voice_chain.PipelineUnitTests.test_pipeline_order_payloads_and_content_types test_voice_chain.VoiceChainE2ETests.test_success_pipeline_ack_files_and_downlink_integrity test_voice_chain.VoiceChainE2ETests.test_bundled_device_sim_full_chain_contract
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S09
scenario: SC_09
cmd: python3 -m unittest -v test_voice_chain.ProtocolAndAudioTests.test_wav_validation_and_short_pcm_tail test_voice_chain.VoiceChainE2ETests.test_success_pipeline_ack_files_and_downlink_integrity
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S10
scenario: SC_10
cmd: python3 -m unittest -v test_voice_chain.PipelineUnitTests.test_5xx_exhaustion_honors_configured_retry_limit test_voice_chain.PipelineUnitTests.test_each_upstream_failure_stops_the_pipeline test_voice_chain.VoiceChainE2ETests.test_upstream_retry_timeout_and_4xx
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S11
scenario: SC_11
cmd: python3 -m unittest -v test_voice_chain.PipelineUnitTests.test_4xx_and_timeout_do_not_retry test_voice_chain.PipelineUnitTests.test_each_upstream_failure_stops_the_pipeline test_voice_chain.PipelineUnitTests.test_http_total_deadline_rejects_slow_trickle test_voice_chain.VoiceChainE2ETests.test_upstream_retry_timeout_and_4xx
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S12
scenario: SC_12
cmd: python3 -m unittest -v test_voice_chain.ConnectionIsolationUnitTests.test_tts_write_failure_is_isolated_from_next_session test_voice_chain.VoiceChainE2ETests.test_concurrent_sessions_and_downlink_disconnect_are_isolated
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S13
scenario: SC_13
cmd: python3 -m unittest -v test_voice_chain.VoiceChainE2ETests.test_concurrent_sessions_and_downlink_disconnect_are_isolated
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

## 自检结论

本人（x-dev）已在本机运行全部 auto verify 命令，并确认结果与本报告一致。额外执行题面 device-sim 全链 Smoke，ACK 为预期中文 text/reply，下行 9 块共 26656 字节，upload.wav、reply.wav 与下行 PCM 均逐字节匹配真源素材。Gate 修复后补充慢速持续响应的总 deadline 回归测试。

本报告由 x-dev 于 2026-07-22T16:51:15Z 生成。
