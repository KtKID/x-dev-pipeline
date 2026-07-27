#!/usr/bin/env python3
"""spec/spec7/change/capability 包的确定性校验引擎。

本模块拥有包类型识别、Markdown 机械解析、V1-V7 与 V13-V20 规则聚合。
当前 task 校验由 req.py 拥有，统一 CLI 位于 xdev.py。
"""

from __future__ import annotations

import re
from pathlib import Path

import req
import spec as spec_engine


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
DEPRECATED_SPEC2_MARKER_RE = re.compile(
    r"^>\s*spec_version:\s*2\s*$",
    re.IGNORECASE,
)



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


SCENARIO_PROFILES = {
    "legacy": {"given": True, "rule": "V3"},
}


def scenario_contract_issues(lines: list[tuple[int, str]], rel: str, profile: str):
    """校验 legacy 包的 Requirement/Scenario。"""
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
            if req_line is not None:
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




def detect_type(pkg: Path) -> str:
    if spec_engine.looks_like_spec(pkg):
        return "spec"
    spec_md = pkg / "spec.md"
    if spec_md.is_file() and any(
        DEPRECATED_SPEC2_MARKER_RE.match(line)
        for _number, line in lines_outside_fences(read_text(spec_md))
    ):
        return "unsupported-spec2"
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
            for m in LINK_RE.finditer(line):
                target = m.group(1).strip()
                if target.startswith("<") and target.endswith(">"):
                    target = target[1:-1].strip()
                if target.startswith(("http://", "https://", "mailto:", "#")):
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
    if ptype == "spec":
        return
    for f in md_files(pkg):
        if not f.exists():
            continue
        rel = str(f.relative_to(pkg))
        lines = list(lines_outside_fences(read_text(f)))
        if ptype == "change":
            active_lines: list[tuple[int, str]] = []
            in_removed = False
            for line_number, value in lines:
                if H2_RE.match(value):
                    delta = DELTA_HEAD_RE.match(value)
                    in_removed = bool(delta and delta.group(1) == "REMOVED")
                    if in_removed:
                        continue
                if not in_removed:
                    active_lines.append((line_number, value))
            lines = active_lines
        yield from scenario_contract_issues(
            lines, rel, "legacy",
        )


def check_spec_contract(pkg: Path, ptype: str):
    if ptype != "spec":
        return
    yield from spec_engine.validate_issues(pkg)


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


CHECKS = [
    check_files_complete,
    check_link_rules,
    check_req_scenario,
    check_spec_contract,
    check_delta_markers,
    check_task_backrefs,
    check_module_consistency,
    check_status_vocab,
]


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
    if ptype == "unsupported-spec2":
        result["issues"].append(
            issue("spec.md", 0, "V0", "spec_version: 2 已废除；请迁移为 spec_version: 3")
        )
        return result
    for check in CHECKS:
        if ptype == "legacy" and check is check_files_complete:
            continue  # legacy 不按新档位查齐全
        try:
            result["issues"].extend(check(pkg, ptype))
        except Exception as e:  # 单条规则崩溃不拖垮整体
            result["issues"].append(issue("(package)", 0, "V0", f"{check.__name__} 执行失败：{e}"))
    if ptype == "spec" and (pkg / "tasks").is_dir():
        try:
            result["issues"].extend(req.spec_scenario_coverage(pkg))
        except Exception as e:
            result["issues"].append(issue("(package)", 0, "V0", f"spec_scenario_coverage 执行失败：{e}"))
    return result
