#!/usr/bin/env python3
"""核对 x-cr 报告结构（格式见 skills/x-cr/references/report-template.md）。

用法：python3 validate_report.py <报告路径>...
退出码：0 全部通过，1 有报告不通过。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

RULE_ID_RE = re.compile(r"^(?:[a-z0-9][a-z0-9-]*:(?:C\d+|D\d+|feat\d+-场景\d+)|新\d+)$")
ISSUE_ID_RE = re.compile(r"^B\d+$")
DETAIL_RE = re.compile(r"^### (B\d+):", re.MULTILINE)
HASH_RE = re.compile(r"\b[0-9a-f]{7,40}\b")

RESULTS = {"守住了", "被打破", "没法验证", "没走到", "来源不一"}
NEEDS_ISSUE = {"被打破", "没法验证", "来源不一"}
SEVERITIES = {"P0", "P1", "P2"}
STATUSES = {"待修", "已修", "误报不修", "待确认"}


@dataclass(frozen=True)
class Table:
    headers: list[str]
    rows: list[list[str]]


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _section(text: str, heading: str) -> str | None:
    match = re.search(rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)", text, re.MULTILINE)
    return match.group(1) if match else None


def _first_table(section: str, required: tuple[str, ...]) -> Table | None:
    lines = section.splitlines()
    index = 0
    while index < len(lines):
        if not lines[index].lstrip().startswith("|"):
            index += 1
            continue
        block: list[list[str]] = []
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            block.append(_cells(lines[index]))
            index += 1
        if len(block) >= 2 and _is_separator(block[1]) and all(h in block[0] for h in required):
            width = len(block[0])
            return Table(block[0], [row for row in block[2:] if len(row) == width])
    return None


def _value(table: Table, row: list[str], header: str) -> str:
    return row[table.headers.index(header)]


def _details(section: str) -> dict[str, str]:
    parts = re.split(r"^(?=### B\d+:)", section, flags=re.MULTILINE)
    out: dict[str, str] = {}
    for part in parts:
        match = DETAIL_RE.match(part)
        if match:
            out.setdefault(match.group(1), part)
    return out


def _field(block: str, name: str) -> str | None:
    match = re.search(rf"^- {re.escape(name)}：(.*)$", block, re.MULTILINE)
    return match.group(1).strip() if match else None


def _check_fix(issue_id: str, severity: str, status: str, detail: str, errors: list[str]) -> None:
    fix_match = re.search(r"^\*\*修复\*\*\s*$([\s\S]*)", detail, re.MULTILINE)
    if status == "待修":
        return
    if not fix_match:
        errors.append(f"{issue_id} 状态是{status}，详情里缺少「**修复**」段")
        return
    fix = fix_match.group(1)
    result = _field(fix, "结果")
    if result != status:
        errors.append(f"{issue_id} 问题表状态是{status}，修复段结果是 `{result or ''}`，两处要一致")
    if status == "已修":
        for name in ("改动位置", "反例测试", "验证"):
            if not _field(fix, name):
                errors.append(f"{issue_id} 已修，修复段缺少「{name}」")
        location = _field(fix, "改动位置") or ""
        if location and "`" not in location:
            errors.append(f"{issue_id} 的改动位置要写文件和函数（用反引号标出），比如 `src/a.py` 的 `f()`")
        if HASH_RE.search(location):
            errors.append(f"{issue_id} 的改动位置写了 commit 哈希，改成文件和函数位置")
        test = _field(fix, "反例测试") or ""
        if severity in {"P0", "P1"} and test.startswith("无"):
            errors.append(f"{issue_id} 是 {severity}，已修必须留一条能复跑的反例测试")
    elif status == "误报不修" and not _field(fix, "理由"):
        errors.append(f"{issue_id} 误报不修，修复段缺少「理由」")
    elif status == "待确认" and not _field(fix, "要确认"):
        errors.append(f"{issue_id} 待确认，修复段缺少「要确认」")


def validate_text(text: str) -> list[str]:
    errors: list[str] = []
    sections = {name: _section(text, name) for name in ("范围", "规则表", "问题")}
    for name, value in sections.items():
        if value is None:
            errors.append(f"缺少 `## {name}`")
    if any(value is None for value in sections.values()):
        return errors

    rules = _first_table(sections["规则表"] or "", ("编号", "结论", "问题"))
    if rules is None:
        errors.append("「规则表」缺少含 编号、结论、问题 三列的表格")
    issues = _first_table(sections["问题"] or "", ("ID", "严重度", "状态", "位置"))
    if issues is None:
        errors.append("「问题」缺少含 ID、严重度、状态、位置 四列的表格")
    if rules is None or issues is None:
        return errors

    issue_rows: dict[str, tuple[str, str]] = {}
    for row in issues.rows:
        issue_id = _value(issues, row, "ID")
        if not ISSUE_ID_RE.fullmatch(issue_id):
            errors.append(f"问题编号不对：`{issue_id}`，要写 B1、B2…")
            continue
        if issue_id in issue_rows:
            errors.append(f"问题编号重复：`{issue_id}`")
        severity = _value(issues, row, "严重度")
        status = _value(issues, row, "状态")
        if severity not in SEVERITIES:
            errors.append(f"{issue_id} 的严重度不对：`{severity}`，只能是 P0、P1、P2")
        if status not in STATUSES:
            errors.append(f"{issue_id} 的状态不对：`{status}`，只能是 待修、已修、误报不修、待确认")
        if not _value(issues, row, "位置").strip("-  "):
            errors.append(f"{issue_id} 没写位置")
        issue_rows[issue_id] = (severity, status)

    seen_rules: set[str] = set()
    for row in rules.rows:
        rule_id = _value(rules, row, "编号")
        result = _value(rules, row, "结论")
        linked = _value(rules, row, "问题")
        if not RULE_ID_RE.fullmatch(rule_id):
            errors.append(f"规则编号不对：`{rule_id}`，要写 <spec 名>:C2、<spec 名>:feat03-场景2、<spec 名>:D04 或 新1")
            continue
        if rule_id in seen_rules:
            errors.append(f"规则编号重复：`{rule_id}`")
        seen_rules.add(rule_id)
        if result not in RESULTS:
            errors.append(f"{rule_id} 的结论不对：`{result}`，只能是 守住了、被打破、没法验证、没走到、来源不一")
        linked_ids = [x.strip() for x in linked.split("、") if x.strip() not in {"", "-"}]
        if result in NEEDS_ISSUE and not linked_ids:
            errors.append(f"{rule_id} 结论是{result}，要连到一个问题（B1…）")
        for issue_id in linked_ids:
            if issue_id not in issue_rows:
                errors.append(f"{rule_id} 连到的 {issue_id} 不在问题表里")

    details = _details(sections["问题"] or "")
    for issue_id in sorted(set(issue_rows) - set(details)):
        errors.append(f"{issue_id} 缺少 `### {issue_id}:` 详情")
    for issue_id in sorted(set(details) - set(issue_rows)):
        errors.append(f"`### {issue_id}:` 在问题表里没有对应行")
    if len(DETAIL_RE.findall(sections["问题"] or "")) != len(details):
        errors.append("有重复的 `### Bn:` 详情标题")

    for issue_id, (severity, status) in issue_rows.items():
        detail = details.get(issue_id)
        if detail is None:
            continue
        for name in ("规则", "位置", "反例", "证据", "怎么改"):
            if not _field(detail, name):
                errors.append(f"{issue_id} 详情缺少「{name}」")
        if status in STATUSES:
            _check_fix(issue_id, severity, status, detail, errors)

    return errors


def validate_path(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"无法读取报告: {exc}"]
    return validate_text(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="核对 x-cr 报告结构")
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
