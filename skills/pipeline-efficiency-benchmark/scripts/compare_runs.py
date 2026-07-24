#!/usr/bin/env python3
"""Generate scope-safe horizontal comparison JSON and Markdown."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from benchmark_common import BenchmarkError, percent_delta, read_json, write_json


def score_value(run: dict[str, Any], kind: str) -> float | None:
    value = run.get("scores", {}).get(kind)
    if not isinstance(value, dict) or value.get("score") is None:
        return None
    return float(value["score"])


def comparable_delta(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    comparable = (
        current.get("scope") == baseline.get("scope")
        and current.get("usage", {}).get("convention")
        == baseline.get("usage", {}).get("convention")
    )
    reason = None
    if current.get("scope") != baseline.get("scope"):
        reason = "scope_mismatch"
    elif current.get("usage", {}).get("convention") != baseline.get("usage", {}).get("convention"):
        reason = "token_convention_mismatch"
    metrics = {}
    for key, path in {
        "total_tokens": ("usage", "total_tokens"),
        "effective_tokens": ("usage", "effective_tokens"),
        "main_active_seconds": ("duration", "main_active_seconds"),
        "executor_time_sum_seconds": ("duration", "executor_time_sum_seconds"),
        "tool_calls": ("calls", "tool_calls"),
        "llm_calls": ("calls", "llm_calls"),
    }.items():
        current_value = current.get(path[0], {}).get(path[1])
        baseline_value = baseline.get(path[0], {}).get(path[1])
        metrics[key] = {
            "baseline": baseline_value,
            "current": current_value,
            "delta_pct": percent_delta(current_value, baseline_value) if comparable else None,
        }
    full_current = score_value(current, "full")
    full_baseline = score_value(baseline, "full")
    spec_current = score_value(current, "spec_risk")
    spec_baseline = score_value(baseline, "spec_risk")
    return {
        "comparable": comparable,
        "reason": reason,
        "metrics": metrics,
        "score_delta_points": {
            "full": round(full_current - full_baseline, 2)
            if full_current is not None and full_baseline is not None
            else None,
            "spec_risk": round(spec_current - spec_baseline, 2)
            if spec_current is not None and spec_baseline is not None
            else None,
        },
    }


def format_value(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Pipeline Efficiency Benchmark 横向对比",
        "",
        f"- Baseline：`{result['baseline_run_id']}`",
        f"- Candidate：`{result['candidate_run_id']}`",
        f"- 晋级：**{'PASS' if result['promotion']['passed'] else 'FAIL'}**",
        "",
        "## 核心指标",
        "",
        "| Run | Scope | Full score | Spec/Risk | Total tokens | Effective tokens | Main seconds | Executor seconds | Tools | LLM calls |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for run in result["runs"]:
        lines.append(
            "| {label} | {scope} | {full} | {spec} | {total} | {effective} | {main} | {executor} | {tools} | {llm} |".format(
                label=run["label"],
                scope=run["scope"],
                full=format_value(score_value(run, "full")),
                spec=format_value(score_value(run, "spec_risk")),
                total=format_value(run["usage"].get("total_tokens")),
                effective=format_value(run["usage"].get("effective_tokens")),
                main=format_value(run["duration"].get("main_active_seconds")),
                executor=format_value(run["duration"].get("executor_time_sum_seconds")),
                tools=format_value(run["calls"].get("tool_calls")),
                llm=format_value(run["calls"].get("llm_calls")),
            )
        )
    lines.extend(["", "## 相对 Baseline", ""])
    for run_id, comparison in result["comparisons"].items():
        lines.append(f"### {run_id}")
        lines.append("")
        if not comparison["comparable"]:
            lines.append(f"比较状态：不可直接比较，原因 `{comparison['reason']}`。")
            lines.append("")
            continue
        lines.extend(
            [
                "| 指标 | Baseline | Current | Delta |",
                "|---|---:|---:|---:|",
            ]
        )
        for metric, values in comparison["metrics"].items():
            delta = values["delta_pct"]
            lines.append(
                f"| {metric} | {format_value(values['baseline'])} | {format_value(values['current'])} | "
                f"{format_value(delta) + '%' if delta is not None else '—'} |"
            )
        lines.append("")
    lines.extend(["## 晋级门禁", ""])
    for check in result["promotion"]["checks"]:
        lines.append(f"- {'PASS' if check['passed'] else 'FAIL'} · {check['name']}: {check['evidence']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="append", required=True, type=Path)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--min-quality", type=float, default=100.0)
    parser.add_argument("--min-token-reduction-pct", type=float, default=10.0)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    args = parser.parse_args()
    try:
        runs = [read_json(path) for path in args.run]
        by_id = {run.get("run_id"): run for run in runs}
        if len(by_id) != len(runs) or None in by_id:
            raise BenchmarkError("run_id 缺失或重复")
        if args.baseline not in by_id:
            raise BenchmarkError(f"baseline run_id 不存在: {args.baseline}")
        if args.candidate not in by_id:
            raise BenchmarkError(f"candidate run_id 不存在: {args.candidate}")
        baseline = by_id[args.baseline]
        candidate = by_id[args.candidate]
        comparisons = {
            run["run_id"]: comparable_delta(run, baseline)
            for run in runs
            if run["run_id"] != args.baseline
        }
        candidate_comparison = comparisons[args.candidate]
        candidate_full = candidate.get("scores", {}).get("full")
        quality = score_value(candidate, "full")
        critical = (
            candidate_full.get("critical_gate_passed")
            if isinstance(candidate_full, dict)
            else None
        )
        token_delta = candidate_comparison["metrics"]["total_tokens"]["delta_pct"]
        checks = [
            {
                "name": "same_scope_and_token_convention",
                "passed": bool(candidate_comparison["comparable"]),
                "evidence": candidate_comparison["reason"] or "comparable",
            },
            {
                "name": "full_quality",
                "passed": quality is not None and quality >= args.min_quality,
                "evidence": f"score={quality}, required={args.min_quality}",
            },
            {
                "name": "critical_gate",
                "passed": critical is True,
                "evidence": f"critical_gate_passed={critical}",
            },
            {
                "name": "token_reduction",
                "passed": token_delta is not None and token_delta <= -args.min_token_reduction_pct,
                "evidence": f"delta_pct={token_delta}, required<=-{args.min_token_reduction_pct}",
            },
        ]
        result = {
            "schema_version": 1,
            "baseline_run_id": args.baseline,
            "candidate_run_id": args.candidate,
            "runs": runs,
            "comparisons": comparisons,
            "promotion": {
                "passed": all(check["passed"] for check in checks),
                "checks": checks,
                "min_quality": args.min_quality,
                "min_token_reduction_pct": args.min_token_reduction_pct,
            },
        }
        write_json(args.output_json, result)
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(result), encoding="utf-8")
    except (BenchmarkError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"valid": True, "promotion_passed": result["promotion"]["passed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
