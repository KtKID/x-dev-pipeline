#!/usr/bin/env python3
"""x-req3 的自包含确定性 task 引擎。

输入是 ``docs/spec/<spec>/spec.md`` 单文件 spec3 包，task 位于
``docs/spec/<spec>/tasks/<task>/``。本模块负责 scaffold、Scenario 追踪、
spec 级覆盖、可选边界图一致性、任务状态与依赖图。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import spec as spec_engine


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

SCENARIO_IDS_CELL_RE = re.compile(r"^SC_[0-9]{2}(?:\s*,\s*SC_[0-9]{2})*$")

CHECKLIST_HEADER_KEYWORDS = {
    "id": ("#", "编号"),
    "title": ("任务说明", "任务", "标题"),
    "scenario": ("Scenario",),
    "risk": ("风险",),
    "file": ("涉及文件", "文件"),
    "dep": ("依赖",),
    "status": ("状态",),
}


TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
SPEC_LINE_RE = re.compile(r"^>\s*spec:\s*(\S+)\s*$", re.IGNORECASE)
RISK_LINE_RE = re.compile(r"^>\s*risk:\s*(\S+)\s*$", re.IGNORECASE)
TASK_ID_RE = re.compile(r"(?:T|#)(\d+)", re.IGNORECASE)
ID_COL_RE = re.compile(r"(?:T|#)?(\d+)", re.IGNORECASE)
PRODUCT_RE = re.compile(r"product:\s*([^\s,;]+)")
RISK_VALUES = {"Q0", "Q1", "Q2", "Q3"}

DONE = "done"
TODO = "todo"
BLOCKED = "blocked"
TOKEN_RE = re.compile(r"\[(?P<box>[ x!])\]")
STATUS_EMOJI_MAP = {"🟢": DONE, "✅": DONE, "🔴": BLOCKED}

def issue(file: str, line: int, rule: str, msg: str) -> dict:
    return {"file": file, "line": line, "rule": rule, "msg": msg}


def cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def first_table(text: str):
    """返回第一个 markdown 表：(表头 cells, [(行号, cells), ...])；无表返回 (None, [])。"""
    lines = text.splitlines()
    i = 0
    while i < len(lines) - 1:
        if lines[i].lstrip().startswith("|") and TABLE_SEP_RE.match(lines[i + 1]):
            header = cells(lines[i])
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append((j + 1, cells(lines[j])))
                j += 1
            return header, rows
        i += 1
    return None, []


def spec_of_task_dir(task_dir: Path) -> str | None:
    """校验 task_dir 是否落在 docs/spec/<spec-name>/tasks/<task-name>/，返回归属 spec 相对路径；不合法返回 None。"""
    parts = task_dir.resolve().parts
    for i in range(len(parts) - 4):
        if parts[i] == "docs" and parts[i + 1] == "spec" and parts[i + 3] == "tasks":
            return "/".join(("docs", "spec", parts[i + 2]))
    return None


def header_value(text: str, key: str) -> str | None:
    """读取头部 `> spec: ...` / `> risk: ...` 行的取值；缺失返回 None。"""
    pattern = SPEC_LINE_RE if key == "spec" else RISK_LINE_RE
    for line in text.splitlines():
        m = pattern.match(line.strip())
        if m:
            return m.group(1)
    return None


def col_idx(header: list[str], *keywords: str) -> int | None:
    for kw in keywords:
        for i, c in enumerate(header):
            if kw in c:
                return i
    return None


def parse_deps(raw: str) -> list[str]:
    """解析依赖列：支持 'T1' / 'T2,T3' / 'T2/T3' / '#1 #2' / 'None' / '' → 归一化 id 列表。"""
    if not raw or raw.strip() == "None":
        return []
    ids = TASK_ID_RE.findall(raw)
    return [f"T{n}" for n in ids]


def task_engine_status(raw_status: str) -> str:
    """从状态列文本判定引擎状态（done/todo/blocked），token 优先、emoji 降级。"""
    m = TOKEN_RE.search(raw_status)
    if m:
        box = m.group("box")
        if box == "x":
            return DONE
        if box == "!":
            return BLOCKED
        return TODO
    for emoji, status in STATUS_EMOJI_MAP.items():
        if emoji in raw_status:
            return status
    return TODO


def is_legal_status(raw_status: str) -> bool:
    """R3Q7：状态列是否落在 status/graph 复用的同一词表内（已定义 token 或纯 emoji 兼容集合）。"""
    if TOKEN_RE.search(raw_status):
        return True
    return any(emoji in raw_status for emoji in STATUS_EMOJI_MAP)


def normalize_module_name(value: str) -> str:
    """归一化 Markdown/Mermaid 的节点标签，供 R3Q9 做词法双向比对。"""
    value = re.sub(r"<br\s*/?>.*$", "", value, flags=re.IGNORECASE)
    value = value.split("·", 1)[0]
    value = re.split(r"[：:]", value, maxsplit=1)[0]
    value = re.sub(r"[`*_]", "", value)
    return re.sub(r"[^0-9A-Za-z一-鿿]+", "", value).lower()


MERMAID_LABEL_RE = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*\s*(?:\[\s*\"([^\"]+)\"\s*\]|\[\s*([^\]]+)\s*\]|\(\s*\"([^\"]+)\"\s*\)|\(\s*([^\)]+)\s*\))"
)


def mermaid_modules(text: str) -> dict[str, str]:
    """提取所有 mermaid fenced block 中的节点标签。"""
    names: dict[str, str] = {}
    in_mermaid = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            marker = line.lstrip()[3:].strip().lower()
            if in_mermaid:
                in_mermaid = False
            elif marker == "mermaid":
                in_mermaid = True
            continue
        if not in_mermaid:
            continue
        for match in MERMAID_LABEL_RE.finditer(line):
            original = next(group for group in match.groups() if group is not None).strip()
            normalized = normalize_module_name(original)
            if normalized:
                names[normalized] = original
    return names



def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def has_spec3_marker(spec_dir: Path) -> bool:
    return spec_engine.has_spec3_marker(spec_dir)


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
    spec_path = spec_of_task_dir(task_dir)
    spec_dir = resolve_spec_dir(task_dir)
    if spec_path is None or spec_dir is None:
        print(
            f"错误：{task_dir} 必须位于含 spec_version: 3 的 docs/spec/<spec>/tasks/<task>/",
            file=sys.stderr,
        )
        return 2

    readiness_issues = spec3_contract_issues(spec_dir)
    if readiness_issues:
        details = "；".join(item["msg"] for item in readiness_issues)
        print(f"错误：spec3 未通过就绪门禁：{details}", file=sys.stderr)
        return 2

    diagram_required = len(boundary_module_names(spec_dir)) >= 3
    artifact_ids = ["dev-checklist"] + (["diagram"] if with_diagram or diagram_required else [])
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
    return spec_engine.spec_scenarios(spec_md)


def scenario_id_counts(spec_md: Path):
    return spec_engine.scenario_id_counts(spec_md)


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


def boundary_module_names(spec_dir: Path) -> dict[str, str]:
    return spec_engine.boundary_module_names(spec_dir)


def spec3_contract_issues(spec_dir: Path) -> list[dict]:
    """兼容 req3 调用面，spec3 文档契约由 spec 引擎统一实现。"""
    return spec_engine.validate_issues(spec_dir)


def parse_checklist(task_dir: Path) -> list[dict]:
    checklist = task_dir / "dev-checklist.md"
    if not checklist.is_file():
        raise FileNotFoundError(f"缺少 dev-checklist.md：{task_dir}")
    header, rows = first_table(read_text(checklist))
    if not header:
        raise ValueError(f"dev-checklist.md 无可解析表格：{checklist}")

    indexes = {
        key: col_idx(header, *keywords)
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
        match = ID_COL_RE.search(raw_id)
        if not raw_id or raw_id == "None" or match is None:
            continue
        raw_files = cell(values, indexes["file"])
        product_match = PRODUCT_RE.search(raw_files) if raw_files else None
        parsed.append({
            "id": f"T{match.group(1)}",
            "title": cell(values, indexes["title"]),
            "scenario": (
                cell(values, indexes["scenario"])
                if indexes["scenario"] is not None else None
            ),
            "risk": cell(values, indexes["risk"]),
            "deps": parse_deps(cell(values, indexes["dep"])),
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
    if spec_dir is None:
        return []
    declared = boundary_module_names(spec_dir)
    if len(declared) >= 3 and not diagram.is_file():
        return [issue(
            str(task_dir), 0, "R3Q9",
            f"影响边界包含 {len(declared)} 个模块，task 缺少必需的 diagram.md",
        )]
    if not diagram.is_file():
        return []
    rendered = mermaid_modules(read_text(diagram))
    issues: list[dict] = []
    for name in sorted(declared.keys() - rendered.keys()):
        issues.append(issue(
            str(diagram), 0, "R3Q9", f"影响边界模块「{declared[name]}」缺少 Mermaid 节点",
        ))
    for name in sorted(rendered.keys() - declared.keys()):
        issues.append(issue(
            str(diagram), 0, "R3Q9", f"Mermaid 节点「{rendered[name]}」未在影响边界表声明",
        ))
    return issues


def validate_issues(task_dir: Path) -> list[dict]:
    checklist = task_dir / "dev-checklist.md"
    if not checklist.is_file():
        return [issue(str(task_dir), 0, "R3Q0", "缺少 dev-checklist.md")]
    text = read_text(checklist)
    issues: list[dict] = []
    spec_value = header_value(text, "spec")
    spec_dir = resolve_spec_dir(task_dir)
    declared = spec_of_task_dir(task_dir)
    if not spec_value:
        issues.append(issue(str(checklist), 0, "R3Q1", "头部缺少 spec: 指针"))
    elif spec_dir is None:
        issues.append(issue(str(checklist), 0, "R3Q1", "task 上级缺少合法 spec_version: 3 spec.md"))
    elif declared and spec_value.strip().rstrip("/") != declared:
        issues.append(issue(
            str(checklist), 0, "R3Q1",
            f"spec: 指针与 task 实际归属不符：头部写「{spec_value}」，实际位于「{declared}」",
        ))

    risk_value = header_value(text, "risk")
    if not risk_value:
        issues.append(issue(str(checklist), 0, "R3Q2", "头部缺少 risk: 取值"))
    elif risk_value.upper() not in RISK_VALUES:
        issues.append(issue(str(checklist), 0, "R3Q2", f"risk: 取值非法：{risk_value}"))

    if spec_dir is not None:
        for spec_issue in spec3_contract_issues(spec_dir):
            issues.append(issue(
                str(checklist), 0, "R3Q10",
                f"归属 spec3 未就绪：{spec_issue['msg']}",
            ))

    try:
        rows = parse_checklist(task_dir)
    except (FileNotFoundError, ValueError) as exc:
        issues.append(issue(str(checklist), 0, "R3Q3", str(exc)))
        return issues

    scenario_counts = scenario_id_counts(spec_dir / "spec.md") if spec_dir else None
    known_ids = {row["id"] for row in rows}
    for row in rows:
        if not row["title"]:
            issues.append(issue(str(checklist), row["line"], "R3Q4", f"{row['id']} 任务说明为空"))
        if not row["risk"]:
            issues.append(issue(str(checklist), row["line"], "R3Q4", f"{row['id']} 风险列为空"))
        for dependency in row["deps"]:
            if dependency not in known_ids:
                issues.append(issue(
                    str(checklist), row["line"], "R3Q8",
                    f"{row['id']} 依赖「{dependency}」不在 task 表中",
                ))
        if not is_legal_status(row["raw_status"]):
            issues.append(issue(
                str(checklist), row["line"], "R3Q7",
                f"{row['id']} 状态非法：{row['raw_status'] or '(空)'}",
            ))
        scenario = row["scenario"]
        if scenario is None:
            issues.append(issue(str(checklist), row["line"], "R3Q3", "表头缺 Scenario IDs 列"))
            continue
        if not scenario:
            issues.append(issue(
                str(checklist), row["line"], "R3Q5",
                f"{row['id']} Scenario IDs 为空；纯技术行须写 None",
            ))
            continue
        try:
            referenced_ids = parse_scenario_ids(scenario)
        except ValueError as exc:
            issues.append(issue(
                str(checklist), row["line"], "R3Q5", f"{row['id']} {exc}",
            ))
            continue
        if not referenced_ids or scenario_counts is None:
            continue
        for scenario_id in referenced_ids:
            count = scenario_counts.get(scenario_id, 0)
            if count == 0:
                issues.append(issue(
                    str(checklist), row["line"], "R3Q5",
                    f"{row['id']} Scenario ID 悬空：「{scenario_id}」不在 {spec_value}/spec.md 中",
                ))
            elif count > 1:
                issues.append(issue(
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
        issue(str(spec_md), 0, "R3Q6", f"Scenario「{scenario_id}」未被该 spec 下任何 task 承接")
        for scenario_id in scenario_ids if scenario_id not in covered
    ]


def resolve_task_list(task_dir: Path) -> tuple[list[dict], list[dict]]:
    """解析 checklist 并判定引擎状态 + 产物锚点交叉验证。

    返回 (tasks, product_issues)。product_check：done 但文件缺失→"missing"；
    todo 但文件已存在→"stale"；无锚点→不设该字段。
    """
    raw_tasks = parse_checklist(task_dir)
    tasks: list[dict] = []
    product_issues: list[dict] = []
    for t in raw_tasks:
        status = task_engine_status(t["raw_status"])
        entry = {
            "id": t["id"],
            "title": t["title"],
            "status": status,
            "deps": t["deps"],
            "product": t["product"],
        }
        if t["product"]:
            target = task_dir / t["product"]
            exists = target.exists()
            if status == DONE and not exists:
                entry["product_check"] = "missing"
                product_issues.append({
                    "id": t["id"], "rule": "product",
                    "msg": f"标记 done 但产物缺失：{t['product']}",
                })
            elif status == TODO and exists:
                entry["product_check"] = "stale"
                product_issues.append({
                    "id": t["id"], "rule": "product",
                    "msg": f"标记 todo 但产物已存在：{t['product']}",
                })
        tasks.append(entry)
    return tasks, product_issues


def compute_progress(tasks: list[dict]) -> dict:
    total = len(tasks)
    done = sum(1 for t in tasks if t["status"] == DONE)
    blocked = sum(1 for t in tasks if t["status"] == BLOCKED)
    todo = total - done - blocked
    return {"total": total, "done": done, "todo": todo, "blocked": blocked}


# ---------- 状态：任务状态 + 进度 ----------


def status(task_dir: Path, as_json: bool) -> int:
    try:
        tasks, product_issues = resolve_task_list(task_dir)
    except (FileNotFoundError, ValueError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    progress = compute_progress(tasks)
    payload = {"task": task_dir.name, "tasks": tasks, "progress": progress}
    if product_issues:
        payload["product_issues"] = product_issues
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"== {task_dir.name}  status")
        for t in tasks:
            mark = {"done": "✓", "todo": "·", "blocked": "!"}[t["status"]]
            deps = f" ← {','.join(t['deps'])}" if t["deps"] else ""
            print(f"  {mark} {t['id']}  {t['title']}{deps}")
        p = progress
        print(f"  进度：{p['done']}/{p['total']} done · {p['todo']} todo · {p['blocked']} blocked")
    return 0


# ---------- graph：依赖拓扑排序 ----------


def topo_sort(task_ids: list[str], deps_map: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    """Kahn 拓扑排序 + 环检测。返回 (order, cycle_nodes)。"""
    valid = set(task_ids)
    adj: dict[str, list[str]] = {tid: [] for tid in task_ids}
    indeg: dict[str, int] = {tid: 0 for tid in task_ids}
    for tid in task_ids:
        for dep in deps_map.get(tid, []):
            if dep in valid:
                adj[dep].append(tid)
                indeg[tid] += 1
    queue = sorted([tid for tid in task_ids if indeg[tid] == 0])
    order: list[str] = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        nexts = []
        for nxt in adj[node]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                nexts.append(nxt)
        queue.extend(sorted(nexts))
    cycle = [tid for tid in task_ids if tid not in set(order)]
    return order, cycle


def compute_graph(tasks: list[dict]) -> dict:
    """算 ready / blocked / order / parallel_batches。"""
    by_id = {t["id"]: t for t in tasks}
    ids = [t["id"] for t in tasks]
    deps_map = {t["id"]: t["deps"] for t in tasks}
    order, cycle = topo_sort(ids, deps_map)

    ready: list[str] = []
    blocked: list[dict] = []
    for t in tasks:
        if t["status"] == DONE:
            continue
        deps = deps_map[t["id"]]
        missing = []
        for dep in deps:
            if dep not in by_id:
                missing.append(dep)
            elif by_id[dep]["status"] != DONE:
                missing.append(dep)
        if missing:
            blocked.append({"id": t["id"], "missing": missing})
        else:
            ready.append(t["id"])

    done_ids = {t["id"] for t in tasks if t["status"] == DONE}
    batches: list[list[str]] = []
    placed: set[str] = set(done_ids)
    for _ in range(len(order)):
        layer = []
        for tid in order:
            if tid in placed:
                continue
            if by_id[tid]["status"] == DONE:
                placed.add(tid)
                continue
            deps = deps_map[tid]
            if all(d in placed for d in deps if d in by_id) and all(d in by_id for d in deps):
                layer.append(tid)
        if not layer:
            break
        for tid in layer:
            placed.add(tid)
        batches.append(layer)

    return {
        "ready": ready,
        "blocked": blocked,
        "order": order,
        "parallel_batches": batches,
        "cycle": cycle,
    }


def graph(task_dir: Path, as_json: bool) -> int:
    try:
        tasks, _ = resolve_task_list(task_dir)
    except (FileNotFoundError, ValueError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    result = compute_graph(tasks)
    cycle = result["cycle"]
    if cycle and as_json:
        payload = {
            "task": task_dir.name,
            "error": "dependency_cycle",
            "cycle_nodes": cycle,
            "ready": result["ready"],
            "blocked": result["blocked"],
            "order": result["order"],
            "parallel_batches": result["parallel_batches"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    if cycle:
        print(f"错误：检测到依赖环：{', '.join(cycle)}", file=sys.stderr)
        return 1
    if as_json:
        payload = {
            "task": task_dir.name,
            "ready": result["ready"],
            "blocked": result["blocked"],
            "order": result["order"],
            "parallel_batches": result["parallel_batches"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"== {task_dir.name}  graph")
        print(f"  拓扑序：{' → '.join(result['order'])}")
        if result["ready"]:
            print(f"  可执行 (ready)：{', '.join(result['ready'])}")
        if result["blocked"]:
            for b in result["blocked"]:
                print(f"  阻塞 {b['id']}：缺 {', '.join(b['missing'])}")
        for i, batch in enumerate(result["parallel_batches"], 1):
            print(f"  并行批次 {i}：{', '.join(batch)}")
    return 0
