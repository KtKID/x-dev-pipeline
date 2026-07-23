"""Canonical journal record codec."""

from __future__ import annotations

import json
import zlib
from typing import Any


class RecordError(ValueError):
    """A journal line has invalid structure or integrity data."""


_BUSINESS_FIELDS = {
    "expected_version",
    "key",
    "op",
    "request_id",
    "seq",
    "value",
}
_ALL_FIELDS = _BUSINESS_FIELDS | {"crc32"}


def _canonical_json(value: object) -> bytes:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise RecordError("record is not JSON serializable") from exc
    return encoded.encode("utf-8")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_payload(payload: dict[str, object]) -> None:
    if set(payload) != _BUSINESS_FIELDS:
        raise RecordError("record fields are invalid")
    if payload["op"] not in {"put", "delete"}:
        raise RecordError("record operation is invalid")
    if not _is_int(payload["seq"]) or payload["seq"] <= 0:
        raise RecordError("record seq is invalid")
    if not _is_int(payload["expected_version"]) or payload["expected_version"] < 0:
        raise RecordError("record expected_version is invalid")
    if not isinstance(payload["key"], str):
        raise RecordError("record key is invalid")
    if not isinstance(payload["request_id"], str):
        raise RecordError("record request_id is invalid")
    value = payload["value"]
    if payload["op"] == "put" and not isinstance(value, str):
        raise RecordError("put record value is invalid")
    if payload["op"] == "delete" and value is not None:
        raise RecordError("delete record value is invalid")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RecordError("record has duplicate JSON keys")
        result[key] = value
    return result


def encode_record(record: dict[str, object]) -> bytes:
    """Return one canonical, newline-terminated record with its CRC-32."""
    if not isinstance(record, dict):
        raise RecordError("record must be an object")
    payload = dict(record)
    payload.pop("crc32", None)
    _validate_payload(payload)
    crc32 = f"{zlib.crc32(_canonical_json(payload)) & 0xFFFFFFFF:08x}"
    encoded = dict(payload)
    encoded["crc32"] = crc32
    return _canonical_json(encoded) + b"\n"


def decode_record(raw: bytes) -> dict[str, object]:
    """Validate and decode exactly one newline-terminated journal record."""
    if not isinstance(raw, bytes) or not raw.endswith(b"\n"):
        raise RecordError("record is missing its newline")
    body = raw[:-1]
    if not body or b"\n" in body:
        raise RecordError("record must occupy one physical line")
    try:
        decoded = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_object_without_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecordError) as exc:
        raise RecordError("record JSON is invalid") from exc
    if not isinstance(decoded, dict) or set(decoded) != _ALL_FIELDS:
        raise RecordError("record fields are invalid")
    crc32 = decoded.get("crc32")
    if not isinstance(crc32, str) or len(crc32) != 8:
        raise RecordError("record crc32 is invalid")
    if any(character not in "0123456789abcdef" for character in crc32):
        raise RecordError("record crc32 is invalid")
    payload = {key: value for key, value in decoded.items() if key != "crc32"}
    _validate_payload(payload)
    expected_crc = f"{zlib.crc32(_canonical_json(payload)) & 0xFFFFFFFF:08x}"
    if crc32 != expected_crc:
        raise RecordError("record crc32 does not match")
    return decoded
