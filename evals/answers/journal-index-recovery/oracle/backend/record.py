"""Canonical JSONL record codec for the hidden reference implementation."""

from __future__ import annotations

import json
import zlib


FIELDS = {"seq", "op", "key", "value", "request_id", "expected_version", "crc32"}


class RecordError(ValueError):
    pass


def _body(record: dict[str, object]) -> bytes:
    value = {key: item for key, item in record.items() if key != "crc32"}
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _validate(record: dict[str, object]) -> None:
    if set(record) != FIELDS:
        raise RecordError("record fields mismatch")
    if not isinstance(record["seq"], int) or isinstance(record["seq"], bool) or record["seq"] <= 0:
        raise RecordError("invalid seq")
    if record["op"] not in {"put", "delete"}:
        raise RecordError("invalid op")
    if not isinstance(record["key"], str) or not record["key"]:
        raise RecordError("invalid key")
    if record["op"] == "put" and not isinstance(record["value"], str):
        raise RecordError("put value must be string")
    if record["op"] == "delete" and record["value"] is not None:
        raise RecordError("delete value must be null")
    if not isinstance(record["request_id"], str) or not record["request_id"]:
        raise RecordError("invalid request_id")
    version = record["expected_version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise RecordError("invalid expected_version")
    crc = record["crc32"]
    if not isinstance(crc, str) or len(crc) != 8:
        raise RecordError("invalid crc32")


def encode_record(record: dict[str, object]) -> bytes:
    value = dict(record)
    value["crc32"] = "00000000"
    _validate(value)
    value["crc32"] = f"{zlib.crc32(_body(value)) & 0xFFFFFFFF:08x}"
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def decode_record(raw: bytes) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecordError("invalid json") from exc
    if not isinstance(value, dict):
        raise RecordError("record must be object")
    _validate(value)
    expected = f"{zlib.crc32(_body(value)) & 0xFFFFFFFF:08x}"
    if value["crc32"] != expected:
        raise RecordError("crc mismatch")
    return value

