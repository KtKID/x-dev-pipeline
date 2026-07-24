#!/usr/bin/env python3
"""Validate comparison formulas, scope boundaries, and report linkage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark_common import percent_delta, read_json


def validate(path: Path, report: Path | None) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    try:
        value = read_json(path)
    except ValueError as exc:
        return [{"code": "C001", "message": str(exc)}]
    runs = value.get("runs")
    if not isinstance(runs, list) or not runs:
        return [{"code": "C002", "message": "runs 必须是非空数组"}]
    by_id = {run.get("run_id"): run for run in runs if isinstance(run, dict)}
    baseline_id = value.get("baseline_run_id")
    candidate_id = value.get("candidate_run_id")
    if baseline_id not in by_id:
        issues.append({"code": "C003", "message": "baseline_run_id 不存在"})
    if candidate_id not in by_id:
        issues.append({"code": "C004", "message": "candidate_run_id 不存在"})

    for run_id, run in by_id.items():
        usage = run.get("usage", {})
        input_tokens = usage.get("input_tokens")
        cached = usage.get("cached_input_tokens")
        output = usage.get("output_tokens")
        total = usage.get("total_tokens")
        effective = usage.get("effective_tokens")
        if not all(isinstance(item, int) for item in (input_tokens, cached, output, total, effective)):
            issues.append({"code": "C005", "message": f"{run_id} Token 字段不完整"})
            continue
        if input_tokens + output != total:
            issues.append({"code": "C006", "message": f"{run_id} total_tokens 加总错误"})
        if input_tokens - cached + output != effective:
            issues.append({"code": "C007", "message": f"{run_id} effective_tokens 加总错误"})

    baseline = by_id.get(baseline_id)
    comparisons = value.get("comparisons")
    if baseline and isinstance(comparisons, dict):
        for run_id, comparison in comparisons.items():
            run = by_id.get(run_id)
            if not run or not isinstance(comparison, dict):
                issues.append({"code": "C008", "message": f"comparison run 无效: {run_id}"})
                continue
            if comparison.get("comparable"):
                for metric, values in comparison.get("metrics", {}).items():
                    expected = percent_delta(values.get("current"), values.get("baseline"))
                    if values.get("delta_pct") != expected:
                        issues.append(
                            {"code": "C009", "message": f"{run_id}.{metric} delta 公式错误"}
                        )

    promotion = value.get("promotion")
    if not isinstance(promotion, dict) or not isinstance(promotion.get("checks"), list):
        issues.append({"code": "C010", "message": "缺少 promotion checks"})
    elif promotion.get("passed") != all(check.get("passed") is True for check in promotion["checks"]):
        issues.append({"code": "C011", "message": "promotion.passed 与 checks 不一致"})

    if report is not None:
        if not report.is_file():
            issues.append({"code": "C012", "message": f"报告不存在: {report}"})
        else:
            text = report.read_text(encoding="utf-8")
            for run_id in by_id:
                if run_id not in text and by_id[run_id].get("label") not in text:
                    issues.append({"code": "C013", "message": f"报告未包含 run: {run_id}"})
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("comparison", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    issues = validate(args.comparison, args.report)
    result = {"valid": not issues, "issues": issues}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif issues:
        for issue in issues:
            print(f"{issue['code']}: {issue['message']}")
    else:
        print("comparison validation: PASS")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
