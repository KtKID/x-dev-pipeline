#!/usr/bin/env python3
"""req — x-req2 的 task 确定性引擎，被 tools/xdev.py import 后按命令委托调用。

只服务 docs/spec/<spec-name>/tasks/<task-name>/ 结构，不识别旧结构。
当前只实现 scaffold；validate/status/graph/verify 见
openspec/changes/xreq-spec-driven/tasks.md 1.1.3-1.1.8，尚未落地。
不单独作主 CLI 入口（命令统一走 xdev.py，见 design.md 决策 A）。

退出码沿用 xdev.py 风格：0 正常；2 用法或 IO 错误。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

ARTIFACTS = {
    "dev-checklist": {
        "generates": "dev-checklist.md",
        "template": "skills/x-req2/templates/dev-checklist.md",
    },
    "diagram": {
        "generates": "diagram.md",
        "template": "skills/x-req2/templates/diagram.md",
    },
}


def read_text(f: Path) -> str:
    return f.read_text(encoding="utf-8", errors="replace")


def spec_of_task_dir(task_dir: Path) -> str | None:
    """校验 task_dir 是否落在 docs/spec/<spec-name>/tasks/<task-name>/，返回归属 spec 相对路径；不合法返回 None。"""
    parts = task_dir.resolve().parts
    for i in range(len(parts) - 4):
        if parts[i] == "docs" and parts[i + 1] == "spec" and parts[i + 3] == "tasks":
            return "/".join(("docs", "spec", parts[i + 2]))
    return None


def artifact_template(artifact_id: str) -> str:
    return read_text(PLUGIN_ROOT / ARTIFACTS[artifact_id]["template"])


def scaffold(task_dir: Path, with_diagram: bool, as_json: bool) -> int:
    """scaffold 子命令：只认 docs/spec/*/tasks/ 位置，生成 dev-checklist.md（不产 README）与按需 diagram.md；已有文件保持原状。"""
    spec_path = spec_of_task_dir(task_dir)
    if spec_path is None:
        print(
            f"错误：{task_dir} 不在 docs/spec/<spec-name>/tasks/<task-name>/ 结构下，"
            "req.py 不支持旧结构（dev-pipeline/tasks/）或其他路径",
            file=sys.stderr,
        )
        return 2

    artifact_ids = ["dev-checklist"]
    if with_diagram:
        artifact_ids.append("diagram")

    created: list[str] = []
    skipped: list[str] = []
    try:
        task_dir.mkdir(parents=True, exist_ok=True)
        for artifact_id in artifact_ids:
            path = task_dir / ARTIFACTS[artifact_id]["generates"]
            if path.exists():
                skipped.append(str(path))
                continue
            content = artifact_template(artifact_id)
            if artifact_id == "dev-checklist":
                content = content.replace("# <task-name>", f"# {task_dir.name}", 1)
                content = content.replace("> spec: docs/spec/<spec-name>", f"> spec: {spec_path}", 1)
            elif artifact_id == "diagram":
                content = content.replace("<TASK_NAME>", task_dir.name, 1)
            path.write_text(content, encoding="utf-8")
            created.append(str(path))
    except OSError as exc:
        print(f"错误：scaffold 无法写入 {task_dir}：{exc}", file=sys.stderr)
        return 2

    payload = {"task": str(task_dir), "spec": spec_path, "created": created, "skipped": skipped}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"== scaffold {task_dir}")
        print(f"  spec: {spec_path}")
        for path in created:
            print(f"  created: {path}")
        for path in skipped:
            print(f"  skipped: {path}")
    return 0
