#!/usr/bin/env python3
"""Command-line interface for the local journal store."""

from __future__ import annotations

import argparse
import json
import sys

try:
    from .store import JournalStore, StoreError
except ImportError:  # Direct script execution.
    from store import JournalStore, StoreError


EXIT_CODES = {
    "ARGUMENT_ERROR": 2,
    "NOT_FOUND": 3,
    "VERSION_CONFLICT": 4,
    "IDEMPOTENCY_CONFLICT": 5,
    "RECOVERY_REQUIRED": 6,
    "CORRUPT_LOG": 7,
    "CORRUPT_SNAPSHOT": 8,
}


class _ArgumentFailure(ValueError):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _ArgumentFailure(message)


def _non_negative_int(raw: str) -> int:
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="journal", add_help=False)
    parser.add_argument("--root", required=True)
    commands = parser.add_subparsers(dest="command", required=True)

    put = commands.add_parser("put", add_help=False)
    put.add_argument("--key", required=True)
    put.add_argument("--value", required=True)
    put.add_argument("--request-id", required=True)
    put.add_argument("--expected-version", required=True, type=_non_negative_int)

    get = commands.add_parser("get", add_help=False)
    get.add_argument("--key", required=True)

    delete = commands.add_parser("delete", add_help=False)
    delete.add_argument("--key", required=True)
    delete.add_argument("--request-id", required=True)
    delete.add_argument("--expected-version", required=True, type=_non_negative_int)

    commands.add_parser("list", add_help=False)
    commands.add_parser("compact", add_help=False)
    commands.add_parser("recover", add_help=False)
    return parser


def _emit(body: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> int:
    try:
        args = _parser().parse_args()
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
        _emit({"ok": True, **result})
        return 0
    except _ArgumentFailure as exc:
        _emit({"ok": False, "error": {"code": "ARGUMENT_ERROR", "message": str(exc)}})
        return 2
    except StoreError as exc:
        _emit({"ok": False, "error": {"code": exc.code, "message": str(exc)}})
        return EXIT_CODES.get(exc.code, 2)
    except Exception as exc:
        _emit({"ok": False, "error": {"code": "INTERNAL_ERROR", "message": str(exc)}})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
