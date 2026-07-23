"""Crash-consistent journal store."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from .locking import StateLock
    from .record import RecordError, decode_record, encode_record
except ImportError:  # Direct `python fixture/backend/cli.py` execution.
    from locking import StateLock
    from record import RecordError, decode_record, encode_record


class StoreError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class _State:
    last_seq: int
    items: dict[str, dict[str, object]]
    requests: dict[str, dict[str, object]]


@dataclass
class _Loaded:
    state: _State
    valid_end: int
    total_bytes: int
    has_recoverable_tail: bool


_FINGERPRINT_FIELDS = frozenset({"op", "key", "value", "expected_version"})
_RESULT_FIELDS = frozenset({"seq", "key", "version", "replayed"})
_ITEM_FIELDS = frozenset({"value", "version", "tombstone"})
_SNAPSHOT_FIELDS = frozenset({"format", "last_seq", "items", "requests"})


class JournalStore:
    def __init__(self, root) -> None:
        self.root = Path(root)
        self.events_path = self.root / "events.log"
        self.snapshot_path = self.root / "snapshot.json"

    @staticmethod
    def _is_int(value: object, *, minimum: int) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value >= minimum

    @classmethod
    def _fingerprint(cls, op: str, key: str, value: object, expected_version: int) -> dict[str, object]:
        return {
            "op": op,
            "key": key,
            "value": value,
            "expected_version": expected_version,
        }

    @staticmethod
    def _error(code: str, message: str) -> StoreError:
        return StoreError(code, message)

    @staticmethod
    def _empty_state() -> _State:
        return _State(last_seq=0, items={}, requests={})

    def _ensure_events_log(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.events_path, "ab"):
            pass

    def _snapshot_error(self, message: str) -> StoreError:
        return self._error("CORRUPT_SNAPSHOT", message)

    def _read_snapshot(self) -> _State:
        if not self.snapshot_path.exists():
            return self._empty_state()
        try:
            raw = self.snapshot_path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise self._snapshot_error("snapshot.json is malformed") from exc
        if not isinstance(value, dict) or set(value) != _SNAPSHOT_FIELDS:
            raise self._snapshot_error("snapshot.json has an invalid schema")
        if value.get("format") != 1 or not self._is_int(value.get("last_seq"), minimum=0):
            raise self._snapshot_error("snapshot.json has invalid metadata")
        raw_items = value.get("items")
        raw_requests = value.get("requests")
        if not isinstance(raw_items, dict) or not isinstance(raw_requests, dict):
            raise self._snapshot_error("snapshot.json has invalid indexes")

        items: dict[str, dict[str, object]] = {}
        for key, item in raw_items.items():
            if not isinstance(key, str) or not isinstance(item, dict) or set(item) != _ITEM_FIELDS:
                raise self._snapshot_error("snapshot.json has an invalid item")
            version = item.get("version")
            tombstone = item.get("tombstone")
            item_value = item.get("value")
            if not self._is_int(version, minimum=1) or version > value["last_seq"]:
                raise self._snapshot_error("snapshot.json has an invalid item version")
            if not isinstance(tombstone, bool):
                raise self._snapshot_error("snapshot.json has an invalid tombstone")
            if tombstone and item_value is not None:
                raise self._snapshot_error("snapshot tombstone has a value")
            if not tombstone and not isinstance(item_value, str):
                raise self._snapshot_error("snapshot live item lacks a string value")
            items[key] = {"value": item_value, "version": version, "tombstone": tombstone}

        requests: dict[str, dict[str, object]] = {}
        for request_id, request in raw_requests.items():
            if not isinstance(request_id, str) or not isinstance(request, dict):
                raise self._snapshot_error("snapshot.json has an invalid request")
            if set(request) != {"fingerprint", "result"}:
                raise self._snapshot_error("snapshot request has an invalid schema")
            fingerprint = request["fingerprint"]
            result = request["result"]
            if not isinstance(fingerprint, dict) or set(fingerprint) != _FINGERPRINT_FIELDS:
                raise self._snapshot_error("snapshot request fingerprint is invalid")
            if not isinstance(result, dict) or set(result) != _RESULT_FIELDS:
                raise self._snapshot_error("snapshot request result is invalid")
            if (
                fingerprint.get("op") not in {"put", "delete"}
                or not isinstance(fingerprint.get("key"), str)
                or not self._is_int(fingerprint.get("expected_version"), minimum=0)
            ):
                raise self._snapshot_error("snapshot request fingerprint is invalid")
            if fingerprint["op"] == "put" and not isinstance(fingerprint.get("value"), str):
                raise self._snapshot_error("snapshot put fingerprint lacks a string value")
            if fingerprint["op"] == "delete" and fingerprint.get("value") is not None:
                raise self._snapshot_error("snapshot delete fingerprint has a value")
            if (
                not self._is_int(result.get("seq"), minimum=1)
                or not isinstance(result.get("key"), str)
                or not self._is_int(result.get("version"), minimum=1)
                or result.get("replayed") is not False
                or result["seq"] != result["version"]
                or result["seq"] > value["last_seq"]
                or result["key"] != fingerprint["key"]
            ):
                raise self._snapshot_error("snapshot request result is invalid")
            requests[request_id] = {
                "fingerprint": dict(fingerprint),
                "result": dict(result),
            }

        requests_by_seq: dict[int, dict[str, object]] = {}
        for request in requests.values():
            result = request["result"]
            assert isinstance(result, dict)
            seq = result["seq"]
            assert isinstance(seq, int)
            if seq in requests_by_seq:
                raise self._snapshot_error("snapshot.json has duplicate request sequences")
            requests_by_seq[seq] = request
        if set(requests_by_seq) != set(range(1, value["last_seq"] + 1)):
            raise self._snapshot_error("snapshot.json is missing committed request metadata")
        for key, item in items.items():
            version = item["version"]
            assert isinstance(version, int)
            request = requests_by_seq.get(version)
            if request is None:
                raise self._snapshot_error("snapshot item lacks its mutation request")
            fingerprint = request["fingerprint"]
            assert isinstance(fingerprint, dict)
            expected_op = "delete" if item["tombstone"] else "put"
            if (
                fingerprint["key"] != key
                or fingerprint["op"] != expected_op
                or fingerprint["value"] != item["value"]
            ):
                raise self._snapshot_error("snapshot item disagrees with its mutation request")
        return _State(last_seq=value["last_seq"], items=items, requests=requests)

    @staticmethod
    def _line_segments(raw: bytes):
        """Yield (payload, end_offset, terminated) for every physical record."""
        if not raw:
            return
        start = 0
        for index, byte in enumerate(raw):
            if byte == 10:
                yield raw[start:index], index + 1, True
                start = index + 1
        if start < len(raw):
            yield raw[start:], len(raw), False

    def _apply_record(self, state: _State, record: dict[str, object]) -> None:
        seq = record["seq"]
        key = record["key"]
        op = record["op"]
        expected_version = record["expected_version"]
        request_id = record["request_id"]
        assert isinstance(seq, int) and isinstance(key, str) and isinstance(op, str)
        assert isinstance(expected_version, int) and isinstance(request_id, str)
        if request_id in state.requests:
            raise ValueError("request_id appears more than once")
        current = state.items.get(key)
        current_version = 0 if current is None else current["version"]
        if expected_version != current_version:
            raise ValueError("record expected_version does not match reconstructed state")
        if op == "delete" and current is None:
            raise ValueError("delete record targets a key that never appeared")
        state.items[key] = {
            "value": record["value"],
            "version": seq,
            "tombstone": op == "delete",
        }
        state.requests[request_id] = {
            "fingerprint": self._fingerprint(op, key, record["value"], expected_version),
            "result": {"seq": seq, "key": key, "version": seq, "replayed": False},
        }
        state.last_seq = seq

    def _load_state(self, *, allow_recoverable_tail: bool) -> _Loaded:
        state = self._read_snapshot()
        snapshot_seq = state.last_seq
        self._ensure_events_log()
        try:
            raw = self.events_path.read_bytes()
        except OSError as exc:
            raise self._error("CORRUPT_LOG", "events.log cannot be read") from exc

        valid_end = 0
        previous_log_seq = 0
        segments = list(self._line_segments(raw))
        for index, (line, end_offset, terminated) in enumerate(segments):
            is_last = index == len(segments) - 1
            if not terminated:
                if is_last:
                    if allow_recoverable_tail:
                        return _Loaded(state, valid_end, len(raw), True)
                    raise self._error("RECOVERY_REQUIRED", "events.log has a truncated final record")
                raise self._error("CORRUPT_LOG", "events.log has an unterminated non-final record")
            try:
                record = decode_record(line)
                seq = record["seq"]
                assert isinstance(seq, int)
                if seq <= previous_log_seq:
                    raise ValueError("log sequence is not strictly increasing")
                previous_log_seq = seq
                # A crash between compaction's two replaces can leave a valid
                # prefix already represented by the committed snapshot.
                if seq > snapshot_seq:
                    self._apply_record(state, record)
            except (RecordError, ValueError, AssertionError) as exc:
                if is_last:
                    if allow_recoverable_tail:
                        return _Loaded(state, valid_end, len(raw), True)
                    raise self._error("RECOVERY_REQUIRED", "events.log has an invalid final record") from exc
                raise self._error("CORRUPT_LOG", "events.log has an invalid non-final record") from exc
            valid_end = end_offset
        return _Loaded(state, valid_end, len(raw), False)

    @staticmethod
    def _response(result: dict[str, object], *, replayed: bool) -> dict[str, object]:
        response = dict(result)
        response["replayed"] = replayed
        return response

    def _append(self, record: dict[str, object]) -> None:
        encoded = encode_record(record)
        with open(self.events_path, "ab") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())

    def _mutate(
        self,
        *,
        op: str,
        key: str,
        value: object,
        request_id: str,
        expected_version: int,
    ) -> dict[str, object]:
        if not isinstance(key, str) or not isinstance(request_id, str):
            raise self._error("INVALID_ARGUMENT", "key and request_id must be strings")
        if not self._is_int(expected_version, minimum=0):
            raise self._error("INVALID_ARGUMENT", "expected_version must be a non-negative integer")
        if op == "put" and not isinstance(value, str):
            raise self._error("INVALID_ARGUMENT", "put value must be a string")
        if op == "delete" and value is not None:
            raise self._error("INVALID_ARGUMENT", "delete value must be null")

        with StateLock(self.root, exclusive=True):
            state = self._load_state(allow_recoverable_tail=False).state
            fingerprint = self._fingerprint(op, key, value, expected_version)
            existing = state.requests.get(request_id)
            if existing is not None:
                if existing["fingerprint"] == fingerprint:
                    result = existing["result"]
                    assert isinstance(result, dict)
                    return self._response(result, replayed=True)
                raise self._error("IDEMPOTENCY_CONFLICT", "request_id has different request content")

            current = state.items.get(key)
            current_version = 0 if current is None else current["version"]
            if expected_version != current_version:
                raise self._error("VERSION_CONFLICT", "expected_version does not match the current version")
            if op == "delete" and current is None:
                raise self._error("NOT_FOUND", "key has never appeared")
            next_seq = state.last_seq + 1
            record = {
                "seq": next_seq,
                "op": op,
                "key": key,
                "value": value,
                "request_id": request_id,
                "expected_version": expected_version,
            }
            self._append(record)
            return {"seq": next_seq, "key": key, "version": next_seq, "replayed": False}

    def put(self, **kwargs):
        return self._mutate(op="put", **kwargs)

    def get(self, key: str):
        if not isinstance(key, str):
            raise self._error("INVALID_ARGUMENT", "key must be a string")
        with StateLock(self.root, exclusive=False):
            state = self._load_state(allow_recoverable_tail=False).state
            item = state.items.get(key)
            if item is None or item["tombstone"]:
                raise self._error("NOT_FOUND", "key does not have a live value")
            return {"key": key, "value": item["value"], "version": item["version"]}

    def delete(self, **kwargs):
        return self._mutate(op="delete", value=None, **kwargs)

    def list_items(self):
        with StateLock(self.root, exclusive=False):
            state = self._load_state(allow_recoverable_tail=False).state
            items = []
            for key in sorted(state.items):
                item = state.items[key]
                if not item["tombstone"]:
                    items.append({"key": key, "value": item["value"], "version": item["version"]})
            return {"items": items}

    def _fsync_directory(self) -> None:
        descriptor = os.open(self.root, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _write_replace(self, target: Path, payload: bytes) -> None:
        temporary = target.with_name(target.name + ".tmp")
        with open(temporary, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        self._fsync_directory()

    @staticmethod
    def _snapshot_payload(state: _State) -> bytes:
        snapshot = {
            "format": 1,
            "last_seq": state.last_seq,
            "items": state.items,
            "requests": state.requests,
        }
        return json.dumps(
            snapshot,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    def compact(self):
        with StateLock(self.root, exclusive=True):
            state = self._load_state(allow_recoverable_tail=False).state
            self._write_replace(self.snapshot_path, self._snapshot_payload(state))
            self._write_replace(self.events_path, b"")
            return {"snapshot_seq": state.last_seq}

    def recover(self):
        with StateLock(self.root, exclusive=True):
            loaded = self._load_state(allow_recoverable_tail=True)
            if not loaded.has_recoverable_tail:
                return {"truncated_bytes": 0}
            truncated_bytes = loaded.total_bytes - loaded.valid_end
            with open(self.events_path, "r+b") as handle:
                handle.truncate(loaded.valid_end)
                handle.flush()
                os.fsync(handle.fileno())
            return {"truncated_bytes": truncated_bytes}
