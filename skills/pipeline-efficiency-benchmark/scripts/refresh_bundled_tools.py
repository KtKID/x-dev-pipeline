#!/usr/bin/env python3
"""Refresh the exact executor tool bundle shipped with this skill."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from benchmark_common import BUNDLED_TOOLS, BenchmarkError, sha256_file, write_json


SKILL_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_DIR = SKILL_ROOT / "assets" / "executor-tools"


def refresh(source_tools: Path) -> dict:
    source_tools = source_tools.resolve()
    if not source_tools.is_dir():
        raise BenchmarkError(f"tools 源目录不存在: {source_tools}")

    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, str]] = []
    for name in BUNDLED_TOOLS:
        source = source_tools / name
        if not source.is_file():
            raise BenchmarkError(f"tools 源缺少 {name}: {source}")
        destination = BUNDLE_DIR / name
        shutil.copy2(source, destination)
        entries.append({"name": name, "sha256": sha256_file(destination)})

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_tools": str(source_tools),
        "tools": entries,
    }
    write_json(BUNDLE_DIR / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-tools", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        manifest = refresh(args.source_tools)
    except BenchmarkError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        import json

        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print(f"bundled tools refreshed: {len(manifest['tools'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
