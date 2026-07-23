# Dev Report — backend-end-to-end — 20260722-174049

## 改动文件清单

- `fixture/backend/app.py`
- `fixture/backend/audio.py`
- `fixture/backend/http_client.py`
- `fixture/backend/protocol.py`
- `fixture/backend/config.json`
- `fixture/backend/test_app.py`
- `fixture/backend/test_audio.py`
- `fixture/backend/test_http_client.py`
- `fixture/backend/test_protocol.py`
- `fixture/backend/e2e_test.py`
- `docs/spec/voice-chain/spec.md`
- `docs/spec/voice-chain/tasks/backend-end-to-end/dev-checklist.md`
- `docs/spec/voice-chain/tasks/backend-end-to-end/diagram.md`

## 验证证据

```verify
id: S1
scenario: SC_01
cmd: python3 -m unittest e2e_test.VoiceChainE2E.test_01_normal_chain_and_files -v
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S2
scenario: SC_02
cmd: python3 -m unittest e2e_test.VoiceChainE2E.test_02_disconnect_resume_completes_chain -v
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S3
scenario: SC_03
cmd: python3 -m unittest e2e_test.VoiceChainE2E.test_03_pipelined_sticky_and_split_frames -v
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S4
scenario: SC_04
cmd: python3 -m unittest test_protocol.FrameDecoderTests.test_bad_magic_has_no_associated_sequence test_protocol.FrameDecoderTests.test_bad_crc_preserves_associated_sequence test_protocol.FrameDecoderTests.test_valid_frames_before_an_error_are_preserved test_app.DownlinkTests.test_valid_hello_is_acked_before_later_bad_crc_error test_app.DownlinkTests.test_audio_end_then_bad_crc_in_same_batch_gets_error -v
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S5
scenario: SC_05
cmd: python3 -m unittest e2e_test.VoiceChainE2E.test_04_bad_magic_crc_and_oversized_length -v
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S6
scenario: SC_06
cmd: python3 -m unittest test_app.UploadSessionTests.test_end_rejects_missing_chunks_and_wrong_hash -v
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S7
scenario: SC_07
cmd: python3 -m unittest test_audio.WavTests -v
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S8
scenario: SC_08
cmd: python3 -m unittest e2e_test.VoiceChainE2E.test_05_5xx_retries_and_timeout_is_bounded -v
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S9
scenario: SC_09
cmd: python3 -m unittest e2e_test.VoiceChainE2E.test_05_5xx_retries_and_timeout_is_bounded e2e_test.VoiceChainE2E.test_06_unknown_audio_is_upstream_error_without_hang test_http_client.HttpClientTests test_app.DownlinkTests.test_json_frame_over_wire_limit_becomes_upstream_error -v
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S10
scenario: SC_10
cmd: python3 -m unittest e2e_test.VoiceChainE2E.test_08_downlink_reset_does_not_stop_server -v
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S11
scenario: SC_11
cmd: python3 -m unittest e2e_test.VoiceChainE2E.test_07_concurrent_sessions_are_isolated -v
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S12
scenario: SC_12
cmd: python3 -m unittest test_app.UploadSessionTests.test_gap_and_chunk_after_short_chunk_fail test_app.UploadSessionTests.test_session_id_cannot_escape_sessions_directory test_app.UploadSessionTests.test_upload_and_session_capacity_are_bounded test_app.UploadSessionTests.test_session_directory_symlink_is_rejected -v
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S13
scenario: SC_13
cmd: python3 -m unittest e2e_test.VoiceChainE2E.test_01_normal_chain_and_files -v
cwd: fixture/backend
expect_exit: 0
expect_contains: OK
mode: auto
```

## 补充 Smoke 证据

- `python3 ../device-sim/device_sim.py --server 127.0.0.1:9000 --wav ../assets/ask_weather.wav --session smoke-weather --out smoke-out`：exit 0，END ACK 含预期 text/reply，下行 9 块、26656 字节。
- `cmp -s sessions/smoke-weather/upload.wav ../assets/ask_weather.wav`：exit 0。
- `cmp -s sessions/smoke-weather/reply.wav ../assets/tts_weather.wav`：exit 0。
- 下行 `smoke-out/reply_payload.bin` 与 `audio.wav_pcm(tts_weather.wav)` 逐字节一致：`SMOKE_PCM_OK 26656`。

## 自检结论

本人（x-dev）已在本机运行全部 auto verify 命令，并确认结果与本报告一致。
本报告由 x-dev 于 2026-07-22T17:40:49Z 生成。
