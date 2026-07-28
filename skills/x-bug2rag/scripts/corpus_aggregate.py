#!/usr/bin/env python3
"""Build and maintain a progressively disclosed risk corpus.

The aggregate corpus keeps full risk cards in stable Markdown shards while
generating two smaller discovery layers:

1. ``taxonomy.md``: a compact routing directory for the LLM.
2. ``indexes/*.md``: compact search views for LLM inspection and route tests.
3. ``indexes/*.jsonl``: deterministic machine indexes and locators.

Full cards remain the source of truth. Indexes and the manifest are generated
artifacts and can be rebuilt deterministically from ``shards/*.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


SCHEMA_VERSION = 1
DEFAULT_SHARD_SIZE = 200
FIELD_ORDER = (
    "关键词",
    "Risk",
    "场景",
    "错误实现",
    "正确实现",
    "可观察差异",
    "分类",
    "来源",
)
REQUIRED_FIELDS = FIELD_ORDER[:-1]
HEADING_RE = re.compile(r"(?m)^##[ \t]+(AR-(\d{3,}))[ \t]*$")
ANY_H2_RE = re.compile(r"(?m)^##[ \t]+(.+?)[ \t]*$")
FIELD_RE = re.compile(
    rf"^({'|'.join(re.escape(field) for field in FIELD_ORDER)})"
    r"[：:]\s*(.*?)\s*$"
)
SPLIT_RE = re.compile(r"[，,、；;]+")


@dataclass(frozen=True)
class Route:
    key: str
    label: str
    scope: str


ROUTES = (
    Route("state-machine", "状态机", "状态转换、恢复历史、非法跳跃和不变量"),
    Route("concurrency", "并发/时序", "重试并发、消息乱序、读写交错和部分失败"),
    Route("idempotency", "幂等/唯一", "重复副作用、唯一键冲突和去重边界"),
    Route("boundary-default", "边界/默认值", "空值、零值、缺失输入、边界和默认行为"),
    Route("authorization", "权限/越权", "身份、租户、能力白名单、审批和访问边界"),
    Route("resource-lifecycle", "资源生命周期", "超时、取消、清理、句柄和资源耗尽"),
    Route("persistence", "持久化一致性", "多阶段提交、索引正文一致性和崩溃恢复"),
    Route("sensitive-data", "数据敏感", "PII、secret、日志、错误信息和枚举风险"),
)
ROUTE_BY_LABEL = {route.label: route for route in ROUTES}


class AggregateError(ValueError):
    """User-facing aggregate-corpus contract error."""


@dataclass(frozen=True)
class RiskEntry:
    id: str
    fields: dict[str, str]

    @property
    def number(self) -> int:
        return int(self.id.split("-", 1)[1])

    @property
    def risk(self) -> str:
        return self.fields["Risk"]

    def render(self) -> str:
        lines = [f"## {self.id}", ""]
        for field in FIELD_ORDER:
            value = self.fields.get(field, "")
            if value:
                lines.append(f"{field}：{value}")
        return "\n".join(lines).rstrip() + "\n"


def _split_values(value: str) -> list[str]:
    return [part.strip() for part in SPLIT_RE.split(value) if part.strip()]


def _route_for_label(label: str) -> Route:
    known = ROUTE_BY_LABEL.get(label)
    if known is not None:
        return known
    digest = hashlib.sha1(label.encode("utf-8")).hexdigest()[:8]
    return Route(f"other-{digest}", label, f"{label} 类失败机制")


def _parse_section(risk_id: str, body: str, source: str) -> RiskEntry:
    fields: dict[str, str] = {}
    for number, line in enumerate(body.splitlines(), start=1):
        if not line.strip():
            continue
        match = FIELD_RE.fullmatch(line)
        if match is None:
            raise AggregateError(
                f"{source}: {risk_id} 包含未知内容（section 行 {number}）：{line}"
            )
        field, value = match.groups()
        if field in fields:
            raise AggregateError(f"{source}: {risk_id} 字段重复：{field}")
        fields[field] = value.strip()

    missing = [field for field in REQUIRED_FIELDS if not fields.get(field)]
    if missing:
        raise AggregateError(
            f"{source}: {risk_id} 缺少非空字段：" + "、".join(missing)
        )
    return RiskEntry(id=risk_id, fields=fields)


def parse_entries(text: str, *, source: str) -> list[RiskEntry]:
    headings = list(HEADING_RE.finditer(text))
    all_h2 = [match.group(1) for match in ANY_H2_RE.finditer(text)]
    valid_h2 = [match.group(1) for match in headings]
    invalid_h2 = [heading for heading in all_h2 if heading not in valid_h2]
    if invalid_h2:
        raise AggregateError(
            f"{source}: 二级标题必须使用 AR-NNN，发现：" + "、".join(invalid_h2)
        )
    if not headings:
        raise AggregateError(f"{source}: corpus 缺少风险条目")

    entries: list[RiskEntry] = []
    seen: set[str] = set()
    for index, heading in enumerate(headings):
        risk_id = heading.group(1)
        if risk_id in seen:
            raise AggregateError(f"{source}: 风险 ID 重复：{risk_id}")
        seen.add(risk_id)
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[heading.end():end]
        entries.append(_parse_section(risk_id, body, source))

    numbers = [entry.number for entry in entries]
    if numbers != sorted(numbers):
        raise AggregateError(f"{source}: 风险条目必须按 ID 升序排列")
    return entries


def _ensure_global_contract(entries: Sequence[RiskEntry]) -> None:
    ids = [entry.id for entry in entries]
    if len(ids) != len(set(ids)):
        raise AggregateError("聚合 corpus 存在重复风险 ID")
    risks = [entry.risk for entry in entries]
    duplicates = sorted(risk for risk, count in Counter(risks).items() if count > 1)
    if duplicates:
        raise AggregateError("聚合 corpus 存在重复 Risk：" + "；".join(duplicates))
    numbers = [entry.number for entry in entries]
    if numbers != sorted(numbers):
        raise AggregateError("聚合 corpus 必须按风险 ID 升序排列")


def validate_flat_corpus(path: Path) -> list[str]:
    """Validate one rich-card Markdown catalog with this skill's own contract."""
    try:
        text = path.read_text(encoding="utf-8")
        entries = parse_entries(text, source=str(path))
        _ensure_global_contract(entries)
    except (AggregateError, OSError, UnicodeError) as exc:
        return [str(exc)]
    return []


def _shard_bounds(number: int, shard_size: int) -> tuple[int, int]:
    start = ((number - 1) // shard_size) * shard_size + 1
    return start, start + shard_size - 1


def _shard_path(number: int, shard_size: int) -> str:
    start, end = _shard_bounds(number, shard_size)
    return f"shards/risk-{start:06d}-{end:06d}.md"


def _compact_record(entry: RiskEntry, shard_size: int) -> dict[str, object]:
    keywords = _split_values(entry.fields["关键词"])
    categories = _split_values(entry.fields["分类"])
    locator = {
        "shard": _shard_path(entry.number, shard_size),
        "section": entry.id,
    }
    text = "\n".join(
        (
            f"ID：{entry.id}",
            f"关键词：{'、'.join(keywords)}",
            f"分类：{'、'.join(categories)}",
            f"失败机制：{entry.fields['Risk']}",
            f"触发条件：{entry.fields['场景']}",
            f"可观察结果：{entry.fields['可观察差异']}",
            f"详情：{locator['shard']}#{entry.id}",
        )
    )
    return {
        "id": entry.id,
        "keywords": keywords,
        "categories": categories,
        "mechanism": entry.fields["Risk"],
        "trigger": entry.fields["场景"],
        "effect": entry.fields["可观察差异"],
        "summary": entry.fields["Risk"],
        "locator": locator,
        "text": text,
    }


def _jsonl(records: Iterable[dict[str, object]]) -> str:
    return "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    )


def _compact_markdown(records: Iterable[dict[str, object]]) -> str:
    sections = [
        f"## {record['id']}\n\n{record['text']}"
        for record in records
    ]
    return "\n\n".join(sections).rstrip() + "\n"


def _taxonomy(entries: Sequence[RiskEntry]) -> tuple[str, dict[str, list[RiskEntry]]]:
    grouped: dict[str, list[RiskEntry]] = {}
    route_meta: dict[str, Route] = {}
    for entry in entries:
        for label in _split_values(entry.fields["分类"]):
            route = _route_for_label(label)
            grouped.setdefault(route.key, []).append(entry)
            route_meta[route.key] = route

    lines = [
        "# 风险路由目录",
        "",
        f"> schema_version: {SCHEMA_VERSION}",
        f"> entry_count: {len(entries)}",
        "> 使用：从问题提取对象、动作、失败机制、触发条件和可观察结果；选择所有相关节点；一次搜索这些节点的二级索引；按 ID 批量读取详情。",
        "",
    ]
    ordered_routes = list(ROUTES)
    known_keys = {route.key for route in ROUTES}
    ordered_routes.extend(
        route_meta[key] for key in sorted(route_meta) if key not in known_keys
    )
    for route in ordered_routes:
        route_entries = grouped.get(route.key, [])
        keywords = Counter(
            keyword
            for entry in route_entries
            for keyword in _split_values(entry.fields["关键词"])
        )
        common = [
            keyword
            for keyword, _ in sorted(
                keywords.items(),
                key=lambda item: (-item[1], item[0]),
            )[:12]
        ]
        index_path = f"indexes/{route.key}.md" if route_entries else "无（当前 0 条）"
        lines.extend(
            (
                f"## {route.key.upper()} — {route.label}",
                "",
                f"范围：{route.scope}",
                f"条目数：{len(route_entries)}",
                f"典型关键词：{'、'.join(common) if common else '无'}",
                f"二级索引：{index_path}",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n", grouped


def render_layout(
    entries: Sequence[RiskEntry],
    *,
    shard_size: int,
) -> dict[str, str]:
    if shard_size < 1:
        raise AggregateError("shard-size 必须大于等于 1")
    _ensure_global_contract(entries)
    if not entries:
        raise AggregateError("聚合 corpus 至少需要一条风险经验")

    files: dict[str, str] = {}
    by_shard: dict[str, list[RiskEntry]] = {}
    for entry in entries:
        by_shard.setdefault(_shard_path(entry.number, shard_size), []).append(entry)
    for path, shard_entries in by_shard.items():
        files[path] = "\n".join(
            entry.render().rstrip() for entry in shard_entries
        ).rstrip() + "\n"

    taxonomy, grouped = _taxonomy(entries)
    files["taxonomy.md"] = taxonomy
    records = [_compact_record(entry, shard_size) for entry in entries]
    files["indexes/all.jsonl"] = _jsonl(records)
    files["indexes/all.md"] = _compact_markdown(records)
    files["indexes/locator.jsonl"] = _jsonl(
        {"id": record["id"], "locator": record["locator"]}
        for record in records
    )
    record_by_id = {str(record["id"]): record for record in records}
    for route_key, route_entries in grouped.items():
        route_records = [record_by_id[entry.id] for entry in route_entries]
        files[f"indexes/{route_key}.jsonl"] = _jsonl(route_records)
        files[f"indexes/{route_key}.md"] = _compact_markdown(route_records)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "entry_count": len(entries),
        "shard_size": shard_size,
        "first_id": entries[0].id,
        "last_id": entries[-1].id,
        "taxonomy": "taxonomy.md",
        "all_index": "indexes/all.jsonl",
        "all_search_view": "indexes/all.md",
        "locator_index": "indexes/locator.jsonl",
        "shards": sorted(by_shard),
    }
    files["manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return files


def _write_empty_layout(target: Path, files: dict[str, str]) -> None:
    target.mkdir(parents=True, exist_ok=False)
    for relative, content in sorted(files.items()):
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _replace_layout(target: Path, files: dict[str, str]) -> None:
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{target.name}-stage-",
        dir=parent,
    ) as raw_stage:
        stage = Path(raw_stage) / target.name
        _write_empty_layout(stage, files)
        if not target.exists():
            stage.replace(target)
            return
        if not target.is_dir():
            raise AggregateError(f"目标必须是目录：{target}")
        backup = Path(raw_stage) / f"{target.name}.backup"
        target.replace(backup)
        try:
            stage.replace(target)
        except OSError:
            backup.replace(target)
            raise
        shutil.rmtree(backup)


def _load_manifest(target: Path) -> dict[str, object]:
    path = target / "manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AggregateError(f"聚合 manifest 不可读：{path}: {exc}") from exc
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise AggregateError(
            f"manifest schema_version 必须为 {SCHEMA_VERSION}"
        )
    shard_size = payload.get("shard_size")
    if not isinstance(shard_size, int) or shard_size < 1:
        raise AggregateError("manifest shard_size 必须是正整数")
    return payload


def load_aggregate(target: Path) -> tuple[list[RiskEntry], int]:
    if not target.is_dir():
        raise AggregateError(f"聚合 corpus 目录不存在：{target}")
    manifest = _load_manifest(target)
    shard_size = int(manifest["shard_size"])
    shard_paths = sorted((target / "shards").glob("risk-*.md"))
    if not shard_paths:
        raise AggregateError(f"{target}: shards 目录缺少风险分片")
    entries: list[RiskEntry] = []
    for path in shard_paths:
        entries.extend(
            parse_entries(path.read_text(encoding="utf-8"), source=str(path))
        )
    _ensure_global_contract(entries)
    return entries, shard_size


def validate_layout(target: Path) -> list[str]:
    try:
        entries, shard_size = load_aggregate(target)
        expected = render_layout(entries, shard_size=shard_size)
    except (AggregateError, OSError, UnicodeError) as exc:
        return [str(exc)]

    issues: list[str] = []
    expected_paths = set(expected)
    actual_paths = {
        str(path.relative_to(target))
        for path in target.rglob("*")
        if path.is_file()
    }
    for missing in sorted(expected_paths - actual_paths):
        issues.append(f"缺少生成文件：{missing}")
    for stale in sorted(actual_paths - expected_paths):
        issues.append(f"存在未登记文件：{stale}")
    for relative, content in sorted(expected.items()):
        path = target / relative
        if path.is_file() and path.read_text(encoding="utf-8") != content:
            issues.append(f"生成文件与分片事实不一致：{relative}")
    return issues


def build_aggregate(
    source: Path,
    target: Path,
    *,
    shard_size: int,
) -> list[RiskEntry]:
    if target.exists():
        raise AggregateError(f"目标已存在，停止覆盖：{target}")
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AggregateError(f"源 corpus 不可读：{source}: {exc}") from exc
    entries = parse_entries(text, source=str(source))
    files = render_layout(entries, shard_size=shard_size)
    _replace_layout(target, files)
    return entries


def rebuild_aggregate(target: Path) -> list[RiskEntry]:
    entries, shard_size = load_aggregate(target)
    _replace_layout(target, render_layout(entries, shard_size=shard_size))
    return entries


def append_entry(
    target: Path,
    fields: dict[str, str],
    *,
    dry_run: bool = False,
) -> RiskEntry:
    entries, shard_size = load_aggregate(target)
    missing = [field for field in REQUIRED_FIELDS if not fields.get(field)]
    if missing:
        raise AggregateError("缺少非空字段：" + "、".join(missing))
    risk = fields["Risk"].strip()
    for existing in entries:
        if existing.risk == risk:
            raise AggregateError(f"Risk 已存在：{existing.id}")
    next_number = max(entry.number for entry in entries) + 1
    entry = RiskEntry(
        id=f"AR-{next_number:03d}",
        fields={field: fields.get(field, "").strip() for field in FIELD_ORDER},
    )
    if not dry_run:
        updated = [*entries, entry]
        _replace_layout(target, render_layout(updated, shard_size=shard_size))
    return entry


def read_entries(target: Path, ids: Sequence[str]) -> list[dict[str, str]]:
    entries, shard_size = load_aggregate(target)
    by_id = {entry.id: entry for entry in entries}
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for risk_id in ids:
        if risk_id in seen:
            continue
        seen.add(risk_id)
        entry = by_id.get(risk_id)
        if entry is None:
            raise AggregateError(f"风险 ID 不存在：{risk_id}")
        selected.append(
            {
                "id": entry.id,
                "source": str((target / _shard_path(entry.number, shard_size)).resolve()),
                "text": entry.render().rstrip(),
            }
        )
    return selected


def select_routes(
    target: Path,
    routes: Sequence[str],
    output: Path,
) -> list[str]:
    entries, shard_size = load_aggregate(target)
    selected = _entries_for_routes(entries, routes)
    if output.exists() and output.read_bytes():
        raise AggregateError(f"输出文件已有内容，停止覆盖：{output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    records = [_compact_record(entry, shard_size) for entry in selected]
    output.write_text(_compact_markdown(records), encoding="utf-8")
    return [entry.id for entry in selected]


def _entries_for_routes(
    entries: Sequence[RiskEntry],
    routes: Sequence[str],
) -> list[RiskEntry]:
    selected_routes = {route.strip().lower() for route in routes if route.strip()}
    if not selected_routes:
        raise AggregateError("至少需要一个 route")
    known_routes = {
        _route_for_label(label).key
        for entry in entries
        for label in _split_values(entry.fields["分类"])
    }
    unknown = sorted(selected_routes - known_routes - {"all"})
    if unknown:
        raise AggregateError("未知 route：" + "、".join(unknown))

    selected = [
        entry
        for entry in entries
        if "all" in selected_routes
        or selected_routes.intersection(
            _route_for_label(label).key
            for label in _split_values(entry.fields["分类"])
        )
    ]
    if not selected:
        raise AggregateError("所选 route 没有候选条目")
    return selected


def _search_terms(text: str) -> Counter[str]:
    lowered = text.lower()
    terms: Counter[str] = Counter(
        re.findall(r"[a-z0-9_][a-z0-9_.-]*", lowered)
    )
    for sequence in re.findall(r"[\u3400-\u9fff]+", lowered):
        if len(sequence) == 1:
            terms[sequence] += 1
            continue
        for size in (2, 3):
            if len(sequence) < size:
                continue
            for index in range(len(sequence) - size + 1):
                terms[sequence[index:index + size]] += 1
    return terms


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(term, 0) for term, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def search_entries(
    target: Path,
    *,
    query: str,
    routes: Sequence[str],
    top_n: int,
) -> list[dict[str, object]]:
    if not query.strip():
        raise AggregateError("query 不能为空")
    if top_n < 1:
        raise AggregateError("top-n 必须大于等于 1")
    entries, shard_size = load_aggregate(target)
    candidates = _entries_for_routes(entries, routes)
    query_terms = _search_terms(query)
    weighted_fields = (
        ("关键词", 3.0),
        ("Risk", 4.0),
        ("场景", 2.0),
        ("可观察差异", 3.0),
        ("分类", 1.5),
    )
    ranked: list[tuple[float, RiskEntry]] = []
    for entry in candidates:
        score = sum(
            weight * _cosine(query_terms, _search_terms(entry.fields[field]))
            for field, weight in weighted_fields
        )
        if score > 0:
            ranked.append((score, entry))
    ranked.sort(key=lambda item: (-item[0], item[1].number))

    matches: list[dict[str, object]] = []
    for score, entry in ranked[:top_n]:
        record = _compact_record(entry, shard_size)
        matches.append(
            {
                "id": entry.id,
                "score": round(score, 6),
                "summary": record["summary"],
                "locator": record["locator"],
                "text": record["text"],
            }
        )
    return matches


def _field_arguments(parser: argparse.ArgumentParser) -> None:
    for field, option in (
        ("关键词", "keywords"),
        ("Risk", "risk"),
        ("场景", "scene"),
        ("错误实现", "wrong"),
        ("正确实现", "correct"),
        ("可观察差异", "observable"),
        ("分类", "category"),
        ("来源", "source"),
    ):
        parser.add_argument(f"--{option}", dest=field, default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build")
    build.add_argument("--source", required=True)
    build.add_argument("--target", required=True)
    build.add_argument("--shard-size", type=int, default=DEFAULT_SHARD_SIZE)

    rebuild = commands.add_parser("rebuild")
    rebuild.add_argument("--target", required=True)

    validate = commands.add_parser("validate")
    validate.add_argument("--target", required=True)

    validate_flat = commands.add_parser("validate-flat")
    validate_flat.add_argument("--target", required=True)

    append = commands.add_parser("append")
    append.add_argument("--target", required=True)
    append.add_argument("--dry-run", action="store_true")
    _field_arguments(append)

    read = commands.add_parser("read")
    read.add_argument("--target", required=True)
    read.add_argument("--ids", nargs="+", required=True)

    select = commands.add_parser("select")
    select.add_argument("--target", required=True)
    select.add_argument("--routes", nargs="+", required=True)
    select.add_argument("--output", required=True)

    search = commands.add_parser("search")
    search.add_argument("--target", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--routes", nargs="+", default=["all"])
    search.add_argument("--top-n", type=int, default=5)
    for command in (
        build,
        rebuild,
        validate,
        validate_flat,
        append,
        read,
        select,
        search,
    ):
        command.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build":
            entries = build_aggregate(
                Path(args.source),
                Path(args.target),
                shard_size=args.shard_size,
            )
            payload = {
                "command": "build",
                "target": args.target,
                "entry_count": len(entries),
                "first_id": entries[0].id,
                "last_id": entries[-1].id,
                "valid": True,
            }
        elif args.command == "rebuild":
            entries = rebuild_aggregate(Path(args.target))
            payload = {
                "command": "rebuild",
                "target": args.target,
                "entry_count": len(entries),
                "valid": True,
            }
        elif args.command == "validate":
            issues = validate_layout(Path(args.target))
            payload = {
                "command": "validate",
                "target": args.target,
                "valid": not issues,
                "issues": issues,
            }
            _emit(payload, args.as_json)
            return 1 if issues else 0
        elif args.command == "validate-flat":
            issues = validate_flat_corpus(Path(args.target))
            payload = {
                "command": "validate-flat",
                "target": args.target,
                "valid": not issues,
                "issues": issues,
            }
            _emit(payload, args.as_json)
            return 1 if issues else 0
        elif args.command == "append":
            fields = {field: getattr(args, field).strip() for field in FIELD_ORDER}
            entry = append_entry(
                Path(args.target),
                fields,
                dry_run=args.dry_run,
            )
            payload = {
                "command": "append",
                "target": args.target,
                "dry_run": args.dry_run,
                "stored": [] if args.dry_run else [entry.id],
                "preview_id": entry.id if args.dry_run else None,
                "section": entry.render().rstrip() if args.dry_run else None,
                "valid": True,
            }
        elif args.command == "read":
            matches = read_entries(Path(args.target), args.ids)
            payload = {
                "command": "read",
                "target": args.target,
                "matches": matches,
                "valid": True,
            }
        elif args.command == "select":
            selected_ids = select_routes(
                Path(args.target),
                args.routes,
                Path(args.output),
            )
            payload = {
                "command": "select",
                "target": args.target,
                "routes": args.routes,
                "output": args.output,
                "selected_count": len(selected_ids),
                "selected_ids": selected_ids,
                "valid": True,
            }
        else:
            matches = search_entries(
                Path(args.target),
                query=args.query,
                routes=args.routes,
                top_n=args.top_n,
            )
            payload = {
                "command": "search",
                "target": args.target,
                "query": args.query,
                "routes": args.routes,
                "top_n": args.top_n,
                "matches": matches,
                "valid": True,
            }
    except (AggregateError, OSError, UnicodeError) as exc:
        _emit(
            {
                "command": args.command,
                "valid": False,
                "error": str(exc),
            },
            args.as_json,
        )
        return 1
    _emit(payload, args.as_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
