#!/usr/bin/env python3
"""x-code-audit 实操题：建副本、判分。

  audit_grade.py setup <workdir>                 复制 evals/problems/code-audit/cases/library/project，git 提交一次，留 <workdir>.orig
  audit_grade.py grade <full|module> <workdir> [--json]
退出码：0 全过，1 有没过的项，2 输入错误。
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "evals/problems/code-audit/cases/library/project"
CHECKS = ROOT / "evals/answers/code-audit/checks.json"
AUDIT = ROOT / "skills/x-code-audit/scripts/audit.py"
_s = importlib.util.spec_from_file_location("audit_mod", AUDIT)
A = importlib.util.module_from_spec(_s)
sys.modules["audit_mod"] = A
_s.loader.exec_module(A)
SKIP = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", "reports"}


def setup(work: Path) -> int:
    for p in (work, Path(str(work) + ".orig")):
        if p.exists():
            shutil.rmtree(p)
    shutil.copytree(FIXTURE, work, ignore=shutil.ignore_patterns(*SKIP))
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
        subprocess.run(["git", "-c", "user.email=e@x", "-c", "user.name=e", *args], cwd=work, check=True, capture_output=True)
    shutil.copytree(work, Path(str(work) + ".orig"))
    print(work)
    return 0


def files(base: Path) -> dict[str, bytes]:
    return {str(p.relative_to(base)): p.read_bytes() for p in base.rglob("*")
            if p.is_file() and not (set(p.relative_to(base).parts) & SKIP)}


def as_list(x):
    return x if isinstance(x, list) else ([x] if x else [])


def match(iss: dict, rule: dict) -> bool:
    if rule.get("layer") and iss.get("层") not in rule["layer"]:
        return False
    if rule.get("severity") and iss.get("严重度") not in rule["severity"]:
        return False
    where = iss.get("位置", "")
    blob = " ".join(str(v) for v in iss.values())
    if rule.get("file") and not any(f in where for f in as_list(rule["file"])):
        return False
    if rule.get("func") and not re.search(rf"\b{re.escape(rule['func'])}\b", where + " " + iss.get("标题", "")):
        return False
    if rule.get("text") and not any(t in blob for t in rule["text"]):
        return False
    if rule.get("title_text") and not any(t in iss.get("标题", "") for t in rule["title_text"]):
        return False
    if rule.get("unless_text") and any(t in blob for t in rule["unless_text"]):
        return False
    return True


def grade(case: str, work: Path) -> dict:
    checks = json.loads(CHECKS.read_text(encoding="utf-8"))[case]
    items = []

    def item(name, ok, detail=""):
        items.append({"check": name, "ok": bool(ok), "detail": detail})

    audit_dir = work / "reports/audit"
    reports = sorted(audit_dir.glob("audit-*.md")) if audit_dir.is_dir() else []
    others = [p.name for p in audit_dir.iterdir()] if audit_dir.is_dir() else []
    item("只产出一份报告", len(reports) == 1 and len(others) == 1, f"reports/audit/ 下有：{others}")
    if not reports:
        return {"case": case, "items": items}
    m = re.fullmatch(r"audit-([0-9a-f]{8})\.md", reports[0].name)
    item("文件名带 8 位检查 ID", m, reports[0].name)
    if not m:
        return {"case": case, "items": items}
    rep = A.Report(work, m.group(1))
    text = rep.text
    head = text.split("## 问题", 1)[0]
    item("开头写了检查 ID 和范围", rep.header("检查 ID") == rep.id and rep.header("范围") and "## 范围" in head,
         f"检查 ID={rep.header('检查 ID')} 范围={rep.header('范围')}")
    snapshot = text
    errors = A.cmd_verify(rep)
    rep.text = snapshot
    rep.save()
    item("audit.py verify 通过", not errors, "；".join(errors[:6]))
    item("报告状态是完成", (rep.header("状态") or "").startswith("完成"), rep.header("状态"))
    conclusion = rep.section("结论").strip()
    item("写了结论", conclusion and "主 agent 在 merge" not in conclusion, conclusion[:80])

    before, now = files(Path(str(work) + ".orig")), files(work)
    changed = sorted(k for k in set(before) | set(now) if before.get(k) != now.get(k))
    item("没改代码、配置和文档", not changed, f"{changed}")

    issues = rep.issues()
    sev = [i.get("严重度") for i in issues]
    item("问题按 P0 → P2 排序", sev == sorted(sev, key=lambda s: A.SEVERITIES.index(s) if s in A.SEVERITIES else 9), f"{sev}")
    plain = [n for n, i in enumerate(issues, 1) if not (i.get("是什么") and i.get("影响") and i.get("位置"))]
    item("每个问题都写了是什么、影响、位置", not plain, f"缺的：A{plain}")
    for rule in checks["expect"]:
        hits = [f"A{n}" for n, i in enumerate(issues, 1) if match(i, rule)]
        item(f"找到：{rule['name']}", hits, f"要 {rule}")
    for rule in checks["forbid"]:
        bad = [f"A{n}" for n, i in enumerate(issues, 1) if match(i, rule)]
        item(f"没误报：{rule['name']}", not bad, f"误报：{bad}")
    if checks.get("scope_only"):
        scope = checks["scope_only"]
        out = [f"A{n}" for n, i in enumerate(issues, 1)
               if i.get("层") in ("L2", "L4", "L6") and scope not in i.get("位置", "") and "tests/" not in i.get("位置", "")]
        item(f"L2/L4/L6 只报 {scope} 里的问题（它的测试除外）", not out, f"范围外：{out}")
    return {"case": case, "items": items, "issues": len(issues),
            "by_severity": {s: sev.count(s) for s in A.SEVERITIES},
            "ai_issues_with_fix": sum(1 for i in issues if i.get("层") in ("L4", "L6") and i.get("怎么改")),
            "ai_issues": sum(1 for i in issues if i.get("层") in ("L4", "L6"))}


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "setup":
        return setup(Path(argv[1]))
    as_json = "--json" in argv
    args = [a for a in argv if a != "--json"]
    if len(args) != 3 or args[0] != "grade" or args[1] not in ("full", "module"):
        print(__doc__, file=sys.stderr)
        return 2
    res = grade(args[1], Path(args[2]))
    ok = sum(i["ok"] for i in res["items"])
    res["passed"], res["total"] = ok, len(res["items"])
    if as_json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        for i in res["items"]:
            print(("✅ " if i["ok"] else "❌ ") + i["check"] + ("" if i["ok"] else f" —— {i['detail']}"))
        print(f"{args[1]}：{ok}/{len(res['items'])}")
    return 0 if ok == len(res["items"]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
