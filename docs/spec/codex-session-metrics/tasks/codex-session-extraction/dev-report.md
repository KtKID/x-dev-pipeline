# Dev Report — codex-session-extraction — 20260720-162047

## 改动文件清单

- `tools/metrics.py`
- `test/test_metrics.py`
- `docs/spec/codex-session-metrics/spec.md`
- `docs/spec/codex-session-metrics/modules.md`
- `docs/spec/codex-session-metrics/design.md`
- `docs/spec/codex-session-metrics/tasks/codex-session-extraction/dev-checklist.md`
- `docs/spec/codex-session-metrics/tasks/codex-session-extraction/diagram.md`

## 验证证据

```verify
id: S1
scenario: fork rollout 含父 session 前缀
cmd: python3 -m unittest test.test_metrics -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S2
scenario: 子 agent 生成后接受修复反馈
cmd: python3 -m unittest test.test_metrics -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S3
scenario: 最后回合未完成
cmd: python3 -m unittest test.test_metrics -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S4
scenario: 真实 fork 子 agent session
cmd: PYTHONPATH=tools python3 -c 'from pathlib import Path; import metrics; v=metrics.parse_codex_session_source(Path("/Users/kid/.codex/sessions/2026/07/20/rollout-2026-07-20T23-39-12-019f802e-68c1-7422-a52a-c4ab06902e4c.jsonl"), []); print(v["tokens"]["input"], v["tokens"]["cached_input"], v["tokens"]["output"], v["tokens"]["reasoning_output"], v["tokens"]["total"])'
cwd: .
expect_exit: 0
expect_contains: 765666 704256 18864 3906 784530
mode: auto
```

```verify
id: S5
scenario: 无继承基线的独立 session
cmd: python3 -m unittest test.test_metrics -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S6
scenario: 累计计数器回退
cmd: python3 -m unittest test.test_metrics -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S7
scenario: 推理 Token 纳入 measurement
cmd: python3 -m unittest test.test_metrics -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S8
scenario: 真实两回合子 agent session
cmd: PYTHONPATH=tools python3 -c 'from pathlib import Path; import metrics; v=metrics.parse_codex_session_source(Path("/Users/kid/.codex/sessions/2026/07/20/rollout-2026-07-20T23-39-12-019f802e-68c1-7422-a52a-c4ab06902e4c.jsonl"), []); print(v["started_at"], v["ended_at"], v["duration_ms"])'
cwd: .
expect_exit: 0
expect_contains: 2026-07-20T15:39:13.099Z 2026-07-20T15:46:59.364Z 466265
mode: auto
```

```verify
id: M1
scenario: 后续增加 Claude session parser
mode: manual
steps: 实现独立 Claude parser 并输出与 parse_codex_session_source 相同的 normalized source 字段，再调用 build_measurement 与 aggregate_spec2；确认 Codex parser 无需改动。
```

```verify
id: S9
scenario: 检查新增函数命名
cmd: git diff --unified=0 -- tools/metrics.py
cwd: .
expect_exit: 0
expect_contains: parse_codex_session_source
expect_contains: _codex_token_delta
mode: auto
```

```verify
id: S10
scenario: rubric 路径只存在于继承前缀
cmd: python3 -m unittest test.test_metrics -v
cwd: .
expect_exit: 0
expect_contains: test_grader_only_path_in_inherited_prefix_is_ignored
mode: auto
```

```verify
id: S11
scenario: 活动窗口读取 rubric
cmd: python3 -m unittest test.test_metrics -v
cwd: .
expect_exit: 0
expect_contains: test_grader_only_path_in_active_window_is_invalid
mode: auto
```

```verify
id: S12
scenario: 既有单回合 fixture
cmd: python3 -m unittest test.test_metrics -v
cwd: .
expect_exit: 0
expect_contains: test_uses_last_cumulative_snapshot_and_assistant_reply_duration
mode: auto
```

```verify
id: S13
scenario: 回归测试集
cmd: python3 -m unittest test.test_metrics -v
cwd: .
expect_exit: 0
expect_contains: Ran 24 tests
expect_contains: OK
mode: auto
```

## 自检结论

本人（x-dev）已在本机运行全部 auto verify 命令，并确认结果与本报告一致。
本报告由 x-dev 于 2026-07-20T16:20:47Z 生成。
