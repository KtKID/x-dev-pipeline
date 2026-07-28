#!/usr/bin/env python3
"""Append a triaged risk lesson to a RAG corpus.

This script is the mechanical tail of skill x-bug2rag. It does NOT decide
whether a bug is worth keeping -- that judgment lives in the skill body. Given
fields the LLM already produced, it:

  1. Allocates the next AR-NNN id by scanning the target corpus.
  2. Refuses duplicate Risk text so the same lesson is not stored twice.
  3. Formats the entry with x-bug2rag's canonical field order.
  4. Appends to the corpus, then validates with x-bug2rag's own contract.
  5. Rolls back on validation failure.

Output is JSON or human text; exit 0 on store, non-zero on any refusal.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

BUG2RAG_SKILL_DIR = Path(__file__).resolve().parents[1]
AGGREGATE_SCRIPT = BUG2RAG_SKILL_DIR / "scripts" / "corpus_aggregate.py"


def _load_aggregate_module():
    module_name = "x_bug2rag_corpus_aggregate"
    spec = importlib.util.spec_from_file_location(module_name, AGGREGATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load aggregate contract: {AGGREGATE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


AGGREGATE_MODULE = _load_aggregate_module()
ROUTE_BY_LABEL = AGGREGATE_MODULE.ROUTE_BY_LABEL
validate_flat_corpus = AGGREGATE_MODULE.validate_flat_corpus

# 必填字段：召回后必须能据此构造对/错反例并完成一级路由。
REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    ("keywords", "关键词"),
    ("risk", "Risk"),
    ("scene", "场景"),
    ("wrong", "错误实现"),
    ("correct", "正确实现"),
    ("observable", "可观察差异"),
    ("category", "分类"),
)
OPTIONAL_FIELDS: tuple[tuple[str, str], ...] = (
    ("source", "来源"),
)
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

RISK_ID_RE = re.compile(r"^##\s+(AR-(\d{3,}))\s*$")
RISK_LINE_RE = re.compile(r"^Risk[：:]\s*(.+?)\s*$")


class TriageError(ValueError):
    """User-facing refusal (missing field, duplicate, rollback)."""


@dataclass(frozen=True)
class StoredEntry:
    id: str
    risk: str

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "risk": self.risk}


def _read_corpus(path: Path) -> str:
    if not path.is_file():
        raise TriageError(f"target corpus not found: {path}")
    return path.read_text(encoding="utf-8")


def next_risk_id(text: str) -> str:
    """Return the next AR-NNN by incrementing the highest existing id."""
    highest = 0
    for line in text.splitlines():
        match = RISK_ID_RE.match(line)
        if match:
            highest = max(highest, int(match.group(2)))
    return f"AR-{highest + 1:03d}"


def _has_duplicate_risk(text: str, risk: str) -> bool:
    needle = risk.strip()
    if not needle:
        return False
    for line in text.splitlines():
        match = RISK_LINE_RE.match(line)
        if match and match.group(1).strip() == needle:
            return True
    return False


def _normalize(value: str | None) -> str:
    return (value or "").strip()


def _require_fields(values: dict[str, str]) -> None:
    missing = [
        label
        for key, label in REQUIRED_FIELDS
        if not values.get(key)
    ]
    if missing:
        raise TriageError("missing required field(s): " + ", ".join(missing))
    categories = [
        part.strip()
        for part in re.split(r"[，,、；;]+", values["category"])
        if part.strip()
    ]
    unknown = sorted(set(categories) - set(ROUTE_BY_LABEL))
    if unknown:
        raise TriageError(
            "unknown category: "
            + ", ".join(unknown)
            + "; expected one or more of: "
            + ", ".join(ROUTE_BY_LABEL)
        )


def format_entry(risk_id: str, values: dict[str, str]) -> str:
    """Render one AR-NNN section in the canonical field order."""
    lines = [f"## {risk_id}", ""]
    for key, label in REQUIRED_FIELDS:
        lines.append(f"{label}：{values[key]}")
    for key, label in OPTIONAL_FIELDS:
        if values.get(key):
            lines.append(f"{label}：{values[key]}")
    # Section 之间留一个空行；末尾换行交给追加逻辑处理。
    lines.append("")
    return "\n".join(lines)


def _append_section(path: Path, section: str) -> None:
    original = path.read_text(encoding="utf-8")
    # 让 section 与既有正文之间恰好空一行；吃掉尾部多余的空行。
    stripped = original.rstrip("\n")
    prefix = stripped + "\n\n" if stripped else ""
    path.write_text(prefix + section + "\n", encoding="utf-8")


def _rollback(path: Path, original: str) -> None:
    path.write_text(original, encoding="utf-8")


def _validate(path: Path) -> list[dict[str, object]]:
    return [
        {"code": "XBR001", "message": issue}
        for issue in validate_flat_corpus(path)
    ]


def store_entry(
    target: Path,
    values: dict[str, str],
) -> StoredEntry:
    """Append one entry, validate, and roll back on validation failure."""
    _require_fields(values)
    text = _read_corpus(target)
    if _has_duplicate_risk(text, values["risk"]):
        raise TriageError(
            "duplicate Risk text already present in corpus; not stored"
        )
    risk_id = next_risk_id(text)
    section = format_entry(risk_id, values)
    original = target.read_text(encoding="utf-8")
    _append_section(target, section)
    issues = _validate(target)
    if issues:
        _rollback(target, original)
        rendered = "; ".join(
            f"[{issue.get('code')}] {issue.get('message')}" for issue in issues
        )
        raise TriageError(f"validation failed after append, rolled back: {rendered}")
    return StoredEntry(id=risk_id, risk=values["risk"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        required=True,
        help="flat corpus file or aggregate corpus directory to append to",
    )
    for key, label in ALL_FIELDS:
        parser.add_argument(
            f"--{key}",
            dest=key,
            default="",
            help=f"{label}（{'必填' if (key, label) in REQUIRED_FIELDS else '可选'}）",
        )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将要写入的 section，不写盘、不校验",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _emit_error(message: str, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"stored": [], "errors": [message]}, ensure_ascii=False))
    else:
        print(f"ERROR: {message}", file=sys.stderr)
    return 1


def _emit_success(entry: StoredEntry, as_json: bool) -> int:
    if as_json:
        print(
            json.dumps(
                {"stored": [entry.as_dict()], "errors": []},
                ensure_ascii=False,
            )
        )
    else:
        print(f"stored {entry.id}: {entry.risk}")
    return 0


def _delegate_aggregate(
    target: Path,
    values: dict[str, str],
    *,
    dry_run: bool,
    as_json: bool,
) -> int:
    command = [
        sys.executable,
        str(AGGREGATE_SCRIPT),
        "append",
        "--target",
        str(target),
    ]
    for key, _ in ALL_FIELDS:
        value = values.get(key, "")
        if value:
            command.extend((f"--{key}", value))
    if dry_run:
        command.append("--dry-run")
    if as_json:
        command.append("--json")
    try:
        proc = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return _emit_error(f"aggregate script not runnable: {exc}", as_json)
    stream = sys.stdout if proc.returncode == 0 or as_json else sys.stderr
    print(proc.stdout.strip() or proc.stderr.strip(), file=stream)
    return proc.returncode


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    values = {key: _normalize(getattr(args, key)) for key, _ in ALL_FIELDS}
    target = Path(args.target)

    if target.is_dir():
        return _delegate_aggregate(
            target,
            values,
            dry_run=args.dry_run,
            as_json=args.as_json,
        )

    if args.dry_run:
        try:
            _require_fields(values)
        except TriageError as exc:
            return _emit_error(str(exc), args.as_json)
        text = _read_corpus(target)
        preview_id = next_risk_id(text)
        section = format_entry(preview_id, values)
        if args.as_json:
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "preview_id": preview_id,
                        "section": section,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(section)
        return 0

    try:
        entry = store_entry(target, values)
    except TriageError as exc:
        return _emit_error(str(exc), args.as_json)
    return _emit_success(entry, args.as_json)


if __name__ == "__main__":
    sys.exit(main())
