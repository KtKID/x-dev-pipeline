#!/usr/bin/env python3
"""机械检查 x-spec2 边界 round-trip update eval。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


TRACE_IDS = ("D3", "U3", "U5", "U6", "U7", "U9", "J2", "J3", "J6")
SDK_CAPABILITIES = ("帧序号", "确认", "背压", "控制消息优先级", "断线续传")
SYNC_TARGETS = ("J8", "D3", "modules.md", "Requirement", "design.md")


def expectation(text: str, passed: bool, evidence: str) -> dict[str, object]:
    return {"text": text, "passed": passed, "evidence": evidence}


def grade(assessment: Path) -> dict[str, object]:
    body = assessment.read_text(encoding="utf-8", errors="replace") if assessment.is_file() else ""
    trace_presence = {token: token in body for token in TRACE_IDS}
    sdk_presence = {token: token in body for token in SDK_CAPABILITIES}
    sync_presence = {token: token in body for token in SYNC_TARGETS}

    checks = [
        expectation(
            "回答引用 D3 及其 U/J 依据",
            all(trace_presence.values()),
            f"追溯项: {trace_presence}",
        ),
        expectation(
            "回答恢复原选择理由、备选与否决原因、重评条件",
            all(token in body for token in ("原选择", "理由", "原备选", "否决原因", "原重评条件")),
            "检查原边界恢复的五个语义标签",
        ),
        expectation(
            "回答识别 SDK 新事实触发 D3 重评",
            "SDK" in body and "重评已触发" in body and all(sdk_presence.values()),
            f"SDK 能力: {sdk_presence}",
        ),
        expectation(
            "需求本质、系统目标和不变量稳定时判为原地细化",
            "原地细化" in body and all(token in body for token in ("需求本质", "系统目标", "系统不变量")),
            "检查分类与三项意图判据",
        ),
        expectation(
            "回答列出 J/D、模块、Requirement 与动态模型同步范围",
            all(sync_presence.values()) and "同步更新范围" in body,
            f"同步目标: {sync_presence}",
        ),
    ]
    passed = sum(bool(item["passed"]) for item in checks)
    return {
        "assessment": str(assessment),
        "expectations": checks,
        "summary": {
            "passed": passed,
            "failed": len(checks) - passed,
            "total": len(checks),
            "pass_rate": passed / len(checks),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("assessment", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    result = grade(args.assessment.resolve())
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
