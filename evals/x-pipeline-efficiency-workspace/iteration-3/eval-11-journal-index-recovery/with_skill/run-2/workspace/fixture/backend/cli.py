#!/usr/bin/env python3
"""JSON command-line interface for the local journal store."""

from __future__ import annotations

import argparse
import json
import sys

if __package__:
    from .store import JournalStore, StoreError
else:
    from store import JournalStore, StoreError


class _ArgumentError(ValueError):
    pass


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _ArgumentError(message)


def _non_negative_integer(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return value


def _parser() -> _JsonArgumentParser:
    parser = _JsonArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--root", required=True)
    commands = parser.add_subparsers(dest="command", required=True)

    put = commands.add_parser("put", add_help=False, allow_abbrev=False)
    put.add_argument("--key", required=True)
    put.add_argument("--value", required=True)
    put.add_argument("--request-id", required=True)
    put.add_argument("--expected-version", required=True, type=_non_negative_integer)

    get = commands.add_parser("get", add_help=False, allow_abbrev=False)
    get.add_argument("--key", required=True)

    delete = commands.add_parser("delete", add_help=False, allow_abbrev=False)
    delete.add_argument("--key", required=True)
    delete.add_argument("--request-id", required=True)
    delete.add_argument("--expected-version", required=True, type=_non_negative_integer)

    commands.add_parser("list", add_help=False, allow_abbrev=False)
    commands.add_parser("compact", add_help=False, allow_abbrev=False)
    commands.add_parser("recover", add_help=False, allow_abbrev=False)
    return parser


def _success(store: JournalStore, arguments: argparse.Namespace) -> dict[str, object]:
    if arguments.command == "put":
        return {
            "ok": True,
            **store.put(
                key=arguments.key,
                value=arguments.value,
                request_id=arguments.request_id,
                expected_version=arguments.expected_version,
            ),
        }
    if arguments.command == "get":
        return {"ok": True, **store.get(arguments.key)}
    if arguments.command == "delete":
        return {
            "ok": True,
            **store.delete(
                key=arguments.key,
                request_id=arguments.request_id,
                expected_version=arguments.expected_version,
            ),
        }
    if arguments.command == "list":
        return {"ok": True, "items": store.list_items()}
    if arguments.command == "compact":
        return {"ok": True, **store.compact()}
    if arguments.command == "recover":
        return {"ok": True, **store.recover()}
    raise _ArgumentError(f"unknown command: {arguments.command}")


def _failure(code: str, message: str) -> dict[str, object]:
    return {"ok": False, "error": {"code": code, "message": message}}


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> int:
    try:
        arguments = _parser().parse_args()
        payload = _success(JournalStore(arguments.root), arguments)
        exit_code = 0
    except _ArgumentError as exc:
        payload = _failure("INVALID_ARGUMENT", str(exc))
        exit_code = 2
    except StoreError as exc:
        exits = {
            "INVALID_ARGUMENT": 2,
            "NOT_FOUND": 3,
            "VERSION_CONFLICT": 4,
            "IDEMPOTENCY_CONFLICT": 5,
            "RECOVERY_REQUIRED": 6,
            "CORRUPT_LOG": 7,
            "CORRUPT_SNAPSHOT": 8,
        }
        payload = _failure(exc.code, str(exc))
        exit_code = exits.get(exc.code, 1)
    except Exception as exc:
        print(f"journal CLI internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        payload = _failure("INTERNAL_ERROR", "local journal operation failed")
        exit_code = 1
    _emit(payload)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
