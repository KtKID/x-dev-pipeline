#!/usr/bin/env python3
"""Normalize supported run telemetry and grading into benchmark-run.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from benchmark_common import BenchmarkError, read_json, require_non_negative_int, write_json


def nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def normalize_usage(metrics: dict[str, Any]) -> tuple[dict[str, Any], str]:
    candidate: dict[str, Any] | None = None
    source_kind = "unknown"
    if isinstance(nested(metrics, "usage", "agent_tree_all_in"), dict):
        candidate = nested(metrics, "usage", "agent_tree_all_in")
        source_kind = "full-pipeline-metrics"
    elif isinstance(nested(metrics, "usage", "agent_tree"), dict):
        candidate = nested(metrics, "usage", "agent_tree")
        source_kind = "token-analysis-agent-tree"
    elif isinstance(nested(metrics, "usage", "full_session"), dict):
        candidate = nested(metrics, "usage", "full_session")
        source_kind = "token-analysis-full-session"
    elif isinstance(metrics.get("tokens"), dict):
        raw = metrics["tokens"]
        candidate = {
            "input_tokens": raw.get("input"),
            "cached_input_tokens": raw.get("cached_input"),
            "output_tokens": raw.get("output"),
            "reasoning_output_tokens": raw.get("reasoning_output"),
            "total_tokens": raw.get("total"),
        }
        source_kind = "measurement"
    elif "input_tokens" in metrics and ("total_tokens" in metrics or "input_plus_output_tokens" in metrics):
        candidate = metrics
        source_kind = "flat-telemetry"
    if not isinstance(candidate, dict):
        raise BenchmarkError("无法识别 metrics Token schema")

    input_tokens = require_non_negative_int(candidate.get("input_tokens"), "input_tokens")
    cached_input_tokens = require_non_negative_int(
        candidate.get("cached_input_tokens", 0),
        "cached_input_tokens",
    )
    output_tokens = require_non_negative_int(candidate.get("output_tokens"), "output_tokens")
    reasoning_output_tokens = require_non_negative_int(
        candidate.get("reasoning_output_tokens", 0),
        "reasoning_output_tokens",
    )
    total_tokens = candidate.get("total_tokens", candidate.get("input_plus_output_tokens"))
    total_tokens = require_non_negative_int(total_tokens, "total_tokens")
    if cached_input_tokens > input_tokens:
        raise BenchmarkError("cached_input_tokens 不能大于 input_tokens")
    if reasoning_output_tokens > output_tokens:
        raise BenchmarkError("reasoning_output_tokens 不能大于 output_tokens")
    if input_tokens + output_tokens != total_tokens:
        raise BenchmarkError(
            f"Token 加总不一致: input={input_tokens}, output={output_tokens}, total={total_tokens}"
        )
    uncached = input_tokens - cached_input_tokens
    return (
        {
            "convention": "cached_input_is_subset_of_input",
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "uncached_input_tokens": uncached,
            "output_tokens": output_tokens,
            "reasoning_output_tokens": reasoning_output_tokens,
            "total_tokens": total_tokens,
            "effective_tokens": uncached + output_tokens,
            "cached_share_of_input_pct": round(cached_input_tokens / input_tokens * 100, 2)
            if input_tokens
            else 0.0,
        },
        source_kind,
    )


def require_non_negative_number(value: object, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise BenchmarkError(f"{field} 必须是非负数字")
    return float(value)


def optional_non_negative_number(value: object, field: str) -> float | None:
    if value is None:
        return None
    return require_non_negative_number(value, field)


def round_amount(value: float) -> float:
    return round(value, 12)


def unknown_cost(reason: str) -> dict[str, Any]:
    return {
        "status": "unknown",
        "currency": None,
        "pricing": None,
        "calculation": {
            "uncached_input": None,
            "cached_input": None,
            "cache_write_input": None,
            "output": None,
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


def normalize_cost(
    usage: dict[str, Any],
    pricing: dict[str, Any] | None,
    run_model: object,
) -> dict[str, Any]:
    if pricing is None:
        return unknown_cost("pricing_not_provided")

    currency = pricing.get("currency")
    pricing_model = pricing.get("model")
    source_url = pricing.get("source_url")
    queried_at = pricing.get("queried_at")
    if not isinstance(currency, str) or not currency.strip():
        raise BenchmarkError("pricing.currency 必须是非空字符串")
    if not isinstance(pricing_model, str) or not pricing_model.strip():
        raise BenchmarkError("pricing.model 必须是非空字符串")
    if isinstance(run_model, str) and run_model and pricing_model != run_model:
        raise BenchmarkError(
            f"pricing.model 与 run model 不一致: pricing={pricing_model}, run={run_model}"
        )
    if not isinstance(source_url, str) or not source_url.strip():
        raise BenchmarkError("pricing.source_url 必须是非空字符串")
    if not isinstance(queried_at, str) or not queried_at.strip():
        raise BenchmarkError("pricing.queried_at 必须是非空字符串")

    rates = pricing.get("rates_per_million_tokens")
    if not isinstance(rates, dict):
        raise BenchmarkError("pricing.rates_per_million_tokens 必须是 object")
    uncached_rate = require_non_negative_number(
        rates.get("uncached_input"),
        "pricing.rates_per_million_tokens.uncached_input",
    )
    cached_rate = require_non_negative_number(
        rates.get("cached_input"),
        "pricing.rates_per_million_tokens.cached_input",
    )
    output_rate = require_non_negative_number(
        rates.get("output"),
        "pricing.rates_per_million_tokens.output",
    )
    cache_write_rate = optional_non_negative_number(
        rates.get("cache_write_input"),
        "pricing.rates_per_million_tokens.cache_write_input",
    )

    telemetry = pricing.get("telemetry")
    if telemetry is None:
        telemetry = {}
    if not isinstance(telemetry, dict):
        raise BenchmarkError("pricing.telemetry 必须是 object")
    cache_write_tokens_value = telemetry.get("cache_write_tokens")
    cache_write_tokens = (
        require_non_negative_int(cache_write_tokens_value, "pricing.telemetry.cache_write_tokens")
        if cache_write_tokens_value is not None
        else None
    )
    uncached_tokens = usage["uncached_input_tokens"]
    if cache_write_tokens is not None and cache_write_tokens > uncached_tokens:
        raise BenchmarkError("pricing.telemetry.cache_write_tokens 不能大于 uncached input")
    if cache_write_tokens not in (None, 0) and cache_write_rate is None:
        raise BenchmarkError("存在 cache_write_tokens 时必须提供 cache_write_input 单价")

    regular_uncached_tokens = (
        uncached_tokens - cache_write_tokens
        if cache_write_tokens is not None
        else uncached_tokens
    )
    uncached_amount = regular_uncached_tokens * uncached_rate / 1_000_000
    cached_amount = usage["cached_input_tokens"] * cached_rate / 1_000_000
    output_amount = usage["output_tokens"] * output_rate / 1_000_000
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
            + usage["cached_input_tokens"] * cached_rate
            + usage["output_tokens"] * output_rate
        ) / 1_000_000
    else:
        cache_write_upper_bound = api_equivalent

    no_cache = (
        usage["input_tokens"] * uncached_rate + usage["output_tokens"] * output_rate
    ) / 1_000_000
    cache_savings = no_cache - api_equivalent
    cache_savings_pct = round(cache_savings / no_cache * 100, 2) if no_cache else 0.0

    billing_input = pricing.get("billing")
    if billing_input is None:
        billing_input = {}
    if not isinstance(billing_input, dict):
        raise BenchmarkError("pricing.billing 必须是 object")
    billing_mode = billing_input.get("mode", "unknown")
    if not isinstance(billing_mode, str) or not billing_mode:
        raise BenchmarkError("pricing.billing.mode 必须是非空字符串")
    actual_cash = optional_non_negative_number(
        billing_input.get("actual_cash_increment"),
        "pricing.billing.actual_cash_increment",
    )
    quota_multiplier = optional_non_negative_number(
        billing_input.get("quota_multiplier"),
        "pricing.billing.quota_multiplier",
    )
    quota_equivalent = (
        round_amount(api_equivalent * quota_multiplier)
        if quota_multiplier is not None
        else None
    )
    billing_note = billing_input.get("note")
    if billing_note is not None and not isinstance(billing_note, str):
        raise BenchmarkError("pricing.billing.note 必须是字符串")

    return {
        "status": "priced",
        "currency": currency,
        "pricing": {
            "model": pricing_model,
            "source_url": source_url,
            "queried_at": queried_at,
            "rates_per_million_tokens": {
                "uncached_input": uncached_rate,
                "cached_input": cached_rate,
                "cache_write_input": cache_write_rate,
                "output": output_rate,
            },
            "cached_input_storage": pricing.get("cached_input_storage"),
            "cache_write_tokens": cache_write_tokens,
        },
        "calculation": {
            "uncached_input": round_amount(uncached_amount),
            "cached_input": round_amount(cached_amount),
            "cache_write_input": round_amount(cache_write_amount)
            if cache_write_amount is not None
            else None,
            "output": round_amount(output_amount),
            "api_equivalent": round_amount(api_equivalent),
            "cache_write_upper_bound": round_amount(cache_write_upper_bound),
            "no_cache_api_equivalent": round_amount(no_cache),
            "cache_savings": round_amount(cache_savings),
            "cache_savings_pct": cache_savings_pct,
        },
        "billing": {
            "mode": billing_mode,
            "actual_cash_increment": round_amount(actual_cash)
            if actual_cash is not None
            else None,
            "quota_multiplier": quota_multiplier,
            "quota_equivalent": quota_equivalent,
            "note": billing_note,
        },
        "unknown_reason": None,
    }


def normalize_duration(metrics: dict[str, Any]) -> dict[str, float | None]:
    duration = metrics.get("duration")
    if isinstance(duration, dict):
        main = duration.get("main_active_seconds")
        if main is None and duration.get("main_active_total_ms") is not None:
            main = duration["main_active_total_ms"] / 1000
        executor = duration.get("executor_time_sum_seconds")
        if executor is None and duration.get("executor_time_sum_ms") is not None:
            executor = duration["executor_time_sum_ms"] / 1000
        reviewer = duration.get("qa_reviewer_nested_seconds")
        if reviewer is None and duration.get("q3_reviewer_nested_ms") is not None:
            reviewer = duration["q3_reviewer_nested_ms"] / 1000
        return {
            "main_active_seconds": float(main) if main is not None else None,
            "nested_reviewer_seconds": float(reviewer) if reviewer is not None else None,
            "executor_time_sum_seconds": float(executor) if executor is not None else None,
        }
    if metrics.get("duration_ms") is not None:
        seconds = float(metrics["duration_ms"]) / 1000
        return {
            "main_active_seconds": seconds,
            "nested_reviewer_seconds": None,
            "executor_time_sum_seconds": seconds,
        }
    if metrics.get("session_wall_seconds") is not None:
        seconds = float(metrics["session_wall_seconds"])
        return {
            "main_active_seconds": seconds,
            "nested_reviewer_seconds": None,
            "executor_time_sum_seconds": seconds,
        }
    return {
        "main_active_seconds": None,
        "nested_reviewer_seconds": None,
        "executor_time_sum_seconds": None,
    }


def normalize_calls(metrics: dict[str, Any], metadata: dict[str, Any] | None) -> dict[str, int | None]:
    tools = nested(metrics, "usage", "agent_tree_all_in", "tool_calls")
    llm = nested(metrics, "usage", "agent_tree_all_in", "llm_calls")
    if tools is None:
        tools = nested(metrics, "tool_calls", "agent_tree_total")
    if tools is None and metadata:
        tools = nested(metadata, "execution", "tool_calls")
    if llm is None and metadata:
        llm = nested(metadata, "execution", "llm_calls")
    failures = nested(metadata or {}, "execution", "failed_commands")
    return {
        "tool_calls": int(tools) if tools is not None else None,
        "llm_calls": int(llm) if llm is not None else None,
        "failed_commands": int(failures) if failures is not None else None,
    }


def normalize_score(path: Path | None, kind: str) -> dict[str, Any] | None:
    if path is None:
        return None
    grading = read_json(path)
    summary = grading.get("summary") if isinstance(grading.get("summary"), dict) else {}
    score = grading.get("quality_score", grading.get("score", summary.get("score")))
    passed = grading.get("passed", summary.get("passed"))
    total = grading.get("total", summary.get("total"))
    if score is None:
        raise BenchmarkError(f"{kind} grading 缺少 score: {path}")
    return {
        "score": float(score),
        "passed": int(passed) if passed is not None else None,
        "total": int(total) if total is not None else None,
        "critical_gate_passed": grading.get("critical_gate_passed"),
        "rubric_version": grading.get("rubric_version"),
        "source": str(path.resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--iteration")
    parser.add_argument("--scope", required=True, choices=("full_pipeline", "spec_risk_only"))
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--timing", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument(
        "--pricing",
        type=Path,
        help="本 run 的冻结价格与账单口径 JSON；缺省时金额显式记录为 unknown",
    )
    parser.add_argument("--full-grading", type=Path)
    parser.add_argument("--spec-risk-grading", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        metrics = read_json(args.metrics)
        timing = read_json(args.timing) if args.timing else metrics
        metadata = read_json(args.metadata) if args.metadata else None
        usage, source_kind = normalize_usage(metrics)
        pricing = read_json(args.pricing) if args.pricing else None
        model = (metadata or {}).get("model", nested(metrics, "run", "model"))
        if model is None and pricing is not None:
            model = pricing.get("model")
        phases = metrics.get("phases")
        if not isinstance(phases, list):
            phases = nested(metrics, "phase_allocation", "phases")
        if not isinstance(phases, list):
            phases = []
        result = {
            "schema_version": 2,
            "run_id": args.run_id,
            "label": args.label,
            "iteration": args.iteration,
            "scope": args.scope,
            "model": model,
            "reasoning_effort": (metadata or {}).get(
                "reasoning_effort",
                nested(metrics, "run", "reasoning_effort"),
            ),
            "usage": usage,
            "cost": normalize_cost(usage, pricing, model),
            "duration": normalize_duration(timing),
            "calls": normalize_calls(metrics, metadata),
            "scores": {
                "full": normalize_score(args.full_grading, "full"),
                "spec_risk": normalize_score(args.spec_risk_grading, "spec-risk"),
            },
            "phases": phases,
            "measurement": {
                "metrics_schema": source_kind,
                "metrics_source": str(args.metrics.resolve()),
                "timing_source": str(args.timing.resolve()) if args.timing else str(args.metrics.resolve()),
                "metadata_source": str(args.metadata.resolve()) if args.metadata else None,
                "pricing_source": str(args.pricing.resolve()) if args.pricing else None,
            },
        }
        write_json(args.output, result)
    except (BenchmarkError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"valid": True, "output": str(args.output.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
