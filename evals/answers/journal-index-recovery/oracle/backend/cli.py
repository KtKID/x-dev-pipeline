#!/usr/bin/env python3
"""Reference command line adapter."""

from __future__ import annotations

import argparse
import json
import sys

from store import JournalStore, StoreError


EXITS = {"NOT_FOUND": 3, "VERSION_CONFLICT": 4, "IDEMPOTENCY_CONFLICT": 5, "RECOVERY_REQUIRED": 6, "CORRUPT_LOG": 7, "CORRUPT_SNAPSHOT": 8}


class UsageError(ValueError):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


def parser() -> Parser:
    root = Parser(add_help=True)
    root.add_argument("--root", required=True)
    commands = root.add_subparsers(dest="command", required=True)
    put = commands.add_parser("put")
    put.add_argument("--key", required=True)
    put.add_argument("--value", required=True)
    put.add_argument("--request-id", required=True)
    put.add_argument("--expected-version", required=True, type=int)
    get = commands.add_parser("get")
    get.add_argument("--key", required=True)
    delete = commands.add_parser("delete")
    delete.add_argument("--key", required=True)
    delete.add_argument("--request-id", required=True)
    delete.add_argument("--expected-version", required=True, type=int)
    commands.add_parser("list")
    commands.add_parser("compact")
    commands.add_parser("recover")
    return root


def emit(value: dict[str, object]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        if getattr(args, "expected_version", 0) < 0:
            raise UsageError("expected-version must be non-negative")
        store = JournalStore(args.root)
        if args.command == "put":
            result = store.put(key=args.key, value=args.value, request_id=args.request_id, expected_version=args.expected_version)
        elif args.command == "get":
            result = store.get(args.key)
        elif args.command == "delete":
            result = store.delete(key=args.key, request_id=args.request_id, expected_version=args.expected_version)
        elif args.command == "list":
            result = store.list_items()
        elif args.command == "compact":
            result = store.compact()
        else:
            result = store.recover()
        emit(result)
        return 0
    except UsageError as exc:
        emit({"ok": False, "error": {"code": "USAGE", "message": str(exc)}})
        return 2
    except StoreError as exc:
        emit({"ok": False, "error": {"code": exc.code, "message": str(exc)}})
        return EXITS.get(exc.code, 1)


if __name__ == "__main__":
    raise SystemExit(main())

