#!/usr/bin/env python3
"""确定性评分：spec / qdev / 链路同步 / 分组 / 多 agent 开发几组 JSON 判题。

用法：python3 evals/scripts/grade_spec_routing.py <kind> <answer.json> [--json]
kind：spec-scope、qdev-spec-routing、change-sync、qdev-confirm-check、req-grouping、dev-worker、dev-main
退出码：0 全对，1 有错题，2 输入错误。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KINDS = ("spec-scope", "qdev-spec-routing", "change-sync", "qdev-confirm-check", "req-grouping", "dev-worker", "dev-main")
EXISTING_SPECS = {"member", "catalog", "loan", "fine", "message", "engineering"}
QDEV_FIELDS = ["route", "writes", "task_spec", "confirm", "tech_design"]

# 早期轮次用英文取值，评分时按同义处理
ALIASES = {
    "append": "加到已有", "new": "新建", "log-only": "只记变更",
    "mainline": "转主线", "task": "task②",
}

# change-sync 题目项目里已有的编号
EXISTING_ITEMS = {"D01", "D02", "D03", "T1", "T2", "T3", "T4", "T5", "任务行1", "任务行2", "任务行3"}


def canon(value):
    if isinstance(value, str):
        v = value.strip()
        return ALIASES.get(v.lower(), v)
    return value


def norm_writes(writes):
    out = set()
    for w in writes or []:
        spec = str(w.get("spec", "")).strip().lower()
        action = canon(str(w.get("action", "")))
        if action == "新建" and spec not in EXISTING_SPECS:
            spec = "*"
        if action == "问用户":
            spec = "*"
        out.add((spec, action))
    return out


def new_spec_name(writes):
    for w in writes or []:
        if canon(str(w.get("action", ""))) == "新建":
            return str(w.get("spec", "")).strip().lower()
    return None


def norm_changes(changes):
    out = set()
    for c in changes or []:
        item = str(c.get("item", "")).strip().replace(" ", "")
        action = str(c.get("action", "")).strip()
        if action == "新增" and item not in EXISTING_ITEMS:
            # 新编号一律归为“新D / 新T / 新任务行”
            m = re.match(r"^(新)?(D|T|任务行)", item)
            if m:
                item = "新" + m.group(2)
        out.add((item, action))
    return out


GROUPING_CASES = None


def grade_grouping(exp, got):
    """3 分：完整、硬规则（文件交集 + 指定同组）、组数范围。"""
    global GROUPING_CASES
    if GROUPING_CASES is None:
        cases = json.loads((ROOT / "evals/problems/req-grouping/cases.json").read_text())
        GROUPING_CASES = {c["id"]: c for c in cases}
    case = GROUPING_CASES[got.get("id")] if got.get("id") in GROUPING_CASES else None
    groups = got.get("groups") or {}
    wrong, score = [], 0
    where = {}
    dup = False
    for g, rows in groups.items():
        for r in rows or []:
            if r in where:
                dup = True
            where[r] = g
    all_rows = [r["row"] for r in case["rows"]] if case else []
    if case and not dup and sorted(where) == sorted(all_rows):
        score += 1
    else:
        wrong.append({"field": "完整", "expected": all_rows, "got": groups})
    hard_ok = True
    if case:
        rows = case["rows"]
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if set(a["files"]) & set(b["files"]) and where.get(a["row"]) != where.get(b["row"]):
                    hard_ok = False
        for same in exp["same"]:
            if len({where.get(r) for r in same}) != 1:
                hard_ok = False
    if hard_ok:
        score += 1
    else:
        wrong.append({"field": "硬规则/同组", "expected": exp["same"] or "文件有交集的行同组", "got": groups})
    lo, hi = exp["count"]
    n = len([g for g, rows in groups.items() if rows])
    if lo <= n <= hi:
        score += 1
    else:
        wrong.append({"field": "组数", "expected": f"{lo}–{hi}", "got": n})
    return score, 3, wrong


def grade_case(kind, exp, got):
    """返回 (得分, 满分, 错误列表)。"""
    if kind == "spec-scope":
        ok = norm_writes(got.get("writes")) == {tuple(x) for x in exp}
        return (1 if ok else 0), 1, ([] if ok else [{"field": "writes", "expected": exp, "got": got.get("writes")}])
    if kind in ("dev-worker", "dev-main"):
        ok = str(got.get("action", "")).strip() == exp
        return (1 if ok else 0), 1, ([] if ok else [{"field": "action", "expected": exp, "got": got.get("action")}])
    if kind == "req-grouping":
        return grade_grouping(exp, got)
    if kind == "qdev-confirm-check":
        ok = str(got.get("result", "")).strip() == exp
        return (1 if ok else 0), 1, ([] if ok else [{"field": "result", "expected": exp, "got": got.get("result")}])
    if kind == "change-sync":
        ok = norm_changes(got.get("changes")) == {tuple(x) for x in exp}
        return (1 if ok else 0), 1, ([] if ok else [{"field": "changes", "expected": exp, "got": got.get("changes")}])

    score, wrong = 0, []
    for field in QDEV_FIELDS:
        e, g = exp[field], got.get(field)
        if field == "writes":
            ok = norm_writes(g) == {tuple(x) for x in e}
        elif field == "task_spec" and e == "*":
            name = str(g).strip().lower() if g is not None else None
            ok = name is not None and name not in EXISTING_SPECS and name == new_spec_name(got.get("writes"))
        elif isinstance(e, str):
            ok = isinstance(g, str) and canon(g).lower() == e.lower()
        else:
            ok = g == e
        if ok:
            score += 1
        else:
            wrong.append({"field": field, "expected": e, "got": g})
    return score, len(QDEV_FIELDS), wrong


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in KINDS:
        print(__doc__)
        return 2
    kind, answer_path = sys.argv[1], Path(sys.argv[2])
    expected = json.loads((ROOT / "evals/answers" / kind / "expected.json").read_text())
    try:
        answers = {a["id"]: a for a in json.loads(answer_path.read_text())}
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"答案文件无法读取：{e}")
        return 2

    rows, score, total = [], 0, 0
    for cid, exp in expected.items():
        got = answers.get(cid, {})
        s, t, wrong = grade_case(kind, exp, got)
        score += s
        total += t
        rows.append({"id": cid, "ok": not wrong, "wrong": wrong, "reason": got.get("reason")})

    result = {"eval": kind, "score": score, "total": total,
              "cases_passed": sum(r["ok"] for r in rows), "cases": len(rows), "rows": rows}
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{kind}: 得分 {score}/{total}，整题 {result['cases_passed']}/{result['cases']}")
        for r in rows:
            for w in r["wrong"]:
                print(f"  ✗ {r['id']} {w['field']}: 期望 {w['expected']}，实际 {w['got']}")
            if r["wrong"]:
                print(f"    理由：{r['reason']}")
    return 0 if score == total else 1


if __name__ == "__main__":
    sys.exit(main())
