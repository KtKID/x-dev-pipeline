"""xdev start / coverage / check（x-dev/scripts/delivery.py）的测试。"""
import json
import os
import subprocess
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from test.test_checklist_engine import DESIGN, SPEC, run

ROWS = [
    "| T1 | 借书与上限（用例 T1、T2；C1；D01、D02；unit） | feat01 场景1, 场景2 | src/loan/borrow.py, tests/test_borrow.py | None | A | None | [x] 🟢 |",
    "| T2 | 续借（用例 T3、T4；D02、D03；unit） | feat02 场景1-2 | src/loan/renew.py, tests/test_renew.py | None | A | T1 | [x] 🟢 |",
    "| T3 | 逾期天数（用例 T5；D02；unit） | feat03 场景1 | src/loan/overdue.py, tests/test_overdue.py | None | A | T1 | [x] 🟢 |",
]

MAPPING = [
    "| T1 | tests/test_borrow.py::test_borrow_ok | unit | 通过 |",
    "| T2 | tests/test_borrow.py::test_sixth_rejected | unit | 通过 |",
    "| T3 | tests/test_renew.py::test_renew | unit | 通过 |",
    "| T4 | tests/test_renew.py::test_overdue_rejected | unit | 通过 |",
    "| T5 | tests/test_overdue.py::test_days | unit | 通过 |",
]

BORROW = "def borrow(n):\n    if n >= 5:\n        return 'rejected'\n    return 'ok'\n"

# 测试命令：写一份 coverage.py JSON 报告；covered 环境变量决定 borrow.py 第 3 行有没有跑到
REPORT_SCRIPT = textwrap.dedent("""\
    import json, os, sys
    full = os.environ.get("COVER_ALL") == "1"
    files = {"src/loan/borrow.py": {"executed_lines": [1, 2, 4] + ([3] if full else []),
                                    "missing_lines": [] if full else [3]}}
    json.dump({"files": files}, open("cov.json", "w"))
    sys.exit(int(os.environ.get("FAIL", "0")))
    """)


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


class DeliveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@t")
        git(self.root, "config", "user.name", "t")
        self.spec_dir = self.root / "docs/spec/loan"
        self.task = self.spec_dir / "tasks/task-core"
        self.task.mkdir(parents=True)
        (self.spec_dir / "spec.md").write_text(SPEC, encoding="utf-8")
        (self.spec_dir / "tech-design.md").write_text(DESIGN, encoding="utf-8")
        tests = {
            "tests/test_borrow.py": "def test_borrow_ok(): pass\ndef test_sixth_rejected(): pass\n",
            "tests/test_renew.py": "def test_renew(): pass\ndef test_overdue_rejected(): pass\n",
            "tests/test_overdue.py": "def test_days(): pass\n",
        }
        for f in ["src/loan/borrow.py", "src/loan/renew.py", "src/loan/overdue.py"]:
            (self.root / f).parent.mkdir(parents=True, exist_ok=True)
            (self.root / f).write_text("", encoding="utf-8")
        for f, body in tests.items():
            (self.root / f).parent.mkdir(parents=True, exist_ok=True)
            (self.root / f).write_text(body, encoding="utf-8")
        (self.root / "make_report.py").write_text(REPORT_SCRIPT, encoding="utf-8")
        (self.root / ".gitignore").write_text("cov.json\n", encoding="utf-8")
        self.cwd = os.getcwd()
        os.chdir(self.root)
        self.write(ROWS, MAPPING)
        self.assertEqual(run("baseline", str(self.task))[0], 0)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")
        code, out, err = run("start", str(self.task))
        self.assertEqual(code, 0, err)
        # 开发：改 borrow.py
        (self.root / "src/loan/borrow.py").write_text(BORROW, encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        os.environ.pop("COVER_ALL", None)
        os.environ.pop("FAIL", None)
        self.tmp.cleanup()

    def write(self, rows, mapping, risk="Q1"):
        path = self.task / "dev-checklist.md"
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        keep = {k: next((l for l in old.splitlines() if l.startswith(f"> {k}")), None) for k in ("拆解基线", "代码基线")}
        text = textwrap.dedent(f"""\
            # task-core · 开发清单

            > spec: docs/spec/loan/spec.md
            > 状态：待验证
            > 执行者：未知
            > tech-design: docs/spec/loan/tech-design.md
            > 本轮范围：feat01 场景1-2、feat02 场景1-2、feat03 场景1
            > 范围依据：用户确认的 spec
            > 拆解基线：<由 xdev baseline 写入>
            > risk: {risk}
            > 分组理由：1 组：改动小
            > 创建: 2026-11-21

            | # | 任务 | 场景回指 | 涉及文件 | 风险 | 并行组 | 依赖 | 状态 |
            |---|---|---|---|---|---|---|---|
            """) + "\n".join(rows) + textwrap.dedent("""

            ## 结果

            ### 用例对应

            | 用例 | 测试位置 | 层级 | 结果 |
            |---|---|---|---|
            """) + "\n".join(mapping) + "\n"
        if keep["拆解基线"] and "<" not in keep["拆解基线"]:
            text = text.replace("> 拆解基线：<由 xdev baseline 写入>", keep["拆解基线"])
        if keep["代码基线"]:
            text = text.replace("> 创建: 2026-11-21", keep["代码基线"] + "\n> 创建: 2026-11-21")
        path.write_text(text, encoding="utf-8")

    def coverage(self):
        return run("coverage", str(self.task), "--cmd", "python3 make_report.py", "--report", "cov.json", "--json")

    def check(self):
        code, out, _ = run("check", str(self.task), "--json")
        return code, [p["rule"] for p in json.loads(out)["problems"]], json.loads(out)

    # start
    def test_start_records_head_once(self):
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, capture_output=True, text=True).stdout.strip()
        text = (self.task / "dev-checklist.md").read_text(encoding="utf-8")
        self.assertIn(f"> 代码基线：{head}", text)
        git(self.root, "commit", "-qam", "later", "--allow-empty")
        run("start", str(self.task))
        self.assertIn(f"> 代码基线：{head}", (self.task / "dev-checklist.md").read_text(encoding="utf-8"))

    # coverage
    def test_uncovered_line_is_listed_and_fails(self):
        code, out, _ = self.coverage()
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["covered"], 3)
        self.assertEqual(data["files"]["src/loan/borrow.py"]["uncovered"], "3")
        text = (self.task / "dev-checklist.md").read_text(encoding="utf-8")
        self.assertIn("> 覆盖率：❌ 75%", text)

    def test_full_coverage_passes_and_check_passes(self):
        os.environ["COVER_ALL"] = "1"
        code, out, _ = self.coverage()
        self.assertEqual(code, 0, out)
        self.receipt(checked="无")
        code, rules, payload = self.check()
        self.assertEqual(rules, [], payload)
        self.assertEqual(code, 0)

    def test_failing_test_command_fails_even_at_100(self):
        os.environ["COVER_ALL"] = "1"
        os.environ["FAIL"] = "1"
        self.assertEqual(self.coverage()[0], 1)
        self.assertIn("TESTS", self.check()[1])

    def test_changed_file_missing_from_report_counts_as_uncovered(self):
        os.environ["COVER_ALL"] = "1"
        (self.root / "src/loan/renew.py").write_text("def renew():\n    return 14\n", encoding="utf-8")
        code, out, _ = self.coverage()
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(data["not_in_report"], {"src/loan/renew.py": "1-2"})

    def test_file_without_coverage_tool_accepted_with_reason(self):
        os.environ["COVER_ALL"] = "1"
        (self.root / "src/loan/run.sh").write_text("echo hi\n", encoding="utf-8")
        self.assertEqual(self.coverage()[0], 1)
        self.assertIn("COVERAGE", self.check()[1])
        path = self.task / "dev-checklist.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n### 问题与处置\n\n- src/loan/run.sh 没有 shell 覆盖率工具，T1 的 smoke 会调它\n", encoding="utf-8")
        self.receipt(checked="无")
        self.assertEqual(self.check()[1], [])

    def test_no_git_repo_is_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            task = Path(d) / "t.md"
            task.write_text("# t\n\n> 状态：x\n", encoding="utf-8")
            code, _, err = run("start", str(task))
            self.assertEqual(code, 2)
            self.assertIn("git", err)

    def test_new_untracked_file_counts(self):
        os.environ["COVER_ALL"] = "1"
        (self.root / "src/loan/fine.py").write_text("X = 1\n", encoding="utf-8")
        data = json.loads(self.coverage()[1])
        self.assertIn("src/loan/fine.py", data["not_in_report"])

    def test_test_files_and_docs_are_not_counted(self):
        os.environ["COVER_ALL"] = "1"
        (self.root / "tests/test_borrow.py").write_text("def test_borrow_ok(): pass\ndef test_sixth_rejected(): pass\nx = 1\n", encoding="utf-8")
        (self.root / "docs/notes.py").write_text("y = 2\n", encoding="utf-8")
        self.assertEqual(self.coverage()[0], 0)

    def test_code_changed_after_coverage_is_stale(self):
        os.environ["COVER_ALL"] = "1"
        self.coverage()
        (self.root / "src/loan/borrow.py").write_text(BORROW + "# later\n", encoding="utf-8")
        self.assertIn("COVERAGE_STALE", self.check()[1])

    def test_exclusion_marker_needs_reason(self):
        os.environ["COVER_ALL"] = "1"
        (self.root / "src/loan/borrow.py").write_text(BORROW.replace("return 'ok'", "return 'ok'  # pragma: no cover"), encoding="utf-8")
        self.coverage()
        self.assertIn("COVERAGE_EXCLUDE", self.check()[1])
        path = self.task / "dev-checklist.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n### 问题与处置\n\n- src/loan/borrow.py:4 防御分支，测试环境造不出来\n", encoding="utf-8")
        self.assertNotIn("COVERAGE_EXCLUDE", self.check()[1])

    def test_out_dir_leaves_checklist_alone(self):
        os.environ["COVER_ALL"] = "1"
        before = (self.task / "dev-checklist.md").read_text(encoding="utf-8")
        code, _, _ = run("coverage", str(self.task), "--cmd", "python3 make_report.py", "--report", "cov.json", "--out", str(self.root / "w"))
        self.assertEqual(code, 0)
        self.assertTrue((self.root / "w/coverage.json").is_file())
        self.assertEqual(before, (self.task / "dev-checklist.md").read_text(encoding="utf-8"))

    # 功能检查回执
    def receipt(self, verdict="通过", rows="", checked="tests/test_borrow.py"):
        path = self.task / "evidence" / "feature-check.md"
        path.write_text(
            f"功能检查回执 · task-core · 结论：{verdict} · P0 ×0 · P1 ×0 · P2 ×0\n已检查：{checked}（共 3 个测试函数）\n\n"
            "| 编号 | 位置 | 严重度 | 问题类型 | 证据 | 怎么改 |\n|---|---|---|---|---|---|\n" + rows + "\n穷尽声明：已检查范围内没有其他问题。\n",
            encoding="utf-8")
        return str(path)

    def change_test(self, extra="\ndef test_more(): assert 1 == 1\n"):
        f = self.root / "tests/test_borrow.py"
        f.write_text(f.read_text(encoding="utf-8") + extra, encoding="utf-8")

    def test_q1_needs_feature_check_even_without_test_changes(self):
        os.environ["COVER_ALL"] = "1"
        self.coverage()
        problems = self.check()[2]["problems"]
        self.assertEqual([p["rule"] for p in problems], ["FEATURE_CHECK"])
        self.assertIn("派工单照抄这份完整清单）：无", problems[0]["msg"])
        self.receipt(checked="无")
        self.assertEqual(self.check()[1], [])

    def test_q0_skips_feature_check(self):
        os.environ["COVER_ALL"] = "1"
        rows = [r.replace(r.split("|")[3], " None ") for r in ROWS]
        self.write(rows, MAPPING, risk="Q0")
        self.change_test()
        self.coverage()
        self.assertEqual(self.check()[1], [])
        code, out, _ = run("check", str(self.task))
        self.assertEqual(code, 0, out)
        self.assertIn("不需要功能检查", out)

    def test_changed_test_is_listed(self):
        os.environ["COVER_ALL"] = "1"
        self.change_test()
        self.coverage()
        self.assertIn("FEATURE_CHECK", self.check()[1])
        msg = " ".join(p["msg"] for p in self.check()[2]["problems"])
        self.assertIn("tests/test_borrow.py", msg)

    def test_feature_check_pass_shows_coverage_and_p2(self):
        os.environ["COVER_ALL"] = "1"
        self.change_test()
        self.coverage()
        self.receipt(rows="| issue-1 | tests/test_borrow.py::test_more | P2 | 数据测不出对错 | x | y |\n")
        code, out, _ = run("check", str(self.task))
        self.assertEqual(code, 0, out)
        self.assertIn("改动行覆盖率 100%（4/4 行）", out)
        self.assertIn("功能检查通过（P2 ×1）", out)

    def test_test_edit_after_receipt_makes_both_stale(self):
        os.environ["COVER_ALL"] = "1"
        self.change_test()
        self.coverage()
        self.receipt()
        self.change_test("\ndef test_red(): assert False\n")
        self.assertIn("COVERAGE_STALE", self.check()[1])
        time.sleep(0.01)
        self.coverage()
        self.assertIn("FEATURE_CHECK_STALE", self.check()[1])
        self.receipt()
        self.assertNotIn("FEATURE_CHECK_STALE", self.check()[1])

    def test_p1_blocks_until_fixed_or_rebutted(self):
        os.environ["COVER_ALL"] = "1"
        self.change_test()
        self.coverage()
        self.receipt("不通过", "| issue-1 | tests/test_borrow.py::test_more | P1 | 断言恒真 | tests/test_borrow.py:3 `assert 1 == 1` | 断言借书结果 |\n"
                             "| issue-12 | src/loan/borrow.py:2 | P0 | 漏了要的 | x | y |\n")
        self.assertIn("FEATURE_CHECK_OPEN", self.check()[1])
        path = self.task / "dev-checklist.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n### 问题与处置\n\n- 功能检查 · issue-1 · 不采纳：这是占位冒烟，真实断言在 test_borrow_ok\n", encoding="utf-8")
        msg = " ".join(p["msg"] for p in self.check()[2]["problems"])
        self.assertIn("issue-12", msg)
        self.assertNotIn("issue-1、", msg)
        path.write_text(path.read_text(encoding="utf-8") + "- 功能检查 · issue-12 · 不采纳：第 2 行就是上限判断\n", encoding="utf-8")
        self.assertEqual(self.check()[1], [])

    def test_failed_verdict_without_blocking_issue_is_flagged(self):
        os.environ["COVER_ALL"] = "1"
        self.coverage()
        self.receipt("不通过", checked="无")
        self.assertIn("FEATURE_CHECK_OPEN", self.check()[1])

    def test_receipt_must_list_every_changed_test_exactly(self):
        os.environ["COVER_ALL"] = "1"
        self.change_test()
        (self.root / "tests/test_new.py").write_text("def test_new(): pass\n", encoding="utf-8")
        self.coverage()
        self.receipt()
        self.assertIn("FEATURE_CHECK", self.check()[1])
        self.receipt(checked="x/tests/test_borrow.py.bak、tests/test_new.py")
        problems = self.check()[2]["problems"]
        self.assertEqual([p["rule"] for p in problems], ["FEATURE_CHECK"])
        self.assertIn("tests/test_borrow.py、tests/test_new.py", problems[0]["msg"])  # 重做时也给完整清单
        self.receipt(checked="\n- tests/test_borrow.py\n- tests/test_new.py")
        self.assertEqual(self.check()[1], [])

    def test_receipt_with_heading_still_reads_findings(self):
        os.environ["COVER_ALL"] = "1"
        self.change_test()
        self.coverage()
        path = self.task / "evidence" / "feature-check.md"
        path.write_text("功能检查回执 · task-core · 结论：通过\n已检查：tests/test_borrow.py\n\n## 问题\n\n"
                        "| 编号 | 位置 | 严重度 | 问题类型 | 证据 | 怎么改 |\n|---|---|---|---|---|---|\n| issue-1 | tests/test_borrow.py::test_more | P1 | 断言恒真 | x | y |\n", encoding="utf-8")
        self.assertIn("FEATURE_CHECK_OPEN", self.check()[1])

    def test_old_receipt_name_is_not_accepted(self):
        os.environ["COVER_ALL"] = "1"
        self.coverage()
        (self.task / "evidence" / "test-integrity.md").write_text("测试真实性检查回执 · task-core · 结论：通过\n已检查：无\n", encoding="utf-8")
        self.assertIn("FEATURE_CHECK", self.check()[1])

    # check
    def test_check_without_coverage_record(self):
        self.assertIn("COVERAGE", self.check()[1])

    def test_missing_case_mapping_and_scene(self):
        os.environ["COVER_ALL"] = "1"
        self.write(ROWS, MAPPING[:4])
        self.coverage()
        rules = self.check()[1]
        self.assertIn("CASE_UNMAPPED", rules)
        self.assertIn("SCENE_UNCOVERED", rules)

    def test_mapping_to_missing_test(self):
        os.environ["COVER_ALL"] = "1"
        self.write(ROWS, [MAPPING[0].replace("test_borrow_ok", "test_nope")] + MAPPING[1:])
        self.coverage()
        self.assertIn("MAPPING_PATH", self.check()[1])

    def test_failed_case_result(self):
        os.environ["COVER_ALL"] = "1"
        self.write(ROWS, [MAPPING[0].replace("通过", "失败")] + MAPPING[1:])
        self.coverage()
        rules = self.check()[1]
        self.assertIn("MAPPING_RESULT", rules)
        self.assertIn("SCENE_UNCOVERED", rules)

    def test_row_not_green(self):
        os.environ["COVER_ALL"] = "1"
        self.write([ROWS[0].replace("[x] 🟢", "[ ] 🟡")] + ROWS[1:], MAPPING)
        self.coverage()
        self.assertIn("ROW_STATUS", self.check()[1])

    def test_high_risk_row_needs_real_chain(self):
        os.environ["COVER_ALL"] = "1"
        rows = [ROWS[0].replace("| None | A |", "| 高:改写借阅上限判断 | A |")] + ROWS[1:]
        self.write(rows, MAPPING, risk="Q2")
        self.coverage()
        self.assertIn("HIGH_RISK", self.check()[1])
        self.write(rows, [MAPPING[0].replace("| unit |", "| smoke |")] + MAPPING[1:], risk="Q2")
        self.coverage()
        self.assertNotIn("HIGH_RISK", self.check()[1])

    def test_spec_change_after_baseline(self):
        os.environ["COVER_ALL"] = "1"
        self.coverage()
        spec = self.spec_dir / "spec.md"
        spec.write_text(spec.read_text(encoding="utf-8").replace("今天加 30 天", "今天加 21 天"), encoding="utf-8")
        self.assertIn("SPEC_CHANGED", self.check()[1])

    def test_result_tables_are_not_task_rows(self):
        code, out, _ = run("validate", str(self.task), "--json")
        self.assertEqual(json.loads(out)["packages"][0]["issues"], [])


QDEV = textwrap.dedent("""\
    # 借书上限提示

    > 所属 spec：[loan](../spec.md)
    > 状态：进行中
    > 执行者：未知
    > 创建：2026-11-21

    ## ① 需求与变更

    - spec 归属与确认：{confirm}

    ## ③ 测试用例与变化

    | 用例 / 主定义 | 变化类型 | 依据 | 预期 | 位置 |
    |---|---|---|---|---|
    | T1 | 新增 | feat01 场景2 | 提示上限 | unit |
    | T2 | 删除 | feat01 场景9 | 旧提示 | unit |

    ## ⑤ 验证结果

    ### 用例对应

    | 用例 | 测试位置 | 层级 | 结果 |
    |---|---|---|---|
    {mapping}
    """)


class QdevCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@t")
        git(self.root, "config", "user.name", "t")
        (self.root / "docs/spec/loan/tasks").mkdir(parents=True)
        (self.root / "docs/spec/loan/spec.md").write_text(SPEC, encoding="utf-8")
        (self.root / "src").mkdir()
        (self.root / "src/limit.py").write_text("", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests/test_limit.py").write_text("def test_limit(): pass\n", encoding="utf-8")
        (self.root / "make_report.py").write_text(
            "import json\njson.dump({'files': {'src/limit.py': {'executed_lines': [1], 'missing_lines': []}}}, open('cov.json', 'w'))\n",
            encoding="utf-8")
        (self.root / ".gitignore").write_text("cov.json\n", encoding="utf-8")
        self.task = self.root / "docs/spec/loan/tasks/limit-hint.md"
        self.task.write_text(QDEV.format(confirm="2026-11-21 用户回复“可以”", mapping="| T1 | tests/test_limit.py::test_limit | unit | 通过 |"), encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")
        self.cwd = os.getcwd()
        os.chdir(self.root)
        self.assertEqual(run("start", str(self.task))[0], 0)
        (self.root / "src/limit.py").write_text("LIMIT = 5\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def rules(self, receipt=True):
        run("coverage", str(self.task), "--cmd", "python3 make_report.py", "--report", "cov.json")
        if receipt:
            (self.root / "docs/spec/loan/tasks/limit-hint-evidence/feature-check.md").write_text(
                "功能检查回执 · limit-hint · 结论：通过 · P0 ×0 · P1 ×0 · P2 ×0\n已检查：无\n\n"
                "| 编号 | 位置 | 严重度 | 问题类型 | 证据 | 怎么改 |\n|---|---|---|---|---|---|\n", encoding="utf-8")
        code, out, _ = run("check", str(self.task), "--json")
        return code, [p["rule"] for p in json.loads(out)["problems"]]

    def test_qdev_passes(self):
        self.assertEqual(self.rules(), (0, []))
        self.assertTrue((self.root / "docs/spec/loan/tasks/limit-hint-evidence/coverage.json").is_file())

    def test_qdev_with_scenes_needs_feature_check(self):
        self.assertEqual(self.rules(receipt=False), (1, ["FEATURE_CHECK"]))

    def test_qdev_without_scenes_skips_feature_check(self):
        text = self.task.read_text(encoding="utf-8").replace("2026-11-21 用户回复“可以”", "只记变更，未写场景，无需确认")
        self.task.write_text(text, encoding="utf-8")
        self.assertEqual(self.rules(receipt=False), (0, []))

    def test_qdev_mixed_confirmation_still_needs_feature_check(self):
        text = self.task.read_text(encoding="utf-8").replace("2026-11-21 用户回复“可以”", "engineering 只记变更，无需确认；loan 已确认（2026-11-21 用户回复“可以”）")
        self.task.write_text(text, encoding="utf-8")
        self.assertEqual(self.rules(receipt=False), (1, ["FEATURE_CHECK"]))

    def test_qdev_missing_confirmation_and_case(self):
        text = self.task.read_text(encoding="utf-8")
        text = text.replace("2026-11-21 用户回复“可以”", "<用户确认的时间>").replace("| T1 | tests/test_limit.py::test_limit | unit | 通过 |", "")
        self.task.write_text(text, encoding="utf-8")
        code, rules = self.rules()
        self.assertEqual(code, 1)
        self.assertIn("SPEC_CONFIRM", rules)
        self.assertIn("CASE_UNMAPPED", rules)


class ReportFormatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@t")
        git(self.root, "config", "user.name", "t")
        (self.root / "pkg").mkdir()
        (self.root / "pkg/a.go").write_text("package pkg\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")
        self.base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, capture_output=True, text=True).stdout.strip()
        (self.root / "pkg/a.go").write_text("package pkg\n\nfunc A(x int) int {\n\tif x > 0 {\n\t\treturn 1\n\t}\n\treturn 0\n}\n", encoding="utf-8")
        from test.test_checklist_engine import xdev
        self.delivery = xdev.delivery

    def tearDown(self):
        self.tmp.cleanup()

    def measure(self, name, body):
        report = self.root / name
        report.write_text(body, encoding="utf-8")
        return self.delivery.measure(self.root, self.base, [report])

    def test_go_profile_with_module_path(self):
        data = self.measure("c.out", "mode: set\nexample.com/m/pkg/a.go:3.20,4.11 1 1\nexample.com/m/pkg/a.go:4.11,6.3 1 0\nexample.com/m/pkg/a.go:7.2,7.10 1 1\n")
        self.assertEqual(data["files"]["pkg/a.go"]["uncovered"], "5-6")

    def test_lcov(self):
        data = self.measure("lcov.info", f"SF:{self.root}/pkg/a.go\nDA:3,1\nDA:4,1\nDA:5,0\nDA:7,1\nend_of_record\n")
        self.assertEqual(data["files"]["pkg/a.go"]["uncovered"], "5")
        self.assertEqual(data["total"], 4)

    def test_cobertura(self):
        xml = f"""<?xml version="1.0"?><coverage><sources><source>{self.root}</source></sources><packages><package><classes>
        <class filename="pkg/a.go"><lines><line number="3" hits="1"/><line number="5" hits="2"/><line number="7" hits="0"/></lines></class>
        </classes></package></packages></coverage>"""
        data = self.measure("cov.xml", xml)
        self.assertEqual(data["files"]["pkg/a.go"]["uncovered"], "7")
        self.assertEqual(data["covered"], 2)


if __name__ == "__main__":
    unittest.main()
