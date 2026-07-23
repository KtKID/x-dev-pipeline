#!/usr/bin/env python3
"""Journal CLI. Implement from task contract."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from store import JournalStore, StoreError


class _UsageError(ValueError):
    pass


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _UsageError(message)


EXIT_CODES = {
    "INVALID_ARGUMENT": 2,
    "NOT_FOUND": 3,
    "VERSION_CONFLICT": 4,
    "IDEMPOTENCY_CONFLICT": 5,
    "RECOVERY_REQUIRED": 6,
    "CORRUPT_LOG": 7,
    "CORRUPT_SNAPSHOT": 8,
}


def _parser() -> _ArgumentParser:
    parser = _ArgumentParser(prog="journal", add_help=False)
    parser.add_argument("--root", required=True)
    commands = parser.add_subparsers(dest="command", required=True)

    put = commands.add_parser("put", add_help=False)
    put.add_argument("--key", required=True)
    put.add_argument("--value", required=True)
    put.add_argument("--request-id", required=True)
    put.add_argument("--expected-version", required=True, type=int)

    get = commands.add_parser("get", add_help=False)
    get.add_argument("--key", required=True)

    delete = commands.add_parser("delete", add_help=False)
    delete.add_argument("--key", required=True)
    delete.add_argument("--request-id", required=True)
    delete.add_argument("--expected-version", required=True, type=int)

    commands.add_parser("list", add_help=False)
    commands.add_parser("compact", add_help=False)
    commands.add_parser("recover", add_help=False)
    return parser


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def _failure(code: str, message: str) -> dict[str, object]:
    return {"ok": False, "error": {"code": code, "message": message}}


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if getattr(args, "expected_version", 0) < 0:
            raise _UsageError("expected-version must be non-negative")
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
        elif args.command == "recover":
            result = store.recover()
        else:
            raise _UsageError(f"unknown command: {args.command}")
        _emit({"ok": True, **result})
        return 0
    except _UsageError as exc:
        _emit(_failure("INVALID_ARGUMENT", str(exc)))
        return 2
    except StoreError as exc:
        _emit(_failure(exc.code, str(exc)))
        return EXIT_CODES.get(exc.code, 2)
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        _emit(_failure("INVALID_ARGUMENT", "internal journal error"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
