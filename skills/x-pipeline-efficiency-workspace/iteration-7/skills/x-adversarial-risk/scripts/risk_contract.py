#!/usr/bin/env python3
"""Validate the bounded x-adversarial-risk Spec contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


METADATA_FIELDS = (
    "adversarial_risk_version",
    "complexity",
    "importance",
    "risk_average",
    "review_budget",
    "adversarial_review",
)
HEADER_FIELDS = ("spec_version", *METADATA_FIELDS)
VALID_BUDGETS = {"standard", "deep", "full"}
VALID_STATUSES = {"pending", "skipped-standard", "complete"}
SUPPORTED_VERSIONS = {"1", "2", "3"}
SCENARIO_RE = re.compile(r"^###\s+Scenario\s+(SC_\d{2,}):\s*(.+?)\s*$")
SOURCE_RE = re.compile(r"^-\s*来源[：:]\s*(.+?)\s*$")
V1_ADVERSARIAL_SOURCE_RE = re.compile(
    r"^adversarial-review\s*\((?:"
    r"AR-\d{3}(?:\s*,\s*AR-\d{3})*"
    r"|assumption:[^)]+"
    r")\)$"
)
NAMESPACED_RISK_ID_PATTERN = r"[A-Za-z][A-Za-z0-9]*-risk-\d{3}"
NAMESPACED_RISK_ID_RE = re.compile(rf"^{NAMESPACED_RISK_ID_PATTERN}$")
V2_ADVERSARIAL_SOURCE_RE = re.compile(
    r"^adversarial-review\s*\("
    r"(?:"
    r"(?P<legacy_risk_id>AR-\d{3});\s*"
    r"pattern:(?P<pattern>[a-z0-9][a-z0-9-]*)"
    rf"|(?P<risk_id>{NAMESPACED_RISK_ID_PATTERN})"
    r"|assumption:[^)]+"
    r")"
    r"\)$"
)
V3_ADVERSARIAL_SOURCE_RE = re.compile(
    r"^adversarial-review\s*\("
    r"(?:"
    rf"rag:(?P<risk_id>{NAMESPACED_RISK_ID_PATTERN})"
    r"|assumption:[^)]+"
    r")"
    r"\)$"
)
CATALOG_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
CATALOG_FIELD_RE = re.compile(r"^(关键词|Risk)[：:]\s*(.*?)\s*$")
REQUIRED_CATALOG_FIELDS = ("关键词", "Risk")
FORBIDDEN_CATALOG_MARKERS = (
    "来源证据",
    "/Volumes/",
    "skills/x-pipeline-efficiency-workspace/",
)


@dataclass(frozen=True)
class Issue:
    code: str
    line: int
    message: str

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "line": self.line, "message": self.message}


@dataclass(frozen=True)
class RiskCard:
    id: str
    keywords: str
    risk: str

    @property
    def text(self) -> str:
        return f"关键词：{self.keywords}\nRisk：{self.risk}"


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

    for index, key in enumerate(HEADER_FIELDS):
        if index >= len(lines) or not re.match(rf"^>\s*{key}:\s*\S.*$", lines[index]):
            issues.append(
                Issue(
                    "SPEC_HEADER_FORMAT",
                    index + 1,
                    f"第 {index + 1} 行必须使用 > {key}: <值>",
                )
            )
    if len(lines) > len(HEADER_FIELDS) and lines[len(HEADER_FIELDS)] != "":
        issues.append(
            Issue(
                "SPEC_HEADER_FORMAT",
                len(HEADER_FIELDS) + 1,
                "七个元数据字段后必须保留一个空行",
            )
        )

    version = metadata.get("adversarial_risk_version", "")
    if version not in SUPPORTED_VERSIONS:
        issues.append(
            Issue(
                "SPEC_VERSION",
                _line_number(lines, "adversarial_risk_version"),
                "adversarial_risk_version 必须为 1、2 或 3",
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
        elif version == "1" and not V1_ADVERSARIAL_SOURCE_RE.fullmatch(source_value):
            issues.append(
                Issue(
                    "SPEC_SCENARIO_SOURCE",
                    source_line,
                    f"{scenario_id} 的 v1 对抗性来源必须引用 AR-nnn 或 assumption:<说明>",
                )
            )
        elif version == "2" and not V2_ADVERSARIAL_SOURCE_RE.fullmatch(source_value):
            issues.append(
                Issue(
                    "SPEC_SCENARIO_SOURCE",
                    source_line,
                    f"{scenario_id} 的 v2 对抗性来源必须使用 "
                    "命名空间化风险 ID、历史 AR-nnn; pattern:<标签> "
                    "或 assumption:<说明>",
                )
            )
        elif version == "3" and not V3_ADVERSARIAL_SOURCE_RE.fullmatch(source_value):
            issues.append(
                Issue(
                    "SPEC_SCENARIO_SOURCE",
                    source_line,
                    f"{scenario_id} 的 v3 RAG 来源必须使用 "
                    "adversarial-review (rag:<命名空间化风险 ID>)；"
                    "独立假设使用 assumption:<说明>",
                )
            )

    return issues


def parse_catalog(text: str) -> tuple[list[RiskCard], list[Issue]]:
    lines = text.splitlines()
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = CATALOG_HEADING_RE.match(line)
        if match:
            starts.append((index, match.group(1)))

    issues: list[Issue] = []
    if not starts:
        return [], [Issue("CATALOG_EMPTY", 0, "错题集缺少风险条目")]

    cards: list[RiskCard] = []
    seen_ids: set[str] = set()
    for position, (start, risk_id) in enumerate(starts):
        heading_line = start + 1
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        fields: dict[str, tuple[int, str]] = {}

        valid_id = bool(NAMESPACED_RISK_ID_RE.fullmatch(risk_id))
        if not valid_id:
            issues.append(
                Issue(
                    "CATALOG_ID",
                    heading_line,
                    f"错题 ID 必须匹配 <namespace>-risk-<三位序号>：{risk_id}",
                )
            )
        elif risk_id in seen_ids:
            issues.append(
                Issue("CATALOG_DUPLICATE_ID", heading_line, f"错题 ID 重复：{risk_id}")
            )
        else:
            seen_ids.add(risk_id)

        for offset in range(start + 1, end):
            line = lines[offset]
            if not line.strip():
                continue
            match = CATALOG_FIELD_RE.fullmatch(line)
            if not match:
                issues.append(
                    Issue(
                        "CATALOG_UNKNOWN_CONTENT",
                        offset + 1,
                        f"{risk_id} 只允许关键词和 Risk 字段",
                    )
                )
                continue
            field, value = match.groups()
            if field in fields:
                issues.append(
                    Issue(
                        "CATALOG_DUPLICATE_FIELD",
                        offset + 1,
                        f"{risk_id} 字段重复：{field}",
                    )
                )
                continue
            fields[field] = (offset + 1, value.strip())

        for field in REQUIRED_CATALOG_FIELDS:
            if field not in fields or not fields[field][1]:
                issues.append(
                    Issue(
                        "CATALOG_MISSING_FIELD",
                        heading_line,
                        f"{risk_id} 缺少非空字段：{field}",
                    )
                )

        if valid_id and all(
            field in fields and fields[field][1] for field in REQUIRED_CATALOG_FIELDS
        ):
            cards.append(
                RiskCard(
                    id=risk_id,
                    keywords=fields["关键词"][1],
                    risk=fields["Risk"][1],
                )
            )

    if starts[0][1] != "A-risk-001":
        issues.append(
            Issue(
                "CATALOG_FIRST_ID",
                starts[0][0] + 1,
                "首条错题 ID 必须为 A-risk-001",
            )
        )

    return cards, issues


def validate_corpus(text: str) -> list[Issue]:
    lines = text.splitlines()
    _, issues = parse_catalog(text)

    for number, line in enumerate(lines, start=1):
        for marker in FORBIDDEN_CATALOG_MARKERS:
            if marker in line:
                issues.append(
                    Issue(
                        "CATALOG_EVIDENCE_PATH",
                        number,
                        f"错题集包含发布环境外的证据标记：{marker}",
                    )
                )

    return issues


def validate_traceability(spec_text: str, catalog_text: str) -> list[Issue]:
    lines = spec_text.splitlines()
    metadata, _ = _metadata(lines)
    version = metadata.get("adversarial_risk_version")
    if version not in {"2", "3"}:
        return []

    cards, _ = parse_catalog(catalog_text)
    catalog_ids = {card.id for card in cards}
    issues: list[Issue] = []
    for number, line in enumerate(lines, start=1):
        source_match = SOURCE_RE.match(line)
        if not source_match:
            continue
        source = source_match.group(1)
        source_re = (
            V3_ADVERSARIAL_SOURCE_RE
            if version == "3"
            else V2_ADVERSARIAL_SOURCE_RE
        )
        match = source_re.fullmatch(source)
        if not match or not match.group("risk_id"):
            continue
        risk_id = match.group("risk_id")
        if risk_id not in catalog_ids:
            issues.append(
                Issue(
                    "SPEC_SOURCE_CATALOG",
                    number,
                    f"来源引用的 {risk_id} 不在错题集中",
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
    spec_parser = subparsers.add_parser("validate-spec")
    spec_parser.add_argument("target")
    spec_parser.add_argument("--json", action="store_true", dest="as_json")
    corpus_parser = subparsers.add_parser("validate-corpus")
    corpus_parser.add_argument("target")
    corpus_parser.add_argument("--json", action="store_true", dest="as_json")
    review_parser = subparsers.add_parser("validate-review")
    review_parser.add_argument("target")
    review_parser.add_argument("--catalog", required=True)
    review_parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target_text, target_io_issue = _read_target(args.target)
    if target_io_issue is not None:
        _emit(args.command, args.target, [target_io_issue], args.as_json)
        return 2

    if args.command == "validate-spec":
        issues = validate_spec(target_text or "")
        output_target = args.target
    elif args.command == "validate-corpus":
        issues = validate_corpus(target_text or "")
        output_target = args.target
    else:
        catalog_text, catalog_io_issue = _read_target(args.catalog)
        if catalog_io_issue is not None:
            output_target = f"{args.target} + {args.catalog}"
            _emit(args.command, output_target, [catalog_io_issue], args.as_json)
            return 2
        issues = [
            *validate_spec(target_text or ""),
            *validate_corpus(catalog_text or ""),
            *validate_traceability(target_text or "", catalog_text or ""),
        ]
        output_target = f"{args.target} + {args.catalog}"

    _emit(args.command, output_target, issues, args.as_json)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
