#!/usr/bin/env python3
"""确定性评分：spec-scope 与 qdev-spec-routing 两组 JSON 判题。

用法：python3 evals/scripts/grade_spec_routing.py <spec-scope|qdev-spec-routing> <answer.json> [--json]
退出码：0 全对，1 有错题，2 输入错误。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXISTING = {"member", "catalog", "loan", "fine", "message", "engineering"}
FIELDS = ["route", "writes", "task_spec", "confirm", "tech_design"]


def norm_writes(writes):
    out = set()
    for w in writes or []:
        spec = str(w.get("spec", "")).strip().lower()
        action = str(w.get("action", "")).strip().lower()
        if action == "new" and spec not in EXISTING:
            spec = "*"
        out.add((spec, action))
    return out


def new_name(writes):
    for w in writes or []:
        if str(w.get("action", "")).lower() == "new":
            return str(w.get("spec", "")).strip().lower()
    return None


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("spec-scope", "qdev-spec-routing"):
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
        if kind == "spec-scope":
            exp = {"writes": exp}
        wrong = []
        for field in FIELDS:
            if field not in exp:
                continue
            total += 1
            e = exp[field]
            g = got.get(field)
            if field == "writes":
                ok = norm_writes(g) == {tuple(x) for x in e}
            elif field == "task_spec" and e == "*":
                ok = g is not None and str(g).lower() not in EXISTING and str(g).lower() == new_name(got.get("writes"))
            elif isinstance(e, str) and isinstance(g, str):
                ok = g.strip().lower() == e.lower()
            else:
                ok = g == e
            if ok:
                score += 1
            else:
                wrong.append({"field": field, "expected": e, "got": g})
        rows.append({"id": cid, "ok": not wrong, "wrong": wrong, "reason": got.get("reason")})

    result = {"eval": kind, "score": score, "total": total,
              "cases_passed": sum(r["ok"] for r in rows), "cases": len(rows), "rows": rows}
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{kind}: 字段 {score}/{total}，整题 {result['cases_passed']}/{result['cases']}")
        for r in rows:
            if not r["ok"]:
                for w in r["wrong"]:
                    print(f"  ✗ {r['id']} {w['field']}: 期望 {w['expected']}，实际 {w['got']}")
                print(f"    理由：{r['reason']}")
    return 0 if score == total else 1


if __name__ == "__main__":
    sys.exit(main())
