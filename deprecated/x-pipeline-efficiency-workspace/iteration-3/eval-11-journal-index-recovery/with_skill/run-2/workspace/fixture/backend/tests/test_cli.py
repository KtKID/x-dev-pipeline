from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "cli.py"


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "state"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *arguments: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        completed = subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )
        lines = completed.stdout.splitlines()
        self.assertEqual(len(lines), 1, completed)
        payload = json.loads(lines[0])
        self.assertIsInstance(payload, dict)
        return completed, payload

    def test_real_cli_restart_compact_and_error_exit_codes(self) -> None:
        put, first = self.run_cli("put", "--key", "alpha", "--value", "A", "--request-id", "r1", "--expected-version", "0")
        self.assertEqual(
            (put.returncode, first),
            (0, {"ok": True, "seq": 1, "key": "alpha", "version": 1, "replayed": False}),
        )

        get, found = self.run_cli("get", "--key", "alpha")
        self.assertEqual((get.returncode, found), (0, {"ok": True, "key": "alpha", "value": "A", "version": 1}))
        listed, items = self.run_cli("list")
        self.assertEqual(
            (listed.returncode, items),
            (0, {"ok": True, "items": [{"key": "alpha", "value": "A", "version": 1}]}),
        )

        conflict, error = self.run_cli("put", "--key", "alpha", "--value", "B", "--request-id", "r2", "--expected-version", "0")
        self.assertEqual((conflict.returncode, error["error"]["code"]), (4, "VERSION_CONFLICT"))

        replay, replayed = self.run_cli("put", "--key", "alpha", "--value", "A", "--request-id", "r1", "--expected-version", "0")
        self.assertEqual(
            (replay.returncode, replayed),
            (0, {"ok": True, "seq": 1, "key": "alpha", "version": 1, "replayed": True}),
        )

        idem, idem_error = self.run_cli("delete", "--key", "alpha", "--request-id", "r1", "--expected-version", "1")
        self.assertEqual((idem.returncode, idem_error["error"]["code"]), (5, "IDEMPOTENCY_CONFLICT"))

        compact, compacted = self.run_cli("compact")
        self.assertEqual((compact.returncode, compacted), (0, {"ok": True, "snapshot_seq": 1}))
        restarted, value = self.run_cli("get", "--key", "alpha")
        self.assertEqual((restarted.returncode, value), (0, {"ok": True, "key": "alpha", "value": "A", "version": 1}))

        deleted, delete_result = self.run_cli("delete", "--key", "alpha", "--request-id", "r3", "--expected-version", "1")
        self.assertEqual(
            (deleted.returncode, delete_result),
            (0, {"ok": True, "seq": 2, "key": "alpha", "version": 2, "replayed": False}),
        )
        delete_replay, delete_replayed = self.run_cli("delete", "--key", "alpha", "--request-id", "r3", "--expected-version", "1")
        self.assertEqual(
            (delete_replay.returncode, delete_replayed),
            (0, {"ok": True, "seq": 2, "key": "alpha", "version": 2, "replayed": True}),
        )
        empty_list, empty_items = self.run_cli("list")
        self.assertEqual((empty_list.returncode, empty_items), (0, {"ok": True, "items": []}))

        missing, missing_error = self.run_cli("get", "--key", "missing")
        self.assertEqual((missing.returncode, missing_error["error"]["code"]), (3, "NOT_FOUND"))

    def test_argument_errors_are_single_json_object(self) -> None:
        completed, payload = self.run_cli("put", "--key", "alpha")
        self.assertEqual((completed.returncode, payload["error"]["code"]), (2, "INVALID_ARGUMENT"))

    def test_cli_tail_recovery(self) -> None:
        self.run_cli("put", "--key", "alpha", "--value", "A", "--request-id", "r1", "--expected-version", "0")
        tail = b"{bad"
        with self.root.joinpath("events.log").open("ab") as handle:
            handle.write(tail)

        blocked, error = self.run_cli("list")
        self.assertEqual((blocked.returncode, error["error"]["code"]), (6, "RECOVERY_REQUIRED"))
        recovered, result = self.run_cli("recover")
        self.assertEqual((recovered.returncode, result["truncated_bytes"]), (0, len(tail)))

    def test_corrupt_log_and_snapshot_exit_codes(self) -> None:
        self.run_cli("put", "--key", "alpha", "--value", "A", "--request-id", "r1", "--expected-version", "0")
        self.run_cli("put", "--key", "beta", "--value", "B", "--request-id", "r2", "--expected-version", "0")
        log = self.root / "events.log"
        log.write_bytes(log.read_bytes().replace(b'"value":"A"', b'"value":"X"', 1))
        corrupt_log, log_error = self.run_cli("recover")
        self.assertEqual((corrupt_log.returncode, log_error["error"]["code"]), (7, "CORRUPT_LOG"))

        snapshot_root = Path(self.temp.name) / "snapshot-state"
        self.root = snapshot_root
        self.run_cli("put", "--key", "alpha", "--value", "A", "--request-id", "r1", "--expected-version", "0")
        self.run_cli("compact")
        snapshot_root.joinpath("snapshot.json").write_text("{}\n", encoding="utf-8")
        corrupt_snapshot, snapshot_error = self.run_cli("list")
        self.assertEqual((corrupt_snapshot.returncode, snapshot_error["error"]["code"]), (8, "CORRUPT_SNAPSHOT"))

    def test_multiprocess_different_keys_and_same_version_contention(self) -> None:
        different = [
            subprocess.Popen(
                [sys.executable, str(CLI), "--root", str(self.root), "put", "--key", f"key-{index}", "--value", str(index), "--request-id", f"r-{index}", "--expected-version", "0"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for index in range(8)
        ]
        different_results = []
        for index, process in enumerate(different):
            stdout, _ = process.communicate()
            different_results.append((index, process.returncode, json.loads(stdout)))
        self.assertTrue(all(code == 0 for _, code, _ in different_results))
        self.assertEqual(sorted(payload["seq"] for _, _, payload in different_results), list(range(1, 9)))
        _, listed = self.run_cli("list")
        expected_items = sorted(
            [
                {
                    "key": f"key-{index}",
                    "value": str(index),
                    "version": payload["version"],
                }
                for index, _, payload in different_results
            ],
            key=lambda item: item["key"],
        )
        self.assertEqual(listed, {"ok": True, "items": expected_items})

        self.run_cli("put", "--key", "shared", "--value", "initial", "--request-id", "shared-0", "--expected-version", "0")
        records_before = len(self.root.joinpath("events.log").read_bytes().splitlines())
        contenders = [
            subprocess.Popen(
                [sys.executable, str(CLI), "--root", str(self.root), "put", "--key", "shared", "--value", str(index), "--request-id", f"shared-{index + 1}", "--expected-version", "9"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for index in range(6)
        ]
        contender_results = []
        for index, process in enumerate(contenders):
            stdout, _ = process.communicate()
            contender_results.append((index, process.returncode, json.loads(stdout)))
        self.assertEqual([code for _, code, _ in contender_results].count(0), 1)
        self.assertEqual([code for _, code, _ in contender_results].count(4), 5)
        winner_index, _, winner = next(item for item in contender_results if item[1] == 0)
        self.assertEqual(winner, {"ok": True, "seq": 10, "key": "shared", "version": 10, "replayed": False})
        self.assertTrue(
            all(payload["error"]["code"] == "VERSION_CONFLICT" for _, code, payload in contender_results if code == 4)
        )
        _, final_shared = self.run_cli("get", "--key", "shared")
        self.assertEqual(
            final_shared,
            {"ok": True, "key": "shared", "value": str(winner_index), "version": 10},
        )
        records_after = len(self.root.joinpath("events.log").read_bytes().splitlines())
        self.assertEqual(records_after, records_before + 1)


if __name__ == "__main__":
    unittest.main()
