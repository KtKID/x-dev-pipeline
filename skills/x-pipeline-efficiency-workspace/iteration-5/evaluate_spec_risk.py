#!/usr/bin/env python3
"""Deterministic grader for the isolated journal Spec risk run."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


HEADER_RE = re.compile(r"^>\s*([a-z_]+):\s*(.+?)\s*$", re.MULTILINE)
SCENARIO_RE = re.compile(
    r"^### Scenario (SC_\d+):[^\n]*\n(?P<body>.*?)(?=^### Scenario SC_\d+:|\Z)",
    re.MULTILINE | re.DOTALL,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def scenarios(text: str) -> dict[str, str]:
    return {
        match.group(1): match.group("body").strip()
        for match in SCENARIO_RE.finditer(text)
    }


def source(body: str) -> str:
    match = re.search(r"^- 来源：(.+?)\s*$", body, re.MULTILINE)
    return match.group(1).strip() if match else ""


def expected_budget(complexity: int, importance: int) -> tuple[float, str]:
    average = round((complexity + importance) / 2, 1)
    if average < 3:
        budget = "standard"
    elif average < 4:
        budget = "deep"
    else:
        budget = "full"
    if complexity == 5 or importance == 5:
        budget = "full"
    elif (complexity == 4 or importance == 4) and budget == "standard":
        budget = "deep"
    return average, budget


def run_validator(workspace: Path, command: str, target: str) -> dict[str, Any]:
    argv = [
        "python3",
        "skills/x-adversarial-risk/scripts/risk_contract.py",
        command,
        target,
        "--json",
    ]
    completed = subprocess.run(
        argv,
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": " ".join(argv),
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def add(
    expectations: list[dict[str, Any]],
    text: str,
    passed: bool,
    evidence: str,
) -> None:
    expectations.append(
        {"text": text, "passed": bool(passed), "evidence": evidence}
    )


def main() -> int:
    args = parse_args()
    workspace = args.workspace.resolve()
    initial_path = workspace / "artifacts/spec.initial.md"
    final_path = workspace / "artifacts/spec.final.md"
    summary_path = workspace / "artifacts/run-summary.json"
    live_path = workspace / "docs/spec/journal-index-recovery/spec.md"

    expectations: list[dict[str, Any]] = []
    required = [initial_path, final_path, summary_path, live_path]
    add(
        expectations,
        "Initial, final, summary, and live Spec artifacts are persisted.",
        all(path.is_file() for path in required),
        ", ".join(f"{path.name}={path.is_file()}" for path in required),
    )
    if not all(path.is_file() for path in required):
        payload = {
            "score": round(
                100
                * sum(item["passed"] for item in expectations)
                / len(expectations)
            ),
            "expectations": expectations,
        }
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return 1

    initial_text = initial_path.read_text(encoding="utf-8")
    final_text = final_path.read_text(encoding="utf-8")
    live_text = live_path.read_text(encoding="utf-8")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    headers = dict(HEADER_RE.findall(final_text))
    initial_scenarios = scenarios(initial_text)
    final_scenarios = scenarios(final_text)
    initial_sources = {sid: source(body) for sid, body in initial_scenarios.items()}
    final_sources = {sid: source(body) for sid, body in final_scenarios.items()}

    try:
        complexity = int(headers["complexity"])
        importance = int(headers["importance"])
        average = float(headers["risk_average"])
        budget = headers["review_budget"]
        review = headers["adversarial_review"]
        calculated_average, calculated_budget = expected_budget(
            complexity, importance
        )
        scoring_valid = (
            1 <= complexity <= 5
            and 1 <= importance <= 5
            and average == calculated_average
            and budget == calculated_budget
        )
        scoring_evidence = (
            f"complexity={complexity}, importance={importance}, "
            f"average={average}/{calculated_average}, "
            f"budget={budget}/{calculated_budget}, review={review}"
        )
    except (KeyError, TypeError, ValueError) as exc:
        complexity = importance = 0
        average = 0.0
        budget = review = ""
        scoring_valid = False
        scoring_evidence = f"header parse failed: {exc}"

    add(
        expectations,
        "Complexity and importance produce the required average and dynamic budget.",
        scoring_valid,
        scoring_evidence,
    )
    add(
        expectations,
        "Crash recovery, locking, idempotency, and concurrency are scored complexity 5.",
        complexity == 5,
        f"complexity={complexity}",
    )
    add(
        expectations,
        "The local single-user CLI is scored importance 1 from the supplied task evidence.",
        importance == 1,
        f"importance={importance}",
    )
    add(
        expectations,
        "A dimension score of 5 upgrades the review budget to full and completes review.",
        budget == "full" and review == "complete",
        f"budget={budget}, adversarial_review={review}",
    )
    add(
        expectations,
        "Every first-draft Scenario is labeled initial-spec.",
        bool(initial_sources)
        and all(value == "initial-spec" for value in initial_sources.values()),
        json.dumps(initial_sources, ensure_ascii=False, sort_keys=True),
    )
    initial_stable = all(
        sid in final_scenarios and final_sources.get(sid) == "initial-spec"
        for sid in initial_scenarios
    )
    add(
        expectations,
        "The adversarial pass preserves all initial Scenario IDs and provenance.",
        initial_stable,
        f"initial={sorted(initial_scenarios)}, final={sorted(final_scenarios)}",
    )
    adversarial = {
        sid: body
        for sid, body in final_scenarios.items()
        if final_sources.get(sid, "").startswith("adversarial-review")
    }
    add(
        expectations,
        "The final Spec adds traceable adversarial-review Scenarios.",
        bool(adversarial) and len(final_scenarios) > len(initial_scenarios),
        json.dumps(
            {sid: final_sources[sid] for sid in adversarial},
            ensure_ascii=False,
            sort_keys=True,
        ),
    )

    issue_requirements = {
        "AR-001": ["snapshot", "journal", "崩溃"],
        "AR-002": ["snapshot", "CORRUPT_SNAPSHOT"],
        "AR-003": ["CORRUPT_LOG", "完整"],
        "AR-004": ["request_id", "NOT_FOUND", "VERSION_CONFLICT"],
        "AR-005": ["顶层字段", "message", "exit"],
    }
    issue_hits: dict[str, list[str]] = {}
    for issue, keywords in issue_requirements.items():
        matching = [
            sid
            for sid, body in adversarial.items()
            if issue in final_sources.get(sid, "")
            and all(keyword in body for keyword in keywords)
        ]
        issue_hits[issue] = matching

    add(
        expectations,
        "AR-001 compact replace-window recovery is covered by an observable Scenario.",
        bool(issue_hits["AR-001"]),
        json.dumps(issue_hits["AR-001"], ensure_ascii=False),
    )
    add(
        expectations,
        "AR-002 semantic snapshot consistency is covered by an observable Scenario.",
        bool(issue_hits["AR-002"]),
        json.dumps(issue_hits["AR-002"], ensure_ascii=False),
    )
    add(
        expectations,
        "AR-003 logically invalid complete journal records are classified as CORRUPT_LOG.",
        bool(issue_hits["AR-003"]),
        json.dumps(issue_hits["AR-003"], ensure_ascii=False),
    )
    add(
        expectations,
        "AR-004 failed request IDs remain reusable for a later valid mutation.",
        bool(issue_hits["AR-004"]),
        json.dumps(issue_hits["AR-004"], ensure_ascii=False),
    )
    add(
        expectations,
        "AR-005 validates the complete public error response contract.",
        bool(issue_hits["AR-005"]),
        json.dumps(issue_hits["AR-005"], ensure_ascii=False),
    )

    summary_skills = summary.get("skills_read", [])
    add(
        expectations,
        "The run summary records x-spec3 and x-adversarial-risk as actually read.",
        any("x-spec3" in item for item in summary_skills)
        and any("x-adversarial-risk" in item for item in summary_skills),
        json.dumps(summary_skills, ensure_ascii=False),
    )
    add(
        expectations,
        "The final artifact exactly matches the live Spec.",
        final_text == live_text,
        f"same_bytes={final_text == live_text}",
    )
    add(
        expectations,
        "No pending markers or template placeholders remain in the final Spec.",
        "ARV-pending" not in final_text
        and "<spec-name>" not in final_text
        and "待审查" not in final_text,
        "checked ARV-pending, <spec-name>, 待审查",
    )

    validators = [
        run_validator(
            workspace,
            "validate-spec",
            "docs/spec/journal-index-recovery/spec.md",
        ),
        run_validator(
            workspace,
            "validate-corpus",
            "skills/x-adversarial-risk/references/risk-mistakes.md",
        ),
    ]
    add(
        expectations,
        "The Spec and corpus mechanical validators both pass.",
        all(result["exit_code"] == 0 for result in validators),
        json.dumps(validators, ensure_ascii=False),
    )

    passed = sum(item["passed"] for item in expectations)
    score = round(100 * passed / len(expectations))
    payload = {
        "schema_version": 1,
        "score": score,
        "passed": passed,
        "total": len(expectations),
        "expectations": expectations,
        "parsed": {
            "complexity": complexity,
            "importance": importance,
            "risk_average": average,
            "review_budget": budget,
            "adversarial_review": review,
            "initial_scenarios": sorted(initial_scenarios),
            "adversarial_scenarios": sorted(adversarial),
            "issue_hits": issue_hits,
        },
        "validators": validators,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0 if passed == len(expectations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
