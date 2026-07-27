from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import zlib


BACKEND = Path(__file__).resolve().parents[1]
CLI = BACKEND / "cli.py"
sys.path.insert(0, str(BACKEND))

from record import RecordError, decode_record, encode_record  # noqa: E402
import store as store_module  # noqa: E402
from store import JournalStore, StoreError  # noqa: E402


def raw_with_crc(payload: dict[str, object], *, crc32: str | None = None) -> bytes:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    checksum = crc32 or f"{zlib.crc32(canonical) & 0xffffffff:08x}"
    return (
        json.dumps(
            {**payload, "crc32": checksum},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def directory_bytes(root: Path) -> dict[str, tuple[str, object]]:
    if not root.exists():
        return {}
    snapshot: dict[str, tuple[str, object]] = {}
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        if path.is_symlink():
            snapshot[relative] = ("symlink", os.readlink(path))
        elif path.is_dir():
            snapshot[relative] = ("dir", None)
        else:
            snapshot[relative] = ("file", path.read_bytes())
    return snapshot


class JournalTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "state"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def cli(self, *args: str, root: Path | None = None) -> tuple[int, dict[str, object], str]:
        state_root = root or self.root
        return self.raw_cli("--root", str(state_root), *args)

    def raw_cli(self, *args: str) -> tuple[int, dict[str, object], str]:
        process = subprocess.run(
            [sys.executable, str(CLI), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
        lines = process.stdout.splitlines()
        self.assertEqual(len(lines), 1, (process.args, process.stdout, process.stderr))
        return process.returncode, json.loads(lines[0]), process.stderr


class RecordTests(JournalTestCase):
    def test_canonical_crc_round_trip_and_strict_validation(self) -> None:
        record = {
            "expected_version": 0,
            "key": "alpha",
            "op": "put",
            "request_id": "r-1",
            "seq": 1,
            "value": "A",
        }
        raw = encode_record(record)
        self.assertTrue(raw.endswith(b"\n"))
        decoded_json = json.loads(raw)
        payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.assertEqual(decoded_json["crc32"], f"{zlib.crc32(payload) & 0xffffffff:08x}")
        self.assertEqual(decode_record(raw), {**record, "crc32": decoded_json["crc32"]})

        invalid_records = [
            raw[:-1],
            b"\xff\n",
            b"{bad}\n",
            raw.replace(b'"crc32":"', b'"crc32":"0', 1),
            encode_record({**record, "op": "delete", "value": None}).replace(
                b'"value":null', b'"value":"bad"', 1
            ),
        ]
        for invalid in invalid_records:
            with self.subTest(invalid=invalid):
                with self.assertRaises(RecordError):
                    decode_record(invalid)

    def test_every_record_field_is_strictly_validated(self) -> None:
        valid = {
            "expected_version": 0,
            "key": "alpha",
            "op": "put",
            "request_id": "r-1",
            "seq": 1,
            "value": "A",
        }
        invalid_payloads = {
            "extra": {**valid, "extra": 1},
            "seq-string": {**valid, "seq": "1"},
            "seq-bool": {**valid, "seq": True},
            "seq-zero": {**valid, "seq": 0},
            "expected-string": {**valid, "expected_version": "0"},
            "expected-bool": {**valid, "expected_version": False},
            "expected-negative": {**valid, "expected_version": -1},
            "key-object": {**valid, "key": {}},
            "request-array": {**valid, "request_id": []},
            "op-array": {**valid, "op": []},
            "op-unknown": {**valid, "op": "patch"},
            "put-null": {**valid, "value": None},
            "delete-string": {**valid, "op": "delete", "value": "A"},
        }
        for name, payload in invalid_payloads.items():
            with self.subTest(name=name, boundary="encode"):
                with self.assertRaises(RecordError):
                    encode_record(payload)
            with self.subTest(name=name, boundary="decode"):
                with self.assertRaises(RecordError):
                    decode_record(raw_with_crc(payload))

        wrong_json_types = {
            "expected_version": [None, False, "0", [], {}],
            "key": [None, False, 0, [], {}],
            "op": [None, False, 0, [], {}],
            "request_id": [None, False, 0, [], {}],
            "seq": [None, False, "1", [], {}],
            "value": [None, False, 0, [], {}],
        }
        for field, invalid_values in wrong_json_types.items():
            for invalid_value in invalid_values:
                payload = {**valid, field: invalid_value}
                with self.subTest(
                    field=field,
                    invalid_type=type(invalid_value).__name__,
                    boundary="type-matrix",
                ):
                    with self.assertRaises(RecordError):
                        encode_record(payload)
                    with self.assertRaises(RecordError):
                        decode_record(raw_with_crc(payload))

        for field in valid:
            missing = {key: value for key, value in valid.items() if key != field}
            with self.subTest(field=field, boundary="encode-missing"):
                with self.assertRaises(RecordError):
                    encode_record(missing)
            with self.subTest(field=field, boundary="decode-missing"):
                with self.assertRaises(RecordError):
                    decode_record(raw_with_crc(missing))

        full = json.loads(raw_with_crc(valid))
        valid_raw = json.dumps(full, sort_keys=True, separators=(",", ":")).encode("utf-8")
        for field, value in full.items():
            duplicate_prefix = (
                json.dumps(field, separators=(",", ":"))
                + ":"
                + json.dumps(value, separators=(",", ":"))
                + ","
            ).encode("utf-8")
            with self.subTest(field=field, boundary="decode-duplicate"):
                with self.assertRaises(RecordError):
                    decode_record(b"{" + duplicate_prefix + valid_raw[1:] + b"\n")

        without_crc = (
            json.dumps(valid, sort_keys=True, separators=(",", ":")).encode("utf-8")
            + b"\n"
        )
        with self.assertRaises(RecordError):
            decode_record(without_crc)
        for invalid_crc in [
            None,
            1,
            True,
            [],
            {},
            "ABCDEF12",
            "abcdef1",
            "abcdef123",
            "gggggggg",
            "11111111",
        ]:
            with self.subTest(crc32=invalid_crc):
                encoded = (
                    json.dumps(
                        {**valid, "crc32": invalid_crc},
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    + b"\n"
                )
                with self.assertRaises(RecordError):
                    decode_record(encoded)

        payload_crc = f"{zlib.crc32(json.dumps(valid, sort_keys=True, separators=(',', ':')).encode('utf-8')) & 0xffffffff:08x}"
        shuffled_full = {
            "value": "A",
            "seq": 1,
            "request_id": "r-1",
            "op": "put",
            "key": "alpha",
            "expected_version": 0,
            "crc32": payload_crc,
        }
        shuffled_raw = (
            json.dumps(shuffled_full, separators=(",", ":")).encode("utf-8") + b"\n"
        )
        self.assertEqual(decode_record(shuffled_raw), shuffled_full)
        with self.assertRaises(RecordError):
            decode_record(b"[" * 1200 + b"0" + b"]" * 1200 + b"\n")


class StateMachineTests(JournalTestCase):
    def test_put_get_list_delete_versions_and_restart(self) -> None:
        store = JournalStore(self.root)
        first = store.put(
            key="beta", value="B", request_id="r-1", expected_version=0
        )
        second = store.put(
            key="alpha", value="A", request_id="r-2", expected_version=0
        )
        self.assertEqual((first["seq"], second["seq"]), (1, 2))
        self.assertEqual(
            JournalStore(self.root).list_items(),
            [
                {"key": "alpha", "value": "A", "version": 2},
                {"key": "beta", "value": "B", "version": 1},
            ],
        )

        deleted = JournalStore(self.root).delete(
            key="alpha", request_id="r-3", expected_version=2
        )
        self.assertEqual(deleted["version"], 3)
        with self.assertRaisesRegex(StoreError, "alpha") as missing:
            JournalStore(self.root).get("alpha")
        self.assertEqual(missing.exception.code, "NOT_FOUND")
        with self.assertRaises(StoreError) as repeated_delete:
            JournalStore(self.root).delete(
                key="alpha", request_id="r-4", expected_version=3
            )
        self.assertEqual(repeated_delete.exception.code, "NOT_FOUND")
        resurrected = JournalStore(self.root).put(
            key="alpha", value="A2", request_id="r-5", expected_version=3
        )
        self.assertEqual(resurrected["seq"], 4)

    def test_version_and_idempotency_conflicts_have_no_side_effects(self) -> None:
        store = JournalStore(self.root)
        first = store.put(key="k", value="v1", request_id="same", expected_version=0)
        size = (self.root / "events.log").stat().st_size
        replay = JournalStore(self.root).put(
            key="k", value="v1", request_id="same", expected_version=0
        )
        self.assertEqual(replay, {**first, "replayed": True})
        self.assertEqual((self.root / "events.log").stat().st_size, size)

        with self.assertRaises(StoreError) as idempotency:
            JournalStore(self.root).put(
                key="other", value="v1", request_id="same", expected_version=0
            )
        self.assertEqual(idempotency.exception.code, "IDEMPOTENCY_CONFLICT")
        with self.assertRaises(StoreError) as version:
            JournalStore(self.root).put(
                key="k", value="v2", request_id="new", expected_version=0
            )
        self.assertEqual(version.exception.code, "VERSION_CONFLICT")
        self.assertEqual((self.root / "events.log").stat().st_size, size)
        self.assertEqual(JournalStore(self.root).get("k")["value"], "v1")

        for request_id, expected_version in [("delete-stale", 0), ("delete-future", 2)]:
            with self.subTest(expected_version=expected_version):
                conflict_root = Path(self.temp_dir.name) / request_id
                JournalStore(conflict_root).put(
                    key="k", value="v1", request_id="initial", expected_version=0
                )
                before_delete_conflict = directory_bytes(conflict_root)
                with self.assertRaises(StoreError) as delete_version:
                    JournalStore(conflict_root).delete(
                        key="k",
                        request_id=request_id,
                        expected_version=expected_version,
                    )
                self.assertEqual(delete_version.exception.code, "VERSION_CONFLICT")
                self.assertEqual(directory_bytes(conflict_root), before_delete_conflict)
                self.assertEqual(
                    JournalStore(conflict_root).get("k"),
                    {"key": "k", "value": "v1", "version": 1},
                )
                committed_delete = JournalStore(conflict_root).delete(
                    key="k", request_id=request_id, expected_version=1
                )
                self.assertEqual(committed_delete["seq"], 2)


class RecoveryAndCompactionTests(JournalTestCase):
    @staticmethod
    def _record(
        *,
        seq: int,
        key: str,
        request_id: str,
        expected_version: int = 0,
        value: str = "value",
    ) -> dict[str, object]:
        return {
            "expected_version": expected_version,
            "key": key,
            "op": "put",
            "request_id": request_id,
            "seq": seq,
            "value": value,
        }

    def test_tail_damage_requires_recovery_and_truncates_exact_bytes(self) -> None:
        self.cli(
            "put",
            "--key",
            "k",
            "--value",
            "v",
            "--request-id",
            "r1",
            "--expected-version",
            "0",
        )
        log = self.root / "events.log"
        good_size = log.stat().st_size
        tail = b'{"broken":'
        with log.open("ab") as stream:
            stream.write(tail)
            stream.flush()
            os.fsync(stream.fileno())

        code, output, _ = self.cli("get", "--key", "k")
        self.assertEqual((code, output["error"]["code"]), (6, "RECOVERY_REQUIRED"))
        self.assertEqual(log.stat().st_size, good_size + len(tail))
        code, output, _ = self.cli("recover")
        self.assertEqual(code, 0)
        self.assertEqual(output["truncated_bytes"], len(tail))
        self.assertEqual(log.stat().st_size, good_size)
        self.assertEqual(self.cli("get", "--key", "k")[1]["value"], "v")
        self.assertEqual(self.cli("recover")[1]["truncated_bytes"], 0)

    def test_middle_damage_is_immutable_corrupt_log(self) -> None:
        first = {
            "expected_version": 0,
            "key": "a",
            "op": "put",
            "request_id": "r1",
            "seq": 1,
            "value": "A",
        }
        second = {
            "expected_version": 0,
            "key": "b",
            "op": "put",
            "request_id": "r2",
            "seq": 2,
            "value": "B",
        }
        self.root.mkdir()
        original = encode_record(first) + b"{bad}\n" + encode_record(second)
        (self.root / "events.log").write_bytes(original)
        before = (self.root / "events.log").read_bytes()
        for command in [("list",), ("recover",)]:
            code, output, _ = self.cli(*command)
            self.assertEqual((code, output["error"]["code"]), (7, "CORRUPT_LOG"))
            self.assertEqual((self.root / "events.log").read_bytes(), before)

    def test_log_damage_matrix_classifies_tail_and_middle_without_side_effects(self) -> None:
        first = encode_record(self._record(seq=1, key="a", request_id="r1", value="A"))
        second = encode_record(self._record(seq=2, key="b", request_id="r2", value="B"))
        invalid_field = raw_with_crc(
            {**self._record(seq=2, key="b", request_id="bad-field"), "op": []}
        )
        wrong_crc = raw_with_crc(
            self._record(seq=2, key="b", request_id="bad-crc"),
            crc32="00000000",
        )
        seq_gap = encode_record(self._record(seq=3, key="b", request_id="gap"))
        deep_json = b"[" * 1200 + b"0" + b"]" * 1200 + b"\n"
        tail_variants = {
            "missing-lf": second[:-1],
            "utf8": b"\xff\n",
            "json": b"{bad}\n",
            "field": invalid_field,
            "crc": wrong_crc,
            "seq": seq_gap,
            "deep": deep_json,
        }
        ordinary_commands = [
            ("get", "--key", "a"),
            ("list",),
            (
                "put",
                "--key",
                "a",
                "--value",
                "A2",
                "--request-id",
                "blocked-put",
                "--expected-version",
                "1",
            ),
            (
                "delete",
                "--key",
                "a",
                "--request-id",
                "blocked-delete",
                "--expected-version",
                "1",
            ),
            ("compact",),
        ]
        for name, damaged in tail_variants.items():
            with self.subTest(position="tail", damage=name):
                root = Path(self.temp_dir.name) / f"tail-{name}"
                root.mkdir()
                (root / "writer.lock").write_bytes(b"")
                (root / "snapshot.json.tmp").write_bytes(b"snapshot sentinel")
                (root / "events.log.tmp").write_bytes(b"log sentinel")
                (root / "events.log").write_bytes(first + damaged)
                before = directory_bytes(root)
                for command in ordinary_commands:
                    code, output, _ = self.cli(*command, root=root)
                    self.assertEqual(
                        (code, output["error"]["code"]),
                        (6, "RECOVERY_REQUIRED"),
                        (name, command, output),
                    )
                    self.assertEqual(directory_bytes(root), before)
                code, output, _ = self.cli("recover", root=root)
                self.assertEqual(code, 0)
                self.assertEqual(output["truncated_bytes"], len(damaged))
                self.assertEqual((root / "events.log").read_bytes(), first)
                self.assertEqual(
                    {
                        key: value
                        for key, value in directory_bytes(root).items()
                        if key != "events.log"
                    },
                    {key: value for key, value in before.items() if key != "events.log"},
                )

        middle_variants = {
            key: value
            for key, value in tail_variants.items()
            if key != "missing-lf"
        }
        immutable_commands = [
            ("get", "--key", "a"),
            ("list",),
            (
                "put",
                "--key",
                "a",
                "--value",
                "A2",
                "--request-id",
                "blocked",
                "--expected-version",
                "1",
            ),
            (
                "delete",
                "--key",
                "a",
                "--request-id",
                "blocked-delete",
                "--expected-version",
                "1",
            ),
            ("compact",),
            ("recover",),
        ]
        for name, damaged in middle_variants.items():
            with self.subTest(position="middle", damage=name):
                root = Path(self.temp_dir.name) / f"middle-{name}"
                root.mkdir()
                (root / "writer.lock").write_bytes(b"")
                (root / "snapshot.json.tmp").write_bytes(b"snapshot sentinel")
                (root / "events.log.tmp").write_bytes(b"log sentinel")
                (root / "events.log").write_bytes(first + damaged + second)
                before = directory_bytes(root)
                for command in immutable_commands:
                    code, output, _ = self.cli(*command, root=root)
                    self.assertEqual(
                        (code, output["error"]["code"]),
                        (7, "CORRUPT_LOG"),
                        (name, command, output),
                    )
                    self.assertEqual(directory_bytes(root), before)

    def test_compact_restart_idempotency_seq_and_corrupt_snapshot(self) -> None:
        store = JournalStore(self.root)
        first = store.put(key="a", value="A", request_id="r1", expected_version=0)
        store.put(key="b", value="B", request_id="r2", expected_version=0)
        store.delete(key="b", request_id="r3", expected_version=2)
        compacted = store.compact()
        self.assertEqual(compacted["snapshot_seq"], 3)
        self.assertEqual((self.root / "events.log").read_bytes(), b"")
        self.assertTrue((self.root / "snapshot.json").is_file())
        (self.root / "snapshot.json.tmp").write_text("{ignored", encoding="utf-8")
        (self.root / "events.log.tmp").write_text("ignored", encoding="utf-8")

        replay = JournalStore(self.root).put(
            key="a", value="A", request_id="r1", expected_version=0
        )
        self.assertEqual(replay, {**first, "replayed": True})
        next_result = JournalStore(self.root).put(
            key="b", value="B2", request_id="r4", expected_version=3
        )
        self.assertEqual(next_result["seq"], 4)
        self.assertEqual(JournalStore(self.root).compact()["snapshot_seq"], 4)

        (self.root / "snapshot.json").write_text("{broken", encoding="utf-8")
        snapshot_before = (self.root / "snapshot.json").read_bytes()
        code, output, _ = self.cli("recover")
        self.assertEqual((code, output["error"]["code"]), (8, "CORRUPT_SNAPSHOT"))
        self.assertEqual((self.root / "snapshot.json").read_bytes(), snapshot_before)

    def test_committed_snapshot_tolerates_pre_clear_log_after_interrupted_compact(self) -> None:
        store = JournalStore(self.root)
        first = store.put(key="a", value="A", request_id="r1", expected_version=0)
        pre_compact_log = (self.root / "events.log").read_bytes()
        store.compact()
        (self.root / "events.log").write_bytes(pre_compact_log)

        self.assertEqual(JournalStore(self.root).get("a")["version"], first["version"])
        second = JournalStore(self.root).put(
            key="a", value="A2", request_id="r2", expected_version=first["version"]
        )
        self.assertEqual(second["seq"], 2)
        self.assertEqual(JournalStore(self.root).compact()["snapshot_seq"], 2)

    def test_snapshot_damage_matrix_is_read_only_and_stably_classified(self) -> None:
        seed = Path(self.temp_dir.name) / "snapshot-seed"
        JournalStore(seed).put(key="a", value="A", request_id="r1", expected_version=0)
        JournalStore(seed).compact()
        valid_snapshot = (seed / "snapshot.json").read_bytes()
        invalid_history = json.loads(valid_snapshot)
        invalid_history["requests"]["r1"]["fingerprint"]["expected_version"] = 1
        invalid_history_raw = (
            json.dumps(
                invalid_history, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            + b"\n"
        )
        wrong_version = json.loads(valid_snapshot)
        wrong_version["format_version"] = 2
        wrong_version_raw = (
            json.dumps(wrong_version, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
            + b"\n"
        )
        variants = {
            "utf8": b"\xff",
            "json": b"{broken",
            "schema": b"{}\n",
            "history": invalid_history_raw,
            "format": wrong_version_raw,
            "deep": b"[" * 1200 + b"0" + b"]" * 1200,
        }
        commands = [
            ("get", "--key", "a"),
            ("list",),
            (
                "put",
                "--key",
                "b",
                "--value",
                "B",
                "--request-id",
                "blocked",
                "--expected-version",
                "0",
            ),
            (
                "delete",
                "--key",
                "a",
                "--request-id",
                "blocked-delete",
                "--expected-version",
                "1",
            ),
            ("compact",),
            ("recover",),
        ]
        for name, snapshot in variants.items():
            with self.subTest(damage=name):
                root = Path(self.temp_dir.name) / f"snapshot-{name}"
                root.mkdir()
                (root / "snapshot.json").write_bytes(snapshot)
                (root / "events.log").write_bytes(
                    encode_record(self._record(seq=1, key="a", request_id="r1", value="A"))
                )
                (root / "writer.lock").write_bytes(b"lock sentinel")
                (root / "snapshot.json.tmp").write_bytes(b"snapshot tmp sentinel")
                (root / "events.log.tmp").write_bytes(b"log tmp sentinel")
                before = directory_bytes(root)
                for command in commands:
                    code, output, _ = self.cli(*command, root=root)
                    self.assertEqual(
                        (code, output["error"]["code"]),
                        (8, "CORRUPT_SNAPSHOT"),
                        (name, command, output),
                    )
                    self.assertEqual(directory_bytes(root), before)

        pristine_root = Path(self.temp_dir.name) / "snapshot-only"
        pristine_root.mkdir()
        (pristine_root / "snapshot.json").write_bytes(b"{broken")
        before = directory_bytes(pristine_root)
        code, output, _ = self.cli("recover", root=pristine_root)
        self.assertEqual((code, output["error"]["code"]), (8, "CORRUPT_SNAPSHOT"))
        self.assertEqual(directory_bytes(pristine_root), before)

    def test_commit_and_compact_fsync_replace_order_and_snapshot_structure(self) -> None:
        observed: list[tuple[str, str]] = []
        root_path = str(self.root.resolve())
        events_path = str((self.root / "events.log").resolve())
        snapshot_tmp_path = str((self.root / "snapshot.json.tmp").resolve())
        snapshot_path = str((self.root / "snapshot.json").resolve())
        events_tmp_path = str((self.root / "events.log.tmp").resolve())
        real_fsync = store_module.os.fsync
        real_replace = store_module.os.replace
        real_path_open = Path.open

        class ObservedStream:
            def __init__(self, stream, name: str) -> None:
                self.stream = stream
                self.name = name

            def __enter__(self):
                self.stream.__enter__()
                return self

            def __exit__(self, exc_type, exc, traceback):
                return self.stream.__exit__(exc_type, exc, traceback)

            def write(self, data):
                observed.append(("write", self.name))
                return self.stream.write(data)

            def flush(self):
                observed.append(("flush", self.name))
                return self.stream.flush()

            def __getattr__(self, name):
                return getattr(self.stream, name)

        def observe_open(path: Path, *args, **kwargs):
            stream = real_path_open(path, *args, **kwargs)
            if path.name in {"events.log", "snapshot.json.tmp", "events.log.tmp"}:
                resolved = str(path.resolve())
                observed.append(("open", resolved))
                return ObservedStream(stream, resolved)
            return stream

        def descriptor_name(file_descriptor: int) -> str:
            descriptor = os.fstat(file_descriptor)
            candidates = [
                self.root,
                self.root / "events.log",
                self.root / "snapshot.json.tmp",
                self.root / "events.log.tmp",
                self.root / "writer.lock",
            ]
            for candidate in candidates:
                try:
                    candidate_stat = candidate.stat()
                except FileNotFoundError:
                    continue
                if (
                    candidate_stat.st_dev == descriptor.st_dev
                    and candidate_stat.st_ino == descriptor.st_ino
                ):
                    return str(candidate.resolve())
            return "unknown"

        def observe_fsync(file_descriptor: int) -> None:
            observed.append(("fsync", descriptor_name(file_descriptor)))
            real_fsync(file_descriptor)

        def observe_replace(source, destination) -> None:
            source_path = str(Path(source).resolve())
            destination_path = str(Path(destination).resolve())
            source_stat = Path(source).stat()
            observed.append(("replace", f"{source_path}->{destination_path}"))
            real_replace(source, destination)
            destination_stat = Path(destination).stat()
            self.assertEqual(
                (destination_stat.st_dev, destination_stat.st_ino),
                (source_stat.st_dev, source_stat.st_ino),
            )

        with mock.patch.object(Path, "open", new=observe_open):
            with mock.patch.object(store_module.os, "fsync", side_effect=observe_fsync):
                JournalStore(self.root).put(
                    key="a", value="A", request_id="r1", expected_version=0
                )
        mutation_write = max(
            index
            for index, event in enumerate(observed)
            if event == ("write", events_path)
        )
        self.assertEqual(
            observed[mutation_write : mutation_write + 3],
            [
                ("write", events_path),
                ("flush", events_path),
                ("fsync", events_path),
            ],
        )

        JournalStore(self.root).put(
            key="b", value="B", request_id="r2", expected_version=0
        )
        JournalStore(self.root).delete(
            key="b", request_id="r3", expected_version=2
        )
        observed.clear()
        with mock.patch.object(Path, "open", new=observe_open):
            with mock.patch.object(store_module.os, "fsync", side_effect=observe_fsync):
                with mock.patch.object(
                    store_module.os, "replace", side_effect=observe_replace
                ):
                    result = JournalStore(self.root).compact()
        self.assertEqual(result["snapshot_seq"], 3)
        snapshot_tmp_open = observed.index(("open", snapshot_tmp_path))
        self.assertEqual(
            observed[snapshot_tmp_open:],
            [
                ("open", snapshot_tmp_path),
                ("write", snapshot_tmp_path),
                ("flush", snapshot_tmp_path),
                ("fsync", snapshot_tmp_path),
                ("replace", f"{snapshot_tmp_path}->{snapshot_path}"),
                ("fsync", root_path),
                ("open", events_tmp_path),
                ("write", events_tmp_path),
                ("flush", events_tmp_path),
                ("fsync", events_tmp_path),
                ("replace", f"{events_tmp_path}->{events_path}"),
                ("fsync", root_path),
            ],
        )
        self.assertEqual(
            {path.name for path in self.root.iterdir()},
            {"events.log", "snapshot.json", "writer.lock"},
        )
        snapshot = json.loads((self.root / "snapshot.json").read_bytes())
        self.assertEqual(set(snapshot), {"format_version", "keys", "last_seq", "requests"})
        self.assertEqual((snapshot["format_version"], snapshot["last_seq"]), (1, 3))
        self.assertEqual(
            snapshot["keys"],
            {
                "a": {"tombstone": False, "value": "A", "version": 1},
                "b": {"tombstone": True, "value": None, "version": 3},
            },
        )
        self.assertEqual(
            snapshot["requests"],
            {
                "r1": {
                    "fingerprint": {
                        "expected_version": 0,
                        "key": "a",
                        "op": "put",
                        "value": "A",
                    },
                    "result": {"key": "a", "seq": 1, "version": 1},
                },
                "r2": {
                    "fingerprint": {
                        "expected_version": 0,
                        "key": "b",
                        "op": "put",
                        "value": "B",
                    },
                    "result": {"key": "b", "seq": 2, "version": 2},
                },
                "r3": {
                    "fingerprint": {
                        "expected_version": 2,
                        "key": "b",
                        "op": "delete",
                        "value": None,
                    },
                    "result": {"key": "b", "seq": 3, "version": 3},
                },
            },
        )
        self.assertEqual((self.root / "events.log").read_bytes(), b"")


class CliAndConcurrencyTests(JournalTestCase):
    def spawn_ready_cli(self, marker: Path, *args: str) -> subprocess.Popen:
        script = """
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
marker = pathlib.Path(sys.argv[2])
import fcntl
real_flock = fcntl.flock
def ready_flock(file_descriptor, operation):
    marker.write_text("ready", encoding="utf-8")
    return real_flock(file_descriptor, operation)
fcntl.flock = ready_flock
import cli
sys.argv = ["journal", "--root", sys.argv[3], *sys.argv[4:]]
raise SystemExit(cli.main())
"""
        return subprocess.Popen(
            [
                sys.executable,
                "-c",
                script,
                str(BACKEND),
                str(marker),
                str(self.root),
                *args,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def wait_until_ready(
        self, markers: list[Path], processes: list[subprocess.Popen]
    ) -> None:
        deadline = time.monotonic() + 10
        while not all(marker.exists() for marker in markers):
            if time.monotonic() >= deadline:
                self.fail(
                    f"children did not reach flock: markers={markers}, "
                    f"returncodes={[process.poll() for process in processes]}"
                )
            time.sleep(0.01)
        self.assertTrue(all(process.poll() is None for process in processes))

    def test_cli_contract_and_exit_codes(self) -> None:
        code, put, stderr = self.cli(
            "put",
            "--key",
            "k",
            "--value",
            "",
            "--request-id",
            "r1",
            "--expected-version",
            "0",
        )
        self.assertEqual((code, stderr, put["ok"], put["replayed"]), (0, "", True, False))
        self.assertEqual(self.cli("get", "--key", "k")[1]["value"], "")
        self.assertEqual(self.cli("list")[1]["items"][0]["key"], "k")

        code, output, _ = self.cli("get", "--key", "missing")
        self.assertEqual((code, output["error"]["code"]), (3, "NOT_FOUND"))
        code, output, _ = self.cli(
            "put",
            "--key",
            "k",
            "--value",
            "x",
            "--request-id",
            "r2",
            "--expected-version",
            "0",
        )
        self.assertEqual((code, output["error"]["code"]), (4, "VERSION_CONFLICT"))
        code, output, _ = self.cli(
            "put",
            "--key",
            "other",
            "--value",
            "x",
            "--request-id",
            "r1",
            "--expected-version",
            "0",
        )
        self.assertEqual((code, output["error"]["code"]), (5, "IDEMPOTENCY_CONFLICT"))
        code, output, _ = self.cli("put", "--key", "incomplete")
        self.assertEqual((code, output["error"]["code"]), (2, "INVALID_ARGUMENT"))
        code, output, _ = self.cli(
            "put",
            "--key",
            "x",
            "--value",
            "x",
            "--request-id",
            "negative",
            "--expected-version",
            "-1",
        )
        self.assertEqual((code, output["error"]["code"]), (2, "INVALID_ARGUMENT"))
        for arguments in [
            ("unknown",),
            (
                "put",
                "--key",
                "x",
                "--value",
                "x",
                "--request-id",
                "not-int",
                "--expected-version",
                "abc",
            ),
            ("list", "--unknown-option"),
        ]:
            with self.subTest(arguments=arguments):
                code, output, _ = self.cli(*arguments)
                self.assertEqual(
                    (code, output["error"]["code"]), (2, "INVALID_ARGUMENT")
                )
        root_arguments = ["--root", str(self.root)]
        required_argument_cases = [
            root_arguments,
            ["list"],
            root_arguments
            + [
                "put",
                "--value",
                "v",
                "--request-id",
                "missing-key",
                "--expected-version",
                "0",
            ],
            root_arguments
            + [
                "put",
                "--key",
                "k",
                "--request-id",
                "missing-value",
                "--expected-version",
                "0",
            ],
            root_arguments
            + [
                "put",
                "--key",
                "k",
                "--value",
                "v",
                "--expected-version",
                "0",
            ],
            root_arguments
            + [
                "put",
                "--key",
                "k",
                "--value",
                "v",
                "--request-id",
                "missing-version",
            ],
            root_arguments + ["get"],
            root_arguments
            + [
                "delete",
                "--request-id",
                "missing-key",
                "--expected-version",
                "1",
            ],
            root_arguments
            + ["delete", "--key", "k", "--expected-version", "1"],
            root_arguments
            + ["delete", "--key", "k", "--request-id", "missing-version"],
        ]
        for arguments in required_argument_cases:
            with self.subTest(missing_required=arguments):
                code, output, _ = self.raw_cli(*arguments)
                self.assertEqual(
                    (code, output["error"]["code"]), (2, "INVALID_ARGUMENT")
                )

        invalid_root = Path(self.temp_dir.name) / "state-file"
        invalid_root.write_text("not a directory", encoding="utf-8")
        code, output, _ = self.cli("list", root=invalid_root)
        self.assertEqual((code, output["error"]["code"]), (2, "INVALID_ARGUMENT"))

    def test_full_real_cli_lifecycle_and_restart(self) -> None:
        code, beta, stderr = self.cli(
            "put",
            "--key",
            "beta",
            "--value",
            "B",
            "--request-id",
            "r-beta",
            "--expected-version",
            "0",
        )
        self.assertEqual(
            (code, stderr, beta),
            (
                0,
                "",
                {
                    "ok": True,
                    "seq": 1,
                    "key": "beta",
                    "version": 1,
                    "replayed": False,
                },
            ),
        )
        code, alpha, stderr = self.cli(
            "put",
            "--key",
            "alpha",
            "--value",
            "A",
            "--request-id",
            "r-alpha",
            "--expected-version",
            "0",
        )
        self.assertEqual((code, stderr, alpha["seq"], alpha["replayed"]), (0, "", 2, False))
        code, replay, stderr = self.cli(
            "put",
            "--key",
            "beta",
            "--value",
            "B",
            "--request-id",
            "r-beta",
            "--expected-version",
            "0",
        )
        self.assertEqual(
            (code, stderr, replay),
            (
                0,
                "",
                {
                    "ok": True,
                    "seq": 1,
                    "key": "beta",
                    "version": 1,
                    "replayed": True,
                },
            ),
        )
        conflicting_commands = {
            "key": (
                "put",
                "--key",
                "other",
                "--value",
                "B",
                "--request-id",
                "r-beta",
                "--expected-version",
                "0",
            ),
            "value": (
                "put",
                "--key",
                "beta",
                "--value",
                "different",
                "--request-id",
                "r-beta",
                "--expected-version",
                "0",
            ),
            "expected_version": (
                "put",
                "--key",
                "beta",
                "--value",
                "B",
                "--request-id",
                "r-beta",
                "--expected-version",
                "1",
            ),
            "op": (
                "delete",
                "--key",
                "beta",
                "--request-id",
                "r-beta",
                "--expected-version",
                "0",
            ),
        }
        for dimension, command in conflicting_commands.items():
            with self.subTest(idempotency_dimension=dimension):
                before_conflict = directory_bytes(self.root)
                code, conflict, stderr = self.cli(*command)
                self.assertEqual(
                    (code, stderr, conflict["error"]["code"]),
                    (5, "", "IDEMPOTENCY_CONFLICT"),
                )
                self.assertEqual(directory_bytes(self.root), before_conflict)
        replay_after_conflicts = self.cli(
            "put",
            "--key",
            "beta",
            "--value",
            "B",
            "--request-id",
            "r-beta",
            "--expected-version",
            "0",
        )[1]
        self.assertEqual((replay_after_conflicts["seq"], replay_after_conflicts["replayed"]), (1, True))
        self.assertEqual(
            self.cli("get", "--key", "alpha")[1],
            {"ok": True, "key": "alpha", "value": "A", "version": 2},
        )
        self.assertEqual(
            self.cli("list")[1],
            {
                "ok": True,
                "items": [
                    {"key": "alpha", "value": "A", "version": 2},
                    {"key": "beta", "value": "B", "version": 1},
                ],
            },
        )
        code, deleted, stderr = self.cli(
            "delete",
            "--key",
            "beta",
            "--request-id",
            "r-delete",
            "--expected-version",
            "1",
        )
        self.assertEqual(
            (code, stderr, deleted),
            (
                0,
                "",
                {
                    "ok": True,
                    "seq": 3,
                    "key": "beta",
                    "version": 3,
                    "replayed": False,
                },
            ),
        )
        self.assertEqual(
            self.cli(
                "delete",
                "--key",
                "beta",
                "--request-id",
                "r-delete",
                "--expected-version",
                "1",
            )[1]["replayed"],
            True,
        )
        self.assertEqual(self.cli("compact")[1], {"ok": True, "snapshot_seq": 3})
        self.assertEqual(
            self.cli("get", "--key", "beta")[0:2],
            (3, {"ok": False, "error": {"code": "NOT_FOUND", "message": "key 'beta' was not found"}}),
        )
        self.assertEqual(
            self.cli("list")[1],
            {
                "ok": True,
                "items": [{"key": "alpha", "value": "A", "version": 2}],
            },
        )
        self.assertEqual(
            self.cli("recover")[1], {"ok": True, "truncated_bytes": 0}
        )

    def test_concurrent_processes_have_unique_seq_and_single_winner(self) -> None:
        self.root.mkdir()
        lock_path = self.root / "writer.lock"
        lock_path.write_bytes(b"")
        different = []
        different_markers = []
        with lock_path.open("a+b") as barrier:
            fcntl.flock(barrier.fileno(), fcntl.LOCK_EX)
            for index in range(8):
                marker = Path(self.temp_dir.name) / f"different-ready-{index}"
                different_markers.append(marker)
                different.append(
                    self.spawn_ready_cli(
                        marker,
                        "put",
                        "--key",
                        f"k{index}",
                        "--value",
                        str(index),
                        "--request-id",
                        f"r{index}",
                        "--expected-version",
                        "0",
                    )
                )
            self.wait_until_ready(different_markers, different)
            fcntl.flock(barrier.fileno(), fcntl.LOCK_UN)
        results = []
        for process in different:
            stdout, _ = process.communicate(timeout=10)
            results.append((process.returncode, json.loads(stdout)))
        self.assertTrue(all(code == 0 for code, _ in results), results)
        self.assertEqual(sorted(output["seq"] for _, output in results), list(range(1, 9)))
        self.assertEqual(len(JournalStore(self.root).list_items()), 8)

        current = JournalStore(self.root).put(
            key="shared", value="base", request_id="base", expected_version=0
        )
        contenders = []
        contender_markers = []
        with lock_path.open("a+b") as barrier:
            fcntl.flock(barrier.fileno(), fcntl.LOCK_EX)
            for index in range(6):
                marker = Path(self.temp_dir.name) / f"contender-ready-{index}"
                contender_markers.append(marker)
                contenders.append(
                    self.spawn_ready_cli(
                        marker,
                        "put",
                        "--key",
                        "shared",
                        "--value",
                        f"v{index}",
                        "--request-id",
                        f"shared-{index}",
                        "--expected-version",
                        str(current["version"]),
                    )
                )
            self.wait_until_ready(contender_markers, contenders)
            fcntl.flock(barrier.fileno(), fcntl.LOCK_UN)
        contender_results = []
        for process in contenders:
            stdout, _ = process.communicate(timeout=10)
            contender_results.append((process.returncode, json.loads(stdout)))
        self.assertEqual(sum(code == 0 for code, _ in contender_results), 1)
        self.assertTrue(
            all(
                code == 0 or output["error"]["code"] == "VERSION_CONFLICT"
                for code, output in contender_results
            ),
            contender_results,
        )
        log_records = [
            decode_record(line)
            for line in (self.root / "events.log").read_bytes().splitlines(keepends=True)
        ]
        self.assertEqual([record["seq"] for record in log_records], list(range(1, 11)))


if __name__ == "__main__":
    unittest.main()
