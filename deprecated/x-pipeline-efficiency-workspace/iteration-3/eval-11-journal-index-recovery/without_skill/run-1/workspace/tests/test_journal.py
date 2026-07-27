from __future__ import annotations

import concurrent.futures
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zlib


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND = WORKSPACE / "fixture" / "backend"
CLI = BACKEND / "cli.py"
sys.path.insert(0, str(BACKEND))

from record import RecordError, decode_record, encode_record  # noqa: E402
import store as store_module  # noqa: E402
from store import JournalStore  # noqa: E402


def cli(root: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(CLI), "--root", str(root), *args],
        cwd=WORKSPACE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
    )
    lines = proc.stdout.splitlines()
    if len(lines) != 1:
        raise AssertionError(
            f"CLI must emit one stdout JSON object; rc={proc.returncode}, "
            f"stdout={proc.stdout!r}, stderr={proc.stderr!r}"
        )
    try:
        result = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise AssertionError(f"invalid CLI JSON: {proc.stdout!r}") from exc
    if not isinstance(result, dict):
        raise AssertionError(f"CLI JSON must be an object: {result!r}")
    return proc, result


def put(root: Path, key: str, value: str, request_id: str, version: int):
    return cli(
        root,
        "put",
        "--key",
        key,
        "--value",
        value,
        "--request-id",
        request_id,
        "--expected-version",
        str(version),
    )


def delete(root: Path, key: str, request_id: str, version: int):
    return cli(
        root,
        "delete",
        "--key",
        key,
        "--request-id",
        request_id,
        "--expected-version",
        str(version),
    )


def raw_record(core: dict[str, object], *, crc: str | None = None) -> bytes:
    canonical = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    actual_crc = crc or f"{zlib.crc32(canonical) & 0xFFFFFFFF:08x}"
    return (
        json.dumps(
            {**core, "crc32": actual_crc}, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        + b"\n"
    )


class RecordCodecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = {
            "expected_version": 0,
            "key": "alpha",
            "op": "put",
            "request_id": "r-1",
            "seq": 1,
            "value": "A",
        }

    def test_canonical_crc_round_trip(self) -> None:
        canonical = json.dumps(
            self.base, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        crc = f"{zlib.crc32(canonical) & 0xFFFFFFFF:08x}"
        expected = dict(self.base, crc32=crc)
        raw = encode_record(self.base)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(
            raw,
            json.dumps(
                expected, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            + b"\n",
        )
        self.assertEqual(decode_record(raw), expected)

    def test_strict_decode_rejects_all_record_corruption_classes(self) -> None:
        invalid_cores = [
            {k: v for k, v in self.base.items() if k != "key"},
            dict(self.base, extra=True),
            dict(self.base, key=7),
            dict(self.base, request_id=None),
            dict(self.base, seq=True),
            dict(self.base, seq=0),
            dict(self.base, seq=-1),
            dict(self.base, seq=1.5),
            dict(self.base, expected_version=True),
            dict(self.base, expected_version=-1),
            dict(self.base, expected_version=1.0),
            dict(self.base, op="merge"),
            dict(self.base, value=9),
            dict(self.base, op="delete", value="not-null"),
        ]
        invalid_raw = [b"\xff\n", b"{bad json}\n"]
        invalid_raw.extend(raw_record(core) for core in invalid_cores)
        invalid_raw.extend(
            raw_record(self.base, crc=crc)
            for crc in ("00000000", "ABCDEF12", "abc", "gggggggg")
        )
        for raw in invalid_raw:
            with self.subTest(raw=raw):
                with self.assertRaises(RecordError):
                    decode_record(raw)


class JournalCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "state"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def assert_error(self, result: dict[str, object], code: str) -> None:
        self.assertEqual(result.get("ok"), False)
        error = result.get("error")
        self.assertIsInstance(error, dict)
        assert isinstance(error, dict)
        self.assertEqual(error.get("code"), code)
        self.assertIsInstance(error.get("message"), str)
        self.assertTrue(error.get("message"))

    def test_crud_versions_idempotency_and_restart(self) -> None:
        p1, r1 = put(self.root, "alpha", "A", "r-1", 0)
        self.assertEqual(p1.returncode, 0)
        self.assertEqual(
            r1,
            {"ok": True, "seq": 1, "key": "alpha", "version": 1, "replayed": False},
        )
        before_retry = (self.root / "events.log").read_bytes()
        pr, retry = put(self.root, "alpha", "A", "r-1", 0)
        self.assertEqual(pr.returncode, 0)
        self.assertEqual(retry, dict(r1, replayed=True))
        self.assertEqual((self.root / "events.log").read_bytes(), before_retry)

        p2, r2 = put(self.root, "alpha", "B", "r-2", 1)
        self.assertEqual(p2.returncode, 0)
        self.assertEqual(
            r2,
            {"ok": True, "seq": 2, "key": "alpha", "version": 2, "replayed": False},
        )
        _, latest = cli(self.root, "get", "--key", "alpha")
        self.assertEqual(latest, {"ok": True, "key": "alpha", "value": "B", "version": 2})

        before_old_retry = (self.root / "events.log").read_bytes()
        _, old_retry = put(self.root, "alpha", "A", "r-1", 0)
        self.assertEqual(old_retry, dict(r1, replayed=True))
        self.assertEqual((self.root / "events.log").read_bytes(), before_old_retry)
        _, after_old_retry = cli(self.root, "get", "--key", "alpha")
        self.assertEqual(
            after_old_retry,
            {"ok": True, "key": "alpha", "value": "B", "version": 2},
        )
        conflict_proc, conflict = put(self.root, "alpha", "changed", "r-1", 0)
        self.assertEqual(conflict_proc.returncode, 5)
        self.assert_error(conflict, "IDEMPOTENCY_CONFLICT")

        before_version = (self.root / "events.log").read_bytes()
        version_proc, version_result = put(self.root, "alpha", "C", "r-3", 0)
        self.assertEqual(version_proc.returncode, 4)
        self.assert_error(version_result, "VERSION_CONFLICT")
        self.assertEqual((self.root / "events.log").read_bytes(), before_version)

        put(self.root, "zeta", "Z", "r-z", 0)
        put(self.root, "beta", "B", "r-b", 0)
        list_proc, listed = cli(self.root, "list")
        self.assertEqual(list_proc.returncode, 0)
        self.assertEqual(
            listed,
            {
                "ok": True,
                "items": [
                    {"key": "alpha", "value": "B", "version": 2},
                    {"key": "beta", "value": "B", "version": 4},
                    {"key": "zeta", "value": "Z", "version": 3},
                ],
            },
        )

        delete_proc, deleted = delete(self.root, "alpha", "r-del", 2)
        self.assertEqual(delete_proc.returncode, 0)
        self.assertEqual(
            deleted,
            {"ok": True, "seq": 5, "key": "alpha", "version": 5, "replayed": False},
        )
        tombstone = decode_record((self.root / "events.log").read_bytes().splitlines()[-1])
        self.assertEqual(
            {key: tombstone[key] for key in ("op", "key", "value", "seq", "expected_version")},
            {"op": "delete", "key": "alpha", "value": None, "seq": 5, "expected_version": 2},
        )
        get_proc, missing = cli(self.root, "get", "--key", "alpha")
        self.assertEqual(get_proc.returncode, 3)
        self.assert_error(missing, "NOT_FOUND")
        _, listed_after = cli(self.root, "list")
        self.assertEqual(
            listed_after,
            {
                "ok": True,
                "items": [
                    {"key": "beta", "value": "B", "version": 4},
                    {"key": "zeta", "value": "Z", "version": 3},
                ],
            },
        )

        before_absent_delete = (self.root / "events.log").read_bytes()
        tomb_proc, tomb_result = delete(self.root, "alpha", "r-del-2", 5)
        self.assertEqual(tomb_proc.returncode, 3)
        self.assert_error(tomb_result, "NOT_FOUND")
        self.assertEqual((self.root / "events.log").read_bytes(), before_absent_delete)
        _, still_missing = cli(self.root, "get", "--key", "alpha")
        self.assert_error(still_missing, "NOT_FOUND")
        reused_absent_proc, reused_absent = put(
            self.root, "alpha", "restored", "r-del-2", 5
        )
        self.assertEqual(reused_absent_proc.returncode, 0)
        self.assertEqual(reused_absent["seq"], 6)

        before_wrong_version = (self.root / "events.log").read_bytes()
        wrong_proc, wrong_result = delete(self.root, "alpha", "r-del-3", 0)
        self.assertEqual(wrong_proc.returncode, 4)
        self.assert_error(wrong_result, "VERSION_CONFLICT")
        self.assertEqual((self.root / "events.log").read_bytes(), before_wrong_version)
        _, after_wrong_version = cli(self.root, "get", "--key", "alpha")
        self.assertEqual(
            after_wrong_version,
            {"ok": True, "key": "alpha", "value": "restored", "version": 6},
        )
        reused_version_proc, reused_version = put(
            self.root, "alpha", "after-conflict", "r-del-3", 6
        )
        self.assertEqual(reused_version_proc.returncode, 0)
        self.assertEqual(reused_version["seq"], 7)

    def test_idempotency_fingerprint_checks_each_request_field(self) -> None:
        variants = {
            "value": lambda root: put(root, "alpha", "changed", "shared", 0),
            "key": lambda root: put(root, "beta", "A", "shared", 0),
            "expected_version": lambda root: put(root, "alpha", "A", "shared", 1),
            "op": lambda root: delete(root, "alpha", "shared", 1),
        }
        for name, conflicting_call in variants.items():
            with self.subTest(field=name):
                root = Path(self.temp.name) / f"fingerprint-{name}"
                _, first = put(root, "alpha", "A", "shared", 0)
                before = (root / "events.log").read_bytes()
                proc, result = conflicting_call(root)
                self.assertEqual(proc.returncode, 5)
                self.assert_error(result, "IDEMPOTENCY_CONFLICT")
                self.assertEqual((root / "events.log").read_bytes(), before)
                _, current = cli(root, "get", "--key", "alpha")
                self.assertEqual(
                    current, {"ok": True, "key": "alpha", "value": "A", "version": 1}
                )
                retry_proc, retry = put(root, "alpha", "A", "shared", 0)
                self.assertEqual(retry_proc.returncode, 0)
                self.assertEqual(retry, dict(first, replayed=True))

    def test_delete_never_seen_and_cli_parameter_errors(self) -> None:
        proc, result = delete(self.root, "missing", "r-missing", 0)
        self.assertEqual(proc.returncode, 3)
        self.assert_error(result, "NOT_FOUND")
        self.assertEqual((self.root / "events.log").read_bytes(), b"")

        cases = [(), ("unknown",), ("put", "--key", "x")]
        for args in cases:
            with self.subTest(args=args):
                p, body = cli(self.root, *args)
                self.assertEqual(p.returncode, 2)
                self.assert_error(body, "INVALID_ARGUMENT")

    def test_tail_recovery_and_healthy_recover_are_exact(self) -> None:
        put(self.root, "alpha", "A", "r-1", 0)
        log = self.root / "events.log"
        healthy = log.read_bytes()
        tail = b'{"crc32":"00000000"'
        with log.open("ab") as fh:
            fh.write(tail)
            fh.flush()
            os.fsync(fh.fileno())
        damaged = log.read_bytes()

        proc, result = cli(self.root, "get", "--key", "alpha")
        self.assertEqual(proc.returncode, 6)
        self.assert_error(result, "RECOVERY_REQUIRED")
        self.assertEqual(log.read_bytes(), damaged)

        recover_proc, recovered = cli(self.root, "recover")
        self.assertEqual(recover_proc.returncode, 0)
        self.assertEqual(recovered, {"ok": True, "truncated_bytes": len(tail)})
        self.assertEqual(log.read_bytes(), healthy)
        _, again = cli(self.root, "recover")
        self.assertEqual(again, {"ok": True, "truncated_bytes": 0})

    def test_each_last_record_corruption_is_recoverable(self) -> None:
        corrupt_tails = [
            b"\xff\n",
            b"{}\n",
            b'{"bad":true}\n',
            b'{"bad":\rbroken}\n',
            b"[" * 2000 + b"]" * 2000 + b"\n",
            encode_record(
                {
                    "expected_version": 0,
                    "key": "unterminated",
                    "op": "put",
                    "request_id": "unterminated-request",
                    "seq": 2,
                    "value": "complete-json",
                }
            )[:-1],
            b'{"crc32":"00000000","expected_version":0,"key":"x","op":"put",'
            b'"request_id":"bad","seq":2,"value":"x"}\n',
        ]
        for index, tail in enumerate(corrupt_tails):
            root = Path(self.temp.name) / f"tail-{index}"
            put(root, "alpha", "A", f"r-{index}", 0)
            log = root / "events.log"
            healthy = log.read_bytes()
            with log.open("ab") as fh:
                fh.write(tail)
            proc, result = cli(root, "list")
            self.assertEqual(proc.returncode, 6)
            self.assert_error(result, "RECOVERY_REQUIRED")
            _, recovered = cli(root, "recover")
            self.assertEqual(recovered["truncated_bytes"], len(tail))
            self.assertEqual(log.read_bytes(), healthy)

    def test_deep_json_middle_record_is_corrupt_log(self) -> None:
        deep_json = b"[" * 2000 + b"]" * 2000 + b"\n"
        valid = encode_record(
            {
                "expected_version": 0,
                "key": "alpha",
                "op": "put",
                "request_id": "r-1",
                "seq": 1,
                "value": "A",
            }
        )
        self.root.mkdir(parents=True)
        log = self.root / "events.log"
        log.write_bytes(deep_json + valid)
        damaged = log.read_bytes()
        for command in (("list",), ("recover",)):
            proc, result = cli(self.root, *command)
            self.assertEqual(proc.returncode, 7)
            self.assert_error(result, "CORRUPT_LOG")
            self.assertEqual(log.read_bytes(), damaged)

    def test_middle_log_corruption_is_read_only_even_for_recover(self) -> None:
        put(self.root, "alpha", "A", "r-1", 0)
        put(self.root, "beta", "B", "r-2", 0)
        log = self.root / "events.log"
        lines = log.read_bytes().splitlines(keepends=True)
        lines[0] = b"{broken}\n"
        damaged = b"".join(lines)
        log.write_bytes(damaged)

        for command in (("list",), ("recover",), ("compact",)):
            with self.subTest(command=command):
                proc, result = cli(self.root, *command)
                self.assertEqual(proc.returncode, 7)
                self.assert_error(result, "CORRUPT_LOG")
                self.assertEqual(log.read_bytes(), damaged)

    def test_compact_restart_tmp_ignore_and_idempotency(self) -> None:
        _, first = put(self.root, "alpha", "A", "r-1", 0)
        _, beta_put = put(self.root, "beta", "B", "r-2", 0)
        _, beta_delete = delete(self.root, "beta", "r-3", 2)
        _, alpha_update = put(self.root, "alpha", "B", "r-4", 1)
        original_log = (self.root / "events.log").read_bytes()

        compact_proc, compacted = cli(self.root, "compact")
        self.assertEqual(compact_proc.returncode, 0)
        self.assertEqual(compacted, {"ok": True, "snapshot_seq": 4})
        self.assertEqual((self.root / "events.log").read_bytes(), b"")
        self.assertTrue((self.root / "snapshot.json").is_file())
        snapshot_data = json.loads((self.root / "snapshot.json").read_bytes())
        self.assertEqual(
            snapshot_data["requests"]["r-1"]["fingerprint"],
            {"op": "put", "key": "alpha", "value": "A", "expected_version": 0},
        )
        self.assertEqual(
            snapshot_data["requests"]["r-2"]["fingerprint"],
            {"op": "put", "key": "beta", "value": "B", "expected_version": 0},
        )
        self.assertEqual(
            snapshot_data["requests"]["r-3"]["fingerprint"],
            {"op": "delete", "key": "beta", "value": None, "expected_version": 2},
        )
        self.assertEqual(
            snapshot_data["requests"]["r-4"]["fingerprint"],
            {"op": "put", "key": "alpha", "value": "B", "expected_version": 1},
        )

        (self.root / "snapshot.json.tmp").write_bytes(b"totally invalid")
        _, got = cli(self.root, "get", "--key", "alpha")
        self.assertEqual(got, {"ok": True, "key": "alpha", "value": "B", "version": 4})
        _, listed = cli(self.root, "list")
        self.assertEqual(
            listed,
            {"ok": True, "items": [{"key": "alpha", "value": "B", "version": 4}]},
        )
        beta_proc, beta_missing = cli(self.root, "get", "--key", "beta")
        self.assertEqual(beta_proc.returncode, 3)
        self.assert_error(beta_missing, "NOT_FOUND")

        empty_log = (self.root / "events.log").read_bytes()
        retry_proc, retry = put(self.root, "alpha", "A", "r-1", 0)
        self.assertEqual(retry_proc.returncode, 0)
        self.assertEqual(retry, dict(first, replayed=True))
        _, retry_beta_put = put(self.root, "beta", "B", "r-2", 0)
        self.assertEqual(retry_beta_put, dict(beta_put, replayed=True))
        _, retry_beta_delete = delete(self.root, "beta", "r-3", 2)
        self.assertEqual(retry_beta_delete, dict(beta_delete, replayed=True))
        _, retry_alpha_update = put(self.root, "alpha", "B", "r-4", 1)
        self.assertEqual(retry_alpha_update, dict(alpha_update, replayed=True))
        self.assertEqual((self.root / "events.log").read_bytes(), empty_log)
        _, after_replays = cli(self.root, "get", "--key", "alpha")
        self.assertEqual(
            after_replays, {"ok": True, "key": "alpha", "value": "B", "version": 4}
        )
        absent_delete_proc, absent_delete = delete(self.root, "beta", "new-delete", 3)
        self.assertEqual(absent_delete_proc.returncode, 3)
        self.assert_error(absent_delete, "NOT_FOUND")
        self.assertEqual((self.root / "events.log").read_bytes(), empty_log)
        _, new = put(self.root, "gamma", "G", "r-5", 0)
        self.assertEqual(new["seq"], 5)

        # Simulate the authorized crash window after snapshot replace and before log replacement.
        overlap_root = Path(self.temp.name) / "overlap"
        put(overlap_root, "a", "1", "o-1", 0)
        put(overlap_root, "b", "2", "o-2", 0)
        overlap_log = (overlap_root / "events.log").read_bytes()
        cli(overlap_root, "compact")
        (overlap_root / "events.log").write_bytes(overlap_log)
        _, overlap_list = cli(overlap_root, "list")
        self.assertEqual([i["key"] for i in overlap_list["items"]], ["a", "b"])
        _, overlap_retry = put(overlap_root, "a", "1", "o-1", 0)
        self.assertEqual(overlap_retry["seq"], 1)
        self.assertEqual(overlap_retry["replayed"], True)
        _, overlap_new = put(overlap_root, "c", "3", "o-3", 0)
        self.assertEqual(overlap_new["seq"], 3)

    def test_corrupt_snapshot_never_falls_back_or_rewrites(self) -> None:
        put(self.root, "alpha", "A", "r-1", 0)
        cli(self.root, "compact")
        snapshot = self.root / "snapshot.json"
        snapshot.write_bytes(b'{"last_seq":"bad"}\n')
        damaged = snapshot.read_bytes()
        for command in (("get", "--key", "alpha"), ("recover",), ("compact",)):
            with self.subTest(command=command):
                proc, result = cli(self.root, *command)
                self.assertEqual(proc.returncode, 8)
                self.assert_error(result, "CORRUPT_SNAPSHOT")
                self.assertEqual(snapshot.read_bytes(), damaged)

    def test_nested_snapshot_type_corruption_maps_to_corrupt_snapshot(self) -> None:
        put(self.root, "alpha", "A", "r-1", 0)
        cli(self.root, "compact")
        snapshot = self.root / "snapshot.json"
        decoded = json.loads(snapshot.read_bytes())
        decoded["requests"]["r-1"]["fingerprint"]["op"] = []
        snapshot.write_text(json.dumps(decoded), encoding="utf-8")
        damaged = snapshot.read_bytes()

        proc, result = cli(self.root, "list")
        self.assertEqual(proc.returncode, 8)
        self.assert_error(result, "CORRUPT_SNAPSHOT")
        self.assertEqual(snapshot.read_bytes(), damaged)

    def test_hostile_snapshot_depth_and_declared_sequence_are_bounded(self) -> None:
        self.root.mkdir(parents=True)
        snapshot = self.root / "snapshot.json"
        corrupt_snapshots = [
            b"[" * 2000 + b"]" * 2000,
            json.dumps(
                {
                    "format_version": 1,
                    "last_seq": 1_000_000_000,
                    "entries": {},
                    "requests": {},
                }
            ).encode(),
        ]
        for raw in corrupt_snapshots:
            with self.subTest(size=len(raw)):
                snapshot.write_bytes(raw)
                proc, result = cli(self.root, "list")
                self.assertEqual(proc.returncode, 8)
                self.assert_error(result, "CORRUPT_SNAPSHOT")
                self.assertEqual(snapshot.read_bytes(), raw)

    def test_recover_partial_snapshot_overlap_tail_remains_loadable(self) -> None:
        put(self.root, "alpha", "A", "r-1", 0)
        put(self.root, "beta", "B", "r-2", 0)
        log = self.root / "events.log"
        first_record = log.read_bytes().split(b"\n", 1)[0] + b"\n"
        cli(self.root, "compact")
        corrupt_tail = b'{"broken":'
        log.write_bytes(first_record + corrupt_tail)

        failed, result = cli(self.root, "list")
        self.assertEqual(failed.returncode, 6)
        self.assert_error(result, "RECOVERY_REQUIRED")
        recovered, body = cli(self.root, "recover")
        self.assertEqual(recovered.returncode, 0)
        self.assertEqual(body["truncated_bytes"], len(corrupt_tail))
        _, listed = cli(self.root, "list")
        self.assertEqual([item["key"] for item in listed["items"]], ["alpha", "beta"])
        _, following = put(self.root, "gamma", "G", "r-3", 0)
        self.assertEqual(following["seq"], 3)
        _, final = cli(self.root, "list")
        self.assertEqual([item["key"] for item in final["items"]], ["alpha", "beta", "gamma"])

    def test_crc_valid_replay_invariant_violation_is_corrupt_log(self) -> None:
        put(self.root, "alpha", "A", "duplicate-request", 0)
        log = self.root / "events.log"
        duplicate = encode_record(
            {
                "expected_version": 0,
                "key": "beta",
                "op": "put",
                "request_id": "duplicate-request",
                "seq": 2,
                "value": "B",
            }
        )
        with log.open("ab") as stream:
            stream.write(duplicate)
        damaged = log.read_bytes()

        for command in (("list",), ("recover",)):
            with self.subTest(command=command):
                proc, result = cli(self.root, *command)
                self.assertEqual(proc.returncode, 7)
                self.assert_error(result, "CORRUPT_LOG")
                self.assertEqual(log.read_bytes(), damaged)

    def test_durability_primitive_order_for_append_and_compact(self) -> None:
        store = JournalStore(self.root)

        real_lock = store_module.StateLock
        real_open = Path.open
        real_fsync = os.fsync
        real_replace = os.replace

        def tracked_lock(events: list[tuple[object, ...]]):
            class TrackingLock:
                def __init__(self, root, *, exclusive: bool) -> None:
                    self.inner = real_lock(root, exclusive=exclusive)
                    self.exclusive = exclusive

                def __enter__(self):
                    events.append(("lock_enter", self.exclusive))
                    self.inner.__enter__()
                    events.append(("lock_acquired", self.exclusive))
                    return self

                def __exit__(self, exc_type, exc, tb):
                    events.append(("lock_release", self.exclusive))
                    result = self.inner.__exit__(exc_type, exc, tb)
                    events.append(("lock_released", self.exclusive))
                    return result

            return TrackingLock

        class TrackingFile:
            def __init__(
                self,
                inner,
                label: str,
                events: list[tuple[object, ...]],
                active_fds: dict[int, str] | None = None,
            ) -> None:
                self.inner = inner
                self.label = label
                self.events = events
                self.fd = inner.fileno()
                self.active_fds = active_fds
                if active_fds is not None:
                    active_fds[self.fd] = label

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self.events.append(("close", self.label, self.fd))
                try:
                    return self.inner.__exit__(exc_type, exc, tb)
                finally:
                    if self.active_fds is not None:
                        self.active_fds.pop(self.fd, None)

            def write(self, data):
                self.events.append(("write", self.label, self.fd))
                return self.inner.write(data)

            def truncate(self, size=None):
                self.events.append(("truncate", self.label, self.fd))
                return self.inner.truncate(size)

            def flush(self):
                self.events.append(("flush", self.label, self.fd))
                return self.inner.flush()

            def fileno(self):
                return self.fd

            def __getattr__(self, name):
                return getattr(self.inner, name)

        def event_index(events: list[tuple[object, ...]], name: str, label: str | None = None) -> int:
            for index, event in enumerate(events):
                if event[0] == name and (label is None or event[1] == label):
                    return index
            self.fail(f"missing durability event: {name} {label or ''}; got {events!r}")

        append_events: list[tuple[object, ...]] = []

        def append_open(path, mode="r", *args, **kwargs):
            inner = real_open(path, mode, *args, **kwargs)
            if Path(path) == store.events_path and mode == "ab":
                return TrackingFile(inner, "append", append_events)
            return inner

        def append_fsync(fd: int):
            append_events.append(("fsync", "file", fd))
            return real_fsync(fd)

        real_load = store._load

        def append_load():
            append_events.append(("load_start",))
            result = real_load()
            append_events.append(("load_end",))
            return result

        with mock.patch.object(Path, "open", new=append_open), \
             mock.patch.object(store_module, "StateLock", new=tracked_lock(append_events)), \
             mock.patch.object(store_module.os, "fsync", new=append_fsync), \
             mock.patch.object(store, "_load", new=append_load):
            result = store.put(
                key="alpha", value="A", request_id="durable-1", expected_version=0
            )
            append_events.append(("return", result["seq"]))
        self.assertEqual(result["seq"], 1)
        self.assertLess(event_index(append_events, "lock_acquired"), event_index(append_events, "load_start"))
        self.assertLess(event_index(append_events, "load_end"), event_index(append_events, "write"))
        self.assertLess(event_index(append_events, "write"), event_index(append_events, "flush"))
        self.assertLess(event_index(append_events, "flush"), event_index(append_events, "fsync"))
        self.assertLess(event_index(append_events, "fsync"), event_index(append_events, "lock_release"))
        self.assertLess(event_index(append_events, "lock_released"), event_index(append_events, "return"))
        append_fd = append_events[event_index(append_events, "write")][2]
        self.assertEqual(append_events[event_index(append_events, "fsync")][2], append_fd)
        self.assertIn(("lock_enter", True), append_events)

        conflict_events: list[tuple[object, ...]] = []
        real_store_error = store_module.StoreError
        conflict_load = store._load

        def tracked_conflict_load():
            conflict_events.append(("load_start",))
            state = conflict_load()
            conflict_events.append(("load_end",))
            return state

        class TrackingStoreError(real_store_error):
            def __init__(self, code: str, message: str) -> None:
                conflict_events.append(("state_error", code))
                super().__init__(code, message)

        with mock.patch.object(store_module, "StateLock", new=tracked_lock(conflict_events)), \
             mock.patch.object(store_module, "StoreError", new=TrackingStoreError), \
             mock.patch.object(store, "_load", new=tracked_conflict_load):
            with self.assertRaises(real_store_error):
                store.put(
                    key="alpha", value="conflict", request_id="durable-conflict", expected_version=0
                )
        self.assertLess(event_index(conflict_events, "lock_acquired"), event_index(conflict_events, "load_start"))
        self.assertLess(event_index(conflict_events, "load_end"), event_index(conflict_events, "state_error"))
        self.assertLess(event_index(conflict_events, "state_error"), event_index(conflict_events, "lock_release"))

        log = store.events_path
        with log.open("ab") as stream:
            stream.write(b'{"broken":')
            stream.flush()
            real_fsync(stream.fileno())
        recover_events: list[tuple[object, ...]] = []

        def recover_open(path, mode="r", *args, **kwargs):
            inner = real_open(path, mode, *args, **kwargs)
            if Path(path) == log and mode == "r+b":
                return TrackingFile(inner, "recover", recover_events)
            return inner

        def recover_fsync(fd: int):
            recover_events.append(("fsync", "file", fd))
            return real_fsync(fd)

        real_decode_snapshot = store._decode_snapshot
        real_scan_log = store._scan_log

        def recover_decode_snapshot():
            recover_events.append(("decode_snapshot_start",))
            state = real_decode_snapshot()
            recover_events.append(("decode_snapshot_end",))
            return state

        def recover_scan_log(state):
            recover_events.append(("scan_log_start",))
            scan = real_scan_log(state)
            recover_events.append(("scan_log_end",))
            return scan

        with mock.patch.object(Path, "open", new=recover_open), \
             mock.patch.object(store_module, "StateLock", new=tracked_lock(recover_events)), \
             mock.patch.object(store_module.os, "fsync", new=recover_fsync), \
             mock.patch.object(store, "_decode_snapshot", new=recover_decode_snapshot), \
             mock.patch.object(store, "_scan_log", new=recover_scan_log):
            recovered = store.recover()
            recover_events.append(("return", recovered["truncated_bytes"]))
        self.assertGreater(recovered["truncated_bytes"], 0)
        self.assertLess(event_index(recover_events, "lock_acquired"), event_index(recover_events, "decode_snapshot_start"))
        self.assertLess(event_index(recover_events, "decode_snapshot_end"), event_index(recover_events, "scan_log_start"))
        self.assertLess(event_index(recover_events, "scan_log_end"), event_index(recover_events, "truncate"))
        self.assertLess(event_index(recover_events, "truncate"), event_index(recover_events, "flush"))
        self.assertLess(event_index(recover_events, "flush"), event_index(recover_events, "fsync"))
        self.assertLess(event_index(recover_events, "fsync"), event_index(recover_events, "lock_release"))
        self.assertLess(event_index(recover_events, "lock_released"), event_index(recover_events, "return"))
        recover_fd = recover_events[event_index(recover_events, "truncate")][2]
        self.assertEqual(recover_events[event_index(recover_events, "fsync")][2], recover_fd)
        self.assertIn(("lock_enter", True), recover_events)

        compact_events: list[tuple[object, ...]] = []
        compact_active_files: dict[int, str] = {}
        compact_directories: set[int] = set()
        real_os_open = os.open
        real_os_close = os.close

        def compact_open(path, mode="r", *args, **kwargs):
            inner = real_open(path, mode, *args, **kwargs)
            if mode == "wb" and Path(path).name in {"snapshot.json.tmp", "events.log.tmp"}:
                return TrackingFile(
                    inner, Path(path).name, compact_events, compact_active_files
                )
            return inner

        def compact_fsync(fd: int):
            file_mode = os.fstat(fd).st_mode
            if fd in compact_active_files:
                target = compact_active_files[fd]
            elif fd in compact_directories and stat.S_ISDIR(file_mode):
                target = "state-directory"
            else:
                target = "other"
            compact_events.append(("fsync", target, fd))
            return real_fsync(fd)

        def compact_os_open(path, flags, *args, **kwargs):
            fd = real_os_open(path, flags, *args, **kwargs)
            if Path(path) == self.root and stat.S_ISDIR(os.fstat(fd).st_mode):
                compact_directories.add(fd)
                compact_events.append(("directory_open", "state-directory", fd))
            return fd

        def compact_os_close(fd: int):
            try:
                return real_os_close(fd)
            finally:
                if fd in compact_directories:
                    compact_events.append(("directory_close", "state-directory", fd))
                    compact_directories.discard(fd)

        def compact_replace(source, target):
            compact_events.append(("replace", Path(source).name, Path(target).name))
            return real_replace(source, target)

        real_compact_load = store._load

        def compact_load():
            compact_events.append(("load_start",))
            state = real_compact_load()
            compact_events.append(("load_end",))
            return state

        with mock.patch.object(Path, "open", new=compact_open), \
             mock.patch.object(store_module, "StateLock", new=tracked_lock(compact_events)), \
             mock.patch.object(store_module.os, "fsync", new=compact_fsync), \
             mock.patch.object(store_module.os, "replace", new=compact_replace), \
             mock.patch.object(store_module.os, "open", new=compact_os_open), \
             mock.patch.object(store_module.os, "close", new=compact_os_close), \
             mock.patch.object(store, "_load", new=compact_load):
            store.compact()
            compact_events.append(("return",))
        compact_durability = [
            (event[0], event[1])
            for event in compact_events
            if event[0] in {"flush", "fsync", "replace"}
        ]
        self.assertEqual(
            compact_durability,
            [
                ("flush", "snapshot.json.tmp"),
                ("fsync", "snapshot.json.tmp"),
                ("replace", "snapshot.json.tmp"),
                ("fsync", "state-directory"),
                ("flush", "events.log.tmp"),
                ("fsync", "events.log.tmp"),
                ("replace", "events.log.tmp"),
                ("fsync", "state-directory"),
            ],
        )
        self.assertIn(("lock_enter", True), compact_events)
        self.assertLess(event_index(compact_events, "lock_acquired"), event_index(compact_events, "load_start"))
        self.assertLess(event_index(compact_events, "load_end"), event_index(compact_events, "write", "snapshot.json.tmp"))
        last_fsync = max(
            index for index, event in enumerate(compact_events) if event[0] == "fsync"
        )
        self.assertLess(last_fsync, event_index(compact_events, "lock_release"))
        self.assertLess(event_index(compact_events, "lock_released"), event_index(compact_events, "return"))


class JournalConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "state"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_concurrent_new_keys_have_unique_sequences_and_no_loss(self) -> None:
        count = 16
        with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
            futures = [
                pool.submit(put, self.root, f"key-{i:02d}", f"value-{i}", f"req-{i}", 0)
                for i in range(count)
            ]
        outcomes = [future.result() for future in futures]
        self.assertTrue(all(proc.returncode == 0 for proc, _ in outcomes))
        self.assertEqual(sorted(result["seq"] for _, result in outcomes), list(range(1, count + 1)))
        _, listed = cli(self.root, "list")
        self.assertEqual(len(listed["items"]), count)
        self.assertEqual(
            [item["key"] for item in listed["items"]],
            [f"key-{i:02d}" for i in range(count)],
        )

    def test_concurrent_same_version_has_exactly_one_commit(self) -> None:
        put(self.root, "shared", "initial", "seed", 0)
        count = 12
        with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
            futures = [
                pool.submit(put, self.root, "shared", f"value-{i}", f"race-{i}", 1)
                for i in range(count)
            ]
        outcomes = [future.result() for future in futures]
        self.assertEqual(sum(proc.returncode == 0 for proc, _ in outcomes), 1)
        self.assertEqual(sum(proc.returncode == 4 for proc, _ in outcomes), count - 1)
        self.assertEqual(len((self.root / "events.log").read_bytes().splitlines()), 2)
        _, current = cli(self.root, "get", "--key", "shared")
        self.assertEqual(current["version"], 2)

    def test_mutations_compact_and_recover_serialize_without_loss(self) -> None:
        count = 10
        operations = [
            (put, (self.root, f"mixed-{i:02d}", str(i), f"mixed-request-{i}", 0))
            for i in range(count)
        ]
        operations.extend((cli, (self.root, "compact")) for _ in range(3))
        operations.extend((cli, (self.root, "recover")) for _ in range(3))
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(function, *arguments) for function, arguments in operations]
        outcomes = [future.result() for future in futures]
        self.assertTrue(all(proc.returncode == 0 for proc, _ in outcomes))

        _, listed = cli(self.root, "list")
        self.assertEqual(
            [item["key"] for item in listed["items"]],
            [f"mixed-{i:02d}" for i in range(count)],
        )
        _, following = put(self.root, "after", "value", "after-request", 0)
        self.assertEqual(following["seq"], count + 1)


if __name__ == "__main__":
    unittest.main()
