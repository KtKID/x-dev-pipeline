#!/usr/bin/env python3
"""xdev verify 的确定性执行引擎。

承接父 spec 声明 ``spec_version: 3`` 的
``docs/spec/<spec>/tasks/<task>/``，按 checklist 的 Scenario 限定验收范围。

公开 CLI 由 ``x-dev/scripts/xdev.py`` 提供；本模块负责 verify block 解析、命令执行、
验收覆盖对账和退出码。
"""

from __future__ import annotations

import json
import importlib
import importlib.util
import re
import subprocess
import sys
from pathlib import Path


def _load_sibling_engine(module_name: str, skill_name: str):
    """从同一插件的所属 skill 加载引擎；扁平执行包优先使用同目录副本。"""
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    skills_root = Path(__file__).resolve().parents[2]
    path = skills_root / skill_name / "scripts" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 {skill_name} 的 {module_name}.py：{path}")
    engine = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = engine
    try:
        spec.loader.exec_module(engine)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return engine


def _engine(module_name: str, skill_name: str):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        return _load_sibling_engine(module_name, skill_name)


req = _engine("req", "x-req")


VERIFY_FENCE_RE = re.compile(r"^\s*```verify\s*$", re.IGNORECASE)
FENCE_END_RE = re.compile(r"^\s*```\s*$")

VERIFY_KEYS = {
    "id", "scenario", "cmd", "cwd", "expect_exit", "expect_contains", "timeout", "mode", "steps",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def latest_dev_report(task_dir: Path) -> Path:
    reports = [path for path in task_dir.glob("dev-report*.md") if path.is_file()]
    if not reports:
        raise FileNotFoundError(f"缺少 dev-report*.md：{task_dir}")
    return max(reports, key=lambda path: (path.stat().st_mtime_ns, path.name))


def parse_verify_blocks(report: Path) -> list[dict]:
    """解析 fenced verify 块；格式错误统一提升为 ValueError。"""
    blocks: list[dict] = []
    ids: set[str] = set()
    lines = read_text(report).splitlines()
    index = 0
    while index < len(lines):
        if not VERIFY_FENCE_RE.match(lines[index]):
            index += 1
            continue
        start_line = index + 1
        index += 1
        raw_lines: list[tuple[int, str]] = []
        while index < len(lines) and not FENCE_END_RE.match(lines[index]):
            raw_lines.append((index + 1, lines[index]))
            index += 1
        if index == len(lines):
            raise ValueError(f"verify 块第 {start_line} 行未闭合")
        index += 1

        values: dict[str, object] = {"expect_contains": []}
        seen: set[str] = set()
        for line_number, raw in raw_lines:
            line = raw.strip()
            if not line:
                continue
            if ":" not in line:
                raise ValueError(f"verify 块第 {start_line} 行第 {line_number} 行格式应为 key: value")
            key, value = (part.strip() for part in line.split(":", 1))
            if key not in VERIFY_KEYS:
                raise ValueError(f"verify 块第 {start_line} 行存在未知 key：{key}")
            if not value:
                raise ValueError(f"verify 块第 {start_line} 行的 {key} 不能为空")
            if key == "expect_contains":
                values["expect_contains"].append(value)
                continue
            if key in seen:
                raise ValueError(f"verify 块第 {start_line} 行的 {key} 重复")
            seen.add(key)
            values[key] = value

        ident = str(values.get("id", "")).strip()
        if not ident:
            raise ValueError(f"verify 块第 {start_line} 行缺少 id")
        if ident in ids:
            raise ValueError(f"verify 块 id 重复：{ident}")
        ids.add(ident)
        mode = str(values.get("mode", "auto")).lower()
        if mode not in {"auto", "manual"}:
            raise ValueError(f"verify 块 {ident} 的 mode 必须为 auto 或 manual")
        if mode == "auto" and not str(values.get("cmd", "")).strip():
            raise ValueError(f"verify 块 {ident} 的 auto 模式缺少 cmd")
        if mode == "manual" and not str(values.get("steps", "")).strip():
            raise ValueError(f"verify 块 {ident} 的 manual 模式缺少 steps")
        try:
            expect_exit = int(str(values.get("expect_exit", "0")))
        except ValueError as exc:
            raise ValueError(f"verify 块 {ident} 的 expect_exit 必须是整数") from exc
        timeout = None
        if "timeout" in values:
            try:
                timeout = int(str(values["timeout"]))
            except ValueError as exc:
                raise ValueError(f"verify 块 {ident} 的 timeout 必须是正整数") from exc
            if timeout <= 0:
                raise ValueError(f"verify 块 {ident} 的 timeout 必须是正整数")
        blocks.append({
            "id": ident,
            "scenario": str(values.get("scenario", "")).strip(),
            "cmd": str(values.get("cmd", "")).strip(),
            "cwd": str(values.get("cwd", ".")).strip(),
            "expect_exit": expect_exit,
            "expect_contains": list(values["expect_contains"]),
            "timeout": timeout,
            "mode": mode,
            "steps": str(values.get("steps", "")).strip(),
            "line": start_line,
        })

    return blocks


def project_root_of_task_dir(task_dir: Path) -> Path | None:
    """从 req task 实际位置推出项目根（``docs/`` 的上一级）。"""
    parents = task_dir.resolve().parents
    return parents[4] if len(parents) >= 5 else None


def verify_cwd(raw_cwd: str, block_id: str, root: Path, root_name: str) -> Path:
    candidate = (root / raw_cwd).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"verify 块 {block_id} 的 cwd 必须是{root_name}内相对路径：{raw_cwd}") from exc
    if not candidate.is_dir():
        raise ValueError(f"verify 块 {block_id} 的 cwd 不存在或不是目录：{raw_cwd}")
    return candidate


def execute_verify_block(block: dict, root: Path, root_name: str) -> dict:
    cwd = verify_cwd(block["cwd"], block["id"], root, root_name)
    timed_out = False
    try:
        result = subprocess.run(
            block["cmd"], shell=True, cwd=cwd, text=True, capture_output=True,
            timeout=block["timeout"], check=False,
        )
        exit_code = result.returncode
        output = (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        output = stdout + stderr
    missing_contains = [text for text in block["expect_contains"] if text not in output]
    failed = timed_out or exit_code != block["expect_exit"] or bool(missing_contains)
    return {
        "id": block["id"],
        "scenario": block["scenario"],
        "cmd": block["cmd"],
        "exit_code": exit_code,
        "expected_exit": block["expect_exit"],
        "missing_contains": missing_contains,
        "timed_out": timed_out,
        "output_tail": output,
        "pass": not failed,
    }


def execute_verify_blocks(
    blocks: list[dict], only: str | None, root: Path, root_name: str,
) -> tuple[list[dict], list[dict], list[dict], set[str]]:
    """筛选并执行 auto 块，同时返回全部 manual 与 auto 场景声明。"""
    all_auto = [block for block in blocks if block["mode"] == "auto"]
    if only is not None:
        selected = [block for block in all_auto if block["id"] == only]
        if not selected:
            raise ValueError(f"未找到 auto verify 块：{only}")
    else:
        selected = all_auto
    manual = [
        {"id": block["id"], "scenario": block["scenario"], "steps": block["steps"]}
        for block in blocks if block["mode"] == "manual"
    ]
    results = [execute_verify_block(block, root, root_name) for block in selected]
    pass_items = [
        {key: value for key, value in result.items() if key != "output_tail"}
        for result in results if result["pass"]
    ]
    fail_items = [
        {key: value for key, value in result.items() if key != "pass"}
        for result in results if not result["pass"]
    ]
    declared_auto = {block["scenario"].strip() for block in all_auto if block["scenario"].strip()}
    return pass_items, fail_items, manual, declared_auto


def emit_payload(payload: dict, as_json: bool, requirements: list[str] | None = None) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"== {payload['task']} verify")
        if requirements is not None:
            print(f"  requirements: {'、'.join(requirements) if requirements else '(无验收绑定)'}")
        print(
            f"  pass: {len(payload['pass'])} · fail: {len(payload['fail'])} "
            f"· manual: {len(payload['manual'])}"
        )
        for item in payload["fail"]:
            print(f"  ! {item['id']} exit={item['exit_code']} expected={item['expected_exit']}")
        for name in payload["uncovered"]:
            print(f"  ! uncovered scenario: {name}")
    return 0 if not payload["fail"] and not payload["uncovered"] else 1


def verify_req(task_dir: Path, as_json: bool, only: str | None) -> int:
    """验证 req task；unit/smoke 必须 auto，e2e 必须声明 auto 或 manual。"""
    try:
        if not task_dir.is_dir():
            raise FileNotFoundError(f"不是目录：{task_dir}")
        spec_path = req.spec_of_task_dir(task_dir)
        if spec_path is None:
            raise ValueError(f"{task_dir} 不在 docs/spec/<spec-name>/tasks/<task-name>/ 结构下")
        spec_dir = req.resolve_spec_dir(task_dir)
        if spec_dir is None:
            raise ValueError(f"{task_dir} 的上级不是合法 spec_version: 3 包")
        spec_md = spec_dir / "spec.md"
        scope = req.task_scenarios(task_dir)
        scenarios = req.spec_scenarios(spec_md)
        by_id = {item["id"]: item for item in scenarios}
        if dangling := [scenario_id for scenario_id in scope if scenario_id not in by_id]:
            raise ValueError(
                f"checklist 承接的 Scenario 在 {spec_md} 中不存在：{'、'.join(dangling)}"
            )
        malformed = [
            scenario_id for scenario_id in scope
            if by_id[scenario_id]["layer"] not in {"unit", "smoke", "e2e"}
        ]
        if malformed:
            raise ValueError(
                f"{spec_md} 的 Scenario 缺少合法测试层：{'、'.join(malformed)}"
            )

        project_root = project_root_of_task_dir(task_dir)
        if project_root is None:
            raise ValueError(f"无法从 {task_dir} 推出项目根")
        report = latest_dev_report(task_dir)
        blocks = parse_verify_blocks(report)
        pass_items, fail_items, manual, declared_auto = execute_verify_blocks(
            blocks, only, project_root, "项目",
        )
        declared_manual = {
            item["scenario"].strip() for item in manual if item["scenario"].strip()
        }
        expected_auto = [
            scenario_id for scenario_id in scope
            if by_id[scenario_id]["layer"] in {"unit", "smoke"}
        ]
        expected_declared = [
            scenario_id for scenario_id in scope
            if by_id[scenario_id]["layer"] == "e2e"
        ]
        uncovered = [name for name in expected_auto if name not in declared_auto]
        uncovered.extend(
            name for name in expected_declared
            if name not in declared_auto and name not in declared_manual
        )
        payload = {
            "task": task_dir.name,
            "spec": spec_path,
            "profile": "req",
            "dev_report": str(report),
            "scenarios": scope,
            "scenario_layers": {
                scenario_id: by_id[scenario_id]["layer"] for scenario_id in scope
            },
            "expected_auto": expected_auto,
            "expected_declared": expected_declared,
            "pass": pass_items,
            "fail": fail_items,
            "manual": manual,
            "uncovered": list(dict.fromkeys(uncovered)),
        }
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    return emit_payload(payload, as_json)


def verify(task_dir: Path, as_json: bool, only: str | None) -> int:
    """验证父 spec 声明 spec_version: 3 的 task。"""
    return verify_req(task_dir, as_json, only)
