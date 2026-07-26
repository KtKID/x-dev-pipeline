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


def unknown_cost(reason: str) -> dict[str, Any]:
    return {
        "status": "unknown",
        "currency": None,
        "pricing": None,
        "calculation": {
            "api_equivalent": None,
            "cache_write_upper_bound": None,
            "no_cache_api_equivalent": None,
            "cache_savings": None,
            "cache_savings_pct": None,
        },
        "billing": {
            "mode": "unknown",
            "actual_cash_increment": None,
            "quota_multiplier": None,
            "quota_equivalent": None,
            "note": reason,
        },
        "unknown_reason": reason,
    }


def ensure_cost(run: dict[str, Any]) -> None:
    if not isinstance(run.get("cost"), dict):
        run["cost"] = unknown_cost("cost_not_persisted_in_historical_run")


def cost_value(run: dict[str, Any], field: str) -> float | None:
    calculation = run.get("cost", {}).get("calculation")
    if not isinstance(calculation, dict):
        return None
    value = calculation.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return float(value)


def cost_delta(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    current_value = cost_value(current, "api_equivalent")
    baseline_value = cost_value(baseline, "api_equivalent")
    current_currency = current.get("cost", {}).get("currency")
    baseline_currency = baseline.get("cost", {}).get("currency")
    same_scope = current.get("scope") == baseline.get("scope")
    same_currency = (
        isinstance(current_currency, str)
        and current_currency
        and current_currency == baseline_currency
    )
    available = current_value is not None and baseline_value is not None
    comparable = same_scope and same_currency and available
    if not available:
        reason = "amount_unavailable"
    elif not same_scope:
        reason = "scope_mismatch"
    elif not same_currency:
        reason = "currency_mismatch"
    else:
        reason = None
    same_model_reasoning = (
        current.get("model") == baseline.get("model")
        and current.get("reasoning_effort") == baseline.get("reasoning_effort")
    )
    qualification = (
        "same_model_reasoning"
        if comparable and same_model_reasoning
        else "cross_model_or_reasoning_arithmetic_context"
        if comparable
        else None
    )
    return {
        "comparable": comparable,
        "reason": reason,
        "currency": current_currency if same_currency else None,
        "baseline": baseline_value,
        "current": current_value,
        "delta": round(current_value - baseline_value, 12) if comparable else None,
        "delta_pct": percent_delta(current_value, baseline_value) if comparable else None,
        "qualification": qualification,
    }


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
    amount_delta = cost_delta(current, baseline)
    metrics["api_equivalent_cost"] = {
        "baseline": amount_delta["baseline"],
        "current": amount_delta["current"],
        "delta_pct": amount_delta["delta_pct"],
        "currency": amount_delta["currency"],
        "qualification": amount_delta["qualification"],
    }
    return {
        "comparable": comparable,
        "reason": reason,
        "metrics": metrics,
        "cost": amount_delta,
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


def format_money(value: object, currency: object) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "unknown"
    prefix = "$" if currency == "USD" else f"{currency} "
    return f"{prefix}{float(value):,.6f}"


def format_rate(value: object, currency: object) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "—"
    prefix = "$" if currency == "USD" else f"{currency} "
    return f"{prefix}{float(value):,.4f}"


def markdown_link(label: str, url: object) -> str:
    if not isinstance(url, str) or not url:
        return "unknown"
    return f"[{label}]({url})"


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
        "| Run | Scope | Full score | Spec/Risk | Total tokens | Effective tokens | API 等价成本 | Main seconds | Executor seconds | Tools | LLM calls |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for run in result["runs"]:
        lines.append(
            "| {label} | {scope} | {full} | {spec} | {total} | {effective} | {cost} | {main} | {executor} | {tools} | {llm} |".format(
                label=run["label"],
                scope=run["scope"],
                full=format_value(score_value(run, "full")),
                spec=format_value(score_value(run, "spec_risk")),
                total=format_value(run["usage"].get("total_tokens")),
                effective=format_value(run["usage"].get("effective_tokens")),
                cost=format_money(
                    cost_value(run, "api_equivalent"),
                    run.get("cost", {}).get("currency"),
                ),
                main=format_value(run["duration"].get("main_active_seconds")),
                executor=format_value(run["duration"].get("executor_time_sum_seconds")),
                tools=format_value(run["calls"].get("tool_calls")),
                llm=format_value(run["calls"].get("llm_calls")),
            )
        )
    lines.extend(
        [
            "",
            "## 金额",
            "",
            "金额统一使用每个 run 冻结的价格快照计算。API 等价成本用于跨运行观察；实际现金增量与套餐额度单独列示。",
            "",
            "| Run | Model | 单价 / 1M（uncached / cached / cache-write / output） | API 等价成本 | Cache-write 上界 | 无缓存成本 | 缓存节省 | 实际现金增量 | 套餐额度权重 | 价格来源 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for run in result["runs"]:
        cost = run.get("cost", {})
        currency = cost.get("currency")
        pricing = cost.get("pricing")
        calculation = cost.get("calculation", {})
        billing = cost.get("billing", {})
        if isinstance(pricing, dict):
            rates = pricing.get("rates_per_million_tokens", {})
            rates_text = " / ".join(
                format_rate(rates.get(key), currency)
                for key in (
                    "uncached_input",
                    "cached_input",
                    "cache_write_input",
                    "output",
                )
            )
            source = markdown_link(
                str(pricing.get("queried_at") or "pricing"),
                pricing.get("source_url"),
            )
        else:
            rates_text = "unknown"
            source = str(cost.get("unknown_reason") or "unknown")
        savings_value = calculation.get("cache_savings")
        savings_pct = calculation.get("cache_savings_pct")
        savings = format_money(savings_value, currency)
        if isinstance(savings_pct, (int, float)) and not isinstance(savings_pct, bool):
            savings += f" · {float(savings_pct):.2f}%"
        multiplier = billing.get("quota_multiplier")
        quota = format_money(billing.get("quota_equivalent"), currency)
        if isinstance(multiplier, (int, float)) and not isinstance(multiplier, bool):
            quota = f"{float(multiplier):g}× · {quota}"
        lines.append(
            "| {label} | {model} | {rates} | {api} | {upper} | {no_cache} | {savings} | {cash} | {quota} | {source} |".format(
                label=run["label"],
                model=run.get("model") or "unknown",
                rates=rates_text,
                api=format_money(calculation.get("api_equivalent"), currency),
                upper=format_money(calculation.get("cache_write_upper_bound"), currency),
                no_cache=format_money(calculation.get("no_cache_api_equivalent"), currency),
                savings=savings,
                cash=format_money(billing.get("actual_cash_increment"), currency),
                quota=quota,
                source=source,
            )
        )
    lines.extend(["", "### 相对 Baseline 的金额变化", ""])
    lines.extend(
        [
            "| Run | Baseline | Current | Delta | Delta % | 口径 |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for run_id, comparison in result["comparisons"].items():
        amount = comparison["cost"]
        lines.append(
            "| {run_id} | {baseline} | {current} | {delta} | {delta_pct} | {qualification} |".format(
                run_id=run_id,
                baseline=format_money(amount.get("baseline"), amount.get("currency")),
                current=format_money(amount.get("current"), amount.get("currency")),
                delta=format_money(amount.get("delta"), amount.get("currency")),
                delta_pct=f"{amount['delta_pct']:.2f}%"
                if isinstance(amount.get("delta_pct"), (int, float))
                else "unknown",
                qualification=amount.get("qualification") or amount.get("reason") or "unknown",
            )
        )
    lines.extend(["", "## 相对 Baseline", ""])
    for run_id, comparison in result["comparisons"].items():
        lines.append(f"### {run_id}")
        lines.append("")
        if not comparison["comparable"]:
            lines.append(f"比较状态：范围或 Token 口径不一致，原因 `{comparison['reason']}`。")
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
        for run in runs:
            ensure_cost(run)
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
            "schema_version": 2,
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
            "cost_policy": {
                "required_report_fields": [
                    "pricing_source",
                    "queried_at",
                    "rates_per_million_tokens",
                    "api_equivalent",
                    "cache_write_upper_bound",
                    "no_cache_api_equivalent",
                    "cache_savings",
                    "actual_cash_increment",
                    "quota_multiplier",
                    "quota_equivalent",
                ],
                "unknown_is_explicit": True,
                "promotion_uses_cost": False,
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
