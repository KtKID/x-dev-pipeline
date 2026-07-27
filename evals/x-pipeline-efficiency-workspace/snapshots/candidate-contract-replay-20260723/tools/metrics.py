#!/usr/bin/env python3
"""x-spec2 的确定性评测指标计算工具。

extractor 只接受一个显式的执行来源：

* 已完成的 Codex rollout JSONL，或
* 从 subagent 完成通知中捕获的 timing.json。

它从不扫描 session 目录，也从不把 prompt 或 transcript 内容复制进
measurement.json。退出码遵循仓库约定：0 表示成功，1 表示样本可读但样本/样本对
无效，2 表示用法、IO、JSON 或 schema 错误。
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


# 成对比较的两种配置：启用 skill 与不启用 skill
CONFIGURATIONS = ("with_skill", "without_skill")
# measurement 中允许出现的 token 字段顺序，最后一个是合计项
TOKEN_KEYS = ("input", "cached_input", "output", "reasoning_output", "total")
CODEX_TOKEN_FIELDS = {
    "input": "input_tokens",
    "cached_input": "cached_input_tokens",
    "output": "output_tokens",
    "reasoning_output": "reasoning_output_tokens",
    "total": "total_tokens",
}


class MetricsError(ValueError):
    """输入无法解析或不满足声明的 schema（对应退出码 2）。"""


class InvalidSample(ValueError):
    """输入可读，但测量边界或成对比较无效（对应退出码 1）。"""


def _is_int(value: object) -> bool:
    """判断值是否为真正的整数（排除 bool，因为 bool 是 int 的子类）。"""
    return isinstance(value, int) and not isinstance(value, bool)


def _non_negative_int(value: object, field: str) -> int:
    """校验 ``value`` 是非负整数，否则抛出 MetricsError。``field`` 仅用于错误提示。"""
    if not _is_int(value) or value < 0:
        raise MetricsError(f"{field} 必须是非负整数")
    return value


def _non_empty_string(value: object, field: str) -> str:
    """校验 ``value`` 是非空字符串并返回去首尾空白后的结果，否则抛出 MetricsError。"""
    if not isinstance(value, str) or not value.strip():
        raise MetricsError(f"{field} 必须是非空字符串")
    return value.strip()


def read_json(path: Path) -> dict[str, Any]:
    """读取 JSON 文件并解析为 dict；顶层必须是 object，否则抛出 MetricsError。"""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MetricsError(f"无法读取 JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MetricsError(f"JSON 顶层必须是 object: {path}")
    return value


def parse_timestamp(value: object, field: str) -> datetime:
    """把 ISO-8601 字符串解析为带时区的 datetime；格式非法或缺时区则抛出 MetricsError。"""
    raw = _non_empty_string(value, field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MetricsError(f"{field} 不是合法 ISO-8601 时间: {raw}") from exc
    if parsed.tzinfo is None:
        raise MetricsError(f"{field} 必须包含时区: {raw}")
    return parsed


def prompt_hash(prompt: str) -> str:
    """计算 prompt 文本的 SHA-256 摘要，返回 ``sha256:<hex>``。只存哈希避免明文落盘。"""
    return "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def validate_metadata(value: dict[str, Any]) -> dict[str, Any]:
    """校验 run 元数据：必填字段、取值范围、配置取值、输入集合不重叠、rubric 未泄露。

    返回标准化后的子集（剔除掉 rubric_exposed 等仅用于校验的字段）。
    """
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
    """校验 ``grading.expectations`` 并统计通过率。

    若 grading 内含 ``summary``，则将其与逐项统计交叉核对，不一致即报错。
    返回 ``(quality_summary, normalized_expectations)``。
    """
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
    """从 subagent 完成通知保存的 timing.json 解析执行来源。

    timing.json 只提供 agent_id、总 token 与耗时，model / repo_sha / 起止时间均未知，
    故填 None，由后续一致性校验放行（不做 model/sha 比对）。
    """
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


def _read_codex_session_rows(
    path: Path,
) -> list[tuple[int, str, dict[str, Any], datetime]]:
    """读取 Codex JSONL，并保留行号、原文、事件与带时区时间。"""
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MetricsError(f"无法读取 session {path}: {exc}") from exc

    rows: list[tuple[int, str, dict[str, Any], datetime]] = []
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
        rows.append((line_number, raw_line, row, timestamp))
    if not rows:
        raise MetricsError("session 为空")
    return rows


def _codex_session_identity(
    rows: list[tuple[int, str, dict[str, Any], datetime]],
) -> tuple[int, str, str, datetime, str]:
    """从首个有效 Codex session_meta 取得活动 session 身份。"""
    for index, (line_number, _raw_line, row, timestamp) in enumerate(rows):
        if row.get("type") != "session_meta":
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            raise MetricsError(f"session[{line_number}].session_meta.payload 必须是 object")
        canonical_id = payload.get("id")
        if not isinstance(canonical_id, str) or not canonical_id.strip():
            canonical_id = payload.get("session_id")
        git = payload.get("git")
        repo_sha = git.get("commit_hash") if isinstance(git, dict) else None
        canonical_id = _non_empty_string(
            canonical_id, f"session[{line_number}].session_meta.id"
        )
        repo_sha = _non_empty_string(
            repo_sha, f"session[{line_number}].session_meta.git.commit_hash"
        )
        raw_timestamp = _non_empty_string(
            row.get("timestamp"), f"session[{line_number}].timestamp"
        )
        return index, canonical_id, repo_sha, timestamp, raw_timestamp
    raise MetricsError("session 缺少 session_meta")


def _codex_total_usage(row: dict[str, Any]) -> dict[str, Any] | None:
    """返回 Codex token_count 的累计用量对象，其他事件返回 None。"""
    payload = row.get("payload")
    if row.get("type") != "event_msg" or not isinstance(payload, dict):
        return None
    if payload.get("type") != "token_count":
        return None
    info = payload.get("info")
    if not isinstance(info, dict):
        raise MetricsError("token_count.payload.info 必须是 object")
    usage = info.get("total_token_usage")
    if not isinstance(usage, dict):
        raise MetricsError("token_count.payload.info.total_token_usage 必须是 object")
    return usage


def _validate_codex_token_snapshots(snapshots: list[dict[str, Any]]) -> None:
    """校验 Codex 累计快照的所有分桶逐次单调。"""
    previous: dict[str, int] | None = None
    for snapshot_index, usage in enumerate(snapshots, start=1):
        current = {
            target: _non_negative_int(
                usage.get(source), f"token.snapshot[{snapshot_index}].{source}"
            )
            for target, source in CODEX_TOKEN_FIELDS.items()
        }
        if previous is not None:
            for target, source in CODEX_TOKEN_FIELDS.items():
                if current[target] < previous[target]:
                    raise InvalidSample(f"Codex Token 累计计数器回退: {source}")
        previous = current


def _codex_token_delta(
    baseline: dict[str, Any] | None, final: dict[str, Any]
) -> dict[str, int]:
    """计算 Codex 累计 Token 快照在五个 provider 分桶上的增量。"""
    tokens: dict[str, int] = {}
    for target, source in CODEX_TOKEN_FIELDS.items():
        final_value = _non_negative_int(final.get(source), f"token.final.{source}")
        baseline_value = 0
        if baseline is not None:
            baseline_value = _non_negative_int(
                baseline.get(source), f"token.baseline.{source}"
            )
        delta = final_value - baseline_value
        if delta < 0:
            raise InvalidSample(f"Codex Token 累计计数器回退: {source}")
        tokens[target] = delta
    return tokens


def parse_codex_session_source(
    path: Path, grader_only_inputs: list[str]
) -> dict[str, Any]:
    """把一个显式 Codex session JSONL 转换为 normalized source。

    生命周期窗口用于耗时；活动执行窗口用于模型、Token 与 grader-only 扫描。
    fork 继承前缀中的累计快照只作为 Token 基线。
    """
    rows = _read_codex_session_rows(path)
    header_index, session_id, repo_sha, started_at, started_at_raw = (
        _codex_session_identity(rows)
    )

    active_start_index: int | None = None
    for index in range(header_index + 1, len(rows)):
        _line, _raw_line, row, timestamp = rows[index]
        if row.get("type") == "turn_context" and timestamp >= started_at:
            active_start_index = index
            break
    if active_start_index is None:
        raise InvalidSample("session 缺少活动 turn_context")

    completions = [
        index
        for index in range(active_start_index, len(rows))
        if rows[index][2].get("type") == "event_msg"
        and isinstance(rows[index][2].get("payload"), dict)
        and rows[index][2]["payload"].get("type") == "task_complete"
    ]
    if not completions:
        raise InvalidSample("活动 session 缺少 task_complete")
    active_end_index = completions[-1]

    turns = [
        (index, rows[index])
        for index in range(active_start_index, len(rows))
        if rows[index][2].get("type") == "turn_context"
    ]
    if turns[-1][0] >= active_end_index:
        raise InvalidSample("最后活动 turn_context 之后缺少 task_complete")

    models: set[str] = set()
    for _index, (line_number, _raw_line, row, _timestamp) in turns:
        payload = row.get("payload")
        if not isinstance(payload, dict):
            raise MetricsError(f"session[{line_number}].turn_context.payload 必须是 object")
        models.add(
            _non_empty_string(payload.get("model"), f"session[{line_number}].turn_context.model")
        )
    if len(models) != 1:
        raise InvalidSample(f"活动 turn_context 模型数量必须为 1，实际 {len(models)}")
    model = next(iter(models))

    for index in range(active_start_index, active_end_index + 1):
        line_number, _raw_line, row, _timestamp = rows[index]
        if row.get("type") != "session_meta":
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            raise MetricsError(f"session[{line_number}].session_meta.payload 必须是 object")
        candidate_id = payload.get("id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            candidate_id = payload.get("session_id")
        if isinstance(candidate_id, str) and candidate_id.strip() != session_id:
            raise InvalidSample("活动执行窗口出现不同 Codex session ID")
        git = payload.get("git")
        candidate_sha = git.get("commit_hash") if isinstance(git, dict) else None
        if isinstance(candidate_sha, str) and candidate_sha.strip() != repo_sha:
            raise InvalidSample("活动执行窗口出现不同 repo SHA")

    assistant_replies = [
        (index, rows[index])
        for index in range(active_start_index, active_end_index)
        if rows[index][2].get("type") == "response_item"
        and isinstance(rows[index][2].get("payload"), dict)
        and rows[index][2]["payload"].get("type") == "message"
        and rows[index][2]["payload"].get("role") == "assistant"
    ]
    last_turn_index = turns[-1][0]
    assistant_replies = [item for item in assistant_replies if item[0] > last_turn_index]
    if not assistant_replies:
        raise InvalidSample("最后活动 turn_context 之后缺少 assistant 回复")
    reply_index, (_line, _raw_line, reply_row, ended_at) = assistant_replies[-1]
    if ended_at < started_at:
        raise MetricsError("最后 assistant 回复时间早于 session_meta")
    ended_at_raw = _non_empty_string(reply_row.get("timestamp"), "assistant_reply.timestamp")

    baseline_usage: dict[str, Any] | None = None
    for index in range(header_index + 1, active_start_index):
        usage = _codex_total_usage(rows[index][2])
        if usage is not None:
            baseline_usage = usage

    active_usages: list[tuple[int, dict[str, Any]]] = []
    for index in range(active_start_index, active_end_index):
        usage = _codex_total_usage(rows[index][2])
        if usage is not None:
            active_usages.append((index, usage))
    if not active_usages or active_usages[-1][0] <= reply_index:
        raise InvalidSample("最后 assistant 回复之后缺少累计 token_count")
    final_usage = active_usages[-1][1]
    _validate_codex_token_snapshots(
        ([baseline_usage] if baseline_usage is not None else [])
        + [usage for _index, usage in active_usages]
    )

    active_raw_text = "\n".join(
        rows[index][1] for index in range(active_start_index, active_end_index + 1)
    )
    for grader_input in grader_only_inputs:
        if grader_input and grader_input in active_raw_text:
            raise InvalidSample(f"session 读取了 grader-only input: {grader_input}")

    duration_ms = round((ended_at - started_at).total_seconds() * 1000)
    return {
        "source": {"kind": "codex_rollout", "id": session_id},
        "model": model,
        "repo_sha": repo_sha,
        "started_at": started_at_raw,
        "ended_at": ended_at_raw,
        "duration_ms": duration_ms,
        "tokens": _codex_token_delta(baseline_usage, final_usage),
    }


def parse_rollout_source(path: Path, grader_only_inputs: list[str]) -> dict[str, Any]:
    """兼容入口：委托给 Codex 专用 parser。"""
    return parse_codex_session_source(path, grader_only_inputs)


def build_measurement(
    metadata: dict[str, Any], grading: dict[str, Any], source: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """组合 metadata / grading / source 生成确定性 measurement。

    若 source 提供了 model 或 repo_sha（即来自 rollout），则与 metadata 交叉核对一致性。
    返回 ``(measurement, expectations)``：prompt 只以 sha256 形式落盘，避免明文泄露。
    """
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
    """把对象序列化为稳定、可复现的 JSON 字节（保留中文、缩进 2、以换行结尾）。"""
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    """原子写入文件：先写临时文件并 fsync，再 os.replace 覆盖目标，并对目录 fsync。

    任何中断都只会留下临时残骸（在 finally 中清理），不会损坏已存在的目标文件。
    """
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
    """``extract`` 子命令实现：读 metadata + grading，按来源解析，写出 measurement.json。"""
    metadata = validate_metadata(read_json(Path(args.metadata)))
    grading = read_json(Path(args.grading))
    if args.codex_session:
        source = parse_codex_session_source(
            Path(args.codex_session), metadata["grader_only_inputs"]
        )
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
    """校验一份已生成的 measurement.json 是否满足 schema 约束（字段完整、计数自洽、pass_rate 一致）。"""
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
    """计算一组数值的统计摘要：均值、总体标准差（样本数≤1 时为 0）、最小、最大。"""
    return {
        "mean": statistics.mean(values),
        "stddev": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def _load_grading_for_measurement(path: Path) -> dict[str, Any]:
    """读取与 measurement.json 同目录的 grading.json；不存在则返回空 dict。"""
    grading_path = path.parent / "grading.json"
    return read_json(grading_path) if grading_path.exists() else {}


def aggregate_spec2(iteration_dir: Path) -> tuple[dict[str, Any], str]:
    """聚合一个 iteration 目录下所有成对的 with/without skill measurement。

    步骤：
    1. 递归收集所有 ``measurement.json`` 并逐个校验；
    2. 按 ``(eval_id, run_number)`` 分组，每组必须同时含两种配置（成对）；
    3. 成对样本必须 prompt_sha256 / model / repo_sha 完全一致才可比较；
    4. 重新读各自 grading.json 复核质量统计与评分断言文本一致；
    5. 汇总 pass_rate / 耗时 / token 的均值与 delta，单样本标记为 pilot。

    返回 ``(benchmark_dict, benchmark_markdown)``。
    """
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

    # 校验每组都成对，且关键字段可比、评分断言一致
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

    # 逐 run 构造结果，并按配置收集指标序列
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

    # 汇总统计与 with/without 差值（delta），单样本记为 pilot
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
    # 生成 Markdown 摘要表格
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
    """``aggregate-spec2`` 子命令实现：校验目录、聚合并写出 benchmark.json 与 benchmark.md。"""
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
    """命令行入口：注册 ``extract`` 与 ``aggregate-spec2`` 子命令并统一错误码。

    退出码：0 成功 / 1 ``InvalidSample``（样本可读但无效）/ 2 ``MetricsError`` 或 ``OSError``。
    argparse 用法错误由 argparse 自身以退出码 2 处理。
    """
    parser = argparse.ArgumentParser(prog="metrics")
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="从完成的 Codex run 提取 x-spec2 measurement")
    source = extract.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--codex-session", "--session", dest="codex_session",
        help="已完成的 Codex rollout JSONL（--session 为兼容别名）",
    )
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
