#!/usr/bin/env python3
"""Deterministic x-spec2 evaluation metrics.

The extractor accepts one explicit execution source:

* a completed Codex rollout JSONL, or
* a timing.json captured from a subagent completion notification.

It never scans session directories and never copies prompts or transcript content
into measurement.json.  Exit codes follow the repository convention: 0 success,
1 readable but invalid sample/pair, 2 usage, IO, JSON, or schema error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


CONFIGURATIONS = ("with_skill", "without_skill")
TOKEN_KEYS = ("input", "cached_input", "output", "reasoning_output", "total")


class MetricsError(ValueError):
    """Input cannot be parsed or does not satisfy the declared schema."""


class InvalidSample(ValueError):
    """Input is readable, but the measurement boundary or comparison is invalid."""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _non_negative_int(value: object, field: str) -> int:
    if not _is_int(value) or value < 0:
        raise MetricsError(f"{field} 必须是非负整数")
    return value


def _non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MetricsError(f"{field} 必须是非空字符串")
    return value.strip()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MetricsError(f"无法读取 JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MetricsError(f"JSON 顶层必须是 object: {path}")
    return value


def parse_timestamp(value: object, field: str) -> datetime:
    raw = _non_empty_string(value, field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MetricsError(f"{field} 不是合法 ISO-8601 时间: {raw}") from exc
    if parsed.tzinfo is None:
        raise MetricsError(f"{field} 必须包含时区: {raw}")
    return parsed


def prompt_hash(prompt: str) -> str:
    return "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def validate_metadata(value: dict[str, Any]) -> dict[str, Any]:
    required = (
        "eval_id",
        "eval_name",
        "configuration",
        "run_number",
        "prompt",
        "model",
        "repo_sha",
        "executor_inputs",
        "grader_only_inputs",
        "rubric_exposed",
    )
    missing = [key for key in required if key not in value]
    if missing:
        raise MetricsError(f"metadata 缺少字段: {', '.join(missing)}")

    eval_id = _non_negative_int(value["eval_id"], "metadata.eval_id")
    run_number = _non_negative_int(value["run_number"], "metadata.run_number")
    if eval_id == 0 or run_number == 0:
        raise MetricsError("metadata.eval_id 与 run_number 必须大于 0")
    configuration = _non_empty_string(value["configuration"], "metadata.configuration")
    if configuration not in CONFIGURATIONS:
        raise MetricsError(f"metadata.configuration 必须是 {'|'.join(CONFIGURATIONS)}")

    executor_inputs = value["executor_inputs"]
    grader_only_inputs = value["grader_only_inputs"]
    if not isinstance(executor_inputs, list) or not all(isinstance(item, str) for item in executor_inputs):
        raise MetricsError("metadata.executor_inputs 必须是字符串数组")
    if not isinstance(grader_only_inputs, list) or not all(isinstance(item, str) for item in grader_only_inputs):
        raise MetricsError("metadata.grader_only_inputs 必须是字符串数组")
    overlap = sorted(set(executor_inputs) & set(grader_only_inputs))
    if overlap:
        raise InvalidSample(f"executor 与 grader 输入重叠: {', '.join(overlap)}")
    if value["rubric_exposed"] is not False:
        raise InvalidSample("run metadata 标记 rubric exposure")

    return {
        "eval_id": eval_id,
        "eval_name": _non_empty_string(value["eval_name"], "metadata.eval_name"),
        "configuration": configuration,
        "run_number": run_number,
        "prompt": _non_empty_string(value["prompt"], "metadata.prompt"),
        "model": _non_empty_string(value["model"], "metadata.model"),
        "repo_sha": _non_empty_string(value["repo_sha"], "metadata.repo_sha"),
        "executor_inputs": executor_inputs,
        "grader_only_inputs": grader_only_inputs,
    }


def grading_quality(value: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    expectations = value.get("expectations")
    if not isinstance(expectations, list) or not expectations:
        raise MetricsError("grading.expectations 必须是非空数组")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(expectations, start=1):
        if not isinstance(item, dict):
            raise MetricsError(f"grading.expectations[{index}] 必须是 object")
        text = _non_empty_string(item.get("text"), f"grading.expectations[{index}].text")
        passed = item.get("passed")
        if not isinstance(passed, bool):
            raise MetricsError(f"grading.expectations[{index}].passed 必须是 boolean")
        evidence = _non_empty_string(item.get("evidence"), f"grading.expectations[{index}].evidence")
        normalized.append({"text": text, "passed": passed, "evidence": evidence})

    passed_count = sum(1 for item in normalized if item["passed"])
    total = len(normalized)
    quality = {"passed": passed_count, "total": total, "pass_rate": passed_count / total}
    summary = value.get("summary")
    if isinstance(summary, dict):
        expected = (summary.get("passed"), summary.get("total"), summary.get("pass_rate"))
        actual = (passed_count, total, quality["pass_rate"])
        if expected[0] != actual[0] or expected[1] != actual[1]:
            raise MetricsError("grading.summary 与逐项 expectation 统计不一致")
        if not isinstance(expected[2], (int, float)) or isinstance(expected[2], bool):
            raise MetricsError("grading.summary.pass_rate 必须是数字")
        if not math.isclose(float(expected[2]), actual[2], abs_tol=1e-9):
            raise MetricsError("grading.summary.pass_rate 与逐项 expectation 统计不一致")
    return quality, normalized


def parse_timing_source(path: Path) -> dict[str, Any]:
    value = read_json(path)
    agent_id = _non_empty_string(value.get("agent_id"), "timing.agent_id")
    total = _non_negative_int(value.get("total_tokens"), "timing.total_tokens")
    duration = _non_negative_int(value.get("duration_ms"), "timing.duration_ms")
    return {
        "source": {"kind": "subagent_notification", "id": agent_id},
        "model": None,
        "repo_sha": None,
        "started_at": None,
        "ended_at": None,
        "duration_ms": duration,
        "tokens": {
            "input": None,
            "cached_input": None,
            "output": None,
            "reasoning_output": None,
            "total": total,
        },
    }


def parse_rollout_source(path: Path, grader_only_inputs: list[str]) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MetricsError(f"无法读取 session {path}: {exc}") from exc
    for grader_input in grader_only_inputs:
        if grader_input and grader_input in raw_text:
            raise InvalidSample(f"session 读取了 grader-only input: {grader_input}")

    rows: list[tuple[int, dict[str, Any], datetime]] = []
    for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise MetricsError(f"session 第 {line_number} 行 JSON 损坏: {exc}") from exc
        if not isinstance(row, dict):
            raise MetricsError(f"session 第 {line_number} 行必须是 object")
        timestamp = parse_timestamp(row.get("timestamp"), f"session[{line_number}].timestamp")
        rows.append((line_number, row, timestamp))
    if not rows:
        raise MetricsError("session 为空")

    session_ids: set[str] = set()
    repo_shas: set[str] = set()
    for _line, row, _timestamp in rows:
        if row.get("type") != "session_meta" or not isinstance(row.get("payload"), dict):
            continue
        payload = row["payload"]
        canonical_id = payload.get("id")
        if not isinstance(canonical_id, str) or not canonical_id:
            canonical_id = payload.get("session_id")
        if isinstance(canonical_id, str) and canonical_id:
            session_ids.add(canonical_id)
        git = payload.get("git")
        if isinstance(git, dict) and isinstance(git.get("commit_hash"), str) and git["commit_hash"]:
            repo_shas.add(git["commit_hash"])
    if len(session_ids) != 1:
        raise InvalidSample(f"session ID 数量必须为 1，实际 {len(session_ids)}")
    if len(repo_shas) != 1:
        raise InvalidSample(f"repo SHA 数量必须为 1，实际 {len(repo_shas)}")

    turns = [item for item in rows if item[1].get("type") == "turn_context"]
    if len(turns) != 1:
        raise InvalidSample(f"turn_context 数量必须为 1，实际 {len(turns)}")
    turn_payload = turns[0][1].get("payload")
    if not isinstance(turn_payload, dict):
        raise MetricsError("turn_context.payload 必须是 object")
    model = _non_empty_string(turn_payload.get("model"), "turn_context.payload.model")

    completions = [
        item for item in rows
        if item[1].get("type") == "event_msg"
        and isinstance(item[1].get("payload"), dict)
        and item[1]["payload"].get("type") == "task_complete"
    ]
    if len(completions) != 1:
        raise InvalidSample(f"task_complete 数量必须为 1，实际 {len(completions)}")
    completed_at = completions[0][2]

    snapshots: list[tuple[datetime, dict[str, Any]]] = []
    for _line, row, timestamp in rows:
        payload = row.get("payload")
        if row.get("type") != "event_msg" or not isinstance(payload, dict):
            continue
        if payload.get("type") != "token_count" or timestamp > completed_at:
            continue
        info = payload.get("info")
        total_usage = info.get("total_token_usage") if isinstance(info, dict) else None
        if isinstance(total_usage, dict):
            snapshots.append((timestamp, total_usage))
    if not snapshots:
        raise InvalidSample("task_complete 之前缺少累计 token_count")
    _snapshot_time, usage = max(snapshots, key=lambda item: item[0])

    started_at = turns[0][2]
    if completed_at < started_at:
        raise MetricsError("task_complete 时间早于 turn_context")
    duration_ms = round((completed_at - started_at).total_seconds() * 1000)
    tokens = {
        "input": _non_negative_int(usage.get("input_tokens"), "token.input_tokens"),
        "cached_input": _non_negative_int(usage.get("cached_input_tokens"), "token.cached_input_tokens"),
        "output": _non_negative_int(usage.get("output_tokens"), "token.output_tokens"),
        "reasoning_output": _non_negative_int(
            usage.get("reasoning_output_tokens"), "token.reasoning_output_tokens"
        ),
        "total": _non_negative_int(usage.get("total_tokens"), "token.total_tokens"),
    }
    return {
        "source": {"kind": "codex_rollout", "id": next(iter(session_ids))},
        "model": model,
        "repo_sha": next(iter(repo_shas)),
        "started_at": turns[0][1]["timestamp"],
        "ended_at": completions[0][1]["timestamp"],
        "duration_ms": duration_ms,
        "tokens": tokens,
    }


def build_measurement(
    metadata: dict[str, Any], grading: dict[str, Any], source: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    quality, expectations = grading_quality(grading)
    if source["model"] is not None and source["model"] != metadata["model"]:
        raise InvalidSample(
            f"model 不一致: metadata={metadata['model']} session={source['model']}"
        )
    if source["repo_sha"] is not None and source["repo_sha"] != metadata["repo_sha"]:
        raise InvalidSample(
            f"repo_sha 不一致: metadata={metadata['repo_sha']} session={source['repo_sha']}"
        )
    measurement = {
        "schema_version": 1,
        "eval_id": metadata["eval_id"],
        "eval_name": metadata["eval_name"],
        "configuration": metadata["configuration"],
        "run_number": metadata["run_number"],
        "source": source["source"],
        "model": metadata["model"],
        "repo_sha": metadata["repo_sha"],
        "prompt_sha256": prompt_hash(metadata["prompt"]),
        "started_at": source["started_at"],
        "ended_at": source["ended_at"],
        "duration_ms": source["duration_ms"],
        "tokens": source["tokens"],
        "quality": quality,
    }
    return measurement, expectations


def stable_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


def extract_command(args: argparse.Namespace) -> int:
    metadata = validate_metadata(read_json(Path(args.metadata)))
    grading = read_json(Path(args.grading))
    if args.session:
        source = parse_rollout_source(Path(args.session), metadata["grader_only_inputs"])
    else:
        source = parse_timing_source(Path(args.timing))
    measurement, _expectations = build_measurement(metadata, grading, source)
    output = Path(args.output)
    atomic_write(output, stable_json_bytes(measurement))
    if args.as_json:
        print(json.dumps(measurement, ensure_ascii=False, indent=2))
    else:
        print(output)
    return 0


def validate_measurement(value: dict[str, Any], path: Path) -> dict[str, Any]:
    required = (
        "schema_version", "eval_id", "eval_name", "configuration", "run_number",
        "source", "model", "repo_sha", "prompt_sha256", "started_at", "ended_at",
        "duration_ms", "tokens", "quality",
    )
    missing = [key for key in required if key not in value]
    if missing:
        raise MetricsError(f"{path} 缺少 measurement 字段: {', '.join(missing)}")
    if value["schema_version"] != 1:
        raise MetricsError(f"{path} schema_version 必须为 1")
    if value["configuration"] not in CONFIGURATIONS:
        raise MetricsError(f"{path} configuration 非法")
    _non_negative_int(value["eval_id"], f"{path}.eval_id")
    _non_negative_int(value["run_number"], f"{path}.run_number")
    _non_negative_int(value["duration_ms"], f"{path}.duration_ms")
    tokens = value["tokens"]
    quality = value["quality"]
    if not isinstance(tokens, dict) or any(key not in tokens for key in TOKEN_KEYS):
        raise MetricsError(f"{path} tokens schema 非法")
    _non_negative_int(tokens["total"], f"{path}.tokens.total")
    for key in TOKEN_KEYS[:-1]:
        if tokens[key] is not None:
            _non_negative_int(tokens[key], f"{path}.tokens.{key}")
    if not isinstance(quality, dict):
        raise MetricsError(f"{path} quality 必须是 object")
    passed = _non_negative_int(quality.get("passed"), f"{path}.quality.passed")
    total = _non_negative_int(quality.get("total"), f"{path}.quality.total")
    if total == 0 or passed > total:
        raise MetricsError(f"{path} quality 计数非法")
    pass_rate = quality.get("pass_rate")
    if not isinstance(pass_rate, (int, float)) or isinstance(pass_rate, bool):
        raise MetricsError(f"{path} quality.pass_rate 必须是数字")
    if not math.isclose(float(pass_rate), passed / total, abs_tol=1e-9):
        raise MetricsError(f"{path} quality.pass_rate 与计数不一致")
    return value


def _metric_summary(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "stddev": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def _load_grading_for_measurement(path: Path) -> dict[str, Any]:
    grading_path = path.parent / "grading.json"
    return read_json(grading_path) if grading_path.exists() else {}


def aggregate_spec2(iteration_dir: Path) -> tuple[dict[str, Any], str]:
    paths = sorted(iteration_dir.rglob("measurement.json"))
    if not paths:
        raise InvalidSample(f"未找到 measurement.json: {iteration_dir}")
    loaded = [(path, validate_measurement(read_json(path), path)) for path in paths]
    groups: dict[tuple[int, int], dict[str, tuple[Path, dict[str, Any]]]] = {}
    for path, item in loaded:
        key = (item["eval_id"], item["run_number"])
        bucket = groups.setdefault(key, {})
        configuration = item["configuration"]
        if configuration in bucket:
            raise InvalidSample(f"重复 measurement: eval={key[0]} run={key[1]} {configuration}")
        bucket[configuration] = (path, item)

    pairs: list[tuple[tuple[int, int], dict[str, tuple[Path, dict[str, Any]]]]] = []
    for key in sorted(groups):
        bucket = groups[key]
        missing = [configuration for configuration in CONFIGURATIONS if configuration not in bucket]
        if missing:
            raise InvalidSample(f"paired run 缺失: eval={key[0]} run={key[1]} {','.join(missing)}")
        left = bucket["with_skill"][1]
        right = bucket["without_skill"][1]
        mismatches = [
            field for field in ("prompt_sha256", "model", "repo_sha")
            if left[field] != right[field]
        ]
        if mismatches:
            raise InvalidSample(
                f"paired run 不可比: eval={key[0]} run={key[1]} {','.join(mismatches)}"
            )
        grading_by_configuration: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
        for configuration in CONFIGURATIONS:
            path, item = bucket[configuration]
            grading_path = path.parent / "grading.json"
            if not grading_path.exists():
                raise InvalidSample(f"paired run 缺少 grading: {grading_path}")
            quality, expectations = grading_quality(read_json(grading_path))
            if quality != item["quality"]:
                raise InvalidSample(f"measurement 与 grading 统计不一致: {path}")
            grading_by_configuration[configuration] = (quality, expectations)
        with_texts = [
            item["text"] for item in grading_by_configuration["with_skill"][1]
        ]
        without_texts = [
            item["text"] for item in grading_by_configuration["without_skill"][1]
        ]
        if with_texts != without_texts:
            raise InvalidSample(
                f"paired run 评分断言不一致: eval={key[0]} run={key[1]}"
            )
        pairs.append((key, bucket))

    runs: list[dict[str, Any]] = []
    values: dict[str, dict[str, list[float]]] = {
        configuration: {"pass_rate": [], "time_seconds": [], "tokens": []}
        for configuration in CONFIGURATIONS
    }
    for _key, bucket in pairs:
        for configuration in CONFIGURATIONS:
            path, item = bucket[configuration]
            grading = _load_grading_for_measurement(path)
            expectations = grading.get("expectations", []) if isinstance(grading, dict) else []
            execution_metrics = grading.get("execution_metrics", {}) if isinstance(grading, dict) else {}
            quality = item["quality"]
            time_seconds = item["duration_ms"] / 1000
            total_tokens = item["tokens"]["total"]
            run = {
                "eval_id": item["eval_id"],
                "eval_name": item["eval_name"],
                "configuration": configuration,
                "run_number": item["run_number"],
                "result": {
                    "pass_rate": quality["pass_rate"],
                    "passed": quality["passed"],
                    "failed": quality["total"] - quality["passed"],
                    "total": quality["total"],
                    "time_seconds": time_seconds,
                    "tokens": total_tokens,
                    "tool_calls": execution_metrics.get("total_tool_calls", 0),
                    "errors": execution_metrics.get("errors_encountered", 0),
                },
                "expectations": expectations,
                "notes": [],
            }
            runs.append(run)
            values[configuration]["pass_rate"].append(float(quality["pass_rate"]))
            values[configuration]["time_seconds"].append(time_seconds)
            values[configuration]["tokens"].append(float(total_tokens))

    summary = {
        configuration: {
            metric: _metric_summary(metric_values)
            for metric, metric_values in values[configuration].items()
        }
        for configuration in CONFIGURATIONS
    }
    delta = {
        metric: summary["with_skill"][metric]["mean"] - summary["without_skill"][metric]["mean"]
        for metric in ("pass_rate", "time_seconds", "tokens")
    }
    summary["delta"] = {
        "pass_rate": f"{delta['pass_rate']:+.2f}",
        "time_seconds": f"{delta['time_seconds']:+.1f}",
        "tokens": f"{delta['tokens']:+.0f}",
    }
    sample_size = len(pairs)
    pilot = sample_size == 1
    notes = [
        "单样本 pilot 只验证测量链路，不用于推断 x-spec2 的稳定增益。"
    ] if pilot else []
    benchmark = {
        "metadata": {
            "skill_name": "x-spec2",
            "skill_path": "skills/x-spec2",
            "executor_model": pairs[0][1]["with_skill"][1]["model"],
            "timestamp": max(
                (item["ended_at"] for _path, item in loaded if item["ended_at"] is not None),
                default=None,
            ),
            "evals_run": sorted({item["eval_id"] for _path, item in loaded}),
            "runs_per_configuration": sample_size,
            "pilot": pilot,
            "sample_size_per_configuration": sample_size,
        },
        "runs": runs,
        "run_summary": summary,
        "notes": notes,
    }
    markdown_lines = [
        "# Skill Benchmark: x-spec2",
        "",
        f"- Pilot: {'yes' if pilot else 'no'}",
        f"- Samples per configuration: {sample_size}",
        "",
        "| Metric | With Skill | Without Skill | Delta |",
        "|---|---:|---:|---:|",
        f"| Pass rate | {summary['with_skill']['pass_rate']['mean']:.2%} | "
        f"{summary['without_skill']['pass_rate']['mean']:.2%} | {summary['delta']['pass_rate']} |",
        f"| Duration | {summary['with_skill']['time_seconds']['mean']:.1f}s | "
        f"{summary['without_skill']['time_seconds']['mean']:.1f}s | {summary['delta']['time_seconds']}s |",
        f"| Total tokens | {summary['with_skill']['tokens']['mean']:.0f} | "
        f"{summary['without_skill']['tokens']['mean']:.0f} | {summary['delta']['tokens']} |",
    ]
    if notes:
        markdown_lines.extend(["", "## Notes", "", *[f"- {note}" for note in notes]])
    return benchmark, "\n".join(markdown_lines) + "\n"


def aggregate_command(args: argparse.Namespace) -> int:
    iteration_dir = Path(args.iteration_dir)
    if not iteration_dir.is_dir():
        raise MetricsError(f"iteration 目录不存在: {iteration_dir}")
    benchmark, markdown = aggregate_spec2(iteration_dir)
    atomic_write(iteration_dir / "benchmark.json", stable_json_bytes(benchmark))
    atomic_write(iteration_dir / "benchmark.md", markdown.encode("utf-8"))
    if args.as_json:
        print(json.dumps(benchmark, ensure_ascii=False, indent=2))
    else:
        print(iteration_dir / "benchmark.json")
        print(iteration_dir / "benchmark.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="metrics")
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="从完成的 Codex run 提取 x-spec2 measurement")
    source = extract.add_mutually_exclusive_group(required=True)
    source.add_argument("--session", help="已完成的 Codex rollout JSONL")
    source.add_argument("--timing", help="子 agent 完成通知保存的 timing.json")
    extract.add_argument("--metadata", required=True, help="run eval_metadata.json")
    extract.add_argument("--grading", required=True, help="独立 grading.json")
    extract.add_argument("--output", required=True, help="measurement.json 输出路径")
    extract.add_argument("--json", action="store_true", dest="as_json")

    aggregate = sub.add_parser("aggregate-spec2", help="聚合 x-spec2 paired measurements")
    aggregate.add_argument("iteration_dir", help="skills/x-spec2-workspace/iteration-N")
    aggregate.add_argument("--json", action="store_true", dest="as_json")

    args = parser.parse_args(argv)
    try:
        if args.command == "extract":
            return extract_command(args)
        return aggregate_command(args)
    except InvalidSample as exc:
        print(f"无效样本：{exc}", file=sys.stderr)
        return 1
    except (MetricsError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
