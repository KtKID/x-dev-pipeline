#!/usr/bin/env python3
"""iteration-7 x-spec3 的确定性文档校验引擎。

核心职责：
1. 解析 ``docs/spec/<name>/spec.md`` 的元数据、章节、表格和 Scenario。
2. 校验风险评分、审查预算、RAG/no-corpus 路径及 x-req3 就绪状态。
3. 向 ``xdev.py``、``req3.py`` 和独立命令行提供统一的 issue 列表。

职责边界：本模块只读，不生成或修改 spec/task 文件。task 拆解、覆盖关系、
状态和文件 scaffold 由 ``req3.py`` 负责，统一 CLI 分发由 ``xdev.py`` 负责。
"""

# 设计说明：公开函数提供包识别、Scenario/边界读取和完整校验；以下划线开头
# 的函数负责 Markdown 解析及各子契约。所有 issue 保留原始行号，V19 表示
# spec3 文档/风险契约问题，V20 表示 Scenario 契约问题。

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path



HEADER_FIELDS = (
    "spec_version",
    "adversarial_risk_version",
    "complexity",
    "importance",
    "risk_average",
    "review_budget",
    "adversarial_review",
)
VALID_BUDGETS = {"standard", "deep", "full"}
VALID_STATUSES = {"pending", "skipped-standard", "complete"}
MODEL_TUPLE = ("数据流", "状态", "时序", "资源", "不变量", "故障")
REQUIRED_SECTIONS = (
    "任务目标",
    "非目标",
    "风险评分依据",
    "影响边界与不变量",
    "判断依据",
    "建模覆盖声明",
    "验收清单",
    "测试驱动开发",
    "对抗性审查记录",
    "Scenarios",
)
BOUNDARY_HEADER = ("模块", "角色", "本次影响", "主要风险", "必须保持的不变量", "依据")
JUDGMENT_HEADER = ("J-ID", "判断", "来源", "证据或推断", "状态")
MODEL_HEADER = ("维度", "覆盖位置或具体不适用理由")
RISK_BASIS_FIELDS = ("复杂度", "重要性", "预算升级")
REVIEW_HEADER = (
    "Review",
    "预算",
    "风险来源",
    "查询",
    "召回 ID",
    "复用 Scenario",
    "新增 Scenario",
    "CLI",
)

SPEC3_MARKER_RE = re.compile(r"^>\s*spec_version:\s*3\s*$", re.IGNORECASE)
FIELD_RE = re.compile(r"^>\s*([a-z_]+):\s*(.*?)\s*$")
H1_RE = re.compile(r"^#\s+(.+?)\s*$")
H2_RE = re.compile(r"^##\s+(.+?)\s*$")
H3_RE = re.compile(r"^###\s+(.+?)\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*$")
SCENARIO_RE = re.compile(r"^###\s+Scenario\s+(SC_[0-9]{2})\s*:\s*(.+?)\s*$")
SCENARIO_HEADING_RE = re.compile(r"^###\s+Scenario\b", re.IGNORECASE)
GWT_RE = re.compile(
    r"^\s*[-*+]\s*\*\*(GIVEN|WHEN|THEN)\*\*\s*[：:]?\s*(.*?)\s*$",
    re.IGNORECASE,
)
LAYER_RE = re.compile(
    r"^\s*[-*+]?\s*测试层\s*[：:]\s*(unit|smoke|e2e)\s*$",
    re.IGNORECASE,
)
EVIDENCE_RE = re.compile(r"^\s*[-*+]?\s*依据\s*[：:]\s*(.+?)\s*$")
SOURCE_RE = re.compile(r"^\s*[-*+]?\s*来源\s*[：:]\s*(.+?)\s*$")
V3_SOURCE_RE = re.compile(
    r"^adversarial-review\s*\((?:"
    r"rag:(?P<risk_id>AR-\d{3})"
    r"|assumption:(?P<assumption>[^)]+)"
    r")\)$"
)
RISK_ID_RE = re.compile(r"\bAR-\d{3}\b")
REVIEW_RAG_SOURCE_RE = re.compile(r"^RAG:(?P<risk_id>AR-\d{3})$")
REVIEW_ASSUMPTION_SOURCE_RE = re.compile(r"^assumption:(?P<assumption>.+)$")
REVIEW_ID_RE = re.compile(r"^ARV-\d+$")
JUDGMENT_ID_RE = re.compile(r"^J\d+$")



def issue(file: str, line: int, rule: str, msg: str) -> dict:
    """构造稳定的校验问题对象，供 CLI 和测试统一消费。"""
    return {"file": file, "line": line, "rule": rule, "msg": msg}


def normalize_module_name(value: str) -> str:
    """归一化 Markdown/Mermaid 模块标签，供 spec3 边界图做词法比对。"""
    value = re.sub(r"<br\s*/?>.*$", "", value, flags=re.IGNORECASE)
    value = value.split("·", 1)[0]
    value = re.split(r"[：:]", value, maxsplit=1)[0]
    value = re.sub(r"[\x60*_]", "", value)
    return re.sub(r"[^0-9A-Za-z一-鿿]+", "", value).lower()

def read_text(path: Path) -> str:
    """以 UTF-8 读取文本，遇到非法字节时使用替代字符保持校验流程可继续。"""
    return path.read_text(encoding="utf-8", errors="replace")


def _outside_fences(lines: list[str]) -> list[str]:
    """保留原行号，把 fenced code 及 fence 行替换为空行。"""
    visible: list[str] = []
    active_marker: str | None = None
    for line in lines:
        stripped = line.lstrip()
        marker = "```" if stripped.startswith("```") else "~~~" if stripped.startswith("~~~") else None
        if marker is not None:
            if active_marker is None:
                active_marker = marker
            elif active_marker == marker:
                active_marker = None
            visible.append("")
            continue
        visible.append("" if active_marker is not None else line)
    return visible


def expected_budget(complexity: int, importance: int) -> str:
    """根据复杂度、重要性及单维升级规则计算 standard/deep/full 预算。"""
    average = (complexity + importance) / 2
    if average >= 4 or max(complexity, importance) == 5:
        return "full"
    if average >= 3 or max(complexity, importance) == 4:
        return "deep"
    return "standard"


def has_spec3_marker(spec_dir: Path) -> bool:
    """判断目录中的 spec.md 是否包含代码围栏外的 spec_version: 3 标记。"""
    spec_md = spec_dir / "spec.md"
    if not spec_md.is_file():
        return False
    lines = _outside_fences(read_text(spec_md).splitlines())
    return any(SPEC3_MARKER_RE.match(line.strip()) for line in lines)


def looks_like_spec3(spec_dir: Path) -> bool:
    """识别 marker 完整或正在填写 iteration-7 风险头部的 spec3 包。"""
    spec_md = spec_dir / "spec.md"
    if not spec_md.is_file():
        return False
    lines = _outside_fences(read_text(spec_md).splitlines())
    return any(
        SPEC3_MARKER_RE.match(line.strip())
        or re.match(r"^>\s*adversarial_risk_version\s*:", line)
        for line in lines[:8]
    )


def _cells(row: str) -> list[str]:
    """把 Markdown 表格行拆成去除首尾空白的单元格列表。"""
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _section_bounds(lines: list[str], prefix: str) -> tuple[int | None, int]:
    """按标题前缀定位二级章节，返回开始索引和下一个二级章节索引。"""
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if (match := H2_RE.match(line)) and match.group(1).strip().startswith(prefix)
        ),
        None,
    )
    if start is None:
        return None, len(lines)
    end = next(
        (index for index in range(start + 1, len(lines)) if H2_RE.match(lines[index])),
        len(lines),
    )
    return start, end


def _section_occurrences(lines: list[str], prefix: str) -> list[int]:
    """返回指定二级章节前缀的全部出现位置，用于检测缺失和重复章节。"""
    return [
        index
        for index, line in enumerate(lines)
        if (match := H2_RE.match(line)) and match.group(1).strip().startswith(prefix)
    ]


def _first_table(
    lines: list[str], start: int, end: int,
) -> tuple[list[str] | None, list[tuple[int, list[str]]]]:
    """解析指定行区间内的第一张 Markdown 表格，并保留数据行原始行号。"""
    for index in range(start + 1, max(start + 1, end - 1)):
        if not lines[index].lstrip().startswith("|"):
            continue
        if index + 1 >= end or not TABLE_SEPARATOR_RE.match(lines[index + 1]):
            continue
        header = _cells(lines[index])
        rows: list[tuple[int, list[str]]] = []
        cursor = index + 2
        while cursor < end and lines[cursor].lstrip().startswith("|"):
            rows.append((cursor + 1, _cells(lines[cursor])))
            cursor += 1
        return header, rows
    return None, []


def _section_table(
    lines: list[str], prefix: str,
) -> tuple[list[str] | None, list[tuple[int, list[str]]]]:
    """定位指定二级章节并返回该章节中的第一张 Markdown 表格。"""
    start, end = _section_bounds(lines, prefix)
    if start is None:
        return None, []
    return _first_table(lines, start, end)


def _section_has_content(lines: list[str], prefix: str) -> bool:
    """判断指定二级章节是否包含三级标题之外的非空正文。"""
    start, end = _section_bounds(lines, prefix)
    if start is None:
        return False
    return any(line.strip() and not H3_RE.match(line) for line in lines[start + 1 : end])


def _metadata(lines: list[str]) -> tuple[dict[str, str], list[dict]]:
    """解析顶部七个固定元数据字段，并检查顺序、重复、空行和一级标题。"""
    values: dict[str, str] = {}
    issues: list[dict] = []
    for number, line in enumerate(lines, start=1):
        match = FIELD_RE.match(line)
        if match is None or match.group(1) not in HEADER_FIELDS:
            continue
        key, value = match.groups()
        if key in values:
            issues.append(issue("spec.md", number, "V19", f"元数据字段重复：{key}"))
        else:
            values[key] = value.strip()

    for index, key in enumerate(HEADER_FIELDS):
        number = index + 1
        if index >= len(lines):
            issues.append(issue(
                "spec.md", number, "V19", f"第 {number} 行必须为 > {key}: <值>",
            ))
            continue
        match = FIELD_RE.match(lines[index])
        if match is None or match.group(1) != key or not match.group(2).strip():
            issues.append(issue(
                "spec.md", number, "V19", f"第 {number} 行必须为 > {key}: <值>",
            ))
    if len(lines) < 8 or lines[7] != "":
        issues.append(issue("spec.md", 8, "V19", "七个元数据字段后第八行必须为空行"))
    if len(lines) < 9 or not (title := H1_RE.match(lines[8])) or title.group(1).strip() == "<spec-name>":
        issues.append(issue("spec.md", 9, "V19", "第九行必须为已填写的 # <spec-name>"))
    return values, issues


def _metadata_issues(lines: list[str], require_ready: bool) -> tuple[dict[str, str], list[dict]]:
    """校验版本、双评分、平均分、预算和审查状态，返回元数据及 V19 问题。"""
    metadata, issues = _metadata(lines)
    version = metadata.get("spec_version", "")
    if version != "3":
        issues.append(issue("spec.md", 1, "V19", "spec_version 必须为 3"))
    risk_version = metadata.get("adversarial_risk_version", "")
    if risk_version != "3":
        issues.append(issue(
            "spec.md", 2, "V19", "当前 iteration-7 要求 adversarial_risk_version 为 3",
        ))

    scores: dict[str, int] = {}
    for key, number in (("complexity", 3), ("importance", 4)):
        value = metadata.get(key, "")
        if not re.fullmatch(r"[1-5]", value):
            issues.append(issue("spec.md", number, "V19", f"{key} 必须为 1..5 的整数"))
        else:
            scores[key] = int(value)

    average_text = metadata.get("risk_average", "")
    average: float | None = None
    if not re.fullmatch(r"[1-5]\.[05]", average_text):
        issues.append(issue(
            "spec.md", 5, "V19", "risk_average 必须为 1.0..5.0 且以 .0 或 .5 结尾",
        ))
    else:
        average = float(average_text)

    budget = metadata.get("review_budget", "")
    if budget not in VALID_BUDGETS:
        issues.append(issue(
            "spec.md", 6, "V19", "review_budget 必须为 standard、deep 或 full",
        ))
    if len(scores) == 2:
        expected_average = (scores["complexity"] + scores["importance"]) / 2
        if average is not None and average != expected_average:
            issues.append(issue(
                "spec.md", 5, "V19", f"risk_average 应为 {expected_average:.1f}",
            ))
        required = expected_budget(scores["complexity"], scores["importance"])
        if budget and budget != required:
            issues.append(issue("spec.md", 6, "V19", f"review_budget 应为 {required}"))

    status = metadata.get("adversarial_review", "")
    if status not in VALID_STATUSES:
        issues.append(issue(
            "spec.md", 7, "V19",
            "adversarial_review 必须为 pending、skipped-standard 或 complete",
        ))
    elif status == "skipped-standard" and budget != "standard":
        issues.append(issue(
            "spec.md", 7, "V19", "skipped-standard 只适用于 standard 预算",
        ))
    elif status == "complete" and budget == "standard":
        issues.append(issue(
            "spec.md", 7, "V19", "standard 预算完成态必须为 skipped-standard",
        ))
    elif status == "pending" and require_ready:
        issues.append(issue(
            "spec.md", 7, "V19", "对抗性风险审查仍为 pending，阻断 x-req3",
        ))
    return metadata, issues


def _parse_scenarios(lines: list[str]) -> list[dict]:
    """解析 Scenarios 章节，汇总每个场景的标题、GWT、测试层、依据和来源。"""
    start, end = _section_bounds(lines, "Scenarios")
    if start is None:
        return []
    scenarios: list[dict] = []
    current: dict | None = None

    def close_current() -> None:
        """完成当前 Scenario 的字段统计并追加到解析结果。"""
        nonlocal current
        if current is None:
            return
        body = current["body"]
        gwt_matches = [
            (match.group(1).upper(), match.group(2).strip())
            for _line, value in body
            if (match := GWT_RE.match(value))
        ]
        current["gwt"] = {
            key: value for key, value in gwt_matches
        }
        current["gwt_counts"] = Counter(key for key, _value in gwt_matches)
        layers = [
            match.group(1).lower()
            for _line, value in body
            if (match := LAYER_RE.match(value))
        ]
        evidences = [
            match.group(1).strip()
            for _line, value in body
            if (match := EVIDENCE_RE.match(value))
        ]
        sources = [
            match.group(1).strip()
            for _line, value in body
            if (match := SOURCE_RE.match(value))
        ]
        current["layer"] = layers[0] if layers else None
        current["layer_count"] = len(layers)
        current["evidence"] = evidences[0] if evidences else None
        current["evidence_count"] = len(evidences)
        current["source"] = sources[0] if sources else None
        current["source_count"] = len(sources)
        scenarios.append(current)
        current = None

    for index in range(start + 1, end):
        line = lines[index]
        if match := SCENARIO_RE.match(line):
            close_current()
            current = {
                "id": match.group(1),
                "name": match.group(2).strip(),
                "line": index + 1,
                "body": [],
            }
        elif H3_RE.match(line):
            close_current()
        elif current is not None:
            current["body"].append((index + 1, line))
    close_current()
    return scenarios


def spec_scenarios(spec_md: Path) -> list[dict]:
    """读取 spec.md，排除代码围栏后返回结构化 Scenario 列表。"""
    if not spec_md.is_file():
        return []
    return _parse_scenarios(_outside_fences(read_text(spec_md).splitlines()))


def scenario_id_counts(spec_md: Path) -> Counter:
    """统计 spec.md 中每个 Scenario ID 的出现次数。"""
    return Counter(item["id"] for item in spec_scenarios(spec_md))


def boundary_module_names(spec_dir: Path) -> dict[str, str]:
    """从影响边界表提取模块名，返回标准化名称到原始名称的映射。"""
    spec_md = spec_dir / "spec.md"
    if not spec_md.is_file():
        return {}
    lines = _outside_fences(read_text(spec_md).splitlines())
    header, rows = _section_table(lines, "影响边界与不变量")
    if header != list(BOUNDARY_HEADER):
        return {}
    modules: dict[str, str] = {}
    for _line, row in rows:
        if not row:
            continue
        original = row[0].strip()
        normalized = normalize_module_name(original)
        if normalized:
            modules[normalized] = original
    return modules


def _package_issues(spec_dir: Path) -> list[dict]:
    """检查 spec3 根目录保持单文件结构，只允许 spec.md、隐藏项和 tasks/。"""
    issues: list[dict] = []
    try:
        entries = list(spec_dir.iterdir())
    except OSError:
        return issues
    for entry in entries:
        if entry.name.startswith(".") or entry.name == "spec.md":
            continue
        if entry.is_dir() and entry.name == "tasks":
            continue
        issues.append(issue(
            entry.name,
            0,
            "V19",
            f"spec3 单文件包根目录只允许 spec.md 和后续 tasks/：{entry.name}",
        ))
    return issues


def _required_section_issues(lines: list[str]) -> list[dict]:
    """检查固定二级章节的存在性、唯一性和关键章节非空要求。"""
    issues: list[dict] = []
    for section in REQUIRED_SECTIONS:
        occurrences = _section_occurrences(lines, section)
        if not occurrences:
            issues.append(issue("spec.md", 0, "V19", f"缺少二级节「{section}」"))
        elif len(occurrences) > 1:
            issues.append(issue(
                "spec.md", occurrences[1] + 1, "V19", f"二级节「{section}」重复",
            ))
    for section in ("任务目标", "非目标", "风险评分依据", "测试驱动开发"):
        if _section_occurrences(lines, section) and not _section_has_content(lines, section):
            issues.append(issue("spec.md", 0, "V19", f"二级节「{section}」内容为空"))
    return issues


def _template_placeholder_issues(lines: list[str]) -> list[dict]:
    """检测反引号代码之外仍未替换的尖括号模板占位符或注释。"""
    issues: list[dict] = []
    for number, line in enumerate(lines, start=1):
        prose = re.sub(r"`[^`]*`", "", line)
        placeholders = re.findall(r"<[^>\n]+>", prose)
        if placeholders:
            issues.append(issue(
                "spec.md",
                number,
                "V19",
                f"删除模板注释或占位符：{'、'.join(placeholders)}",
            ))
    return issues


def _risk_basis_issues(lines: list[str]) -> list[dict]:
    """检查风险评分依据包含非空的复杂度、重要性和预算升级说明。"""
    start, end = _section_bounds(lines, "风险评分依据")
    if start is None:
        return []
    issues: list[dict] = []
    for field in RISK_BASIS_FIELDS:
        match = next(
            (
                re.match(rf"^\s*[-*+]\s*{field}\s*[：:]\s*(.+?)\s*$", lines[index])
                for index in range(start + 1, end)
                if re.match(rf"^\s*[-*+]\s*{field}\s*[：:]", lines[index])
            ),
            None,
        )
        if match is None or not match.group(1).strip():
            issues.append(issue(
                "spec.md", start + 1, "V19", f"风险评分依据缺少非空「{field}」项",
            ))
    return issues


def _table_issues(lines: list[str], require_ready: bool) -> list[dict]:
    """校验影响边界、判断依据和建模覆盖三张核心表及其就绪条件。"""
    issues: list[dict] = []
    boundary_header, boundary_rows = _section_table(lines, "影响边界与不变量")
    if boundary_header != list(BOUNDARY_HEADER):
        issues.append(issue("spec.md", 0, "V19", "影响边界表必须使用固定六列表头"))
    elif not boundary_rows:
        issues.append(issue("spec.md", 0, "V19", "影响边界表至少需要一个模块"))
    else:
        for number, row in boundary_rows:
            missing = [
                BOUNDARY_HEADER[index]
                for index in range(len(BOUNDARY_HEADER))
                if index >= len(row) or not row[index].strip()
            ]
            if "主要风险" in missing:
                issues.append(issue(
                    "spec.md", number, "V19", "影响边界模块的主要风险为空",
                ))
                missing.remove("主要风险")
            if missing:
                issues.append(issue(
                    "spec.md", number, "V19",
                    f"影响边界行存在空字段：{'、'.join(missing)}",
                ))

    judgment_header, judgment_rows = _section_table(lines, "判断依据")
    if judgment_header != list(JUDGMENT_HEADER):
        issues.append(issue("spec.md", 0, "V19", "判断依据表必须使用固定五列表头"))
    elif not judgment_rows:
        issues.append(issue("spec.md", 0, "V19", "判断依据表至少需要一个判断"))
    else:
        ids: Counter = Counter()
        for number, row in judgment_rows:
            values = row + [""] * (len(JUDGMENT_HEADER) - len(row))
            judgment_id, judgment, source, evidence, status = values[:5]
            if not JUDGMENT_ID_RE.fullmatch(judgment_id):
                issues.append(issue(
                    "spec.md", number, "V19", "判断 J-ID 必须为 J1、J2 等稳定编号",
                ))
            ids[judgment_id] += 1
            empty = [
                JUDGMENT_HEADER[index]
                for index, value in enumerate(values[:5])
                if not value.strip()
            ]
            if empty:
                issues.append(issue(
                    "spec.md", number, "V19", f"判断依据行存在空字段：{'、'.join(empty)}",
                ))
            if status not in {"已确认", "待确认"}:
                issues.append(issue(
                    "spec.md", number, "V19",
                    f"判断 {judgment_id or '(未知 J-ID)'} 状态必须为 已确认 或 待确认",
                ))
            elif status == "待确认" and require_ready:
                issues.append(issue(
                    "spec.md", number, "V19",
                    f"判断 {judgment_id} 仍为待确认，spec3 不可交接 x-req3",
                ))
        for judgment_id, count in ids.items():
            if judgment_id and count > 1:
                issues.append(issue(
                    "spec.md", 0, "V19", f"判断 J-ID 重复：{judgment_id}",
                ))
            if judgment_id and count == 1:
                references = re.findall(
                    rf"(?<![A-Za-z0-9_-]){re.escape(judgment_id)}(?![A-Za-z0-9_-])",
                    "\n".join(lines),
                )
                if len(references) < 2:
                    issues.append(issue(
                        "spec.md", 0, "V19", f"判断 {judgment_id} 没有被边界或 Scenario 消费",
                    ))

    model_header, model_rows = _section_table(lines, "建模覆盖声明")
    if model_header != list(MODEL_HEADER):
        issues.append(issue("spec.md", 0, "V19", "建模覆盖声明必须使用固定两列表头"))
    else:
        model_counts = Counter(row[0].strip() for _line, row in model_rows if row)
        missing = [name for name in MODEL_TUPLE if model_counts[name] == 0]
        if missing:
            issues.append(issue(
                "spec.md", 0, "V19", f"建模覆盖声明缺少：{'、'.join(missing)}",
            ))
        for number, row in model_rows:
            if not row:
                continue
            dimension = row[0].strip()
            if dimension in MODEL_TUPLE and (
                len(row) < 2 or not row[1].strip()
            ):
                issues.append(issue(
                    "spec.md", number, "V19", f"建模覆盖「{dimension}」缺少锚点或不适用理由",
                ))
        duplicates = [name for name in MODEL_TUPLE if model_counts[name] > 1]
        if duplicates:
            issues.append(issue(
                "spec.md", 0, "V19", f"建模覆盖维度重复：{'、'.join(duplicates)}",
            ))
    return issues


def _acceptance_issues(lines: list[str]) -> list[dict]:
    """校验单元、Smoke、E2E 三层验收结构以及 E2E 决策和依据。"""
    issues: list[dict] = []
    start, end = _section_bounds(lines, "验收清单")
    if start is None:
        return issues
    headings: dict[str, tuple[int, int]] = {}
    h3_starts = [
        (index, match.group(1).strip())
        for index in range(start + 1, end)
        if (match := H3_RE.match(lines[index]))
    ]
    for position, (index, name) in enumerate(h3_starts):
        sub_end = h3_starts[position + 1][0] if position + 1 < len(h3_starts) else end
        headings[name] = (index, sub_end)
    for name in ("单元测试", "Smoke 测试", "E2E 测试"):
        if name not in headings:
            issues.append(issue("spec.md", start + 1, "V19", f"验收清单缺少 ### {name}"))
    for name in ("单元测试", "Smoke 测试"):
        if name not in headings:
            continue
        sub_start, sub_end = headings[name]
        if not any(line.strip() for line in lines[sub_start + 1 : sub_end]):
            issues.append(issue(
                "spec.md", sub_start + 1, "V19", f"{name}验收内容为空",
            ))
    if "E2E 测试" in headings:
        sub_start, sub_end = headings["E2E 测试"]
        body = lines[sub_start + 1 : sub_end]
        decision = next(
            (
                match.group(1)
                for line in body
                if (match := re.match(r"^\s*[-*+]?\s*决策\s*[：:]\s*(需要|省略)\s*$", line))
            ),
            None,
        )
        evidence = next(
            (
                match.group(1).strip()
                for line in body
                if (match := re.match(r"^\s*[-*+]?\s*依据\s*[：:]\s*(.+?)\s*$", line))
            ),
            None,
        )
        if decision is None:
            issues.append(issue(
                "spec.md", sub_start + 1, "V19", "E2E 测试必须明确写 决策：需要 或 决策：省略",
            ))
        if not evidence:
            issues.append(issue(
                "spec.md", sub_start + 1, "V19", "E2E 测试必须填写判定依据",
            ))
    return issues


def _review_issues(
    lines: list[str], metadata: dict[str, str],
) -> tuple[list[dict], set[str]]:
    """校验 ARV 审查记录、Top5/no-corpus/失败路径，并返回成功召回的风险 ID。"""
    issues: list[dict] = []
    recalled_ids: set[str] = set()
    header, rows = _section_table(lines, "对抗性审查记录")
    if header != list(REVIEW_HEADER):
        issues.append(issue("spec.md", 0, "V19", "对抗性审查记录必须使用固定八列表头"))
        return issues, recalled_ids

    status = metadata.get("adversarial_review", "")
    budget = metadata.get("review_budget", "")
    completed_rows = [
        (number, row) for number, row in rows if row and REVIEW_ID_RE.fullmatch(row[0].strip())
    ]
    if status in {"skipped-standard", "complete"} and not completed_rows:
        issues.append(issue(
            "spec.md", 0, "V19", "已完成审查缺少 ARV-n 记录行",
        ))

    for number, row in completed_rows:
        values = row + [""] * (len(REVIEW_HEADER) - len(row))
        values = values[: len(REVIEW_HEADER)]
        if any(not value.strip() for value in values):
            issues.append(issue(
                "spec.md", number, "V19", "ARV-n 记录的八个字段必须全部填写",
            ))
        if any("<" in value and ">" in value for value in values):
            issues.append(issue(
                "spec.md", number, "V19", "ARV-n 记录仍含模板占位符",
            ))
        if values[1] != budget:
            issues.append(issue(
                "spec.md", number, "V19", f"ARV-n 预算必须与 review_budget={budget} 一致",
            ))
        recalled = RISK_ID_RE.findall(values[4])
        cli = values[7]
        cli_fields = {
            key.strip(): value.strip()
            for segment in cli.split(";")
            if "=" in segment
            for key, value in [segment.split("=", 1)]
        }
        no_corpus = "skipped:no-corpus" in cli
        exit_match = re.search(r"\bexit\s*=\s*(\d+)\b", cli)
        exit_code = int(exit_match.group(1)) if exit_match else None
        exit_zero = exit_code == 0
        recall_failed = exit_code is not None and exit_code != 0
        source_tokens = [
            token.strip() for token in re.split(r"[；;]", values[2]) if token.strip()
        ]
        assumption_sources: list[str] = []
        for token in source_tokens:
            if token == "no-corpus":
                if not no_corpus:
                    issues.append(issue(
                        "spec.md", number, "V19",
                        "风险来源 no-corpus 只适用于 CLI=skipped:no-corpus",
                    ))
                continue
            if token == "无":
                if not (no_corpus or recall_failed):
                    issues.append(issue(
                        "spec.md", number, "V19",
                        "风险来源 无 只适用于无语料或召回失败路径",
                    ))
                continue
            if rag_match := REVIEW_RAG_SOURCE_RE.fullmatch(token):
                risk_id = rag_match.group("risk_id")
                if no_corpus:
                    issues.append(issue(
                        "spec.md", number, "V19",
                        "CLI=skipped:no-corpus 时风险来源不得包含 RAG ID",
                    ))
                if risk_id not in recalled:
                    issues.append(issue(
                        "spec.md", number, "V19",
                        f"风险来源引用的 RAG ID 未进入召回 ID 列：{risk_id}",
                    ))
                continue
            if assumption_match := REVIEW_ASSUMPTION_SOURCE_RE.fullmatch(token):
                assumption = assumption_match.group("assumption").strip()
                if assumption:
                    assumption_sources.append(assumption)
                    continue
            issues.append(issue(
                "spec.md", number, "V19",
                "风险来源必须由 RAG:AR-NNN、assumption:<非空说明>、"
                "无 或 no-corpus 组成",
            ))
        if exit_zero:
            recalled_ids.update(recalled)
            if not 1 <= len(recalled) <= 5 or len(set(recalled)) != len(recalled):
                issues.append(issue(
                    "spec.md", number, "V19",
                    "Top5 成功召回必须记录一至五个唯一风险 ID",
                ))
            matches_value = cli_fields.get("matches", "")
            if not matches_value.isdigit() or int(matches_value) != len(recalled):
                issues.append(issue(
                    "spec.md", number, "V19",
                    "Top5 成功召回的 CLI matches 必须等于召回 ID 数量",
                ))
        elif not no_corpus and not re.search(r"\bexit\s*=\s*\d+\b", cli):
            issues.append(issue(
                "spec.md", number, "V19",
                "CLI 必须记录 exit=<code> 与 matches，或写 skipped:no-corpus",
            ))
        if no_corpus and values[4] != "无":
            issues.append(issue(
                "spec.md", number, "V19",
                "CLI=skipped:no-corpus 时召回 ID 必须为 无",
            ))
        if recall_failed:
            if values[4] != "无":
                issues.append(issue(
                    "spec.md", number, "V19", "召回失败时召回 ID 必须为 无",
                ))
            if not re.search(r"\bmatches\s*=\s*0\b", cli):
                issues.append(issue(
                    "spec.md", number, "V19", "召回失败时 CLI 必须记录 matches=0",
                ))
            for field in ("error", "message"):
                if not cli_fields.get(field):
                    issues.append(issue(
                        "spec.md", number, "V19",
                        f"召回失败时 CLI 必须记录非空 {field}=<值>",
                    ))
        if status == "complete":
            if not no_corpus and not exit_zero:
                issues.append(issue(
                    "spec.md", number, "V19",
                    "deep/full 的 complete 状态要求 Top5 召回成功或 CLI=skipped:no-corpus",
                ))
            if no_corpus and not assumption_sources:
                issues.append(issue(
                    "spec.md", number, "V19",
                    "deep/full 无语料路径必须在风险来源记录 assumption:<短说明>",
                ))
            if budget == "full" and not assumption_sources:
                issues.append(issue(
                    "spec.md", number, "V19",
                    "full 预算必须记录一个独立 assumption 故障假设",
                ))
        if status == "skipped-standard" and values[6] != "无":
            issues.append(issue(
                "spec.md", number, "V19", "standard 路径必须保持新增 Scenario 为 无",
            ))
    return issues, recalled_ids


def _scenario_issues(
    lines: list[str],
    metadata: dict[str, str],
    recalled_ids: set[str],
) -> list[dict]:
    """校验 Scenario 编号、唯一字段、测试层、来源及 RAG 召回交叉引用。"""
    issues: list[dict] = []
    start, end = _section_bounds(lines, "Scenarios")
    if start is None:
        return issues
    for index in range(start + 1, end):
        if SCENARIO_HEADING_RE.match(lines[index]) and not SCENARIO_RE.match(lines[index]):
            issues.append(issue(
                "spec.md", index + 1, "V20",
                "Scenario 标题必须为 `### Scenario SC_01: <可判定行为名称>`",
            ))
    scenarios = _parse_scenarios(lines)
    if not scenarios:
        return [*issues, issue("spec.md", 0, "V20", "Scenarios 节至少需要一个 Scenario")]

    ids = Counter(item["id"] for item in scenarios)
    names = Counter(item["name"] for item in scenarios)
    actual_ids = [item["id"] for item in scenarios]
    expected_ids = [f"SC_{index:02d}" for index in range(1, len(scenarios) + 1)]
    if actual_ids != expected_ids:
        issues.append(issue(
            "spec.md", 0, "V20", "Scenario ID 必须从 SC_01 开始按文档顺序连续递增",
        ))

    status = metadata.get("adversarial_review", "")
    for item in scenarios:
        scenario_id = item["id"]
        name = item["name"] or "(空)"
        if ids[scenario_id] > 1:
            issues.append(issue(
                "spec.md", item["line"], "V20", f"Scenario ID 重复：{scenario_id}",
            ))
        if names[item["name"]] > 1:
            issues.append(issue("spec.md", item["line"], "V20", f"Scenario 名重名：{name}"))
        missing_gwt = [key for key in ("GIVEN", "WHEN", "THEN") if not item["gwt"].get(key)]
        if missing_gwt:
            issues.append(issue(
                "spec.md", item["line"], "V20",
                f"Scenario「{name}」缺少非空：{'、'.join(missing_gwt)}",
            ))
        duplicate_gwt = [
            key for key in ("GIVEN", "WHEN", "THEN") if item["gwt_counts"][key] > 1
        ]
        if duplicate_gwt:
            issues.append(issue(
                "spec.md", item["line"], "V20",
                f"Scenario「{name}」重复字段：{'、'.join(duplicate_gwt)}",
            ))
        if item["layer_count"] != 1:
            issues.append(issue(
                "spec.md", item["line"], "V20",
                f"Scenario「{name}」缺少唯一测试层 unit|smoke|e2e",
            ))
        if item["evidence_count"] != 1 or not item["evidence"]:
            issues.append(issue(
                "spec.md", item["line"], "V20", f"Scenario「{name}」必须填写唯一依据",
            ))
        source = item["source"]
        if item["source_count"] != 1:
            issues.append(issue(
                "spec.md", item["line"], "V20", f"Scenario「{name}」必须填写唯一来源",
            ))
        if source == "initial-spec":
            continue
        source_match = V3_SOURCE_RE.fullmatch(source or "")
        if source_match is None:
            issues.append(issue(
                "spec.md", item["line"], "V20",
                f"Scenario「{name}」来源必须为 initial-spec、"
                "adversarial-review (rag:AR-NNN) 或 "
                "adversarial-review (assumption:<短说明>)",
            ))
            continue
        assumption = source_match.group("assumption")
        if assumption is not None and not assumption.strip():
            issues.append(issue(
                "spec.md", item["line"], "V20",
                f"Scenario「{name}」的 assumption 来源说明不能为空",
            ))
            continue
        if status == "skipped-standard":
            issues.append(issue(
                "spec.md", item["line"], "V20", "standard 路径不允许扩张对抗性 Scenario",
            ))
        risk_id = source_match.group("risk_id")
        if risk_id and risk_id not in recalled_ids:
            issues.append(issue(
                "spec.md", item["line"], "V20",
                f"Scenario「{name}」引用的风险 ID 未进入 ARV-n 召回记录：{risk_id}",
            ))
    return issues


def validate_issues(spec_dir: Path, *, require_ready: bool = True) -> list[dict]:
    """聚合全部 iteration-7 spec3 机械校验；默认同时执行 x-req3 就绪门禁。"""
    spec_md = spec_dir / "spec.md"
    if not spec_md.is_file():
        return [issue("(package)", 0, "V19", "spec3 包缺少 spec.md")]
    lines = _outside_fences(read_text(spec_md).splitlines())
    metadata, issues = _metadata_issues(lines, require_ready)
    issues.extend(_package_issues(spec_dir))
    issues.extend(_required_section_issues(lines))
    issues.extend(_template_placeholder_issues(lines))
    issues.extend(_risk_basis_issues(lines))
    issues.extend(_table_issues(lines, require_ready))
    issues.extend(_acceptance_issues(lines))
    review_issues, recalled_ids = _review_issues(lines, metadata)
    issues.extend(review_issues)
    issues.extend(_scenario_issues(lines, metadata, recalled_ids))
    return issues


def validate_command(spec_dir: Path, *, as_json: bool, require_ready: bool) -> int:
    """执行一次目录校验，输出文本或 JSON，并按结果返回 0、1、2 退出码。"""
    try:
        issues = validate_issues(spec_dir, require_ready=require_ready)
    except OSError as exc:
        print(f"错误：读取 spec3 失败：{exc}", file=sys.stderr)
        return 2
    payload = {
        "path": str(spec_dir),
        "type": "spec3",
        "require_ready": require_ready,
        "issues": issues,
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"== {spec_dir}  [spec3]")
        if not issues:
            print("   ok")
        for item in issues:
            location = f"{item['file']}:{item['line']}" if item["line"] else item["file"]
            print(f"   {location}  {item['rule']}  {item['msg']}")
        mark = "✓" if not issues else "✗"
        print(f"{mark} validate：{len(issues)} issue(s)")
    return 0 if not issues else 1


def main(argv: list[str] | None = None) -> int:
    """解析独立 CLI 的 validate 子命令和 --json/--allow-pending 参数。"""
    parser = argparse.ArgumentParser(description="iteration-7 x-spec3 确定性校验")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="校验 spec3 单文件包")
    validate_parser.add_argument("spec_dir", type=Path)
    validate_parser.add_argument("--json", action="store_true")
    validate_parser.add_argument(
        "--allow-pending",
        action="store_true",
        help="只检查结构契约，允许 pending 审查与待确认判断",
    )
    args = parser.parse_args(argv)
    if args.command == "validate":
        return validate_command(
            args.spec_dir,
            as_json=args.json,
            require_ready=not args.allow_pending,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
