"""Crash-consistent journal store used to validate the hidden evaluator."""

from __future__ import annotations

import json
import os
from pathlib import Path

from locking import StateLock
from record import RecordError, decode_record, encode_record


class StoreError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _fingerprint(op: str, key: str, value: str | None, expected_version: int) -> dict[str, object]:
    return {"op": op, "key": key, "value": value, "expected_version": expected_version}


def _empty_state() -> dict[str, object]:
    return {"last_seq": 0, "entries": {}, "requests": {}}


class JournalStore:
    def __init__(self, root) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def log_path(self) -> Path:
        return self.root / "events.log"

    def _snapshot(self) -> dict[str, object]:
        path = self.root / "snapshot.json"
        if not path.exists():
            return _empty_state()
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("schema_version") != 1:
                raise ValueError("schema")
            last_seq = value["last_seq"]
            entries = value["entries"]
            requests = value["requests"]
            if not isinstance(last_seq, int) or isinstance(last_seq, bool) or last_seq < 0:
                raise ValueError("last_seq")
            if not isinstance(entries, dict) or not isinstance(requests, dict):
                raise ValueError("maps")
            for key, item in entries.items():
                if not isinstance(key, str) or not isinstance(item, dict):
                    raise ValueError("entry")
                if set(item) != {"value", "version", "deleted"}:
                    raise ValueError("entry fields")
                if not isinstance(item["version"], int) or not isinstance(item["deleted"], bool):
                    raise ValueError("entry values")
                if item["deleted"] and item["value"] is not None:
                    raise ValueError("tombstone")
                if not item["deleted"] and not isinstance(item["value"], str):
                    raise ValueError("value")
            for request_id, item in requests.items():
                if not isinstance(request_id, str) or not isinstance(item, dict):
                    raise ValueError("request")
                if set(item) != {"fingerprint", "result"}:
                    raise ValueError("request fields")
                if not isinstance(item["fingerprint"], dict) or not isinstance(item["result"], dict):
                    raise ValueError("request values")
            return {"last_seq": last_seq, "entries": entries, "requests": requests}
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            raise StoreError("CORRUPT_SNAPSHOT", f"invalid committed snapshot: {exc}") from exc

    def _apply(self, state: dict[str, object], record: dict[str, object]) -> None:
        entries = state["entries"]
        requests = state["requests"]
        assert isinstance(entries, dict) and isinstance(requests, dict)
        seq = record["seq"]
        assert isinstance(seq, int)
        if seq != state["last_seq"] + 1:
            raise StoreError("CORRUPT_LOG", "non-contiguous seq")
        key = record["key"]
        request_id = record["request_id"]
        assert isinstance(key, str) and isinstance(request_id, str)
        current = entries.get(key)
        current_version = current["version"] if isinstance(current, dict) else 0
        if record["expected_version"] != current_version:
            raise StoreError("CORRUPT_LOG", "record expected_version mismatch")
        fingerprint = _fingerprint(str(record["op"]), key, record["value"] if isinstance(record["value"], str) else None, int(record["expected_version"]))
        if request_id in requests:
            raise StoreError("CORRUPT_LOG", "duplicate request_id in log")
        deleted = record["op"] == "delete"
        entries[key] = {"value": None if deleted else record["value"], "version": seq, "deleted": deleted}
        result = {"ok": True, "seq": seq, "key": key, "version": seq, "replayed": False}
        requests[request_id] = {"fingerprint": fingerprint, "result": result}
        state["last_seq"] = seq

    def _load(self, *, permit_tail: bool = False) -> tuple[dict[str, object], int, int]:
        state = self._snapshot()
        self.log_path.touch(exist_ok=True)
        raw = self.log_path.read_bytes()
        offset = 0
        valid_offset = 0
        lines = raw.splitlines(keepends=True)
        for index, line in enumerate(lines):
            final = index == len(lines) - 1
            if not line.endswith(b"\n"):
                if final:
                    break
                raise StoreError("CORRUPT_LOG", "unterminated middle record")
            try:
                record = decode_record(line[:-1])
                seq = int(record["seq"])
                if seq > int(state["last_seq"]):
                    self._apply(state, record)
            except (RecordError, StoreError, ValueError, TypeError) as exc:
                if final:
                    break
                if isinstance(exc, StoreError):
                    raise
                raise StoreError("CORRUPT_LOG", f"invalid middle record: {exc}") from exc
            offset += len(line)
            valid_offset = offset
        tail_bytes = len(raw) - valid_offset
        if tail_bytes and not permit_tail:
            raise StoreError("RECOVERY_REQUIRED", "recoverable invalid tail")
        return state, valid_offset, tail_bytes

    def _mutate(self, *, op: str, key: str, value: str | None, request_id: str, expected_version: int) -> dict[str, object]:
        with StateLock(self.root, exclusive=True):
            state, _offset, _tail = self._load()
            entries = state["entries"]
            requests = state["requests"]
            assert isinstance(entries, dict) and isinstance(requests, dict)
            fingerprint = _fingerprint(op, key, value, expected_version)
            prior = requests.get(request_id)
            if isinstance(prior, dict):
                if prior.get("fingerprint") != fingerprint:
                    raise StoreError("IDEMPOTENCY_CONFLICT", "request_id already used with different request")
                result = dict(prior["result"])
                result["replayed"] = True
                return result
            current = entries.get(key)
            current_version = current["version"] if isinstance(current, dict) else 0
            if current_version != expected_version:
                raise StoreError("VERSION_CONFLICT", f"expected {expected_version}, current {current_version}")
            if op == "delete" and (not isinstance(current, dict) or current.get("deleted") is True):
                raise StoreError("NOT_FOUND", "key not found")
            seq = int(state["last_seq"]) + 1
            record = {"seq": seq, "op": op, "key": key, "value": value, "request_id": request_id, "expected_version": expected_version}
            encoded = encode_record(record)
            with self.log_path.open("ab") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            return {"ok": True, "seq": seq, "key": key, "version": seq, "replayed": False}

    def put(self, *, key: str, value: str, request_id: str, expected_version: int):
        return self._mutate(op="put", key=key, value=value, request_id=request_id, expected_version=expected_version)

    def delete(self, *, key: str, request_id: str, expected_version: int):
        return self._mutate(op="delete", key=key, value=None, request_id=request_id, expected_version=expected_version)

    def get(self, key: str):
        with StateLock(self.root, exclusive=False):
            state, _offset, _tail = self._load()
            entries = state["entries"]
            assert isinstance(entries, dict)
            item = entries.get(key)
            if not isinstance(item, dict) or item.get("deleted") is True:
                raise StoreError("NOT_FOUND", "key not found")
            return {"ok": True, "key": key, "value": item["value"], "version": item["version"]}

    def list_items(self):
        with StateLock(self.root, exclusive=False):
            state, _offset, _tail = self._load()
            entries = state["entries"]
            assert isinstance(entries, dict)
            items = [{"key": key, "value": item["value"], "version": item["version"]} for key, item in sorted(entries.items()) if isinstance(item, dict) and not item["deleted"]]
            return {"ok": True, "items": items}

    def _atomic_replace(self, path: Path, data: bytes) -> None:
        temp = path.with_name(path.name + ".tmp")
        with temp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        descriptor = os.open(self.root, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def compact(self):
        with StateLock(self.root, exclusive=True):
            state, _offset, _tail = self._load()
            snapshot = {"schema_version": 1, **state}
            raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            self._atomic_replace(self.root / "snapshot.json", raw)
            self._atomic_replace(self.log_path, b"")
            return {"ok": True, "snapshot_seq": state["last_seq"]}

    def recover(self):
        with StateLock(self.root, exclusive=True):
            _state, valid_offset, tail_bytes = self._load(permit_tail=True)
            if tail_bytes:
                with self.log_path.open("r+b") as handle:
                    handle.truncate(valid_offset)
                    handle.flush()
                    os.fsync(handle.fileno())
            return {"ok": True, "truncated_bytes": tail_bytes}

