#!/usr/bin/env python3
"""Initialize and seed the user-global x-dev-pipeline RAG corpus.

Every platform uses the same location relative to the user's home directory:

    ~/.x-dev-pipeline/rag/risk-catalog.md

The two mutations are intentionally separate:

1. ``init`` creates the user-global RAG directory.
2. ``import-existing`` copies an existing ``risk-catalog.md`` into it.

``--home`` exists for deterministic tests and first-user simulations. Normal
invocations resolve the home directory with ``Path.home()``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Sequence


BUG2RAG_SKILL_DIR = Path(__file__).resolve().parents[1]
SKILLS_DIR = BUG2RAG_SKILL_DIR.parent
AGGREGATE_SCRIPT = BUG2RAG_SKILL_DIR / "scripts" / "corpus_aggregate.py"
DEFAULT_EXISTING_CORPUS = (
    SKILLS_DIR / "x-adversarial-risk" / "references" / "risk-catalog.md"
)
APP_DIRECTORY = ".x-dev-pipeline"
RAG_DIRECTORY = "rag"
CORPUS_FILENAME = "risk-catalog.md"


def _load_aggregate_module():
    module_name = "x_bug2rag_home_corpus_aggregate"
    spec = importlib.util.spec_from_file_location(module_name, AGGREGATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load aggregate contract: {AGGREGATE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


AGGREGATE_MODULE = _load_aggregate_module()
AggregateError = AGGREGATE_MODULE.AggregateError
parse_entries = AGGREGATE_MODULE.parse_entries
validate_flat_corpus = AGGREGATE_MODULE.validate_flat_corpus


def user_rag_directory(home: Path | None = None) -> Path:
    home_directory = home if home is not None else Path.home()
    return home_directory.expanduser() / APP_DIRECTORY / RAG_DIRECTORY


def user_corpus_path(home: Path | None = None) -> Path:
    return user_rag_directory(home) / CORPUS_FILENAME


def _resolved_home(raw: str | None) -> Path | None:
    if raw is None:
        return None
    return Path(raw).expanduser()


def _add_home_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--home",
        help="测试或模拟首次使用时指定 Home；默认使用 Path.home()",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    path = commands.add_parser("path")
    _add_home_argument(path)

    init = commands.add_parser("init")
    _add_home_argument(init)

    import_existing = commands.add_parser("import-existing")
    _add_home_argument(import_existing)
    import_existing.add_argument(
        "--source",
        default=str(DEFAULT_EXISTING_CORPUS),
        help="已有单文件 corpus；默认使用插件自带 risk-catalog.md",
    )

    validate = commands.add_parser("validate")
    _add_home_argument(validate)

    for command in (path, init, import_existing, validate):
        command.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _emit(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if payload.get("command") == "path":
        print(payload["target"])
        return
    print(json.dumps(payload, ensure_ascii=False))


def _emit_error(command: str, target: Path, message: str, *, as_json: bool) -> int:
    payload = {
        "command": command,
        "target": str(target),
        "valid": False,
        "error": message,
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ERROR: {message}", file=sys.stderr)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    home = _resolved_home(args.home)
    directory = user_rag_directory(home)
    target = user_corpus_path(home)

    try:
        if args.command == "path":
            payload = {
                "command": "path",
                "target": str(target),
                "valid": True,
            }
        elif args.command == "init":
            if directory.exists() and not directory.is_dir():
                raise AggregateError(f"用户 RAG 路径必须是目录：{directory}")
            created = not directory.exists()
            directory.mkdir(parents=True, exist_ok=True)
            payload = {
                "command": "init",
                "directory": str(directory),
                "target": str(target),
                "created": created,
                "valid": True,
            }
        elif args.command == "import-existing":
            if not directory.is_dir():
                raise AggregateError(f"请先初始化用户 RAG 目录：{directory}")
            source = Path(args.source)
            source_issues = validate_flat_corpus(source)
            if source_issues:
                raise AggregateError(
                    "源 corpus 校验失败：" + "；".join(source_issues)
                )
            source_bytes = source.read_bytes()
            entries = parse_entries(
                source_bytes.decode("utf-8"),
                source=str(source),
            )
            if target.exists():
                if target.read_bytes() == source_bytes:
                    payload = {
                        "command": "import-existing",
                        "source": str(source),
                        "target": str(target),
                        "copied": False,
                        "entry_count": len(entries),
                        "first_id": entries[0].id,
                        "last_id": entries[-1].id,
                        "valid": True,
                    }
                    _emit(payload, as_json=args.as_json)
                    return 0
                raise AggregateError(f"目标 corpus 已有内容，停止覆盖：{target}")
            temporary_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    prefix=".risk-catalog-",
                    suffix=".tmp",
                    dir=directory,
                    delete=False,
                ) as temporary:
                    temporary.write(source_bytes)
                    temporary_path = Path(temporary.name)
                os.replace(temporary_path, target)
            finally:
                if temporary_path is not None and temporary_path.exists():
                    temporary_path.unlink()
            target_issues = validate_flat_corpus(target)
            if target_issues:
                target.unlink()
                raise AggregateError(
                    "复制后的 corpus 校验失败，已回滚："
                    + "；".join(target_issues)
                )
            payload = {
                "command": "import-existing",
                "source": str(source),
                "target": str(target),
                "copied": True,
                "entry_count": len(entries),
                "first_id": entries[0].id,
                "last_id": entries[-1].id,
                "valid": True,
            }
        else:
            issues = validate_flat_corpus(target)
            entries = (
                parse_entries(
                    target.read_text(encoding="utf-8"),
                    source=str(target),
                )
                if not issues
                else []
            )
            payload = {
                "command": "validate",
                "target": str(target),
                "entry_count": len(entries),
                "valid": not issues,
                "issues": issues,
            }
            _emit(payload, as_json=args.as_json)
            return 1 if issues else 0
    except (AggregateError, OSError, UnicodeError) as exc:
        return _emit_error(
            args.command,
            target,
            str(exc),
            as_json=args.as_json,
        )

    _emit(payload, as_json=args.as_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
