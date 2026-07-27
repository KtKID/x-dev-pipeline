"""Canonical journal record codec. Implement from task contract."""

from __future__ import annotations

import json
import re
import zlib


class RecordError(ValueError):
    pass


_CORE_FIELDS = {
    "expected_version",
    "key",
    "op",
    "request_id",
    "seq",
    "value",
}
_ALL_FIELDS = _CORE_FIELDS | {"crc32"}
_CRC_PATTERN = re.compile(r"[0-9a-f]{8}")


def _canonical_bytes(record: dict[str, object]) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _validate_core(record: dict[str, object]) -> None:
    if set(record) != _CORE_FIELDS:
        raise RecordError("record fields do not match the journal schema")

    seq = record["seq"]
    expected_version = record["expected_version"]
    if isinstance(seq, bool) or not isinstance(seq, int) or seq <= 0:
        raise RecordError("seq must be a positive integer")
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version < 0
    ):
        raise RecordError("expected_version must be a non-negative integer")
    if not isinstance(record["key"], str):
        raise RecordError("key must be a string")
    if not isinstance(record["request_id"], str):
        raise RecordError("request_id must be a string")

    op = record["op"]
    value = record["value"]
    if op == "put":
        if not isinstance(value, str):
            raise RecordError("put value must be a string")
    elif op == "delete":
        if value is not None:
            raise RecordError("delete value must be null")
    else:
        raise RecordError("op must be put or delete")


def encode_record(record: dict[str, object]) -> bytes:
    if not isinstance(record, dict):
        raise RecordError("record must be an object")
    if set(record) == _ALL_FIELDS:
        core = {key: value for key, value in record.items() if key != "crc32"}
    else:
        core = dict(record)
    _validate_core(core)
    encoded_core = _canonical_bytes(core)
    crc = f"{zlib.crc32(encoded_core) & 0xFFFFFFFF:08x}"
    return _canonical_bytes({**core, "crc32": crc}) + b"\n"


def decode_record(raw: bytes) -> dict[str, object]:
    if not isinstance(raw, bytes):
        raise RecordError("record input must be bytes")
    payload = raw[:-1] if raw.endswith(b"\n") else raw
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RecordError("record is not valid UTF-8") from exc
    try:
        decoded = json.loads(text)
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise RecordError("record is not valid JSON") from exc
    if not isinstance(decoded, dict) or set(decoded) != _ALL_FIELDS:
        raise RecordError("record fields do not match the journal schema")

    crc = decoded.get("crc32")
    if not isinstance(crc, str) or _CRC_PATTERN.fullmatch(crc) is None:
        raise RecordError("crc32 must be eight lowercase hexadecimal digits")
    core = {key: value for key, value in decoded.items() if key != "crc32"}
    _validate_core(core)
    actual_crc = f"{zlib.crc32(_canonical_bytes(core)) & 0xFFFFFFFF:08x}"
    if crc != actual_crc:
        raise RecordError("crc32 mismatch")
    return decoded
