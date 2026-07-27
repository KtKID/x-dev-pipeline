"""Crash-consistent journal store."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from locking import StateLock
from record import RecordError, decode_record, encode_record


class StoreError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _RecoverableTail(StoreError):
    def __init__(self, offset: int, total_bytes: int) -> None:
        super().__init__("RECOVERY_REQUIRED", "events.log has an invalid final record")
        self.offset = offset
        self.total_bytes = total_bytes


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _initial_state() -> dict[str, Any]:
    return {"last_seq": 0, "keys": {}, "requests": {}}


def _fingerprint(op: str, key: str, value: Optional[str], expected_version: int) -> dict[str, object]:
    return {
        "op": op,
        "key": key,
        "value": value,
        "expected_version": expected_version,
    }


def _validate_mutation_input(
    op: object,
    key: object,
    value: object,
    request_id: object,
    expected_version: object,
) -> None:
    if op not in {"put", "delete"}:
        raise ValueError("operation must be put or delete")
    if not isinstance(key, str):
        raise ValueError("key must be a string")
    if not isinstance(request_id, str):
        raise ValueError("request_id must be a string")
    if not _is_int(expected_version) or expected_version < 0:
        raise ValueError("expected_version must be a non-negative integer")
    if op == "put" and not isinstance(value, str):
        raise ValueError("put value must be a string")
    if op == "delete" and value is not None:
        raise ValueError("delete value must be null")


class JournalStore:
    def __init__(self, root) -> None:
        self.root = Path(root)
        self.events_path = self.root / "events.log"
        self.snapshot_path = self.root / "snapshot.json"
        self.snapshot_tmp_path = self.root / "snapshot.json.tmp"
        self.events_tmp_path = self.root / "events.log.tmp"
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.events_path.exists():
            self.events_path.touch()

    def _load_snapshot(self) -> dict[str, Any]:
        if not self.snapshot_path.exists():
            return _initial_state()
        try:
            raw = self.snapshot_path.read_bytes()
            decoded = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_json_object_without_duplicates,
            )
            return self._validate_snapshot(decoded)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise StoreError("CORRUPT_SNAPSHOT", "snapshot.json is invalid") from exc

    def _validate_snapshot(self, snapshot: object) -> dict[str, Any]:
        if not isinstance(snapshot, dict) or set(snapshot) != {"last_seq", "keys", "requests"}:
            raise ValueError("snapshot fields are invalid")
        last_seq = snapshot["last_seq"]
        keys = snapshot["keys"]
        requests = snapshot["requests"]
        if not _is_int(last_seq) or last_seq < 0:
            raise ValueError("snapshot last_seq is invalid")
        if not isinstance(keys, dict) or not isinstance(requests, dict):
            raise ValueError("snapshot maps are invalid")

        checked_keys: dict[str, dict[str, object]] = {}
        for key, entry in keys.items():
            if not isinstance(key, str) or not isinstance(entry, dict):
                raise ValueError("snapshot key entry is invalid")
            if set(entry) != {"value", "version"}:
                raise ValueError("snapshot key fields are invalid")
            value = entry["value"]
            version = entry["version"]
            if value is not None and not isinstance(value, str):
                raise ValueError("snapshot key value is invalid")
            if not _is_int(version) or version <= 0 or version > last_seq:
                raise ValueError("snapshot key version is invalid")
            checked_keys[key] = {"value": value, "version": version}

        checked_requests: dict[str, dict[str, dict[str, object]]] = {}
        for request_id, entry in requests.items():
            if not isinstance(request_id, str) or not isinstance(entry, dict):
                raise ValueError("snapshot request entry is invalid")
            if set(entry) != {"fingerprint", "result"}:
                raise ValueError("snapshot request fields are invalid")
            fingerprint = entry["fingerprint"]
            result = entry["result"]
            if not isinstance(fingerprint, dict) or set(fingerprint) != {
                "op",
                "key",
                "value",
                "expected_version",
            }:
                raise ValueError("snapshot request fingerprint is invalid")
            _validate_mutation_input(
                fingerprint["op"],
                fingerprint["key"],
                fingerprint["value"],
                request_id,
                fingerprint["expected_version"],
            )
            if not isinstance(result, dict) or set(result) != {
                "seq",
                "key",
                "version",
                "replayed",
            }:
                raise ValueError("snapshot request result is invalid")
            if (
                not _is_int(result["seq"])
                or result["seq"] <= 0
                or result["seq"] > last_seq
                or not isinstance(result["key"], str)
                or not _is_int(result["version"])
                or result["version"] != result["seq"]
                or result["replayed"] is not False
                or result["key"] != fingerprint["key"]
            ):
                raise ValueError("snapshot request result is invalid")
            checked_requests[request_id] = {
                "fingerprint": dict(fingerprint),
                "result": dict(result),
            }

        if last_seq == 0 and (checked_keys or checked_requests):
            raise ValueError("empty snapshot has state")
        result_by_seq = {
            entry["result"]["seq"]: (request_id, entry)
            for request_id, entry in checked_requests.items()
        }
        if len(checked_requests) != last_seq or set(result_by_seq) != set(range(1, last_seq + 1)):
            raise ValueError("snapshot request history is incomplete")
        expected_keys: dict[str, dict[str, object]] = {}
        for sequence in range(1, last_seq + 1):
            _, entry = result_by_seq[sequence]
            fingerprint = entry["fingerprint"]
            expected_keys[fingerprint["key"]] = {
                "value": fingerprint["value"],
                "version": sequence,
            }
        if checked_keys != expected_keys:
            raise ValueError("snapshot key state does not match request history")
        replayed_state = _initial_state()
        for sequence in range(1, last_seq + 1):
            request_id, entry = result_by_seq[sequence]
            fingerprint = entry["fingerprint"]
            try:
                self._apply_record(
                    replayed_state,
                    {
                        "expected_version": fingerprint["expected_version"],
                        "key": fingerprint["key"],
                        "op": fingerprint["op"],
                        "request_id": request_id,
                        "seq": sequence,
                        "value": fingerprint["value"],
                    },
                )
            except RecordError as exc:
                raise ValueError("snapshot request history has an invalid transition") from exc
        if replayed_state != {
            "last_seq": last_seq,
            "keys": checked_keys,
            "requests": checked_requests,
        }:
            raise ValueError("snapshot state does not match request history")
        return {
            "last_seq": last_seq,
            "keys": checked_keys,
            "requests": checked_requests,
        }

    def _read_journal(self) -> tuple[list[tuple[dict[str, object], int]], int]:
        try:
            raw = self.events_path.read_bytes()
        except FileNotFoundError:
            return [], 0
        if not raw:
            return [], 0

        pieces = raw.split(b"\n")
        has_final_newline = raw.endswith(b"\n")
        complete_bodies = pieces[:-1]
        tail_body = None if has_final_newline else pieces[-1]
        records: list[tuple[dict[str, object], int]] = []
        offset = 0
        for index, body in enumerate(complete_bodies):
            line = body + b"\n"
            try:
                record = decode_record(line)
            except RecordError as exc:
                if index == len(complete_bodies) - 1 and tail_body is None:
                    raise _RecoverableTail(offset, len(raw)) from exc
                raise StoreError("CORRUPT_LOG", "events.log has an invalid record") from exc
            records.append((record, offset))
            offset += len(line)

        if tail_body is not None:
            raise _RecoverableTail(offset, len(raw))
        return records, len(raw)

    def _apply_record(self, state: dict[str, Any], record: dict[str, object]) -> None:
        seq = record["seq"]
        expected_version = record["expected_version"]
        key = record["key"]
        op = record["op"]
        request_id = record["request_id"]
        value = record["value"]
        if not _is_int(seq) or not _is_int(expected_version):
            raise RecordError("record number is invalid")
        if not isinstance(key, str) or not isinstance(op, str) or not isinstance(request_id, str):
            raise RecordError("record fields are invalid")
        if seq != state["last_seq"] + 1:
            raise RecordError("record seq is out of order")
        if request_id in state["requests"]:
            raise RecordError("record request_id repeats")
        current = state["keys"].get(key)
        current_version = 0 if current is None else current["version"]
        if expected_version != current_version:
            raise RecordError("record expected_version conflicts")
        if op == "delete" and (current is None or current["value"] is None):
            raise RecordError("record deletes a missing key")
        if op == "put" and not isinstance(value, str):
            raise RecordError("record put value is invalid")
        if op == "delete" and value is not None:
            raise RecordError("record delete value is invalid")

        result = {"seq": seq, "key": key, "version": seq, "replayed": False}
        state["keys"][key] = {"value": value, "version": seq}
        state["requests"][request_id] = {
            "fingerprint": _fingerprint(op, key, value, expected_version),
            "result": result,
        }
        state["last_seq"] = seq

    def _matches_snapshot_history(
        self,
        record: dict[str, object],
        request_id: str,
        entry: dict[str, dict[str, object]],
    ) -> bool:
        fingerprint = entry["fingerprint"]
        result = entry["result"]
        return (
            record["request_id"] == request_id
            and record["op"] == fingerprint["op"]
            and record["key"] == fingerprint["key"]
            and record["value"] == fingerprint["value"]
            and record["expected_version"] == fingerprint["expected_version"]
            and record["seq"] == result["seq"]
            and record["key"] == result["key"]
            and record["seq"] == result["version"]
        )

    def _load_state(self) -> dict[str, Any]:
        state = self._load_snapshot()
        records, _ = self._read_journal()
        if not records:
            return state

        snapshot_seq = state["last_seq"]
        history_by_seq = {
            entry["result"]["seq"]: (request_id, entry)
            for request_id, entry in state["requests"].items()
        }
        previous_seq: Optional[int] = None
        stale_count = 0
        while stale_count < len(records):
            record, _ = records[stale_count]
            seq = record["seq"]
            if not _is_int(seq) or seq > snapshot_seq:
                break
            history = history_by_seq.get(seq)
            valid_stale_record = (
                history is not None
                and (previous_seq is None or seq == previous_seq + 1)
                and self._matches_snapshot_history(record, history[0], history[1])
            )
            if not valid_stale_record:
                raise StoreError("CORRUPT_LOG", "events.log conflicts with snapshot history")
            previous_seq = seq
            stale_count += 1

        if stale_count and previous_seq != snapshot_seq:
            raise StoreError("CORRUPT_LOG", "events.log has an incomplete stale prefix")

        for index in range(stale_count, len(records)):
            record, _ = records[index]
            try:
                self._apply_record(state, record)
            except RecordError as exc:
                raise StoreError("CORRUPT_LOG", "events.log has an invalid record") from exc
        return state

    def _append_record(self, record: dict[str, object]) -> None:
        encoded = encode_record(record)
        with self.events_path.open("ab") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())

    def _mutate(
        self,
        *,
        op: str,
        key: str,
        value: Optional[str],
        request_id: str,
        expected_version: int,
    ) -> dict[str, object]:
        _validate_mutation_input(op, key, value, request_id, expected_version)
        with StateLock(self.root, exclusive=True):
            state = self._load_state()
            fingerprint = _fingerprint(op, key, value, expected_version)
            saved_request = state["requests"].get(request_id)
            if saved_request is not None:
                if saved_request["fingerprint"] != fingerprint:
                    raise StoreError(
                        "IDEMPOTENCY_CONFLICT",
                        "request_id was already used with different content",
                    )
                replayed = dict(saved_request["result"])
                replayed["replayed"] = True
                return replayed

            current = state["keys"].get(key)
            current_version = 0 if current is None else current["version"]
            if expected_version != current_version:
                raise StoreError("VERSION_CONFLICT", "expected_version does not match")
            if op == "delete" and (current is None or current["value"] is None):
                raise StoreError("NOT_FOUND", "key does not exist")

            seq = state["last_seq"] + 1
            record = {
                "expected_version": expected_version,
                "key": key,
                "op": op,
                "request_id": request_id,
                "seq": seq,
                "value": value,
            }
            self._append_record(record)
            self._apply_record(state, decode_record(encode_record(record)))
            return dict(state["requests"][request_id]["result"])

    def put(self, **kwargs):
        return self._mutate(op="put", **kwargs)

    def get(self, key: str):
        if not isinstance(key, str):
            raise ValueError("key must be a string")
        with StateLock(self.root, exclusive=False):
            state = self._load_state()
            entry = state["keys"].get(key)
            if entry is None or entry["value"] is None:
                raise StoreError("NOT_FOUND", "key does not exist")
            return {"key": key, "value": entry["value"], "version": entry["version"]}

    def delete(self, **kwargs):
        return self._mutate(op="delete", value=None, **kwargs)

    def list_items(self):
        with StateLock(self.root, exclusive=False):
            state = self._load_state()
            return [
                {"key": key, "value": entry["value"], "version": entry["version"]}
                for key, entry in sorted(state["keys"].items())
                if entry["value"] is not None
            ]

    def _write_synced(self, path: Path, data: bytes) -> None:
        with path.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

    def _fsync_root(self) -> None:
        descriptor = os.open(str(self.root), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _snapshot_bytes(self, state: dict[str, Any]) -> bytes:
        return (
            json.dumps(
                state,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )

    def compact(self):
        with StateLock(self.root, exclusive=True):
            state = self._load_state()
            self._write_synced(self.snapshot_tmp_path, self._snapshot_bytes(state))
            os.replace(self.snapshot_tmp_path, self.snapshot_path)
            self._fsync_root()
            self._write_synced(self.events_tmp_path, b"")
            os.replace(self.events_tmp_path, self.events_path)
            self._fsync_root()
            return {"snapshot_seq": state["last_seq"]}

    def recover(self):
        with StateLock(self.root, exclusive=True):
            try:
                self._load_state()
            except _RecoverableTail as tail:
                with self.events_path.open("r+b") as handle:
                    handle.truncate(tail.offset)
                    handle.flush()
                    os.fsync(handle.fileno())
                return {"truncated_bytes": tail.total_bytes - tail.offset}
            return {"truncated_bytes": 0}
