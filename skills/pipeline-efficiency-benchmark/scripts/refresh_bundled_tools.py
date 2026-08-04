#!/usr/bin/env python3
"""Refresh the exact executor tool bundle shipped with this skill from skill-owned sources."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from benchmark_common import BUNDLED_TOOLS, BenchmarkError, sha256_file, write_json


SKILL_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_DIR = SKILL_ROOT / "assets" / "executor-tools"

TOOL_SOURCES = {
    "xdev.py": ("x-dev", "scripts/xdev.py"),
    "validator.py": ("x-spec", "scripts/validator.py"),
    "flag.py": ("x-qa-gate", "scripts/flag.py"),
    "req.py": ("x-req", "scripts/req.py"),
    "spec.py": ("x-spec", "scripts/spec.py"),
    "verify.py": ("x-verify", "scripts/verify.py"),
    "metrics.py": ("pipeline-efficiency-benchmark", "scripts/metrics.py"),
}


def refresh(skills_root: Path) -> dict:
    skills_root = skills_root.resolve()
    if not skills_root.is_dir():
        raise BenchmarkError(f"skills 根目录不存在: {skills_root}")

    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, str]] = []
    for name in BUNDLED_TOOLS:
        skill_name, relative = TOOL_SOURCES[name]
        source = skills_root / skill_name / relative
        if not source.is_file():
            raise BenchmarkError(f"skill 脚本缺少 {name}: {source}")
        destination = BUNDLE_DIR / name
        shutil.copy2(source, destination)
        entries.append(
            {
                "name": name,
                "source": f"{skill_name}/{relative}",
                "sha256": sha256_file(destination),
            }
        )

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_skills": str(skills_root),
        "tools": entries,
    }
    write_json(BUNDLE_DIR / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-root", type=Path, default=SKILL_ROOT.parent)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        manifest = refresh(args.skills_root)
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
