#!/usr/bin/env python3
"""Deterministic, stdlib-only evaluator for journal-index-recovery."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import zlib


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
ORACLE_CASE = REPO_ROOT / "cases" / "journal-index-recovery"
PUBLIC_PROMPT = REPO_ROOT / "evals" / "problems" / "journal-index-recovery" / "PROMPT.md"
RECORD_FIELDS = {"seq", "op", "key", "value", "request_id", "expected_version", "crc32"}
ERROR_EXITS = {
    "NOT_FOUND": 3,
    "VERSION_CONFLICT": 4,
    "IDEMPOTENCY_CONFLICT": 5,
    "RECOVERY_REQUIRED": 6,
    "CORRUPT_LOG": 7,
    "CORRUPT_SNAPSHOT": 8,
}


def canonical_body(record: dict[str, object], *, ensure_ascii: bool = False) -> bytes:
    return json.dumps(
        {key: value for key, value in record.items() if key != "crc32"},
        ensure_ascii=ensure_ascii,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def make_record(*, seq: int, op: str, key: str, value: str | None, request_id: str, expected_version: int) -> bytes:
    record: dict[str, object] = {
        "seq": seq,
        "op": op,
        "key": key,
        "value": value,
        "request_id": request_id,
        "expected_version": expected_version,
    }
    record["crc32"] = f"{zlib.crc32(canonical_body(record)) & 0xFFFFFFFF:08x}"
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


class Harness:
    def __init__(self, fixture: pathlib.Path) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="journal-eval-")
        self.root = pathlib.Path(self.temp.name)
        self.backend = self.root / "backend"
        self.state = self.root / "state"
        shutil.copytree(fixture / "backend", self.backend)
        self.cli = self.backend / "cli.py"
        if not self.cli.is_file():
            raise AssertionError("fixture/backend/cli.py missing")

    def command(self, *args: str, timeout: float = 8) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(self.cli), "--root", str(self.state), *args],
            cwd=self.backend,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        lines = [line for line in result.stdout.decode("utf-8", errors="strict").splitlines() if line.strip()]
        assert len(lines) == 1, {"stdout": result.stdout.decode(errors="replace"), "stderr": result.stderr.decode(errors="replace")}
        value = json.loads(lines[0])
        assert isinstance(value, dict), value
        return result.returncode, value

    def process(self, *args: str) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            [sys.executable, str(self.cli), "--root", str(self.state), *args],
            cwd=self.backend,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def close(self) -> None:
        self.temp.cleanup()

    def __enter__(self) -> "Harness":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def error(value: dict[str, object]) -> str:
    detail = value.get("error")
    assert value.get("ok") is False and isinstance(detail, dict), value
    code = detail.get("code")
    assert isinstance(code, str), value
    return code


def assert_error_envelope(value: dict[str, object]) -> dict[str, object]:
    assert set(value) == {"ok", "error"} and value["ok"] is False, value
    detail = value["error"]
    assert isinstance(detail, dict) and set(detail) == {"code", "message"}, value
    assert isinstance(detail["code"], str) and detail["code"], value
    assert isinstance(detail["message"], str), value
    return detail


def assert_public_error(rc: int, value: dict[str, object], code: str) -> None:
    assert rc == ERROR_EXITS[code], (rc, value)
    detail = assert_error_envelope(value)
    assert detail["code"] == code, value


class Checks:
    def __init__(self, workspace: pathlib.Path) -> None:
        self.workspace = workspace
        self.fixture = workspace / "fixture"
        self.details: dict[str, tuple[bool, str]] = {}

    def record(self, key: str, fn) -> None:
        try:
            evidence = fn()
            self.details[key] = (True, str(evidence or "check passed"))
        except Exception as exc:
            self.details[key] = (False, f"{type(exc).__name__}: {exc}")

    def cli_contract(self) -> str:
        with Harness(self.fixture) as h:
            rc, value = h.command("get")
            assert rc == 2 and error(value), (rc, value)
            rc, value = h.command("get", "--key", "missing")
            assert rc == 3 and error(value) == "NOT_FOUND"
            rc, value = h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            assert rc == 0 and value.get("ok") is True
            rc, value = h.command("put", "--key", "a", "--value", "B", "--request-id", "r2", "--expected-version", "0")
            assert rc == 4 and error(value) == "VERSION_CONFLICT"
            rc, value = h.command("put", "--key", "b", "--value", "B", "--request-id", "r1", "--expected-version", "0")
            assert rc == 5 and error(value) == "IDEMPOTENCY_CONFLICT"
        return "CLI emitted one JSON object and stable usage/not-found/version/idempotency exits"

    def persistence(self) -> str:
        with Harness(self.fixture) as h:
            rc, beta = h.command("put", "--key", "beta", "--value", "B", "--request-id", "r-beta", "--expected-version", "0")
            rc2, alpha = h.command("put", "--key", "alpha", "--value", "A", "--request-id", "r-alpha", "--expected-version", "0")
            assert rc == rc2 == 0 and beta["version"] == 1 and alpha["version"] == 2
            rc, got = h.command("get", "--key", "alpha")
            assert rc == 0 and got == {"ok": True, "key": "alpha", "value": "A", "version": 2}
            rc, listed = h.command("list")
            assert rc == 0 and [item["key"] for item in listed["items"]] == ["alpha", "beta"]
        return "put/get/list persisted exact values and versions across fresh CLI processes"

    def idempotent_replay(self) -> str:
        with Harness(self.fixture) as h:
            args = ("put", "--key", "a", "--value", "A", "--request-id", "same", "--expected-version", "0")
            rc, first = h.command(*args)
            before = (h.state / "events.log").read_bytes()
            rc2, second = h.command(*args)
            after = (h.state / "events.log").read_bytes()
            assert rc == rc2 == 0 and first["seq"] == second["seq"] == 1
            assert first["replayed"] is False and second["replayed"] is True
            assert before == after
        return "identical request replay returned seq=1 and appended zero bytes"

    def idempotency_conflict(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r", "--expected-version", "0")
            before = (h.state / "events.log").read_bytes()
            rc, value = h.command("put", "--key", "a", "--value", "B", "--request-id", "r", "--expected-version", "1")
            assert rc == 5 and error(value) == "IDEMPOTENCY_CONFLICT"
            assert (h.state / "events.log").read_bytes() == before
            assert h.command("get", "--key", "a")[1]["value"] == "A"
        return "request_id conflict preserved log and live value"

    def version_conflict(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            before = (h.state / "events.log").read_bytes()
            rc, value = h.command("put", "--key", "a", "--value", "B", "--request-id", "r2", "--expected-version", "0")
            assert rc == 4 and error(value) == "VERSION_CONFLICT"
            assert (h.state / "events.log").read_bytes() == before
            assert h.command("get", "--key", "a")[1]["version"] == 1
        return "stale expected_version caused a side-effect-free VERSION_CONFLICT"

    def tombstone(self) -> str:
        with Harness(self.fixture) as h:
            put = h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")[1]
            deleted = h.command("delete", "--key", "a", "--request-id", "r2", "--expected-version", str(put["version"]))[1]
            assert deleted["version"] == 2
            rc, value = h.command("get", "--key", "a")
            assert rc == 3 and error(value) == "NOT_FOUND"
            assert h.command("list")[1]["items"] == []
            resurrected = h.command("put", "--key", "a", "--value", "A2", "--request-id", "r3", "--expected-version", "2")[1]
            assert resurrected["version"] == 3
            rc, value = h.command("delete", "--key", "never", "--request-id", "r4", "--expected-version", "0")
            assert rc == 3 and error(value) == "NOT_FOUND"
        return "delete hid live data, retained version=2, and allowed versioned resurrection"

    def canonical_log(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "天气", "--value", "晴", "--request-id", "r-cn", "--expected-version", "0")
            lines = (h.state / "events.log").read_bytes().splitlines()
            assert len(lines) == 1
            record = json.loads(lines[0].decode("utf-8"))
            assert set(record) == RECORD_FIELDS
            modes = []
            for ensure_ascii in (False, True):
                rendered = json.dumps(record, ensure_ascii=ensure_ascii, sort_keys=True, separators=(",", ":")).encode("utf-8")
                expected = f"{zlib.crc32(canonical_body(record, ensure_ascii=ensure_ascii)) & 0xFFFFFFFF:08x}"
                if lines[0] == rendered and record["crc32"] == expected:
                    modes.append(ensure_ascii)
            assert len(modes) == 1, {"raw": lines[0], "crc32": record["crc32"]}
        return "events.log matched canonical UTF-8 JSON and independently computed CRC-32"

    def truncated_tail(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            log = h.state / "events.log"
            healthy = log.read_bytes()
            tail = b'{"crc32":"dead'
            with log.open("ab") as handle:
                handle.write(tail)
            rc, value = h.command("get", "--key", "a")
            assert rc == 6 and error(value) == "RECOVERY_REQUIRED"
            rc, recovered = h.command("recover")
            assert rc == 0 and recovered["truncated_bytes"] == len(tail)
            assert log.read_bytes() == healthy and h.command("get", "--key", "a")[1]["value"] == "A"
        return "recover truncated an incomplete tail at the last valid byte boundary"

    def bad_crc_tail(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            log = h.state / "events.log"
            healthy = log.read_bytes()
            bad = bytearray(make_record(seq=2, op="put", key="b", value="B", request_id="r2", expected_version=0))
            marker = bad.find(b'"crc32":"') + len(b'"crc32":"')
            bad[marker] = ord("0") if bad[marker] != ord("0") else ord("1")
            with log.open("ab") as handle:
                handle.write(bad)
            assert h.command("list")[0] == 6
            rc, recovered = h.command("recover")
            assert rc == 0 and recovered["truncated_bytes"] == len(bad)
            assert log.read_bytes() == healthy and [item["key"] for item in h.command("list")[1]["items"]] == ["a"]
        return "recover removed a final CRC-invalid record and preserved committed state"

    def middle_corruption(self) -> str:
        with Harness(self.fixture) as h:
            for index, key in enumerate(("a", "b", "c"), start=1):
                h.command("put", "--key", key, "--value", key.upper(), "--request-id", f"r{index}", "--expected-version", "0")
            log = h.state / "events.log"
            lines = log.read_bytes().splitlines(keepends=True)
            bad = bytearray(lines[1])
            marker = bad.find(b'"crc32":"') + len(b'"crc32":"')
            bad[marker] = ord("0") if bad[marker] != ord("0") else ord("1")
            lines[1] = bytes(bad)
            log.write_bytes(b"".join(lines))
            frozen = log.read_bytes()
            for command in (("list",), ("recover",)):
                rc, value = h.command(*command)
                assert rc == 7 and error(value) == "CORRUPT_LOG", (rc, value)
                assert log.read_bytes() == frozen
        return "middle corruption produced read-only CORRUPT_LOG for normal and recover paths"

    def compact_state(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "live", "--value", "L", "--request-id", "r1", "--expected-version", "0")
            h.command("put", "--key", "gone", "--value", "G", "--request-id", "r2", "--expected-version", "0")
            h.command("delete", "--key", "gone", "--request-id", "r3", "--expected-version", "2")
            rc, value = h.command("compact")
            assert rc == 0 and value["snapshot_seq"] == 3
            assert (h.state / "snapshot.json").is_file() and (h.state / "events.log").read_bytes() == b""
            assert h.command("get", "--key", "live")[1]["value"] == "L"
            assert h.command("get", "--key", "gone")[0] == 3
            assert [item["key"] for item in h.command("list")[1]["items"]] == ["live"]
        return "compact restored live and tombstoned states from snapshot with an empty log"

    def compact_ledger(self) -> str:
        with Harness(self.fixture) as h:
            args = ("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            first = h.command(*args)[1]
            h.command("compact")
            replay = h.command(*args)[1]
            assert replay["replayed"] is True and replay["seq"] == first["seq"] == 1
            assert (h.state / "events.log").read_bytes() == b""
            next_value = h.command("put", "--key", "b", "--value", "B", "--request-id", "r2", "--expected-version", "0")[1]
            assert next_value["seq"] == 2
        return "snapshot retained request replay data and next global seq"

    def snapshot_commit(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            (h.state / "snapshot.json.tmp").write_text("uncommitted garbage", encoding="utf-8")
            assert h.command("get", "--key", "a")[1]["value"] == "A"
            h.command("compact")
            (h.state / "snapshot.json").write_text("committed garbage", encoding="utf-8")
            rc, value = h.command("get", "--key", "a")
            assert rc == 8 and error(value) == "CORRUPT_SNAPSHOT"
        return "stale snapshot.tmp was ignored and malformed committed snapshot was rejected"

    def compact_replace_window(self) -> str:
        with Harness(self.fixture) as h:
            args = ("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            rc, first = h.command(*args)
            assert rc == 0 and first["seq"] == 1
            old_log = (h.state / "events.log").read_bytes()
            assert h.command("compact")[0] == 0
            snapshot = (h.state / "snapshot.json").read_bytes()

            # Crash model: snapshot is published, while the old journal still
            # contains the prefix already represented by that snapshot.
            (h.state / "events.log").write_bytes(old_log)
            rc, replay = h.command(*args)
            assert rc == 0 and replay["seq"] == 1 and replay["replayed"] is True
            assert (h.state / "events.log").read_bytes() == old_log
            assert (h.state / "snapshot.json").read_bytes() == snapshot

            rc, committed = h.command(
                "put", "--key", "b", "--value", "B",
                "--request-id", "r2", "--expected-version", "0",
            )
            assert rc == 0 and committed["seq"] == 2
            assert h.command("get", "--key", "a")[1]["value"] == "A"
            assert h.command("get", "--key", "b")[1]["value"] == "B"
        return "snapshot-covered journal prefix was deduplicated across the compact replace window"

    def semantic_snapshot(self) -> str:
        with Harness(self.fixture) as h:
            h.state.mkdir(parents=True)
            payload = {
                "last_seq": 2,
                "keys": {"a": {"value": "B", "tombstone": False, "version": 2}},
                "requests": {
                    "r1": {
                        "fingerprint": {
                            "op": "put", "key": "a", "value": "A", "expected_version": 5,
                        },
                        "result": {
                            "ok": True, "seq": 1, "key": "a", "version": 1, "replayed": False,
                        },
                    },
                    "r2": {
                        "fingerprint": {
                            "op": "put", "key": "a", "value": "B", "expected_version": 1,
                        },
                        "result": {
                            "ok": True, "seq": 2, "key": "a", "version": 2, "replayed": False,
                        },
                    },
                },
            }
            snapshot = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            (h.state / "snapshot.json").write_bytes(snapshot)
            (h.state / "events.log").write_bytes(b"")
            commands = (
                ("get", "--key", "a"),
                ("list",),
                ("put", "--key", "b", "--value", "B", "--request-id", "r3", "--expected-version", "0"),
                ("compact",),
                ("recover",),
            )
            for command in commands:
                rc, value = h.command(*command)
                assert_public_error(rc, value, "CORRUPT_SNAPSHOT")
                assert (h.state / "snapshot.json").read_bytes() == snapshot
                assert (h.state / "events.log").read_bytes() == b""
        return "structurally valid but semantically impossible snapshot was rejected read-only"

    def semantic_tail(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            log = h.state / "events.log"
            invalid = make_record(
                seq=2, op="put", key="a", value="B",
                request_id="r2", expected_version=0,
            )
            with log.open("ab") as handle:
                handle.write(invalid)
            frozen = log.read_bytes()
            commands = (
                ("get", "--key", "a"),
                ("put", "--key", "b", "--value", "B", "--request-id", "r3", "--expected-version", "0"),
                ("compact",),
                ("recover",),
            )
            for command in commands:
                rc, value = h.command(*command)
                assert_public_error(rc, value, "CORRUPT_LOG")
                assert log.read_bytes() == frozen
        return "physically valid but semantically invalid final record remained read-only CORRUPT_LOG"

    def failed_request_reuse(self) -> str:
        with Harness(self.fixture) as h:
            rc, value = h.command(
                "delete", "--key", "missing", "--request-id", "reuse-missing", "--expected-version", "0",
            )
            assert_public_error(rc, value, "NOT_FOUND")
            rc, created = h.command(
                "put", "--key", "missing", "--value", "M",
                "--request-id", "reuse-missing", "--expected-version", "0",
            )
            assert rc == 0 and created["seq"] == 1 and created["replayed"] is False

            rc, value = h.command(
                "put", "--key", "missing", "--value", "M2",
                "--request-id", "reuse-stale", "--expected-version", "0",
            )
            assert_public_error(rc, value, "VERSION_CONFLICT")
            rc, updated = h.command(
                "put", "--key", "missing", "--value", "M2",
                "--request-id", "reuse-stale", "--expected-version", "1",
            )
            assert rc == 0 and updated["seq"] == 2 and updated["replayed"] is False
            assert (h.state / "events.log").read_bytes().count(b"\n") == 2
        return "failed missing-delete and stale-version request ids remained available for valid commits"

    def complete_error_contract(self) -> str:
        with Harness(self.fixture) as h:
            rc, value = h.command("get")
            assert rc == 2, (rc, value)
            argument_code = assert_error_envelope(value)["code"]
            rc, value = h.command("put")
            assert rc == 2 and assert_error_envelope(value)["code"] == argument_code, (rc, value)
            rc, value = h.command("get", "--key", "missing")
            assert_public_error(rc, value, "NOT_FOUND")
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            rc, value = h.command(
                "put", "--key", "a", "--value", "B", "--request-id", "r2", "--expected-version", "0",
            )
            assert_public_error(rc, value, "VERSION_CONFLICT")
            rc, value = h.command(
                "put", "--key", "b", "--value", "B", "--request-id", "r1", "--expected-version", "0",
            )
            assert_public_error(rc, value, "IDEMPOTENCY_CONFLICT")

        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            with (h.state / "events.log").open("ab") as handle:
                handle.write(b'{"partial"')
            rc, value = h.command("list")
            assert_public_error(rc, value, "RECOVERY_REQUIRED")

        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            invalid = make_record(
                seq=2, op="put", key="a", value="B",
                request_id="r2", expected_version=0,
            )
            with (h.state / "events.log").open("ab") as handle:
                handle.write(invalid)
            rc, value = h.command("list")
            assert_public_error(rc, value, "CORRUPT_LOG")

        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            h.command("compact")
            (h.state / "snapshot.json").write_text("{broken", encoding="utf-8")
            rc, value = h.command("get", "--key", "a")
            assert_public_error(rc, value, "CORRUPT_SNAPSHOT")
        return "all seven public errors preserved exact JSON envelopes, string messages, codes, and exits"

    def concurrent_writers(self) -> str:
        with Harness(self.fixture) as h:
            processes = [h.process("put", "--key", f"k{i:02}", "--value", str(i), "--request-id", f"r{i:02}", "--expected-version", "0") for i in range(20)]
            results = []
            for process in processes:
                out, err = process.communicate(timeout=15)
                assert process.returncode == 0, (out.decode(errors="replace"), err.decode(errors="replace"))
                results.append(json.loads(out))
            assert len({value["seq"] for value in results}) == 20
            listed = h.command("list")[1]["items"]
            assert len(listed) == 20 and [item["key"] for item in listed] == [f"k{i:02}" for i in range(20)]
        return "20 concurrent processes committed unique seq values with no lost keys"

    def concurrent_conflict(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "shared", "--value", "initial", "--request-id", "seed", "--expected-version", "0")
            processes = [h.process("put", "--key", "shared", "--value", f"v{i}", "--request-id", f"r{i}", "--expected-version", "1") for i in range(8)]
            exits = []
            for process in processes:
                out, err = process.communicate(timeout=15)
                assert out.strip(), err.decode(errors="replace")
                exits.append(process.returncode)
            assert exits.count(0) == 1 and exits.count(4) == 7, exits
            assert h.command("get", "--key", "shared")[1]["version"] == 2
        return "one of eight same-version writers committed and seven observed VERSION_CONFLICT"

    def stdlib_only(self) -> str:
        backend = self.fixture / "backend"
        local = {path.stem for path in backend.glob("*.py")}
        stdlib_root = pathlib.Path(sysconfig.get_paths()["stdlib"]).resolve()
        external: set[str] = set()
        for path in backend.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots = [node.module.split(".")[0]]
                else:
                    continue
                for root in roots:
                    if root in local:
                        continue
                    spec = importlib.util.find_spec(root)
                    origin = None if spec is None else spec.origin
                    if origin in ("built-in", "frozen"):
                        continue
                    if origin is None:
                        external.add(root)
                        continue
                    resolved = pathlib.Path(origin).resolve()
                    if stdlib_root not in resolved.parents or "site-packages" in resolved.parts:
                        external.add(root)
        assert not external, sorted(external)
        return "backend imports resolve to Python stdlib or local modules"

    def success_contract(self) -> str:
        with Harness(self.fixture) as h:
            args = ("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            rc, first = h.command(*args)
            assert rc == 0 and first == {
                "ok": True,
                "seq": 1,
                "key": "a",
                "version": 1,
                "replayed": False,
            }, first
            rc, replayed = h.command(*args)
            assert rc == 0 and replayed == {
                "ok": True,
                "seq": 1,
                "key": "a",
                "version": 1,
                "replayed": True,
            }, replayed
            rc, deleted = h.command(
                "delete",
                "--key",
                "a",
                "--request-id",
                "r2",
                "--expected-version",
                "1",
            )
            assert rc == 0 and deleted == {
                "ok": True,
                "seq": 2,
                "key": "a",
                "version": 2,
                "replayed": False,
            }, deleted
            assert h.command("list") == (0, {"ok": True, "items": []})
            assert h.command("compact") == (0, {"ok": True, "snapshot_seq": 2})
            assert h.command("recover") == (0, {"ok": True, "truncated_bytes": 0})
        return "all success responses exposed the exact public fields and values"

    def healthy_recover(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            log = h.state / "events.log"
            before = log.read_bytes()
            for _ in range(2):
                rc, value = h.command("recover")
                assert rc == 0 and value == {"ok": True, "truncated_bytes": 0}, value
                assert log.read_bytes() == before
                assert h.command("get", "--key", "a")[1]["value"] == "A"
        return "healthy recover repeated twice without changing journal bytes or state"

    def storage_layout(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            h.command("compact")
            h.command("recover")
            names = {path.name for path in h.state.iterdir()}
            assert names <= {"events.log", "snapshot.json", "writer.lock"}, sorted(names)
            assert {"events.log", "snapshot.json", "writer.lock"} <= names, sorted(names)
            assert (h.state / "events.log").read_bytes() == b""
            snapshot = json.loads((h.state / "snapshot.json").read_text(encoding="utf-8"))
            assert isinstance(snapshot, dict) and snapshot
        return "state directory contained only committed journal, snapshot, and lock files"

    def hygiene(self) -> str:
        assert not (self.workspace / ".git").exists()
        for relative in ("fixture/README.md",):
            candidate = self.workspace / relative
            oracle = ORACLE_CASE / relative
            assert candidate.is_file() and candidate.read_bytes() == oracle.read_bytes(), relative
        prompt = self.workspace / "PROMPT.md"
        assert prompt.is_file() and prompt.read_bytes() == PUBLIC_PROMPT.read_bytes(), "PROMPT.md"
        for path in self.workspace.rglob("*.pid"):
            raise AssertionError(f"pid leftover: {path}")
        return "public prompt and fixture README remained unchanged; no nested git or pid state"


EXPECTATIONS = [
    ("CLI JSON 结构与稳定退出码符合契约。", "cli_contract"),
    ("put/get/list 跨进程保持值、version 与排序。", "persistence"),
    ("同 request_id 同内容重试返回原 seq 且不追加。", "idempotent_replay"),
    ("同 request_id 不同内容产生无副作用幂等冲突。", "idempotency_conflict"),
    ("expected_version 冲突保持状态稳定。", "version_conflict"),
    ("delete、tombstone version 与 NOT_FOUND 语义正确。", "tombstone"),
    ("events.log 使用规范 JSON 与可独立校验 CRC-32。", "canonical_log"),
    ("截断尾部触发恢复并精确截断。", "truncated_tail"),
    ("最后记录 CRC 损坏可恢复且既有状态稳定。", "bad_crc_tail"),
    ("中间记录损坏只读失败且 recover 拒绝改写。", "middle_corruption"),
    ("compact 通过 snapshot + 空 log 恢复 live/tombstone 状态。", "compact_state"),
    ("compact 保留幂等账本与后续 seq 单调性。", "compact_ledger"),
    ("未提交 snapshot 临时文件被忽略，损坏的已提交 snapshot 被拒绝。", "snapshot_commit"),
    ("多进程并发写不同 key 无丢失且 seq 唯一。", "concurrent_writers"),
    ("同 key 同 expected_version 并发更新只有一个成功。", "concurrent_conflict"),
    ("backend 运行时代码只依赖 Python 标准库与本地模块。", "stdlib_only"),
    ("成功响应的 JSON 字段和值符合公开契约。", "success_contract"),
    ("健康日志 recover 可重复执行且无副作用。", "healthy_recover"),
    ("compact/recover 后状态目录符合固定布局且无临时文件。", "storage_layout"),
    ("compact snapshot/journal 替换窗口重启时重叠前缀只计入一次。", "compact_replace_window"),
    ("结构合法但语义不可能的 snapshot 被只读拒绝。", "semantic_snapshot"),
    ("物理完整但逻辑非法的最后记录被判为 CORRUPT_LOG。", "semantic_tail"),
    ("失败 mutation 不占用 request_id，修正后可复用提交。", "failed_request_reuse"),
    ("七类公开错误保持完整 JSON 契约与稳定退出码。", "complete_error_contract"),
    ("运行产物保持在声明范围且输入未被改写。", "hygiene"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    checks = Checks(args.workspace.resolve())
    for _text, method in EXPECTATIONS:
        checks.record(method, getattr(checks, method))
    expectations = []
    for text, method in EXPECTATIONS:
        passed, evidence = checks.details[method]
        expectations.append({"text": text, "passed": passed, "evidence": evidence})
    passed = sum(1 for item in expectations if item["passed"])
    critical_passed = all(checks.details[method][0] for _text, method in EXPECTATIONS[:24])
    result = {
        "rubric_version": 3,
        "assertion_points": 4,
        "expectations": expectations,
        "summary": {"passed": passed, "failed": len(expectations) - passed, "total": len(expectations), "pass_rate": passed / len(expectations)},
        "quality_score": passed * 4,
        "critical_gate_passed": critical_passed,
        "execution_metrics": {"total_tool_calls": 0, "errors_encountered": len(expectations) - passed},
        "eval_feedback": {"suggestions": [], "overall": "Deterministic local CLI, corruption, compaction, idempotency, storage-layout, and process-concurrency checks."},
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if passed == 25 and critical_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
