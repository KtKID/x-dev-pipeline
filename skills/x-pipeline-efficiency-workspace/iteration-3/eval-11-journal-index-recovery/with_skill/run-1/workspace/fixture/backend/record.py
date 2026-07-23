"""Canonical journal record codec."""

from __future__ import annotations

import json
import re
import zlib


class RecordError(ValueError):
    """A physical record cannot be interpreted as a committed mutation."""


_PAYLOAD_FIELDS = {
    "expected_version",
    "key",
    "op",
    "request_id",
    "seq",
    "value",
}
_RECORD_FIELDS = _PAYLOAD_FIELDS | {"crc32"}
_CRC_RE = re.compile(r"^[0-9a-f]{8}$")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_payload(payload: dict[str, object]) -> None:
    if set(payload) != _PAYLOAD_FIELDS:
        raise RecordError("record fields do not match the journal schema")
    if payload["op"] not in {"put", "delete"}:
        raise RecordError("record op must be put or delete")
    if not isinstance(payload["key"], str) or not payload["key"]:
        raise RecordError("record key must be a non-empty string")
    if not isinstance(payload["request_id"], str) or not payload["request_id"]:
        raise RecordError("record request_id must be a non-empty string")
    if not _is_int(payload["seq"]) or payload["seq"] <= 0:
        raise RecordError("record seq must be a positive integer")
    if not _is_int(payload["expected_version"]) or payload["expected_version"] < 0:
        raise RecordError("record expected_version must be a non-negative integer")
    if payload["op"] == "put" and not isinstance(payload["value"], str):
        raise RecordError("put record value must be a string")
    if payload["op"] == "delete" and payload["value"] is not None:
        raise RecordError("delete record value must be null")


def _canonical_bytes(payload: dict[str, object]) -> bytes:
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RecordError("record is not JSON encodable") from exc


def encode_record(record: dict[str, object]) -> bytes:
    """Encode a mutation as canonical JSON with a computed CRC and final LF."""
    if not isinstance(record, dict):
        raise RecordError("record must be an object")
    payload = {key: value for key, value in record.items() if key != "crc32"}
    _validate_payload(payload)
    crc = format(zlib.crc32(_canonical_bytes(payload)) & 0xFFFFFFFF, "08x")
    encoded = dict(payload)
    encoded["crc32"] = crc
    return _canonical_bytes(encoded) + b"\n"


def decode_record(raw: bytes) -> dict[str, object]:
    """Decode one physical record, accepting its single terminating LF."""
    if not isinstance(raw, bytes):
        raise RecordError("record input must be bytes")
    body = raw[:-1] if raw.endswith(b"\n") else raw
    if not body or b"\n" in body or b"\r" in body:
        raise RecordError("record must contain one non-empty JSON line")
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise RecordError("record is not valid UTF-8") from exc
    try:
        decoded = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise RecordError("record is not valid JSON") from exc
    if not isinstance(decoded, dict) or set(decoded) != _RECORD_FIELDS:
        raise RecordError("record fields do not match the journal schema")
    crc = decoded.get("crc32")
    if not isinstance(crc, str) or _CRC_RE.fullmatch(crc) is None:
        raise RecordError("record crc32 must be eight lowercase hexadecimal digits")
    payload = {key: value for key, value in decoded.items() if key != "crc32"}
    _validate_payload(payload)
    expected = format(zlib.crc32(_canonical_bytes(payload)) & 0xFFFFFFFF, "08x")
    if crc != expected:
        raise RecordError("record CRC mismatch")
    return decoded
