"""Canonical journal record codec. Implement from task contract."""

from __future__ import annotations


class RecordError(ValueError):
    pass


def encode_record(record: dict[str, object]) -> bytes:
    raise NotImplementedError


def decode_record(raw: bytes) -> dict[str, object]:
    raise NotImplementedError

