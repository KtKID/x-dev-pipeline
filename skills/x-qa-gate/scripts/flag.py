#!/usr/bin/env python3
"""QA Gate issue 登记与双文件可恢复事务引擎。

本模块由 x-dev/scripts/xdev.py 的 flag 子命令调用，独立拥有输入校验、checklist 状态降级、
issue ledger 编号、事务提交和崩溃恢复。仅使用标准库。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
ID_COL_RE = re.compile(r"(?:T|#)?(\d+)", re.IGNORECASE)
TOKEN_RE = re.compile(r"\[(?P<box>[ x!])\]")
BLOCKED = "blocked"
FLAG_TASK_RE = re.compile(r"T[1-9][0-9]*")
ISSUE_LINE_RE = re.compile(r"^- issue-([0-9]+) \|", re.MULTILINE)
REPORT_NAME_RE = re.compile(
    r"^qa-gate-report-(?P<timestamp>[0-9]{8}-[0-9]{6})(?:-(?P<suffix>[0-9]+))?\.md$"
)
FLAG_MARKER_NAME = ".flag-transaction.json"
FLAG_MARKER_TEMP_NAME = ".flag-transaction.json.tmp"
FLAG_MARKER_VERSION = 1
FLAG_TEMP_SUFFIX = ".flag.tmp"


def cells(row: str) -> list[str]:
    """拆分 Markdown 表格行。"""
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def task_engine_status(raw_status: str) -> str:
    """把 token/emoji 状态压缩为 done、todo、blocked。"""
    token = TOKEN_RE.search(raw_status)
    if token is not None:
        if token.group("box").lower() == "x":
            return "done"
        if token.group("box") == "!":
            return BLOCKED
        return "todo"
    if "🔴" in raw_status:
        return BLOCKED
    if "🟢" in raw_status or "✅" in raw_status:
        return "done"
    return "todo"


class FlagError(ValueError):
    """flag 可操作错误；CLI 统一映射为退出码 2。"""


def normalize_flag_inputs(
    task_arg: str, severity: str, loc: str, msg: str
) -> tuple[list[str], str, str, str]:
    """校验并归一化 flag 参数，不接触文件系统。"""
    raw_tasks = task_arg.split(",")
    task_ids = [item.strip() for item in raw_tasks]
    if not task_ids or any(not item for item in task_ids):
        raise FlagError("--task 含空项")
    invalid = [item for item in task_ids if FLAG_TASK_RE.fullmatch(item) is None]
    if invalid:
        raise FlagError(f"--task 仅接受 T1、T2 形式：{', '.join(invalid)}")
    duplicates = sorted({item for item in task_ids if task_ids.count(item) > 1})
    if duplicates:
        raise FlagError(f"--task 含重复项：{', '.join(duplicates)}")

    severity = severity.strip().upper()
    if severity not in {"P0", "P1", "P2"}:
        raise FlagError("--severity 仅接受 P0、P1、P2")

    loc = loc.strip()
    if not loc or "|" in loc or "\r" in loc or "\n" in loc:
        raise FlagError("--loc 必须是单行 path:正整数，且不能包含竖线")
    path_part, separator, line_part = loc.rpartition(":")
    if not separator or not path_part or re.fullmatch(r"[1-9][0-9]*", line_part) is None:
        raise FlagError("--loc 必须是 path:正整数")

    msg = msg.replace("\r\n", " ").replace("\r", " ").replace("\n", " ").strip()
    if not msg:
        raise FlagError("--msg 归一化后不能为空")
    if not all(char.isprintable() for char in msg):
        raise FlagError("--msg 只能包含可打印字符")
    return task_ids, severity, loc, msg


def _checklist_layout(checklist_text: str) -> tuple[list[str], int, int, int]:
    """返回保留换行的行、首个表数据起点、ID 列和状态列。"""
    lines = checklist_text.splitlines(keepends=True)
    for index in range(len(lines) - 1):
        if not lines[index].lstrip().startswith("|"):
            continue
        if TABLE_SEP_RE.match(lines[index + 1].rstrip("\r\n")) is None:
            continue
        header = cells(lines[index])

        def col_idx(*keywords: str) -> int | None:
            for keyword in keywords:
                for cell_index, value in enumerate(header):
                    if keyword in value:
                        return cell_index
            return None

        id_idx = col_idx("#", "编号")
        status_idx = col_idx("状态")
        if id_idx is None or status_idx is None:
            raise FlagError("dev-checklist.md 表头缺少 #/编号 或状态列")
        return lines, index + 2, id_idx, status_idx
    raise FlagError("dev-checklist.md 无可解析表格")


def _target_checklist_rows(
    checklist_text: str, task_ids: list[str]
) -> tuple[list[str], int, dict[str, int]]:
    """定位目标 task 的唯一表格行；重复或缺失都作为调用错误。"""
    lines, row_start, id_idx, status_idx = _checklist_layout(checklist_text)
    found: dict[str, list[int]] = {task_id: [] for task_id in task_ids}
    for line_index in range(row_start, len(lines)):
        if not lines[line_index].lstrip().startswith("|"):
            break
        row_cells = cells(lines[line_index])
        if id_idx >= len(row_cells):
            continue
        raw_id = re.sub(r"[`*]", "", row_cells[id_idx]).strip()
        match = ID_COL_RE.fullmatch(raw_id)
        if match is None:
            continue
        task_id = f"T{match.group(1)}"
        if task_id in found:
            found[task_id].append(line_index)

    missing = [task_id for task_id, indexes in found.items() if not indexes]
    duplicate = [task_id for task_id, indexes in found.items() if len(indexes) > 1]
    if missing:
        raise FlagError(f"checklist 缺少目标 task：{', '.join(missing)}")
    if duplicate:
        raise FlagError(f"checklist 目标 task 重复：{', '.join(duplicate)}")
    return lines, status_idx, {task_id: indexes[0] for task_id, indexes in found.items()}


def downgrade_task_rows(checklist_text: str, task_ids: list[str]) -> tuple[str, list[str]]:
    """把目标 task 状态单元格降为 `[!] 🔴`，保持行内其他内容与已 blocked 状态。"""
    lines, status_idx, target_rows = _target_checklist_rows(checklist_text, task_ids)
    downgraded: list[str] = []
    for task_id in task_ids:
        line_index = target_rows[task_id]
        raw_line = lines[line_index]
        newline = ""
        if raw_line.endswith("\r\n"):
            raw_line, newline = raw_line[:-2], "\r\n"
        elif raw_line.endswith(("\n", "\r")):
            raw_line, newline = raw_line[:-1], raw_line[-1]
        parts = raw_line.split("|")
        segment_index = status_idx + 1  # 表格行以 | 开头，首段为空
        if segment_index >= len(parts) - 1:
            raise FlagError(f"checklist 的 {task_id} 状态单元格缺失")
        old_segment = parts[segment_index]
        old_status = old_segment.strip()
        if task_engine_status(old_status) == BLOCKED:
            continue
        spacing = re.fullmatch(r"(\s*).*?(\s*)", old_segment)
        leading = spacing.group(1) if spacing else " "
        trailing = spacing.group(2) if spacing else " "
        parts[segment_index] = f"{leading}[!] 🔴{trailing}"
        lines[line_index] = "|".join(parts) + newline
        downgraded.append(task_id)
    return "".join(lines), downgraded


def next_issue_id(report_text: str) -> str:
    """只扫描代码所有的 issue 行首，返回本轮下一个 issue ID。"""
    numbers = [int(match.group(1)) for match in ISSUE_LINE_RE.finditer(report_text)]
    return f"issue-{max(numbers, default=0) + 1}"


def render_issue_report(report_path: Path) -> str:
    """创建新轮 issue ledger 的固定骨架。"""
    return (
        f"# QA Gate Issue Ledger — {report_path.stem}\n\n"
        "> 由 `x-dev/scripts/xdev.py flag` 生成和维护；issue 行归代码所有；本轮首条由代码分配为 `issue-1`。\n\n"
        "## Issues\n"
    )


def append_issue_line(report_text: str, issue: dict) -> str:
    """issue ledger 行的唯一格式化点。"""
    prefix = report_text if report_text.endswith("\n") else report_text + "\n"
    task_text = ",".join(issue["tasks"])
    return (
        f"{prefix}- {issue['issue']} | {issue['severity']} | {task_text} | "
        f"{issue['loc']} | {issue['msg']}\n"
    )


def _report_sort_key(path: Path) -> tuple[str, int]:
    match = REPORT_NAME_RE.fullmatch(path.name)
    if match is None:
        raise FlagError(f"非法 QA Gate report 文件名：{path.name}")
    suffix = int(match.group("suffix") or 0)
    return match.group("timestamp"), suffix


def resolve_current_report(
    reports_dir: Path, new_round: bool, now: datetime | None = None
) -> tuple[Path, str, str | None]:
    """选择本轮 ledger；只返回目标和内容，不在事务外创建业务文件。"""
    candidates = []
    if reports_dir.exists():
        candidates = [
            path for path in reports_dir.iterdir()
            if path.is_file() and REPORT_NAME_RE.fullmatch(path.name)
        ]
    if new_round or not candidates:
        timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
        base = reports_dir / f"qa-gate-report-{timestamp}.md"
        if not base.exists():
            return base, render_issue_report(base), None
        suffix = 1
        while True:
            candidate = reports_dir / f"qa-gate-report-{timestamp}-{suffix:02d}.md"
            if not candidate.exists():
                return candidate, render_issue_report(candidate), None
            suffix += 1
    report_path = max(candidates, key=_report_sort_key)
    try:
        report_bytes = report_path.read_bytes()
        return report_path, report_bytes.decode("utf-8"), _sha256_bytes(report_bytes)
    except (OSError, UnicodeError) as exc:
        raise FlagError(f"读取 QA Gate ledger 失败：{exc}") from exc


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_durable_temp(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _relative_transaction_path(task_dir: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(task_dir.resolve()))
    except ValueError as exc:
        raise FlagError(f"事务路径越出 task 目录：{path}") from exc


def _resolve_transaction_path(task_dir: Path, raw: object) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
        raise FlagError(f"事务标记包含非法相对路径：{raw!r}")
    path = (task_dir / raw).resolve()
    try:
        path.relative_to(task_dir.resolve())
    except ValueError as exc:
        raise FlagError(f"事务标记路径越出 task 目录：{raw}") from exc
    return path


def _flag_result(result: object, recovered: bool) -> dict:
    if not isinstance(result, dict):
        raise FlagError("事务标记缺少 result")
    required = ("issue", "downgraded", "report", "recovered")
    if set(result) != set(required):
        raise FlagError("事务标记 result 字段不完整")
    if not isinstance(result["issue"], str) or not isinstance(result["downgraded"], list):
        raise FlagError("事务标记 result 类型非法")
    if not isinstance(result["report"], str):
        raise FlagError("事务标记 report 类型非法")
    return {
        "issue": result["issue"],
        "downgraded": result["downgraded"],
        "report": result["report"],
        "recovered": recovered,
    }


def recover_flag_transaction(task_dir: Path) -> dict | None:
    """幂等前滚 pending flag 事务；成功后返回原 issue 结果。"""
    marker_path = task_dir / "reports" / "qa-gate" / FLAG_MARKER_NAME
    if not marker_path.exists():
        return None
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FlagError(f"读取事务标记失败，marker 已保留：{exc}") from exc
    if marker.get("version") != FLAG_MARKER_VERSION:
        raise FlagError(f"不支持的事务标记版本：{marker.get('version')!r}")
    targets = marker.get("targets")
    if not isinstance(targets, list) or len(targets) != 2:
        raise FlagError("事务标记必须包含两个目标")

    for entry in targets:
        if not isinstance(entry, dict):
            raise FlagError("事务标记 target 结构非法")
        target = _resolve_transaction_path(task_dir, entry.get("target"))
        temp_raw = entry.get("temp")
        expected = entry.get("sha256")
        before = entry.get("before_sha256")
        if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
            raise FlagError(f"事务标记目标哈希非法：{target}")
        if before is not None and (
            not isinstance(before, str) or re.fullmatch(r"[0-9a-f]{64}", before) is None
        ):
            raise FlagError(f"事务标记旧目标哈希非法：{target}")
        try:
            current = _sha256_file(target)
            if current == expected:
                if temp_raw is not None:
                    _resolve_transaction_path(task_dir, temp_raw).unlink(missing_ok=True)
                continue
            if current != before:
                raise FlagError(
                    f"事务目标已被其他写入修改：{target}；当前 {current}，事务读取时 {before}"
                )
            temp = _resolve_transaction_path(task_dir, temp_raw)
            if not temp.exists():
                raise FlagError(
                    f"事务恢复材料缺失：{temp}；目标 {target} 期望 SHA-256 {expected}"
                )
            try:
                os.replace(temp, target)
            except FileNotFoundError:
                if _sha256_file(target) != expected:
                    raise
            _fsync_directory(target.parent)
            if _sha256_file(target) != expected:
                raise FlagError(f"事务恢复后哈希不匹配：{target}；期望 {expected}")
        except OSError as exc:
            raise FlagError(f"事务恢复失败，marker 已保留：{exc}") from exc

    marker_temp_raw = marker.get("marker_temp")
    try:
        if marker_temp_raw:
            marker_temp = _resolve_transaction_path(task_dir, marker_temp_raw)
            marker_temp.unlink(missing_ok=True)
        marker_path.unlink()
        _fsync_directory(marker_path.parent)
    except OSError as exc:
        raise FlagError(f"事务目标已完成，但 marker 清理失败：{exc}") from exc
    return _flag_result(marker.get("result"), recovered=True)


def commit_flag_transaction(
    task_dir: Path,
    checklist_path: Path,
    checklist_text: str,
    report_path: Path,
    report_text: str,
    result: dict,
    checklist_before_sha256: str,
    report_before_sha256: str | None,
) -> dict:
    """串行写入固定临时文件，完整发布 marker 后提交两个目标。"""
    reports_dir = task_dir / "reports" / "qa-gate"
    reports_dir.mkdir(parents=True, exist_ok=True)
    checklist_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    target_contents = [
        (checklist_path, checklist_text.encode("utf-8"), checklist_before_sha256),
        (report_path, report_text.encode("utf-8"), report_before_sha256),
    ]
    prepared: list[Path] = []
    targets: list[dict] = []
    marker_temp = reports_dir / FLAG_MARKER_TEMP_NAME
    marker_path = reports_dir / FLAG_MARKER_NAME
    marker_published = False
    try:
        if marker_path.exists():
            raise FlagError("检测到 pending flag 事务；请先恢复后再登记新 issue")
        for target, content, before_sha256 in target_contents:
            expected_sha256 = _sha256_bytes(content)
            temp = target.parent / f".{target.name}{FLAG_TEMP_SUFFIX}"
            targets.append({
                "target": _relative_transaction_path(task_dir, target),
                "temp": _relative_transaction_path(task_dir, temp),
                "sha256": expected_sha256,
                "before_sha256": before_sha256,
            })
            if _sha256_file(target) == expected_sha256:
                temp.unlink(missing_ok=True)
                continue
            temp.unlink(missing_ok=True)
            prepared.append(temp)
            _write_durable_temp(temp, content)
        marker = {
            "version": FLAG_MARKER_VERSION,
            "marker_temp": _relative_transaction_path(task_dir, marker_temp),
            "targets": targets,
            "result": result,
        }
        marker_bytes = json.dumps(marker, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        marker_temp.unlink(missing_ok=True)
        prepared.append(marker_temp)
        _write_durable_temp(marker_temp, marker_bytes)
        os.replace(marker_temp, marker_path)
        marker_published = True
        _fsync_directory(reports_dir)

        stale_targets = []
        for entry in targets:
            target = _resolve_transaction_path(task_dir, entry["target"])
            current = _sha256_file(target)
            if current not in {entry["before_sha256"], entry["sha256"]}:
                stale_targets.append(str(target))
        if stale_targets:
            marker_path.unlink(missing_ok=True)
            _fsync_directory(reports_dir)
            marker_published = False
            raise FlagError(
                "事务读取后目标发生变化，请重试 flag：" + ", ".join(stale_targets)
            )

        for entry in targets:
            target = _resolve_transaction_path(task_dir, entry["target"])
            temp = _resolve_transaction_path(task_dir, entry["temp"])
            if _sha256_file(target) == entry["sha256"]:
                temp.unlink(missing_ok=True)
                continue
            try:
                os.replace(temp, target)
            except FileNotFoundError:
                if _sha256_file(target) != entry["sha256"]:
                    raise
            _fsync_directory(target.parent)
            if _sha256_file(target) != entry["sha256"]:
                raise FlagError(f"事务提交后哈希不匹配：{target}")
        marker_path.unlink(missing_ok=True)
        for path in prepared:
            path.unlink(missing_ok=True)
        _fsync_directory(reports_dir)
        return _flag_result(result, recovered=False)
    except FlagError:
        if not marker_published:
            for path in prepared:
                path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        if not marker_published:
            for path in prepared:
                path.unlink(missing_ok=True)
        state = "marker 已保留，可由下次 flag 恢复" if marker_published else "业务文件未提交"
        raise FlagError(f"flag 事务 IO 失败（{state}）：{exc}") from exc


def _emit_flag_result(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return
    verb = "已恢复" if result["recovered"] else "已登记"
    downgraded = ",".join(result["downgraded"]) or "无"
    print(f"{verb} {result['issue']} → {result['report']}；降级：{downgraded}")


def flag_command(
    task_dir: Path,
    task_arg: str,
    severity: str,
    loc: str,
    msg: str,
    new_round: bool,
    as_json: bool,
) -> int:
    """flag 子命令：恢复 → 校验 → 生成 → 双目标事务提交。"""
    try:
        recovered = recover_flag_transaction(task_dir)
        if recovered is not None:
            _emit_flag_result(recovered, as_json)
            return 0
        if not task_dir.is_dir():
            raise FlagError(f"不是 task 目录：{task_dir}")
        task_ids, severity, loc, msg = normalize_flag_inputs(task_arg, severity, loc, msg)
        checklist_path = task_dir / "dev-checklist.md"
        try:
            checklist_text = checklist_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise FlagError(f"读取 dev-checklist.md 失败：{exc}") from exc

        # P2 也先定位并验证目标唯一性；登记的每个 T# 都必须是现存 task。
        _target_checklist_rows(checklist_text, task_ids)
        if severity in {"P0", "P1"}:
            new_checklist, downgraded = downgrade_task_rows(checklist_text, task_ids)
        else:
            new_checklist, downgraded = checklist_text, []

        report_path, report_text, report_before_sha256 = resolve_current_report(
            task_dir / "reports" / "qa-gate", new_round
        )
        issue_id = next_issue_id(report_text)
        issue = {
            "issue": issue_id,
            "tasks": task_ids,
            "severity": severity,
            "loc": loc,
            "msg": msg,
        }
        new_report = append_issue_line(report_text, issue)
        result = {
            "issue": issue_id,
            "downgraded": downgraded,
            "report": report_path.name,
            "recovered": False,
        }
        committed = commit_flag_transaction(
            task_dir,
            checklist_path,
            new_checklist,
            report_path,
            new_report,
            result,
            _sha256_bytes(checklist_text.encode("utf-8")),
            report_before_sha256,
        )
        _emit_flag_result(committed, as_json)
        return 0
    except (FlagError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
