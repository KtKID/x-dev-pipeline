#!/usr/bin/env python3
"""req — x-req2 的 task 确定性引擎，被 tools/xdev.py import 后按命令委托调用。

只服务 docs/spec/<spec-name>/tasks/<task-name>/ 结构，不识别旧结构。
暴露 scaffold/validate/status/graph/verify 五个函数供 xdev.py 委托调用；
不单独作主 CLI 入口（命令统一走 xdev.py，见 design.md 决策 A）。

退出码沿用 xdev.py 风格：0 正常；1 存在 issue/校验失败；2 用法或 IO 错误。

validate issue 规则码（REQ 前缀，独立于 xdev.py 的 V 编号）：
- REQ0 dev-checklist.md 缺失
- REQ1 头部 spec: 指针缺失，或未指向合法 spec 包（缺 spec.md/modules.md）
- REQ2 头部 risk: 缺失，或不在 {Q0,Q1,Q2,Q3} 内
- REQ3 任务表解析失败（缺 #/状态等关键列）
- REQ4 行内容非空校验（任务说明 / 风险列为空）
- REQ5 行 Requirement 悬空或在归属 spec.md 中重名
- REQ6 spec 级：Requirement 未被该 spec 下任何 task 承接（硬 issue，spec 级判定）
- REQ7 行状态非法：状态列既非已定义 token（`[ ]`/`[x]`/`[!]`）也非纯 emoji 兼容集合，复用 status/graph 同一解析词表
- REQ8 行依赖悬空：依赖列引用的 task ID 不在同一 checklist 表中
- REQ9 diagram.md 与归属 spec 包 modules.md 模块名不一致（双向比较，仅 diagram.md 存在时运行，spec 指针失效时跳过）
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
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

# ---------- 常量与正则（与 xdev.py 有意小幅重复，见 design.md「取舍」：换取子域解耦） ----------

CHECKLIST_HEADER_KEYWORDS = {
    "id": ("#", "编号"),
    "title": ("任务说明", "任务", "标题"),
    "requirement": ("Requirement",),
    "risk": ("风险",),
    "file": ("涉及文件", "文件"),
    "dep": ("依赖",),
    "status": ("状态",),
}

TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
REQ_RE = re.compile(r"^###\s+Requirement:\s*(.*)$")
SCEN_RE = re.compile(r"^####\s+Scenario:\s*(.*)$")
H3_RE = re.compile(r"^###\s+")
H4_RE = re.compile(r"^####\s+")
H2_RE = re.compile(r"^##\s+")
VALIDATION_RE = re.compile(r"^\s*[-*+]?\s*验证:\s*(auto|manual)\s*$", re.IGNORECASE)
SPEC_LINE_RE = re.compile(r"^>\s*spec:\s*(\S+)\s*$", re.IGNORECASE)
RISK_LINE_RE = re.compile(r"^>\s*risk:\s*(\S+)\s*$", re.IGNORECASE)
TASK_ID_RE = re.compile(r"(?:T|#)(\d+)", re.IGNORECASE)
ID_COL_RE = re.compile(r"(?:T|#)?(\d+)", re.IGNORECASE)
PRODUCT_RE = re.compile(r"product:\s*([^\s,;]+)")
VERIFY_FENCE_RE = re.compile(r"^\s*```verify\s*$", re.IGNORECASE)
FENCE_END_RE = re.compile(r"^\s*```\s*$")

RISK_VALUES = {"Q0", "Q1", "Q2", "Q3"}

DONE = "done"
TODO = "todo"
BLOCKED = "blocked"
TOKEN_RE = re.compile(r"\[(?P<box>[ x!])\]")
STATUS_EMOJI_MAP = {"🟢": DONE, "✅": DONE, "🔴": BLOCKED}

VERIFY_KEYS = {
    "id", "scenario", "cmd", "cwd", "expect_exit", "expect_contains", "timeout", "mode", "steps",
}


def issue(file: str, line: int, rule: str, msg: str) -> dict:
    return {"file": file, "line": line, "rule": rule, "msg": msg}


def read_text(f: Path) -> str:
    return f.read_text(encoding="utf-8", errors="replace")


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


# ---------- checklist 解析（唯一实现，供 validate/status/graph/verify 复用） ----------

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


def parse_checklist(task_dir: Path) -> list[dict]:
    """解析新表头任务表：`# | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix`。

    表头按关键词查列（容忍顺序/措辞小幅变化），"#"/"状态" 两列必须能定位，
    其余列缺失时对应字段留空，不阻断解析（status/graph 等仍可运作）。

    返回的每个 task dict 含：id, title, requirement, risk, deps(list[str]),
    raw_status(str), product(str|None), line(int)。引擎状态由 task_engine_status
    单独判定，便于 status/graph/validate 各自复用。
    """
    checklist = task_dir / "dev-checklist.md"
    if not checklist.exists():
        raise FileNotFoundError(f"缺少 dev-checklist.md：{task_dir}")
    header, rows = first_table(read_text(checklist))
    if not header:
        raise ValueError(f"dev-checklist.md 无可解析表格：{checklist}")

    id_idx = col_idx(header, *CHECKLIST_HEADER_KEYWORDS["id"])
    title_idx = col_idx(header, *CHECKLIST_HEADER_KEYWORDS["title"])
    req_idx = col_idx(header, *CHECKLIST_HEADER_KEYWORDS["requirement"])
    risk_idx = col_idx(header, *CHECKLIST_HEADER_KEYWORDS["risk"])
    file_idx = col_idx(header, *CHECKLIST_HEADER_KEYWORDS["file"])
    dep_idx = col_idx(header, *CHECKLIST_HEADER_KEYWORDS["dep"])
    status_idx = col_idx(header, *CHECKLIST_HEADER_KEYWORDS["status"])
    if id_idx is None or status_idx is None:
        missing = []
        if id_idx is None:
            missing.append("#/编号 列")
        if status_idx is None:
            missing.append("状态 列")
        raise ValueError(f"dev-checklist.md 表头缺关键列：{', '.join(missing)}")

    def cell(cs: list[str], idx: int | None) -> str:
        return cs[idx].strip() if idx is not None and idx < len(cs) else ""

    tasks: list[dict] = []
    for line_no, cs in rows:
        if len(cs) <= max(i for i in (id_idx, status_idx) if i is not None):
            continue
        raw_id = cell(cs, id_idx)
        if not raw_id or raw_id.lower() in ("—", "-", "n/a"):
            continue
        m = ID_COL_RE.search(raw_id)
        if not m:
            continue
        norm_id = f"T{m.group(1)}"
        raw_files = cell(cs, file_idx)
        product = None
        if raw_files:
            pm = PRODUCT_RE.search(raw_files)
            if pm:
                product = pm.group(1)
        tasks.append({
            "id": norm_id,
            "title": cell(cs, title_idx),
            "requirement": cell(cs, req_idx),
            "risk": cell(cs, risk_idx),
            "deps": parse_deps(cell(cs, dep_idx)),
            "raw_status": cell(cs, status_idx),
            "product": product,
            "line": line_no,
        })
    return tasks


def parse_deps(raw: str) -> list[str]:
    """解析依赖列：支持 'T1' / 'T2,T3' / 'T2/T3' / '#1 #2' / '—' / '' → 归一化 id 列表。"""
    if not raw or raw.strip() in ("—", "-", ""):
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
    """REQ7：状态列是否落在 status/graph 复用的同一词表内（已定义 token 或纯 emoji 兼容集合）。"""
    if TOKEN_RE.search(raw_status):
        return True
    return any(emoji in raw_status for emoji in STATUS_EMOJI_MAP)


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


# ---------- validate：头部校验 + 行级校验（1.1.4/1.1.5） ----------

def spec_requirements(spec_md: Path) -> list[str]:
    """按声明顺序返回 spec.md「验收」节下的 Requirement 名（含重复项，供计数/去重复用）。

    严格限定在 `## 验收` 区段内扫描，不识别该区段外偶然出现的同形标题。
    """
    if not spec_md.exists():
        return []
    lines = read_text(spec_md).splitlines()
    start, end = section_bounds(lines, "验收")
    if start is None:
        return []
    return [m.group(1).strip() for line in lines[start + 1 : end] if (m := REQ_RE.match(line))]


def requirement_name_counts(spec_md: Path) -> Counter:
    """统计归属 spec.md 验收中每个 Requirement 名出现次数（用于悬空/重名判定）。"""
    return Counter(spec_requirements(spec_md))


def resolve_spec_dir(spec_value: str) -> Path | None:
    """把头部 spec: 取值解析为合法 spec 包目录；缺 spec.md/modules.md 视为非法。"""
    candidate = (PLUGIN_ROOT / spec_value).resolve()
    if (candidate / "spec.md").is_file() and (candidate / "modules.md").is_file():
        return candidate
    return None


def validate_issues(task_dir: Path) -> list[dict]:
    """单 task 校验：头部（spec:/risk:）+ 行级（Requirement 悬空/重名、风险与任务说明非空）。

    不判定 spec 级 Requirement 全覆盖（见 spec_requirement_coverage，避免多 task 互相误报）。
    归属 spec 指针失效时，降级为一条头部 issue，行级 Requirement 存在性检查随之跳过（不级联）。
    """
    checklist = task_dir / "dev-checklist.md"
    rel = str(checklist)
    if not checklist.exists():
        return [issue(str(task_dir), 0, "REQ0", "缺少 dev-checklist.md")]
    text = read_text(checklist)
    issues: list[dict] = []

    spec_value = header_value(text, "spec")
    spec_dir: Path | None = None
    if not spec_value:
        issues.append(issue(rel, 0, "REQ1", "头部缺少 spec: 指针"))
    else:
        spec_dir = resolve_spec_dir(spec_value)
        if spec_dir is None:
            issues.append(issue(rel, 0, "REQ1", f"spec: 指针未指向合法 spec 包（缺 spec.md/modules.md）：{spec_value}"))

    risk_value = header_value(text, "risk")
    if not risk_value:
        issues.append(issue(rel, 0, "REQ2", "头部缺少 risk: 取值"))
    elif risk_value.upper() not in RISK_VALUES:
        issues.append(issue(rel, 0, "REQ2", f"risk: 取值非法（须 Q0/Q1/Q2/Q3）：{risk_value}"))

    try:
        rows = parse_checklist(task_dir)
    except (FileNotFoundError, ValueError) as exc:
        issues.append(issue(rel, 0, "REQ3", str(exc)))
        return issues

    req_counts = requirement_name_counts(spec_dir / "spec.md") if spec_dir is not None else None
    known_ids = {row["id"] for row in rows}
    for row in rows:
        if not row["title"]:
            issues.append(issue(rel, row["line"], "REQ4", f"{row['id']} 任务说明为空"))
        if not row["risk"]:
            issues.append(issue(rel, row["line"], "REQ4", f"{row['id']} 风险列为空"))
        for dep in row["deps"]:
            if dep not in known_ids:
                issues.append(issue(rel, row["line"], "REQ8", f"{row['id']} 依赖「{dep}」不在 task 表中"))
        if not is_legal_status(row["raw_status"]):
            issues.append(issue(rel, row["line"], "REQ7", f"{row['id']} 状态非法：{row['raw_status'] or '(空)'}"))
        req_name = row["requirement"]
        if not req_name or req_name == "—" or req_counts is None:
            continue
        count = req_counts.get(req_name, 0)
        if count == 0:
            issues.append(issue(rel, row["line"], "REQ5", f"{row['id']} Requirement 悬空：「{req_name}」不在 {spec_value}/spec.md 验收中"))
        elif count > 1:
            issues.append(issue(rel, row["line"], "REQ5", f"{row['id']} Requirement 重名：「{req_name}」在 {spec_value}/spec.md 中出现 {count} 次"))

    issues.extend(diagram_consistency_issues(task_dir, spec_dir))
    return issues


def validate(task_dir: Path, as_json: bool) -> int:
    """validate 子命令：单 task 头部 + 行级校验，打印并返回退出码。"""
    issues = validate_issues(task_dir)
    payload = {"path": str(task_dir), "type": "req2-task", "skipped": False, "issues": issues}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"== {task_dir}  [req2-task]")
        if not issues:
            print("   ok")
        for fd in issues:
            loc = f"{fd['file']}:{fd['line']}" if fd["line"] else fd["file"]
            print(f"   {loc}  {fd['rule']}  {fd['msg']}")
        mark = "✓" if not issues else "✗"
        print(f"{mark} validate：{len(issues)} issue(s)")
    return 0 if not issues else 1


def spec_requirement_coverage(spec_dir: Path) -> list[dict]:
    """spec 级覆盖检查（1.1.6）：合并该 spec 下所有 tasks/*/dev-checklist.md 的 Requirement 引用，
    对照 spec.md 验收 Requirement 全集，未被任何行承接的报硬 issue。

    单 task 解析失败时静默跳过该 task（已由该 task 自身 validate_issues 报出，这里不重复）。
    """
    spec_md = spec_dir / "spec.md"
    names = list(dict.fromkeys(spec_requirements(spec_md)))
    if not names:
        return []
    covered: set[str] = set()
    tasks_dir = spec_dir / "tasks"
    if tasks_dir.is_dir():
        for task_dir in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
            try:
                rows = parse_checklist(task_dir)
            except (FileNotFoundError, ValueError):
                continue
            for row in rows:
                if row["requirement"] and row["requirement"] != "—":
                    covered.add(row["requirement"])
    return [
        issue(str(spec_md), 0, "REQ6", f"Requirement「{name}」未被该 spec 下任何 task 承接")
        for name in names if name not in covered
    ]


# ---------- REQ9：diagram.md 与归属 spec 包 modules.md 模块一致性（双向比较，与 xdev.py V10 逻辑一致，短期各自维护见 design.md「取舍」） ----------

def normalize_module_name(value: str) -> str:
    """归一化 Markdown/Mermaid 的节点标签，供 REQ9 做词法双向比对。"""
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


def spec_module_names(spec_dir: Path) -> dict[str, str]:
    """读取归属 spec 包 modules.md「模块总览」表的模块名，供 REQ9 双向比对。"""
    modules_md = spec_dir / "modules.md"
    if not modules_md.exists():
        return {}
    lines = read_text(modules_md).splitlines()
    start, end = section_bounds(lines, "模块总览")
    if start is None:
        return {}
    header, rows = first_table("\n".join(lines[start + 1 : end]))
    if not header:
        return {}
    idx = next((i for i, c in enumerate(header) if "模块" in c), None)
    if idx is None:
        return {}
    names: dict[str, str] = {}
    for _line, row in rows:
        if idx < len(row):
            original = row[idx].strip()
            normalized = normalize_module_name(original)
            if normalized:
                names[normalized] = original
    return names


def diagram_consistency_issues(task_dir: Path, spec_dir: Path | None) -> list[dict]:
    """REQ9：diagram.md 存在且归属 spec 指针合法时，双向比较其 Mermaid 节点标签与 modules.md 模块总览。

    diagram.md 不存在，或归属 spec 指针失效（spec_dir 为 None）时跳过，后者与 REQ5 的「不级联」约定一致。
    """
    diagram = task_dir / "diagram.md"
    if not diagram.exists() or spec_dir is None:
        return []
    declared = spec_module_names(spec_dir)
    rendered = mermaid_modules(read_text(diagram))
    rel = str(diagram)
    issues: list[dict] = []
    for name in sorted(declared.keys() - rendered.keys()):
        issues.append(issue(rel, 0, "REQ9", f"modules.md 模块「{declared[name]}」缺少 Mermaid 节点"))
    for name in sorted(rendered.keys() - declared.keys()):
        issues.append(issue(rel, 0, "REQ9", f"Mermaid 节点「{rendered[name]}」未在 modules.md 模块总览声明"))
    return issues


# ---------- status：任务状态 + 进度 ----------

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


# ---------- verify：dev-report 证据执行与场景对账（数据源改指归属 spec.md） ----------

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
    """读取归属 spec.md「验收」节的 Scenario 名和验证标记，供 verify 覆盖对账使用。"""
    if not spec_md.exists():
        raise FileNotFoundError(f"缺少 spec.md：{spec_md.parent}")
    lines = read_text(spec_md).splitlines()
    start, end = section_bounds(lines, "验收")
    if start is None:
        return []
    scenarios: list[dict] = []
    current: tuple[str, list[str]] | None = None

    def close_current():
        nonlocal current
        if current is None:
            return
        name, body = current
        marker = next((match.group(1).lower() for line in body if (match := VALIDATION_RE.match(line))), None)
        scenarios.append({"name": name, "mode": marker})
        current = None

    for index in range(start + 1, end):
        line = lines[index]
        if SCEN_RE.match(line):
            close_current()
            current = (SCEN_RE.match(line).group(1).strip(), [])
            continue
        if H3_RE.match(line) or H4_RE.match(line):
            close_current()
            continue
        if current is not None:
            current[1].append(line)
    close_current()
    return scenarios


def verify_cwd(raw_cwd: str, block_id: str) -> Path:
    candidate = (PLUGIN_ROOT / raw_cwd).resolve()
    try:
        candidate.relative_to(PLUGIN_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"verify 块 {block_id} 的 cwd 必须是仓库内相对路径：{raw_cwd}") from exc
    if not candidate.is_dir():
        raise ValueError(f"verify 块 {block_id} 的 cwd 不存在或不是目录：{raw_cwd}")
    return candidate


def execute_verify_block(block: dict) -> dict:
    cwd = verify_cwd(block["cwd"], block["id"])
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


def verify(task_dir: Path, as_json: bool, only: str | None) -> int:
    """verify 子命令：复跑 dev-report verify 块，场景对账指向归属 spec.md 的 auto 场景。"""
    try:
        if not task_dir.is_dir():
            raise FileNotFoundError(f"不是目录：{task_dir}")
        spec_path = spec_of_task_dir(task_dir)
        if spec_path is None:
            raise ValueError(f"{task_dir} 不在 docs/spec/<spec-name>/tasks/<task-name>/ 结构下")
        spec_md = PLUGIN_ROOT / spec_path / "spec.md"
        report = latest_dev_report(task_dir)
        blocks = parse_verify_blocks(report)
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
        results = [execute_verify_block(block) for block in selected]
        pass_items = [{key: value for key, value in result.items() if key != "output_tail"}
                      for result in results if result["pass"]]
        fail_items = [{key: value for key, value in result.items() if key != "pass"}
                      for result in results if not result["pass"]]
        declared_auto = {block["scenario"].strip() for block in all_auto if block["scenario"].strip()}
        uncovered = [
            item["name"] for item in acceptance_scenarios(spec_md)
            if item["mode"] == "auto" and item["name"].strip() not in declared_auto
        ]
        payload = {
            "task": task_dir.name,
            "spec": spec_path,
            "dev_report": str(report),
            "pass": pass_items,
            "fail": fail_items,
            "manual": manual,
            "uncovered": uncovered,
        }
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"== {task_dir.name} verify")
        print(f"  pass: {len(payload['pass'])} · fail: {len(payload['fail'])} · manual: {len(manual)}")
        for item in payload["fail"]:
            print(f"  ! {item['id']} exit={item['exit_code']} expected={item['expected_exit']}")
        for name in uncovered:
            print(f"  ! uncovered scenario: {name}")
    return 0 if not payload["fail"] and not uncovered else 1
