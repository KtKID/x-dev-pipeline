"""当前格式 task 引擎（x-req/scripts/checklist_engine.py）经 xdev CLI 的测试。"""
import io
import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import importlib.util

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("xdev", ROOT / "skills/x-dev/scripts/xdev.py")
xdev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xdev)

SPEC = textwrap.dedent("""\
    # loan：借阅

    > spec：loan
    > 主要入口：src/loan/
    > 状态：在用
    > 最近更新：2026-11-20

    ## 关键约束（用户已确认）

    | 编号 | 约束与适用范围 | 可观察判据与禁止结果 | 确认依据 / 关联场景 |
    |---|---|---|---|
    | C1 | 同一读者最多借 5 本 | 第 6 本被拒 | feat01 场景1、场景2 |

    ## feat01: 借书

    场景1: 没到上限时借书成功
    - GIVEN 读者借的书没到上限（C1）
    - WHEN 借一本书
    - THEN 应还日期是今天加 30 天

    场景2: 到上限时被拒
    - GIVEN 读者借的书已到上限（C1）
    - WHEN 再借一本
    - THEN 提示“已达借阅上限”

    ## feat02: 续借

    场景1: 到期前续借
    - GIVEN 书还没到应还日期
    - WHEN 续借
    - THEN 应还日期是原应还日期加 14 天

    场景2: 逾期续借被拒
    - GIVEN 书已经逾期
    - WHEN 续借
    - THEN 提示“已逾期，不能续借”

    ## feat03: 逾期

    场景1: 逾期天数
    - GIVEN 应还日期之后还书
    - WHEN 还书
    - THEN 逾期天数 = 还书日期 − 应还日期
    """)

DESIGN = textwrap.dedent("""\
    # loan · 技术设计

    ## 必须遵守的技术约束

    | 规则 | 回指场景 / C | 适用入口与必须满足的结果 | 依据与状态 |
    |---|---|---|---|
    | D01 上限检查在借书事务内 | feat01 场景2、C1 | 借书接口 | 代码 |
    | D02 应还日期统一计算 | feat01 场景1、feat02 场景1、feat03 场景1 | dueDate | 代码 |
    | D03 逾期先拒绝 | feat02 场景2 | 续借接口 | 代码 |

    ## 附录 B：测试用例与覆盖矩阵

    | 用例、依据及目的 | 准备数据与操作 | 通过条件 | 测试层级、执行入口及状态 |
    |---|---|---|---|
    | T1 **Smoke** 借书成功 · feat01 场景1；D02 | 借一本 | 今天+30 | unit |
    | T2 第 6 本被拒 · feat01 场景2；C1；D01 | 已借 5 本 | 被拒 | unit |
    | T3 续借日期 · feat02 场景1；D02 | 续借 | +14 | unit |
    | T4 逾期续借被拒 · feat02 场景2；D03 | 逾期 | 被拒 | unit |
    | T5 逾期天数 · feat03 场景1；D02 | 逾期还书 | 天数正确 | unit |
    """)

ROWS = [
    "| T1 | 借书与上限（用例 T1、T2；C1；D01、D02；unit） | feat01 场景1, 场景2 | src/loan/borrow.ts, tests/borrow.test.ts | None | A | None | [ ] ⏳ |",
    "| T2 | 续借（用例 T3、T4；D02、D03；unit） | feat02 场景1-2 | src/loan/renew.ts, tests/renew.test.ts | None | B | None | [ ] ⏳ |",
    "| T3 | 逾期天数（用例 T5；D02；unit） | feat03 场景1 | src/loan/overdue.ts, tests/overdue.test.ts | None | C | T1 | [ ] ⏳ |",
]


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = xdev.main(list(args))
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class ChecklistEngineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.spec_dir = self.root / "docs/spec/loan"
        self.task = self.spec_dir / "tasks/task-core"
        self.task.mkdir(parents=True)
        (self.spec_dir / "spec.md").write_text(SPEC, encoding="utf-8")
        (self.spec_dir / "tech-design.md").write_text(DESIGN, encoding="utf-8")
        for f in ["src/loan/borrow.ts", "src/loan/renew.ts", "src/loan/overdue.ts",
                  "tests/borrow.test.ts", "tests/renew.test.ts", "tests/overdue.test.ts"]:
            (self.root / f).parent.mkdir(parents=True, exist_ok=True)
            (self.root / f).write_text("", encoding="utf-8")
        self.cwd = os.getcwd()
        os.chdir(self.root)
        self.write_checklist(ROWS, risk="Q1")
        code, _, err = run("baseline", str(self.task))
        self.assertEqual(code, 0, err)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def write_checklist(self, rows, risk="Q1", extra_tree=""):
        header = textwrap.dedent(f"""\
            # task-core · 开发清单

            > spec: docs/spec/loan/spec.md
            > 状态：待实现
            > 执行者：未知
            > tech-design: docs/spec/loan/tech-design.md
            > 本轮范围：feat01–feat03
            > 范围依据：用户确认的 spec
            > 拆解基线：<由 xdev baseline 写入>
            > risk: {risk}
            > 分组理由：3 组，文件互不重叠，每组一个完整功能
            > 创建: 2026-11-20

            | # | 任务 | 场景回指 | 涉及文件 | 风险 | 并行组 | 依赖 | 状态 |
            |---|---|---|---|---|---|---|---|
            """)
        tree = "\n## 影响文件树\n\n```text\n" + extra_tree + "```\n" if extra_tree else ""
        path = self.task / "dev-checklist.md"
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        base_line = next((l for l in old.splitlines() if l.startswith("> 拆解基线")), None)
        text = header + "\n".join(rows) + "\n" + tree
        if base_line and "<" not in base_line:
            text = text.replace("> 拆解基线：<由 xdev baseline 写入>", base_line)
        path.write_text(text, encoding="utf-8")

    def issues(self):
        code, out, err = run("validate", str(self.task), "--json")
        payload = json.loads(out)
        return code, [i["rule"] for i in payload["packages"][0]["issues"]], payload

    # validate
    def test_valid_checklist_passes(self):
        code, rules, payload = self.issues()
        self.assertEqual(rules, [], payload)
        self.assertEqual(code, 0)
        self.assertEqual(payload["packages"][0]["type"], "task")

    def test_missing_scene_reference(self):
        rows = ROWS[:2] + [ROWS[2].replace("feat03 场景1", "feat03 场景9")]
        self.write_checklist(rows)
        self.assertIn("SCENE_REF", self.issues()[1])

    def test_missing_case_and_d_reference(self):
        rows = [ROWS[0].replace("用例 T1、T2", "用例 T1、T9").replace("D01、D02", "D01、D07")] + ROWS[1:]
        self.write_checklist(rows)
        rules = self.issues()[1]
        self.assertIn("CASE_REF", rules)
        self.assertIn("D_REF", rules)

    def test_shared_file_in_different_groups_is_rejected(self):
        rows = [ROWS[0], ROWS[1].replace("src/loan/renew.ts", "src/loan/renew.ts, src/loan/borrow.ts"), ROWS[2]]
        self.write_checklist(rows)
        self.assertIn("GROUP_OVERLAP", self.issues()[1])

    def test_shared_file_in_same_group_is_fine(self):
        rows = [ROWS[0], ROWS[1].replace("src/loan/renew.ts", "src/loan/renew.ts, src/loan/borrow.ts").replace("| B |", "| A |"), ROWS[2]]
        self.write_checklist(rows)
        self.assertEqual(self.issues()[1], [])

    def test_dependency_cycle(self):
        rows = [ROWS[0].replace("| A | None |", "| A | T3 |"), ROWS[1], ROWS[2]]
        self.write_checklist(rows)
        self.assertIn("DEP_CYCLE", self.issues()[1])

    def test_unknown_dependency(self):
        rows = ROWS[:2] + [ROWS[2].replace("| C | T1 |", "| C | T8 |")]
        self.write_checklist(rows)
        self.assertIn("DEP", self.issues()[1])

    def test_risk_must_match_rows(self):
        self.write_checklist(ROWS, risk="Q3")
        self.assertIn("RISK", self.issues()[1])
        rows = [ROWS[0].replace("| None | A |", "| 高:并发借书 | A |")] + ROWS[1:]
        self.write_checklist(rows, risk="Q2")
        self.assertEqual(self.issues()[1], [])

    def test_missing_file_unless_marked_new(self):
        rows = ROWS[:2] + [ROWS[2].replace("src/loan/overdue.ts", "src/loan/fees.ts")]
        self.write_checklist(rows)
        self.assertIn("FILES", self.issues()[1])
        self.write_checklist(rows, extra_tree="src/loan/fees.ts   U  # 新增\n")
        self.assertEqual(self.issues()[1], [])

    def test_nested_tree_marks_new_files(self):
        rows = ROWS[:2] + [ROWS[2].replace("src/loan/overdue.ts, tests/overdue.test.ts", "src/loan/fees.ts, tests/fees.test.ts")]
        tree = "repo/\n├── src/\n│   └── loan/\n│       └── fees.ts   U  # 新增\n└── tests/\n    └── fees.test.ts / fees2.test.ts   U  # 新增\n"
        self.write_checklist(rows, extra_tree=tree)
        self.assertEqual(self.issues()[1], [])

    def test_glob_overlap_respects_path_segments(self):
        ce = xdev.checklist
        self.assertFalse(ce.files_overlap("src/*.py", "srcother/x.py"))
        self.assertFalse(ce.files_overlap("src/a.py", "src/ab.py"))
        self.assertTrue(ce.files_overlap("src/*.py", "src/a.py"))
        self.assertTrue(ce.files_overlap("src", "src/a.py"))
        self.assertTrue(ce.files_overlap("src/**/x.py", "src/a/b/x.py"))
        self.assertFalse(ce.files_overlap("lib/**/x.py", "src/a/x.py"))

    def test_tree_without_repo_root_line(self):
        ce = xdev.checklist
        found, stack = set(), []
        for line in ["src/", "└── loan/", "    └── fees.ts   U  # 新增"]:
            ce.parse_tree_line(line, stack, found)
        self.assertIn("src/loan/fees.ts", found)
        found, stack = set(), []
        for line in ["repo/", "├── src/a.ts   U  # 新增"]:
            ce.parse_tree_line(line, stack, found)
        self.assertIn("src/a.ts", found)

    def test_other_spec_placeholder_is_reported(self):
        path = self.task / "dev-checklist.md"
        text = path.read_text(encoding="utf-8").replace("> risk:", "> 其他 spec：<跨多份 spec 时列出；不跨时删掉这一行>\n> risk:")
        path.write_text(text, encoding="utf-8")
        code, rules, payload = self.issues()
        self.assertIn("HEADER", rules)
        self.assertNotIn("BASELINE", rules)

    def test_validate_spec_dir_checks_its_tasks(self):
        code, out, err = run("validate", str(self.spec_dir), "--json")
        result = json.loads(out)["packages"][0]
        self.assertEqual(result["type"], "spec")
        self.assertEqual(result["issues"], [])
        self.assertEqual(code, 0)

    # graph
    def test_graph_orders_groups_by_dependency(self):
        code, out, err = run("graph", str(self.task), "--json")
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertEqual(data["waves"], [["A", "B"], ["C"]])
        self.assertEqual(sorted(map(sorted, data["must_merge"])), [["T1"], ["T2"], ["T3"]])

    # scaffold
    def test_scaffold_fills_header_and_baseline(self):
        new_task = self.spec_dir / "tasks/task-new"
        code, _, err = run("scaffold", str(new_task))
        self.assertEqual(code, 0, err)
        text = (new_task / "dev-checklist.md").read_text(encoding="utf-8")
        self.assertIn("> spec: docs/spec/loan/spec.md", text)
        self.assertIn("docs/spec/loan/spec.md@", text)
        self.assertIn("docs/spec/loan/tech-design.md@", text)

    # impact
    def impact(self):
        code, out, err = run("impact", str(self.task), "--json")
        data = json.loads(out)
        return code, {(a["item"], a["action"]) for a in data["actions"]}

    def test_no_change_means_clean(self):
        self.assertEqual(self.impact(), (0, set()))

    def test_changed_scene(self):
        spec = self.spec_dir / "spec.md"
        spec.write_text(spec.read_text(encoding="utf-8").replace("原应还日期加 14 天", "原应还日期加 21 天"), encoding="utf-8")
        code, acts = self.impact()
        self.assertEqual(code, 1)
        self.assertIn(("T3", "改"), acts)
        self.assertIn(("任务行 T2", "重开"), acts)
        self.assertIn(("tests/renew.test.ts", "改"), acts)
        self.assertIn(("D02", "判断"), acts)
        self.assertNotIn(("任务行 T1", "重开"), acts)
        self.assertNotIn(("T4", "改"), acts)

    def test_added_scene(self):
        spec = self.spec_dir / "spec.md"
        spec.write_text(spec.read_text(encoding="utf-8").replace(
            "## feat03", "场景3: 续借成功提示\n- GIVEN 续借成功\n- WHEN 刷新\n- THEN 显示新日期\n\n## feat03"), encoding="utf-8")
        code, acts = self.impact()
        self.assertIn(("新T（feat02 场景3）", "新增"), acts)
        self.assertIn(("任务行 T2", "重开"), acts)
        self.assertIn(("tests/renew.test.ts", "改"), acts)
        self.assertFalse(any(item.startswith("D") for item, _ in acts))

    def test_removed_scene(self):
        spec = self.spec_dir / "spec.md"
        text = spec.read_text(encoding="utf-8")
        spec.write_text(text[: text.index("## feat03")], encoding="utf-8")
        code, acts = self.impact()
        self.assertIn(("T5", "退役"), acts)
        self.assertIn(("任务行 T3", "重开"), acts)
        self.assertIn(("tests/overdue.test.ts", "改"), acts)
        self.assertNotIn(("D02", "退役"), acts)
        self.assertNotIn(("D02", "判断"), acts)

    def test_changed_d_reopens_all_rows_using_it(self):
        td = self.spec_dir / "tech-design.md"
        td.write_text(td.read_text(encoding="utf-8").replace("D02 应还日期统一计算", "D02 应还日期从续借当天算"), encoding="utf-8")
        code, acts = self.impact()
        self.assertIn(("D02", "改"), acts)
        for row in ("任务行 T1", "任务行 T2", "任务行 T3"):
            self.assertIn((row, "重开"), acts)
        self.assertIn(("tests/borrow.test.ts", "重跑"), acts)

    def test_baseline_clears_impact(self):
        spec = self.spec_dir / "spec.md"
        spec.write_text(spec.read_text(encoding="utf-8").replace("加 14 天", "加 21 天"), encoding="utf-8")
        self.assertEqual(self.impact()[0], 1)
        self.assertEqual(run("baseline", str(self.task))[0], 0)
        self.assertEqual(self.impact(), (0, set()))

    def test_verify_points_current_tasks_elsewhere(self):
        code, _, err = run("verify", str(self.task))
        self.assertEqual(code, 2)
        self.assertIn("x-verify-spec", err)


if __name__ == "__main__":
    unittest.main()
