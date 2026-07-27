#!/usr/bin/env python3
"""Validate a pipeline-eval-report run directory without mutating it."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "manifest.json",
    "events.jsonl",
    "telemetry.json",
    "grading.json",
    "evaluation-report.md",
)
BOOTSTRAP_REQUIRED_FILES = ("manifest.json", "events.jsonl")
TOKEN_FIELDS = ("input", "output", "reasoning", "cache_read", "cache_write")


def load_json(path: Path, issues: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(f"INVALID_JSON {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        issues.append(f"JSON_OBJECT_REQUIRED {path}")
        return {}
    return value


def load_events(path: Path, issues: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        issues.append(f"EVENTS_READ_FAILED {path}: {exc}")
        return rows
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(f"INVALID_EVENT_JSON {path}:{line_number}: {exc}")
            continue
        if not isinstance(value, dict):
            issues.append(f"EVENT_OBJECT_REQUIRED {path}:{line_number}")
            continue
        rows.append(value)
    return rows


def integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def check_tokens(tokens: Any, label: str, issues: list[str]) -> None:
    if not isinstance(tokens, dict):
        issues.append(f"TOKEN_OBJECT_REQUIRED {label}")
        return
    for field in TOKEN_FIELDS:
        value = tokens.get(field)
        if not integer(value) or value < 0:
            issues.append(f"TOKEN_NONNEGATIVE_INT_REQUIRED {label}.{field}")
    if any(not integer(tokens.get(field)) for field in TOKEN_FIELDS):
        return
    expected_without = sum(tokens[field] for field in TOKEN_FIELDS if field != "cache_read")
    expected_with = expected_without + tokens["cache_read"]
    if tokens.get("total_without_cache_read") != expected_without:
        issues.append(
            f"TOKEN_TOTAL_WITHOUT_CACHE_MISMATCH {label}: "
            f"expected={expected_without} actual={tokens.get('total_without_cache_read')}"
        )
    if tokens.get("total_with_cache") != expected_with:
        issues.append(
            f"TOKEN_TOTAL_WITH_CACHE_MISMATCH {label}: "
            f"expected={expected_with} actual={tokens.get('total_with_cache')}"
        )


def check_grading(grading: dict[str, Any], issues: list[str]) -> None:
    expectations = grading.get("expectations")
    summary = grading.get("summary")
    if isinstance(expectations, list) and isinstance(summary, dict):
        valid = [row for row in expectations if isinstance(row, dict)]
        passed = sum(row.get("passed") is True for row in valid)
        failed = sum(row.get("passed") is False for row in valid)
        if summary.get("passed") != passed:
            issues.append("GRADING_PASSED_MISMATCH")
        if summary.get("failed") != failed:
            issues.append("GRADING_FAILED_MISMATCH")
        if summary.get("total") != len(valid):
            issues.append("GRADING_TOTAL_MISMATCH")
        expected_rate = passed / len(valid) if valid else 0.0
        actual_rate = summary.get("pass_rate")
        if not isinstance(actual_rate, (int, float)) or not math.isclose(
            float(actual_rate), expected_rate, rel_tol=0.0, abs_tol=1e-9
        ):
            issues.append("GRADING_PASS_RATE_MISMATCH")
        for index, row in enumerate(valid, 1):
            if row.get("passed") is False:
                for field in ("evidence", "severity", "reason_code"):
                    if not row.get(field):
                        issues.append(f"FAILED_EXPECTATION_MISSING_{field.upper()} #{index}")

    deductions = grading.get("deductions")
    p0_found = False
    if isinstance(deductions, list):
        for index, row in enumerate(deductions, 1):
            if not isinstance(row, dict):
                issues.append(f"DEDUCTION_OBJECT_REQUIRED #{index}")
                continue
            if row.get("severity") == "P0":
                p0_found = True
            for field in ("severity", "reason_code", "finding", "evidence"):
                if not row.get(field):
                    issues.append(f"DEDUCTION_MISSING_{field.upper()} #{index}")

    if isinstance(expectations, list):
        p0_found = p0_found or any(
            isinstance(row, dict)
            and row.get("passed") is False
            and row.get("severity") == "P0"
            for row in expectations
        )

    decision = grading.get("decision")
    if not isinstance(decision, dict):
        issues.append("GRADING_DECISION_REQUIRED")
        return
    if p0_found and decision.get("quality_gate") != "failed":
        issues.append("P0_REQUIRES_FAILED_QUALITY_GATE")
    if decision.get("quality_gate") == "failed" and decision.get("accepted_delivery") is not False:
        issues.append("FAILED_GATE_REQUIRES_ACCEPTED_FALSE")


def check_knowledge(
    events: list[dict[str, Any]], project_root: Path, run_id: str, issues: list[str]
) -> None:
    for event in events:
        if event.get("type") != "knowledge_recorded":
            continue
        ids: list[str] = []
        if isinstance(event.get("knowledge_id"), str):
            ids.append(event["knowledge_id"])
        if isinstance(event.get("knowledge_ids"), list):
            ids.extend(item for item in event["knowledge_ids"] if isinstance(item, str))
        for knowledge_id in ids:
            path = project_root / "pipeline-data" / "knowledge" / "entries" / f"{knowledge_id}.json"
            if not path.is_file():
                issues.append(f"KNOWLEDGE_FILE_MISSING {path}")
                continue
            entry = load_json(path, issues)
            source = entry.get("source")
            if not isinstance(source, dict) or source.get("pipeline_run_id") != run_id:
                issues.append(f"KNOWLEDGE_RUN_ID_MISMATCH {path}")


def check_event_ledger(
    events: list[dict[str, Any]], run_id: str, issues: list[str]
) -> None:
    event_ids: list[str] = []
    for index, event in enumerate(events, 1):
        if event.get("pipeline_run_id") != run_id:
            issues.append(f"PIPELINE_RUN_ID_MISMATCH event_line={index}")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not re.fullmatch(r"evt-\d+", event_id):
            issues.append(f"EVENT_ID_INVALID line={index}")
        else:
            event_ids.append(event_id)
        for field in ("timestamp", "type"):
            if not event.get(field):
                issues.append(f"EVENT_MISSING_{field.upper()} line={index}")
    if len(event_ids) != len(set(event_ids)):
        issues.append("EVENT_ID_DUPLICATE")
    numbers = [int(event_id.split("-")[1]) for event_id in event_ids]
    if numbers != sorted(numbers):
        issues.append("EVENT_ID_ORDER_INVALID")
    if not events or events[0].get("type") not in {"run_started", "run_recognized"}:
        issues.append("FIRST_EVENT_MUST_ESTABLISH_RUN")


def validate(run_dir: Path, project_root: Path) -> list[str]:
    issues: list[str] = []
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        return [f"REQUIRED_FILE_MISSING {manifest_path}"]
    manifest = load_json(manifest_path, issues)
    bootstrap = manifest.get("storage_profile") == "bootstrap-json-v0"
    required_files = BOOTSTRAP_REQUIRED_FILES if bootstrap else REQUIRED_FILES
    for filename in required_files:
        if not (run_dir / filename).is_file():
            issues.append(f"REQUIRED_FILE_MISSING {run_dir / filename}")
    if issues:
        return issues

    events = load_events(run_dir / "events.jsonl", issues)
    run_id = manifest.get("pipeline_run_id")
    if not isinstance(run_id, str) or not run_id.startswith("prun-"):
        issues.append("MANIFEST_PIPELINE_RUN_ID_INVALID")
        run_id = ""
    check_event_ledger(events, run_id, issues)
    if run_id:
        check_knowledge(events, project_root, run_id, issues)
    if bootstrap:
        return issues

    telemetry = load_json(run_dir / "telemetry.json", issues)
    grading = load_json(run_dir / "grading.json", issues)
    report = (run_dir / "evaluation-report.md").read_text(encoding="utf-8")

    for label, value in (("telemetry", telemetry), ("grading", grading)):
        if value.get("pipeline_run_id") != run_id:
            issues.append(f"PIPELINE_RUN_ID_MISMATCH {label}")
    if run_id and run_id not in report:
        issues.append("REPORT_MISSING_PIPELINE_RUN_ID")

    check_tokens(telemetry.get("tokens"), "telemetry.tokens", issues)
    allocation = telemetry.get("phase_allocation")
    if isinstance(allocation, dict) and isinstance(allocation.get("phases"), list):
        phases = [row for row in allocation["phases"] if isinstance(row, dict)]
        if phases:
            for index, phase in enumerate(phases, 1):
                check_tokens(phase, f"telemetry.phase[{index}]", issues)
            totals = telemetry.get("tokens") if isinstance(telemetry.get("tokens"), dict) else {}
            for field in (*TOKEN_FIELDS, "total_without_cache_read", "total_with_cache"):
                if all(integer(phase.get(field)) for phase in phases) and integer(totals.get(field)):
                    actual = sum(phase[field] for phase in phases)
                    if actual != totals[field]:
                        issues.append(
                            f"PHASE_TOKEN_SUM_MISMATCH {field}: expected={totals[field]} actual={actual}"
                        )

    check_grading(grading, issues)

    completed_events = [event for event in events if event.get("type") == "executor_session_completed"]
    if completed_events:
        event_tokens = completed_events[-1].get("tokens")
        totals = telemetry.get("tokens")
        if isinstance(event_tokens, dict) and isinstance(totals, dict):
            for field in (*TOKEN_FIELDS, "total_without_cache_read", "total_with_cache"):
                if field in event_tokens and event_tokens.get(field) != totals.get(field):
                    issues.append(f"EXECUTOR_EVENT_TOKEN_MISMATCH {field}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()

    run_dir = args.run_dir.expanduser().resolve()
    project_root = (
        args.project_root.expanduser().resolve()
        if args.project_root
        else Path(__file__).resolve().parents[3]
    )
    issues = validate(run_dir, project_root)
    result = {
        "run_dir": str(run_dir),
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
