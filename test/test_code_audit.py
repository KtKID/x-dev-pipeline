"""x-code-audit 的 audit.py：用 evals 里埋了问题的 library 项目跑一遍。"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "skills/x-code-audit/scripts/audit.py"
FIXTURE = ROOT / "evals/problems/code-audit/cases/library/project"
ITEMS = {
    "L3": ["功能描述对得上", "使用方式能用", "关键函数说明对得上", "spec 索引还对"],
    "L4": ["职责单一", "对外接口说清楚", "错误情况处理清楚", "测试真在测"],
    "L5": ["同一信息只在一处维护", "模块放对地方", "没有绕过既有抽象", "以前定的约束还守着", "没有多余的抽象"],
    "L6": ["循环里没有查库或调接口", "没有重复计算", "数据结构用得合适", "没有不必要的等待", "资源用完会释放"],
}


def audit(work: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(AUDIT), *args], cwd=work, capture_output=True, text=True, timeout=300)


def git(work: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=work, check=True, capture_output=True)


def receipt(unit: dict, items: list[str], problem: bool) -> str:
    rows = "\n".join(f"| {i} | {'有问题' if problem and n == 0 else '没问题'} | `src/library/loan/loan.py` 的 `renew()`，第 21 行 |"
                     for n, i in enumerate(items))
    issues = "未发现问题"
    if problem:
        issues = ("### 续借里顺带写日志文件\n\n- 严重度：P2\n- 是什么：renew() 里直接写 /tmp/renew.log。\n"
                  "- 影响：换日志方式要改续借代码。\n- 位置：`src/library/loan/loan.py` 的 `renew()`，第 28–29 行\n"
                  "- 证据：第 28 行 open('/tmp/renew.log')\n- 怎么改：改用 logging")
    return (f"# 回执\n\n- 单位：{unit['单位']}\n- 层：{unit['层']}\n- 范围：{unit['范围']}\n- 模型：test\n\n"
            f"## 检查项\n\n| 检查项 | 结论 | 位置 |\n|---|---|---|\n{rows}\n\n## 问题\n\n{issues}\n")


class CodeAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name) / "p"
        shutil.copytree(FIXTURE, self.work, ignore=shutil.ignore_patterns(".git", "__pycache__", "reports"))
        git(self.work, "init", "-q")
        git(self.work, "add", "-A")
        git(self.work, "commit", "-qm", "base")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def start(self, *args: str) -> dict:
        r = audit(self.work, "start", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def fill_units(self, aid: str, problem_unit: str | None = None) -> None:
        units = json.loads(audit(self.work, "units", aid).stdout)
        parts = self.work / f"reports/audit/audit-{aid}.parts"
        parts.mkdir(parents=True, exist_ok=True)
        report = (self.work / f"reports/audit/audit-{aid}.md").read_text(encoding="utf-8")
        for u in units:
            if u["层"] == "L2":
                block = report.split(f"交给 {u['单位']} 确认的候选：", 1)[1]
                items = re.findall(r"^\| (\w+) \| `", block, re.M)
            else:
                items = ITEMS[u["层"]]
            (parts / f"{u['单位']}.md").write_text(receipt(u, items, u["单位"] == problem_unit), encoding="utf-8")

    def test_full_run_finds_seeded_issues_and_verifies(self) -> None:
        aid = self.start()["id"]
        self.assertRegex(aid, r"^[0-9a-f]{8}$")
        self.assertEqual(audit(self.work, "scripts", aid).returncode, 0)
        report = (self.work / f"reports/audit/audit-{aid}.md").read_text(encoding="utf-8")
        for expected in ["extend_loan() 不存在", "RENEW_DAYS 的默认值写错了", "循环依赖", "下层依赖了上层",
                         "old_fine_rate 没人用", "命名规范（ruff N）", "链接失效"]:
            self.assertIn(expected, report)
        self.assertNotIn("handle_overdue 没人用", report)
        self.assertIn("MAX_RENEWALS", report)
        units = json.loads(audit(self.work, "units", aid).stdout)
        loan_l4 = next(u for u in units if u["层"] == "L4" and u["范围"] == "src/library/loan")
        self.fill_units(aid, problem_unit=loan_l4["单位"])
        self.assertEqual(audit(self.work, "merge", aid).returncode, 0)
        self.assertFalse((self.work / f"reports/audit/audit-{aid}.parts").exists())
        r = audit(self.work, "verify", aid)
        self.assertEqual(r.returncode, 0, r.stdout)
        report = (self.work / f"reports/audit/audit-{aid}.md").read_text(encoding="utf-8")
        self.assertIn("> 状态：完成", report)
        sev = re.findall(r"^### A\d+ · (P\d) ·", report, re.M)
        self.assertEqual(sev, sorted(sev))
        self.assertIn("续借里顺带写日志文件", report)
        self.assertEqual(len(list((self.work / "reports/audit").glob("*"))), 1)

    def test_verify_catches_missing_item_and_fake_location(self) -> None:
        aid = self.start()["id"]
        audit(self.work, "scripts", aid)
        self.fill_units(aid)
        units = json.loads(audit(self.work, "units", aid).stdout)
        l4 = next(u for u in units if u["层"] == "L4")
        part = self.work / f"reports/audit/audit-{aid}.parts/{l4['单位']}.md"
        text = part.read_text(encoding="utf-8").replace("| 测试真在测 | 没问题 |", "| 测试真在测 | 看着还行 |")
        text = text.replace("| 职责单一 | 没问题 | `src/library/loan/loan.py` 的 `renew()`，第 21 行 |",
                            "| 职责单一 | 有问题 | `src/library/loan/loan.py` 的 `no_such()`，第 999 行 |")
        part.write_text(text, encoding="utf-8")
        audit(self.work, "merge", aid)
        out = audit(self.work, "verify", aid).stdout
        self.assertIn("结论不对", out)
        self.assertIn("no_such()", out)
        self.assertIn("问题里没有它的条目", out)

    def test_unfinished_units_fail_verify(self) -> None:
        aid = self.start()["id"]
        audit(self.work, "scripts", aid)
        r = audit(self.work, "verify", aid)
        self.assertEqual(r.returncode, 1)
        self.assertIn("还没做完", r.stdout)

    def test_module_mode_scope(self) -> None:
        info = self.start("--module", "src/library/notify")
        scopes = {u["范围"] for u in info["units"] if u["谁查"] == "子 agent"}
        self.assertEqual(scopes, {"src/library/notify"})
        audit(self.work, "scripts", info["id"])
        report = (self.work / f"reports/audit/audit-{info['id']}.md").read_text(encoding="utf-8")
        self.assertNotIn("old_fine_rate", report)
        self.assertIn("mailer.py", report)

    def test_incremental_after_completed_audit(self) -> None:
        aid = self.start()["id"]
        audit(self.work, "scripts", aid)
        self.fill_units(aid)
        audit(self.work, "merge", aid)
        self.assertEqual(audit(self.work, "verify", aid).returncode, 0)
        git(self.work, "add", "-A")
        git(self.work, "commit", "-qm", "audit done")
        f = self.work / "src/library/db/store.py"
        f.write_text(f.read_text(encoding="utf-8") + "\n\ndef unused_helper():\n    return 1\n", encoding="utf-8")
        git(self.work, "commit", "-qam", "change db")
        info = self.start()
        self.assertIn("增量", (self.work / info["report"]).read_text(encoding="utf-8"))
        scopes = {u["范围"] for u in info["units"] if u["谁查"] == "子 agent"}
        self.assertEqual(scopes, {"src/library/db"})
        audit(self.work, "scripts", info["id"])
        report = (self.work / info["report"]).read_text(encoding="utf-8")
        self.assertIn("unused_helper 没人用", report)
        self.assertNotIn("old_fine_rate", report)


if __name__ == "__main__":
    unittest.main()
