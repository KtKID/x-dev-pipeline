#!/usr/bin/env python3
"""Journal CLI. Implement from task contract."""

from __future__ import annotations

import argparse
import json
import sys

try:
    from .store import JournalStore, StoreError
except ImportError:
    from store import JournalStore, StoreError


class CliUsageError(ValueError):
    pass


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliUsageError(message)


def _non_negative_int(raw: str) -> int:
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return value


def _build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(add_help=False, prog="journal")
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


_EXIT_CODES = {
    "INVALID_ARGUMENT": 2,
    "NOT_FOUND": 3,
    "VERSION_CONFLICT": 4,
    "IDEMPOTENCY_CONFLICT": 5,
    "RECOVERY_REQUIRED": 6,
    "CORRUPT_LOG": 7,
    "CORRUPT_SNAPSHOT": 8,
}


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> int:
    try:
        arguments = _build_parser().parse_args()
        store = JournalStore(arguments.root)
        if arguments.command == "put":
            result = store.put(
                key=arguments.key,
                value=arguments.value,
                request_id=arguments.request_id,
                expected_version=arguments.expected_version,
            )
        elif arguments.command == "get":
            result = store.get(arguments.key)
        elif arguments.command == "delete":
            result = store.delete(
                key=arguments.key,
                request_id=arguments.request_id,
                expected_version=arguments.expected_version,
            )
        elif arguments.command == "list":
            result = {"items": store.list_items()}
        elif arguments.command == "compact":
            result = store.compact()
        elif arguments.command == "recover":
            result = store.recover()
        else:
            raise CliUsageError(f"unknown command: {arguments.command}")
        _emit({"ok": True, **result})
        return 0
    except CliUsageError as exc:
        _emit(
            {
                "ok": False,
                "error": {"code": "INVALID_ARGUMENT", "message": str(exc)},
            }
        )
        return 2
    except StoreError as exc:
        _emit({"ok": False, "error": {"code": exc.code, "message": str(exc)}})
        return _EXIT_CODES.get(exc.code, 1)
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "error": {"code": "INTERNAL_ERROR", "message": str(exc)},
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
