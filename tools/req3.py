#!/usr/bin/env python3
"""x-req3 的确定性 task 引擎。

输入是 ``docs/spec/<spec>/spec.md`` 单文件 spec3 包，task 位于
``docs/spec/<spec>/tasks/<task>/``。本模块负责 scaffold、Scenario 追踪、
spec 级覆盖和可选边界图一致性；状态与依赖图复用 req2 的通用 checklist 引擎。
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import req


PLUGIN_ROOT = Path(__file__).resolve().parent.parent

ARTIFACTS = {
    "dev-checklist": {
        "generates": "dev-checklist.md",
        "template": "skills/x-req3/templates/dev-checklist.md",
        "instruction": "按 spec3 Scenario 拆任务；只保存执行信息、风险证据和精确回指。",
    },
    "diagram": {
        "generates": "diagram.md",
        "template": "skills/x-req3/templates/diagram.md",
        "instruction": "把影响边界表投影为模块图，每个声明模块恰好一个节点。",
    },
}

SPEC3_MARKER_RE = re.compile(r"^>\s*spec_version:\s*3\s*$", re.IGNORECASE)
SCENARIO_RE = re.compile(r"^###\s+Scenario\s+(SC_[0-9]{2})\s*:\s*(.+?)\s*$")
SCENARIO_HEADING_RE = re.compile(r"^###\s+Scenario\b", re.IGNORECASE)
SCENARIO_IDS_CELL_RE = re.compile(r"^SC_[0-9]{2}(?:\s*,\s*SC_[0-9]{2})*$")
H3_RE = re.compile(r"^###\s+")
GWT_RE = re.compile(r"^\s*[-*+]\s*\*\*(GIVEN|WHEN|THEN)\*\*", re.IGNORECASE)
LAYER_RE = re.compile(r"^\s*[-*+]?\s*测试层\s*[：:]\s*(unit|smoke|e2e)\s*$", re.IGNORECASE)
EVIDENCE_RE = re.compile(r"^\s*[-*+]?\s*依据\s*[：:]\s*(.+?)\s*$", re.IGNORECASE)
MODEL_TUPLE = ("数据流", "状态", "时序", "资源", "不变量", "故障")
REQUIRED_SECTIONS = (
    "任务目标",
    "非目标",
    "影响边界与不变量",
    "判断依据",
    "建模覆盖声明",
    "验收清单",
    "测试驱动开发",
    "Scenarios",
)

CHECKLIST_HEADER_KEYWORDS = {
    "id": ("#", "编号"),
    "title": ("任务说明", "任务", "标题"),
    "scenario": ("Scenario",),
    "risk": ("风险",),
    "file": ("涉及文件", "文件"),
    "dep": ("依赖",),
    "status": ("状态",),
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def has_spec3_marker(spec_dir: Path) -> bool:
    spec_md = spec_dir / "spec.md"
    if not spec_md.is_file():
        return False
    return any(SPEC3_MARKER_RE.match(line.strip()) for line in read_text(spec_md).splitlines())


def resolve_spec_dir(task_dir: Path) -> Path | None:
    """返回 task 所属 spec3 包；结构或版本不匹配时返回 None。"""
    parents = task_dir.resolve().parents
    if len(parents) < 2:
        return None
    candidate = parents[1]
    if has_spec3_marker(candidate):
        return candidate
    return None


def artifact_template(artifact_id: str) -> str:
    return read_text(PLUGIN_ROOT / ARTIFACTS[artifact_id]["template"])


def artifact_payload(artifact_id: str, task_dir: Path) -> dict:
    entry = ARTIFACTS[artifact_id]
    return {
        "artifact": artifact_id,
        "output_path": str(task_dir / entry["generates"]),
        "exists": (task_dir / entry["generates"]).exists(),
        "template": artifact_template(artifact_id),
        "instruction": entry["instruction"],
        "requires": [],
        "dependencies": [],
        "profile": "req3",
    }


def instructions(artifact_id: str, task_dir: Path, as_json: bool) -> int:
    if artifact_id not in ARTIFACTS:
        print(f"错误：req3 不支持 artifact「{artifact_id}」", file=sys.stderr)
        return 2
    try:
        payload = artifact_payload(artifact_id, task_dir)
    except OSError as exc:
        print(f"错误：读取 req3 模板失败：{exc}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"== {artifact_id} instructions [req3]\n")
        print(payload["template"])
        print(f"\n== instruction\n\n{payload['instruction']}")
    return 0


def scaffold(task_dir: Path, with_diagram: bool, as_json: bool) -> int:
    spec_path = req.spec_of_task_dir(task_dir)
    spec_dir = resolve_spec_dir(task_dir)
    if spec_path is None or spec_dir is None:
        print(
            f"错误：{task_dir} 必须位于含 spec_version: 3 的 docs/spec/<spec>/tasks/<task>/",
            file=sys.stderr,
        )
        return 2

    artifact_ids = ["dev-checklist"] + (["diagram"] if with_diagram else [])
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
                content = content.replace(
                    "> spec: docs/spec/<spec-name>", f"> spec: {spec_path}", 1,
                )
            else:
                content = content.replace("<TASK_NAME>", task_dir.name, 1)
            path.write_text(content, encoding="utf-8")
            created.append(str(path))
    except OSError as exc:
        print(f"错误：scaffold 无法写入 {task_dir}：{exc}", file=sys.stderr)
        return 2

    payload = {
        "task": str(task_dir),
        "spec": spec_path,
        "profile": "req3",
        "created": created,
        "skipped": skipped,
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"== scaffold {task_dir} [req3]")
        for path in created:
            print(f"  created: {path}")
        for path in skipped:
            print(f"  skipped: {path}")
    return 0


def spec_scenarios(spec_md: Path) -> list[dict]:
    """读取 spec3 的直接 Scenario，分别返回稳定 ID 与可编辑语义名。"""
    if not spec_md.is_file():
        return []
    lines = read_text(spec_md).splitlines()
    start, end = req.section_bounds(lines, "Scenarios")
    if start is None:
        return []
    scenarios: list[dict] = []
    current: dict | None = None

    def close_current() -> None:
        nonlocal current
        if current is None:
            return
        body = current["body"]
        current["gwt"] = {
            match.group(1).upper()
            for _line, value in body
            if (match := GWT_RE.match(value))
        }
        current["layer"] = next(
            (match.group(1).lower() for _line, value in body if (match := LAYER_RE.match(value))),
            None,
        )
        current["evidence"] = next(
            (match.group(1).strip() for _line, value in body if (match := EVIDENCE_RE.match(value))),
            None,
        )
        scenarios.append(current)
        current = None

    for index in range(start + 1, end):
        value = lines[index]
        if (match := SCENARIO_RE.match(value)):
            close_current()
            current = {
                "id": match.group(1).upper(),
                "name": match.group(2).strip(),
                "line": index + 1,
                "body": [],
            }
            continue
        if H3_RE.match(value):
            close_current()
            continue
        if current is not None:
            current["body"].append((index + 1, value))
    close_current()
    return scenarios


def scenario_id_counts(spec_md: Path) -> Counter:
    return Counter(item["id"] for item in spec_scenarios(spec_md))


def parse_scenario_ids(value: str) -> list[str]:
    """解析 checklist 的 Scenario IDs 单元格；None 返回空列表。"""
    value = value.strip()
    if value == "None":
        return []
    if not SCENARIO_IDS_CELL_RE.fullmatch(value):
        raise ValueError("Scenario IDs 必须为 SC_01 或 SC_01, SC_02；纯技术行写 None")
    ids = [item.strip() for item in value.split(",")]
    if len(ids) != len(set(ids)):
        raise ValueError("Scenario IDs 单元格存在重复 ID")
    return ids


def _section_table(spec_md: Path, prefix: str) -> tuple[list[str] | None, list[tuple[int, list[str]]]]:
    lines = read_text(spec_md).splitlines()
    start, end = req.section_bounds(lines, prefix)
    if start is None:
        return None, []
    return req.first_table("\n".join(lines[start + 1 : end]))


def boundary_module_names(spec_dir: Path) -> dict[str, str]:
    spec_md = spec_dir / "spec.md"
    if not spec_md.is_file():
        return {}
    header, rows = _section_table(spec_md, "影响边界与不变量")
    if not header:
        return {}
    module_idx = next((index for index, name in enumerate(header) if "模块" in name), None)
    if module_idx is None:
        return {}
    modules: dict[str, str] = {}
    for _line, row in rows:
        if module_idx >= len(row):
            continue
        original = row[module_idx].strip()
        normalized = req.normalize_module_name(original)
        if normalized:
            modules[normalized] = original
    return modules


def spec3_contract_issues(spec_dir: Path) -> list[dict]:
    """返回 spec3 单文件契约的机械问题，供 xdev V19/V20 使用。"""
    spec_md = spec_dir / "spec.md"
    if not spec_md.is_file():
        return [req.issue("(package)", 0, "V19", "spec3 包缺少 spec.md")]
    text = read_text(spec_md)
    lines = text.splitlines()
    issues: list[dict] = []
    if not any(SPEC3_MARKER_RE.match(line.strip()) for line in lines):
        issues.append(req.issue("spec.md", 0, "V19", "缺少 > spec_version: 3 标记"))

    for section in REQUIRED_SECTIONS:
        start, _end = req.section_bounds(lines, section)
        if start is None:
            issues.append(req.issue("spec.md", 0, "V19", f"缺少二级节「{section}」"))

    boundary_header, boundary_rows = _section_table(spec_md, "影响边界与不变量")
    boundary_required = ("模块", "角色", "本次影响", "主要风险", "必须保持的不变量", "依据")
    if not boundary_header or any(name not in boundary_header for name in boundary_required):
        issues.append(req.issue("spec.md", 0, "V19", "影响边界表缺少固定列"))
    elif not boundary_rows:
        issues.append(req.issue("spec.md", 0, "V19", "影响边界表至少需要一个模块"))
    else:
        risk_idx = boundary_header.index("主要风险")
        for line, row in boundary_rows:
            if risk_idx >= len(row) or not row[risk_idx].strip():
                issues.append(req.issue("spec.md", line, "V19", "影响边界模块的主要风险为空"))

    model_header, model_rows = _section_table(spec_md, "建模覆盖声明")
    model_values = {row[0].strip() for _line, row in model_rows if row}
    if not model_header or any(name not in model_values for name in MODEL_TUPLE):
        missing = [name for name in MODEL_TUPLE if name not in model_values]
        issues.append(req.issue("spec.md", 0, "V19", f"建模覆盖声明缺少：{'、'.join(missing)}"))

    scenarios = spec_scenarios(spec_md)
    scenarios_start, scenarios_end = req.section_bounds(lines, "Scenarios")
    if scenarios_start is not None:
        for index in range(scenarios_start + 1, scenarios_end):
            value = lines[index]
            if SCENARIO_HEADING_RE.match(value) and not SCENARIO_RE.match(value):
                issues.append(req.issue(
                    "spec.md", index + 1, "V20",
                    "Scenario 标题必须为 `### Scenario SC_01: <可判定行为名称>`",
                ))
    if not scenarios:
        issues.append(req.issue("spec.md", 0, "V20", "Scenarios 节至少需要一个 Scenario"))
    id_counts = Counter(item["id"] for item in scenarios)
    name_counts = Counter(item["name"] for item in scenarios)
    actual_ids = [item["id"] for item in scenarios]
    expected_ids = [f"SC_{index:02d}" for index in range(1, len(scenarios) + 1)]
    if actual_ids != expected_ids:
        issues.append(req.issue(
            "spec.md", 0, "V20",
            "Scenario ID 必须从 SC_01 开始按文档顺序连续递增",
        ))
    for item in scenarios:
        scenario_id = item["id"]
        name = item["name"] or "(空)"
        if id_counts[scenario_id] > 1:
            issues.append(req.issue(
                "spec.md", item["line"], "V20", f"Scenario ID 重复：{scenario_id}",
            ))
        if name_counts[item["name"]] > 1:
            issues.append(req.issue("spec.md", item["line"], "V20", f"Scenario 名重名：{name}"))
        missing_gwt = [key for key in ("GIVEN", "WHEN", "THEN") if key not in item["gwt"]]
        if missing_gwt:
            issues.append(req.issue(
                "spec.md", item["line"], "V20", f"Scenario「{name}」缺少：{'、'.join(missing_gwt)}",
            ))
        if item["layer"] is None:
            issues.append(req.issue(
                "spec.md", item["line"], "V20", f"Scenario「{name}」缺少测试层 unit|smoke|e2e",
            ))
        if not item["evidence"]:
            issues.append(req.issue("spec.md", item["line"], "V20", f"Scenario「{name}」缺少依据"))
    return issues


def parse_checklist(task_dir: Path) -> list[dict]:
    checklist = task_dir / "dev-checklist.md"
    if not checklist.is_file():
        raise FileNotFoundError(f"缺少 dev-checklist.md：{task_dir}")
    header, rows = req.first_table(read_text(checklist))
    if not header:
        raise ValueError(f"dev-checklist.md 无可解析表格：{checklist}")

    indexes = {
        key: req.col_idx(header, *keywords)
        for key, keywords in CHECKLIST_HEADER_KEYWORDS.items()
    }
    if indexes["id"] is None or indexes["status"] is None:
        missing = []
        if indexes["id"] is None:
            missing.append("#/编号 列")
        if indexes["status"] is None:
            missing.append("状态 列")
        raise ValueError(f"dev-checklist.md 表头缺关键列：{', '.join(missing)}")

    def cell(values: list[str], index: int | None) -> str:
        return values[index].strip() if index is not None and index < len(values) else ""

    parsed: list[dict] = []
    for line_no, values in rows:
        raw_id = cell(values, indexes["id"])
        match = req.ID_COL_RE.search(raw_id)
        if not raw_id or raw_id == "None" or match is None:
            continue
        raw_files = cell(values, indexes["file"])
        product_match = req.PRODUCT_RE.search(raw_files) if raw_files else None
        parsed.append({
            "id": f"T{match.group(1)}",
            "title": cell(values, indexes["title"]),
            "scenario": (
                cell(values, indexes["scenario"])
                if indexes["scenario"] is not None else None
            ),
            "risk": cell(values, indexes["risk"]),
            "deps": req.parse_deps(cell(values, indexes["dep"])),
            "raw_status": cell(values, indexes["status"]),
            "product": product_match.group(1) if product_match else None,
            "line": line_no,
        })
    return parsed


def task_scenarios(task_dir: Path) -> list[str]:
    scenario_ids: list[str] = []
    for row in parse_checklist(task_dir):
        value = row["scenario"]
        if value is None:
            raise ValueError(f"dev-checklist.md 表头缺 Scenario IDs 列：{task_dir}")
        if not value:
            raise ValueError(
                f"dev-checklist.md 第 {row['line']} 行 {row['id']} 的 Scenario IDs 为空；"
                "纯技术行须显式写 None"
            )
        scenario_ids.extend(parse_scenario_ids(value))
    return list(dict.fromkeys(scenario_ids))


def diagram_consistency_issues(task_dir: Path, spec_dir: Path | None) -> list[dict]:
    diagram = task_dir / "diagram.md"
    if not diagram.is_file() or spec_dir is None:
        return []
    declared = boundary_module_names(spec_dir)
    rendered = req.mermaid_modules(read_text(diagram))
    issues: list[dict] = []
    for name in sorted(declared.keys() - rendered.keys()):
        issues.append(req.issue(
            str(diagram), 0, "R3Q9", f"影响边界模块「{declared[name]}」缺少 Mermaid 节点",
        ))
    for name in sorted(rendered.keys() - declared.keys()):
        issues.append(req.issue(
            str(diagram), 0, "R3Q9", f"Mermaid 节点「{rendered[name]}」未在影响边界表声明",
        ))
    return issues


def validate_issues(task_dir: Path) -> list[dict]:
    checklist = task_dir / "dev-checklist.md"
    if not checklist.is_file():
        return [req.issue(str(task_dir), 0, "R3Q0", "缺少 dev-checklist.md")]
    text = read_text(checklist)
    issues: list[dict] = []
    spec_value = req.header_value(text, "spec")
    spec_dir = resolve_spec_dir(task_dir)
    declared = req.spec_of_task_dir(task_dir)
    if not spec_value:
        issues.append(req.issue(str(checklist), 0, "R3Q1", "头部缺少 spec: 指针"))
    elif spec_dir is None:
        issues.append(req.issue(str(checklist), 0, "R3Q1", "task 上级缺少合法 spec_version: 3 spec.md"))
    elif declared and spec_value.strip().rstrip("/") != declared:
        issues.append(req.issue(
            str(checklist), 0, "R3Q1",
            f"spec: 指针与 task 实际归属不符：头部写「{spec_value}」，实际位于「{declared}」",
        ))

    risk_value = req.header_value(text, "risk")
    if not risk_value:
        issues.append(req.issue(str(checklist), 0, "R3Q2", "头部缺少 risk: 取值"))
    elif risk_value.upper() not in req.RISK_VALUES:
        issues.append(req.issue(str(checklist), 0, "R3Q2", f"risk: 取值非法：{risk_value}"))

    try:
        rows = parse_checklist(task_dir)
    except (FileNotFoundError, ValueError) as exc:
        issues.append(req.issue(str(checklist), 0, "R3Q3", str(exc)))
        return issues

    scenario_counts = scenario_id_counts(spec_dir / "spec.md") if spec_dir else None
    known_ids = {row["id"] for row in rows}
    for row in rows:
        if not row["title"]:
            issues.append(req.issue(str(checklist), row["line"], "R3Q4", f"{row['id']} 任务说明为空"))
        if not row["risk"]:
            issues.append(req.issue(str(checklist), row["line"], "R3Q4", f"{row['id']} 风险列为空"))
        for dependency in row["deps"]:
            if dependency not in known_ids:
                issues.append(req.issue(
                    str(checklist), row["line"], "R3Q8",
                    f"{row['id']} 依赖「{dependency}」不在 task 表中",
                ))
        if not req.is_legal_status(row["raw_status"]):
            issues.append(req.issue(
                str(checklist), row["line"], "R3Q7",
                f"{row['id']} 状态非法：{row['raw_status'] or '(空)'}",
            ))
        scenario = row["scenario"]
        if scenario is None:
            issues.append(req.issue(str(checklist), row["line"], "R3Q3", "表头缺 Scenario IDs 列"))
            continue
        if not scenario:
            issues.append(req.issue(
                str(checklist), row["line"], "R3Q5",
                f"{row['id']} Scenario IDs 为空；纯技术行须写 None",
            ))
            continue
        try:
            referenced_ids = parse_scenario_ids(scenario)
        except ValueError as exc:
            issues.append(req.issue(
                str(checklist), row["line"], "R3Q5", f"{row['id']} {exc}",
            ))
            continue
        if not referenced_ids or scenario_counts is None:
            continue
        for scenario_id in referenced_ids:
            count = scenario_counts.get(scenario_id, 0)
            if count == 0:
                issues.append(req.issue(
                    str(checklist), row["line"], "R3Q5",
                    f"{row['id']} Scenario ID 悬空：「{scenario_id}」不在 {spec_value}/spec.md 中",
                ))
            elif count > 1:
                issues.append(req.issue(
                    str(checklist), row["line"], "R3Q5",
                    f"{row['id']} Scenario ID 重复：「{scenario_id}」在 spec.md 中出现 {count} 次",
                ))
    issues.extend(diagram_consistency_issues(task_dir, spec_dir))
    return issues


def spec_scenario_coverage(spec_dir: Path) -> list[dict]:
    spec_md = spec_dir / "spec.md"
    scenario_ids = list(dict.fromkeys(item["id"] for item in spec_scenarios(spec_md)))
    covered: set[str] = set()
    tasks_dir = spec_dir / "tasks"
    if tasks_dir.is_dir():
        for task_dir in sorted(path for path in tasks_dir.iterdir() if path.is_dir()):
            try:
                rows = parse_checklist(task_dir)
            except (FileNotFoundError, ValueError):
                continue
            for row in rows:
                if row["scenario"] and row["scenario"] != "None":
                    try:
                        covered.update(parse_scenario_ids(row["scenario"]))
                    except ValueError:
                        continue
    return [
        req.issue(str(spec_md), 0, "R3Q6", f"Scenario「{scenario_id}」未被该 spec 下任何 task 承接")
        for scenario_id in scenario_ids if scenario_id not in covered
    ]


def status(task_dir: Path, as_json: bool) -> int:
    return req.status(task_dir, as_json)


def graph(task_dir: Path, as_json: bool) -> int:
    return req.graph(task_dir, as_json)
