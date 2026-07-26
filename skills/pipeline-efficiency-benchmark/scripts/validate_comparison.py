#!/usr/bin/env python3
"""Validate comparison formulas, scope boundaries, and report linkage."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from benchmark_common import percent_delta, read_json


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def close(left: object, right: float) -> bool:
    return is_number(left) and math.isclose(
        float(left),
        float(right),
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def validate_run_cost(run_id: object, run: dict, issues: list[dict[str, str]]) -> None:
    cost = run.get("cost")
    if not isinstance(cost, dict):
        issues.append({"code": "C014", "message": f"{run_id} 缺少 cost 金额块"})
        return
    status = cost.get("status")
    if status == "unknown":
        if not isinstance(cost.get("unknown_reason"), str) or not cost["unknown_reason"]:
            issues.append({"code": "C015", "message": f"{run_id} unknown 金额缺少原因"})
        return
    if status != "priced":
        issues.append({"code": "C016", "message": f"{run_id} cost.status 非法"})
        return

    currency = cost.get("currency")
    pricing = cost.get("pricing")
    calculation = cost.get("calculation")
    billing = cost.get("billing")
    if (
        not isinstance(currency, str)
        or not currency
        or not isinstance(pricing, dict)
        or not isinstance(calculation, dict)
        or not isinstance(billing, dict)
    ):
        issues.append({"code": "C017", "message": f"{run_id} priced 金额结构不完整"})
        return
    if not isinstance(pricing.get("source_url"), str) or not pricing["source_url"]:
        issues.append({"code": "C018", "message": f"{run_id} 缺少价格来源 URL"})
    if not isinstance(pricing.get("queried_at"), str) or not pricing["queried_at"]:
        issues.append({"code": "C019", "message": f"{run_id} 缺少价格查询日期"})
    rates = pricing.get("rates_per_million_tokens")
    if not isinstance(rates, dict):
        issues.append({"code": "C020", "message": f"{run_id} 缺少单价"})
        return
    required_rates = ("uncached_input", "cached_input", "output")
    if any(not is_number(rates.get(key)) or rates[key] < 0 for key in required_rates):
        issues.append({"code": "C020", "message": f"{run_id} 必需单价非法"})
        return
    cache_write_rate = rates.get("cache_write_input")
    if cache_write_rate is not None and (
        not is_number(cache_write_rate) or cache_write_rate < 0
    ):
        issues.append({"code": "C020", "message": f"{run_id} cache-write 单价非法"})
        return

    usage = run.get("usage", {})
    uncached_tokens = usage.get("uncached_input_tokens")
    cached_tokens = usage.get("cached_input_tokens")
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if not all(
        isinstance(value, int)
        for value in (uncached_tokens, cached_tokens, input_tokens, output_tokens)
    ):
        return
    cache_write_tokens = pricing.get("cache_write_tokens")
    if cache_write_tokens is not None and (
        not isinstance(cache_write_tokens, int)
        or isinstance(cache_write_tokens, bool)
        or cache_write_tokens < 0
        or cache_write_tokens > uncached_tokens
    ):
        issues.append({"code": "C021", "message": f"{run_id} cache-write tokens 非法"})
        return
    if cache_write_tokens not in (None, 0) and cache_write_rate is None:
        issues.append({"code": "C021", "message": f"{run_id} cache-write tokens 缺少单价"})
        return

    regular_uncached_tokens = (
        uncached_tokens - cache_write_tokens
        if cache_write_tokens is not None
        else uncached_tokens
    )
    uncached_amount = regular_uncached_tokens * rates["uncached_input"] / 1_000_000
    cached_amount = cached_tokens * rates["cached_input"] / 1_000_000
    output_amount = output_tokens * rates["output"] / 1_000_000
    cache_write_amount = (
        cache_write_tokens * cache_write_rate / 1_000_000
        if cache_write_tokens is not None and cache_write_rate is not None
        else None
    )
    api_equivalent = uncached_amount + cached_amount + output_amount
    if cache_write_amount is not None:
        api_equivalent += cache_write_amount
    if cache_write_tokens is None and cache_write_rate is not None:
        cache_write_upper_bound = (
            uncached_tokens * cache_write_rate
            + cached_tokens * rates["cached_input"]
            + output_tokens * rates["output"]
        ) / 1_000_000
    else:
        cache_write_upper_bound = api_equivalent
    no_cache = (
        input_tokens * rates["uncached_input"] + output_tokens * rates["output"]
    ) / 1_000_000
    cache_savings = no_cache - api_equivalent
    cache_savings_pct = round(cache_savings / no_cache * 100, 2) if no_cache else 0.0
    expected = {
        "uncached_input": uncached_amount,
        "cached_input": cached_amount,
        "output": output_amount,
        "api_equivalent": api_equivalent,
        "cache_write_upper_bound": cache_write_upper_bound,
        "no_cache_api_equivalent": no_cache,
        "cache_savings": cache_savings,
        "cache_savings_pct": cache_savings_pct,
    }
    if cache_write_amount is not None:
        expected["cache_write_input"] = cache_write_amount
    for field, expected_value in expected.items():
        if not close(calculation.get(field), expected_value):
            issues.append(
                {
                    "code": "C022",
                    "message": f"{run_id} cost.calculation.{field} 公式错误",
                }
            )

    quota_multiplier = billing.get("quota_multiplier")
    quota_equivalent = billing.get("quota_equivalent")
    if quota_multiplier is None:
        if quota_equivalent is not None:
            issues.append({"code": "C023", "message": f"{run_id} 套餐额度金额缺少倍数"})
    elif not is_number(quota_multiplier) or quota_multiplier < 0:
        issues.append({"code": "C023", "message": f"{run_id} 套餐额度倍数非法"})
    elif not close(quota_equivalent, api_equivalent * quota_multiplier):
        issues.append({"code": "C023", "message": f"{run_id} 套餐额度金额公式错误"})
    actual_cash = billing.get("actual_cash_increment")
    if actual_cash is not None and (not is_number(actual_cash) or actual_cash < 0):
        issues.append({"code": "C024", "message": f"{run_id} 实际现金增量非法"})


def validate(
    path: Path,
    report: Path | None,
    acceptance_report: Path | None = None,
) -> list[dict[str, str]]:
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
        validate_run_cost(run_id, run, issues)

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
                    if metric == "api_equivalent_cost":
                        continue
                    expected = percent_delta(values.get("current"), values.get("baseline"))
                    if values.get("delta_pct") != expected:
                        issues.append(
                            {"code": "C009", "message": f"{run_id}.{metric} delta 公式错误"}
                        )
            amount = comparison.get("cost")
            if not isinstance(amount, dict):
                issues.append({"code": "C025", "message": f"{run_id} 缺少金额比较"})
            elif amount.get("comparable"):
                baseline_amount = amount.get("baseline")
                current_amount = amount.get("current")
                if (
                    not is_number(baseline_amount)
                    or not is_number(current_amount)
                    or not close(amount.get("delta"), current_amount - baseline_amount)
                    or amount.get("delta_pct")
                    != percent_delta(current_amount, baseline_amount)
                ):
                    issues.append({"code": "C026", "message": f"{run_id} 金额 delta 公式错误"})

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
            if "## 金额" not in text or "API 等价成本" not in text:
                issues.append({"code": "C027", "message": "报告缺少金额章节"})
            for run_id in by_id:
                if run_id not in text and by_id[run_id].get("label") not in text:
                    issues.append({"code": "C013", "message": f"报告未包含 run: {run_id}"})
    if acceptance_report is not None:
        if not acceptance_report.is_file():
            issues.append(
                {
                    "code": "C028",
                    "message": f"验收报告不存在: {acceptance_report}",
                }
            )
        else:
            acceptance_text = acceptance_report.read_text(encoding="utf-8")
            required = (
                "## 金额",
                "API 等价成本",
                "实际现金增量",
                "套餐额度",
                "价格",
            )
            missing = [field for field in required if field not in acceptance_text]
            if missing:
                issues.append(
                    {
                        "code": "C029",
                        "message": f"验收报告金额字段缺失: {', '.join(missing)}",
                    }
                )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("comparison", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--acceptance-report", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    issues = validate(args.comparison, args.report, args.acceptance_report)
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
