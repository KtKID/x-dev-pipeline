#!/usr/bin/env python3
"""Prepare, grade, and aggregate the three-arm instruction-form eval."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import shutil
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO_ROOT / "evals/instruction-form-abc.json"
sys.path.insert(0, str(REPO_ROOT))

from tools import metrics as metrics_module  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def repo_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def prepare(workspace: Path) -> None:
    matrix = load_json(MATRIX_PATH)
    prompt_path = REPO_ROOT / matrix["common"]["prompt"]
    cases_path = REPO_ROOT / matrix["common"]["cases"]
    prompt = prompt_path.read_text(encoding="utf-8")
    cases_document = load_json(cases_path)
    cases_by_id = {case["case_id"]: case for case in cases_document["cases"]}
    current_sha = repo_sha()
    eval_root = workspace / "eval-8-instruction-form-adherence"

    for arm_name, arm in matrix["arms"].items():
        rules_path = REPO_ROOT / arm["rules"]
        rules = rules_path.read_text(encoding="utf-8")
        for repetition, order in matrix["paired_orders"].items():
            run_dir = eval_root / arm_name / f"run-{repetition}"
            inputs_dir = run_dir / "inputs"
            outputs_dir = run_dir / "outputs"
            inputs_dir.mkdir(parents=True, exist_ok=True)
            outputs_dir.mkdir(parents=True, exist_ok=True)

            ordered_cases = {
                "schema_version": cases_document["schema_version"],
                "cases": [cases_by_id[case_id] for case_id in order],
            }
            cases_text = json.dumps(ordered_cases, ensure_ascii=False, indent=2) + "\n"
            (inputs_dir / "prompt.md").write_text(prompt, encoding="utf-8")
            (inputs_dir / "rules.md").write_text(rules, encoding="utf-8")
            (inputs_dir / "cases.json").write_text(cases_text, encoding="utf-8")

            prompt_for_viewer = (
                prompt
                + "\n\n本次配置只读取 run 私有的 `inputs/rules.md` 与 "
                "`inputs/cases.json`；规则内容对 grader 隐藏。"
            )
            write_json(
                run_dir / "eval_metadata.json",
                {
                    "eval_id": matrix["eval_id"],
                    "eval_name": matrix["eval_name"],
                    "configuration": arm_name,
                    "configuration_label": arm["label"],
                    "run_number": int(repetition),
                    "prompt": prompt_for_viewer,
                    "model": "gpt-5.6-sol",
                    "repo_sha": current_sha,
                    "executor_inputs": ["inputs/prompt.md", "inputs/rules.md", "inputs/cases.json"],
                    "grader_only_inputs": [
                        "evals/answers/instruction-form-adherence/expected.json",
                        "evals/answers/instruction-form-adherence/rubric.md",
                    ],
                    "rubric_exposed": False,
                    "assertions": [
                        f"{case_id}: result 与隐藏期望完全一致" for case_id in order
                    ],
                },
            )
            combined = prompt + "\n" + rules + "\n" + cases_text
            write_json(
                run_dir / "run_manifest.json",
                {
                    "schema_version": 1,
                    "eval_id": matrix["eval_id"],
                    "configuration": arm_name,
                    "configuration_label": arm["label"],
                    "run_number": int(repetition),
                    "repo_sha": current_sha,
                    "input_sha256": sha256_text(combined),
                    "prompt_sha256": sha256_text(prompt),
                    "rules_sha256": sha256_text(rules),
                    "cases_sha256": sha256_text(cases_text),
                    "instruction_chars": len(rules),
                    "total_input_chars": len(combined),
                    "case_order": order,
                    "grader_visibility": "expected and rubric excluded from executor",
                },
            )

    write_json(
        eval_root / "eval_metadata.json",
        {
            "eval_id": matrix["eval_id"],
            "eval_name": matrix["eval_name"],
            "prompt": prompt,
            "assertions": [
                f"{case_id}: result 与隐藏期望完全一致"
                for case_id in matrix["paired_orders"]["1"]
            ],
        },
    )


def grade(run_dir: Path) -> None:
    matrix = load_json(MATRIX_PATH)
    expected = load_json(REPO_ROOT / matrix["common"]["expected"])
    output_path = run_dir / "outputs/decisions.json"
    parse_error: str | None = None
    duplicate_ids: set[str] = set()
    actual_by_id: dict[str, Any] = {}

    try:
        output = load_json(output_path)
        decisions = output.get("decisions")
        if not isinstance(decisions, list):
            raise ValueError("top-level decisions must be a list")
        for item in decisions:
            if not isinstance(item, dict):
                raise ValueError("each decision must be an object")
            case_id = item.get("case_id")
            if not isinstance(case_id, str):
                raise ValueError("each decision needs a string case_id")
            if case_id in actual_by_id:
                duplicate_ids.add(case_id)
            actual_by_id[case_id] = item.get("result")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parse_error = str(exc)

    ordered_cases = load_json(run_dir / "inputs/cases.json")["cases"]
    expectations: list[dict[str, Any]] = []
    for case in ordered_cases:
        case_id = case["case_id"]
        expected_result = expected[case_id]
        actual_result = actual_by_id.get(case_id)
        passed = (
            parse_error is None
            and case_id not in duplicate_ids
            and isinstance(actual_result, dict)
            and actual_result == expected_result
        )
        if parse_error is not None:
            evidence = f"decisions.json 无法解析：{parse_error}"
        elif case_id in duplicate_ids:
            evidence = f"case_id {case_id} 重复出现"
        elif actual_result is None:
            evidence = f"缺少 case_id {case_id}"
        elif passed:
            evidence = f"精确匹配：{json.dumps(actual_result, ensure_ascii=False, sort_keys=True)}"
        else:
            evidence = (
                "期望 "
                + json.dumps(expected_result, ensure_ascii=False, sort_keys=True)
                + "；实际 "
                + json.dumps(actual_result, ensure_ascii=False, sort_keys=True)
            )
        expectations.append(
            {
                "text": f"{case_id}: result 与隐藏期望完全一致",
                "passed": passed,
                "evidence": evidence,
            }
        )

    passed_count = sum(1 for item in expectations if item["passed"])
    output_chars = output_path.stat().st_size if output_path.exists() else 0
    observed_execution = {
        "tool_calls": {},
        "total_tool_calls": 0,
        "errors_encountered": 1 if parse_error else 0,
    }
    measurement_path = run_dir / "measurement.json"
    if measurement_path.exists():
        measurement = load_json(measurement_path)
        observed_execution.update(measurement.get("execution_metrics", {}))
    write_json(
        run_dir / "grading.json",
        {
            "expectations": expectations,
            "summary": {
                "passed": passed_count,
                "failed": len(expectations) - passed_count,
                "total": len(expectations),
                "pass_rate": passed_count / len(expectations),
            },
            "execution_metrics": {
                **observed_execution,
                "total_steps": 1,
                "output_chars": output_chars,
                "transcript_chars": 0,
            },
            "claims": [],
            "user_notes_summary": {
                "uncertainties": [],
                "needs_review": [],
                "workarounds": [],
            },
            "eval_feedback": {
                "suggestions": [],
                "overall": "精确状态断言由确定性 grader 校验。",
            },
        },
    )


def collect(run_dir: Path, session_path: Path) -> None:
    metadata = load_json(run_dir / "eval_metadata.json")
    grading = load_json(run_dir / "grading.json")
    source = metrics_module.parse_codex_session_source(
        session_path,
        metadata["grader_only_inputs"],
    )
    quality, _expectations = metrics_module.grading_quality(grading)
    execution_metrics = rollout_execution_metrics(session_path)
    if source["repo_sha"] != metadata["repo_sha"]:
        raise ValueError(
            f"repo SHA mismatch: metadata={metadata['repo_sha']} session={source['repo_sha']}"
        )
    measurement = {
        "schema_version": 1,
        "eval_id": metadata["eval_id"],
        "eval_name": metadata["eval_name"],
        "configuration": metadata["configuration"],
        "configuration_label": metadata["configuration_label"],
        "run_number": metadata["run_number"],
        "source": {
            **source["source"],
            "rollout_path": str(session_path.resolve()),
        },
        "model": source["model"],
        "repo_sha": source["repo_sha"],
        "prompt_sha256": metrics_module.prompt_hash(metadata["prompt"]),
        "started_at": source["started_at"],
        "ended_at": source["ended_at"],
        "duration_ms": source["duration_ms"],
        "tokens": source["tokens"],
        "quality": quality,
        "execution_metrics": execution_metrics,
    }
    write_json(run_dir / "measurement.json", measurement)
    grading["execution_metrics"] = {
        **grading.get("execution_metrics", {}),
        **execution_metrics,
    }
    write_json(run_dir / "grading.json", grading)


def rollout_execution_metrics(session_path: Path) -> dict[str, Any]:
    tool_calls: Counter[str] = Counter()
    for raw_line in session_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        row = json.loads(raw_line)
        if row.get("type") != "response_item":
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") not in {"function_call", "custom_tool_call"}:
            continue
        name = payload.get("name")
        tool_calls[str(name or "unknown")] += 1
    return {
        "tool_calls": dict(sorted(tool_calls.items())),
        "total_tool_calls": sum(tool_calls.values()),
        "errors_encountered": 0,
    }


def stat(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "stddev": statistics.pstdev(values),
        "min": min(values),
        "max": max(values),
    }


def aggregate(workspace: Path) -> None:
    matrix = load_json(MATRIX_PATH)
    eval_root = workspace / "eval-8-instruction-form-adherence"
    runs: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    case_frequencies: dict[str, dict[str, Any]] = {}

    for arm_name, arm in matrix["arms"].items():
        arm_runs: list[dict[str, Any]] = []
        case_passes: dict[str, list[bool]] = {}
        for repetition in sorted(matrix["paired_orders"], key=int):
            run_dir = eval_root / arm_name / f"run-{repetition}"
            grading = load_json(run_dir / "grading.json")
            measurement = load_json(run_dir / "measurement.json")
            result = {
                "pass_rate": grading["summary"]["pass_rate"],
                "passed": grading["summary"]["passed"],
                "failed": grading["summary"]["failed"],
                "total": grading["summary"]["total"],
                "time_seconds": measurement["duration_ms"] / 1000,
                "tokens": measurement["tokens"]["total"],
                "tool_calls": measurement["execution_metrics"]["total_tool_calls"],
                "errors": measurement["execution_metrics"]["errors_encountered"],
            }
            run = {
                "eval_id": matrix["eval_id"],
                "eval_name": matrix["eval_name"],
                "configuration": arm_name,
                "configuration_label": arm["label"],
                "run_number": int(repetition),
                "model": measurement["model"],
                "result": result,
                "expectations": grading["expectations"],
                "notes": [],
                "token_buckets": measurement["tokens"],
            }
            runs.append(run)
            arm_runs.append(run)
            for expectation in grading["expectations"]:
                case_id = expectation["text"].split(":", 1)[0]
                case_passes.setdefault(case_id, []).append(expectation["passed"])

        pass_rates = [run["result"]["pass_rate"] for run in arm_runs]
        times = [run["result"]["time_seconds"] for run in arm_runs]
        tokens = [run["result"]["tokens"] for run in arm_runs]
        tool_calls = [run["result"]["tool_calls"] for run in arm_runs]
        summaries[arm_name] = {
            "label": arm["label"],
            "pass_rate": stat(pass_rates),
            "all_10_pass_rate": sum(rate == 1.0 for rate in pass_rates) / len(pass_rates),
            "time_seconds": stat(times),
            "tokens": stat(tokens),
            "tool_calls": stat(tool_calls),
            "instruction_chars": load_json(
                eval_root / arm_name / "run-1/run_manifest.json"
            )["instruction_chars"],
        }
        case_frequencies[arm_name] = {
            case_id: {
                "passed": sum(values),
                "total": len(values),
                "pass_rate": sum(values) / len(values),
            }
            for case_id, values in sorted(case_passes.items())
        }

    arm_names = list(matrix["arms"])
    pairwise: dict[str, Any] = {}
    for left in arm_names:
        for right in arm_names:
            if left >= right:
                continue
            left_summary = summaries[left]
            right_summary = summaries[right]
            pairwise[f"{left}_minus_{right}"] = {
                "pass_rate_points": 100
                * (left_summary["pass_rate"]["mean"] - right_summary["pass_rate"]["mean"]),
                "tokens": left_summary["tokens"]["mean"] - right_summary["tokens"]["mean"],
                "tokens_ratio": left_summary["tokens"]["mean"] / right_summary["tokens"]["mean"] - 1,
                "time_seconds": left_summary["time_seconds"]["mean"]
                - right_summary["time_seconds"]["mean"],
                "time_ratio": left_summary["time_seconds"]["mean"]
                / right_summary["time_seconds"]["mean"]
                - 1,
            }

    viewer_summary: dict[str, Any] = {
        arm_name: {
            "pass_rate": summaries[arm_name]["pass_rate"],
            "time_seconds": summaries[arm_name]["time_seconds"],
            "tokens": summaries[arm_name]["tokens"],
        }
        for arm_name in arm_names
    }
    first, second = arm_names[0], arm_names[1]
    viewer_summary["delta"] = {
        "pass_rate": f"{summaries[first]['pass_rate']['mean'] - summaries[second]['pass_rate']['mean']:+.2f}",
        "time_seconds": f"{summaries[first]['time_seconds']['mean'] - summaries[second]['time_seconds']['mean']:+.1f}",
        "tokens": f"{summaries[first]['tokens']['mean'] - summaries[second]['tokens']['mean']:+.0f}",
    }

    notes = build_notes(summaries, case_frequencies, pairwise)
    benchmark = {
        "metadata": {
            "skill_name": "x-spec2 instruction form",
            "skill_path": "skills/x-spec2",
            "executor_model": runs[0]["model"],
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "evals_run": [matrix["eval_id"]],
            "case_count": 10,
            "runs_per_configuration": matrix["repetitions_per_configuration"],
            "observations_per_configuration": 30,
            "variance_semantics": "three independent executor rollouts per configuration",
        },
        "runs": runs,
        "run_summary": viewer_summary,
        "three_arm_summary": summaries,
        "pairwise_deltas": pairwise,
        "case_frequencies": case_frequencies,
        "notes": notes,
    }
    write_json(workspace / "benchmark.json", benchmark)
    write_json(workspace / "benchmark-analysis.json", notes)
    write_markdown(workspace / "benchmark.md", summaries, pairwise, case_frequencies, notes)


def build_notes(
    summaries: dict[str, Any],
    case_frequencies: dict[str, Any],
    pairwise: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    for arm_name, summary in summaries.items():
        notes.append(
            f"{arm_name}: exact-match {summary['pass_rate']['mean']:.1%} ± "
            f"{summary['pass_rate']['stddev']:.1%}, all-10 run rate "
            f"{summary['all_10_pass_rate']:.1%}, mean {summary['tokens']['mean']:.0f} tokens, "
            f"mean {summary['time_seconds']['mean']:.1f}s, mean "
            f"{summary['tool_calls']['mean']:.2f} tool calls."
        )
    for arm_name, cases in case_frequencies.items():
        variable = [case_id for case_id, value in cases.items() if 0 < value["passed"] < value["total"]]
        failed = [case_id for case_id, value in cases.items() if value["passed"] == 0]
        if variable:
            notes.append(f"{arm_name} 的随机波动 case: {', '.join(variable)}。")
        if failed:
            notes.append(f"{arm_name} 三次均失败的 case: {', '.join(failed)}。")
    for pair, delta in pairwise.items():
        notes.append(
            f"{pair}: quality {delta['pass_rate_points']:+.1f} points, "
            f"tokens {delta['tokens_ratio']:+.1%}, time {delta['time_ratio']:+.1%}."
        )
    return notes


def write_markdown(
    path: Path,
    summaries: dict[str, Any],
    pairwise: dict[str, Any],
    case_frequencies: dict[str, Any],
    notes: list[str],
) -> None:
    lines = [
        "# Instruction Form A/B/C Benchmark",
        "",
        "## Three-arm summary",
        "",
        "| Configuration | Exact match | All-10 runs | Tokens | Time | Tool calls | Instruction chars |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm_name, summary in summaries.items():
        lines.append(
            f"| {arm_name} | {summary['pass_rate']['mean']:.1%} ± "
            f"{summary['pass_rate']['stddev']:.1%} | {summary['all_10_pass_rate']:.1%} | "
            f"{summary['tokens']['mean']:.0f} ± {summary['tokens']['stddev']:.0f} | "
            f"{summary['time_seconds']['mean']:.1f}s ± {summary['time_seconds']['stddev']:.1f}s | "
            f"{summary['tool_calls']['mean']:.2f} ± {summary['tool_calls']['stddev']:.2f} | "
            f"{summary['instruction_chars']} |"
        )
    lines.extend(
        [
            "",
            "## Pairwise deltas",
            "",
            "| Pair | Quality points | Token delta | Token ratio | Time delta | Time ratio |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for pair, delta in pairwise.items():
        lines.append(
            f"| {pair} | {delta['pass_rate_points']:+.1f} | {delta['tokens']:+.0f} | "
            f"{delta['tokens_ratio']:+.1%} | {delta['time_seconds']:+.1f}s | "
            f"{delta['time_ratio']:+.1%} |"
        )
    lines.extend(["", "## Per-case pass frequency", ""])
    arm_names = list(summaries)
    lines.append("| Case | " + " | ".join(arm_names) + " |")
    lines.append("|---|" + "---:|" * len(arm_names))
    case_ids = list(next(iter(case_frequencies.values())).keys())
    for case_id in case_ids:
        values = [
            f"{case_frequencies[arm][case_id]['passed']}/{case_frequencies[arm][case_id]['total']}"
            for arm in arm_names
        ]
        lines.append(f"| {case_id} | " + " | ".join(values) + " |")
    lines.extend(["", "## Analyzer notes", ""])
    lines.extend(f"- {note}" for note in notes)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--workspace", type=Path, required=True)
    grade_parser = subparsers.add_parser("grade")
    grade_parser.add_argument("--run-dir", type=Path, required=True)
    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--run-dir", type=Path, required=True)
    collect_parser.add_argument("--session", type=Path, required=True)
    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("--workspace", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "prepare":
        prepare(args.workspace.resolve())
    elif args.command == "grade":
        grade(args.run_dir.resolve())
    elif args.command == "collect":
        collect(args.run_dir.resolve(), args.session.resolve())
    elif args.command == "aggregate":
        aggregate(args.workspace.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
