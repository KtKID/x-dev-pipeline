#!/usr/bin/env python3
"""Create a clean, self-contained executor workspace."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from benchmark_common import (
    EXECUTOR_TOOLS,
    PIPELINE_STAGES,
    REQUIRED_SKILLS,
    SHARED_SKILLS,
    BenchmarkError,
    is_forbidden_path,
    read_json,
    sha256_file,
    tree_hashes,
    write_json,
)
from validate_workspace import validate_workspace


SKILL_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_DIR = SKILL_ROOT / "assets" / "executor-tools"
DEFAULT_SKILLS_ROOT = SKILL_ROOT.parent


def ensure_public_source(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise BenchmarkError(f"{label} 不存在: {resolved}")
    if is_forbidden_path(resolved):
        raise BenchmarkError(f"{label} 位于 grader-only 路径: {resolved}")
    return resolved


def copy_input(source: Path, destination: Path) -> None:
    if destination.exists():
        raise BenchmarkError(f"目标已存在，拒绝覆盖: {destination}")
    if source.is_dir():
        shutil.copytree(source, destination, symlinks=False)
    elif source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    else:
        raise BenchmarkError(f"不支持的输入类型: {source}")


def copy_skill(source: Path, destination: Path) -> None:
    if destination.exists():
        raise BenchmarkError(f"目标已存在，拒绝覆盖: {destination}")
    shutil.copytree(
        source,
        destination,
        symlinks=False,
        ignore=shutil.ignore_patterns(
            "evals",
            "tests",
            "__pycache__",
            "*.pyc",
            ".git",
        ),
    )


def prepare(
    workspace: Path,
    task_source: Path,
    fixture_source: Path | None,
    prompt_source: Path | None,
    skills_root: Path,
    manifest_output: Path | None,
    profile: str,
    allow_existing: bool,
) -> dict:
    workspace = workspace.resolve()
    if workspace.exists() and any(workspace.iterdir()) and not allow_existing:
        raise BenchmarkError(f"workspace 必须为空目录或不存在: {workspace}")
    workspace.mkdir(parents=True, exist_ok=True)

    task_source = ensure_public_source(task_source, "task-source")

    copy_input(task_source, workspace / "task")
    public_inputs = [{"kind": "task", "source": str(task_source), "target": "task"}]
    if fixture_source is not None:
        fixture_source = ensure_public_source(fixture_source, "fixture-source")
        copy_input(fixture_source, workspace / "fixture")
        public_inputs.append({"kind": "fixture", "source": str(fixture_source), "target": "fixture"})
    if prompt_source is not None:
        prompt_source = ensure_public_source(prompt_source, "prompt-source")
        if not prompt_source.is_file():
            raise BenchmarkError("prompt-source 必须是文件")
        copy_input(prompt_source, workspace / "PROMPT.md")
        public_inputs.append({"kind": "prompt", "source": str(prompt_source), "target": "PROMPT.md"})

    copied_skills: list[dict[str, str]] = []
    copied_tools: list[dict[str, str]] = []
    if profile == "pipeline_candidate":
        skills_root = skills_root.resolve()
        if not skills_root.is_dir():
            raise BenchmarkError(f"skills-root 不存在: {skills_root}")
        for name in REQUIRED_SKILLS:
            source = skills_root / name
            if not (source / "SKILL.md").is_file():
                raise BenchmarkError(f"skills-root 缺少 {name}/SKILL.md: {source}")
            destination = workspace / "skills" / name
            copy_skill(source, destination)
            copied_skills.append(
                {
                    "name": name,
                    "source": str(source),
                    "skill_sha256": sha256_file(destination / "SKILL.md"),
                }
            )

        skills_readme = workspace / "skills" / "README.md"
        skills_readme.write_text(
            "# Local pipeline skill package\n\n"
            "阶段执行顺序：\n\n"
            + "\n".join(f"{index}. `{name}`" for index, name in enumerate(PIPELINE_STAGES, 1))
            + "\n\n共享 skills：\n\n"
            + "\n".join(f"- `{name}`" for name in SHARED_SKILLS)
            + "\n\n`tools/` 随本地执行包提供并经 SHA 校验。\n",
            encoding="utf-8",
        )

        bundle_manifest = read_json(BUNDLE_DIR / "manifest.json")
        bundle_entries = {
            entry.get("name"): entry.get("sha256")
            for entry in bundle_manifest.get("tools", [])
            if isinstance(entry, dict)
        }
        for name in EXECUTOR_TOOLS:
            source = BUNDLE_DIR / name
            if not source.is_file():
                raise BenchmarkError(f"skill bundled tools 缺少 {name}")
            destination = workspace / "tools" / name
            copy_input(source, destination)
            actual_hash = sha256_file(destination)
            if actual_hash != bundle_entries.get(name):
                raise BenchmarkError(f"bundled tool manifest 与文件不一致: {name}")
            copied_tools.append({"name": name, "sha256": actual_hash})

    files = tree_hashes(workspace)
    package_manifest = {
        "schema_version": 1,
        "profile": profile,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prepared_by": "pipeline-efficiency-benchmark",
        "public_inputs": public_inputs,
        "skills_root": str(skills_root.resolve()) if profile == "pipeline_candidate" else None,
        "skills": copied_skills,
        "tools": copied_tools,
        "files": files,
        "grader_material_exposed": False,
    }
    manifest_path = (
        manifest_output.resolve()
        if manifest_output is not None
        else workspace.parent / "executor-package-manifest.json"
    )
    if manifest_path == workspace or workspace in manifest_path.parents:
        raise BenchmarkError("executor package manifest 必须保存在考生 workspace 外")
    if manifest_path.exists():
        raise BenchmarkError(f"manifest 目标已存在，拒绝覆盖: {manifest_path}")
    write_json(manifest_path, package_manifest)

    issues = validate_workspace(workspace, manifest_path)
    if issues:
        raise BenchmarkError("workspace preflight 失败: " + json.dumps(issues, ensure_ascii=False))
    return {
        "valid": True,
        "workspace": str(workspace),
        "skills": [entry["name"] for entry in copied_skills],
        "tools": [entry["name"] for entry in copied_tools],
        "file_count": len(files),
        "manifest": str(manifest_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument(
        "--profile",
        choices=("pipeline_candidate", "public_task_only"),
        default="pipeline_candidate",
    )
    parser.add_argument("--allow-existing", action="store_true")
    parser.add_argument("--task-source", required=True, type=Path)
    parser.add_argument("--fixture-source", type=Path)
    parser.add_argument("--prompt-source", type=Path)
    parser.add_argument("--skills-root", type=Path, default=DEFAULT_SKILLS_ROOT)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = prepare(
            args.workspace,
            args.task_source,
            args.fixture_source,
            args.prompt_source,
            args.skills_root,
            args.manifest_output,
            args.profile,
            args.allow_existing,
        )
    except BenchmarkError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"workspace prepared: {result['workspace']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
