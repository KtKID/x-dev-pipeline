# Dev Report — backend — 20260722-183146

## 改动文件清单

- `fixture/backend/app.py`
- `fixture/backend/audio.py`
- `fixture/backend/http_client.py`
- `fixture/backend/protocol.py`
- `fixture/backend/tests/test_voice_chain.py`
- `docs/spec/voice-chain/spec.md`
- `docs/spec/voice-chain/tasks/backend/dev-checklist.md`
- `docs/spec/voice-chain/tasks/backend/diagram.md`
- `docs/spec/voice-chain/tasks/backend/dev-report.md`

## 实现结果

- 用线程安全的 session 状态保存连续上传块，支持进程内断线续传和相同块的幂等确认。
- 在完整性校验后原子落盘上传文件，按 ASR→LLM→TTS 顺序执行配置驱动的超时与重试策略。
- 校验 TTS WAV 的 PCM16/单声道/16000Hz 格式，ACK 后下发 3200 字节 PCM 块及总块数、SHA-256 元数据。
- 每个连接的协议、上游和 socket 失败都收敛在连接线程内，多会话使用独立状态锁和文件目录。

## 验证证据

```verify
id: V01
scenario: SC_01
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.EndToEndTests.test_pipelined_fragmented_upload_and_full_downlink -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V02
scenario: SC_02
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.EndToEndTests.test_resume_from_contiguous_prefix_completes_chain -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V03
scenario: SC_03
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.EndToEndTests.test_protocol_errors_are_returned_and_connection_closes -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V04
scenario: SC_04
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.EndToEndTests.test_protocol_errors_are_returned_and_connection_closes -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V05
scenario: SC_05
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.EndToEndTests.test_protocol_errors_are_returned_and_connection_closes -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V06
scenario: SC_06
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.EndToEndTests.test_integrity_failure_skips_orchestration -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V07
scenario: SC_07
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.EndToEndTests.test_success_ack_and_reply_file -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V08
scenario: SC_08
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.EndToEndTests.test_upstream_timeout_returns_error_within_finite_time -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V09
scenario: SC_09
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.EndToEndTests.test_single_5xx_retries_and_completes -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V10
scenario: SC_10
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.UpstreamPolicyTests.test_exhausted_5xx_and_4xx_are_upstream_errors -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V11
scenario: SC_11
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.EndToEndTests.test_concurrent_sessions_are_isolated -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V12
scenario: SC_12
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.ProtocolAndAudioTests.test_wav_pcm_accepts_only_device_format_and_chunks_losslessly -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V13
scenario: SC_13
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.EndToEndTests.test_device_sim_cli_completes_real_smoke_chain -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V14
scenario: SC_14
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.EndToEndTests.test_disconnect_during_response_does_not_stop_other_sessions -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V15
scenario: SC_08
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.UpstreamPolicyTests.test_config_is_validated_before_runtime -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V16
scenario: SC_10
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.UpstreamPolicyTests.test_malformed_or_truncated_http_is_upstream_error -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V17
scenario: SC_08
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.UpstreamPolicyTests.test_total_deadline_rejects_trickled_http_body -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

```verify
id: V18
scenario: SC_08
cmd: python3 -m unittest fixture.backend.tests.test_voice_chain.UpstreamPolicyTests.test_total_deadline_rejects_trickled_http_headers -v
cwd: .
expect_exit: 0
expect_contains: OK
timeout: 15
mode: auto
```

## 自检结论

本人（x-dev）已在本机运行全部 auto verify 命令，并确认结果与本报告一致。
本报告由 x-dev 于 20260722-183146 UTC 生成。
