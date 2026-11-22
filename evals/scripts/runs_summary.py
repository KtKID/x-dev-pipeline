#!/usr/bin/env python3
"""汇总 evals/runs/ 下的判题记录。

用法：
  python3 evals/scripts/runs_summary.py            # 每个 eval 最近一轮的每次运行
  python3 evals/scripts/runs_summary.py --all      # 全部轮次
  python3 evals/scripts/runs_summary.py spec-scope # 只看一个 eval 的全部轮次
"""
import json
import re
import sys
from pathlib import Path

RUNS = Path(__file__).resolve().parents[1] / "runs"


def iteration_no(path: Path) -> int:
    m = re.search(r"(\d+)$", path.name)
    return int(m.group(1)) if m else -1


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all" in sys.argv or bool(args)
    evals = [RUNS / a for a in args] if args else sorted(p for p in RUNS.iterdir() if p.is_dir())
    print(f"{'eval':<22}{'轮次':<14}{'运行':<8}{'得分':<10}整题")
    for ev in evals:
        its = sorted((p for p in ev.glob("iteration-*") if p.is_dir()), key=iteration_no)
        if not its:
            continue
        for it in (its if show_all else its[-1:]):
            for run in sorted(it.glob("run-*")):
                g = run / "grading.json"
                if not g.is_file():
                    print(f"{ev.name:<22}{it.name:<14}{run.name:<8}（缺 grading.json）")
                    continue
                d = json.loads(g.read_text(encoding="utf-8"))
                wrong = [r["id"] for r in d.get("rows", []) if not r.get("ok")]
                tail = f"  错题 {'、'.join(wrong)}" if wrong else ""
                print(f"{ev.name:<22}{it.name:<14}{run.name:<8}{d['score']}/{d['total']:<6}{d['cases_passed']}/{d['cases']}{tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
