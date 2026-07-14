#!/usr/bin/env python3
"""xdev — x-dev-pipeline 的确定性工具层（立法层）。

Phase 1 只有 validate：对 spec 包 / change 包做结构校验（机械项），
把散落在 SKILL.md 散文里的格式法律搬进代码。skills 管判断，本工具管机械。

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

用法：
  python3 tools/xdev.py validate [包目录 ...] [--include-legacy] [--json]
  不给目录时，从当前工作目录发现 docs/spec/*/、docs/changes/*/、docs/specs/*/。
  legacy 包（含 diagrams.md / *.html 图集的旧结构）默认跳过，--include-legacy 纳入
  （纳入时不查 V1 档位齐全，只查其余规则）。

退出码：0 全部通过；1 存在 finding；2 用法或 IO 错误。
Phase 2 计划：archive（delta 合并回 specs/ + 移档）、status（进度矩阵 + run-log 退场判据检查）。
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


# ---------- 包类型识别 ----------

def detect_type(pkg: Path) -> str:
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


CHECKS = [
    check_files_complete,   # V1
    check_link_rules,       # V2
    check_req_scenario,     # V3
    check_delta_markers,    # V4
    check_task_backrefs,    # V5
    check_module_consistency,  # V6
    check_status_vocab,     # V7
]


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
    for check in CHECKS:
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
    args = parser.parse_args(argv)

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
