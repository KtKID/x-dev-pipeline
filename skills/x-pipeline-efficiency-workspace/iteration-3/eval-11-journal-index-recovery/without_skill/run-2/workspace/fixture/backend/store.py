"""Crash-consistent journal store. Implement from task contract."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path

try:
    from .locking import StateLock, StateLockError
    from .record import RecordError, decode_record, encode_record
except ImportError:
    from locking import StateLock, StateLockError
    from record import RecordError, decode_record, encode_record


class StoreError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class _State:
    last_seq: int
    keys: dict[str, dict[str, object]]
    requests: dict[str, dict[str, object]]


@dataclass
class _LoadResult:
    state: _State
    valid_log_bytes: int
    total_log_bytes: int
    tail_damaged: bool


def _invalid_argument(message: str) -> StoreError:
    return StoreError("INVALID_ARGUMENT", message)


def _json_with_unique_keys(raw: bytes) -> object:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("not valid UTF-8") from exc

    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(text, object_pairs_hook=reject_duplicates)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("not valid JSON") from exc


def _fingerprint(
    *, op: str, key: str, value: str | None, expected_version: int
) -> dict[str, object]:
    return {
        "expected_version": expected_version,
        "key": key,
        "op": op,
        "value": value,
    }


def _validate_fingerprint(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {
        "expected_version",
        "key",
        "op",
        "value",
    }:
        raise ValueError("invalid request fingerprint fields")
    if type(value["expected_version"]) is not int or value["expected_version"] < 0:
        raise ValueError("invalid request expected_version")
    if type(value["key"]) is not str:
        raise ValueError("invalid request key")
    if value["op"] not in {"put", "delete"}:
        raise ValueError("invalid request op")
    if value["op"] == "put" and type(value["value"]) is not str:
        raise ValueError("invalid put value")
    if value["op"] == "delete" and value["value"] is not None:
        raise ValueError("invalid delete value")
    return dict(value)


class JournalStore:
    def __init__(self, root) -> None:
        self.root = Path(root)

    @property
    def _log_path(self) -> Path:
        return self.root / "events.log"

    @property
    def _snapshot_path(self) -> Path:
        return self.root / "snapshot.json"

    def _ensure_log(self) -> None:
        try:
            with self._log_path.open("ab") as stream:
                stream.flush()
        except OSError as exc:
            raise StoreError("INVALID_ARGUMENT", f"cannot initialize state directory: {exc}") from exc

    def _preflight_snapshot(self) -> None:
        try:
            if self.root.exists() and not self.root.is_dir():
                raise _invalid_argument("state root must be a directory")
        except (OSError, ValueError) as exc:
            raise _invalid_argument(f"invalid state root: {exc}") from exc
        self._load_snapshot()

    @contextmanager
    def _locked(self, *, exclusive: bool):
        try:
            with StateLock(self.root, exclusive=exclusive):
                yield
        except StateLockError as exc:
            raise _invalid_argument(str(exc)) from exc

    def _load_snapshot(self) -> _State:
        if not self._snapshot_path.exists():
            return _State(last_seq=0, keys={}, requests={})
        try:
            raw = self._snapshot_path.read_bytes()
            parsed = _json_with_unique_keys(raw)
            return self._validate_snapshot(parsed)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise StoreError("CORRUPT_SNAPSHOT", f"snapshot is corrupt: {exc}") from exc

    @staticmethod
    def _validate_snapshot(parsed: object) -> _State:
        if not isinstance(parsed, dict) or set(parsed) != {
            "format_version",
            "keys",
            "last_seq",
            "requests",
        }:
            raise ValueError("invalid snapshot fields")
        if type(parsed["format_version"]) is not int or parsed["format_version"] != 1:
            raise ValueError("unsupported snapshot format")
        last_seq = parsed["last_seq"]
        if type(last_seq) is not int or last_seq < 0:
            raise ValueError("invalid snapshot last_seq")
        raw_keys = parsed["keys"]
        raw_requests = parsed["requests"]
        if not isinstance(raw_keys, dict) or not isinstance(raw_requests, dict):
            raise ValueError("keys and requests must be objects")

        keys: dict[str, dict[str, object]] = {}
        key_versions: set[int] = set()
        for key, entry in raw_keys.items():
            if type(key) is not str or not isinstance(entry, dict):
                raise ValueError("invalid key entry")
            if set(entry) != {"tombstone", "value", "version"}:
                raise ValueError("invalid key entry fields")
            tombstone = entry["tombstone"]
            version = entry["version"]
            value = entry["value"]
            if type(tombstone) is not bool:
                raise ValueError("invalid tombstone flag")
            if type(version) is not int or version <= 0 or version > last_seq:
                raise ValueError("invalid key version")
            if version in key_versions:
                raise ValueError("duplicate key version")
            if tombstone and value is not None:
                raise ValueError("tombstone value must be null")
            if not tombstone and type(value) is not str:
                raise ValueError("live value must be a string")
            key_versions.add(version)
            keys[key] = dict(entry)

        requests: dict[str, dict[str, object]] = {}
        request_seqs: set[int] = set()
        requests_by_seq: dict[int, dict[str, object]] = {}
        for request_id, entry in raw_requests.items():
            if type(request_id) is not str or not isinstance(entry, dict):
                raise ValueError("invalid request entry")
            if set(entry) != {"fingerprint", "result"}:
                raise ValueError("invalid request entry fields")
            fingerprint = _validate_fingerprint(entry["fingerprint"])
            result = entry["result"]
            if not isinstance(result, dict) or set(result) != {"key", "seq", "version"}:
                raise ValueError("invalid request result fields")
            if type(result["key"]) is not str or result["key"] != fingerprint["key"]:
                raise ValueError("request result key mismatch")
            if (
                type(result["seq"]) is not int
                or result["seq"] <= 0
                or result["seq"] > last_seq
                or type(result["version"]) is not int
                or result["version"] != result["seq"]
            ):
                raise ValueError("invalid request result version")
            if fingerprint["expected_version"] >= result["seq"]:
                raise ValueError("request expected_version cannot reach result seq")
            if result["seq"] in request_seqs:
                raise ValueError("duplicate request result seq")
            request_seqs.add(result["seq"])
            normalized = {"fingerprint": fingerprint, "result": dict(result)}
            requests[request_id] = normalized
            requests_by_seq[result["seq"]] = normalized

        if request_seqs != set(range(1, last_seq + 1)):
            raise ValueError("request history does not cover every committed seq")
        replayed_keys: dict[str, dict[str, object]] = {}
        for seq in range(1, last_seq + 1):
            request = requests_by_seq[seq]
            fingerprint = request["fingerprint"]
            key = fingerprint["key"]
            current = replayed_keys.get(key)
            current_version = current["version"] if current is not None else 0
            if fingerprint["expected_version"] != current_version:
                raise ValueError("request history has an invalid expected_version")
            if fingerprint["op"] == "delete" and (
                current is None or current["tombstone"] is True
            ):
                raise ValueError("request history deletes a missing value")
            replayed_keys[key] = {
                "tombstone": fingerprint["op"] == "delete",
                "value": fingerprint["value"],
                "version": seq,
            }
        if replayed_keys != keys:
            raise ValueError("key state does not match request history")
        return _State(last_seq=last_seq, keys=keys, requests=requests)

    @staticmethod
    def _physical_records(data: bytes) -> list[tuple[int, bytes]]:
        if not data:
            return []
        parts = data.split(b"\n")
        records: list[tuple[int, bytes]] = []
        offset = 0
        for part in parts[:-1]:
            raw = part + b"\n"
            records.append((offset, raw))
            offset += len(raw)
        if parts[-1]:
            records.append((offset, parts[-1]))
        return records

    @staticmethod
    def _record_matches_snapshot(
        state: _State, record: dict[str, object]
    ) -> bool:
        request = state.requests.get(record["request_id"])
        if request is None:
            return False
        fingerprint = _fingerprint(
            op=record["op"],
            key=record["key"],
            value=record["value"],
            expected_version=record["expected_version"],
        )
        result = {
            "key": record["key"],
            "seq": record["seq"],
            "version": record["seq"],
        }
        return request == {"fingerprint": fingerprint, "result": result}

    @staticmethod
    def _apply_record(state: _State, record: dict[str, object]) -> None:
        if record["seq"] != state.last_seq + 1:
            raise RecordError("record seq is not the next global seq")
        request_id = record["request_id"]
        if request_id in state.requests:
            raise RecordError("request_id is duplicated in the log")
        current = state.keys.get(record["key"])
        current_version = current["version"] if current is not None else 0
        if record["expected_version"] != current_version:
            raise RecordError("record expected_version does not match replay state")
        if record["op"] == "delete" and (
            current is None or current["tombstone"] is True
        ):
            raise RecordError("delete record targets a missing value")

        fingerprint = _fingerprint(
            op=record["op"],
            key=record["key"],
            value=record["value"],
            expected_version=record["expected_version"],
        )
        result = {
            "key": record["key"],
            "seq": record["seq"],
            "version": record["seq"],
        }
        state.last_seq = record["seq"]
        state.keys[record["key"]] = {
            "tombstone": record["op"] == "delete",
            "value": record["value"],
            "version": record["seq"],
        }
        state.requests[request_id] = {
            "fingerprint": fingerprint,
            "result": result,
        }

    def _load(self, *, allow_tail_damage: bool = False) -> _LoadResult:
        state = self._load_snapshot()
        snapshot_seq = state.last_seq
        try:
            data = self._log_path.read_bytes()
        except OSError as exc:
            raise StoreError("CORRUPT_LOG", f"cannot read event log: {exc}") from exc
        records = self._physical_records(data)
        valid_boundary = 0
        previous_overlap_seq: int | None = None
        incremental_started = False
        for index, (offset, raw) in enumerate(records):
            try:
                record = decode_record(raw)
                seq = record["seq"]
                if not incremental_started and seq <= snapshot_seq:
                    if previous_overlap_seq is not None and seq != previous_overlap_seq + 1:
                        raise RecordError("snapshot-overlap records are not contiguous")
                    if not self._record_matches_snapshot(state, record):
                        raise RecordError("snapshot-overlap record does not match snapshot")
                    previous_overlap_seq = seq
                else:
                    incremental_started = True
                    self._apply_record(state, record)
            except (RecordError, KeyError, TypeError, ValueError) as exc:
                is_tail = index == len(records) - 1
                if is_tail and allow_tail_damage:
                    return _LoadResult(
                        state=state,
                        valid_log_bytes=offset,
                        total_log_bytes=len(data),
                        tail_damaged=True,
                    )
                code = "RECOVERY_REQUIRED" if is_tail else "CORRUPT_LOG"
                message = (
                    f"event log has recoverable tail damage at byte {offset}: {exc}"
                    if is_tail
                    else f"event log is corrupt at byte {offset}: {exc}"
                )
                raise StoreError(code, message) from exc
            valid_boundary = offset + len(raw)
        return _LoadResult(
            state=state,
            valid_log_bytes=valid_boundary,
            total_log_bytes=len(data),
            tail_damaged=False,
        )

    @staticmethod
    def _validate_mutation_arguments(
        *, key: object, value: object, request_id: object, expected_version: object, op: str
    ) -> None:
        if type(key) is not str:
            raise _invalid_argument("key must be a string")
        if type(request_id) is not str:
            raise _invalid_argument("request_id must be a string")
        if type(expected_version) is not int or expected_version < 0:
            raise _invalid_argument("expected_version must be a non-negative integer")
        if op == "put" and type(value) is not str:
            raise _invalid_argument("put value must be a string")
        if op == "delete" and value is not None:
            raise _invalid_argument("delete value must be null")

    def _mutate(
        self,
        *,
        op: str,
        key: str,
        value: str | None,
        request_id: str,
        expected_version: int,
    ) -> dict[str, object]:
        self._validate_mutation_arguments(
            key=key,
            value=value,
            request_id=request_id,
            expected_version=expected_version,
            op=op,
        )
        self._preflight_snapshot()
        with self._locked(exclusive=True):
            self._ensure_log()
            state = self._load().state
            fingerprint = _fingerprint(
                op=op,
                key=key,
                value=value,
                expected_version=expected_version,
            )
            existing_request = state.requests.get(request_id)
            if existing_request is not None:
                if existing_request["fingerprint"] != fingerprint:
                    raise StoreError(
                        "IDEMPOTENCY_CONFLICT",
                        f"request_id {request_id!r} was already used for another request",
                    )
                return {**existing_request["result"], "replayed": True}

            current = state.keys.get(key)
            current_version = current["version"] if current is not None else 0
            if expected_version != current_version:
                raise StoreError(
                    "VERSION_CONFLICT",
                    f"key {key!r} has version {current_version}, expected {expected_version}",
                )
            if op == "delete" and (
                current is None or current["tombstone"] is True
            ):
                raise StoreError("NOT_FOUND", f"key {key!r} was not found")

            seq = state.last_seq + 1
            encoded = encode_record(
                {
                    "expected_version": expected_version,
                    "key": key,
                    "op": op,
                    "request_id": request_id,
                    "seq": seq,
                    "value": value,
                }
            )
            try:
                with self._log_path.open("ab") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError as exc:
                raise StoreError("WRITE_FAILED", f"cannot commit event: {exc}") from exc
            return {"seq": seq, "key": key, "version": seq, "replayed": False}

    def put(self, **kwargs):
        return self._mutate(op="put", **kwargs)

    def get(self, key: str):
        if type(key) is not str:
            raise _invalid_argument("key must be a string")
        self._preflight_snapshot()
        with self._locked(exclusive=False):
            self._ensure_log()
            state = self._load().state
            current = state.keys.get(key)
            if current is None or current["tombstone"] is True:
                raise StoreError("NOT_FOUND", f"key {key!r} was not found")
            return {"key": key, "value": current["value"], "version": current["version"]}

    def delete(self, **kwargs):
        return self._mutate(op="delete", value=None, **kwargs)

    def list_items(self):
        self._preflight_snapshot()
        with self._locked(exclusive=False):
            self._ensure_log()
            state = self._load().state
            return [
                {"key": key, "value": entry["value"], "version": entry["version"]}
                for key, entry in sorted(state.keys.items())
                if entry["tombstone"] is False
            ]

    def compact(self):
        self._preflight_snapshot()
        with self._locked(exclusive=True):
            self._ensure_log()
            state = self._load().state
            snapshot = {
                "format_version": 1,
                "keys": state.keys,
                "last_seq": state.last_seq,
                "requests": state.requests,
            }
            snapshot_bytes = (
                json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
                + b"\n"
            )
            self._atomic_replace("snapshot.json.tmp", "snapshot.json", snapshot_bytes)
            self._atomic_replace("events.log.tmp", "events.log", b"")
            return {"snapshot_seq": state.last_seq}

    def recover(self):
        self._preflight_snapshot()
        with self._locked(exclusive=True):
            self._ensure_log()
            result = self._load(allow_tail_damage=True)
            if not result.tail_damaged:
                return {"truncated_bytes": 0}
            truncated_bytes = result.total_log_bytes - result.valid_log_bytes
            try:
                with self._log_path.open("r+b") as stream:
                    stream.truncate(result.valid_log_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError as exc:
                raise StoreError("WRITE_FAILED", f"cannot recover event log: {exc}") from exc
            return {"truncated_bytes": truncated_bytes}

    def _atomic_replace(self, temporary_name: str, final_name: str, data: bytes) -> None:
        temporary_path = self.root / temporary_name
        final_path = self.root / final_name
        try:
            with temporary_path.open("wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, final_path)
            directory_fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as exc:
            raise StoreError("WRITE_FAILED", f"cannot replace {final_name}: {exc}") from exc
