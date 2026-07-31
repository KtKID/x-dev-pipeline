from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "skills/x-cr/scripts/validate_report.py"
SPEC = importlib.util.spec_from_file_location("x_cr_report_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


VALID_REPORT = """\
# Correctness Review 报告

> Schema: x-cr-v2

## 不变量覆盖

| INV-ID | 不变量 | 结论 | 关联问题 |
|--------|--------|------|----------|
| INV-SPEC-01 | 审批范围只能收窄 | 破坏 | B1 |
| INV-CAND-01 | 登录主体来自服务端 | 保持 | - |

## 审查结论

### P0：阻断性正确性错误

| ID | 状态 | INV-ID | 检查项 | 置信度 |
|----|------|--------|--------|--------|
| B1 | ❌ | INV-SPEC-01 | 审批范围扩大 | 已确认 |

## 问题详情

### B1: 审批范围扩大

批准 `git status` 后错误放行了 `git push`。
"""


class XCrReportValidatorTest(unittest.TestCase):
    def test_accepts_valid_report(self) -> None:
        self.assertEqual(VALIDATOR.validate_text(VALID_REPORT), [])

    def test_rejects_missing_detail(self) -> None:
        report = VALID_REPORT.replace(
            "### B1: 审批范围扩大\n\n批准 `git status` 后错误放行了 `git push`。\n",
            "",
        )
        self.assertIn(
            "B1 缺少对应的 `### B1:` 详情",
            VALIDATOR.validate_text(report),
        )

    def test_rejects_duplicate_conclusion_id(self) -> None:
        duplicate = (
            "| B1 | ❌ | INV-SPEC-01 | 第二个问题 | 高 |\n"
        )
        report = VALID_REPORT.replace(
            "| B1 | ❌ | INV-SPEC-01 | 审批范围扩大 | 已确认 |\n",
            "| B1 | ❌ | INV-SPEC-01 | 审批范围扩大 | 已确认 |\n" + duplicate,
        )
        self.assertIn(
            "审查结论中的问题 ID 重复: `B1`",
            VALIDATOR.validate_text(report),
        )

    def test_rejects_broken_invariant_without_issue(self) -> None:
        report = VALID_REPORT.replace(
            "| INV-SPEC-01 | 审批范围只能收窄 | 破坏 | B1 |",
            "| INV-SPEC-01 | 审批范围只能收窄 | 破坏 | - |",
        )
        self.assertIn(
            "INV-SPEC-01 为破坏，必须关联一个 Bn",
            VALIDATOR.validate_text(report),
        )

    def test_rejects_invalid_severity_confidence_and_status(self) -> None:
        report = VALID_REPORT.replace(
            "### P0：阻断性正确性错误",
            "### P3：旧严重度",
        ).replace(
            "| B1 | ❌ | INV-SPEC-01 | 审批范围扩大 | 已确认 |",
            "| B1 | maybe | INV-SPEC-01 | 审批范围扩大 | 猜测 |",
        )
        errors = VALIDATOR.validate_text(report)
        self.assertIn("B1 的状态非法: `maybe`", errors)
        self.assertIn("B1 的严重度缺失或非法: ``", errors)
        self.assertIn("B1 的置信度缺失或非法: `猜测`", errors)


if __name__ == "__main__":
    unittest.main()
