"""实操题判分脚本自测：fix-mixed 不动要判不过；按参考做法修要全过；偷懒的反例测试要被抓到。"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "evals/scripts/handson_setup.py"
GRADE = ROOT / "evals/scripts/handson_grade.py"

NEW_TESTS = '''

import pytest
from library.loan import RenewLimitError, list_loans


def test_list_ignores_client_member_id():
    store = LoanStore([Loan(1, 10, date(2026, 12, 1)), Loan(2, 20, date(2026, 12, 1))])
    assert [l.member_id for l in list_loans(store, 10, {"member_id": 20})] == [10]


def test_third_renewal_rejected():
    store = LoanStore([Loan(1, 10, date(2026, 12, 1))])
    renew(store, 1)
    renew(store, 1)
    with pytest.raises(RenewLimitError):
        renew(store, 1)
'''

BLOCKS = {
    "B1": "\n**修复**\n\n- 结果：已修\n- 改动位置：`src/library/loan.py` 的 `list_loans()`\n- 反例测试：`tests/test_loan.py::test_list_ignores_client_member_id`\n- 验证：全量通过\n",
    "B2": "\n**修复**\n\n- 结果：已修\n- 改动位置：`src/library/loan.py` 的 `renew()`\n- 反例测试：`tests/test_loan.py::test_third_renewal_rejected`\n- 验证：全量通过\n",
    "B3": "\n**修复**\n\n- 结果：误报不修\n- 理由：`return_book()` 已核对归属\n",
    "B4": "\n**修复**\n\n- 结果：待确认\n- 要确认：上限 50 还是 100 元\n",
}


def grade(work: Path) -> dict:
    out = subprocess.run([sys.executable, str(GRADE), "fix-mixed", "fix", str(work), "--json"],
                         capture_output=True, text=True, timeout=300)
    return json.loads(out.stdout)


def reference_fix(work: Path) -> None:
    code = work / "src/library/loan.py"
    t = code.read_text(encoding="utf-8")
    t = t.replace('member_id = request.get("member_id") or session_member_id\n    return store.by_member(member_id)',
                  "return store.by_member(session_member_id)")
    code.write_text(t.replace("if loan.renew_count > MAX_RENEWALS:", "if loan.renew_count >= MAX_RENEWALS:"), encoding="utf-8")
    tests = work / "tests/test_loan.py"
    tests.write_text(tests.read_text(encoding="utf-8") + NEW_TESTS, encoding="utf-8")
    report = next((work / "reports/cr").glob("cr-*.md"))
    r = report.read_text(encoding="utf-8")
    for b, st in [("B1", "已修"), ("B2", "已修"), ("B3", "误报不修"), ("B4", "待确认")]:
        r = re.sub(rf"^(\| {b} \| P\d \| )待修", rf"\g<1>{st}", r, flags=re.M)
    for b, nxt in [("B1", "B2"), ("B2", "B3"), ("B3", "B4"), ("B4", "B5")]:
        r = r.replace(f"\n### {nxt}:", BLOCKS[b] + f"\n### {nxt}:")
    report.write_text(r, encoding="utf-8")


class HandsonGradeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name) / "mixed"
        subprocess.run([sys.executable, str(SETUP), "fix-mixed", str(self.work)], check=True, capture_output=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_untouched_fails(self) -> None:
        result = grade(self.work)
        failed = {i["check"] for i in result["items"] if not i["ok"]}
        self.assertIn("B1 状态是已修", failed)
        self.assertIn("隐藏测试全过", failed)

    def test_reference_fix_passes(self) -> None:
        reference_fix(self.work)
        result = grade(self.work)
        self.assertEqual(result["passed"], result["total"], [i for i in result["items"] if not i["ok"]])

    def test_lazy_regression_test_caught(self) -> None:
        reference_fix(self.work)
        tests = self.work / "tests/test_loan.py"
        tests.write_text(tests.read_text(encoding="utf-8").replace(
            "    with pytest.raises(RenewLimitError):\n        renew(store, 1)\n", "    assert True\n"), encoding="utf-8")
        failed = {i["check"] for i in grade(self.work)["items"] if not i["ok"]}
        self.assertIn("B2 的反例测试修之前会失败", failed)

    def test_touching_out_of_report_function_caught(self) -> None:
        reference_fix(self.work)
        code = self.work / "src/library/loan.py"
        code.write_text(code.read_text(encoding="utf-8").replace("days=days + 1", "days=days"), encoding="utf-8")
        failed = {i["check"] for i in grade(self.work)["items"] if not i["ok"]}
        self.assertIn("extend_due() 没改", failed)


if __name__ == "__main__":
    unittest.main()
