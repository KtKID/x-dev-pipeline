"""Crash-consistent snapshot and append-only journal store."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Optional

try:
    from .locking import StateLock
    from .record import RecordError, decode_record, encode_record
except ImportError:  # Direct ``python backend/cli.py`` execution.
    from locking import StateLock
    from record import RecordError, decode_record, encode_record


class StoreError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _Entry:
    record: dict[str, object]
    start: int
    end: int


@dataclass(frozen=True)
class _LogInspection:
    entries: list[_Entry]
    tail_boundary: Optional[int]
    total_bytes: int


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _empty_state() -> dict[str, object]:
    return {"last_seq": 0, "keys": {}, "requests": {}}


class JournalStore:
    def __init__(self, root) -> None:
        self.root = Path(root)
        self.events_path = self.root / "events.log"
        self.snapshot_path = self.root / "snapshot.json"

    def put(self, **kwargs):
        key = kwargs.get("key")
        value = kwargs.get("value")
        request_id = kwargs.get("request_id")
        expected_version = kwargs.get("expected_version")
        self._validate_request("put", key, value, request_id, expected_version)
        with StateLock(self.root, exclusive=True):
            state = self._load_state()
            return self._mutate(
                state,
                op="put",
                key=key,
                value=value,
                request_id=request_id,
                expected_version=expected_version,
            )

    def get(self, key: str):
        self._validate_key(key)
        with StateLock(self.root, exclusive=False):
            state = self._load_state()
            keys = state["keys"]
            entry = keys.get(key)
            if entry is None or entry["tombstone"]:
                raise StoreError("NOT_FOUND", "key does not exist")
            return {"key": key, "value": entry["value"], "version": entry["version"]}

    def delete(self, **kwargs):
        key = kwargs.get("key")
        request_id = kwargs.get("request_id")
        expected_version = kwargs.get("expected_version")
        self._validate_request("delete", key, None, request_id, expected_version)
        with StateLock(self.root, exclusive=True):
            state = self._load_state()
            return self._mutate(
                state,
                op="delete",
                key=key,
                value=None,
                request_id=request_id,
                expected_version=expected_version,
            )

    def list_items(self):
        with StateLock(self.root, exclusive=False):
            state = self._load_state()
            return [
                {"key": key, "value": entry["value"], "version": entry["version"]}
                for key, entry in sorted(state["keys"].items())
                if not entry["tombstone"]
            ]

    def compact(self):
        with StateLock(self.root, exclusive=True):
            state = self._load_state()
            snapshot = {
                "format": 1,
                "last_seq": state["last_seq"],
                "keys": state["keys"],
                "requests": state["requests"],
            }
            raw = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            snapshot_tmp = self.root / "snapshot.json.tmp"
            self._write_fsynced(snapshot_tmp, raw)
            os.replace(str(snapshot_tmp), str(self.snapshot_path))
            self._fsync_directory()

            events_tmp = self.root / "events.log.tmp"
            self._write_fsynced(events_tmp, b"")
            os.replace(str(events_tmp), str(self.events_path))
            self._fsync_directory()
            return {"snapshot_seq": state["last_seq"]}

    def recover(self):
        with StateLock(self.root, exclusive=True):
            state, inspection = self._load_state(allow_tail=True, include_inspection=True)
            del state
            if inspection.tail_boundary is None:
                return {"truncated_bytes": 0}
            removed = inspection.total_bytes - inspection.tail_boundary
            with self.events_path.open("r+b") as handle:
                handle.truncate(inspection.tail_boundary)
                handle.flush()
                os.fsync(handle.fileno())
            return {"truncated_bytes": removed}

    @staticmethod
    def _validate_key(key: object) -> None:
        if not isinstance(key, str) or not key:
            raise StoreError("ARGUMENT_ERROR", "key must be a non-empty string")

    def _validate_request(
        self,
        op: str,
        key: object,
        value: object,
        request_id: object,
        expected_version: object,
    ) -> None:
        self._validate_key(key)
        if not isinstance(request_id, str) or not request_id:
            raise StoreError("ARGUMENT_ERROR", "request_id must be a non-empty string")
        if not _is_int(expected_version) or expected_version < 0:
            raise StoreError("ARGUMENT_ERROR", "expected_version must be a non-negative integer")
        if op == "put" and not isinstance(value, str):
            raise StoreError("ARGUMENT_ERROR", "put value must be a string")

    def _ensure_events_log(self) -> None:
        descriptor = os.open(str(self.events_path), os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(descriptor)

    def _load_state(self, *, allow_tail=False, include_inspection=False):
        self._ensure_events_log()
        state = self._load_snapshot()
        inspection = self._inspect_log()
        previous_log_seq = None

        for index, entry in enumerate(inspection.entries):
            try:
                seq = entry.record["seq"]
                if previous_log_seq is not None and seq != previous_log_seq + 1:
                    raise ValueError("journal seq is not contiguous")
                previous_log_seq = seq
                if seq <= state["last_seq"]:
                    self._validate_stale_record(state, entry.record)
                    continue
                if seq != state["last_seq"] + 1:
                    raise ValueError("journal seq does not continue snapshot")
                self._apply_committed_record(state, entry.record)
            except (KeyError, TypeError, ValueError) as exc:
                is_physical_last = (
                    inspection.tail_boundary is None and index == len(inspection.entries) - 1
                )
                if is_physical_last:
                    inspection = _LogInspection(
                        entries=inspection.entries[:index],
                        tail_boundary=entry.start,
                        total_bytes=inspection.total_bytes,
                    )
                    break
                raise StoreError("CORRUPT_LOG", "journal contains a corrupt non-tail record") from exc

        if inspection.tail_boundary is not None and not allow_tail:
            raise StoreError("RECOVERY_REQUIRED", "journal has a recoverable damaged tail")
        if include_inspection:
            return state, inspection
        return state

    def _inspect_log(self) -> _LogInspection:
        raw = self.events_path.read_bytes()
        if not raw:
            return _LogInspection([], None, 0)
        entries = []
        offset = 0
        tail_boundary = None
        while offset < len(raw):
            newline = raw.find(b"\n", offset)
            if newline < 0:
                tail_boundary = offset
                break
            end = newline + 1
            line = raw[offset:end]
            is_last = end == len(raw)
            try:
                record = decode_record(line)
            except RecordError as exc:
                if is_last:
                    tail_boundary = offset
                    break
                raise StoreError("CORRUPT_LOG", "journal contains a corrupt non-tail record") from exc
            entries.append(_Entry(record=record, start=offset, end=end))
            offset = end
        return _LogInspection(entries, tail_boundary, len(raw))

    def _load_snapshot(self) -> dict[str, object]:
        if not self.snapshot_path.exists():
            return _empty_state()
        try:
            raw = self.snapshot_path.read_bytes()
            decoded = json.loads(raw.decode("utf-8", errors="strict"))
            return self._validate_snapshot(decoded)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
            raise StoreError("CORRUPT_SNAPSHOT", "committed snapshot is corrupt") from exc

    def _validate_snapshot(self, snapshot: object) -> dict[str, object]:
        if not isinstance(snapshot, dict) or set(snapshot) != {"format", "last_seq", "keys", "requests"}:
            raise ValueError("invalid snapshot fields")
        if not _is_int(snapshot["format"]) or snapshot["format"] != 1:
            raise ValueError("unsupported snapshot format")
        last_seq = snapshot["last_seq"]
        if not _is_int(last_seq) or last_seq < 0:
            raise ValueError("invalid snapshot last_seq")
        keys = snapshot["keys"]
        requests = snapshot["requests"]
        if not isinstance(keys, dict) or not isinstance(requests, dict):
            raise ValueError("invalid snapshot maps")

        checked_keys = {}
        for key, entry in keys.items():
            if not isinstance(key, str) or not key or not isinstance(entry, dict):
                raise ValueError("invalid snapshot key entry")
            if set(entry) != {"value", "tombstone", "version"}:
                raise ValueError("invalid snapshot key fields")
            tombstone = entry["tombstone"]
            version = entry["version"]
            value = entry["value"]
            if not isinstance(tombstone, bool):
                raise ValueError("invalid snapshot tombstone")
            if not _is_int(version) or version <= 0 or version > last_seq:
                raise ValueError("invalid snapshot key version")
            if tombstone and value is not None:
                raise ValueError("tombstone snapshot value must be null")
            if not tombstone and not isinstance(value, str):
                raise ValueError("live snapshot value must be a string")
            checked_keys[key] = {"value": value, "tombstone": tombstone, "version": version}

        checked_requests = {}
        for request_id, entry in requests.items():
            if not isinstance(request_id, str) or not request_id or not isinstance(entry, dict):
                raise ValueError("invalid snapshot request entry")
            if set(entry) != {"fingerprint", "result"}:
                raise ValueError("invalid snapshot request fields")
            fingerprint = entry["fingerprint"]
            result = entry["result"]
            if not isinstance(fingerprint, dict) or set(fingerprint) != {
                "op", "key", "value", "expected_version"
            }:
                raise ValueError("invalid request fingerprint")
            self._validate_snapshot_fingerprint(fingerprint)
            if not isinstance(result, dict) or set(result) != {"seq", "key", "version"}:
                raise ValueError("invalid request result")
            if (
                not _is_int(result["seq"])
                or result["seq"] <= 0
                or result["seq"] > last_seq
                or not _is_int(result["version"])
                or result["version"] != result["seq"]
                or result["key"] != fingerprint["key"]
            ):
                raise ValueError("inconsistent request result")
            checked_requests[request_id] = {
                "fingerprint": dict(fingerprint),
                "result": dict(result),
            }

        by_seq = {}
        for request_id, entry in checked_requests.items():
            seq = entry["result"]["seq"]
            if seq in by_seq:
                raise ValueError("duplicate snapshot request seq")
            by_seq[seq] = (request_id, entry)
        if set(by_seq) != set(range(1, last_seq + 1)):
            raise ValueError("snapshot request history is incomplete")

        reconstructed_keys = {}
        for seq in range(1, last_seq + 1):
            _, request = by_seq[seq]
            fingerprint = request["fingerprint"]
            key = fingerprint["key"]
            current = reconstructed_keys.get(key)
            current_version = current["version"] if current is not None else 0
            if fingerprint["expected_version"] != current_version:
                raise ValueError("snapshot request version transition is invalid")
            if fingerprint["op"] == "delete" and current is None:
                raise ValueError("snapshot delete targets an unknown key")
            reconstructed_keys[key] = {
                "value": fingerprint["value"],
                "tombstone": fingerprint["op"] == "delete",
                "version": seq,
            }
        if reconstructed_keys != checked_keys:
            raise ValueError("snapshot key state does not match request history")
        return {"last_seq": last_seq, "keys": checked_keys, "requests": checked_requests}

    @staticmethod
    def _validate_stale_record(state: dict[str, object], record: dict[str, object]) -> None:
        """Accept an old log after snapshot replace only when snapshot proves it was included."""
        prior = state["requests"].get(record["request_id"])
        fingerprint = {
            "op": record["op"],
            "key": record["key"],
            "value": record["value"],
            "expected_version": record["expected_version"],
        }
        if (
            prior is None
            or prior["fingerprint"] != fingerprint
            or prior["result"]["seq"] != record["seq"]
        ):
            raise ValueError("stale journal record is absent from the snapshot")

    @staticmethod
    def _validate_snapshot_fingerprint(fingerprint: dict[str, object]) -> None:
        op = fingerprint["op"]
        key = fingerprint["key"]
        value = fingerprint["value"]
        expected = fingerprint["expected_version"]
        if op not in {"put", "delete"} or not isinstance(key, str) or not key:
            raise ValueError("invalid request fingerprint identity")
        if not _is_int(expected) or expected < 0:
            raise ValueError("invalid request fingerprint version")
        if op == "put" and not isinstance(value, str):
            raise ValueError("invalid put fingerprint value")
        if op == "delete" and value is not None:
            raise ValueError("invalid delete fingerprint value")

    def _mutate(
        self,
        state: dict[str, object],
        *,
        op: str,
        key: str,
        value: Optional[str],
        request_id: str,
        expected_version: int,
    ) -> dict[str, object]:
        fingerprint = {
            "op": op,
            "key": key,
            "value": value,
            "expected_version": expected_version,
        }
        prior = state["requests"].get(request_id)
        if prior is not None:
            if prior["fingerprint"] != fingerprint:
                raise StoreError(
                    "IDEMPOTENCY_CONFLICT", "request_id was already used for different content"
                )
            replay = dict(prior["result"])
            replay["replayed"] = True
            return replay

        current = state["keys"].get(key)
        current_version = current["version"] if current is not None else 0
        if expected_version != current_version:
            raise StoreError(
                "VERSION_CONFLICT",
                "expected_version does not match the key's latest mutation",
            )
        if op == "delete" and current is None:
            raise StoreError("NOT_FOUND", "key has never existed")

        seq = state["last_seq"] + 1
        record = {
            "seq": seq,
            "op": op,
            "key": key,
            "value": value,
            "request_id": request_id,
            "expected_version": expected_version,
        }
        encoded = encode_record(record)
        with self.events_path.open("ab") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())

        self._apply_committed_record(state, record)
        return {"seq": seq, "key": key, "version": seq, "replayed": False}

    @staticmethod
    def _apply_committed_record(state: dict[str, object], record: dict[str, object]) -> None:
        seq = record["seq"]
        key = record["key"]
        request_id = record["request_id"]
        expected = record["expected_version"]
        if request_id in state["requests"]:
            raise ValueError("duplicate committed request_id")
        current = state["keys"].get(key)
        current_version = current["version"] if current is not None else 0
        if expected != current_version:
            raise ValueError("committed expected_version mismatch")
        if record["op"] == "delete" and current is None:
            raise ValueError("committed delete targets unknown key")
        state["keys"][key] = {
            "value": record["value"],
            "tombstone": record["op"] == "delete",
            "version": seq,
        }
        fingerprint = {
            "op": record["op"],
            "key": key,
            "value": record["value"],
            "expected_version": expected,
        }
        state["requests"][request_id] = {
            "fingerprint": fingerprint,
            "result": {"seq": seq, "key": key, "version": seq},
        }
        state["last_seq"] = seq

    @staticmethod
    def _write_fsynced(path: Path, raw: bytes) -> None:
        with path.open("wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())

    def _fsync_directory(self) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(str(self.root), flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
