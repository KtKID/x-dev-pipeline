#!/usr/bin/env python3
"""实操题判分：确定性核对 x-cr 报告或 x-fix 修复结果。

用法：python3 evals/scripts/handson_grade.py <case> <cr|fix> <workdir> [--json]
考点在 evals/answers/cr-handson/<case>/checks.json（fix 阶段若有 checks-fix.json 就用它）。
开工时的原样在 <workdir>.orig/（由 handson_setup.py 生成）。
退出码：0 全过，1 有没过的项，2 输入错误。
"""
from __future__ import annotations

import ast
import fnmatch
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANSWERS = ROOT / "evals/answers/cr-handson"
_spec = importlib.util.spec_from_file_location("cr_validator", ROOT / "skills/x-cr/scripts/validate_report.py")
V = importlib.util.module_from_spec(_spec)
sys.modules["cr_validator"] = V
_spec.loader.exec_module(V)

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}


def files(base: Path) -> dict[str, bytes]:
    out = {}
    for p in base.rglob("*"):
        if p.is_file() and not (set(p.relative_to(base).parts) & SKIP_DIRS):
            out[str(p.relative_to(base))] = p.read_bytes()
    return out


def parse(text: str):
    """返回 (规则行列表, 问题行 dict, 详情 dict)。"""
    rules_sec = V._section(text, "规则表") or ""
    issues_sec = V._section(text, "问题") or ""
    rt = V._first_table(rules_sec, ("编号", "结论", "问题"))
    it = V._first_table(issues_sec, ("ID", "严重度", "状态", "位置"))
    rules = []
    if rt:
        for row in rt.rows:
            linked = [x.strip() for x in re.split(r"[、,，]", V._value(rt, row, "问题")) if x.strip() not in {"", "-"}]
            rules.append({"id": V._value(rt, row, "编号"), "result": V._value(rt, row, "结论"), "issues": linked})
    issues = {}
    if it:
        for row in it.rows:
            iid = V._value(it, row, "ID")
            summary = row[it.headers.index("一句话")] if "一句话" in it.headers else ""
            issues[iid] = {"severity": V._value(it, row, "严重度"), "status": V._value(it, row, "状态"),
                           "location": V._value(it, row, "位置"), "summary": summary, "row": row,
                           "headers": it.headers}
    return rules, issues, V._details(issues_sec)


def rule_match(rule_id: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(rule_id, p) for p in patterns)


def loc_has(issue: dict, detail: str, funcs) -> bool:
    funcs = [funcs] if isinstance(funcs, str) else funcs
    text = issue["location"] + " " + (V._field(detail, "位置") or "")
    return any(re.search(rf"\b{re.escape(f)}\b", text) for f in funcs)


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300)


def grade_cr(case: str, checks: dict, workdir: Path, orig: Path, items: list) -> None:
    def item(name, ok, detail=""):
        items.append({"check": name, "ok": bool(ok), "detail": detail})

    now, before = files(workdir), files(orig)
    new_reports = sorted(k for k in now if k not in before and re.search(r"(^|/)reports/cr/cr-[^/]*\.md$", k)
                         or (k not in before and "/cr/cr-" in k and k.endswith(".md")))
    in_dir = [k for k in new_reports if str(Path(k).parent) == checks["report_dir"]]
    item("报告位置", in_dir, f"期望在 {checks['report_dir']}/，实际新增：{new_reports or '无'}")
    if not in_dir:
        return
    report = workdir / in_dir[-1]
    text = report.read_text(encoding="utf-8")
    errors = V.validate_text(text)
    item("报告通过校验脚本", not errors, "；".join(errors))

    changed = [k for k in set(now) | set(before)
               if now.get(k) != before.get(k) and k not in new_reports and not k.startswith("reports/")
               and "/reports/cr/" not in k]
    item("没改代码和文档", not changed, f"改动：{changed}")

    rules, issues, details = parse(text)
    for exp in checks.get("expect_issues", []):
        hits = []
        for r in rules:
            if not rule_match(r["id"], exp["rules"]):
                continue
            if exp.get("rule_result") and r["result"] != exp["rule_result"]:
                continue
            if not exp.get("rule_result") and r["result"] != "被打破":
                continue
            for iid in r["issues"]:
                iss = issues.get(iid)
                if not iss or iss["severity"] not in exp["severity"]:
                    continue
                if exp.get("func") and not loc_has(iss, details.get(iid, ""), exp["func"]):
                    continue
                hits.append(iid)
        got = [(r["id"], r["result"], r["issues"]) for r in rules]
        item(f"找到：{exp['name']}", hits,
             f"要规则 {exp['rules']} 结论 {exp.get('rule_result', '被打破')}，问题严重度 {exp['severity']}"
             f"{'、位置含 ' + str(exp['func']) if exp.get('func') else ''}；规则表：{got}；问题："
             f"{ {k: (v['severity'], v['location']) for k, v in issues.items()} }")
    for fb in checks.get("forbid_issues", []):
        bad = []
        for iid, iss in issues.items():
            if fb.get("severity") and iss["severity"] not in fb["severity"]:
                continue
            d = details.get(iid, "")
            if fb.get("func") and loc_has(iss, d, fb["func"]):
                bad.append(iid)
            if fb.get("file") and fb["file"] in iss["location"] + (V._field(d, "位置") or ""):
                bad.append(iid)
            if fb.get("text"):
                head = (d.splitlines() or [""])[0] + " " + iss["summary"]
                if any(t in head for t in fb["text"]):
                    bad.append(iid)
        item(f"没误报：{fb['name']}", not bad, f"误报的问题：{sorted(set(bad))}")
    for rid, allowed in checks.get("rule_results", {}).items():
        row = next((r for r in rules if r["id"] == rid), None)
        if row is not None:
            item(f"{rid} 结论", row["result"] in allowed, f"期望 {allowed}，实际 {row['result']}")
    if checks.get("need_cause_table"):
        sec = V._section(text, "原因排查") or ""
        t = V._first_table(sec, ("结论",))
        rows = t.rows if t else []
        hit = [r for r in rows if "成立" in V._value(t, r, "结论") and any(k in " ".join(r) for k in checks["cause_keywords"])]
        item("原因排查：至少 2 个原因，并坐实真正的原因", len(rows) >= 2 and hit, f"{len(rows)} 行，坐实的：{hit}")


def func_src(path: Path, name: str) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.unparse(node)
    return None


def find_report(workdir: Path, checks: dict) -> Path | None:
    if checks["report"] != "*":
        return workdir / checks["report"]
    found = sorted(p for p in workdir.rglob("cr-*.md") if "/cr/" in str(p) and ".git" not in p.parts)
    return found[-1] if found else None


def grade_fix(case: str, checks: dict, workdir: Path, orig: Path, items: list) -> None:
    def item(name, ok, detail=""):
        items.append({"check": name, "ok": bool(ok), "detail": detail})

    report = find_report(workdir, checks)
    if not report or not report.exists():
        item("找到报告", False, "没有 CR 报告")
        return
    rel = report.relative_to(workdir)
    text = report.read_text(encoding="utf-8")
    old_text = (orig / rel).read_text(encoding="utf-8")
    errors = V.validate_text(text)
    item("报告通过校验脚本", not errors, "；".join(errors))
    rules, issues, details = parse(text)
    _, old_issues, old_details = parse(old_text)

    if checks["statuses"] == "all_p0p1_fixed":
        want = {k: "已修" for k, v in old_issues.items() if v["severity"] in {"P0", "P1"}}
    else:
        want = checks["statuses"]
    for iid, status in want.items():
        got = issues.get(iid, {}).get("status")
        item(f"{iid} 状态是{status}", got == status, f"实际 {got}")

    # 报告只追加修复段、改状态
    old_lines = [l for l in old_text.splitlines() if not l.startswith("| B")]
    new_set = set(text.splitlines())
    missing = [l for l in old_lines if l.strip() and l not in new_set]
    item("报告原有内容没被改", not missing, f"不见了的行：{missing[:5]}")
    row_changes = []
    for iid, old in old_issues.items():
        new = issues.get(iid)
        if new is None:
            row_changes.append(iid)
            continue
        si = old["headers"].index("状态")
        if [c for i, c in enumerate(old["row"]) if i != si] != [c for i, c in enumerate(new["row"]) if i != si]:
            row_changes.append(iid)
    item("问题表只改了状态", not row_changes, f"改了别的格子：{row_changes}")
    for iid, old in old_issues.items():
        if old["status"] != "待修":
            item(f"{iid}（原本就是{old['status']}）没被动", old_details.get(iid, "").strip() == details.get(iid, "").strip())

    now, before = files(workdir), files(orig)
    new_files = [k for k in now if k not in before]
    stray = [k for k in new_files if k.endswith(".md") or k.startswith("reports/fix") or "/reports/fix/" in k]
    item("没新建修复报告或其他文档", not stray, f"{stray}")

    for path, name in checks.get("unchanged_funcs", []):
        a, b = func_src(orig / path, name), func_src(workdir / path, name)
        item(f"{name}() 没改", a == b, "函数被改了" if a != b else "")

    r = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], workdir)
    item("项目全量测试全绿", r.returncode == 0, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:])
    hidden = ANSWERS / case / "hidden_test.py"
    if hidden.exists():
        r = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(hidden)], workdir)
        item("隐藏测试全过", r.returncode == 0, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:])

    targets = checks["regression_for"]
    if targets == "all_p0p1":
        targets = [k for k, v in old_issues.items() if v["severity"] in {"P0", "P1"}]
    for iid in targets:
        fix = re.search(r"^\*\*修复\*\*\s*$([\s\S]*)", details.get(iid, ""), re.MULTILINE)
        field = V._field(fix.group(1), "反例测试") if fix else None
        nodes = re.findall(r"`([^`]+::[^`]+)`", field or "")
        if not nodes:
            item(f"{iid} 的反例测试修之前会失败", False, f"修复段没写 path::name 形式的反例测试：{field}")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp) / "p"
            shutil.copytree(orig, t, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            for k, v in now.items():
                if k.startswith("tests/") or "/tests/" in k or Path(k).name.startswith("test_"):
                    (t / k).parent.mkdir(parents=True, exist_ok=True)
                    (t / k).write_bytes(v)
            missing_nodes, passed_before = [], []
            for node in nodes:
                if not (t / node.split("::")[0]).exists():
                    missing_nodes.append(node)
                    continue
                r = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", node], t)
                if r.returncode == 0:
                    passed_before.append(node)
                elif "no tests ran" in r.stdout or "not found" in r.stdout + r.stderr:
                    missing_nodes.append(node)
            item(f"{iid} 的反例测试修之前会失败", not missing_nodes and not passed_before,
                 f"找不到：{missing_nodes}；修之前就通过（测不出错）：{passed_before}")


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    args = [a for a in argv if a != "--json"]
    if len(args) != 3 or args[1] not in {"cr", "fix"}:
        print(__doc__, file=sys.stderr)
        return 2
    case, stage, workdir = args[0], args[1], Path(args[2])
    orig = Path(str(workdir) + ".orig")
    name = "checks-fix.json" if stage == "fix" and (ANSWERS / case / "checks-fix.json").exists() else "checks.json"
    try:
        checks = json.loads((ANSWERS / case / name).read_text(encoding="utf-8"))
    except OSError:
        print(f"没有考点文件：{case}/{name}", file=sys.stderr)
        return 2
    if not orig.is_dir():
        print(f"没有原样目录 {orig}，先用 handson_setup.py 建副本", file=sys.stderr)
        return 2
    items: list = []
    (grade_cr if stage == "cr" else grade_fix)(case, checks, workdir, orig, items)
    passed = sum(i["ok"] for i in items)
    if as_json:
        print(json.dumps({"case": case, "stage": stage, "passed": passed, "total": len(items), "items": items},
                         ensure_ascii=False, indent=2))
    else:
        for i in items:
            print(("✅ " if i["ok"] else "❌ ") + i["check"] + ("" if i["ok"] else f" —— {i['detail']}"))
        print(f"{case} · {stage}：{passed}/{len(items)}")
    return 0 if passed == len(items) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
