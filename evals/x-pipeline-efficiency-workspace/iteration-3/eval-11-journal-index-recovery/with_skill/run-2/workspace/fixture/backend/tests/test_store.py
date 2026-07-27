from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fixture.backend.store import JournalStore, StoreError


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "state"
        self.store = JournalStore(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def assert_code(self, code: str, callback) -> None:
        with self.assertRaises(StoreError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_state_machine_versions_delete_recreate_and_sorted_list(self) -> None:
        beta = self.store.put(key="beta", value="B", request_id="r1", expected_version=0)
        alpha = self.store.put(key="alpha", value="A", request_id="r2", expected_version=0)
        updated = self.store.put(key="alpha", value="A2", request_id="r3", expected_version=alpha["version"])
        self.assertEqual([beta["seq"], alpha["seq"], updated["seq"]], [1, 2, 3])
        self.assertEqual(self.store.get("alpha"), {"key": "alpha", "value": "A2", "version": 3})
        self.assertEqual([item["key"] for item in self.store.list_items()], ["alpha", "beta"])

        deleted = self.store.delete(key="alpha", request_id="r4", expected_version=3)
        self.assertEqual(deleted["seq"], 4)
        self.assert_code("NOT_FOUND", lambda: self.store.get("alpha"))
        self.assert_code("NOT_FOUND", lambda: self.store.delete(key="alpha", request_id="r5", expected_version=4))
        recreated = self.store.put(key="alpha", value="A3", request_id="r6", expected_version=4)
        self.assertEqual(recreated["seq"], 5)

    def test_version_and_idempotency_failures_do_not_append(self) -> None:
        first = self.store.put(key="alpha", value="A", request_id="r1", expected_version=0)
        log = self.root.joinpath("events.log")
        before = log.read_bytes()

        self.assert_code(
            "VERSION_CONFLICT",
            lambda: self.store.put(key="alpha", value="bad", request_id="r2", expected_version=0),
        )
        self.assertEqual(log.read_bytes(), before)

        replay = self.store.put(key="alpha", value="A", request_id="r1", expected_version=0)
        self.assertEqual(replay, first | {"replayed": True})
        self.assertEqual(log.read_bytes(), before)

        self.assert_code(
            "IDEMPOTENCY_CONFLICT",
            lambda: self.store.put(key="alpha", value="other", request_id="r1", expected_version=0),
        )
        self.assertEqual(log.read_bytes(), before)

    def test_idempotency_survives_later_mutation_restart_and_compact(self) -> None:
        first = self.store.put(key="alpha", value="A", request_id="r1", expected_version=0)
        self.store.put(key="alpha", value="B", request_id="r2", expected_version=1)
        self.assertEqual(JournalStore(self.root).put(key="alpha", value="A", request_id="r1", expected_version=0), first | {"replayed": True})
        self.assertEqual(self.store.compact(), {"snapshot_seq": 2})
        self.assertEqual(self.root.joinpath("events.log").read_bytes(), b"")
        self.assertEqual(JournalStore(self.root).put(key="alpha", value="A", request_id="r1", expected_version=0), first | {"replayed": True})

    def test_tail_damage_requires_recover_and_truncates_exact_bytes(self) -> None:
        self.store.put(key="alpha", value="A", request_id="r1", expected_version=0)
        log = self.root / "events.log"
        healthy = log.read_bytes()
        tail = b'{"broken":'
        with log.open("ab") as handle:
            handle.write(tail)

        self.assert_code("RECOVERY_REQUIRED", lambda: self.store.get("alpha"))
        self.assertEqual(self.store.recover(), {"truncated_bytes": len(tail)})
        self.assertEqual(log.read_bytes(), healthy)
        self.assertEqual(self.store.recover(), {"truncated_bytes": 0})
        self.assertEqual(self.store.get("alpha")["value"], "A")

    def test_missing_newline_and_bad_crc_on_last_record_are_recoverable(self) -> None:
        self.store.put(key="alpha", value="A", request_id="r1", expected_version=0)
        log = self.root / "events.log"
        complete = log.read_bytes()
        log.write_bytes(complete[:-1])
        self.assert_code("RECOVERY_REQUIRED", lambda: self.store.list_items())
        self.assertEqual(self.store.recover(), {"truncated_bytes": len(complete) - 1})
        self.assertEqual(log.read_bytes(), b"")

        committed = self.store.put(key="beta", value="B", request_id="r2", expected_version=0)
        self.assertEqual(committed["seq"], 1)
        damaged = log.read_bytes().replace(b'"value":"B"', b'"value":"X"')
        log.write_bytes(damaged)
        self.assert_code("RECOVERY_REQUIRED", lambda: self.store.list_items())
        self.assertEqual(self.store.recover(), {"truncated_bytes": len(damaged)})
        self.assertEqual(log.read_bytes(), b"")

    def test_middle_damage_is_immutable_and_recover_refuses(self) -> None:
        self.store.put(key="alpha", value="A", request_id="r1", expected_version=0)
        self.store.put(key="beta", value="B", request_id="r2", expected_version=0)
        log = self.root / "events.log"
        damaged = log.read_bytes().replace(b'"value":"A"', b'"value":"X"', 1)
        log.write_bytes(damaged)

        self.assert_code("CORRUPT_LOG", lambda: self.store.list_items())
        self.assert_code("CORRUPT_LOG", lambda: self.store.recover())
        self.assertEqual(log.read_bytes(), damaged)

    def test_complete_semantically_invalid_last_record_is_corrupt_log(self) -> None:
        from fixture.backend.record import encode_record

        self.root.mkdir(parents=True)
        log = self.root / "events.log"
        invalid = encode_record(
            {
                "expected_version": 0,
                "key": "alpha",
                "op": "put",
                "request_id": "r1",
                "seq": 2,
                "value": "A",
            }
        )
        log.write_bytes(invalid)

        self.assert_code("CORRUPT_LOG", lambda: self.store.list_items())
        self.assert_code("CORRUPT_LOG", lambda: self.store.recover())
        self.assertEqual(log.read_bytes(), invalid)

    def test_corrupt_snapshot_blocks_all_commands_and_tmp_is_ignored(self) -> None:
        self.store.put(key="alpha", value="A", request_id="r1", expected_version=0)
        self.store.compact()
        snapshot = self.root / "snapshot.json"
        snapshot.write_text("{}\n", encoding="utf-8")
        self.root.joinpath("snapshot.json.tmp").write_text('{"junk":true}', encoding="utf-8")

        self.assert_code("CORRUPT_SNAPSHOT", lambda: self.store.list_items())
        self.assert_code("CORRUPT_SNAPSHOT", lambda: self.store.recover())

    def test_orphan_snapshot_tmp_is_ignored(self) -> None:
        self.root.mkdir(parents=True)
        self.root.joinpath("snapshot.json.tmp").write_text("not-json", encoding="utf-8")
        self.assertEqual(self.store.list_items(), [])

    def test_compact_crash_window_old_log_is_validated_but_not_replayed(self) -> None:
        self.store.put(key="alpha", value="A", request_id="r1", expected_version=0)
        self.store.delete(key="alpha", request_id="r2", expected_version=1)
        self.store.put(key="beta", value="B", request_id="r3", expected_version=0)
        old_log = self.root.joinpath("events.log").read_bytes()
        self.store.compact()

        self.root.joinpath("events.log").write_bytes(old_log)
        restarted = JournalStore(self.root)
        self.assertEqual(restarted.list_items(), [{"key": "beta", "value": "B", "version": 3}])
        result = restarted.put(key="gamma", value="G", request_id="r4", expected_version=0)
        self.assertEqual(result["seq"], 4)

        lines = self.root.joinpath("events.log").read_bytes().splitlines()
        self.assertEqual(len(lines), 4)
        self.assertEqual(json.loads(lines[-1])["seq"], 4)

    def test_recovering_damaged_stale_tail_leaves_readable_snapshot_state(self) -> None:
        self.store.put(key="alpha", value="A", request_id="r1", expected_version=0)
        self.store.put(key="beta", value="B", request_id="r2", expected_version=0)
        old_log = self.root.joinpath("events.log").read_bytes()
        first_line, second_line = old_log.splitlines(keepends=True)
        self.store.compact()
        damaged_second = second_line.replace(b'"value":"B"', b'"value":"X"')
        self.root.joinpath("events.log").write_bytes(first_line + damaged_second)

        self.assert_code("RECOVERY_REQUIRED", lambda: self.store.list_items())
        self.assertEqual(self.store.recover(), {"truncated_bytes": len(damaged_second)})
        self.assertEqual(
            self.store.list_items(),
            [
                {"key": "alpha", "value": "A", "version": 1},
                {"key": "beta", "value": "B", "version": 2},
            ],
        )
        committed = self.store.put(key="gamma", value="G", request_id="r3", expected_version=0)
        self.assertEqual(committed["seq"], 3)
        self.assertEqual(JournalStore(self.root).get("gamma")["value"], "G")


if __name__ == "__main__":
    unittest.main()
