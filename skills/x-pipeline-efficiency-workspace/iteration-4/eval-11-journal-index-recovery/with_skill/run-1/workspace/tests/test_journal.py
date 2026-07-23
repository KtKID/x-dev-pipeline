from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "fixture" / "backend"
sys.path.insert(0, str(BACKEND))

from record import RecordError, decode_record, encode_record
from store import JournalStore, StoreError


CLI = [sys.executable, str(BACKEND / "cli.py")]


class JournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name) / "state"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def store(self) -> JournalStore:
        return JournalStore(self.root)

    def run_cli(self, *args: str) -> tuple[int, dict[str, object], str]:
        completed = subprocess.run(
            [*CLI, "--root", str(self.root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode, json.loads(completed.stdout), completed.stderr

    def assert_error(self, code: str, operation) -> None:
        with self.assertRaises(StoreError) as captured:
            operation()
        self.assertEqual(code, captured.exception.code)

    def test_record_is_canonical_and_crc_checked(self) -> None:
        encoded = encode_record(
            {
                "seq": 1,
                "op": "put",
                "key": "alpha",
                "value": "A",
                "request_id": "r-1",
                "expected_version": 0,
            }
        )
        self.assertTrue(encoded.endswith(b"\n"))
        decoded = decode_record(encoded)
        self.assertEqual("b3b3257b", decoded["crc32"])
        with self.assertRaises(RecordError):
            decode_record(encoded.replace(b'"value":"A"', b'"value":"B"'))

    def test_put_get_list_delete_and_versions(self) -> None:
        store = self.store()
        self.assertEqual(
            {"seq": 1, "key": "zeta", "version": 1, "replayed": False},
            store.put(key="zeta", value="Z", request_id="r-z", expected_version=0),
        )
        store.put(key="alpha", value="A", request_id="r-a", expected_version=0)
        self.assertEqual(["alpha", "zeta"], [row["key"] for row in store.list_items()["items"]])
        deleted = store.delete(key="alpha", request_id="r-d", expected_version=2)
        self.assertEqual(3, deleted["version"])
        self.assert_error("NOT_FOUND", lambda: store.get("alpha"))
        self.assert_error("NOT_FOUND", lambda: self.store().delete(key="missing", request_id="r-m", expected_version=0))
        self.assert_error("VERSION_CONFLICT", lambda: self.store().put(key="zeta", value="again", request_id="r-c", expected_version=0))

    def test_request_id_replay_and_conflict_survive_restart(self) -> None:
        store = self.store()
        first = store.put(key="alpha", value="A", request_id="r-1", expected_version=0)
        replay = self.store().put(key="alpha", value="A", request_id="r-1", expected_version=0)
        self.assertEqual({**first, "replayed": True}, replay)
        self.assert_error(
            "IDEMPOTENCY_CONFLICT",
            lambda: self.store().put(key="alpha", value="B", request_id="r-1", expected_version=1),
        )
        self.assertEqual(1, self.store().get("alpha")["version"])

    def test_tail_recovery_and_non_tail_corruption(self) -> None:
        store = self.store()
        store.put(key="alpha", value="A", request_id="r-1", expected_version=0)
        events = self.root / "events.log"
        good_size = events.stat().st_size
        with open(events, "ab") as handle:
            handle.write(b'{"partial"')
        self.assert_error("RECOVERY_REQUIRED", lambda: self.store().get("alpha"))
        self.assertEqual({"truncated_bytes": len(b'{"partial"')}, self.store().recover())
        self.assertEqual(good_size, events.stat().st_size)
        self.assertEqual({"truncated_bytes": 0}, self.store().recover())
        with open(events, "ab") as handle:
            handle.write(b"bad\n")
            handle.write(b"also-bad\n")
        self.assert_error("CORRUPT_LOG", lambda: self.store().recover())

    def test_compact_preserves_full_state_and_ignores_snapshot_tmp(self) -> None:
        store = self.store()
        store.put(key="alpha", value="A", request_id="r-1", expected_version=0)
        store.delete(key="alpha", request_id="r-2", expected_version=1)
        store.put(key="beta", value="B", request_id="r-3", expected_version=0)
        self.assertEqual({"snapshot_seq": 3}, store.compact())
        self.assertEqual(b"", (self.root / "events.log").read_bytes())
        (self.root / "snapshot.json.tmp").write_text("{broken", encoding="utf-8")
        restarted = self.store()
        self.assertEqual({"key": "beta", "value": "B", "version": 3}, restarted.get("beta"))
        self.assert_error("NOT_FOUND", lambda: restarted.get("alpha"))
        self.assertEqual(
            {"seq": 1, "key": "alpha", "version": 1, "replayed": True},
            restarted.put(key="alpha", value="A", request_id="r-1", expected_version=0),
        )

    def test_corrupt_committed_snapshot_is_read_only_failure(self) -> None:
        store = self.store()
        store.put(key="alpha", value="A", request_id="r-1", expected_version=0)
        store.compact()
        snapshot = self.root / "snapshot.json"
        snapshot.write_text("{", encoding="utf-8")
        before = snapshot.read_bytes()
        self.assert_error("CORRUPT_SNAPSHOT", lambda: self.store().recover())
        self.assertEqual(before, snapshot.read_bytes())

    def test_snapshot_requires_every_committed_request_for_idempotency(self) -> None:
        store = self.store()
        store.put(key="alpha", value="A", request_id="r-1", expected_version=0)
        store.compact()
        snapshot = self.root / "snapshot.json"
        value = json.loads(snapshot.read_text(encoding="utf-8"))
        del value["requests"]["r-1"]
        snapshot.write_text(json.dumps(value), encoding="utf-8")
        before = snapshot.read_bytes()
        self.assert_error(
            "CORRUPT_SNAPSHOT",
            lambda: self.store().put(key="alpha", value="A", request_id="r-1", expected_version=0),
        )
        self.assertEqual(before, snapshot.read_bytes())

    def test_cli_schema_exit_codes_and_restart(self) -> None:
        code, result, stderr = self.run_cli("put", "--key", "alpha", "--value", "A", "--request-id", "r-1", "--expected-version", "0")
        self.assertEqual((0, {"ok": True, "seq": 1, "key": "alpha", "version": 1, "replayed": False}, ""), (code, result, stderr))
        code, result, _ = self.run_cli("put", "--key", "alpha", "--value", "B", "--request-id", "r-2", "--expected-version", "0")
        self.assertEqual(4, code)
        self.assertEqual("VERSION_CONFLICT", result["error"]["code"])
        code, result, _ = self.run_cli("get", "--key", "alpha")
        self.assertEqual((0, "A", 1), (code, result["value"], result["version"]))

    def test_concurrent_distinct_keys_and_same_version_conflict(self) -> None:
        def put_key(index: int):
            return subprocess.run(
                [*CLI, "--root", str(self.root), "put", "--key", f"k{index}", "--value", str(index), "--request-id", f"r{index}", "--expected-version", "0"],
                capture_output=True,
                text=True,
                check=False,
            )

        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(put_key, range(6)))
        parsed = [json.loads(result.stdout) for result in results]
        self.assertEqual([0] * 6, [result.returncode for result in results])
        self.assertEqual(list(range(1, 7)), sorted(item["seq"] for item in parsed))

        code, result, _ = self.run_cli("put", "--key", "race", "--value", "seed", "--request-id", "seed", "--expected-version", "0")
        self.assertEqual(0, code)

        def update(index: int):
            return subprocess.run(
                [*CLI, "--root", str(self.root), "put", "--key", "race", "--value", str(index), "--request-id", f"race-{index}", "--expected-version", str(result["version"])],
                capture_output=True,
                text=True,
                check=False,
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            competitors = list(pool.map(update, range(4)))
        self.assertEqual(1, sum(entry.returncode == 0 for entry in competitors))
        self.assertEqual(3, sum(entry.returncode == 4 for entry in competitors))


if __name__ == "__main__":
    unittest.main()
