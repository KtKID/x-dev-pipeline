#!/usr/bin/env python3
"""Journal CLI."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from store import JournalStore, StoreError


_EXIT_CODES = {
    "NOT_FOUND": 3,
    "VERSION_CONFLICT": 4,
    "IDEMPOTENCY_CONFLICT": 5,
    "RECOVERY_REQUIRED": 6,
    "CORRUPT_LOG": 7,
    "CORRUPT_SNAPSHOT": 8,
}


class _ArgumentError(ValueError):
    pass


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _ArgumentError(message)


def _non_negative_integer(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a non-negative integer") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("expected a non-negative integer")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = _JsonArgumentParser(add_help=False)
    parser.add_argument("--root", required=True)
    commands = parser.add_subparsers(dest="command", required=True)

    put = commands.add_parser("put", add_help=False)
    put.add_argument("--key", required=True)
    put.add_argument("--value", required=True)
    put.add_argument("--request-id", required=True)
    put.add_argument("--expected-version", required=True, type=_non_negative_integer)

    get = commands.add_parser("get", add_help=False)
    get.add_argument("--key", required=True)

    delete = commands.add_parser("delete", add_help=False)
    delete.add_argument("--key", required=True)
    delete.add_argument("--request-id", required=True)
    delete.add_argument("--expected-version", required=True, type=_non_negative_integer)

    commands.add_parser("list", add_help=False)
    commands.add_parser("compact", add_help=False)
    commands.add_parser("recover", add_help=False)
    return parser


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def _error(code: str, message: str) -> int:
    _emit({"ok": False, "error": {"code": code, "message": message}})
    return _EXIT_CODES.get(code, 2)


def main(argv: Optional[list[str]] = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
        store = JournalStore(args.root)
        if args.command == "put":
            result = store.put(
                key=args.key,
                value=args.value,
                request_id=args.request_id,
                expected_version=args.expected_version,
            )
        elif args.command == "get":
            result = store.get(args.key)
        elif args.command == "delete":
            result = store.delete(
                key=args.key,
                request_id=args.request_id,
                expected_version=args.expected_version,
            )
        elif args.command == "list":
            result = {"items": store.list_items()}
        elif args.command == "compact":
            result = store.compact()
        else:
            result = store.recover()
    except _ArgumentError as exc:
        return _error("INVALID_ARGUMENT", str(exc))
    except StoreError as exc:
        return _error(exc.code, str(exc))
    except ValueError as exc:
        return _error("INVALID_ARGUMENT", str(exc))
    except OSError as exc:
        return _error("IO_ERROR", str(exc))
    _emit({"ok": True, **result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
