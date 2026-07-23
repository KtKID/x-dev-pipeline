#!/usr/bin/env python3
"""Validate x-adversarial-risk Spec metadata and mistake-corpus entries."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


METADATA_FIELDS = (
    "adversarial_risk_version",
    "complexity",
    "importance",
    "risk_average",
    "review_budget",
    "adversarial_review",
)
VALID_BUDGETS = {"standard", "deep", "full"}
VALID_STATUSES = {"pending", "skipped-standard", "complete"}
SCENARIO_RE = re.compile(r"^###\s+Scenario\s+(SC_\d{2,}):\s*(.+?)\s*$")
SOURCE_RE = re.compile(r"^-\s*来源[：:]\s*(.+?)\s*$")
ISSUE_HEADING_RE = re.compile(r"^##\s+(AR-\d{3}):\s*(.+?)\s*$")
CORPUS_FIELD_RE = re.compile(r"^-\s*([^：:]+)[：:]\s*(.*?)\s*$")
ADVERSARIAL_SOURCE_RE = re.compile(
    r"^adversarial-review\s*\((?:"
    r"AR-\d{3}(?:\s*,\s*AR-\d{3})*"
    r"|assumption:[^)]+"
    r")\)$"
)
REQUIRED_CORPUS_FIELDS = (
    "确认状态",
    "动作维度",
    "数据维度",
    "场景维度",
    "被破坏不变量",
    "最小反例",
    "应补 Scenario",
    "来源证据",
)


@dataclass(frozen=True)
class Issue:
    code: str
    line: int
    message: str

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "line": self.line, "message": self.message}


def expected_budget(complexity: int, importance: int) -> str:
    average = (complexity + importance) / 2
    if average >= 4 or max(complexity, importance) == 5:
        return "full"
    if average >= 3 or max(complexity, importance) == 4:
        return "deep"
    return "standard"


def _line_number(lines: Sequence[str], pattern: str) -> int:
    for index, line in enumerate(lines, start=1):
        if pattern in line:
            return index
    return 0


def _metadata(lines: Sequence[str]) -> tuple[dict[str, str], list[Issue]]:
    found: dict[str, str] = {}
    issues: list[Issue] = []
    field_re = re.compile(r"^>\s*([a-z_]+):\s*(.*?)\s*$")

    for number, line in enumerate(lines, start=1):
        match = field_re.match(line)
        if not match or match.group(1) not in METADATA_FIELDS:
            continue
        key, value = match.groups()
        if key in found:
            issues.append(Issue("SPEC_DUPLICATE_FIELD", number, f"风险字段重复：{key}"))
            continue
        found[key] = value

    for key in METADATA_FIELDS:
        if key not in found:
            issues.append(Issue("SPEC_MISSING_FIELD", 0, f"缺少风险字段：{key}"))

    return found, issues


def validate_spec(text: str) -> list[Issue]:
    lines = text.splitlines()
    metadata, issues = _metadata(lines)

    if metadata.get("adversarial_risk_version") != "1":
        issues.append(
            Issue(
                "SPEC_VERSION",
                _line_number(lines, "adversarial_risk_version"),
                "adversarial_risk_version 必须为 1",
            )
        )

    scores: dict[str, int] = {}
    for key in ("complexity", "importance"):
        value = metadata.get(key, "")
        if not re.fullmatch(r"[1-5]", value):
            issues.append(
                Issue(
                    "SPEC_SCORE",
                    _line_number(lines, f"{key}:"),
                    f"{key} 必须是 1..5 的整数",
                )
            )
            continue
        scores[key] = int(value)

    average_value = metadata.get("risk_average", "")
    declared_average: float | None = None
    if not re.fullmatch(r"[1-5]\.[05]", average_value):
        issues.append(
            Issue(
                "SPEC_AVERAGE",
                _line_number(lines, "risk_average:"),
                "risk_average 必须是一位小数，且以 .0 或 .5 结尾",
            )
        )
    else:
        declared_average = float(average_value)

    if len(scores) == 2:
        expected_average = (scores["complexity"] + scores["importance"]) / 2
        if declared_average is not None and declared_average != expected_average:
            issues.append(
                Issue(
                    "SPEC_AVERAGE",
                    _line_number(lines, "risk_average:"),
                    f"risk_average 应为 {expected_average:.1f}",
                )
            )

        declared_budget = metadata.get("review_budget", "")
        required_budget = expected_budget(scores["complexity"], scores["importance"])
        if declared_budget != required_budget:
            issues.append(
                Issue(
                    "SPEC_BUDGET",
                    _line_number(lines, "review_budget:"),
                    f"review_budget 应为 {required_budget}",
                )
            )

    budget = metadata.get("review_budget", "")
    if budget not in VALID_BUDGETS:
        issues.append(
            Issue(
                "SPEC_BUDGET",
                _line_number(lines, "review_budget:"),
                "review_budget 必须是 standard、deep 或 full",
            )
        )

    status = metadata.get("adversarial_review", "")
    if status not in VALID_STATUSES:
        issues.append(
            Issue(
                "SPEC_STATUS",
                _line_number(lines, "adversarial_review:"),
                "adversarial_review 状态非法",
            )
        )
    elif status == "pending":
        issues.append(
            Issue(
                "SPEC_PENDING",
                _line_number(lines, "adversarial_review:"),
                "对抗性风险审查仍为 pending，阻断 x-req3",
            )
        )
    elif status == "skipped-standard" and budget != "standard":
        issues.append(
            Issue(
                "SPEC_STATUS",
                _line_number(lines, "adversarial_review:"),
                "只有 standard 预算可以使用 skipped-standard",
            )
        )
    elif status == "complete" and budget == "standard":
        issues.append(
            Issue(
                "SPEC_STATUS",
                _line_number(lines, "adversarial_review:"),
                "standard 预算完成后应使用 skipped-standard",
            )
        )

    if "## 风险评分依据" not in lines:
        issues.append(Issue("SPEC_SECTION", 0, "缺少 ## 风险评分依据"))
    if "## 对抗性审查记录" not in lines:
        issues.append(Issue("SPEC_SECTION", 0, "缺少 ## 对抗性审查记录"))
    elif status != "pending":
        record_rows = [
            line
            for line in lines
            if re.match(r"^\|\s*ARV-\d+\s*\|", line)
        ]
        if not record_rows:
            issues.append(
                Issue(
                    "SPEC_REVIEW_RECORD",
                    _line_number(lines, "## 对抗性审查记录"),
                    "已完成审查缺少 ARV-n 记录行",
                )
            )

    scenario_starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = SCENARIO_RE.match(line)
        if match:
            scenario_starts.append((index, match.group(1)))

    if not scenario_starts:
        issues.append(Issue("SPEC_SCENARIO", 0, "缺少 SC_NN Scenario"))
    seen_ids: set[str] = set()
    for position, (start, scenario_id) in enumerate(scenario_starts):
        if scenario_id in seen_ids:
            issues.append(
                Issue(
                    "SPEC_SCENARIO_ID",
                    start + 1,
                    f"Scenario ID 重复：{scenario_id}",
                )
            )
        seen_ids.add(scenario_id)

        end = scenario_starts[position + 1][0] if position + 1 < len(scenario_starts) else len(lines)
        source_value = ""
        source_line = 0
        for offset in range(start + 1, end):
            source_match = SOURCE_RE.match(lines[offset])
            if source_match:
                source_value = source_match.group(1)
                source_line = offset + 1
                break

        if not source_value:
            issues.append(
                Issue(
                    "SPEC_SCENARIO_SOURCE",
                    start + 1,
                    f"{scenario_id} 缺少来源字段",
                )
            )
        elif source_value == "initial-spec":
            continue
        elif not ADVERSARIAL_SOURCE_RE.fullmatch(source_value):
            issues.append(
                Issue(
                    "SPEC_SCENARIO_SOURCE",
                    source_line,
                    f"{scenario_id} 的对抗性来源必须引用 AR-nnn 或 assumption:<说明>",
                )
            )

    return issues


def validate_corpus(text: str) -> list[Issue]:
    lines = text.splitlines()
    starts: list[tuple[int, str]] = []
    issues: list[Issue] = []
    for index, line in enumerate(lines):
        match = ISSUE_HEADING_RE.match(line)
        if match:
            starts.append((index, match.group(1)))

    if not starts:
        return [Issue("CORPUS_EMPTY", 0, "错题集缺少 AR-nnn issue")]

    seen_ids: set[str] = set()
    for position, (start, issue_id) in enumerate(starts):
        if issue_id in seen_ids:
            issues.append(
                Issue("CORPUS_DUPLICATE_ID", start + 1, f"issue ID 重复：{issue_id}")
            )
        seen_ids.add(issue_id)

        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        fields: dict[str, tuple[str, int]] = {}
        for offset in range(start + 1, end):
            match = CORPUS_FIELD_RE.match(lines[offset])
            if not match:
                continue
            key, value = match.groups()
            key = key.strip()
            if key in REQUIRED_CORPUS_FIELDS and key not in fields:
                fields[key] = (value.strip(), offset + 1)

        for field in REQUIRED_CORPUS_FIELDS:
            value, line_number = fields.get(field, ("", start + 1))
            if not value:
                issues.append(
                    Issue(
                        "CORPUS_MISSING_FIELD",
                        line_number,
                        f"{issue_id} 缺少字段：{field}",
                    )
                )

        status = fields.get("确认状态", ("", start + 1))[0]
        if status and status != "confirmed":
            issues.append(
                Issue(
                    "CORPUS_STATUS",
                    fields["确认状态"][1],
                    f"{issue_id} 只有 confirmed issue 可以进入错题集",
                )
            )

    return issues


def _read_target(path_text: str) -> tuple[str | None, Issue | None]:
    path = Path(path_text)
    try:
        if not path.is_file():
            raise OSError("目标不是可读文件")
        return path.read_text(encoding="utf-8"), None
    except (OSError, UnicodeError) as exc:
        return None, Issue("IO_ERROR", 0, f"{path}: {exc}")


def _emit(command: str, target: str, issues: Sequence[Issue], as_json: bool) -> None:
    payload = {
        "command": command,
        "target": target,
        "valid": not issues,
        "issues": [issue.as_dict() for issue in issues],
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if not issues:
        print(f"PASS {command}: {target}")
        return
    for issue in issues:
        location = f":{issue.line}" if issue.line else ""
        print(f"{target}{location} [{issue.code}] {issue.message}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate-spec", "validate-corpus"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("target")
        subparser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text, io_issue = _read_target(args.target)
    if io_issue is not None:
        _emit(args.command, args.target, [io_issue], args.as_json)
        return 2

    validators: dict[str, Callable[[str], list[Issue]]] = {
        "validate-spec": validate_spec,
        "validate-corpus": validate_corpus,
    }
    issues = validators[args.command](text or "")
    _emit(args.command, args.target, issues, args.as_json)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
