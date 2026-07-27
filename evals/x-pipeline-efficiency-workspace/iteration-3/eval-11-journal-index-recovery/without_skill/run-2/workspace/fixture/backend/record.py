"""Canonical journal record codec. Implement from task contract."""

from __future__ import annotations

import json
import re
import zlib


class RecordError(ValueError):
    pass


_PAYLOAD_FIELDS = {
    "expected_version",
    "key",
    "op",
    "request_id",
    "seq",
    "value",
}
_ALL_FIELDS = _PAYLOAD_FIELDS | {"crc32"}
_CRC_RE = re.compile(r"^[0-9a-f]{8}$")


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise RecordError(f"record is not JSON encodable: {exc}") from exc


def _validate_payload(record: dict[str, object]) -> None:
    if set(record) != _PAYLOAD_FIELDS:
        raise RecordError("record payload has invalid fields")
    if type(record["seq"]) is not int or record["seq"] <= 0:
        raise RecordError("seq must be a positive integer")
    if type(record["expected_version"]) is not int or record["expected_version"] < 0:
        raise RecordError("expected_version must be a non-negative integer")
    if type(record["key"]) is not str:
        raise RecordError("key must be a string")
    if type(record["request_id"]) is not str:
        raise RecordError("request_id must be a string")
    if type(record["op"]) is not str or record["op"] not in {"put", "delete"}:
        raise RecordError("op must be put or delete")
    if record["op"] == "put" and type(record["value"]) is not str:
        raise RecordError("put value must be a string")
    if record["op"] == "delete" and record["value"] is not None:
        raise RecordError("delete value must be null")


def encode_record(record: dict[str, object]) -> bytes:
    if not isinstance(record, dict):
        raise RecordError("record must be an object")
    payload = dict(record)
    payload.pop("crc32", None)
    _validate_payload(payload)
    crc32 = f"{zlib.crc32(_canonical_json(payload)) & 0xFFFFFFFF:08x}"
    return _canonical_json({**payload, "crc32": crc32}) + b"\n"


def decode_record(raw: bytes) -> dict[str, object]:
    if not isinstance(raw, bytes):
        raise RecordError("raw record must be bytes")
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise RecordError("record must contain exactly one LF-terminated line")
    try:
        text = raw[:-1].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RecordError("record is not valid UTF-8") from exc

    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RecordError(f"duplicate field: {key}")
            result[key] = value
        return result

    try:
        parsed = json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except RecordError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise RecordError("record is not valid JSON") from exc
    if not isinstance(parsed, dict) or set(parsed) != _ALL_FIELDS:
        raise RecordError("record has invalid fields")
    crc32 = parsed["crc32"]
    if not isinstance(crc32, str) or _CRC_RE.fullmatch(crc32) is None:
        raise RecordError("crc32 must be eight lowercase hexadecimal digits")
    payload = {key: parsed[key] for key in _PAYLOAD_FIELDS}
    _validate_payload(payload)
    expected_crc = f"{zlib.crc32(_canonical_json(payload)) & 0xFFFFFFFF:08x}"
    if crc32 != expected_crc:
        raise RecordError("crc32 mismatch")
    return parsed
