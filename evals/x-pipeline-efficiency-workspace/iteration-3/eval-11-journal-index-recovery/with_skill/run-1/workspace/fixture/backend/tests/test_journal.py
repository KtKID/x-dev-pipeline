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


BACKEND = Path(__file__).resolve().parents[1]
CLI = BACKEND / "cli.py"
sys.path.insert(0, str(BACKEND))

from record import RecordError, decode_record, encode_record  # noqa: E402
import store as store_module  # noqa: E402
from store import JournalStore, StoreError  # noqa: E402


def assert_code(testcase: unittest.TestCase, code: str, fn, *args, **kwargs) -> StoreError:
    with testcase.assertRaises(StoreError) as caught:
        fn(*args, **kwargs)
    testcase.assertEqual(caught.exception.code, code)
    return caught.exception


class RecordTests(unittest.TestCase):
    def test_codec_round_trip_and_strict_validation(self) -> None:
        put = {
            "expected_version": 0,
            "key": "alpha",
            "op": "put",
            "request_id": "r-1",
            "seq": 1,
            "value": "A",
        }
        encoded = encode_record(put)
        payload = json.dumps(put, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected_crc = format(zlib.crc32(payload) & 0xFFFFFFFF, "08x")
        expected_record = {**put, "crc32": expected_crc}
        expected_bytes = (
            json.dumps(expected_record, sort_keys=True, separators=(",", ":")).encode("utf-8")
            + b"\n"
        )
        self.assertEqual(encoded, expected_bytes)
        decoded = decode_record(encoded)
        self.assertEqual({key: decoded[key] for key in put}, put)
        self.assertRegex(decoded["crc32"], r"^[0-9a-f]{8}$")

        damaged = bytearray(encoded)
        damaged[damaged.index(b"A")] = ord("B")
        with self.assertRaises(RecordError):
            decode_record(bytes(damaged))
        with self.assertRaises(RecordError):
            encode_record({**put, "seq": True})
        with self.assertRaises(RecordError):
            encode_record({**put, "extra": "field"})
        with self.assertRaises(RecordError):
            encode_record({**put, "op": "delete", "value": "A"})


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "state"
        self.store = JournalStore(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_state_version_delete_and_ordering(self) -> None:
        beta = self.store.put(
            key="beta", value="B", request_id="r-beta", expected_version=0
        )
        alpha = self.store.put(
            key="alpha", value="A", request_id="r-alpha", expected_version=0
        )
        self.assertEqual((beta["seq"], alpha["seq"]), (1, 2))
        self.assertEqual(self.store.get("alpha"), {"key": "alpha", "value": "A", "version": 2})
        self.assertEqual([item["key"] for item in self.store.list_items()], ["alpha", "beta"])

        before = (self.root / "events.log").read_bytes()
        assert_code(
            self,
            "VERSION_CONFLICT",
            self.store.put,
            key="alpha",
            value="bad",
            request_id="r-bad",
            expected_version=0,
        )
        self.assertEqual((self.root / "events.log").read_bytes(), before)

        deleted = self.store.delete(key="alpha", request_id="r-del", expected_version=2)
        self.assertEqual(deleted["seq"], 3)
        assert_code(self, "NOT_FOUND", self.store.get, "alpha")
        self.assertEqual([item["key"] for item in self.store.list_items()], ["beta"])
        assert_code(
            self,
            "VERSION_CONFLICT",
            self.store.put,
            key="alpha",
            value="again",
            request_id="r-zero",
            expected_version=0,
        )
        restored = self.store.put(
            key="alpha", value="again", request_id="r-again", expected_version=3
        )
        self.assertEqual(restored["seq"], 4)

    def test_delete_never_seen_is_not_found(self) -> None:
        before_exists = (self.root / "events.log").exists()
        assert_code(
            self,
            "NOT_FOUND",
            self.store.delete,
            key="missing",
            request_id="r-missing",
            expected_version=0,
        )
        self.assertTrue(before_exists or (self.root / "events.log").read_bytes() == b"")

    def test_idempotency_same_and_conflicting_request(self) -> None:
        first = self.store.put(
            key="alpha", value="A", request_id="request", expected_version=0
        )
        size = (self.root / "events.log").stat().st_size
        replay = JournalStore(self.root).put(
            key="alpha", value="A", request_id="request", expected_version=0
        )
        self.assertEqual(replay["seq"], first["seq"])
        self.assertTrue(replay["replayed"])
        self.assertEqual((self.root / "events.log").stat().st_size, size)
        assert_code(
            self,
            "IDEMPOTENCY_CONFLICT",
            self.store.put,
            key="alpha",
            value="different",
            request_id="request",
            expected_version=0,
        )
        self.assertEqual((self.root / "events.log").stat().st_size, size)

    def test_tail_recovery_and_healthy_recover(self) -> None:
        self.store.put(key="alpha", value="A", request_id="r-1", expected_version=0)
        log = self.root / "events.log"
        original = log.read_bytes()
        tail = b'{"broken":"\xf0\x9f'
        with log.open("ab") as handle:
            handle.write(tail)
        assert_code(self, "RECOVERY_REQUIRED", self.store.get, "alpha")
        self.assertEqual(log.read_bytes(), original + tail)
        self.assertEqual(self.store.recover(), {"truncated_bytes": len(tail)})
        self.assertEqual(log.read_bytes(), original)
        self.assertEqual(self.store.recover(), {"truncated_bytes": 0})
        self.assertEqual(self.store.get("alpha")["value"], "A")

    def test_invalid_complete_final_record_is_recoverable(self) -> None:
        self.store.put(key="alpha", value="A", request_id="r-1", expected_version=0)
        log = self.root / "events.log"
        original = log.read_bytes()
        with log.open("ab") as handle:
            handle.write(b"{}\n")
        assert_code(self, "RECOVERY_REQUIRED", self.store.list_items)
        self.assertEqual(self.store.recover()["truncated_bytes"], 3)
        self.assertEqual(log.read_bytes(), original)

    def test_middle_corruption_refuses_recover(self) -> None:
        self.store.put(key="alpha", value="A", request_id="r-1", expected_version=0)
        self.store.put(key="beta", value="B", request_id="r-2", expected_version=0)
        log = self.root / "events.log"
        lines = log.read_bytes().splitlines(keepends=True)
        first = bytearray(lines[0])
        first[first.index(b"A")] = ord("Z")
        damaged = bytes(first) + lines[1]
        log.write_bytes(damaged)
        assert_code(self, "CORRUPT_LOG", self.store.list_items)
        assert_code(self, "CORRUPT_LOG", self.store.recover)
        self.assertEqual(log.read_bytes(), damaged)

    def test_bare_carriage_return_in_middle_is_corrupt_and_read_only(self) -> None:
        self.store.put(key="alpha", value="A", request_id="r-1", expected_version=0)
        self.store.put(key="beta", value="B", request_id="r-2", expected_version=0)
        log = self.root / "events.log"
        lines = log.read_bytes().split(b"\n")
        damaged = lines[0] + b'\n{"broken":"left\rright"}\n' + lines[1] + b"\n"
        log.write_bytes(damaged)
        assert_code(self, "CORRUPT_LOG", self.store.list_items)
        assert_code(self, "CORRUPT_LOG", self.store.recover)
        self.assertEqual(log.read_bytes(), damaged)

    def test_corrupt_snapshot_blocks_log_fallback_and_tmp_is_ignored(self) -> None:
        self.store.put(key="alpha", value="A", request_id="r-1", expected_version=0)
        self.store.compact()
        (self.root / "snapshot.json.tmp").write_text('{"ignored":true}', encoding="utf-8")
        self.assertEqual(JournalStore(self.root).get("alpha")["value"], "A")
        (self.root / "snapshot.json").write_bytes(b"not-json")
        assert_code(self, "CORRUPT_SNAPSHOT", JournalStore(self.root).list_items)

    def test_snapshot_semantic_history_must_be_complete_and_consistent(self) -> None:
        self.store.put(key="alpha", value="A", request_id="r-1", expected_version=0)
        self.store.put(key="alpha", value="A2", request_id="r-2", expected_version=1)
        self.store.compact()
        snapshot_path = self.root / "snapshot.json"
        valid = json.loads(snapshot_path.read_text(encoding="utf-8"))

        variants = []
        missing_history = json.loads(json.dumps(valid))
        missing_history["requests"] = {}
        variants.append(missing_history)
        bad_transition = json.loads(json.dumps(valid))
        bad_transition["requests"]["r-2"]["fingerprint"]["expected_version"] = 0
        variants.append(bad_transition)
        bad_final_state = json.loads(json.dumps(valid))
        bad_final_state["keys"]["alpha"]["value"] = "stale"
        variants.append(bad_final_state)

        for snapshot in variants:
            with self.subTest(snapshot=snapshot):
                snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
                assert_code(self, "CORRUPT_SNAPSHOT", JournalStore(self.root).list_items)

    def test_compact_restart_preserves_state_idempotency_and_sequence(self) -> None:
        first = self.store.put(
            key="alpha", value="A", request_id="r-1", expected_version=0
        )
        self.store.put(key="beta", value="B", request_id="r-2", expected_version=0)
        self.store.delete(key="beta", request_id="r-3", expected_version=2)
        result = self.store.compact()
        self.assertEqual(result, {"snapshot_seq": 3})
        self.assertEqual((self.root / "events.log").read_bytes(), b"")

        restarted = JournalStore(self.root)
        self.assertEqual(restarted.get("alpha")["version"], 1)
        assert_code(self, "NOT_FOUND", restarted.get, "beta")
        replay = restarted.put(
            key="alpha", value="A", request_id="r-1", expected_version=0
        )
        self.assertEqual(replay["seq"], first["seq"])
        self.assertTrue(replay["replayed"])
        next_result = restarted.put(
            key="alpha", value="A2", request_id="r-4", expected_version=1
        )
        self.assertEqual(next_result["seq"], 4)

    def test_snapshot_committed_before_log_replace_is_replay_safe(self) -> None:
        self.store.put(key="alpha", value="A", request_id="r-1", expected_version=0)
        self.store.put(key="beta", value="B", request_id="r-2", expected_version=0)
        old_log = (self.root / "events.log").read_bytes()
        self.store.compact()
        (self.root / "events.log").write_bytes(old_log)
        restarted = JournalStore(self.root)
        self.assertEqual(len(restarted.list_items()), 2)
        result = restarted.put(
            key="alpha", value="A2", request_id="r-3", expected_version=1
        )
        self.assertEqual(result["seq"], 3)

    def test_fsync_and_replace_order_for_durable_operations(self) -> None:
        events = []
        real_fsync = os.fsync
        real_replace = os.replace

        def fd_label(descriptor: int) -> str:
            descriptor_stat = os.fstat(descriptor)
            if stat.S_ISDIR(descriptor_stat.st_mode):
                return "directory"
            for name in ("events.log", "snapshot.json.tmp", "events.log.tmp"):
                candidate = self.root / name
                try:
                    candidate_stat = candidate.stat()
                except OSError:
                    continue
                if (candidate_stat.st_dev, candidate_stat.st_ino) == (
                    descriptor_stat.st_dev,
                    descriptor_stat.st_ino,
                ):
                    return name
            return "file"

        def fsync_spy(descriptor: int) -> None:
            events.append(("fsync", fd_label(descriptor)))
            real_fsync(descriptor)

        def replace_spy(source, destination) -> None:
            events.append(("replace", Path(destination).name))
            real_replace(source, destination)

        with mock.patch.object(store_module.os, "fsync", side_effect=fsync_spy), mock.patch.object(
            store_module.os, "replace", side_effect=replace_spy
        ):
            self.store.put(key="alpha", value="A", request_id="r-1", expected_version=0)
            self.assertEqual(events, [("fsync", "events.log")])
            events.clear()
            self.store.compact()
            self.assertEqual(
                events,
                [
                    ("fsync", "snapshot.json.tmp"),
                    ("replace", "snapshot.json"),
                    ("fsync", "directory"),
                    ("fsync", "events.log.tmp"),
                    ("replace", "events.log"),
                    ("fsync", "directory"),
                ],
            )
            with (self.root / "events.log").open("ab") as handle:
                handle.write(b"partial")
            events.clear()
            self.store.recover()
            self.assertEqual(events, [("fsync", "events.log")])


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "state"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        completed = subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *args],
            text=True,
            capture_output=True,
            check=False,
        )
        lines = completed.stdout.splitlines()
        self.assertEqual(len(lines), 1, completed)
        return completed, json.loads(lines[0])

    def test_cli_contract_and_exit_codes(self) -> None:
        put, body = self.run_cli(
            "put", "--key", "alpha", "--value", "A", "--request-id", "r-1",
            "--expected-version", "0",
        )
        self.assertEqual(put.returncode, 0)
        self.assertEqual(body, {"ok": True, "seq": 1, "key": "alpha", "version": 1, "replayed": False})

        conflict, body = self.run_cli(
            "put", "--key", "alpha", "--value", "B", "--request-id", "r-2",
            "--expected-version", "0",
        )
        self.assertEqual(conflict.returncode, 4)
        self.assertEqual(body["error"]["code"], "VERSION_CONFLICT")

        get, body = self.run_cli("get", "--key", "alpha")
        self.assertEqual(get.returncode, 0)
        self.assertEqual(body, {"ok": True, "key": "alpha", "value": "A", "version": 1})
        listed, body = self.run_cli("list")
        self.assertEqual(listed.returncode, 0)
        self.assertEqual(
            body,
            {"ok": True, "items": [{"key": "alpha", "value": "A", "version": 1}]},
        )
        deleted, body = self.run_cli(
            "delete", "--key", "alpha", "--request-id", "r-delete",
            "--expected-version", "1",
        )
        self.assertEqual(deleted.returncode, 0)
        self.assertEqual(
            body,
            {"ok": True, "seq": 2, "key": "alpha", "version": 2, "replayed": False},
        )
        deleted_get, body = self.run_cli("get", "--key", "alpha")
        self.assertEqual(deleted_get.returncode, 3)
        self.assertEqual(body["error"]["code"], "NOT_FOUND")

        missing, body = self.run_cli("get", "--key", "missing")
        self.assertEqual(missing.returncode, 3)
        self.assertEqual(body["error"]["code"], "NOT_FOUND")

        bad, body = self.run_cli("put", "--key", "alpha")
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(body["ok"], False)

    def test_cli_recovery_compaction_and_store_error_exit_codes(self) -> None:
        put, _ = self.run_cli(
            "put", "--key", "alpha", "--value", "A", "--request-id", "r-1",
            "--expected-version", "0",
        )
        self.assertEqual(put.returncode, 0)
        replay, body = self.run_cli(
            "put", "--key", "alpha", "--value", "A", "--request-id", "r-1",
            "--expected-version", "0",
        )
        self.assertEqual(replay.returncode, 0)
        self.assertTrue(body["replayed"])
        idem, body = self.run_cli(
            "put", "--key", "alpha", "--value", "B", "--request-id", "r-1",
            "--expected-version", "1",
        )
        self.assertEqual(idem.returncode, 5)
        self.assertEqual(body["error"]["code"], "IDEMPOTENCY_CONFLICT")

        tail = b'{"unfinished":'
        with (self.root / "events.log").open("ab") as handle:
            handle.write(tail)
        recovery_required, body = self.run_cli("get", "--key", "alpha")
        self.assertEqual(recovery_required.returncode, 6)
        self.assertEqual(body["error"]["code"], "RECOVERY_REQUIRED")
        recovered, body = self.run_cli("recover")
        self.assertEqual(recovered.returncode, 0)
        self.assertEqual(body["truncated_bytes"], len(tail))
        healthy, body = self.run_cli("recover")
        self.assertEqual(healthy.returncode, 0)
        self.assertEqual(body["truncated_bytes"], 0)

        compacted, body = self.run_cli("compact")
        self.assertEqual(compacted.returncode, 0)
        self.assertEqual(body["snapshot_seq"], 1)
        updated, body = self.run_cli(
            "put", "--key", "alpha", "--value", "A2", "--request-id", "r-2",
            "--expected-version", "1",
        )
        self.assertEqual(updated.returncode, 0)
        self.assertEqual(body["seq"], 2)

        second = Path(self.temp.name) / "middle-corrupt"
        self.root = second
        self.run_cli(
            "put", "--key", "alpha", "--value", "A", "--request-id", "m-1",
            "--expected-version", "0",
        )
        self.run_cli(
            "put", "--key", "beta", "--value", "B", "--request-id", "m-2",
            "--expected-version", "0",
        )
        lines = (second / "events.log").read_bytes().splitlines(keepends=True)
        damaged = bytearray(lines[0])
        damaged[damaged.index(b"A")] = ord("X")
        (second / "events.log").write_bytes(bytes(damaged) + lines[1])
        corrupt, body = self.run_cli("list")
        self.assertEqual(corrupt.returncode, 7)
        self.assertEqual(body["error"]["code"], "CORRUPT_LOG")
        refused, body = self.run_cli("recover")
        self.assertEqual(refused.returncode, 7)
        self.assertEqual(body["error"]["code"], "CORRUPT_LOG")

        third = Path(self.temp.name) / "snapshot-corrupt"
        self.root = third
        self.run_cli(
            "put", "--key", "alpha", "--value", "A", "--request-id", "s-1",
            "--expected-version", "0",
        )
        self.run_cli("compact")
        (third / "snapshot.json").write_bytes(b"bad-snapshot")
        snapshot_error, body = self.run_cli("list")
        self.assertEqual(snapshot_error.returncode, 8)
        self.assertEqual(body["error"]["code"], "CORRUPT_SNAPSHOT")

    def test_multi_process_serialization(self) -> None:
        def put(key: str, request: str, expected: int) -> tuple[int, dict]:
            completed = subprocess.run(
                [
                    sys.executable, str(CLI), "--root", str(self.root), "put",
                    "--key", key, "--value", request, "--request-id", request,
                    "--expected-version", str(expected),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            return completed.returncode, json.loads(completed.stdout)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda n: put(f"key-{n}", f"new-{n}", 0), range(8)))
        exits = [outcome[0] for outcome in outcomes]
        self.assertEqual(exits, [0] * 8)
        items = JournalStore(self.root).list_items()
        self.assertEqual(len(items), 8)
        self.assertEqual(len({item["version"] for item in items}), 8)

        base = JournalStore(self.root).put(
            key="shared", value="base", request_id="shared-base", expected_version=0
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(
                pool.map(
                    lambda n: (n, *put("shared", f"shared-{n}", base["version"])),
                    range(8),
                )
            )
        exits = [outcome[1] for outcome in outcomes]
        self.assertEqual(exits.count(0), 1)
        self.assertEqual(exits.count(4), 7)
        winner = next(outcome for outcome in outcomes if outcome[1] == 0)
        current = JournalStore(self.root).get("shared")
        self.assertEqual(current["value"], f"shared-{winner[0]}")
        self.assertEqual(current["version"], winner[2]["version"])
        self.assertEqual(winner[2]["seq"], winner[2]["version"])
        self.assertEqual(len(JournalStore(self.root).list_items()), 9)
        records = [decode_record(line) for line in (self.root / "events.log").read_bytes().splitlines(keepends=True)]
        self.assertEqual([record["seq"] for record in records], list(range(1, 11)))
        self.assertEqual(len({record["request_id"] for record in records}), 10)


if __name__ == "__main__":
    unittest.main()
