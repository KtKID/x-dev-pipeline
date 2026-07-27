#!/usr/bin/env python3
"""Journal CLI."""

from __future__ import annotations

import argparse
import json
import sys

try:
    from .store import JournalStore, StoreError
except ImportError:  # Direct script execution.
    from store import JournalStore, StoreError


class _UsageError(ValueError):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _UsageError(message)

    def exit(self, status: int = 0, message: str | None = None) -> None:
        raise _UsageError(message.strip() if message else "help is unavailable")


_EXIT_CODES = {
    "NOT_FOUND": 3,
    "VERSION_CONFLICT": 4,
    "IDEMPOTENCY_CONFLICT": 5,
    "RECOVERY_REQUIRED": 6,
    "CORRUPT_LOG": 7,
    "CORRUPT_SNAPSHOT": 8,
}


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(add_help=False)
    parser.add_argument("--root", required=True)
    commands = parser.add_subparsers(dest="command")
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


def _emit(value: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _parse(argv: list[str]) -> argparse.Namespace:
    args = _parser().parse_args(argv)
    if args.command is None:
        raise _UsageError("a command is required")
    if getattr(args, "expected_version", 0) < 0:
        raise _UsageError("expected_version must be a non-negative integer")
    return args


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse(sys.argv[1:] if argv is None else argv)
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
            result = store.list_items()
        elif args.command == "compact":
            result = store.compact()
        elif args.command == "recover":
            result = store.recover()
        else:
            raise _UsageError("unknown command")
    except _UsageError as exc:
        _emit({"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": str(exc)}})
        return 2
    except StoreError as exc:
        _emit({"ok": False, "error": {"code": exc.code, "message": str(exc)}})
        return _EXIT_CODES.get(exc.code, 2)
    except Exception as exc:
        print(f"journal internal error: {exc}", file=sys.stderr)
        _emit({"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "journal operation failed"}})
        return 1
    _emit({"ok": True, **result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
