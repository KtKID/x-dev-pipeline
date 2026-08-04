#!/usr/bin/env python3
"""Validate an executor workspace before any model sees it."""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import sysconfig
from pathlib import Path

from benchmark_common import (
    FORBIDDEN_COMPONENTS,
    REQUIRED_SKILLS,
    EXECUTOR_TOOLS,
    BenchmarkError,
    is_forbidden_path,
    read_json,
    sha256_file,
)


SKILL_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_MANIFEST = SKILL_ROOT / "assets" / "executor-tools" / "manifest.json"
PACKAGE_MANIFEST = "executor-package-manifest.json"


def local_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        raise BenchmarkError(f"无法解析工具 {path}: {exc}") from exc
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module.split(".", 1)[0])
    return result


def standard_library_modules() -> set[str]:
    """返回当前解释器的顶层标准库模块，兼容没有 ``sys.stdlib_module_names`` 的 Python。"""
    declared = getattr(sys, "stdlib_module_names", None)
    if declared:
        return set(declared)

    modules = set(sys.builtin_module_names)
    stdlib = Path(sysconfig.get_paths()["stdlib"])
    for child in stdlib.iterdir():
        if child.suffix == ".py":
            modules.add(child.stem)
        elif child.is_dir() and (child / "__init__.py").is_file():
            modules.add(child.name)
    return modules


def validate_workspace(workspace: Path, manifest_path: Path | None = None) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    workspace = workspace.resolve()
    if not workspace.is_dir():
        return [{"code": "W001", "path": str(workspace), "message": "workspace 目录不存在"}]

    if not (workspace / "task").is_dir():
        issues.append({"code": "W002", "path": "task", "message": "缺少公开 task 目录"})

    manifest_path = (
        manifest_path.resolve()
        if manifest_path is not None
        else workspace.parent / PACKAGE_MANIFEST
    )
    manifest: dict = {}
    if not manifest_path.is_file():
        issues.append(
            {
                "code": "W009",
                "path": str(manifest_path),
                "message": "缺少 workspace 外的 executor package manifest",
            }
        )
    else:
        try:
            manifest = read_json(manifest_path)
        except BenchmarkError as exc:
            issues.append({"code": "W012", "path": str(manifest_path), "message": str(exc)})
    profile = manifest.get("profile", "pipeline_candidate")
    if profile not in {"pipeline_candidate", "public_task_only"}:
        issues.append({"code": "W015", "path": str(manifest_path), "message": f"未知 profile: {profile}"})

    if profile == "pipeline_candidate":
        skills_dir = workspace / "skills"
        for name in REQUIRED_SKILLS:
            skill_file = skills_dir / name / "SKILL.md"
            if not skill_file.is_file():
                issues.append(
                    {
                        "code": "W003",
                        "path": str(skill_file.relative_to(workspace)),
                        "message": "缺少候选 skill",
                    }
                )

        try:
            bundle = read_json(BUNDLE_MANIFEST)
        except BenchmarkError as exc:
            issues.append({"code": "W004", "path": str(BUNDLE_MANIFEST), "message": str(exc)})
            bundle = {"tools": []}
        expected = {
            entry.get("name"): entry.get("sha256")
            for entry in bundle.get("tools", [])
            if isinstance(entry, dict)
        }

        tools_dir = workspace / "tools"
        for name in EXECUTOR_TOOLS:
            target = tools_dir / name
            if not target.is_file():
                issues.append({"code": "W005", "path": f"tools/{name}", "message": "缺少考生运行工具"})
                continue
            expected_hash = expected.get(name)
            actual_hash = sha256_file(target)
            if expected_hash != actual_hash:
                issues.append(
                    {
                        "code": "W006",
                        "path": f"tools/{name}",
                        "message": f"工具 SHA 不匹配: expected={expected_hash}, actual={actual_hash}",
                    }
                )

        local_modules = {Path(name).stem for name in EXECUTOR_TOOLS}
        stdlib = standard_library_modules()
        for name in EXECUTOR_TOOLS:
            target = tools_dir / name
            if not target.is_file():
                continue
            try:
                imports = local_imports(target)
            except BenchmarkError as exc:
                issues.append({"code": "W007", "path": f"tools/{name}", "message": str(exc)})
                continue
            missing = sorted(
                module
                for module in imports
                if module not in local_modules and module not in stdlib and module != "__future__"
            )
            if missing:
                issues.append(
                    {
                        "code": "W008",
                        "path": f"tools/{name}",
                        "message": f"存在未打包的本地/第三方导入: {', '.join(missing)}",
                    }
                )

    if manifest:
        try:
            hashes = manifest.get("files")
            if not isinstance(hashes, dict):
                raise BenchmarkError("manifest.files 必须是 object")
            for relative, expected_hash in hashes.items():
                target = workspace / relative
                if not target.is_file():
                    issues.append({"code": "W010", "path": relative, "message": "manifest 文件缺失"})
                elif sha256_file(target) != expected_hash:
                    issues.append({"code": "W011", "path": relative, "message": "manifest SHA 不匹配"})
        except BenchmarkError as exc:
            issues.append({"code": "W012", "path": str(manifest_path), "message": str(exc)})

    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace)
        if is_forbidden_path(relative):
            component = next(
                (part for part in relative.parts if part.lower() in FORBIDDEN_COMPONENTS),
                relative.name,
            )
            issues.append(
                {
                    "code": "W013",
                    "path": relative.as_posix(),
                    "message": f"候选 workspace 含 grader-only 路径组件: {component}",
                }
            )

    xdev = workspace / "tools" / "xdev.py"
    if (
        profile == "pipeline_candidate"
        and xdev.is_file()
        and not any(issue["code"] in {"W005", "W006", "W008"} for issue in issues)
    ):
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [sys.executable, str(xdev), "--help"],
            cwd=workspace,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if completed.returncode != 0:
            issues.append(
                {
                    "code": "W014",
                    "path": "tools/xdev.py",
                    "message": f"xdev CLI 无法启动: exit={completed.returncode}, stderr={completed.stderr[-300:]}",
                }
            )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    issues = validate_workspace(args.workspace, args.manifest)
    result = {"valid": not issues, "workspace": str(args.workspace.resolve()), "issues": issues}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif issues:
        for issue in issues:
            print(f"{issue['code']} {issue['path']}: {issue['message']}")
    else:
        print("workspace preflight: PASS")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
