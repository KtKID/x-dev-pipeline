from __future__ import annotations

import concurrent.futures
import json
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "fixture" / "backend"
sys.path.insert(0, str(BACKEND))

from record import RecordError, decode_record, encode_record  # noqa: E402


CLI = BACKEND / "cli.py"


def run_cli(root: Path, *arguments: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, "-B", str(CLI), "--root", str(root), *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    lines = completed.stdout.splitlines()
    if len(lines) != 1:
        raise AssertionError(
            f"expected one stdout JSON object, got {completed.stdout!r}; stderr={completed.stderr!r}"
        )
    return completed.returncode, json.loads(lines[0])


def canonical_tail_with_invalid_field() -> bytes:
    payload = {
        "expected_version": 0,
        "key": "bad",
        "op": "put",
        "request_id": "bad-field",
        "seq": 0,
        "value": "B",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    record = dict(payload)
    record["crc32"] = f"{zlib.crc32(canonical) & 0xFFFFFFFF:08x}"
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def raw_record(payload: dict[str, object]) -> bytes:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    record = dict(payload)
    record["crc32"] = f"{zlib.crc32(canonical) & 0xFFFFFFFF:08x}"
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


class JournalCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "state"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def command(self, *arguments: str) -> tuple[int, dict[str, object]]:
        return run_cli(self.root, *arguments)

    def put(self, key: str, value: str, request_id: str, expected_version: int):
        return self.command(
            "put",
            "--key",
            key,
            "--value",
            value,
            "--request-id",
            request_id,
            "--expected-version",
            str(expected_version),
        )

    def delete(self, key: str, request_id: str, expected_version: int):
        return self.command(
            "delete",
            "--key",
            key,
            "--request-id",
            request_id,
            "--expected-version",
            str(expected_version),
        )

    def assert_error(self, result, code: str, exit_code: int) -> None:
        actual_exit, body = result
        self.assertEqual(actual_exit, exit_code)
        self.assertEqual(set(body), {"ok", "error"})
        self.assertEqual(body["ok"], False)
        self.assertEqual(set(body["error"]), {"code", "message"})
        self.assertEqual(body["error"]["code"], code)
        self.assertIsInstance(body["error"]["message"], str)

    def test_sc_01_canonical_record_crc_and_validation(self) -> None:
        payload = {
            "expected_version": 0,
            "key": "alpha",
            "op": "put",
            "request_id": "r-1",
            "seq": 1,
            "value": "A",
        }
        raw = encode_record(payload)
        self.assertEqual(
            raw,
            b'{"crc32":"b3b3257b","expected_version":0,"key":"alpha","op":"put","request_id":"r-1","seq":1,"value":"A"}\n',
        )
        self.assertTrue(raw.endswith(b"\n"))
        decoded = decode_record(raw)
        self.assertEqual({key: value for key, value in decoded.items() if key != "crc32"}, payload)
        with self.assertRaises(RecordError):
            decode_record(raw.replace(b'"A"', b'"B"'))
        with self.assertRaises(RecordError):
            encode_record({**payload, "seq": 0})
        invalid_payloads = [
            {**payload, "expected_version": "0"},
            {**payload, "key": 1},
            {**payload, "op": "merge"},
            {**payload, "request_id": 1},
            {**payload, "seq": 0},
            {**payload, "value": None},
            {**payload, "op": "delete", "value": "A"},
            {**payload, "extra": "field"},
        ]
        for invalid_payload in invalid_payloads:
            with self.subTest(payload=invalid_payload):
                with self.assertRaises(RecordError):
                    decode_record(raw_record(invalid_payload))

    def test_sc_02_put_get_and_update_version(self) -> None:
        code, created = self.put("alpha", "A", "r1", 0)
        self.assertEqual(code, 0)
        self.assertEqual(created, {"ok": True, "seq": 1, "key": "alpha", "version": 1, "replayed": False})
        self.assertEqual(
            self.command("get", "--key", "alpha"),
            (0, {"ok": True, "key": "alpha", "value": "A", "version": 1}),
        )
        code, updated = self.put("alpha", "B", "r2", 1)
        self.assertEqual(code, 0)
        self.assertEqual(updated, {"ok": True, "seq": 2, "key": "alpha", "version": 2, "replayed": False})
        self.assertEqual(
            self.command("get", "--key", "alpha"),
            (0, {"ok": True, "key": "alpha", "value": "B", "version": 2}),
        )

    def test_sc_03_delete_tombstone_version(self) -> None:
        self.put("alpha", "A", "r1", 0)
        code, deleted = self.delete("alpha", "r2", 1)
        self.assertEqual(code, 0)
        self.assertEqual(deleted["version"], 2)
        self.assert_error(self.command("get", "--key", "alpha"), "NOT_FOUND", 3)
        code, restored = self.put("alpha", "B", "r3", 2)
        self.assertEqual(code, 0)
        self.assertEqual(restored["seq"], 3)

    def test_sc_04_missing_delete_and_stale_mutation_leave_log_unchanged(self) -> None:
        self.assertEqual(self.command("list"), (0, {"ok": True, "items": []}))
        events = self.root / "events.log"
        empty_events = events.read_bytes()
        self.assert_error(self.delete("missing", "missing-r", 0), "NOT_FOUND", 3)
        self.assertEqual(events.read_bytes(), empty_events)
        code, created = self.put("alpha", "A", "r1", 0)
        self.assertEqual(code, 0)
        self.assertEqual(created["seq"], 1)
        before = events.read_bytes()
        self.assert_error(self.put("alpha", "B", "r2", 0), "VERSION_CONFLICT", 4)
        self.assertEqual(events.read_bytes(), before)
        self.assert_error(self.delete("alpha", "r3", 0), "VERSION_CONFLICT", 4)
        self.assertEqual(events.read_bytes(), before)
        code, next_result = self.put("alpha", "B", "r3", 1)
        self.assertEqual(code, 0)
        self.assertEqual(next_result["seq"], 2)

    def test_sc_05_identical_request_replays_initial_result(self) -> None:
        _, first = self.put("alpha", "A", "r1", 0)
        events = (self.root / "events.log").read_bytes()
        code, replay = self.put("alpha", "A", "r1", 0)
        self.assertEqual(code, 0)
        self.assertEqual(replay, {**first, "replayed": True})
        self.assertEqual((self.root / "events.log").read_bytes(), events)

    def test_sc_06_request_id_change_is_idempotency_conflict(self) -> None:
        self.put("alpha", "A", "r1", 0)
        before = (self.root / "events.log").read_bytes()
        changed_requests = [
            ("put", "--key", "alpha", "--value", "B", "--request-id", "r1", "--expected-version", "0"),
            ("put", "--key", "beta", "--value", "A", "--request-id", "r1", "--expected-version", "0"),
            ("put", "--key", "alpha", "--value", "A", "--request-id", "r1", "--expected-version", "1"),
            ("delete", "--key", "alpha", "--request-id", "r1", "--expected-version", "1"),
        ]
        for arguments in changed_requests:
            with self.subTest(arguments=arguments):
                self.assert_error(self.command(*arguments), "IDEMPOTENCY_CONFLICT", 5)
                self.assertEqual((self.root / "events.log").read_bytes(), before)
                self.assertEqual(self.command("get", "--key", "alpha")[1]["value"], "A")

    def test_sc_07_list_only_live_items_in_key_order(self) -> None:
        self.put("z", "Z", "r1", 0)
        self.put("a", "A", "r2", 0)
        self.delete("z", "r3", 1)
        code, body = self.command("list")
        self.assertEqual(code, 0)
        self.assertEqual(body, {"ok": True, "items": [{"key": "a", "value": "A", "version": 2}]})

    def test_sc_08_recover_truncates_each_final_invalid_record_kind(self) -> None:
        valid_without_newline = encode_record(
            {
                "expected_version": 1,
                "key": "alpha",
                "op": "put",
                "request_id": "tail-no-newline",
                "seq": 2,
                "value": "B",
            }
        )[:-1]
        crc_failure = encode_record(
            {
                "expected_version": 1,
                "key": "alpha",
                "op": "put",
                "request_id": "tail-crc",
                "seq": 2,
                "value": "A",
            }
        ).replace(b'"A"', b'"B"')
        tails = [b"\xff", valid_without_newline, b"{broken}\n", canonical_tail_with_invalid_field(), crc_failure]
        for index, tail in enumerate(tails):
            with self.subTest(index=index):
                root = self.root / f"tail-{index}"
                code, _ = run_cli(root, "put", "--key", "alpha", "--value", "A", "--request-id", "r1", "--expected-version", "0")
                self.assertEqual(code, 0)
                events = root / "events.log"
                before_tail = events.stat().st_size
                events.write_bytes(events.read_bytes() + tail)
                self.assert_error(run_cli(root, "get", "--key", "alpha"), "RECOVERY_REQUIRED", 6)
                code, body = run_cli(root, "recover")
                self.assertEqual(code, 0)
                self.assertEqual(body, {"ok": True, "truncated_bytes": len(tail)})
                self.assertEqual(events.stat().st_size, before_tail)
                self.assertEqual(run_cli(root, "get", "--key", "alpha")[1]["value"], "A")
        self.assertEqual(self.command("recover"), (0, {"ok": True, "truncated_bytes": 0}))

    def test_sc_09_earlier_corruption_is_read_only_corrupt_log(self) -> None:
        self.put("alpha", "A", "r1", 0)
        first = (self.root / "events.log").read_bytes()
        later = encode_record(
            {
                "expected_version": 0,
                "key": "beta",
                "op": "put",
                "request_id": "r2",
                "seq": 2,
                "value": "B",
            }
        )
        events = self.root / "events.log"
        corrupted = first + b"{broken}\n" + later
        events.write_bytes(corrupted)
        for arguments in (
            ("get", "--key", "alpha"),
            ("list",),
            ("put", "--key", "gamma", "--value", "G", "--request-id", "r3", "--expected-version", "0"),
            ("delete", "--key", "alpha", "--request-id", "r4", "--expected-version", "1"),
            ("recover",),
            ("compact",),
        ):
            with self.subTest(arguments=arguments):
                self.assert_error(self.command(*arguments), "CORRUPT_LOG", 7)
                self.assertEqual(events.read_bytes(), corrupted)

        semantic_root = self.root / "semantic-final-record"
        self.assertEqual(
            run_cli(semantic_root, "put", "--key", "a", "--value", "A", "--request-id", "s1", "--expected-version", "0")[0],
            0,
        )
        semantic_events = semantic_root / "events.log"
        semantic_events.write_bytes(
            semantic_events.read_bytes()
            + encode_record(
                {
                    "expected_version": 1,
                    "key": "a",
                    "op": "put",
                    "request_id": "s2",
                    "seq": 3,
                    "value": "B",
                }
            )
        )
        preserved = semantic_events.read_bytes()
        for arguments in (
            ("get", "--key", "a"),
            ("put", "--key", "b", "--value", "B", "--request-id", "s3", "--expected-version", "0"),
            ("delete", "--key", "a", "--request-id", "s4", "--expected-version", "1"),
            ("recover",),
        ):
            with self.subTest(arguments=arguments):
                self.assert_error(run_cli(semantic_root, *arguments), "CORRUPT_LOG", 7)
                self.assertEqual(semantic_events.read_bytes(), preserved)

    def test_sc_10_snapshot_validation_and_abandoned_tmp(self) -> None:
        self.put("alpha", "A", "r1", 0)
        self.assertEqual(self.command("compact"), (0, {"ok": True, "snapshot_seq": 1}))
        (self.root / "snapshot.json.tmp").write_bytes(b"{abandoned")
        self.assertEqual(self.command("get", "--key", "alpha")[1]["value"], "A")
        (self.root / "snapshot.json").write_bytes(b"{broken")
        malformed_snapshot = (self.root / "snapshot.json").read_bytes()
        malformed_events = (self.root / "events.log").read_bytes()
        for arguments in (
            ("get", "--key", "alpha"),
            ("list",),
            ("put", "--key", "beta", "--value", "B", "--request-id", "r2", "--expected-version", "0"),
            ("delete", "--key", "alpha", "--request-id", "r3", "--expected-version", "1"),
            ("compact",),
            ("recover",),
        ):
            with self.subTest(arguments=arguments):
                self.assert_error(self.command(*arguments), "CORRUPT_SNAPSHOT", 8)
                self.assertEqual((self.root / "snapshot.json").read_bytes(), malformed_snapshot)
                self.assertEqual((self.root / "events.log").read_bytes(), malformed_events)

        semantic_root = self.root / "semantic-snapshot"
        self.assertEqual(
            run_cli(semantic_root, "put", "--key", "a", "--value", "A", "--request-id", "s1", "--expected-version", "0")[0],
            0,
        )
        self.assertEqual(run_cli(semantic_root, "compact")[0], 0)
        invalid_snapshot = {
            "last_seq": 1,
            "keys": {"a": {"value": None, "version": 1}},
            "requests": {
                "s1": {
                    "fingerprint": {
                        "op": "delete",
                        "key": "a",
                        "value": None,
                        "expected_version": 0,
                    },
                    "result": {"seq": 1, "key": "a", "version": 1, "replayed": False},
                }
            },
        }
        (semantic_root / "snapshot.json").write_text(
            json.dumps(invalid_snapshot, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        semantic_snapshot = (semantic_root / "snapshot.json").read_bytes()
        semantic_events = (semantic_root / "events.log").read_bytes()
        for arguments in (
            ("get", "--key", "a"),
            ("list",),
            ("put", "--key", "b", "--value", "B", "--request-id", "s2", "--expected-version", "0"),
            ("delete", "--key", "a", "--request-id", "s3", "--expected-version", "1"),
            ("compact",),
            ("recover",),
        ):
            with self.subTest(arguments=arguments):
                self.assert_error(run_cli(semantic_root, *arguments), "CORRUPT_SNAPSHOT", 8)
                self.assertEqual((semantic_root / "snapshot.json").read_bytes(), semantic_snapshot)
                self.assertEqual((semantic_root / "events.log").read_bytes(), semantic_events)

    def test_sc_11_compact_preserves_restart_and_idempotency(self) -> None:
        self.put("z", "Z", "r1", 0)
        self.put("a", "A", "r2", 0)
        self.delete("z", "r3", 1)
        self.assertEqual(self.command("compact"), (0, {"ok": True, "snapshot_seq": 3}))
        self.assertEqual((self.root / "events.log").read_bytes(), b"")
        code, replay = self.put("a", "A", "r2", 0)
        self.assertEqual(code, 0)
        self.assertEqual(replay["seq"], 2)
        self.assertTrue(replay["replayed"])
        code, mutation = self.put("z", "ZZ", "r4", 3)
        self.assertEqual(code, 0)
        self.assertEqual(mutation["seq"], 4)
        self.assertEqual(self.command("get", "--key", "z")[1]["value"], "ZZ")

        crash_root = self.root / "compact-replace-window"
        self.assertEqual(
            run_cli(crash_root, "put", "--key", "a", "--value", "A", "--request-id", "c1", "--expected-version", "0")[0],
            0,
        )
        old_journal = (crash_root / "events.log").read_bytes()
        self.assertEqual(run_cli(crash_root, "compact"), (0, {"ok": True, "snapshot_seq": 1}))
        (crash_root / "events.log").write_bytes(old_journal)
        self.assertEqual(
            run_cli(crash_root, "put", "--key", "b", "--value", "B", "--request-id", "c2", "--expected-version", "0")[0],
            0,
        )
        self.assertEqual(run_cli(crash_root, "get", "--key", "b")[1]["value"], "B")

    def test_sc_12_cli_parameter_and_not_found_contract(self) -> None:
        success_root = self.root / "success-contract"
        success_cases = [
            (("list",), {"ok", "items"}),
            (("put", "--key", "alpha", "--value", "A", "--request-id", "p1", "--expected-version", "0"), {"ok", "seq", "key", "version", "replayed"}),
            (("get", "--key", "alpha"), {"ok", "key", "value", "version"}),
            (("delete", "--key", "alpha", "--request-id", "d1", "--expected-version", "1"), {"ok", "seq", "key", "version", "replayed"}),
            (("list",), {"ok", "items"}),
            (("compact",), {"ok", "snapshot_seq"}),
            (("recover",), {"ok", "truncated_bytes"}),
        ]
        for arguments, fields in success_cases:
            with self.subTest(arguments=arguments):
                code, body = run_cli(success_root, *arguments)
                self.assertEqual(code, 0)
                self.assertEqual(body["ok"], True)
                self.assertEqual(set(body), fields)

        self.assert_error(self.command("get", "--key", "missing"), "NOT_FOUND", 3)
        code, body = self.command("put", "--key", "alpha")
        self.assertEqual(code, 2)
        self.assertEqual(set(body), {"ok", "error"})
        self.assertEqual(body["error"]["code"], "INVALID_ARGUMENT")

        conflict_root = self.root / "version-conflict"
        self.assertEqual(run_cli(conflict_root, "put", "--key", "a", "--value", "A", "--request-id", "v1", "--expected-version", "0")[0], 0)
        self.assert_error(
            run_cli(conflict_root, "put", "--key", "a", "--value", "B", "--request-id", "v2", "--expected-version", "0"),
            "VERSION_CONFLICT",
            4,
        )

        idempotency_root = self.root / "idempotency-conflict"
        self.assertEqual(run_cli(idempotency_root, "put", "--key", "a", "--value", "A", "--request-id", "i1", "--expected-version", "0")[0], 0)
        self.assert_error(
            run_cli(idempotency_root, "put", "--key", "a", "--value", "B", "--request-id", "i1", "--expected-version", "1"),
            "IDEMPOTENCY_CONFLICT",
            5,
        )

        tail_root = self.root / "recovery-required"
        self.assertEqual(run_cli(tail_root, "put", "--key", "a", "--value", "A", "--request-id", "t1", "--expected-version", "0")[0], 0)
        tail_events = tail_root / "events.log"
        tail_events.write_bytes(tail_events.read_bytes() + b"{tail")
        self.assert_error(run_cli(tail_root, "list"), "RECOVERY_REQUIRED", 6)

        corrupt_log_root = self.root / "corrupt-log"
        self.assertEqual(run_cli(corrupt_log_root, "put", "--key", "a", "--value", "A", "--request-id", "l1", "--expected-version", "0")[0], 0)
        corrupt_events = corrupt_log_root / "events.log"
        corrupt_events.write_bytes(
            corrupt_events.read_bytes()
            + b"{broken}\n"
            + raw_record(
                {
                    "expected_version": 0,
                    "key": "b",
                    "op": "put",
                    "request_id": "l2",
                    "seq": 2,
                    "value": "B",
                }
            )
        )
        self.assert_error(run_cli(corrupt_log_root, "list"), "CORRUPT_LOG", 7)

        corrupt_snapshot_root = self.root / "corrupt-snapshot"
        self.assertEqual(run_cli(corrupt_snapshot_root, "put", "--key", "a", "--value", "A", "--request-id", "c1", "--expected-version", "0")[0], 0)
        self.assertEqual(run_cli(corrupt_snapshot_root, "compact")[0], 0)
        (corrupt_snapshot_root / "snapshot.json").write_bytes(b"{snapshot")
        self.assert_error(run_cli(corrupt_snapshot_root, "list"), "CORRUPT_SNAPSHOT", 8)

    def test_sc_13_cross_process_serialization(self) -> None:
        roots = self.root / "concurrent"

        def different_key(index: int):
            return run_cli(
                roots,
                "put",
                "--key",
                f"k{index:02d}",
                "--value",
                str(index),
                "--request-id",
                f"d{index}",
                "--expected-version",
                "0",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            different_results = list(executor.map(different_key, range(8)))
        self.assertEqual([code for code, _ in different_results], [0] * 8)
        _, listed = run_cli(roots, "list")
        versions = [item["version"] for item in listed["items"]]
        self.assertEqual(len(versions), 8)
        self.assertEqual(len(set(versions)), 8)

        same_root = self.root / "same-key"

        def same_key(index: int):
            return run_cli(
                same_root,
                "put",
                "--key",
                "same",
                "--value",
                str(index),
                "--request-id",
                f"s{index}",
                "--expected-version",
                "0",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            same_results = list(executor.map(same_key, range(8)))
        self.assertEqual([code for code, _ in same_results].count(0), 1)
        self.assertEqual([code for code, _ in same_results].count(4), 7)

        overlap_root = self.root / "overlap"
        self.assertEqual(run_cli(overlap_root, "put", "--key", "base", "--value", "B", "--request-id", "b1", "--expected-version", "0")[0], 0)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            overlap_results = list(
                executor.map(
                    lambda args: run_cli(overlap_root, *args),
                    [
                        ("compact",),
                        ("recover",),
                        ("put", "--key", "next", "--value", "N", "--request-id", "n1", "--expected-version", "0"),
                    ],
                )
            )
        self.assertEqual([code for code, _ in overlap_results], [0, 0, 0])
        self.assertEqual(run_cli(overlap_root, "get", "--key", "next")[1]["value"], "N")


if __name__ == "__main__":
    unittest.main()
