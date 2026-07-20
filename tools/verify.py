#!/usr/bin/env python3
"""xdev verify 的确定性执行引擎。

只承接 ``docs/spec/<spec>/tasks/<task>/`` 结构：验收场景来自归属
``spec.md``，对账范围由 ``dev-checklist.md`` 承接的 Requirement 决定。

公开 CLI 仍由 ``tools/xdev.py`` 提供；本模块负责 verify block 解析、命令执行、
验收覆盖对账和退出码。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import req


REQ_RE = re.compile(r"^###\s+Requirement:\s*(.*)$")
SCEN_RE = re.compile(r"^####\s+Scenario:\s*(.*)$")
H2_RE = re.compile(r"^##\s+")
H3_RE = re.compile(r"^###\s+")
H4_RE = re.compile(r"^####\s+")
VALIDATION_RE = re.compile(r"^\s*[-*+]?\s*验证\s*[：:]\s*(auto|manual)\s*$", re.IGNORECASE)
VERIFY_FENCE_RE = re.compile(r"^\s*```verify\s*$", re.IGNORECASE)
FENCE_END_RE = re.compile(r"^\s*```\s*$")

VERIFY_KEYS = {
    "id", "scenario", "cmd", "cwd", "expect_exit", "expect_contains", "timeout", "mode", "steps",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def section_bounds(lines: list[str], prefix: str) -> tuple[int | None, int]:
    """返回指定 H2 的起始与结束索引；缺失时起始为 None。"""
    start = next(
        (index for index, line in enumerate(lines) if H2_RE.match(line) and line[3:].strip().startswith(prefix)),
        None,
    )
    if start is None:
        return None, len(lines)
    end = next((index for index in range(start + 1, len(lines)) if H2_RE.match(lines[index])), len(lines))
    return start, end


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


def acceptance_scenarios(spec_md: Path) -> list[dict]:
    """读取 req2 spec.md「验收」节的 Scenario、父 Requirement 和验证标记。"""
    if not spec_md.exists():
        raise FileNotFoundError(f"缺少 spec.md：{spec_md.parent}")
    lines = read_text(spec_md).splitlines()
    start, end = section_bounds(lines, "验收")
    if start is None:
        return []
    scenarios: list[dict] = []
    requirement = ""
    current: tuple[str, list[str]] | None = None

    def close_current() -> None:
        nonlocal current
        if current is None:
            return
        name, body = current
        marker = next((match.group(1).lower() for line in body if (match := VALIDATION_RE.match(line))), None)
        scenarios.append({"requirement": requirement, "name": name, "mode": marker})
        current = None

    for index in range(start + 1, end):
        line = lines[index]
        if (requirement_match := REQ_RE.match(line)):
            close_current()
            requirement = requirement_match.group(1).strip()
            continue
        if (scenario_match := SCEN_RE.match(line)):
            close_current()
            current = (scenario_match.group(1).strip(), [])
            continue
        if H3_RE.match(line) or H4_RE.match(line):
            close_current()
            if H3_RE.match(line):
                requirement = ""
            continue
        if current is not None:
            current[1].append(line)
    close_current()
    return scenarios


def acceptance_defects(spec_md: Path, scope: list[str] | None = None) -> list[str]:
    """返回让 req2 验收对账无法进行的 spec 标注缺陷。"""
    scenarios = acceptance_scenarios(spec_md)

    def concerns_task(item: dict) -> bool:
        return scope is None or not item["requirement"] or item["requirement"] in scope

    orphans = dict.fromkeys(
        item["name"] for item in scenarios
        if item["mode"] == "auto" and not item["requirement"]
    )
    unmarked = dict.fromkeys(
        item["name"] for item in scenarios
        if item["mode"] is None and concerns_task(item)
    )
    return (
        [f"场景「{name}」缺少父 ### Requirement:" for name in orphans]
        + [f"场景「{name}」缺少合法的「验证: auto|manual」标记" for name in unmarked]
    )


def task_requirements(task_dir: Path) -> list[str]:
    """按声明顺序去重返回 req2 task checklist 承接的 Requirement 名。"""
    names: list[str] = []
    for row in req.parse_checklist(task_dir):
        value = row["requirement"]
        if value is None:
            raise ValueError(f"dev-checklist.md 表头缺 Requirement 列：{task_dir}")
        if not value:
            raise ValueError(
                f"dev-checklist.md 第 {row['line']} 行 {row['id']} 的 Requirement 为空；"
                "纯技术行须显式写 None"
            )
        if value != "None":
            names.append(value)
    return list(dict.fromkeys(names))


def project_root_of_task_dir(task_dir: Path) -> Path | None:
    """从 req2 task 实际位置推出项目根（``docs/`` 的上一级）。"""
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


def verify_req2(task_dir: Path, as_json: bool, only: str | None) -> int:
    """验证 req2 task，并把场景对账限定在本 task 承接的 Requirement 内。"""
    try:
        if not task_dir.is_dir():
            raise FileNotFoundError(f"不是目录：{task_dir}")
        spec_path = req.spec_of_task_dir(task_dir)
        if spec_path is None:
            raise ValueError(f"{task_dir} 不在 docs/spec/<spec-name>/tasks/<task-name>/ 结构下")
        spec_dir = req.resolve_spec_dir(task_dir)
        if spec_dir is None:
            raise ValueError(f"{task_dir} 的上级不是合法 spec 包（缺 spec.md/modules.md）")
        spec_md = spec_dir / "spec.md"
        scope = task_requirements(task_dir)
        known = set(req.spec_requirements(spec_md))
        if (dangling := [name for name in scope if name not in known]):
            raise ValueError(
                f"checklist 承接的 Requirement 在 {spec_md} 验收中不存在：{'、'.join(dangling)}"
            )
        if (defects := acceptance_defects(spec_md, scope)):
            raise ValueError(
                f"{spec_md} 的验收标注不足以判定本 task 的范围：" + "；".join(defects)
            )
        project_root = project_root_of_task_dir(task_dir)
        if project_root is None:
            raise ValueError(f"无法从 {task_dir} 推出项目根")
        report = latest_dev_report(task_dir)
        blocks = parse_verify_blocks(report)
        pass_items, fail_items, manual, declared_auto = execute_verify_blocks(
            blocks, only, project_root, "项目",
        )
        expected_auto = list(dict.fromkeys(
            item["name"] for item in acceptance_scenarios(spec_md)
            if item["mode"] == "auto" and item["requirement"] in scope
        ))
        uncovered = [name for name in expected_auto if name.strip() not in declared_auto]
        payload = {
            "task": task_dir.name,
            "spec": spec_path,
            "dev_report": str(report),
            "requirements": scope,
            "expected_auto": expected_auto,
            "pass": pass_items,
            "fail": fail_items,
            "manual": manual,
            "uncovered": uncovered,
        }
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    return emit_payload(payload, as_json, scope)


def verify(task_dir: Path, as_json: bool, only: str | None) -> int:
    """验证 ``docs/spec/<spec>/tasks/<task>`` 结构。"""
    return verify_req2(task_dir, as_json, only)
