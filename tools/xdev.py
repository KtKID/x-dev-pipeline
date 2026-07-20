#!/usr/bin/env python3
"""xdev — x-dev-pipeline 的确定性工具层（立法层）。

确定性工具层把散落在 SKILL.md 散文里的格式法律搬进代码。skills 管判断，
本工具管机械。

规则编号用于 run-log 聚合；V1-V7 保持旧版契约，V13-V18 对应 skills/x-spec2/：
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
  V11 task README 的 risk 与按等级要求的章节
  V12 task README 验收 Requirement/Scenario 结构与验证标记
  V13 spec2 包结构、版本标记与 task 产物隔离
  V14 spec2 建模六元组覆盖与落点
  V15 spec2 用户要求到 Requirement 追溯
  V16 spec2 Requirement 与模块双向覆盖、模块状态
  V17 spec2 design.md 按需生成
  V18 spec2 U/J/D 理由层结构、引用与消费闭合

用法：
  python3 tools/xdev.py validate [包目录 ...] [--include-legacy] [--json]
  不给目录时，从当前工作目录发现 docs/spec/*/、docs/changes/*/、docs/specs/*/。
  legacy 包（含 diagrams.md / *.html 图集的旧结构）默认跳过，--include-legacy 纳入
  （纳入时不查 V1 档位齐全，只查其余规则）。

退出码：0 全部通过；1 存在 issue；2 用法或 IO 错误。
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
  委托 tools/req.py：只认 docs/spec/<spec-name>/tasks/<task-name>/ 结构，增量创建
  dev-checklist.md（不产 README）与可选 diagram.md；已有文件逐字节保留。

  python3 tools/xdev.py verify <task-dir> [--json] [--only <id>]
  解析 dev-report 的 fenced verify 块，复跑自动命令并对账 README 自动验收场景。

  python3 tools/xdev.py flag <task-dir> --task T2,T3 --severity P0 \
      --loc src/a.py:10 --msg "空输入未处理" [--new-round] [--json]
  由代码分配 issue 编号、写 QA Gate ledger，并对 P0/P1 task 执行只降级更新。

退出码：0 正常；1 存在 issue 或依赖环；2 用法或 IO 错误。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import req

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
SPEC2_REQUIRED = ["spec.md", "modules.md"]
CHANGE_REQUIRED = ["proposal.md", "tasks.md"]
SPEC2_FORBIDDEN_TASK_FILES = ("task.md", "tasks.md", "90-task-map.md", "dev-checklist.md")
MODEL_TUPLE = ("数据流", "状态", "时序", "资源", "不变量", "故障")

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SPEC2_LINK_RE = re.compile(r"\[[^\]]*\]\((<[^>]+>|[^)]+)\)")
REQ_RE = re.compile(r"^###\s+Requirement:\s*(.*)$")
SCEN_RE = re.compile(r"^####\s+Scenario:\s*(.*)$")
SPEC2_MARKER_RE = re.compile(r"^>\s*spec_version:\s*2\s*$", re.IGNORECASE)
H3_RE = re.compile(r"^###\s+")
H4_RE = re.compile(r"^####\s+")
H2_RE = re.compile(r"^##\s+")
DELTA_HEAD_RE = re.compile(r"^##\s+(ADDED|MODIFIED|REMOVED)\s+Requirements\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
RISK_RE = re.compile(r"^risk:\s*(\S+)\s*$", re.IGNORECASE)
VERIFY_FENCE_RE = re.compile(r"^\s*```verify\s*$", re.IGNORECASE)
FENCE_END_RE = re.compile(r"^\s*```\s*$")
VALIDATION_RE = re.compile(r"^\s*[-*+]?\s*验证:\s*(auto|manual)\s*$", re.IGNORECASE)
SPEC2_ID_RE = re.compile(r"(?<![A-Za-z0-9_-])([UJD]\d+)(?![A-Za-z0-9_-])")

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TASK_CHECKLIST_HEADER = ["#", "任务", "涉及文件", "依赖", "状态", "fix"]
TASK_STATUS_PAIRS = {
    " ": ("⏳", "▶️", "🟡"),
    "x": ("🟢", "✅"),
    "!": ("🔴",),
}
TASK_STATUS_EMOJIS = tuple(emoji for emojis in TASK_STATUS_PAIRS.values() for emoji in emojis)

INSTRUCTION_SUFFIX = "以上规则与模板内 HTML 注释用于填写约束；完成产物时删除模板注释，不要复制规则文字。"

README_INSTRUCTION = """先写 README 头部 risk: Q0|Q1|Q2|Q3。Q0/Q1 至少含核心目标与验收；Q2/Q3 还含需求要点、涉及模块、架构拆分策略和技术设计。验收由 Requirement/Scenario 组成：每个 Scenario 必须有 WHEN、THEN 与验证: auto|manual；自动场景必须由 dev-report verify 块以 scenario 回指。自动化测试责任放在验收节内，x-dev 记录真实 verify 证据。\n\n""" + INSTRUCTION_SUFFIX
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


def issue(file: str, line: int, rule: str, msg: str) -> dict:
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


def table_in_h2(text: str, prefix: str):
    """读取指定 H2 内第一个表，并把行号换算回原文件。"""
    lines = text.splitlines()
    start, end = section_bounds(lines, prefix)
    if start is None:
        return None, []
    header, rows = first_table("\n".join(lines[start + 1:end]))
    return header, [(start + 1 + line, row) for line, row in rows]


def requirement_entries(text: str) -> list[tuple[int, str]]:
    return [
        (line, match.group(1).strip())
        for line, value in lines_outside_fences(text)
        if (match := REQ_RE.match(value))
    ]


def split_refs(value: str) -> list[str]:
    value = re.sub(r"[`*]", "", value).replace("<br>", "、").replace("<br/>", "、")
    return [part.strip() for part in re.split(r"[、,，;；]", value) if part.strip()]


def clean_cell(value: str) -> str:
    return re.sub(r"[`*]", "", value).strip()


def spec2_id_refs(value: str, prefixes: str = "UJD") -> list[str]:
    return [token for token in SPEC2_ID_RE.findall(value) if token[0] in prefixes]


def spec2_module_names(pkg: Path) -> dict[str, list[int]]:
    modules = pkg / "modules.md"
    if not modules.exists():
        return {}
    header, rows = table_in_h2(read_text(modules), "模块总览")
    if not header:
        return {}
    module_index = next((index for index, name in enumerate(header) if "模块" in name), None)
    if module_index is None:
        return {}
    result: dict[str, list[int]] = {}
    for line, row in rows:
        name = clean_cell(row[module_index]) if module_index < len(row) else ""
        if name:
            result.setdefault(name, []).append(line)
    return result


def spec2_user_definitions(pkg: Path) -> dict[str, list[tuple[int, str]]]:
    spec = pkg / "spec.md"
    if not spec.exists():
        return {}
    header, rows = table_in_h2(read_text(spec), "用户要求追溯")
    if not header:
        return {}
    id_index = next((index for index, name in enumerate(header) if "U-ID" in name), None)
    target_index = next((index for index, name in enumerate(header) if "对应" in name), None)
    if id_index is None or target_index is None:
        return {}
    result: dict[str, list[tuple[int, str]]] = {}
    for line, row in rows:
        user_id = clean_cell(row[id_index]) if id_index < len(row) else ""
        target = clean_cell(row[target_index]) if target_index < len(row) else ""
        if user_id:
            result.setdefault(user_id, []).append((line, target))
    return result


def spec2_decision_definitions(pkg: Path) -> dict[str, list[int]]:
    modules = pkg / "modules.md"
    if not modules.exists():
        return {}
    header, rows = table_in_h2(read_text(modules), "关键决策")
    if not header:
        return {}
    id_index = next((index for index, name in enumerate(header) if "D-ID" in name), None)
    if id_index is None:
        return {}
    result: dict[str, list[int]] = {}
    for line, row in rows:
        decision_id = clean_cell(row[id_index]) if id_index < len(row) else ""
        if decision_id:
            result.setdefault(decision_id, []).append(line)
    return result


def markdown_anchor(title: str) -> str:
    title = re.sub(r"[`*_~]", "", title.strip().lower())
    title = re.sub(r"[^\w\-\s\u4e00-\u9fff]", "", title)
    return re.sub(r"[-\s]+", "-", title).strip("-")


def heading_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for _line, value in lines_outside_fences(text):
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", value)
        if not match:
            continue
        base = markdown_anchor(match.group(1))
        if not base:
            continue
        count = counts.get(base, 0)
        anchors.add(base if count == 0 else f"{base}-{count}")
        counts[base] = count + 1
    return anchors


def parse_package_location(value: str) -> tuple[str, str] | None:
    cleaned = re.sub(r"[`*]", "", value).strip()
    if "#" not in cleaned:
        return None
    path, anchor = cleaned.split("#", 1)
    if not path.strip() or not anchor.strip():
        return None
    return path.strip(), anchor.strip().lower()


def package_location_issue(pkg: Path, value: str) -> str | None:
    parsed = parse_package_location(value)
    if parsed is None:
        return "落点必须使用 文件#段落锚点"
    raw_path, anchor = parsed
    if raw_path.startswith(("/", "file://")) or re.match(r"^[A-Za-z]:[\\/]", raw_path):
        return "落点必须位于当前 spec 包内"
    target = (pkg / raw_path.removeprefix("./")).resolve()
    try:
        target.relative_to(pkg.resolve())
    except ValueError:
        return "落点必须位于当前 spec 包内"
    if not target.is_file():
        return f"落点文件不存在：{raw_path}"
    if anchor not in heading_anchors(read_text(target)):
        return f"落点段落不存在：{raw_path}#{anchor}"
    return None


SCENARIO_PROFILES = {
    "legacy": {"given": True, "validation": False, "rule": "V3", "orphan": False},
    "spec2": {"given": False, "validation": True, "rule": "V3", "orphan": True},
    "task": {"given": False, "validation": True, "rule": "V12", "orphan": True},
}


def scenario_contract_issues(lines: list[tuple[int, str]], rel: str, profile: str):
    """按包 profile 校验 Requirement/Scenario，供 spec 与 task 共用。"""
    contract = SCENARIO_PROFILES[profile]
    req_line = None
    req_name = ""
    scen_count = 0
    scen_line = None
    scen_name = ""
    scen_buf: list[str] = []

    def close_scenario():
        nonlocal scen_line, scen_name, scen_buf
        if scen_line is not None:
            body = "\n".join(scen_buf)
            required = ["WHEN", "THEN"]
            if contract["given"]:
                required.insert(0, "GIVEN")
            missing = [key for key in required if not re.search(rf"\b{key}\b", body)]
            if missing:
                yield issue(rel, scen_line, contract["rule"], f"Scenario「{scen_name}」缺少 {'/'.join(missing)}")
            if contract["validation"] and not any(VALIDATION_RE.match(line) for line in scen_buf):
                yield issue(rel, scen_line, contract["rule"], f"Scenario「{scen_name}」缺少 验证: auto|manual 标记")
        scen_line, scen_name, scen_buf = None, "", []

    def close_requirement():
        nonlocal req_line, req_name, scen_count
        if req_line is not None and scen_count == 0:
            yield issue(rel, req_line, contract["rule"], f"Requirement「{req_name}」没有任何 Scenario")
        req_line, req_name, scen_count = None, "", 0

    for line_number, value in lines:
        if match := REQ_RE.match(value):
            yield from close_scenario()
            yield from close_requirement()
            req_line, req_name = line_number, match.group(1).strip()
            continue
        if match := SCEN_RE.match(value):
            yield from close_scenario()
            scen_name = match.group(1).strip()
            if req_line is None:
                if contract["orphan"]:
                    yield issue(rel, line_number, contract["rule"], "Scenario 没有上级 Requirement")
            else:
                scen_count += 1
            scen_line, scen_buf = line_number, []
            continue
        if H4_RE.match(value) or H3_RE.match(value) or H2_RE.match(value):
            yield from close_scenario()
            if H3_RE.match(value) or H2_RE.match(value):
                yield from close_requirement()
            continue
        if scen_line is not None:
            scen_buf.append(value)
    yield from close_scenario()
    yield from close_requirement()


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


# ---------- 包类型识别 ----------

def has_spec2_marker(pkg: Path) -> bool:
    spec = pkg / "spec.md"
    if not spec.is_file():
        return False
    return any(SPEC2_MARKER_RE.match(line) for _number, line in lines_outside_fences(read_text(spec)))


def detect_type(pkg: Path) -> str:
    parts = pkg.resolve().parts
    if (pkg / "modules.md").exists() or has_spec2_marker(pkg):
        return "spec2"
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
    if ptype == "spec2":
        for name in SPEC2_REQUIRED:
            if not (pkg / name).exists():
                yield issue("(package)", 0, "V13", f"spec2 包缺少必需文件：{name}")
        if not has_spec2_marker(pkg):
            yield issue("spec.md", 0, "V13", "spec2 包缺少 > spec_version: 2 标记")
        for name in SPEC2_FORBIDDEN_TASK_FILES:
            if (pkg / name).exists():
                yield issue(name, 0, "V13", f"spec2 包不得包含 task 产物：{name}")
    elif ptype == "spec7":
        for name in SPEC7_REQUIRED:
            if not (pkg / name).exists():
                yield issue("(package)", 0, "V1", f"spec 包缺少必需文件：{name}")
    elif ptype == "change":
        for name in CHANGE_REQUIRED:
            if not (pkg / name).exists():
                yield issue("(package)", 0, "V1", f"change 包缺少必需文件：{name}")
        delta_files = list((pkg / "delta").glob("*.md")) if (pkg / "delta").exists() else []
        delta_files += list((pkg / "specs").rglob("*.md")) if (pkg / "specs").exists() else []
        if not delta_files:
            yield issue("(package)", 0, "V1", "change 包缺少 delta（delta/*.md 或 specs/**.md 至少一个）")


def check_link_rules(pkg: Path, ptype: str):
    for f in md_files(pkg):
        rel = str(f.relative_to(pkg))
        for ln, line in lines_outside_fences(read_text(f)):
            link_re = SPEC2_LINK_RE if ptype == "spec2" else LINK_RE
            for m in link_re.finditer(line):
                target = m.group(1).strip()
                if target.startswith("<") and target.endswith(">"):
                    target = target[1:-1].strip()
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                if ptype == "spec2":
                    if target.startswith("file://"):
                        yield issue(rel, ln, "V2", f"禁止 file:// 链接：({target})")
                        continue
                    if target.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", target):
                        yield issue(rel, ln, "V2", f"禁止机器绑定绝对路径：({target})")
                        continue
                    raw_path = target.split("#", 1)[0]
                    if not raw_path:
                        continue
                    if raw_path.startswith(("./", "../")):
                        dest = (f.parent / raw_path).resolve()
                    else:
                        dest = (PLUGIN_ROOT / raw_path).resolve()
                    if not dest.exists():
                        yield issue(rel, ln, "V2", f"链接目标不存在：({target})")
                    continue
                if target.startswith("./"):
                    dest = f.parent / target.split("#", 1)[0]
                    if not dest.exists():
                        yield issue(rel, ln, "V2", f"链接目标不存在：({target})")
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
                yield issue(rel, ln, "V2", f"{msg}：({target})")


def check_req_scenario(pkg: Path, ptype: str):
    files = [pkg / "spec.md"] if ptype == "spec2" else md_files(pkg)
    profile = "spec2" if ptype == "spec2" else "legacy"
    for f in files:
        if not f.exists():
            continue
        rel = str(f.relative_to(pkg))
        yield from scenario_contract_issues(list(lines_outside_fences(read_text(f))), rel, profile)


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
                    yield issue(rel, ln, "V4", f"delta 文件只允许 ADDED/MODIFIED/REMOVED Requirements 节：{line.strip()}")
        if legal_sections == 0:
            yield issue(rel, 0, "V4", "delta 文件没有任何 ADDED/MODIFIED/REMOVED Requirements 节")


def check_task_backrefs(pkg: Path, ptype: str):
    f = pkg / "90-task-map.md"
    if not f.exists():
        return
    header, rows = first_table(read_text(f))
    if not header:
        return
    idx = next((i for i, c in enumerate(header) if "DoD" in c), None)
    if idx is None:
        yield issue("90-task-map.md", 0, "V5", "任务表缺少「对应 DoD」列")
        return
    # 合法引用形态（判例：x-infra 用 #3、#6；pilot 用 DoD#5；旧模板用 条目 N）
    ref_re = re.compile(r"(DoD|#\d+|条目\s*\d+)")
    for ln, cs in rows:
        val = cs[idx] if idx < len(cs) else ""
        if not ref_re.search(val):
            yield issue("90-task-map.md", ln, "V5", f"任务行「对应 DoD」列未回指任何条目：{val or '(空)'}")


def check_module_consistency(pkg: Path, ptype: str):
    f02, f90 = pkg / "02-module-breakdown.md", pkg / "90-task-map.md"
    if not (f02.exists() and f90.exists()):
        return
    m02 = set(col_values(read_text(f02), "模块"))
    m90 = set(col_values(read_text(f90), "模块"))
    if not m02 or not m90:
        return
    for name in sorted(m02 - m90):
        yield issue("90-task-map.md", 0, "V6", f"模块「{name}」在 02 总览有、90 缺")
    for name in sorted(m90 - m02):
        yield issue("02-module-breakdown.md", 0, "V6", f"模块「{name}」在 90 有、02 总览缺")


def check_status_vocab(pkg: Path, ptype: str):
    readme = pkg / "README.md"
    if readme.exists():
        for ln, line in enumerate(read_text(readme).splitlines(), 1):
            m = re.match(r"^>\s*状态：\s*(.+)$", line.strip())
            if m and not any(v in m.group(1) for v in STATUS_VOCAB):
                yield issue("README.md", ln, "V7", f"状态取值不在受控词汇内：{m.group(1)}")
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
                yield issue(name, ln, "V7", f"状态取值不在受控词汇内：{cs[idx]}")


def spec2_model_rows(pkg: Path):
    spec = pkg / "spec.md"
    if not spec.exists():
        return None, []
    return table_in_h2(read_text(spec), "建模覆盖声明")


def check_spec2_modeling(pkg: Path, ptype: str):
    if ptype != "spec2":
        return
    header, rows = spec2_model_rows(pkg)
    if not header:
        yield issue("spec.md", 0, "V14", "spec.md 缺少「建模覆盖声明」表")
        return
    tuple_index = next((index for index, name in enumerate(header) if "元组" in name), None)
    value_index = next(
        (index for index, name in enumerate(header) if "落点" in name or "不适用" in name or "结论" in name),
        None,
    )
    if tuple_index is None or value_index is None:
        yield issue("spec.md", 0, "V14", "建模覆盖声明表必须含「元组」与「落点或不适用理由」列")
        return

    seen: dict[str, int] = {}
    for line, row in rows:
        tuple_name = row[tuple_index].strip() if tuple_index < len(row) else ""
        value = row[value_index].strip() if value_index < len(row) else ""
        if tuple_name not in MODEL_TUPLE:
            yield issue("spec.md", line, "V14", f"未知建模元组：{tuple_name or '(空)'}")
            continue
        if tuple_name in seen:
            yield issue("spec.md", line, "V14", f"建模元组重复：{tuple_name}")
        seen[tuple_name] = line
        if not value:
            yield issue("spec.md", line, "V14", f"建模元组「{tuple_name}」缺少落点或不适用理由")
            continue
        if value.startswith("不适用"):
            if not re.match(r"^不适用\s*[：:]\s*\S.+$", value):
                yield issue("spec.md", line, "V14", f"建模元组「{tuple_name}」的不适用理由为空")
            continue
        if message := package_location_issue(pkg, value):
            yield issue("spec.md", line, "V14", f"建模元组「{tuple_name}」{message}")

    for tuple_name in MODEL_TUPLE:
        if tuple_name not in seen:
            yield issue("spec.md", 0, "V14", f"建模覆盖声明缺少元组：{tuple_name}")


def check_spec2_requirement_names(pkg: Path, ptype: str):
    if ptype != "spec2" or not (pkg / "spec.md").exists():
        return
    entries = requirement_entries(read_text(pkg / "spec.md"))
    counts: dict[str, list[int]] = {}
    for line, name in entries:
        if not name:
            yield issue("spec.md", line, "V15", "Requirement 名不能为空")
            continue
        counts.setdefault(name, []).append(line)
    for name, lines in counts.items():
        if len(lines) > 1:
            yield issue("spec.md", lines[1], "V15", f"Requirement 名重名：{name}")


def check_spec2_user_trace(pkg: Path, ptype: str):
    if ptype != "spec2" or not (pkg / "spec.md").exists():
        return
    text = read_text(pkg / "spec.md")
    header, rows = table_in_h2(text, "用户要求追溯")
    if not header:
        yield issue("spec.md", 0, "V15", "spec.md 缺少「用户要求追溯」表")
        return
    id_index = next((index for index, name in enumerate(header) if "U-ID" in name), None)
    raw_index = next((index for index, name in enumerate(header) if "用户原话" in name), None)
    target_index = next((index for index, name in enumerate(header) if "对应" in name), None)
    location_index = next((index for index, name in enumerate(header) if "落实位置" in name), None)
    if None in (id_index, raw_index, target_index, location_index):
        yield issue("spec.md", 0, "V15", "用户要求追溯表必须含「U-ID」「用户原话要求」「对应目标」「落实位置」列")
        return
    if not rows:
        yield issue("spec.md", 0, "V15", "用户要求追溯表至少需要一行")
        return

    names = [name for _line, name in requirement_entries(text)]
    requirement_counts = {name: names.count(name) for name in set(names)}
    module_counts = spec2_module_names(pkg)
    user_ids: dict[str, int] = {}
    for line, row in rows:
        user_id = clean_cell(row[id_index]) if id_index < len(row) else ""
        raw = row[raw_index].strip() if raw_index < len(row) else ""
        target = clean_cell(row[target_index]) if target_index < len(row) else ""
        location = row[location_index].strip() if location_index < len(row) else ""
        if not re.fullmatch(r"U\d+", user_id):
            yield issue("spec.md", line, "V15", f"用户要求 U-ID 非法：{user_id or '(空)'}")
        elif user_id in user_ids:
            yield issue("spec.md", line, "V15", f"用户要求 U-ID 重名：{user_id}")
        else:
            user_ids[user_id] = line
        if not raw:
            yield issue("spec.md", line, "V15", "用户原话要求不能为空")
        if not target:
            yield issue("spec.md", line, "V15", "用户要求缺少对应目标")
        elif requirement_counts.get(target, 0) + len(module_counts.get(target, [])) != 1:
            yield issue("spec.md", line, "V15", f"用户要求回指目标不存在或不唯一：{target}")
        if not location:
            yield issue("spec.md", line, "V15", "用户要求缺少落实位置")
        elif message := package_location_issue(pkg, location):
            yield issue("spec.md", line, "V15", f"用户要求落实位置无效：{message}")


def check_spec2_modules(pkg: Path, ptype: str):
    if ptype != "spec2" or not (pkg / "modules.md").exists() or not (pkg / "spec.md").exists():
        return
    spec_text = read_text(pkg / "spec.md")
    modules_text = read_text(pkg / "modules.md")
    requirements = [name for _line, name in requirement_entries(spec_text) if name]
    requirement_counts = {name: requirements.count(name) for name in set(requirements)}
    header, rows = table_in_h2(modules_text, "模块总览")
    if not header:
        yield issue("modules.md", 0, "V16", "modules.md 缺少「模块总览」表")
        return
    module_index = next((index for index, name in enumerate(header) if "模块" in name), None)
    status_index = next((index for index, name in enumerate(header) if "状态" in name), None)
    decision_index = next((index for index, name in enumerate(header) if "决策回指" in name), None)
    req_index = next((index for index, name in enumerate(header) if "Requirement" in name), None)
    if None in (module_index, status_index, decision_index, req_index):
        yield issue("modules.md", 0, "V16", "模块总览表必须含「模块」「决策回指」「状态」「回指 Requirement」列")
        return
    if not rows:
        yield issue("modules.md", 0, "V16", "模块总览表至少需要一个模块")
        return

    covered: set[str] = set()
    module_names: set[str] = set()
    user_definitions = spec2_user_definitions(pkg)
    decision_definitions = spec2_decision_definitions(pkg)
    for line, row in rows:
        module = row[module_index].strip() if module_index < len(row) else ""
        status = re.sub(r"[`*]", "", row[status_index]).strip() if status_index < len(row) else ""
        decision_refs = spec2_id_refs(row[decision_index], "UD") if decision_index < len(row) else []
        refs = split_refs(row[req_index]) if req_index < len(row) else []
        if not module:
            yield issue("modules.md", line, "V16", "模块名不能为空")
        elif module in module_names:
            yield issue("modules.md", line, "V16", f"模块名重复：{module}")
        module_names.add(module)
        if status not in STATUS_VOCAB:
            yield issue("modules.md", line, "V16", f"模块「{module or '(空)'}」状态取值非法：{status or '(空)'}")
        if not decision_refs:
            yield issue("modules.md", line, "V16", f"模块「{module or '(空)'}」缺少决策回指 U-ID/D-ID")
        for ref in decision_refs:
            if ref.startswith("U"):
                definitions = user_definitions.get(ref, [])
                if len(definitions) != 1:
                    yield issue("modules.md", line, "V16", f"模块「{module or '(空)'}」决策回指悬空或重名：{ref}")
                elif definitions[0][1] != clean_cell(module):
                    yield issue("modules.md", line, "V16", f"模块「{module or '(空)'}」引用的结构型 {ref} 未回指本模块")
            elif len(decision_definitions.get(ref, [])) != 1:
                yield issue("modules.md", line, "V16", f"模块「{module or '(空)'}」决策回指悬空或重名：{ref}")
        if not refs:
            yield issue("modules.md", line, "V16", f"模块「{module or '(空)'}」未回指 Requirement")
        for ref in refs:
            if requirement_counts.get(ref, 0) != 1:
                yield issue("modules.md", line, "V16", f"模块「{module or '(空)'}」回指的 Requirement 不存在或不唯一：{ref}")
            else:
                covered.add(ref)
    for name in sorted(set(requirements) - covered):
        yield issue("modules.md", 0, "V16", f"Requirement 未被任何模块承接：{name}")


def check_spec2_reasoning(pkg: Path, ptype: str):
    if ptype != "spec2" or not (pkg / "spec.md").exists() or not (pkg / "modules.md").exists():
        return

    spec_text = read_text(pkg / "spec.md")
    modules_text = read_text(pkg / "modules.md")
    design = pkg / "design.md"
    if design.exists():
        for line, value in lines_outside_fences(read_text(design)):
            if value.lstrip().startswith("|") and any("D-ID" in cell for cell in cells(value)):
                yield issue("design.md", line, "V18", "design.md 不得定义 D-ID；唯一真源是 modules.md「关键决策」")
    judgment_header, judgment_rows = table_in_h2(spec_text, "判断依据")
    judgment_definitions: dict[str, list[int]] = {}
    if not judgment_header:
        yield issue("spec.md", 0, "V18", "spec.md 缺少「判断依据」表")
    else:
        judgment_columns = {
            "id": next((i for i, name in enumerate(judgment_header) if "J-ID" in name), None),
            "judgment": next((i for i, name in enumerate(judgment_header) if "判断" in name and "J-ID" not in name), None),
            "source": next((i for i, name in enumerate(judgment_header) if "来源" in name), None),
            "evidence": next((i for i, name in enumerate(judgment_header) if "证据" in name or "推断说明" in name), None),
            "status": next((i for i, name in enumerate(judgment_header) if "确认状态" in name), None),
        }
        if any(index is None for index in judgment_columns.values()):
            yield issue("spec.md", 0, "V18", "判断依据表必须含「J-ID」「判断」「来源类型」「证据或推断说明」「确认状态」列")
        else:
            for line, row in judgment_rows:
                values = {
                    name: clean_cell(row[index]) if index < len(row) else ""
                    for name, index in judgment_columns.items()
                }
                judgment_id = values["id"]
                if not re.fullmatch(r"J\d+", judgment_id):
                    yield issue("spec.md", line, "V18", f"J-ID 非法：{judgment_id or '(空)'}")
                else:
                    judgment_definitions.setdefault(judgment_id, []).append(line)
                missing = [name for name in ("judgment", "source", "evidence", "status") if not values[name]]
                if missing:
                    yield issue("spec.md", line, "V18", f"判断依据 {judgment_id or '(空)'} 缺少必需字段：{', '.join(missing)}")

    decision_header, decision_rows = table_in_h2(modules_text, "关键决策")
    decision_definitions: dict[str, list[int]] = {}
    if decision_header:
        decision_columns = {
            "id": next((i for i, name in enumerate(decision_header) if "D-ID" in name), None),
            "decision": next((i for i, name in enumerate(decision_header) if "决策" in name and "D-ID" not in name), None),
            "basis": next((i for i, name in enumerate(decision_header) if "依据" in name), None),
            "rationale": next((i for i, name in enumerate(decision_header) if "选择理由" in name), None),
            "alternative": next((i for i, name in enumerate(decision_header) if "备选" in name and "否决" in name), None),
            "revisit": next((i for i, name in enumerate(decision_header) if "重评" in name), None),
        }
        if any(index is None for index in decision_columns.values()):
            yield issue("modules.md", 0, "V18", "关键决策表必须含「D-ID」「决策」「依据 U/J」「选择理由」「备选与否决原因」「重评条件」列")
        else:
            for line, row in decision_rows:
                values = {
                    name: clean_cell(row[index]) if index < len(row) else ""
                    for name, index in decision_columns.items()
                }
                decision_id = values["id"]
                if not re.fullmatch(r"D\d+", decision_id):
                    yield issue("modules.md", line, "V18", f"D-ID 非法：{decision_id or '(空)'}")
                else:
                    decision_definitions.setdefault(decision_id, []).append(line)
                missing = [name for name in ("decision", "basis", "rationale", "alternative", "revisit") if not values[name]]
                if missing:
                    yield issue("modules.md", line, "V18", f"关键决策 {decision_id or '(空)'} 缺少必需字段：{', '.join(missing)}")
                if not spec2_id_refs(values["basis"], "UJ"):
                    yield issue("modules.md", line, "V18", f"D 依据缺少 U/J 引用：{decision_id or '(空)'}")

    for judgment_id, lines in judgment_definitions.items():
        if len(lines) > 1:
            yield issue("spec.md", lines[1], "V18", f"J-ID 重名：{judgment_id}")
    for decision_id, lines in decision_definitions.items():
        if len(lines) > 1:
            yield issue("modules.md", lines[1], "V18", f"D-ID 重名：{decision_id}")

    user_definitions = spec2_user_definitions(pkg)
    defined = {
        "U": set(user_definitions),
        "J": set(judgment_definitions),
        "D": set(decision_definitions),
    }
    reference_counts: dict[str, int] = {}
    for path in (pkg / "spec.md", pkg / "modules.md", pkg / "design.md"):
        if not path.exists():
            continue
        for _line, value in lines_outside_fences(read_text(path)):
            for token in spec2_id_refs(value):
                reference_counts[token] = reference_counts.get(token, 0) + 1
    for token, count in sorted(reference_counts.items()):
        if token not in defined[token[0]]:
            yield issue("(package)", 0, "V18", f"U/J/D 引用悬空：{token}")
    for judgment_id, lines in sorted(judgment_definitions.items()):
        if len(lines) == 1 and reference_counts.get(judgment_id, 0) <= 1:
            yield issue("spec.md", lines[0], "V18", f"孤儿 J：{judgment_id}")
    for decision_id, lines in sorted(decision_definitions.items()):
        if len(lines) == 1 and reference_counts.get(decision_id, 0) <= 1:
            yield issue("modules.md", lines[0], "V18", f"孤儿 D：{decision_id}")


def check_spec2_design(pkg: Path, ptype: str):
    if ptype != "spec2":
        return
    design = pkg / "design.md"
    _header, rows = spec2_model_rows(pkg)
    design_referenced = False
    for _line, row in rows:
        for value in row:
            parsed = parse_package_location(value)
            if parsed and parsed[0].removeprefix("./") == "design.md":
                design_referenced = True
    if design_referenced and not design.exists():
        yield issue("design.md", 0, "V17", "建模覆盖声明引用 design.md，但文件不存在")
    if design.exists() and (not read_text(design).strip() or not design_referenced):
        yield issue("design.md", 0, "V17", "design.md 仅在动态模型有建模覆盖落点时生成")


def check_task_files_complete(pkg: Path, ptype: str):
    for name in ("README.md", "dev-checklist.md"):
        if not (pkg / name).exists():
            yield issue("(package)", 0, "V8", f"task 包缺少必需文件：{name}")


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
        yield issue("dev-checklist.md", 0, "V9", f"checklist 表头必须为「{expected}」，实际为「{actual}」")
        return
    try:
        parse_checklist(pkg)
    except (FileNotFoundError, ValueError) as exc:
        yield issue("dev-checklist.md", 0, "V9", f"checklist 无法解析：{exc}")
        return

    known_ids: set[str] = set()
    parsed_rows: list[tuple[int, list[str], str]] = []
    for line, row in rows:
        raw_id = row[0].strip() if row else ""
        match = ID_COL_RE.fullmatch(raw_id)
        if not match:
            yield issue("dev-checklist.md", line, "V9", f"非法 task ID：{raw_id or '(空)'}")
            continue
        task_id = f"T{match.group(1)}"
        known_ids.add(task_id)
        parsed_rows.append((line, row, task_id))

    for line, row, _task_id in parsed_rows:
        status = row[4].strip() if len(row) > 4 else ""
        if not is_supported_task_status(status):
            yield issue("dev-checklist.md", line, "V9", f"非法状态：{status or '(空)'}")
        dependencies = parse_deps(row[3] if len(row) > 3 else "")
        for dependency in dependencies:
            if dependency not in known_ids:
                yield issue("dev-checklist.md", line, "V9", f"依赖「{dependency}」不在 task 表中")


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
        yield issue("diagram.md", 0, "V10", f"README 模块「{declared[name]}」缺少 Mermaid 节点")
    for name in sorted(rendered.keys() - declared.keys()):
        yield issue("diagram.md", 0, "V10", f"Mermaid 节点「{rendered[name]}」未在 README 涉及模块声明")


LITE_README_H2_REQUIREMENTS = ("核心目标", "验收")
FULL_README_H2_REQUIREMENTS = (
    "核心目标", "需求要点", "涉及模块", "架构拆分策略", "技术设计", "验收",
)
RISK_VALUES = {"Q0", "Q1", "Q2", "Q3"}


def h2_section(lines: list[str], prefix: str) -> tuple[int | None, int]:
    return section_bounds(lines, prefix)


def check_task_readme(pkg: Path, ptype: str):
    readme = pkg / "README.md"
    if not readme.exists():
        return
    lines = read_text(readme).splitlines()
    risk_entries = [(line_number, match.group(1).upper()) for line_number, line in enumerate(lines, 1)
                    if (match := RISK_RE.match(line.strip()))]
    risk = None
    if not risk_entries:
        yield issue("README.md", 0, "V11", "README 缺少 risk: Q0|Q1|Q2|Q3 字段")
    elif len(risk_entries) > 1:
        yield issue("README.md", risk_entries[1][0], "V11", "README 的 risk 字段必须唯一")
    else:
        risk = risk_entries[0][1]
        if risk not in RISK_VALUES:
            yield issue("README.md", risk_entries[0][0], "V11", f"非法 risk：{risk}（应为 Q0/Q1/Q2/Q3）")

    h2s = [(line_number, line[3:].strip()) for line_number, line in enumerate(lines, 1) if H2_RE.match(line)]
    required = LITE_README_H2_REQUIREMENTS if risk in {"Q0", "Q1"} else FULL_README_H2_REQUIREMENTS
    for heading in required:
        if not any(actual.startswith(heading) for _line, actual in h2s):
            yield issue("README.md", 0, "V11", f"缺少以「{heading}」开头的二级标题")

    acceptance_start, acceptance_end = h2_section(lines, "验收")
    if acceptance_start is None:
        return
    acceptance_lines = lines[acceptance_start:acceptance_end]
    if not any(H3_RE.match(line) and line[4:].strip().startswith("自动化测试责任") for line in acceptance_lines):
        yield issue("README.md", acceptance_start + 1, "V11", "验收区域缺少三级标题「自动化测试责任」")


def check_task_acceptance(pkg: Path, ptype: str):
    """V12：校验验收 Requirement/Scenario、WHEN/THEN 与验证标记。"""
    readme = pkg / "README.md"
    if not readme.exists():
        return
    lines = read_text(readme).splitlines()
    start, end = h2_section(lines, "验收")
    if start is None:
        return
    section = [(index + 1, lines[index]) for index in range(start + 1, end)]
    yield from scenario_contract_issues(section, "README.md", "task")


CHECKS = [
    check_files_complete,   # V1
    check_link_rules,       # V2
    check_req_scenario,     # V3
    check_delta_markers,    # V4
    check_task_backrefs,    # V5
    check_module_consistency,  # V6
    check_status_vocab,     # V7
    check_spec2_modeling,   # V14
    check_spec2_requirement_names,  # V15
    check_spec2_user_trace,  # V15
    check_spec2_modules,    # V16
    check_spec2_design,     # V17
    check_spec2_reasoning,  # V18
]

TASK_CHECKS = [
    check_link_rules,       # V2
    check_task_files_complete,  # V8
    check_task_checklist,   # V9
    check_task_diagram,     # V10
    check_task_readme,      # V11
    check_task_acceptance,  # V12
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

# flag 契约：CLI task 只接受规范 T#；ledger 只从代码所有的行首读取 issue 编号。
FLAG_TASK_RE = re.compile(r"T[1-9][0-9]*")
ISSUE_LINE_RE = re.compile(r"^- issue-([0-9]+) \|", re.MULTILINE)
REPORT_NAME_RE = re.compile(
    r"^qa-gate-report-(?P<timestamp>[0-9]{8}-[0-9]{6})(?:-(?P<suffix>[0-9]+))?\.md$"
)
FLAG_MARKER_NAME = ".flag-transaction.json"
FLAG_MARKER_VERSION = 1


class FlagError(ValueError):
    """flag 可操作错误；CLI 统一映射为退出码 2。"""


def normalize_flag_inputs(
    task_arg: str, severity: str, loc: str, msg: str
) -> tuple[list[str], str, str, str]:
    """校验并归一化 flag 参数，不接触文件系统。"""
    raw_tasks = task_arg.split(",")
    task_ids = [item.strip() for item in raw_tasks]
    if not task_ids or any(not item for item in task_ids):
        raise FlagError("--task 含空项")
    invalid = [item for item in task_ids if FLAG_TASK_RE.fullmatch(item) is None]
    if invalid:
        raise FlagError(f"--task 仅接受 T1、T2 形式：{', '.join(invalid)}")
    duplicates = sorted({item for item in task_ids if task_ids.count(item) > 1})
    if duplicates:
        raise FlagError(f"--task 含重复项：{', '.join(duplicates)}")

    severity = severity.strip().upper()
    if severity not in {"P0", "P1", "P2"}:
        raise FlagError("--severity 仅接受 P0、P1、P2")

    loc = loc.strip()
    if not loc or "|" in loc or "\r" in loc or "\n" in loc:
        raise FlagError("--loc 必须是单行 path:正整数，且不能包含竖线")
    path_part, separator, line_part = loc.rpartition(":")
    if not separator or not path_part or re.fullmatch(r"[1-9][0-9]*", line_part) is None:
        raise FlagError("--loc 必须是 path:正整数")

    msg = msg.replace("\r\n", " ").replace("\r", " ").replace("\n", " ").strip()
    if not msg:
        raise FlagError("--msg 归一化后不能为空")
    if not all(char.isprintable() for char in msg):
        raise FlagError("--msg 只能包含可打印字符")
    return task_ids, severity, loc, msg


def _checklist_layout(checklist_text: str) -> tuple[list[str], int, int, int]:
    """返回保留换行的行、首个表数据起点、ID 列和状态列。"""
    lines = checklist_text.splitlines(keepends=True)
    for index in range(len(lines) - 1):
        if not lines[index].lstrip().startswith("|"):
            continue
        if TABLE_SEP_RE.match(lines[index + 1].rstrip("\r\n")) is None:
            continue
        header = cells(lines[index])

        def col_idx(*keywords: str) -> int | None:
            for keyword in keywords:
                for cell_index, value in enumerate(header):
                    if keyword in value:
                        return cell_index
            return None

        id_idx = col_idx("#", "编号")
        status_idx = col_idx("状态")
        if id_idx is None or status_idx is None:
            raise FlagError("dev-checklist.md 表头缺少 #/编号 或状态列")
        return lines, index + 2, id_idx, status_idx
    raise FlagError("dev-checklist.md 无可解析表格")


def _target_checklist_rows(
    checklist_text: str, task_ids: list[str]
) -> tuple[list[str], int, dict[str, int]]:
    """定位目标 task 的唯一表格行；重复或缺失都作为调用错误。"""
    lines, row_start, id_idx, status_idx = _checklist_layout(checklist_text)
    found: dict[str, list[int]] = {task_id: [] for task_id in task_ids}
    for line_index in range(row_start, len(lines)):
        if not lines[line_index].lstrip().startswith("|"):
            break
        row_cells = cells(lines[line_index])
        if id_idx >= len(row_cells):
            continue
        raw_id = re.sub(r"[`*]", "", row_cells[id_idx]).strip()
        match = ID_COL_RE.fullmatch(raw_id)
        if match is None:
            continue
        task_id = f"T{match.group(1)}"
        if task_id in found:
            found[task_id].append(line_index)

    missing = [task_id for task_id, indexes in found.items() if not indexes]
    duplicate = [task_id for task_id, indexes in found.items() if len(indexes) > 1]
    if missing:
        raise FlagError(f"checklist 缺少目标 task：{', '.join(missing)}")
    if duplicate:
        raise FlagError(f"checklist 目标 task 重复：{', '.join(duplicate)}")
    return lines, status_idx, {task_id: indexes[0] for task_id, indexes in found.items()}


def downgrade_task_rows(checklist_text: str, task_ids: list[str]) -> tuple[str, list[str]]:
    """把目标 task 状态单元格降为 `[!] 🔴`，保持行内其他内容与已 blocked 状态。"""
    lines, status_idx, target_rows = _target_checklist_rows(checklist_text, task_ids)
    downgraded: list[str] = []
    for task_id in task_ids:
        line_index = target_rows[task_id]
        raw_line = lines[line_index]
        newline = ""
        if raw_line.endswith("\r\n"):
            raw_line, newline = raw_line[:-2], "\r\n"
        elif raw_line.endswith(("\n", "\r")):
            raw_line, newline = raw_line[:-1], raw_line[-1]
        parts = raw_line.split("|")
        segment_index = status_idx + 1  # 表格行以 | 开头，首段为空
        if segment_index >= len(parts) - 1:
            raise FlagError(f"checklist 的 {task_id} 状态单元格缺失")
        old_segment = parts[segment_index]
        old_status = old_segment.strip()
        if task_engine_status(old_status) == BLOCKED:
            continue
        spacing = re.fullmatch(r"(\s*).*?(\s*)", old_segment)
        leading = spacing.group(1) if spacing else " "
        trailing = spacing.group(2) if spacing else " "
        parts[segment_index] = f"{leading}[!] 🔴{trailing}"
        lines[line_index] = "|".join(parts) + newline
        downgraded.append(task_id)
    return "".join(lines), downgraded


def next_issue_id(report_text: str) -> str:
    """只扫描代码所有的 issue 行首，返回本轮下一个 issue ID。"""
    numbers = [int(match.group(1)) for match in ISSUE_LINE_RE.finditer(report_text)]
    return f"issue-{max(numbers, default=0) + 1}"


def render_issue_report(report_path: Path) -> str:
    """创建新轮 issue ledger 的固定骨架。"""
    return (
        f"# QA Gate Issue Ledger — {report_path.stem}\n\n"
        "> 由 `tools/xdev.py flag` 生成和维护；issue 行归代码所有；本轮首条由代码分配为 `issue-1`。\n\n"
        "## Issues\n"
    )


def append_issue_line(report_text: str, issue: dict) -> str:
    """issue ledger 行的唯一格式化点。"""
    prefix = report_text if report_text.endswith("\n") else report_text + "\n"
    task_text = ",".join(issue["tasks"])
    return (
        f"{prefix}- {issue['issue']} | {issue['severity']} | {task_text} | "
        f"{issue['loc']} | {issue['msg']}\n"
    )


def _report_sort_key(path: Path) -> tuple[str, int]:
    match = REPORT_NAME_RE.fullmatch(path.name)
    if match is None:
        raise FlagError(f"非法 QA Gate report 文件名：{path.name}")
    suffix = int(match.group("suffix") or 0)
    return match.group("timestamp"), suffix


def resolve_current_report(
    reports_dir: Path, new_round: bool, now: datetime | None = None
) -> tuple[Path, str, str | None]:
    """选择本轮 ledger；只返回目标和内容，不在事务外创建业务文件。"""
    candidates = []
    if reports_dir.exists():
        candidates = [
            path for path in reports_dir.iterdir()
            if path.is_file() and REPORT_NAME_RE.fullmatch(path.name)
        ]
    if new_round or not candidates:
        timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
        base = reports_dir / f"qa-gate-report-{timestamp}.md"
        if not base.exists():
            return base, render_issue_report(base), None
        suffix = 1
        while True:
            candidate = reports_dir / f"qa-gate-report-{timestamp}-{suffix:02d}.md"
            if not candidate.exists():
                return candidate, render_issue_report(candidate), None
            suffix += 1
    report_path = max(candidates, key=_report_sort_key)
    try:
        report_bytes = report_path.read_bytes()
        return report_path, report_bytes.decode("utf-8"), _sha256_bytes(report_bytes)
    except (OSError, UnicodeError) as exc:
        raise FlagError(f"读取 QA Gate ledger 失败：{exc}") from exc


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_durable_temp(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _relative_transaction_path(task_dir: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(task_dir.resolve()))
    except ValueError as exc:
        raise FlagError(f"事务路径越出 task 目录：{path}") from exc


def _resolve_transaction_path(task_dir: Path, raw: object) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
        raise FlagError(f"事务标记包含非法相对路径：{raw!r}")
    path = (task_dir / raw).resolve()
    try:
        path.relative_to(task_dir.resolve())
    except ValueError as exc:
        raise FlagError(f"事务标记路径越出 task 目录：{raw}") from exc
    return path


def _flag_result(result: object, recovered: bool) -> dict:
    if not isinstance(result, dict):
        raise FlagError("事务标记缺少 result")
    required = ("issue", "downgraded", "report", "recovered")
    if set(result) != set(required):
        raise FlagError("事务标记 result 字段不完整")
    if not isinstance(result["issue"], str) or not isinstance(result["downgraded"], list):
        raise FlagError("事务标记 result 类型非法")
    if not isinstance(result["report"], str):
        raise FlagError("事务标记 report 类型非法")
    return {
        "issue": result["issue"],
        "downgraded": result["downgraded"],
        "report": result["report"],
        "recovered": recovered,
    }


def recover_flag_transaction(task_dir: Path) -> dict | None:
    """幂等前滚 pending flag 事务；成功后返回原 issue 结果。"""
    marker_path = task_dir / "reports" / "qa-gate" / FLAG_MARKER_NAME
    if not marker_path.exists():
        return None
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FlagError(f"读取事务标记失败，marker 已保留：{exc}") from exc
    if marker.get("version") != FLAG_MARKER_VERSION:
        raise FlagError(f"不支持的事务标记版本：{marker.get('version')!r}")
    targets = marker.get("targets")
    if not isinstance(targets, list) or len(targets) != 2:
        raise FlagError("事务标记必须包含两个目标")

    for entry in targets:
        if not isinstance(entry, dict):
            raise FlagError("事务标记 target 结构非法")
        target = _resolve_transaction_path(task_dir, entry.get("target"))
        temp = _resolve_transaction_path(task_dir, entry.get("temp"))
        expected = entry.get("sha256")
        before = entry.get("before_sha256")
        if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
            raise FlagError(f"事务标记目标哈希非法：{target}")
        if before is not None and (
            not isinstance(before, str) or re.fullmatch(r"[0-9a-f]{64}", before) is None
        ):
            raise FlagError(f"事务标记旧目标哈希非法：{target}")
        try:
            current = _sha256_file(target)
            if current == expected:
                continue
            if current != before:
                raise FlagError(
                    f"事务目标已被其他写入修改：{target}；当前 {current}，事务读取时 {before}"
                )
            if not temp.exists():
                raise FlagError(
                    f"事务恢复材料缺失：{temp}；目标 {target} 期望 SHA-256 {expected}"
                )
            try:
                os.replace(temp, target)
            except FileNotFoundError:
                if _sha256_file(target) != expected:
                    raise
            _fsync_directory(target.parent)
            if _sha256_file(target) != expected:
                raise FlagError(f"事务恢复后哈希不匹配：{target}；期望 {expected}")
        except OSError as exc:
            raise FlagError(f"事务恢复失败，marker 已保留：{exc}") from exc

    marker_temp_raw = marker.get("marker_temp")
    try:
        if marker_temp_raw:
            marker_temp = _resolve_transaction_path(task_dir, marker_temp_raw)
            marker_temp.unlink(missing_ok=True)
        marker_path.unlink()
        _fsync_directory(marker_path.parent)
    except OSError as exc:
        raise FlagError(f"事务目标已完成，但 marker 清理失败：{exc}") from exc
    return _flag_result(marker.get("result"), recovered=True)


def commit_flag_transaction(
    task_dir: Path,
    checklist_path: Path,
    checklist_text: str,
    report_path: Path,
    report_text: str,
    result: dict,
    checklist_before_sha256: str,
    report_before_sha256: str | None,
) -> dict:
    """完整发布 marker 后提交两个目标；竞争者转入既有事务恢复。"""
    transaction_id = uuid.uuid4().hex
    reports_dir = task_dir / "reports" / "qa-gate"
    reports_dir.mkdir(parents=True, exist_ok=True)
    checklist_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    target_contents = [
        (checklist_path, checklist_text.encode("utf-8"), checklist_before_sha256),
        (report_path, report_text.encode("utf-8"), report_before_sha256),
    ]
    prepared: list[Path] = []
    targets: list[dict] = []
    marker_temp = reports_dir / f".{FLAG_MARKER_NAME}.{transaction_id}.tmp"
    marker_path = reports_dir / FLAG_MARKER_NAME
    marker_published = False
    try:
        for target, content, before_sha256 in target_contents:
            temp = target.parent / f".{target.name}.flag-{transaction_id}.tmp"
            _write_durable_temp(temp, content)
            prepared.append(temp)
            targets.append({
                "target": _relative_transaction_path(task_dir, target),
                "temp": _relative_transaction_path(task_dir, temp),
                "sha256": _sha256_bytes(content),
                "before_sha256": before_sha256,
            })
        marker = {
            "version": FLAG_MARKER_VERSION,
            "transaction": transaction_id,
            "marker_temp": _relative_transaction_path(task_dir, marker_temp),
            "targets": targets,
            "result": result,
        }
        marker_bytes = json.dumps(marker, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        _write_durable_temp(marker_temp, marker_bytes)
        prepared.append(marker_temp)
        try:
            os.link(marker_temp, marker_path)
            marker_published = True
        except FileExistsError:
            for path in prepared:
                path.unlink(missing_ok=True)
            recovered = recover_flag_transaction(task_dir)
            if recovered is None:
                raise FlagError("事务标记竞争后消失，请重试 flag")
            return recovered
        marker_temp.unlink()
        _fsync_directory(reports_dir)

        stale_targets = []
        for entry in targets:
            target = _resolve_transaction_path(task_dir, entry["target"])
            current = _sha256_file(target)
            if current not in {entry["before_sha256"], entry["sha256"]}:
                stale_targets.append(str(target))
        if stale_targets:
            marker_path.unlink(missing_ok=True)
            _fsync_directory(reports_dir)
            marker_published = False
            raise FlagError(
                "事务读取后目标发生变化，请重试 flag：" + ", ".join(stale_targets)
            )

        for entry in targets:
            target = _resolve_transaction_path(task_dir, entry["target"])
            temp = _resolve_transaction_path(task_dir, entry["temp"])
            if _sha256_file(target) == entry["sha256"]:
                continue
            try:
                os.replace(temp, target)
            except FileNotFoundError:
                if _sha256_file(target) != entry["sha256"]:
                    raise
            _fsync_directory(target.parent)
            if _sha256_file(target) != entry["sha256"]:
                raise FlagError(f"事务提交后哈希不匹配：{target}")
        marker_path.unlink(missing_ok=True)
        _fsync_directory(reports_dir)
        return _flag_result(result, recovered=False)
    except FlagError:
        if not marker_published:
            for path in prepared:
                path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        if not marker_published:
            for path in prepared:
                path.unlink(missing_ok=True)
        state = "marker 已保留，可由下次 flag 恢复" if marker_published else "业务文件未提交"
        raise FlagError(f"flag 事务 IO 失败（{state}）：{exc}") from exc


def _emit_flag_result(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return
    verb = "已恢复" if result["recovered"] else "已登记"
    downgraded = ",".join(result["downgraded"]) or "无"
    print(f"{verb} {result['issue']} → {result['report']}；降级：{downgraded}")


def flag_command(
    task_dir: Path,
    task_arg: str,
    severity: str,
    loc: str,
    msg: str,
    new_round: bool,
    as_json: bool,
) -> int:
    """flag 子命令：恢复 → 校验 → 生成 → 双目标事务提交。"""
    try:
        recovered = recover_flag_transaction(task_dir)
        if recovered is not None:
            _emit_flag_result(recovered, as_json)
            return 0
        if not task_dir.is_dir():
            raise FlagError(f"不是 task 目录：{task_dir}")
        task_ids, severity, loc, msg = normalize_flag_inputs(task_arg, severity, loc, msg)
        checklist_path = task_dir / "dev-checklist.md"
        try:
            checklist_text = checklist_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise FlagError(f"读取 dev-checklist.md 失败：{exc}") from exc

        # P2 也先定位并验证目标唯一性；登记的每个 T# 都必须是现存 task。
        _target_checklist_rows(checklist_text, task_ids)
        if severity in {"P0", "P1"}:
            new_checklist, downgraded = downgrade_task_rows(checklist_text, task_ids)
        else:
            new_checklist, downgraded = checklist_text, []

        report_path, report_text, report_before_sha256 = resolve_current_report(
            task_dir / "reports" / "qa-gate", new_round
        )
        issue_id = next_issue_id(report_text)
        issue = {
            "issue": issue_id,
            "tasks": task_ids,
            "severity": severity,
            "loc": loc,
            "msg": msg,
        }
        new_report = append_issue_line(report_text, issue)
        result = {
            "issue": issue_id,
            "downgraded": downgraded,
            "report": report_path.name,
            "recovered": False,
        }
        committed = commit_flag_transaction(
            task_dir,
            checklist_path,
            new_checklist,
            report_path,
            new_report,
            result,
            _sha256_bytes(checklist_text.encode("utf-8")),
            report_before_sha256,
        )
        _emit_flag_result(committed, as_json)
        return 0
    except (FlagError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


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

    返回 (tasks, product_issues)。每个 task 追加 'status' 和 'product_check' 字段。
    product_check：done 但文件缺失→"missing"；todo 但文件已存在→"stale"；无锚点→None。
    这是可选交叉验证，不改变 status 本身（主判依据是 token）。
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
    """统计进度：total/done/todo/blocked。"""
    total = len(tasks)
    done = sum(1 for t in tasks if t["status"] == DONE)
    blocked = sum(1 for t in tasks if t["status"] == BLOCKED)
    todo = total - done - blocked
    return {"total": total, "done": done, "todo": todo, "blocked": blocked}


def status_command(task_dir: Path, as_json: bool) -> int:
    """status 子命令：解析 task 的 dev-checklist，输出任务状态 + 进度。"""
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


# ---------- verify：dev-report 证据执行与场景对账 ----------

VERIFY_KEYS = {
    "id", "scenario", "cmd", "cwd", "expect_exit", "expect_contains", "timeout", "mode", "steps",
}


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


def acceptance_scenarios(readme: Path) -> list[dict]:
    """读取验收节 Scenario 名和验证标记，供覆盖对账使用。"""
    if not readme.exists():
        raise FileNotFoundError(f"缺少 README.md：{readme.parent}")
    lines = read_text(readme).splitlines()
    start, end = h2_section(lines, "验收")
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
        # 未定义截断阈值时保留完整合并输出，避免把新数值常量引入协议。
        "output_tail": output,
        "pass": not failed,
    }


def verify_command(task_dir: Path, as_json: bool, only: str | None) -> int:
    try:
        if not task_dir.is_dir():
            raise FileNotFoundError(f"不是目录：{task_dir}")
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
            item["name"] for item in acceptance_scenarios(task_dir / "README.md")
            if item["mode"] == "auto" and item["name"].strip() not in declared_auto
        ]
        payload = {
            "task": task_dir.name,
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
    result = {"path": str(pkg), "type": ptype, "skipped": False, "issues": []}
    if ptype == "legacy" and not include_legacy:
        result["skipped"] = True
        return result
    if ptype == "unknown":
        result["issues"].append(
            issue("(package)", 0, "V0", "无法识别包类型（既无 proposal.md / 01-goals / spec.md，也非 legacy）")
        )
        return result
    checks = TASK_CHECKS if ptype == "task" else CHECKS
    for check in checks:
        if ptype == "legacy" and check is check_files_complete:
            continue  # legacy 不按新档位查齐全
        try:
            result["issues"].extend(check(pkg, ptype))
        except Exception as e:  # 单条规则崩溃不拖垮整体
            result["issues"].append(issue("(package)", 0, "V0", f"{check.__name__} 执行失败：{e}"))
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

    verify = sub.add_parser("verify", help="复跑 dev-report verify 块并对账 README 自动场景")
    verify.add_argument("task_dir", help="task 目录（含 README.md 与 dev-report*.md）")
    verify.add_argument("--json", action="store_true", dest="as_json", help="机器可读输出")
    verify.add_argument("--only", help="只执行指定的 auto verify 块")

    flag = sub.add_parser("flag", help="登记 QA Gate issue，并对 P0/P1 task 执行只降级更新")
    flag.add_argument("task_dir", help="task 目录（内含 dev-checklist.md）")
    flag.add_argument("--task", required=True, dest="task_ids", help="逗号分隔的 T# 列表，如 T2,T3")
    flag.add_argument("--severity", required=True, choices=["P0", "P1", "P2"], help="P0、P1 或 P2")
    flag.add_argument("--loc", required=True, help="问题位置：path:正整数行号")
    flag.add_argument("--msg", required=True, help="问题描述")
    flag.add_argument("--new-round", action="store_true", help="创建新的 QA Gate ledger 轮次")
    flag.add_argument("--json", action="store_true", dest="as_json", help="机器可读输出")

    args = parser.parse_args(argv)

    if args.cmd == "instructions":
        return instructions_command(args.artifact_id, Path(args.task_dir), args.as_json)

    if args.cmd == "scaffold":
        return req.scaffold(Path(args.task_dir), args.with_diagram, args.as_json)

    if args.cmd == "verify":
        return verify_command(Path(args.task_dir), args.as_json, args.only)

    if args.cmd == "flag":
        return flag_command(
            Path(args.task_dir),
            args.task_ids,
            args.severity,
            args.loc,
            args.msg,
            args.new_round,
            args.as_json,
        )

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
    total = sum(len(r["issues"]) for r in results)
    skipped = sum(1 for r in results if r["skipped"])

    if args.as_json:
        print(json.dumps({"packages": results, "total_issues": total, "skipped_legacy": skipped}, ensure_ascii=False, indent=2))
    else:
        for r in results:
            tag = f"[{r['type']}]"
            if r["skipped"]:
                print(f"== {r['path']}  {tag}  跳过（legacy；--include-legacy 可纳入）")
                continue
            print(f"== {r['path']}  {tag}")
            if not r["issues"]:
                print("   ok")
            for fd in r["issues"]:
                loc = f"{fd['file']}:{fd['line']}" if fd["line"] else fd["file"]
                print(f"   {loc}  {fd['rule']}  {fd['msg']}")
        mark = "✓" if total == 0 else "✗"
        print(f"{mark} validate：{len(results)} 包，{total} issue(s)，{skipped} legacy 跳过")

    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
