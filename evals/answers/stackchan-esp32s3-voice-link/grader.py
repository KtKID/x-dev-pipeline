#!/usr/bin/env python3
"""Grader-only：对 StackChan x-spec2 eval 产物执行可复跑的机械校验。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_FILES = {"spec.md", "modules.md", "design.md"}
MODEL_TUPLES = ("数据流", "状态", "时序", "资源", "不变量", "故障")
REQUIRED_SIGNALS = {
    "hardware": ("StackChan", "ESP32-S3"),
    "wake_and_listen": ("唤醒", "listen"),
    "speech_pipeline": ("ASR", "TTS", "播放"),
    "latency": ("延迟",),
    "barge_in": ("打断", "取消"),
    "observability": ("可观测",),
    "recovery": ("恢复",),
}


def expectation(text: str, passed: bool, evidence: str) -> dict[str, object]:
    return {"text": text, "passed": passed, "evidence": evidence}


def trace_row_count(spec: str) -> int:
    match = re.search(r"^## 用户要求追溯\s*$([\s\S]*?)(?=^##\s|\Z)", spec, flags=re.MULTILINE)
    if not match:
        return 0
    rows = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.fullmatch(r"\|?[\s:|-]+\|?", stripped):
            continue
        rows.append(stripped)
    return max(0, len(rows) - 1)


def grade(outputs_dir: Path) -> dict[str, object]:
    files = sorted(path.name for path in outputs_dir.iterdir() if path.is_file()) if outputs_dir.is_dir() else []
    file_set = set(files)
    expected_files = file_set == REQUIRED_FILES
    nonempty = expected_files and all((outputs_dir / name).stat().st_size > 0 for name in REQUIRED_FILES)

    checks = [
        expectation(
            "输出目录只包含非空的 spec.md、modules.md、design.md",
            expected_files and nonempty,
            f"实际文件: {files}; 非空: {nonempty}",
        )
    ]

    command = [
        sys.executable,
        str(REPO_ROOT / "tools" / "xdev.py"),
        "validate",
        str(outputs_dir),
        "--json",
    ]
    completed = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    validator_payload: object
    try:
        validator_payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        validator_payload = {"stdout": completed.stdout, "stderr": completed.stderr}
    validator_text = json.dumps(validator_payload, ensure_ascii=False)
    validator_passed = completed.returncode == 0 and '"type": "spec2"' in validator_text
    checks.append(
        expectation(
            "xdev 校验成功并识别为 spec2",
            validator_passed,
            f"exit={completed.returncode}; payload={validator_text[:2000]}",
        )
    )

    contents = {
        name: (outputs_dir / name).read_text(encoding="utf-8", errors="replace")
        for name in REQUIRED_FILES
        if (outputs_dir / name).is_file()
    }
    combined = "\n".join(contents.values())
    spec = contents.get("spec.md", "")
    modules = contents.get("modules.md", "")
    design = contents.get("design.md", "")

    tuple_presence = {name: name in spec and name in design for name in MODEL_TUPLES}
    checks.append(
        expectation(
            "spec.md 声明六元组且 design.md 承载六元组动态设计",
            all(tuple_presence.values()),
            f"六元组同时出现情况: {tuple_presence}",
        )
    )

    signal_presence = {
        name: all(token.lower() in combined.lower() for token in tokens)
        for name, tokens in REQUIRED_SIGNALS.items()
    }
    checks.append(
        expectation(
            "产物保留硬件、语音链路、延迟、打断、可观测和恢复信号",
            all(signal_presence.values()),
            f"信号检查: {signal_presence}",
        )
    )

    judgment_ids = set(re.findall(r"\bJ\d+\b", spec))
    decision_ids = set(re.findall(r"\bD\d+\b", modules))
    checks.append(
        expectation(
            "spec.md 拉式记录判断依据且 modules.md 是关键决策真源",
            "## 判断依据" in spec
            and bool(judgment_ids)
            and "## 关键决策" in modules
            and bool(decision_ids)
            and "## 关键决策" not in design,
            f"J={sorted(judgment_ids)}; D={sorted(decision_ids)}; design 定义关键决策={'## 关键决策' in design}",
        )
    )

    trace_rows = trace_row_count(spec)
    checks.append(
        expectation(
            "spec.md 至少包含九行用户要求追溯",
            trace_rows >= 9,
            f"用户追溯数据行计数: {trace_rows}",
        )
    )

    forbidden_names = sorted(
        name for name in files if "task" in name.lower() or "checklist" in name.lower() or name == "README.md"
    )
    checks.append(
        expectation(
            "输出不含 task、checklist 或 README 产物",
            not forbidden_names,
            f"命中的禁止文件: {forbidden_names}",
        )
    )

    passed = sum(bool(item["passed"]) for item in checks)
    return {
        "expectations": checks,
        "summary": {
            "passed": passed,
            "failed": len(checks) - passed,
            "total": len(checks),
            "pass_rate": passed / len(checks),
        },
        "validator": {
            "command": command,
            "exit_code": completed.returncode,
            "payload": validator_payload,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("outputs_dir", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    result = grade(args.outputs_dir.resolve())
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
