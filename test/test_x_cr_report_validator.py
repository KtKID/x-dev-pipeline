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
# CR 报告：审批规则

> 模式：检查代码

## 范围

- 现象或检查目标：审批模块 diff

## 规则表

| 编号 | 规则 | 来源 | 最小反例 | 结论 | 问题 |
|---|---|---|---|---|---|
| harness:C2 | 审批范围只能收窄 | spec.md C2 | 批准 git status 后执行 git push | 被打破 | B1 |
| 新1 | 登录主体来自服务端 | spec 没写；`src/auth.py` 的 `login()` | 传 role=admin | 守住了 | - |

## 问题

| ID | 严重度 | 状态 | 位置 | 一句话 |
|---|---|---|---|---|
| B1 | P0 | 待修 | `src/approve.py` 的 `remember()` 第 12 行 | 审批范围扩大 |

### B1: 审批范围扩大

- 规则：harness:C2
- 位置：`src/approve.py` 的 `remember()`，第 12 行
- 反例：GIVEN 只批准 git status WHEN 执行 git push THEN 被放行
- 证据：remember() 把命令截成根命令 git
- 影响：越权执行
- 怎么改：保存完整命令

## 结论

- 最严重的问题：B1
"""

FIXED = """
**修复**

- 结果：已修
- 改动位置：`src/approve.py` 的 `remember()`，第 12–14 行
- 反例测试：`tests/test_approve.py::test_push_rejected`
- 验证：pytest 全量 30 通过
"""


def fixed_report(fix: str = FIXED, status: str = "已修") -> str:
    return VALID_REPORT.replace("| B1 | P0 | 待修 |", f"| B1 | P0 | {status} |").replace(
        "- 怎么改：保存完整命令\n", "- 怎么改：保存完整命令\n" + fix
    )


class XCrReportValidatorTest(unittest.TestCase):
    def test_accepts_valid_report(self) -> None:
        self.assertEqual(VALIDATOR.validate_text(VALID_REPORT), [])

    def test_accepts_fixed_report(self) -> None:
        self.assertEqual(VALIDATOR.validate_text(fixed_report()), [])

    def test_rejects_missing_section(self) -> None:
        self.assertIn("缺少 `## 规则表`", VALIDATOR.validate_text(VALID_REPORT.replace("## 规则表", "## 别的")))

    def test_rejects_missing_detail(self) -> None:
        report = VALID_REPORT.split("### B1:")[0] + "## 结论\n"
        self.assertIn("B1 缺少 `### B1:` 详情", VALIDATOR.validate_text(report))

    def test_rejects_bad_rule_id_and_result(self) -> None:
        report = VALID_REPORT.replace("| 新1 |", "| INV-CAND-01 |").replace("| 被打破 | B1 |", "| 破坏 | B1 |")
        errors = VALIDATOR.validate_text(report)
        self.assertTrue(any("规则编号不对：`INV-CAND-01`" in e for e in errors))
        self.assertTrue(any("harness:C2 的结论不对" in e for e in errors))

    def test_broken_rule_needs_issue(self) -> None:
        report = VALID_REPORT.replace("| 被打破 | B1 |", "| 被打破 | - |")
        self.assertIn("harness:C2 结论是被打破，要连到一个问题（B1…）", VALIDATOR.validate_text(report))

    def test_unverified_rule_needs_issue(self) -> None:
        report = VALID_REPORT.replace("| 守住了 | - |", "| 没法验证 | - |")
        self.assertIn("新1 结论是没法验证，要连到一个问题（B1…）", VALIDATOR.validate_text(report))

    def test_rejects_bad_severity_and_status(self) -> None:
        report = VALID_REPORT.replace("| B1 | P0 | 待修 |", "| B1 | P3 | ❌ |")
        errors = VALIDATOR.validate_text(report)
        self.assertTrue(any("B1 的严重度不对" in e for e in errors))
        self.assertTrue(any("B1 的状态不对" in e for e in errors))

    def test_fixed_needs_fix_block(self) -> None:
        report = VALID_REPORT.replace("| B1 | P0 | 待修 |", "| B1 | P0 | 已修 |")
        self.assertIn("B1 状态是已修，详情里缺少「**修复**」段", VALIDATOR.validate_text(report))

    def test_fix_result_must_match_status(self) -> None:
        report = fixed_report(status="误报不修")
        self.assertTrue(any("两处要一致" in e for e in VALIDATOR.validate_text(report)))

    def test_rejects_commit_hash_location(self) -> None:
        report = fixed_report(FIXED.replace("`src/approve.py` 的 `remember()`，第 12–14 行", "commit `3f2a9c1e`"))
        self.assertTrue(any("commit 哈希" in e for e in VALIDATOR.validate_text(report)))

    def test_p0_fixed_needs_regression_test(self) -> None:
        report = fixed_report(FIXED.replace("`tests/test_approve.py::test_push_rejected`", "无，不好测"))
        self.assertTrue(any("反例测试" in e for e in VALIDATOR.validate_text(report)))

    def test_false_positive_needs_reason(self) -> None:
        report = fixed_report("\n**修复**\n\n- 结果：误报不修\n", status="误报不修")
        self.assertIn("B1 误报不修，修复段缺少「理由」", VALIDATOR.validate_text(report))


if __name__ == "__main__":
    unittest.main()
