"""Canonical journal record codec."""

from __future__ import annotations

import json
import re
import zlib


class RecordError(ValueError):
    """A journal line is malformed, incomplete, or fails its checksum."""


_FIELDS = frozenset({"expected_version", "key", "op", "request_id", "seq", "value"})
_ALL_FIELDS = _FIELDS | {"crc32"}
_CRC_RE = re.compile(r"^[0-9a-f]{8}$")


def _canonical_json(value: dict[str, object]) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RecordError("record cannot be represented as canonical JSON") from exc


def _require_int(value: object, name: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise RecordError(f"{name} must be an integer >= {minimum}")
    return value


def _validate_payload(value: object, *, allow_crc: bool) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RecordError("record must be a JSON object")
    keys = set(value)
    expected = _ALL_FIELDS if allow_crc else _FIELDS
    if keys != expected:
        raise RecordError("record fields do not match the journal schema")

    payload = {name: value[name] for name in _FIELDS}
    if payload["op"] not in {"put", "delete"}:
        raise RecordError("op must be put or delete")
    if not isinstance(payload["key"], str):
        raise RecordError("key must be a string")
    if not isinstance(payload["request_id"], str):
        raise RecordError("request_id must be a string")
    _require_int(payload["expected_version"], "expected_version", minimum=0)
    _require_int(payload["seq"], "seq", minimum=1)
    if payload["op"] == "put" and not isinstance(payload["value"], str):
        raise RecordError("put value must be a string")
    if payload["op"] == "delete" and payload["value"] is not None:
        raise RecordError("delete value must be null")
    return payload


def _loads_object(raw: bytes) -> dict[str, object]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RecordError("record is not valid UTF-8") from exc

    def unique_object(pairs):
        object_value = {}
        for key, value in pairs:
            if key in object_value:
                raise RecordError("record contains a duplicate JSON key")
            object_value[key] = value
        return object_value

    try:
        value = json.loads(text, object_pairs_hook=unique_object)
    except (json.JSONDecodeError, RecordError) as exc:
        if isinstance(exc, RecordError):
            raise
        raise RecordError("record is not valid JSON") from exc
    if not isinstance(value, dict):
        raise RecordError("record must be a JSON object")
    return value


def encode_record(record: dict[str, object]) -> bytes:
    """Return one canonical, newline-terminated record with a fresh CRC-32."""
    source = dict(record)
    source.pop("crc32", None)
    payload = _validate_payload(source, allow_crc=False)
    crc32 = f"{zlib.crc32(_canonical_json(payload)) & 0xFFFFFFFF:08x}"
    completed = dict(payload)
    completed["crc32"] = crc32
    return _canonical_json(completed) + b"\n"


def decode_record(raw: bytes) -> dict[str, object]:
    """Validate a record line and return its decoded fields, including CRC-32."""
    if raw.endswith(b"\n"):
        raw = raw[:-1]
    if b"\n" in raw or b"\r" in raw:
        raise RecordError("record contains an embedded line break")
    value = _loads_object(raw)
    payload = _validate_payload(value, allow_crc=True)
    crc32 = value["crc32"]
    if not isinstance(crc32, str) or _CRC_RE.fullmatch(crc32) is None:
        raise RecordError("crc32 must be eight lowercase hexadecimal digits")
    expected = f"{zlib.crc32(_canonical_json(payload)) & 0xFFFFFFFF:08x}"
    if crc32 != expected:
        raise RecordError("crc32 mismatch")
    decoded = dict(payload)
    decoded["crc32"] = crc32
    return decoded
