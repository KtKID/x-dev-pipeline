"""Crash-consistent journal store. Implement from task contract."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

from locking import StateLock
from record import RecordError, decode_record, encode_record


class StoreError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class _State:
    last_seq: int
    entries: dict[str, dict[str, object]]
    requests: dict[str, dict[str, object]]


@dataclass
class _ScanResult:
    state: _State
    tail_offset: int | None = None
    total_bytes: int = 0


def _is_int(value: object, *, minimum: int = 0) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= minimum


def _fingerprint(
    op: str, key: str, value: str | None, expected_version: int
) -> dict[str, object]:
    return {
        "op": op,
        "key": key,
        "value": value,
        "expected_version": expected_version,
    }


def _validate_fingerprint(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {
        "op",
        "key",
        "value",
        "expected_version",
    }:
        raise ValueError("invalid request fingerprint")
    op = value["op"]
    key = value["key"]
    request_value = value["value"]
    expected_version = value["expected_version"]
    if not isinstance(op, str) or op not in {"put", "delete"} or not isinstance(key, str):
        raise ValueError("invalid request fingerprint")
    if not _is_int(expected_version):
        raise ValueError("invalid request fingerprint")
    if op == "put" and not isinstance(request_value, str):
        raise ValueError("invalid request fingerprint")
    if op == "delete" and request_value is not None:
        raise ValueError("invalid request fingerprint")
    return dict(value)


class JournalStore:
    def __init__(self, root) -> None:
        self.root = Path(root)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            self.events_path.touch(exist_ok=True)
        except OSError as exc:
            raise StoreError("INVALID_ARGUMENT", f"cannot initialize state directory: {exc}") from exc

    @property
    def events_path(self) -> Path:
        return self.root / "events.log"

    @property
    def snapshot_path(self) -> Path:
        return self.root / "snapshot.json"

    def _empty_state(self) -> _State:
        return _State(last_seq=0, entries={}, requests={})

    def _decode_snapshot(self) -> _State:
        if not self.snapshot_path.exists():
            return self._empty_state()
        try:
            raw = self.snapshot_path.read_bytes()
            decoded = json.loads(raw.decode("utf-8"))
            return self._validate_snapshot(decoded)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            RecursionError,
            TypeError,
            ValueError,
        ) as exc:
            raise StoreError("CORRUPT_SNAPSHOT", f"invalid committed snapshot: {exc}") from exc

    def _validate_snapshot(self, decoded: object) -> _State:
        if not isinstance(decoded, dict) or set(decoded) != {
            "format_version",
            "last_seq",
            "entries",
            "requests",
        }:
            raise ValueError("snapshot object has invalid fields")
        if isinstance(decoded["format_version"], bool) or decoded["format_version"] != 1:
            raise ValueError("unsupported snapshot format")
        last_seq = decoded["last_seq"]
        if not _is_int(last_seq):
            raise ValueError("snapshot last_seq must be a non-negative integer")
        entries_raw = decoded["entries"]
        requests_raw = decoded["requests"]
        if not isinstance(entries_raw, dict) or not isinstance(requests_raw, dict):
            raise ValueError("snapshot entries and requests must be objects")

        entries: dict[str, dict[str, object]] = {}
        for key, entry in entries_raw.items():
            if not isinstance(key, str) or not isinstance(entry, dict) or set(entry) != {
                "value",
                "version",
            }:
                raise ValueError("invalid snapshot entry")
            version = entry["version"]
            value = entry["value"]
            if not _is_int(version, minimum=1) or version > last_seq:
                raise ValueError("invalid snapshot entry version")
            if value is not None and not isinstance(value, str):
                raise ValueError("invalid snapshot entry value")
            entries[key] = {"value": value, "version": version}

        requests: dict[str, dict[str, object]] = {}
        by_seq: dict[int, tuple[str, dict[str, object], dict[str, object]]] = {}
        for request_id, request in requests_raw.items():
            if not isinstance(request_id, str) or not isinstance(request, dict) or set(request) != {
                "fingerprint",
                "result",
            }:
                raise ValueError("invalid snapshot request")
            fingerprint = _validate_fingerprint(request["fingerprint"])
            result = request["result"]
            if not isinstance(result, dict) or set(result) != {
                "seq",
                "key",
                "version",
                "replayed",
            }:
                raise ValueError("invalid snapshot request result")
            seq = result["seq"]
            if (
                not _is_int(seq, minimum=1)
                or not _is_int(result["version"], minimum=1)
                or result["version"] != seq
                or result["key"] != fingerprint["key"]
                or result["replayed"] is not False
                or seq > last_seq
                or seq in by_seq
            ):
                raise ValueError("inconsistent snapshot request result")
            stored_result = {
                "seq": seq,
                "key": result["key"],
                "version": result["version"],
                "replayed": False,
            }
            requests[request_id] = {
                "fingerprint": fingerprint,
                "result": stored_result,
            }
            by_seq[seq] = (request_id, fingerprint, stored_result)

        if len(by_seq) != last_seq or any(
            actual != expected for expected, actual in enumerate(sorted(by_seq), start=1)
        ):
            raise ValueError("snapshot request history does not cover every sequence")

        rebuilt_entries: dict[str, dict[str, object]] = {}
        for seq in range(1, last_seq + 1):
            _request_id, fingerprint, result = by_seq[seq]
            key = fingerprint["key"]
            assert isinstance(key, str)
            current = rebuilt_entries.get(key)
            current_version = 0 if current is None else current["version"]
            if fingerprint["expected_version"] != current_version:
                raise ValueError("snapshot request history has a version discontinuity")
            if fingerprint["op"] == "delete" and (
                current is None or current["value"] is None
            ):
                raise ValueError("snapshot request history deletes an absent key")
            if result["seq"] != seq:
                raise ValueError("snapshot request sequence is inconsistent")
            rebuilt_entries[key] = {
                "value": fingerprint["value"],
                "version": seq,
            }
        if entries != rebuilt_entries:
            raise ValueError("snapshot entries do not match request history")
        return _State(last_seq=last_seq, entries=entries, requests=requests)

    def _record_fingerprint(self, record: dict[str, object]) -> dict[str, object]:
        return _fingerprint(
            str(record["op"]),
            str(record["key"]),
            record["value"] if isinstance(record["value"], str) else None,
            int(record["expected_version"]),
        )

    def _apply_record(self, state: _State, record: dict[str, object]) -> None:
        seq = record["seq"]
        key = record["key"]
        request_id = record["request_id"]
        assert isinstance(seq, int) and isinstance(key, str) and isinstance(request_id, str)
        if seq != state.last_seq + 1:
            raise ValueError("log sequence is not contiguous")
        if request_id in state.requests:
            raise ValueError("log reuses a committed request_id")
        entry = state.entries.get(key)
        current_version = 0 if entry is None else entry["version"]
        if record["expected_version"] != current_version:
            raise ValueError("log expected_version does not match state")
        if record["op"] == "delete" and (entry is None or entry["value"] is None):
            raise ValueError("log deletes an absent key")
        result = {"seq": seq, "key": key, "version": seq, "replayed": False}
        state.entries[key] = {"value": record["value"], "version": seq}
        state.requests[request_id] = {
            "fingerprint": self._record_fingerprint(record),
            "result": result,
        }
        state.last_seq = seq

    def _validate_overlap(self, state: _State, record: dict[str, object]) -> None:
        request_id = record["request_id"]
        assert isinstance(request_id, str)
        stored = state.requests.get(request_id)
        expected_result = {
            "seq": record["seq"],
            "key": record["key"],
            "version": record["seq"],
            "replayed": False,
        }
        if (
            stored is None
            or stored["fingerprint"] != self._record_fingerprint(record)
            or stored["result"] != expected_result
        ):
            raise ValueError("log overlap does not match committed snapshot")

    def _scan_log(self, state: _State) -> _ScanResult:
        try:
            data = self.events_path.read_bytes()
        except OSError as exc:
            raise StoreError("CORRUPT_LOG", f"cannot read events.log: {exc}") from exc
        newline_parts = data.split(b"\n")
        lines = [part + b"\n" for part in newline_parts[:-1]]
        if newline_parts[-1]:
            lines.append(newline_parts[-1])
        offset = 0
        previous_seq: int | None = None
        snapshot_seq = state.last_seq
        for index, line in enumerate(lines):
            is_last = index == len(lines) - 1
            try:
                if not line.endswith(b"\n"):
                    raise RecordError("physical record is missing newline")
                record = decode_record(line)
            except RecordError as exc:
                if is_last:
                    return _ScanResult(state=state, tail_offset=offset, total_bytes=len(data))
                raise StoreError("CORRUPT_LOG", f"corrupt log record before tail: {exc}") from exc
            try:
                seq = record["seq"]
                assert isinstance(seq, int)
                crosses_snapshot_boundary = (
                    previous_seq is not None
                    and previous_seq <= snapshot_seq
                    and seq == snapshot_seq + 1
                )
                if (
                    previous_seq is not None
                    and seq != previous_seq + 1
                    and not crosses_snapshot_boundary
                ):
                    raise ValueError("physical log sequence is not contiguous")
                if seq <= snapshot_seq:
                    if state.last_seq != snapshot_seq:
                        raise ValueError("snapshot overlap appears after new log records")
                    self._validate_overlap(state, record)
                else:
                    self._apply_record(state, record)
                previous_seq = seq
            except (ValueError, AssertionError) as exc:
                raise StoreError("CORRUPT_LOG", f"log replay invariant failed: {exc}") from exc
            offset += len(line)

        return _ScanResult(state=state, total_bytes=len(data))

    def _load(self) -> _State:
        scan = self._scan_log(self._decode_snapshot())
        if scan.tail_offset is not None:
            raise StoreError("RECOVERY_REQUIRED", "events.log has a recoverable corrupt tail")
        return scan.state

    def _validate_mutation(
        self,
        *,
        op: str,
        key: object,
        value: object,
        request_id: object,
        expected_version: object,
    ) -> tuple[str, str | None, str, int]:
        if not isinstance(key, str):
            raise StoreError("INVALID_ARGUMENT", "key must be a string")
        if not isinstance(request_id, str):
            raise StoreError("INVALID_ARGUMENT", "request_id must be a string")
        if not _is_int(expected_version):
            raise StoreError("INVALID_ARGUMENT", "expected_version must be a non-negative integer")
        if op == "put" and not isinstance(value, str):
            raise StoreError("INVALID_ARGUMENT", "put value must be a string")
        if op == "delete" and value is not None:
            raise StoreError("INVALID_ARGUMENT", "delete value must be null")
        return key, value if isinstance(value, str) else None, request_id, expected_version

    def _mutate(
        self,
        *,
        op: str,
        key: object,
        value: object,
        request_id: object,
        expected_version: object,
    ) -> dict[str, object]:
        key, value, request_id, expected_version = self._validate_mutation(
            op=op,
            key=key,
            value=value,
            request_id=request_id,
            expected_version=expected_version,
        )
        with StateLock(self.root, exclusive=True):
            state = self._load()
            fingerprint = _fingerprint(op, key, value, expected_version)
            previous = state.requests.get(request_id)
            if previous is not None:
                if previous["fingerprint"] != fingerprint:
                    raise StoreError(
                        "IDEMPOTENCY_CONFLICT",
                        f"request_id {request_id!r} was committed with different content",
                    )
                replayed = dict(previous["result"])
                replayed["replayed"] = True
                return replayed

            entry = state.entries.get(key)
            current_version = 0 if entry is None else entry["version"]
            if expected_version != current_version:
                raise StoreError(
                    "VERSION_CONFLICT",
                    f"expected version {expected_version}, current version is {current_version}",
                )
            if op == "delete" and (entry is None or entry["value"] is None):
                raise StoreError("NOT_FOUND", f"key {key!r} does not exist")

            seq = state.last_seq + 1
            record = {
                "expected_version": expected_version,
                "key": key,
                "op": op,
                "request_id": request_id,
                "seq": seq,
                "value": value,
            }
            raw = encode_record(record)
            try:
                with self.events_path.open("ab") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError as exc:
                raise StoreError("INVALID_ARGUMENT", f"cannot append events.log: {exc}") from exc
            return {"seq": seq, "key": key, "version": seq, "replayed": False}

    def put(self, **kwargs):
        return self._mutate(op="put", value=kwargs.get("value"), **{
            "key": kwargs.get("key"),
            "request_id": kwargs.get("request_id"),
            "expected_version": kwargs.get("expected_version"),
        })

    def get(self, key: str):
        if not isinstance(key, str):
            raise StoreError("INVALID_ARGUMENT", "key must be a string")
        with StateLock(self.root, exclusive=False):
            state = self._load()
            entry = state.entries.get(key)
            if entry is None or entry["value"] is None:
                raise StoreError("NOT_FOUND", f"key {key!r} does not exist")
            return {"key": key, "value": entry["value"], "version": entry["version"]}

    def delete(self, **kwargs):
        return self._mutate(op="delete", value=None, **{
            "key": kwargs.get("key"),
            "request_id": kwargs.get("request_id"),
            "expected_version": kwargs.get("expected_version"),
        })

    def list_items(self):
        with StateLock(self.root, exclusive=False):
            state = self._load()
            return [
                {"key": key, "value": entry["value"], "version": entry["version"]}
                for key, entry in sorted(state.entries.items())
                if entry["value"] is not None
            ]

    def compact(self):
        with StateLock(self.root, exclusive=True):
            state = self._load()
            snapshot = {
                "format_version": 1,
                "last_seq": state.last_seq,
                "entries": state.entries,
                "requests": state.requests,
            }
            snapshot_bytes = json.dumps(
                snapshot, sort_keys=True, separators=(",", ":")
            ).encode("utf-8") + b"\n"
            self._replace_durable(self.root / "snapshot.json.tmp", self.snapshot_path, snapshot_bytes)
            self._replace_durable(self.root / "events.log.tmp", self.events_path, b"")
            return {"snapshot_seq": state.last_seq}

    def recover(self):
        with StateLock(self.root, exclusive=True):
            state = self._decode_snapshot()
            scan = self._scan_log(state)
            if scan.tail_offset is None:
                return {"truncated_bytes": 0}
            truncated_bytes = scan.total_bytes - scan.tail_offset
            try:
                with self.events_path.open("r+b") as stream:
                    stream.truncate(scan.tail_offset)
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError as exc:
                raise StoreError("CORRUPT_LOG", f"cannot truncate events.log: {exc}") from exc
            return {"truncated_bytes": truncated_bytes}

    def _replace_durable(self, temp_path: Path, target_path: Path, data: bytes) -> None:
        try:
            with temp_path.open("wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, target_path)
            directory_fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as exc:
            raise StoreError("INVALID_ARGUMENT", f"cannot durably replace {target_path.name}: {exc}") from exc
