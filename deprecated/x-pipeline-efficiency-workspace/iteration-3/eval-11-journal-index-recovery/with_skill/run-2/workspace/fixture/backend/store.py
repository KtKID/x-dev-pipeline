"""Crash-consistent snapshot and journal store."""

from __future__ import annotations

import json
import os
from pathlib import Path

if __package__:
    from .locking import StateLock
    from .record import RecordError, decode_record, encode_record
else:
    from locking import StateLock
    from record import RecordError, decode_record, encode_record


class StoreError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _TailDamage(Exception):
    def __init__(self, truncate_to: int, total_bytes: int, message: str) -> None:
        super().__init__(message)
        self.truncate_to = truncate_to
        self.total_bytes = total_bytes


def _is_int(value: object) -> bool:
    return type(value) is int


def _empty_state() -> dict[str, object]:
    return {"last_seq": 0, "keys": {}, "requests": {}}


def _fingerprint(op: str, key: str, value: object, expected_version: int) -> dict[str, object]:
    return {
        "op": op,
        "key": key,
        "value": value,
        "expected_version": expected_version,
    }


def _json_object_without_duplicates(pairs):
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


class JournalStore:
    def __init__(self, root) -> None:
        self.root = Path(root)
        self.log_path = self.root / "events.log"
        self.snapshot_path = self.root / "snapshot.json"

    def put(self, **kwargs):
        key, value, request_id, expected_version = self._mutation_arguments("put", kwargs)
        with StateLock(self.root, exclusive=True):
            self._ensure_log()
            state = self._load_locked()
            return self._mutate_locked(
                state,
                op="put",
                key=key,
                value=value,
                request_id=request_id,
                expected_version=expected_version,
            )

    def get(self, key: str):
        if not isinstance(key, str):
            raise StoreError("INVALID_ARGUMENT", "key must be a string")
        with StateLock(self.root, exclusive=False):
            self._ensure_log()
            state = self._load_locked()
            entry = state["keys"].get(key)
            if entry is None or entry["tombstone"]:
                raise StoreError("NOT_FOUND", f"key {key!r} does not exist")
            return {"key": key, "value": entry["value"], "version": entry["version"]}

    def delete(self, **kwargs):
        key, value, request_id, expected_version = self._mutation_arguments("delete", kwargs)
        with StateLock(self.root, exclusive=True):
            self._ensure_log()
            state = self._load_locked()
            return self._mutate_locked(
                state,
                op="delete",
                key=key,
                value=value,
                request_id=request_id,
                expected_version=expected_version,
            )

    def list_items(self):
        with StateLock(self.root, exclusive=False):
            self._ensure_log()
            state = self._load_locked()
            return [
                {"key": key, "value": entry["value"], "version": entry["version"]}
                for key, entry in sorted(state["keys"].items())
                if not entry["tombstone"]
            ]

    def compact(self):
        with StateLock(self.root, exclusive=True):
            self._ensure_log()
            state = self._load_locked()
            snapshot_bytes = self._encode_snapshot(state)
            self._atomic_replace("snapshot.json.tmp", self.snapshot_path, snapshot_bytes)
            self._atomic_replace("events.log.tmp", self.log_path, b"")
            return {"snapshot_seq": state["last_seq"]}

    def recover(self):
        with StateLock(self.root, exclusive=True):
            self._ensure_log()
            state = self._load_snapshot()
            data = self.log_path.read_bytes()
            try:
                self._scan_log(state, data)
            except _TailDamage as damage:
                with self.log_path.open("r+b") as handle:
                    handle.truncate(damage.truncate_to)
                    handle.flush()
                    os.fsync(handle.fileno())
                return {"truncated_bytes": damage.total_bytes - damage.truncate_to}
            return {"truncated_bytes": 0}

    def _ensure_log(self) -> None:
        with self.log_path.open("ab"):
            pass

    def _mutation_arguments(self, op: str, kwargs: dict[str, object]):
        expected_fields = {"key", "request_id", "expected_version"}
        if op == "put":
            expected_fields.add("value")
        if set(kwargs) != expected_fields:
            raise StoreError("INVALID_ARGUMENT", f"{op} arguments do not match the public contract")
        key = kwargs["key"]
        request_id = kwargs["request_id"]
        expected_version = kwargs["expected_version"]
        value = kwargs.get("value")
        if not isinstance(key, str):
            raise StoreError("INVALID_ARGUMENT", "key must be a string")
        if not isinstance(request_id, str):
            raise StoreError("INVALID_ARGUMENT", "request_id must be a string")
        if not _is_int(expected_version) or expected_version < 0:
            raise StoreError("INVALID_ARGUMENT", "expected_version must be a non-negative integer")
        if op == "put" and not isinstance(value, str):
            raise StoreError("INVALID_ARGUMENT", "put value must be a string")
        return key, value, request_id, expected_version

    def _load_locked(self) -> dict[str, object]:
        state = self._load_snapshot()
        data = self.log_path.read_bytes()
        try:
            return self._scan_log(state, data)
        except _TailDamage as damage:
            raise StoreError(
                "RECOVERY_REQUIRED",
                f"journal tail is incomplete or invalid at byte {damage.truncate_to}",
            ) from damage

    def _load_snapshot(self) -> dict[str, object]:
        if not self.snapshot_path.exists():
            return _empty_state()
        try:
            raw = self.snapshot_path.read_bytes()
            decoded = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_json_object_without_duplicates,
            )
            return self._validate_snapshot(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
            raise StoreError("CORRUPT_SNAPSHOT", "snapshot.json is invalid") from exc

    def _validate_snapshot(self, decoded: object) -> dict[str, object]:
        if not isinstance(decoded, dict) or set(decoded) != {"format_version", "last_seq", "keys", "requests"}:
            raise ValueError("snapshot fields do not match schema")
        if decoded["format_version"] != 1 or not _is_int(decoded["format_version"]):
            raise ValueError("unsupported snapshot format")
        last_seq = decoded["last_seq"]
        keys = decoded["keys"]
        requests = decoded["requests"]
        if not _is_int(last_seq) or last_seq < 0:
            raise ValueError("invalid snapshot last_seq")
        if not isinstance(keys, dict) or not isinstance(requests, dict):
            raise ValueError("snapshot keys and requests must be objects")

        normalized_keys: dict[str, dict[str, object]] = {}
        for key, entry in keys.items():
            if not isinstance(key, str) or not isinstance(entry, dict):
                raise ValueError("invalid snapshot key entry")
            if set(entry) != {"value", "tombstone", "version"}:
                raise ValueError("snapshot key entry fields do not match schema")
            tombstone = entry["tombstone"]
            value = entry["value"]
            version = entry["version"]
            if type(tombstone) is not bool:
                raise ValueError("tombstone must be boolean")
            if tombstone and value is not None:
                raise ValueError("tombstone value must be null")
            if not tombstone and not isinstance(value, str):
                raise ValueError("live value must be a string")
            if not _is_int(version) or version <= 0 or version > last_seq:
                raise ValueError("snapshot key version is out of range")
            normalized_keys[key] = {"value": value, "tombstone": tombstone, "version": version}

        normalized_requests: dict[str, dict[str, object]] = {}
        history: dict[int, tuple[str, dict[str, object], dict[str, object]]] = {}
        for request_id, entry in requests.items():
            if not isinstance(request_id, str) or not isinstance(entry, dict):
                raise ValueError("invalid snapshot request entry")
            if set(entry) != {"fingerprint", "result"}:
                raise ValueError("snapshot request fields do not match schema")
            fingerprint = self._validate_snapshot_fingerprint(entry["fingerprint"])
            result = entry["result"]
            if not isinstance(result, dict) or set(result) != {"seq", "key", "version"}:
                raise ValueError("snapshot result fields do not match schema")
            seq = result["seq"]
            version = result["version"]
            result_key = result["key"]
            if not _is_int(seq) or not _is_int(version) or seq <= 0 or seq != version:
                raise ValueError("snapshot result seq/version is invalid")
            if not isinstance(result_key, str) or result_key != fingerprint["key"]:
                raise ValueError("snapshot result key does not match fingerprint")
            if seq in history:
                raise ValueError("snapshot contains duplicate sequence")
            normalized_result = {"seq": seq, "key": result_key, "version": version}
            normalized_entry = {"fingerprint": fingerprint, "result": normalized_result}
            normalized_requests[request_id] = normalized_entry
            history[seq] = (request_id, fingerprint, normalized_result)

        if set(history) != set(range(1, last_seq + 1)):
            raise ValueError("snapshot request history does not cover last_seq")
        simulated_keys: dict[str, dict[str, object]] = {}
        for seq in range(1, last_seq + 1):
            _, fingerprint, _ = history[seq]
            key = fingerprint["key"]
            current = simulated_keys.get(key)
            current_version = current["version"] if current is not None else 0
            if fingerprint["expected_version"] != current_version:
                raise ValueError("snapshot request history has a version discontinuity")
            if fingerprint["op"] == "delete":
                if current is None or current["tombstone"]:
                    raise ValueError("snapshot history deletes a missing key")
                simulated_keys[key] = {"value": None, "tombstone": True, "version": seq}
            else:
                simulated_keys[key] = {"value": fingerprint["value"], "tombstone": False, "version": seq}
        if simulated_keys != normalized_keys:
            raise ValueError("snapshot materialized keys do not match request history")
        return {"last_seq": last_seq, "keys": normalized_keys, "requests": normalized_requests}

    def _validate_snapshot_fingerprint(self, fingerprint: object) -> dict[str, object]:
        if not isinstance(fingerprint, dict) or set(fingerprint) != {"op", "key", "value", "expected_version"}:
            raise ValueError("snapshot fingerprint fields do not match schema")
        op = fingerprint["op"]
        key = fingerprint["key"]
        value = fingerprint["value"]
        expected_version = fingerprint["expected_version"]
        if op not in {"put", "delete"} or not isinstance(key, str):
            raise ValueError("snapshot fingerprint operation or key is invalid")
        if not _is_int(expected_version) or expected_version < 0:
            raise ValueError("snapshot expected_version is invalid")
        if op == "put" and not isinstance(value, str):
            raise ValueError("snapshot put value is invalid")
        if op == "delete" and value is not None:
            raise ValueError("snapshot delete value is invalid")
        return _fingerprint(op, key, value, expected_version)

    def _scan_log(self, state: dict[str, object], data: bytes) -> dict[str, object]:
        records = self._physical_records(data)
        base_last_seq = state["last_seq"]
        previous_log_seq = None
        fresh_started = False

        for index, (offset, raw) in enumerate(records):
            is_last = index == len(records) - 1
            try:
                record = decode_record(raw)
            except RecordError as exc:
                if is_last:
                    raise _TailDamage(offset, len(data), str(exc)) from exc
                raise StoreError("CORRUPT_LOG", f"journal record at byte {offset} is corrupt") from exc

            try:
                seq = record["seq"]
                if previous_log_seq is not None:
                    crosses_snapshot = previous_log_seq <= base_last_seq and seq == base_last_seq + 1
                    if not crosses_snapshot and seq != previous_log_seq + 1:
                        raise ValueError("journal sequences are not contiguous")
                if previous_log_seq is None and seq > base_last_seq and seq != base_last_seq + 1:
                    raise ValueError("journal does not continue snapshot sequence")
                previous_log_seq = seq

                if seq <= base_last_seq:
                    if fresh_started:
                        raise ValueError("snapshot-covered record follows a fresh record")
                    self._validate_stale_record(state, record)
                else:
                    fresh_started = True
                    self._apply_committed_record(state, record)
            except (ValueError, KeyError, TypeError) as exc:
                raise StoreError("CORRUPT_LOG", f"journal record at byte {offset} is corrupt") from exc
        return state

    def _physical_records(self, data: bytes) -> list[tuple[int, bytes]]:
        records: list[tuple[int, bytes]] = []
        offset = 0
        while offset < len(data):
            newline = data.find(b"\n", offset)
            if newline < 0:
                records.append((offset, data[offset:]))
                break
            end = newline + 1
            records.append((offset, data[offset:end]))
            offset = end
        return records

    def _validate_stale_record(self, state: dict[str, object], record: dict[str, object]) -> None:
        request = state["requests"].get(record["request_id"])
        fingerprint = _fingerprint(record["op"], record["key"], record["value"], record["expected_version"])
        expected_result = {"seq": record["seq"], "key": record["key"], "version": record["seq"]}
        if request is None or request["fingerprint"] != fingerprint or request["result"] != expected_result:
            raise ValueError("snapshot-covered journal record disagrees with snapshot history")

    def _apply_committed_record(self, state: dict[str, object], record: dict[str, object]) -> None:
        if record["seq"] != state["last_seq"] + 1:
            raise ValueError("journal seq does not follow current state")
        request_id = record["request_id"]
        if request_id in state["requests"]:
            raise ValueError("journal reuses a committed request_id")
        key = record["key"]
        current = state["keys"].get(key)
        current_version = current["version"] if current is not None else 0
        if record["expected_version"] != current_version:
            raise ValueError("journal expected_version does not match prior state")
        if record["op"] == "delete" and (current is None or current["tombstone"]):
            raise ValueError("journal deletes a missing key")

        seq = record["seq"]
        fingerprint = _fingerprint(record["op"], key, record["value"], record["expected_version"])
        result = {"seq": seq, "key": key, "version": seq}
        state["last_seq"] = seq
        state["keys"][key] = {
            "value": record["value"],
            "tombstone": record["op"] == "delete",
            "version": seq,
        }
        state["requests"][request_id] = {"fingerprint": fingerprint, "result": result}

    def _mutate_locked(
        self,
        state: dict[str, object],
        *,
        op: str,
        key: str,
        value: object,
        request_id: str,
        expected_version: int,
    ) -> dict[str, object]:
        fingerprint = _fingerprint(op, key, value, expected_version)
        prior = state["requests"].get(request_id)
        if prior is not None:
            if prior["fingerprint"] != fingerprint:
                raise StoreError("IDEMPOTENCY_CONFLICT", f"request_id {request_id!r} has different content")
            return {**prior["result"], "replayed": True}

        current = state["keys"].get(key)
        current_version = current["version"] if current is not None else 0
        if expected_version != current_version:
            raise StoreError(
                "VERSION_CONFLICT",
                f"expected version {expected_version}, current version is {current_version}",
            )
        if op == "delete" and (current is None or current["tombstone"]):
            raise StoreError("NOT_FOUND", f"key {key!r} does not exist")

        seq = state["last_seq"] + 1
        record = {
            "op": op,
            "key": key,
            "value": value,
            "request_id": request_id,
            "expected_version": expected_version,
            "seq": seq,
        }
        raw = encode_record(record)
        with self.log_path.open("ab") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())

        result = {"seq": seq, "key": key, "version": seq}
        state["last_seq"] = seq
        state["keys"][key] = {"value": value, "tombstone": op == "delete", "version": seq}
        state["requests"][request_id] = {"fingerprint": fingerprint, "result": result}
        return {**result, "replayed": False}

    def _encode_snapshot(self, state: dict[str, object]) -> bytes:
        snapshot = {
            "format_version": 1,
            "last_seq": state["last_seq"],
            "keys": state["keys"],
            "requests": state["requests"],
        }
        return json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"

    def _atomic_replace(self, temporary_name: str, destination: Path, content: bytes) -> None:
        temporary = self.root / temporary_name
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(destination))
        self._fsync_directory()

    def _fsync_directory(self) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(str(self.root), flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
