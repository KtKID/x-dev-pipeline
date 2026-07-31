#!/usr/bin/env python3
"""Validate the stable x-cr-v2 report contract."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ISSUE_ID_RE = re.compile(r"^B\d+$")
INV_ID_RE = re.compile(r"^INV-(?:SPEC|CAND)-\d+$")
DETAIL_RE = re.compile(r"^### (B\d+):", re.MULTILINE)
SEVERITY_RE = re.compile(r"^### P([012])(?:：|:)")

ALLOWED_STATUSES = {
    "❌",
    "⚠️",
    "✅",
    "✅已修复",
    "➖无需修复",
    "⏭已跳过",
}
ALLOWED_SEVERITIES = {"P0", "P1", "P2"}
ALLOWED_CONFIDENCE = {"低", "中", "高", "已确认"}
ALLOWED_INVARIANT_RESULTS = {"保持", "破坏", "未验证", "来源冲突", "未触达"}


@dataclass(frozen=True)
class Table:
    headers: list[str]
    rows: list[list[str]]
    severity: str | None


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _section(text: str, heading: str) -> str | None:
    match = re.search(
        rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)",
        text,
        re.MULTILINE,
    )
    return match.group(1) if match else None


def _tables(section: str) -> list[Table]:
    lines = section.splitlines()
    result: list[Table] = []
    severity: str | None = None
    index = 0

    while index < len(lines):
        severity_match = SEVERITY_RE.match(lines[index].strip())
        if severity_match:
            severity = f"P{severity_match.group(1)}"

        if not lines[index].lstrip().startswith("|"):
            index += 1
            continue

        block: list[list[str]] = []
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            block.append(_cells(lines[index]))
            index += 1

        if len(block) >= 2 and _is_separator(block[1]):
            width = len(block[0])
            rows = [row for row in block[2:] if len(row) == width]
            result.append(Table(block[0], rows, severity))

    return result


def _row_value(table: Table, row: list[str], header: str) -> str | None:
    try:
        return row[table.headers.index(header)]
    except ValueError:
        return None


def _has_shortest_evidence_action(text: str, inv_id: str) -> bool:
    escaped = re.escape(inv_id)
    patterns = (
        rf"{escaped}[\s\S]{{0,400}}最短(?:补证|确认|取证)",
        rf"最短(?:补证|确认|取证)[\s\S]{{0,400}}{escaped}",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def validate_text(text: str) -> list[str]:
    errors: list[str] = []

    if not re.search(r"^> Schema: x-cr-v2\s*$", text, re.MULTILINE):
        errors.append("缺少 `> Schema: x-cr-v2`")

    required_sections: dict[str, str | None] = {
        name: _section(text, name)
        for name in ("不变量覆盖", "审查结论", "问题详情")
    }
    for name, value in required_sections.items():
        if value is None:
            errors.append(f"缺少 `## {name}`")

    if any(value is None for value in required_sections.values()):
        return errors

    invariant_section = required_sections["不变量覆盖"] or ""
    conclusion_section = required_sections["审查结论"] or ""
    detail_section = required_sections["问题详情"] or ""

    invariant_ids: set[str] = set()
    invariant_tables = [
        table
        for table in _tables(invariant_section)
        if "INV-ID" in table.headers and "结论" in table.headers
    ]
    if not invariant_tables:
        errors.append("`不变量覆盖` 缺少含 INV-ID 与结论列的表格")

    for table in invariant_tables:
        for row in table.rows:
            inv_id = _row_value(table, row, "INV-ID") or ""
            result = _row_value(table, row, "结论") or ""
            issue = _row_value(table, row, "关联问题")

            if not INV_ID_RE.fullmatch(inv_id):
                errors.append(f"不变量 ID 非法: `{inv_id}`")
                continue
            if inv_id in invariant_ids:
                errors.append(f"不变量 ID 重复: `{inv_id}`")
            invariant_ids.add(inv_id)

            if result not in ALLOWED_INVARIANT_RESULTS:
                errors.append(f"{inv_id} 的结论非法: `{result}`")

            mapped_issue = issue is not None and ISSUE_ID_RE.fullmatch(issue) is not None
            if result == "破坏" and not mapped_issue:
                errors.append(f"{inv_id} 为破坏，必须关联一个 Bn")
            if result in {"未验证", "来源冲突"}:
                if not mapped_issue and not _has_shortest_evidence_action(text, inv_id):
                    errors.append(
                        f"{inv_id} 为{result}，必须关联 Bn 或记录最短补证/确认动作"
                    )

    conclusion_ids: set[str] = set()
    conclusion_inv_ids: dict[str, str] = {}
    conclusion_tables = [
        table for table in _tables(conclusion_section) if "ID" in table.headers
    ]
    if not conclusion_tables:
        errors.append("`审查结论` 缺少含 ID 列的表格")

    for table in conclusion_tables:
        for row in table.rows:
            issue_id = _row_value(table, row, "ID") or ""
            if issue_id == "-":
                continue
            if not ISSUE_ID_RE.fullmatch(issue_id):
                errors.append(f"问题 ID 非法: `{issue_id}`")
                continue
            if issue_id in conclusion_ids:
                errors.append(f"审查结论中的问题 ID 重复: `{issue_id}`")
            conclusion_ids.add(issue_id)

            status = _row_value(table, row, "状态")
            if status not in ALLOWED_STATUSES:
                errors.append(f"{issue_id} 的状态非法: `{status or ''}`")

            severity = _row_value(table, row, "严重度") or table.severity
            if severity not in ALLOWED_SEVERITIES:
                errors.append(f"{issue_id} 的严重度缺失或非法: `{severity or ''}`")

            confidence = _row_value(table, row, "置信度")
            if confidence not in ALLOWED_CONFIDENCE:
                errors.append(f"{issue_id} 的置信度缺失或非法: `{confidence or ''}`")

            inv_id = _row_value(table, row, "INV-ID")
            if inv_id is None:
                errors.append(f"{issue_id} 缺少 INV-ID 列")
            elif inv_id != "-" and not INV_ID_RE.fullmatch(inv_id):
                errors.append(f"{issue_id} 的 INV-ID 非法: `{inv_id}`")
            elif inv_id != "-":
                conclusion_inv_ids[issue_id] = inv_id

    detail_ids = DETAIL_RE.findall(detail_section)
    detail_id_set = set(detail_ids)
    for issue_id in sorted(set(detail_ids)):
        if detail_ids.count(issue_id) > 1:
            errors.append(f"问题详情标题重复: `{issue_id}`")

    for issue_id in sorted(conclusion_ids - detail_id_set):
        errors.append(f"{issue_id} 缺少对应的 `### {issue_id}:` 详情")
    for issue_id in sorted(detail_id_set - conclusion_ids):
        errors.append(f"`### {issue_id}:` 在审查结论中没有对应行")

    for issue_id, inv_id in sorted(conclusion_inv_ids.items()):
        if inv_id not in invariant_ids:
            errors.append(f"{issue_id} 引用的 {inv_id} 不在不变量覆盖表中")

    return errors


def validate_path(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"无法读取报告: {exc}"]
    return validate_text(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()

    failed = False
    for report in args.reports:
        errors = validate_path(report)
        if errors:
            failed = True
            print(f"FAIL {report}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"OK   {report}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
