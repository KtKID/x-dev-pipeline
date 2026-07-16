#!/usr/bin/env python3
"""xdev — x-dev-pipeline 的确定性工具层（立法层）。

确定性工具层把散落在 SKILL.md 散文里的格式法律搬进代码。skills 管判断，
本工具管机械。

规则编号（run-log 聚合用；文字正源见 skills/x-spec/templates/TEMPLATE_GUIDE.md）：
  V0 包类型无法识别 / 文件不可读
  V1 档位所需文件齐全（spec7 七件 / change 包 proposal+delta+tasks）
  V2 路径引用规则：包内链接只用 ./ 且目标存在；代码路径只写 repo: 纯文本；
     禁 ../ 、绝对路径、file://、盘符、docs/ 仓库相对路径
  V3 Requirement/Scenario 结构：每条 "### Requirement:" ≥1 个 "#### Scenario:"，
     场景含 GIVEN / WHEN / THEN（Phase 2 模板落地后生效，对无 Requirement 的文件不触发）
  V4 delta 文件只允许 "## ADDED|MODIFIED|REMOVED Requirements" 三种二级节
  V5 90-task-map 每行任务回指 DoD
  V6 02 模块总览 与 90 task-map 的模块清单一致（词法比对）
  V7 状态取值 ∈ 受控词汇（正源：x-spec SKILL.md「状态定义」）
  V8 task 包包含 README.md 与 dev-checklist.md（diagram.md 可选）
  V9 task checklist 使用固定表头、合法状态和存在的依赖 ID
  V10 可选 diagram 的 Mermaid 节点与 README「涉及模块」双向一致
  V11 task README 的必需章节、自动化测试责任和 Smoke/E2E 证据

用法：
  python3 tools/xdev.py validate [包目录 ...] [--include-legacy] [--json]
  不给目录时，从当前工作目录发现 docs/spec/*/、docs/changes/*/、docs/specs/*/。
  legacy 包（含 diagrams.md / *.html 图集的旧结构）默认跳过，--include-legacy 纳入
  （纳入时不查 V1 档位齐全，只查其余规则）。

退出码：0 全部通过；1 存在 finding；2 用法或 IO 错误。
用法：
  python3 tools/xdev.py validate [包目录 ...] [--include-legacy] [--json]
  不给目录时，从当前工作目录发现 docs/spec/*/、docs/changes/*/、docs/specs/*/。
  legacy 包（含 diagrams.md / *.html 图集的旧结构）默认跳过，--include-legacy 纳入
  （纳入时不查 V1 档位齐全，只查其余规则）。

  python3 tools/xdev.py status <task-dir> [--json]
  解析 dev-pipeline/tasks/<task>/dev-checklist.md，按 token+emoji 双轨判定任务状态，
  输出进度 JSON。纯 emoji 旧 checklist 自动兼容降级（见 STATUS_EMOJI_MAP）。

  python3 tools/xdev.py graph <task-dir> [--json]
  基于 status 解析结果做依赖拓扑排序（Kahn），输出 ready / blocked / order /
  parallel_batches；检测依赖环时报错并列出环节点（退出码 1）。

  python3 tools/xdev.py instructions <artifact-id> --task <task-dir> [--json]
  返回 task 产物的模板、填写规则、目标路径和依赖存在状态。

  python3 tools/xdev.py scaffold <task-dir> [--with-diagram] [--json]
  增量创建 README.md、dev-checklist.md 与可选 diagram.md；已有文件逐字节保留。

退出码：0 正常；1 存在 finding 或依赖环；2 用法或 IO 错误。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STATUS_VOCAB = ("探索中", "方案确认", "可进入 x-req", "开发中", "已完成")

SPEC7_REQUIRED = [
    "README.md",
    "01-goals-and-boundaries.md",
    "02-module-breakdown.md",
    "03-core-workflows.md",
    "04-data-and-state.md",
    "05-validation-and-evolution.md",
    "90-task-map.md",
]
CHANGE_REQUIRED = ["proposal.md", "tasks.md"]

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
REQ_RE = re.compile(r"^###\s+Requirement:\s*(.*)$")
SCEN_RE = re.compile(r"^####\s+Scenario:\s*(.*)$")
H3_RE = re.compile(r"^###\s+")
H4_RE = re.compile(r"^####\s+")
H2_RE = re.compile(r"^##\s+")
DELTA_HEAD_RE = re.compile(r"^##\s+(ADDED|MODIFIED|REMOVED)\s+Requirements\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TASK_CHECKLIST_HEADER = ["#", "任务", "涉及文件", "依赖", "状态", "fix"]
TASK_STATUS_PAIRS = {
    " ": ("⏳", "▶️", "🟡"),
    "x": ("🟢", "✅"),
    "!": ("🔴",),
}
TASK_STATUS_EMOJIS = tuple(emoji for emojis in TASK_STATUS_PAIRS.values() for emoji in emojis)

INSTRUCTION_SUFFIX = "以上规则与模板内 HTML 注释用于填写约束；完成产物时删除模板注释，不要复制规则文字。"

README_INSTRUCTION = """先将已确认的需求逐条写入 README。核心目标、需求要点、涉及模块、架构拆分策略、技术设计、可客观验证的 DoD 与 Smoke/E2E 验收路径必须相互可追溯；自动化测试责任应明确交给 x-dev，并由 dev-report 记录真实命令和结果。Smoke/E2E 优先提供可执行命令，交互验收写明 manual。\n\n""" + INSTRUCTION_SUFFIX
CHECKLIST_INSTRUCTION = """开发清单从 README 的架构拆分策略推导。P0 覆盖契约、边界入口和核心状态，P1 覆盖适配集成与主要验证，P2 覆盖增强；每行关联涉及文件、依赖和状态。核心逻辑、持久化迁移、安全、跨模块集成和公共 API 变更标注 🔍；同优先级且无依赖、无写冲突的任务可以并行。\n\n""" + INSTRUCTION_SUFFIX
DIAGRAM_INSTRUCTION = """README 是架构文字事实源，diagram 是只读投影。将 README 的涉及模块、边界类和依赖关系映射为 Mermaid 节点与连线；模块名保持一致，按模块划分 subgraph，并压缩同质重复节点。\n\n""" + INSTRUCTION_SUFFIX

ARTIFACTS = {
    "readme": {
        "generates": "README.md",
        "template": "skills/x-req/templates/README.md",
        "requires": [],
        "instruction": README_INSTRUCTION,
    },
    "dev-checklist": {
        "generates": "dev-checklist.md",
        "template": "skills/x-req/templates/dev-checklist.md",
        "requires": ["readme"],
        "instruction": CHECKLIST_INSTRUCTION,
    },
    "diagram": {
        "generates": "diagram.md",
        "template": "skills/x-req/templates/diagram.md",
        "requires": ["readme"],
        "instruction": DIAGRAM_INSTRUCTION,
    },
}


def finding(file: str, line: int, rule: str, msg: str) -> dict:
    return {"file": file, "line": line, "rule": rule, "msg": msg}


# ---------- 基础解析 ----------

def read_text(f: Path) -> str:
    return f.read_text(encoding="utf-8", errors="replace")


def md_files(pkg: Path):
    return sorted(p for p in pkg.rglob("*.md") if "archive" not in p.parts)


def lines_outside_fences(text: str):
    """按行产出 (行号, 内容)，跳过 ``` 围栏内部（mermaid / 代码示例不参与检查）。"""
    fenced = False
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            yield i, line


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


def col_values(text: str, col_keyword: str) -> list[str]:
    """第一个表里、表头含关键词那一列的全部非空值（去掉 `*` 等修饰）。"""
    header, rows = first_table(text)
    if not header:
        return []
    idx = next((i for i, c in enumerate(header) if col_keyword in c), None)
    if idx is None:
        return []
    vals = []
    for _ln, cs in rows:
        if idx < len(cs):
            v = re.sub(r"[`*]", "", cs[idx]).strip()
            if v:
                vals.append(v)
    return vals


def artifact_template(artifact_id: str) -> str:
    """从工具位置推导插件根目录，读取唯一注册表声明的模板。"""
    entry = ARTIFACTS[artifact_id]
    return read_text(PLUGIN_ROOT / entry["template"])


def artifact_payload(artifact_id: str, task_dir: Path) -> dict:
    """构造 instructions 命令的稳定事实输出。"""
    entry = ARTIFACTS[artifact_id]
    output_path = task_dir / entry["generates"]
    dependencies = []
    for dependency_id in entry["requires"]:
        dependency_path = task_dir / ARTIFACTS[dependency_id]["generates"]
        dependencies.append({
            "id": dependency_id,
            "path": str(dependency_path),
            "exists": dependency_path.exists(),
        })
    return {
        "artifact": artifact_id,
        "output_path": str(output_path),
        "exists": output_path.exists(),
        "template": artifact_template(artifact_id),
        "instruction": entry["instruction"],
        "requires": entry["requires"],
        "dependencies": dependencies,
    }


def instructions_command(artifact_id: str, task_dir: Path, as_json: bool) -> int:
    """instructions 子命令：报告产物事实，不把依赖缺失升级为错误。"""
    if artifact_id not in ARTIFACTS:
        choices = ", ".join(ARTIFACTS)
        print(f"错误：未知 artifact ID「{artifact_id}」，可用：{choices}", file=sys.stderr)
        return 2
    try:
        payload = artifact_payload(artifact_id, task_dir)
    except OSError as exc:
        print(f"错误：读取 artifact 模板失败：{exc}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"== {payload['artifact']} instructions")
    print(f"  输出：{payload['output_path']}")
    print(f"  已存在：{'是' if payload['exists'] else '否'}")
    print(f"  依赖：{', '.join(payload['requires']) or '无'}")
    for dependency in payload["dependencies"]:
        state = "存在" if dependency["exists"] else "缺失"
        print(f"  依赖产物 {dependency['id']}：{dependency['path']}（{state}）")
    print("\n== template\n")
    print(payload["template"])
    print("\n== instruction\n")
    print(payload["instruction"])
    return 0


def scaffold_command(task_dir: Path, with_diagram: bool, as_json: bool) -> int:
    """scaffold 子命令：仅创建缺失产物，已有文件保持原字节内容。"""
    artifact_ids = ["readme", "dev-checklist"]
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
            if artifact_id == "readme":
                content = content.replace("# <task-name>", f"# {task_dir.name}", 1)
            path.write_text(content, encoding="utf-8")
            created.append(str(path))
    except OSError as exc:
        print(f"错误：scaffold 无法写入 {task_dir}：{exc}", file=sys.stderr)
        return 2

    payload = {"task": str(task_dir), "created": created, "skipped": skipped}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"== scaffold {task_dir}")
        for path in created:
            print(f"  created: {path}")
        for path in skipped:
            print(f"  skipped: {path}")
    return 0


# ---------- 包类型识别 ----------

def detect_type(pkg: Path) -> str:
    parts = pkg.resolve().parts
    if (pkg / "dev-checklist.md").exists() or any(
        parts[i : i + 2] == ("dev-pipeline", "tasks") for i in range(len(parts) - 1)
    ):
        return "task"
    if (
        (pkg / "diagrams.md").exists()
        or (pkg / "diagrams.html").exists()
        or (pkg / "architecture.html").exists()
    ):
        return "legacy"
    if (pkg / "proposal.md").exists():
        return "change"
    if (pkg / "01-goals-and-boundaries.md").exists():
        return "spec7"
    if (pkg / "spec.md").exists():
        return "capability"
    return "unknown"


# ---------- 检查规则（一条规则一个函数；加规则 = 加函数 + 注册） ----------

def check_files_complete(pkg: Path, ptype: str):
    if ptype == "spec7":
        for name in SPEC7_REQUIRED:
            if not (pkg / name).exists():
                yield finding("(package)", 0, "V1", f"spec 包缺少必需文件：{name}")
    elif ptype == "change":
        for name in CHANGE_REQUIRED:
            if not (pkg / name).exists():
                yield finding("(package)", 0, "V1", f"change 包缺少必需文件：{name}")
        delta_files = list((pkg / "delta").glob("*.md")) if (pkg / "delta").exists() else []
        delta_files += list((pkg / "specs").rglob("*.md")) if (pkg / "specs").exists() else []
        if not delta_files:
            yield finding("(package)", 0, "V1", "change 包缺少 delta（delta/*.md 或 specs/**.md 至少一个）")


def check_link_rules(pkg: Path, ptype: str):
    for f in md_files(pkg):
        rel = str(f.relative_to(pkg))
        for ln, line in lines_outside_fences(read_text(f)):
            for m in LINK_RE.finditer(line):
                target = m.group(1)
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                if target.startswith("./"):
                    dest = f.parent / target.split("#", 1)[0]
                    if not dest.exists():
                        yield finding(rel, ln, "V2", f"链接目标不存在：({target})")
                    continue
                if target.startswith("../"):
                    msg = "禁止 ../ 上跳链接（包必须可整体移动）"
                elif re.match(r"^[A-Za-z]:[\\/]", target):
                    msg = "禁止 Windows 盘符路径"
                elif target.startswith("/"):
                    msg = "禁止绝对路径"
                elif target.startswith("file://"):
                    msg = "禁止 file:// 链接"
                elif target.startswith("repo:"):
                    msg = "repo: 路径写纯文本，不做成链接"
                elif target.startswith("docs/"):
                    msg = "禁止仓库相对路径（随移动失效）"
                else:
                    msg = "包内链接必须以 ./ 开头"
                yield finding(rel, ln, "V2", f"{msg}：({target})")


def check_req_scenario(pkg: Path, ptype: str):
    for f in md_files(pkg):
        rel = str(f.relative_to(pkg))
        req_line = None
        req_name = ""
        scen_count = 0
        scen_line = None
        scen_buf: list[str] = []

        def close_scenario():
            nonlocal scen_line, scen_buf
            if scen_line is not None:
                body = "\n".join(scen_buf)
                missing = [k for k in ("GIVEN", "WHEN", "THEN") if k not in body]
                if missing:
                    yield finding(rel, scen_line, "V3", f"Scenario 缺少 {'/'.join(missing)}")
            scen_line, scen_buf = None, []

        def close_requirement():
            nonlocal req_line, scen_count
            if req_line is not None and scen_count == 0:
                yield finding(rel, req_line, "V3", f"Requirement「{req_name}」没有任何 Scenario")
            req_line, scen_count = None, 0

        for ln, line in lines_outside_fences(read_text(f)):
            if REQ_RE.match(line):
                yield from close_scenario()
                yield from close_requirement()
                req_line, req_name = ln, REQ_RE.match(line).group(1).strip()
                continue
            if SCEN_RE.match(line):
                yield from close_scenario()
                if req_line is not None:
                    scen_count += 1
                    scen_line, scen_buf = ln, []
                continue
            if H4_RE.match(line) or H3_RE.match(line) or H2_RE.match(line):
                yield from close_scenario()
                if H3_RE.match(line) or H2_RE.match(line):
                    yield from close_requirement()
                continue
            if scen_line is not None:
                scen_buf.append(line)
        yield from close_scenario()
        yield from close_requirement()


def check_delta_markers(pkg: Path, ptype: str):
    if ptype != "change":
        return
    delta_files = list((pkg / "delta").glob("*.md")) if (pkg / "delta").exists() else []
    delta_files += list((pkg / "specs").rglob("*.md")) if (pkg / "specs").exists() else []
    for f in delta_files:
        rel = str(f.relative_to(pkg))
        legal_sections = 0
        for ln, line in lines_outside_fences(read_text(f)):
            if line.startswith("## "):
                if DELTA_HEAD_RE.match(line):
                    legal_sections += 1
                else:
                    yield finding(rel, ln, "V4", f"delta 文件只允许 ADDED/MODIFIED/REMOVED Requirements 节：{line.strip()}")
        if legal_sections == 0:
            yield finding(rel, 0, "V4", "delta 文件没有任何 ADDED/MODIFIED/REMOVED Requirements 节")


def check_task_backrefs(pkg: Path, ptype: str):
    f = pkg / "90-task-map.md"
    if not f.exists():
        return
    header, rows = first_table(read_text(f))
    if not header:
        return
    idx = next((i for i, c in enumerate(header) if "DoD" in c), None)
    if idx is None:
        yield finding("90-task-map.md", 0, "V5", "任务表缺少「对应 DoD」列")
        return
    # 合法引用形态（判例：x-infra 用 #3、#6；pilot 用 DoD#5；旧模板用 条目 N）
    ref_re = re.compile(r"(DoD|#\d+|条目\s*\d+)")
    for ln, cs in rows:
        val = cs[idx] if idx < len(cs) else ""
        if not ref_re.search(val):
            yield finding("90-task-map.md", ln, "V5", f"任务行「对应 DoD」列未回指任何条目：{val or '(空)'}")


def check_module_consistency(pkg: Path, ptype: str):
    f02, f90 = pkg / "02-module-breakdown.md", pkg / "90-task-map.md"
    if not (f02.exists() and f90.exists()):
        return
    m02 = set(col_values(read_text(f02), "模块"))
    m90 = set(col_values(read_text(f90), "模块"))
    if not m02 or not m90:
        return
    for name in sorted(m02 - m90):
        yield finding("90-task-map.md", 0, "V6", f"模块「{name}」在 02 总览有、90 缺")
    for name in sorted(m90 - m02):
        yield finding("02-module-breakdown.md", 0, "V6", f"模块「{name}」在 90 有、02 总览缺")


def check_status_vocab(pkg: Path, ptype: str):
    readme = pkg / "README.md"
    if readme.exists():
        for ln, line in enumerate(read_text(readme).splitlines(), 1):
            m = re.match(r"^>\s*状态：\s*(.+)$", line.strip())
            if m and not any(v in m.group(1) for v in STATUS_VOCAB):
                yield finding("README.md", ln, "V7", f"状态取值不在受控词汇内：{m.group(1)}")
    for name in ("02-module-breakdown.md", "90-task-map.md"):
        f = pkg / name
        if not f.exists():
            continue
        header, rows = first_table(read_text(f))
        if not header:
            continue
        idx = next((i for i, c in enumerate(header) if "状态" in c), None)
        if idx is None:
            continue
        for ln, cs in rows:
            if idx < len(cs) and cs[idx] and not any(v in cs[idx] for v in STATUS_VOCAB):
                yield finding(name, ln, "V7", f"状态取值不在受控词汇内：{cs[idx]}")


def check_task_files_complete(pkg: Path, ptype: str):
    for name in ("README.md", "dev-checklist.md"):
        if not (pkg / name).exists():
            yield finding("(package)", 0, "V8", f"task 包缺少必需文件：{name}")


def is_supported_task_status(value: str) -> bool:
    """V9 的双轨与历史 emoji 状态契约。"""
    token = TOKEN_RE.search(value)
    if token:
        return any(emoji in value for emoji in TASK_STATUS_PAIRS[token.group("box")])
    return any(emoji in value for emoji in TASK_STATUS_EMOJIS)


def check_task_checklist(pkg: Path, ptype: str):
    checklist = pkg / "dev-checklist.md"
    if not checklist.exists():
        return
    text = read_text(checklist)
    header, rows = first_table(text)
    if header != TASK_CHECKLIST_HEADER:
        actual = " | ".join(header or []) or "(无表格)"
        expected = " | ".join(TASK_CHECKLIST_HEADER)
        yield finding("dev-checklist.md", 0, "V9", f"checklist 表头必须为「{expected}」，实际为「{actual}」")
        return
    try:
        parse_checklist(pkg)
    except (FileNotFoundError, ValueError) as exc:
        yield finding("dev-checklist.md", 0, "V9", f"checklist 无法解析：{exc}")
        return

    known_ids: set[str] = set()
    parsed_rows: list[tuple[int, list[str], str]] = []
    for line, row in rows:
        raw_id = row[0].strip() if row else ""
        match = ID_COL_RE.fullmatch(raw_id)
        if not match:
            yield finding("dev-checklist.md", line, "V9", f"非法 task ID：{raw_id or '(空)'}")
            continue
        task_id = f"T{match.group(1)}"
        known_ids.add(task_id)
        parsed_rows.append((line, row, task_id))

    for line, row, _task_id in parsed_rows:
        status = row[4].strip() if len(row) > 4 else ""
        if not is_supported_task_status(status):
            yield finding("dev-checklist.md", line, "V9", f"非法状态：{status or '(空)'}")
        dependencies = parse_deps(row[3] if len(row) > 3 else "")
        for dependency in dependencies:
            if dependency not in known_ids:
                yield finding("dev-checklist.md", line, "V9", f"依赖「{dependency}」不在 task 表中")


def normalize_module_name(value: str) -> str:
    """归一化 Markdown/Mermaid 的节点标签，供 V10 做词法双向比对。"""
    value = re.sub(r"<br\s*/?>.*$", "", value, flags=re.IGNORECASE)
    value = value.split("·", 1)[0]
    value = re.split(r"[：:]", value, maxsplit=1)[0]
    value = re.sub(r"[`*_]", "", value)
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).lower()


def readme_modules(text: str) -> dict[str, str]:
    """提取 README「涉及模块」段落的项目符号或表格模块名。"""
    section: list[str] = []
    active = False
    for line in text.splitlines():
        if H2_RE.match(line):
            if line[3:].strip().startswith("涉及模块"):
                active = True
                continue
            if active:
                break
        if active:
            section.append(line)
    names: dict[str, str] = {}
    for line in section:
        match = re.match(r"^\s*[-*+]\s+(.+)$", line)
        if match:
            original = match.group(1).strip()
            normalized = normalize_module_name(original)
            if normalized:
                names[normalized] = original
    header, rows = first_table("\n".join(section))
    if header:
        index = next((i for i, cell in enumerate(header) if "模块" in cell), None)
        if index is not None:
            for _line, row in rows:
                if index < len(row):
                    original = row[index].strip()
                    normalized = normalize_module_name(original)
                    if normalized:
                        names[normalized] = original
    return names


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


def check_task_diagram(pkg: Path, ptype: str):
    readme = pkg / "README.md"
    diagram = pkg / "diagram.md"
    if not (readme.exists() and diagram.exists()):
        return
    declared = readme_modules(read_text(readme))
    rendered = mermaid_modules(read_text(diagram))
    for name in sorted(declared.keys() - rendered.keys()):
        yield finding("diagram.md", 0, "V10", f"README 模块「{declared[name]}」缺少 Mermaid 节点")
    for name in sorted(rendered.keys() - declared.keys()):
        yield finding("diagram.md", 0, "V10", f"Mermaid 节点「{rendered[name]}」未在 README 涉及模块声明")


README_H2_REQUIREMENTS = ("核心目标", "需求要点", "涉及模块", "架构拆分策略", "DoD", "Smoke / E2E 验收用例")


def check_task_readme(pkg: Path, ptype: str):
    readme = pkg / "README.md"
    if not readme.exists():
        return
    lines = read_text(readme).splitlines()
    h2s = [(line_number, line[3:].strip()) for line_number, line in enumerate(lines, 1) if H2_RE.match(line)]
    for heading in README_H2_REQUIREMENTS:
        if not any(actual.startswith(heading) for _line, actual in h2s):
            yield finding("README.md", 0, "V11", f"缺少以「{heading}」开头的二级标题")

    smoke_index = next((line_number - 1 for line_number, actual in h2s if actual.startswith("Smoke / E2E 验收用例")), None)
    if smoke_index is None:
        return
    end_index = next((
        index for index in range(smoke_index + 1, len(lines)) if H2_RE.match(lines[index])
    ), len(lines))
    smoke_lines = lines[smoke_index:end_index]
    if not any(H3_RE.match(line) and line[4:].strip().startswith("自动化测试责任") for line in smoke_lines):
        yield finding("README.md", smoke_index + 1, "V11", "Smoke / E2E 区域缺少三级标题「自动化测试责任」")
    has_fenced_command = any(line.lstrip().startswith("```") for line in smoke_lines)
    has_manual = any("manual" in line.lower() for line in smoke_lines)
    if not has_fenced_command and not has_manual:
        yield finding("README.md", smoke_index + 1, "V11", "Smoke / E2E 区域缺少围栏命令代码块或 manual 标记")


CHECKS = [
    check_files_complete,   # V1
    check_link_rules,       # V2
    check_req_scenario,     # V3
    check_delta_markers,    # V4
    check_task_backrefs,    # V5
    check_module_consistency,  # V6
    check_status_vocab,     # V7
]

TASK_CHECKS = [
    check_link_rules,       # V2
    check_task_files_complete,  # V8
    check_task_checklist,   # V9
    check_task_diagram,     # V10
    check_task_readme,      # V11
]


# ---------- 编排：status / graph（dev-pipeline/tasks 消费 dev-checklist） ----------
#
# 与 validate 段的区别：validate 作用于 docs/{spec,changes} 包，status/graph 作用于
# dev-pipeline/tasks/<task>/dev-checklist.md。两套目录体系，解析函数复用 first_table/cells。

# 引擎三态（编排只关心"能不能往下走"，把 6 个 emoji 中间态压缩）
DONE = "done"
TODO = "todo"
BLOCKED = "blocked"

# 状态列格式：token + emoji 双轨，如 "[x] 🟢" / "[ ] ⏳" / "[!] 🔴"。
# token 正则：匹配复选框 token；[x]→done、[!]→blocked、[ ](或无 token)→进入 emoji 降级。
TOKEN_RE = re.compile(r"\[(?P<box>[ x!])\]")

# 旧 emoji 兼容降级（无 token 时按 emoji 判）：🟢✅→done、🔴→blocked、其余→todo。
STATUS_EMOJI_MAP = {
    "🟢": DONE,
    "✅": DONE,
    "🔴": BLOCKED,
}

# task id 正则：T1 / T2 / #1 / #12 等。用于解析依赖列里的 id 引用（要求前缀，
# 避免把依赖文本里的裸数字误当 id）。
TASK_ID_RE = re.compile(r"(?:T|#)(\d+)", re.IGNORECASE)

# id 列归一化正则：T1 / #1 / 纯数字 1 都接受（id 列单独成格，裸数字无歧义）。
# 与 TASK_ID_RE 的区别：后者用于依赖列（混在文本里，必须前缀）；前者用于 id 列（独立格）。
ID_COL_RE = re.compile(r"(?:T|#)?(\d+)", re.IGNORECASE)

# 产物锚点：备注/涉及文件列里的 product:path 标记（相对 task 目录）。
PRODUCT_RE = re.compile(r"product:\s*([^\s,;]+)")


def parse_checklist(task_dir: Path) -> list[dict]:
    """解析 dev-checklist.md 的任务表，返回 task 列表（未判定引擎状态）。

    复用 first_table/cells 解析表格。表头必须含 "#"（或"编号"）列和"状态"列；
    "依赖"列可选（缺失当无依赖）；"涉及文件"列可选（用于提取 product 锚点）。

    返回的每个 task dict 含：id, title, deps(list[str]), raw_status(str),
    product(str|None)。引擎状态由 task_engine_status 单独判定，便于复用。
    """
    checklist = task_dir / "dev-checklist.md"
    if not checklist.exists():
        raise FileNotFoundError(f"缺少 dev-checklist.md：{task_dir}")
    header, rows = first_table(read_text(checklist))
    if not header:
        raise ValueError(f"dev-checklist.md 无可解析表格：{checklist}")

    def col_idx(*keywords: str) -> int | None:
        for kw in keywords:
            for i, c in enumerate(header):
                if kw in c:
                    return i
        return None

    id_idx = col_idx("#", "编号")
    title_idx = col_idx("任务", "标题")
    dep_idx = col_idx("依赖", "deps")
    status_idx = col_idx("状态")
    file_idx = col_idx("涉及文件", "文件")
    if id_idx is None or status_idx is None:
        missing = []
        if id_idx is None:
            missing.append("#/编号 列")
        if status_idx is None:
            missing.append("状态 列")
        raise ValueError(f"dev-checklist.md 表头缺关键列：{', '.join(missing)}")

    tasks: list[dict] = []
    for _ln, cs in rows:
        if len(cs) <= max(i for i in (id_idx, status_idx) if i is not None):
            continue
        raw_id = cs[id_idx].strip()
        if not raw_id or raw_id.lower() in ("—", "-", "n/a"):
            continue
        # 归一化 id：T1 / #1 / 纯数字 1 → "T1"（大写 T 前缀，与依赖列引用一致）
        # id 列用 ID_COL_RE（接受纯数字），依赖列用 TASK_ID_RE（要求前缀，见 parse_deps）
        m = ID_COL_RE.search(raw_id)
        if not m:
            continue
        norm_id = f"T{m.group(1)}"
        title = cs[title_idx].strip() if title_idx is not None and title_idx < len(cs) else ""
        raw_deps = cs[dep_idx].strip() if dep_idx is not None and dep_idx < len(cs) else ""
        raw_status = cs[status_idx].strip()
        raw_files = cs[file_idx].strip() if file_idx is not None and file_idx < len(cs) else ""
        product = None
        if raw_files:
            pm = PRODUCT_RE.search(raw_files)
            if pm:
                product = pm.group(1)
        tasks.append({
            "id": norm_id,
            "title": title,
            "deps": parse_deps(raw_deps),
            "raw_status": raw_status,
            "product": product,
        })
    return tasks


def parse_deps(raw: str) -> list[str]:
    """解析依赖列：支持 'T1' / 'T2,T3' / 'T2/T3' / '#1 #2' / '—' / '' → 归一化 id 列表。

    多分隔符（, / 空格）混合也能处理；无依赖符号（—、-、空）返回空列表。
    """
    if not raw or raw.strip() in ("—", "-", ""):
        return []
    ids = TASK_ID_RE.findall(raw)
    return [f"T{n}" for n in ids]


def task_engine_status(raw_status: str) -> str:
    """从状态列文本判定引擎状态（done/todo/blocked）。

    双轨判定：先尝试 token（[x]/[!]），无 token 则按 emoji 降级。
    这让纯 emoji 旧 checklist（如 qa-gate-pipeline）无需迁移即可被解析。
    """
    m = TOKEN_RE.search(raw_status)
    if m:
        box = m.group("box")
        if box == "x":
            return DONE
        if box == "!":
            return BLOCKED
        # box 是空格 → token 显式标记未完成，不进 emoji 降级
        return TODO
    # 无 token：按 emoji 降级
    for emoji, status in STATUS_EMOJI_MAP.items():
        if emoji in raw_status:
            return status
    return TODO


def resolve_task_list(task_dir: Path) -> tuple[list[dict], list[dict]]:
    """解析 checklist 并判定引擎状态 + 产物锚点交叉验证。

    返回 (tasks, product_findings)。每个 task 追加 'status' 和 'product_check' 字段。
    product_check：done 但文件缺失→"missing"；todo 但文件已存在→"stale"；无锚点→None。
    这是可选交叉验证，不改变 status 本身（主判依据是 token）。
    """
    raw_tasks = parse_checklist(task_dir)
    tasks: list[dict] = []
    product_findings: list[dict] = []
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
                product_findings.append({
                    "id": t["id"], "rule": "product",
                    "msg": f"标记 done 但产物缺失：{t['product']}",
                })
            elif status == TODO and exists:
                entry["product_check"] = "stale"
                product_findings.append({
                    "id": t["id"], "rule": "product",
                    "msg": f"标记 todo 但产物已存在：{t['product']}",
                })
        tasks.append(entry)
    return tasks, product_findings


def compute_progress(tasks: list[dict]) -> dict:
    """统计进度：total/done/todo/blocked。"""
    total = len(tasks)
    done = sum(1 for t in tasks if t["status"] == DONE)
    blocked = sum(1 for t in tasks if t["status"] == BLOCKED)
    todo = total - done - blocked
    return {"total": total, "done": done, "todo": todo, "blocked": blocked}


def status_command(task_dir: Path, as_json: bool) -> int:
    """status 子命令：解析 task 的 dev-checklist，输出任务状态 + 进度。"""
    try:
        tasks, product_findings = resolve_task_list(task_dir)
    except (FileNotFoundError, ValueError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    progress = compute_progress(tasks)
    payload = {"task": task_dir.name, "tasks": tasks, "progress": progress}
    if product_findings:
        payload["product_findings"] = product_findings
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
    """Kahn 拓扑排序 + 环检测。

    返回 (order, cycle_nodes)。order 覆盖所有无环节点；cycle_nodes 是环内节点
    （order 长度 < 节点总数时存在）。排序后入队保证确定性（对标 OpenSpec getBuildOrder）。
    """
    # 只保留指向已知 task 的依赖（悬空 id 由 graph 的 blocked 暴露，不污染拓扑）
    valid = set(task_ids)
    adj: dict[str, list[str]] = {tid: [] for tid in task_ids}
    indeg: dict[str, int] = {tid: 0 for tid in task_ids}
    for tid in task_ids:
        for dep in deps_map.get(tid, []):
            if dep in valid:
                adj[dep].append(tid)
                indeg[tid] += 1
    # Kahn：入度 0 的排序后入队，逐层弹出
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
    """算 ready / blocked / order / parallel_batches。

    ready：依赖全 done 且自身未 done（对标 OpenSpec getNextArtifacts）。
    blocked：有未满足依赖（含悬空 id），附 missing 列表（对标 getBlocked）。
    order：合法拓扑序（无环时覆盖全部节点）。
    parallel_batches：按拓扑层分层，同层可并行派子 agent。
    """
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
                missing.append(dep)            # 悬空依赖
            elif by_id[dep]["status"] != DONE:
                missing.append(dep)            # 依赖未完成
        if missing:
            blocked.append({"id": t["id"], "missing": missing})
        else:
            ready.append(t["id"])

    # parallel_batches：按拓扑层分组的"待执行批次"。
    # 只含未 done 的任务；done 的任务视为前置已满足（直接计入 placed 起步集），
    # 让分层从"下一批该做什么"开始，而非把已完成的也排进批次。
    # blocked（悬空依赖或依赖未完成）的任务：悬空的不进批次（无法满足），
    # 依赖未完成的正常进批次（等前置层完成即可）。
    done_ids = {t["id"] for t in tasks if t["status"] == DONE}
    batches: list[list[str]] = []
    placed: set[str] = set(done_ids)  # done 的任务视作已置位，从第 0 层起算
    for _ in range(len(order)):
        layer = []
        for tid in order:
            if tid in placed:
                continue
            if by_id[tid]["status"] == DONE:
                placed.add(tid)
                continue
            deps = deps_map[tid]
            # 该任务可入本层：所有已知依赖都已 placed（含 done 起步集）
            # 悬空依赖（不在 by_id）→ 无法满足，跳过不进批次
            if all(d in placed for d in deps if d in by_id) and all(
                d in by_id for d in deps
            ):
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


def graph_command(task_dir: Path, as_json: bool) -> int:
    """graph 子命令：拓扑排序 + ready/blocked + 环检测。"""
    try:
        tasks, _ = resolve_task_list(task_dir)
    except (FileNotFoundError, ValueError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    result = compute_graph(tasks)
    cycle = result["cycle"]
    if cycle and as_json:
        # 环是错误状态：输出 JSON 但退出码 1（agent 契约：JSON 模式留一个完整文档）
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
        print(f"  环内节点：{', '.join(cycle)}", file=sys.stderr)
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


# ---------- 编排 ----------

def discover(root: Path) -> list[Path]:
    pkgs = []
    for base in ("docs/spec", "docs/changes", "docs/specs"):
        d = root / base
        if d.is_dir():
            for sub in sorted(d.iterdir()):
                if sub.is_dir() and sub.name != "archive":
                    pkgs.append(sub)
    return pkgs


def validate_pkg(pkg: Path, include_legacy: bool) -> dict:
    ptype = detect_type(pkg)
    result = {"path": str(pkg), "type": ptype, "skipped": False, "findings": []}
    if ptype == "legacy" and not include_legacy:
        result["skipped"] = True
        return result
    if ptype == "unknown":
        result["findings"].append(
            finding("(package)", 0, "V0", "无法识别包类型（既无 proposal.md / 01-goals / spec.md，也非 legacy）")
        )
        return result
    checks = TASK_CHECKS if ptype == "task" else CHECKS
    for check in checks:
        if ptype == "legacy" and check is check_files_complete:
            continue  # legacy 不按新档位查齐全
        try:
            result["findings"].extend(check(pkg, ptype))
        except Exception as e:  # 单条规则崩溃不拖垮整体
            result["findings"].append(finding("(package)", 0, "V0", f"{check.__name__} 执行失败：{e}"))
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="xdev", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="结构校验（机械项）")
    v.add_argument("targets", nargs="*", help="包目录；缺省时自动发现 docs/{spec,changes,specs}/*/")
    v.add_argument("--include-legacy", action="store_true", help="把 legacy 图集结构的旧包也纳入检查")
    v.add_argument("--json", action="store_true", dest="as_json", help="机器可读输出")

    s = sub.add_parser("status", help="解析 task 的 dev-checklist，输出任务状态 + 进度")
    s.add_argument("task_dir", help="task 目录（dev-pipeline/tasks/<name>/，内含 dev-checklist.md）")
    s.add_argument("--json", action="store_true", dest="as_json", help="机器可读输出")

    g = sub.add_parser("graph", help="基于 status 做依赖拓扑排序，输出 ready/blocked/并行批次")
    g.add_argument("task_dir", help="task 目录")
    g.add_argument("--json", action="store_true", dest="as_json", help="机器可读输出")

    i = sub.add_parser("instructions", help="返回 task 产物模板、填写规则与依赖事实")
    i.add_argument("artifact_id", help=f"artifact ID：{', '.join(ARTIFACTS)}")
    i.add_argument("--task", required=True, dest="task_dir", help="目标 task 目录")
    i.add_argument("--json", action="store_true", dest="as_json", help="机器可读输出")

    c = sub.add_parser("scaffold", help="增量创建 task 包骨架，已有文件保持原状")
    c.add_argument("task_dir", help="目标 task 目录")
    c.add_argument("--with-diagram", action="store_true", help="同时创建可选 diagram.md")
    c.add_argument("--json", action="store_true", dest="as_json", help="机器可读输出")

    args = parser.parse_args(argv)

    if args.cmd == "instructions":
        return instructions_command(args.artifact_id, Path(args.task_dir), args.as_json)

    if args.cmd == "scaffold":
        return scaffold_command(Path(args.task_dir), args.with_diagram, args.as_json)

    if args.cmd in ("status", "graph"):
        task_dir = Path(args.task_dir)
        if not task_dir.is_dir():
            print(f"错误：不是目录：{task_dir}", file=sys.stderr)
            return 2
        if args.cmd == "status":
            return status_command(task_dir, args.as_json)
        return graph_command(task_dir, args.as_json)

    if args.targets:
        pkgs = [Path(t) for t in args.targets]
        for p in pkgs:
            if not p.is_dir():
                print(f"错误：不是目录：{p}", file=sys.stderr)
                return 2
    else:
        pkgs = discover(Path.cwd())
        if not pkgs:
            print("错误：未发现任何包（docs/spec|changes|specs 下无子目录），可显式传目录", file=sys.stderr)
            return 2

    results = [validate_pkg(p, args.include_legacy) for p in pkgs]
    total = sum(len(r["findings"]) for r in results)
    skipped = sum(1 for r in results if r["skipped"])

    if args.as_json:
        print(json.dumps({"packages": results, "total_findings": total, "skipped_legacy": skipped}, ensure_ascii=False, indent=2))
    else:
        for r in results:
            tag = f"[{r['type']}]"
            if r["skipped"]:
                print(f"== {r['path']}  {tag}  跳过（legacy；--include-legacy 可纳入）")
                continue
            print(f"== {r['path']}  {tag}")
            if not r["findings"]:
                print("   ok")
            for fd in r["findings"]:
                loc = f"{fd['file']}:{fd['line']}" if fd["line"] else fd["file"]
                print(f"   {loc}  {fd['rule']}  {fd['msg']}")
        mark = "✓" if total == 0 else "✗"
        print(f"{mark} validate：{len(results)} 包，{total} finding(s)，{skipped} legacy 跳过")

    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
