# Dev Report — journal-store — 20260723-012418

## 改动文件清单

- `fixture/backend/record.py`
- `fixture/backend/locking.py`
- `fixture/backend/store.py`
- `fixture/backend/cli.py`
- `tests/test_journal.py`
- `docs/spec/journal-index-recovery/spec.md`
- `docs/spec/journal-index-recovery/tasks/journal-store/dev-checklist.md`
- `docs/spec/journal-index-recovery/tasks/journal-store/diagram.md`
- `docs/spec/journal-index-recovery/tasks/journal-store/dev-report.md`

## 验证证据

```verify
id: S01
scenario: SC_01
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.RecordCodecTests -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S02
scenario: SC_02
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalCliTests.test_crud_versions_idempotency_and_restart -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S03
scenario: SC_03
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalCliTests.test_crud_versions_idempotency_and_restart -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S04
scenario: SC_04
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalCliTests.test_crud_versions_idempotency_and_restart -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S05
scenario: SC_05
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalCliTests.test_delete_never_seen_and_cli_parameter_errors tests.test_journal.JournalCliTests.test_crud_versions_idempotency_and_restart -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S06
scenario: SC_06
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalCliTests.test_crud_versions_idempotency_and_restart tests.test_journal.JournalCliTests.test_compact_restart_tmp_ignore_and_idempotency -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S07
scenario: SC_07
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalCliTests.test_crud_versions_idempotency_and_restart tests.test_journal.JournalCliTests.test_idempotency_fingerprint_checks_each_request_field -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S08
scenario: SC_08
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalCliTests.test_durability_primitive_order_for_append_and_compact -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S09
scenario: SC_09
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalCliTests.test_each_last_record_corruption_is_recoverable -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S10
scenario: SC_10
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalCliTests.test_tail_recovery_and_healthy_recover_are_exact tests.test_journal.JournalCliTests.test_durability_primitive_order_for_append_and_compact -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S11
scenario: SC_11
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalCliTests.test_middle_log_corruption_is_read_only_even_for_recover tests.test_journal.JournalCliTests.test_corrupt_snapshot_never_falls_back_or_rewrites tests.test_journal.JournalCliTests.test_nested_snapshot_type_corruption_maps_to_corrupt_snapshot tests.test_journal.JournalCliTests.test_crc_valid_replay_invariant_violation_is_corrupt_log tests.test_journal.JournalCliTests.test_deep_json_middle_record_is_corrupt_log tests.test_journal.JournalCliTests.test_hostile_snapshot_depth_and_declared_sequence_are_bounded -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S12
scenario: SC_12
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalCliTests.test_compact_restart_tmp_ignore_and_idempotency tests.test_journal.JournalCliTests.test_durability_primitive_order_for_append_and_compact -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S13
scenario: SC_13
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalCliTests.test_compact_restart_tmp_ignore_and_idempotency tests.test_journal.JournalCliTests.test_recover_partial_snapshot_overlap_tail_remains_loadable -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S14
scenario: SC_14
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalConcurrencyTests.test_concurrent_new_keys_have_unique_sequences_and_no_loss tests.test_journal.JournalConcurrencyTests.test_mutations_compact_and_recover_serialize_without_loss -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S15
scenario: SC_15
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalConcurrencyTests.test_concurrent_same_version_has_exactly_one_commit -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: S16
scenario: SC_16
cmd: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_journal.JournalCliTests -v
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

## 自检结论

本人（x-dev）已在本机运行全部 auto verify 命令，并确认结果与本报告一致。
本报告由 x-dev 于 2026-07-23T01:24:18Z 生成，并于 2026-07-23T01:35:58Z、2026-07-23T01:51:22Z、2026-07-23T02:11:31Z 补入 R1/R2/R3 回归证据。
