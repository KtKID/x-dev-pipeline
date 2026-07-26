#!/usr/bin/env python3
"""Shared deterministic helpers for pipeline-efficiency-benchmark."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


REQUIRED_SKILLS = (
    "x-spec3",
    "x-adversarial-risk",
    "x-req3",
    "x-dev",
    "x-verify",
    "x-qa-gate",
    "x-fix",
)

EXECUTOR_TOOLS = (
    "xdev.py",
    "validator.py",
    "flag.py",
    "req3.py",
    "spec.py",
    "verify.py",
)

BUNDLED_TOOLS = (
    *EXECUTOR_TOOLS,
    "metrics.py",
)

FORBIDDEN_COMPONENTS = {
    "oracle",
    "oracles",
    "rubric",
    "rubrics",
    "grader",
    "graders",
    "answers",
    "evaluator-only",
}


class BenchmarkError(ValueError):
    """Raised for deterministic input, schema, or comparison failures."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"无法读取 JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BenchmarkError(f"JSON 顶层必须是 object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        handle.write(payload)
        temp_name = handle.name
    os.replace(temp_name, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def iter_regular_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            yield path


def tree_hashes(root: Path, *, exclude: set[str] | None = None) -> dict[str, str]:
    excluded = exclude or set()
    result: dict[str, str] = {}
    for path in iter_regular_files(root):
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        result[relative] = sha256_file(path)
    return result


def is_forbidden_path(path: Path) -> bool:
    return any(part.lower() in FORBIDDEN_COMPONENTS for part in path.parts)


def require_non_negative_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise BenchmarkError(f"{field} 必须是非负整数")
    return value


def require_number(value: object, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise BenchmarkError(f"{field} 必须是数字")
    return float(value)


def percent_delta(current: float | int | None, baseline: float | int | None) -> float | None:
    if current is None or baseline in (None, 0):
        return None
    return round((float(current) / float(baseline) - 1.0) * 100.0, 2)
