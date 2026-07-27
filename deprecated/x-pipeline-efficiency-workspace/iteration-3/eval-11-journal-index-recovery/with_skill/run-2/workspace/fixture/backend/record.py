"""Canonical journal record codec."""

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
_RECORD_FIELDS = _PAYLOAD_FIELDS | {"crc32"}
_CRC_PATTERN = re.compile(r"[0-9a-f]{8}\Z")


def _is_int(value: object) -> bool:
    return type(value) is int


def _validate_payload(payload: dict[str, object]) -> None:
    if set(payload) != _PAYLOAD_FIELDS:
        raise RecordError("record payload fields do not match the journal schema")
    if not _is_int(payload["expected_version"]) or payload["expected_version"] < 0:
        raise RecordError("expected_version must be a non-negative integer")
    if not _is_int(payload["seq"]) or payload["seq"] <= 0:
        raise RecordError("seq must be a positive integer")
    if not isinstance(payload["key"], str):
        raise RecordError("key must be a string")
    if not isinstance(payload["request_id"], str):
        raise RecordError("request_id must be a string")
    if not isinstance(payload["op"], str) or payload["op"] not in {"put", "delete"}:
        raise RecordError("op must be put or delete")
    if payload["op"] == "put" and not isinstance(payload["value"], str):
        raise RecordError("put value must be a string")
    if payload["op"] == "delete" and payload["value"] is not None:
        raise RecordError("delete value must be null")


def _canonical_payload(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _crc(payload: dict[str, object]) -> str:
    return f"{zlib.crc32(_canonical_payload(payload)) & 0xFFFFFFFF:08x}"


def encode_record(record: dict[str, object]) -> bytes:
    if not isinstance(record, dict):
        raise RecordError("record must be an object")
    fields = set(record)
    if fields != _PAYLOAD_FIELDS and fields != _RECORD_FIELDS:
        raise RecordError("record fields do not match the journal schema")
    payload = {key: value for key, value in record.items() if key != "crc32"}
    _validate_payload(payload)
    if "crc32" in record:
        supplied = record["crc32"]
        if not isinstance(supplied, str) or _CRC_PATTERN.fullmatch(supplied) is None:
            raise RecordError("crc32 must be eight lowercase hexadecimal digits")
    encoded = {"crc32": _crc(payload), **payload}
    return json.dumps(encoded, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def _object_without_duplicate_keys(pairs):
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RecordError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def decode_record(raw: bytes) -> dict[str, object]:
    if not isinstance(raw, bytes):
        raise RecordError("record input must be bytes")
    if not raw.endswith(b"\n") or b"\n" in raw[:-1]:
        raise RecordError("record must contain exactly one newline at the end")
    try:
        text = raw[:-1].decode("utf-8")
        decoded = json.loads(text, object_pairs_hook=_object_without_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecordError("record is not valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict) or set(decoded) != _RECORD_FIELDS:
        raise RecordError("record fields do not match the journal schema")
    supplied_crc = decoded["crc32"]
    if not isinstance(supplied_crc, str) or _CRC_PATTERN.fullmatch(supplied_crc) is None:
        raise RecordError("crc32 must be eight lowercase hexadecimal digits")
    payload = {key: value for key, value in decoded.items() if key != "crc32"}
    _validate_payload(payload)
    if supplied_crc != _crc(payload):
        raise RecordError("record CRC does not match its payload")
    return decoded
