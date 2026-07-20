#!/usr/bin/env python3
"""req.py（x-req2 task 确定性引擎）的标准库测试：validate 正/反样例、diagram 一致性、spec 级覆盖、scaffold、端到端。"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import req  # noqa: E402
import xdev  # noqa: E402


CHECKLIST_HEADER = (
    "| # | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix |\n"
    "|---|---------|-------------|------|---------|------|------|-----|\n"
)


def capture(fn, *args, **kwargs) -> tuple[object, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = fn(*args, **kwargs)
    return result, stdout.getvalue(), stderr.getvalue()


def capture_main(args: list[str]) -> tuple[int, str, str]:
    return capture(xdev.main, args)


class ReqEngineTestCase(unittest.TestCase):
    """公共 fixture：<tmp>/docs/spec/<spec>/tasks/<task>/，PLUGIN_ROOT 打到 <tmp> 供 spec 指针解析。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        templates_src = ROOT / "skills" / "x-req2" / "templates"
        templates_dst = self.root / "skills" / "x-req2" / "templates"
        templates_dst.mkdir(parents=True)
        for template in templates_src.iterdir():
            (templates_dst / template.name).write_bytes(template.read_bytes())
        patcher = patch.object(req, "PLUGIN_ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def make_spec_raw(self, name: str, acceptance_body: str) -> Path:
        """验收节由调用方完全控制的 spec 包，用于构造非常规分层（无 Requirement、H3 截断等）。"""
        spec_dir = self.root / "docs" / "spec" / name
        spec_dir.mkdir(parents=True)
        (spec_dir / "modules.md").write_text("# modules\n\n## 模块总览\n", encoding="utf-8")
        (spec_dir / "spec.md").write_text(f"# {name}\n\n## 验收\n\n{acceptance_body}\n", encoding="utf-8")
        return spec_dir

    def make_spec(self, name: str, requirements: list[str]) -> Path:
        body = "\n\n".join(
            f"### Requirement: {r}\n\n系统 SHALL {r}。\n\n#### Scenario: {r}生效\n\n"
            f"- **WHEN** 触发{r}\n- **THEN** {r}生效\n- 验证: auto"
            for r in requirements
        )
        return self.make_spec_raw(name, body)

    def make_task(
        self, spec_name: str, task_name: str, rows: list[str], risk: str = "Q1", spec_pointer: str | None = None
    ) -> Path:
        task_dir = self.root / "docs" / "spec" / spec_name / "tasks" / task_name
        task_dir.mkdir(parents=True)
        pointer = spec_pointer if spec_pointer is not None else f"docs/spec/{spec_name}"
        header = f"# {task_name}\n\n> spec: {pointer}\n> risk: {risk}\n\n"
        (task_dir / "dev-checklist.md").write_text(
            header + CHECKLIST_HEADER + "".join(f"{row}\n" for row in rows), encoding="utf-8"
        )
        return task_dir

    def write_checklist(self, spec_name: str, task_name: str, text: str) -> Path:
        task_dir = self.root / "docs" / "spec" / spec_name / "tasks" / task_name
        task_dir.mkdir(parents=True)
        (task_dir / "dev-checklist.md").write_text(text, encoding="utf-8")
        return task_dir


# ---------- 1.3.1 req.py 正样例（核心 validate/status/graph；diagram 变体见 TestDiagramConsistency） ----------

class TestValidatePositive(ReqEngineTestCase):
    def test_valid_single_task_has_zero_issues(self):
        self.make_spec("demo-spec", ["示例功能A"])
        task = self.make_task(
            "demo-spec", "demo-task",
            ["| T1 | 实现示例功能A | 示例功能A | 低：INV1 | product:src/a.py | — | [x] ✅ | — |"],
        )
        self.assertEqual(req.validate_issues(task), [])

    def test_status_and_graph_parse_dependency_chain(self):
        self.make_spec("demo-spec", ["示例功能A"])
        task = self.make_task(
            "demo-spec", "demo-task",
            [
                "| T1 | 实现示例功能A | 示例功能A | 低 | — | — | [x] ✅ | — |",
                "| T2 | 补充测试 | — | — | — | T1 | [ ] ⏳ | — |",
            ],
        )
        status_code, _out, err = capture(req.status, task, as_json=True)
        self.assertEqual(status_code, 0, err)
        graph_code, _out, err = capture(req.graph, task, as_json=True)
        self.assertEqual(graph_code, 0, err)

        tasks, _product_issues = req.resolve_task_list(task)
        by_id = {t["id"]: t for t in tasks}
        self.assertEqual(by_id["T1"]["status"], "done")
        self.assertEqual(by_id["T2"]["status"], "todo")

        result = req.compute_graph(tasks)
        self.assertEqual(result["ready"], ["T2"])
        self.assertEqual(result["blocked"], [])
        self.assertEqual(result["order"], ["T1", "T2"])
        self.assertEqual(result["parallel_batches"], [["T2"]])


# ---------- 1.3.2-1.3.5 req.py 反样例（行级合并 REQ4/5/7/8 / 表头 REQ3 / spec 指针 REQ1 / risk REQ2） ----------

class TestValidateNegative(ReqEngineTestCase):
    def test_missing_spec_pointer_reports_req1(self):
        self.make_spec("demo-spec", ["示例功能A"])
        task = self.write_checklist(
            "demo-spec", "demo-task",
            f"# demo-task\n\n> risk: Q1\n\n{CHECKLIST_HEADER}"
            "| T1 | 任务 | — | — | — | — | [ ] ⏳ | — |\n",
        )
        issues = req.validate_issues(task)
        self.assertEqual([i["rule"] for i in issues], ["REQ1"])
        self.assertIn("缺少 spec:", issues[0]["msg"])

    def test_invalid_spec_pointer_reports_req1_without_cascading_to_req5(self):
        task = self.make_task(
            "demo-spec", "demo-task",
            ["| T1 | 任务 | 不存在的需求 | 低 | — | — | [ ] ⏳ | — |"],
            spec_pointer="docs/spec/no-such-spec",
        )
        issues = req.validate_issues(task)
        self.assertEqual([i["rule"] for i in issues], ["REQ1"])
        # 归属改为按 task 实际位置推定后，文案由「指针未指向」变为「task 上级不是」；
        # 断言取两者共有的稳定子串，避免微调文案就误红。
        self.assertIn("合法 spec 包", issues[0]["msg"])

    def test_missing_or_invalid_risk_reports_req2(self):
        self.make_spec("demo-spec", ["示例功能A"])
        missing = self.write_checklist(
            "demo-spec", "task-missing-risk",
            f"# task-missing-risk\n\n> spec: docs/spec/demo-spec\n\n{CHECKLIST_HEADER}"
            "| T1 | 任务 | — | — | — | — | [ ] ⏳ | — |\n",
        )
        issues = req.validate_issues(missing)
        req2 = [i for i in issues if i["rule"] == "REQ2"]
        self.assertEqual(len(req2), 1)
        self.assertIn("缺少 risk:", req2[0]["msg"])

        invalid = self.make_task(
            "demo-spec", "task-invalid-risk",
            ["| T1 | 任务 | — | — | — | — | [ ] ⏳ | — |"],
            risk="trivial",
        )
        issues = req.validate_issues(invalid)
        req2 = [i for i in issues if i["rule"] == "REQ2"]
        self.assertEqual(len(req2), 1)
        self.assertIn("risk: 取值非法", req2[0]["msg"])

    def test_dangling_requirement_reports_req5(self):
        self.make_spec("demo-spec", ["示例功能A"])
        task = self.make_task(
            "demo-spec", "demo-task",
            ["| T1 | 任务 | 不存在的需求X | 低 | — | — | [ ] ⏳ | — |"],
        )
        issues = req.validate_issues(task)
        self.assertEqual([i["rule"] for i in issues], ["REQ5"])
        self.assertIn("Requirement 悬空", issues[0]["msg"])

    def test_duplicate_requirement_name_reports_req5(self):
        self.make_spec("demo-spec", ["重复功能", "重复功能"])
        task = self.make_task(
            "demo-spec", "demo-task",
            ["| T1 | 任务 | 重复功能 | 低 | — | — | [ ] ⏳ | — |"],
        )
        issues = req.validate_issues(task)
        self.assertEqual([i["rule"] for i in issues], ["REQ5"])
        self.assertIn("Requirement 重名", issues[0]["msg"])

    def test_empty_title_and_risk_cells_report_req4(self):
        self.make_spec("demo-spec", ["示例功能A"])
        task = self.make_task(
            "demo-spec", "demo-task",
            ["| T1 |  | — |  | — | — | [ ] ⏳ | — |"],
        )
        issues = req.validate_issues(task)
        self.assertEqual(len(issues), 2)
        self.assertEqual({i["rule"] for i in issues}, {"REQ4"})
        messages = " ".join(i["msg"] for i in issues)
        self.assertIn("任务说明为空", messages)
        self.assertIn("风险列为空", messages)

    def test_illegal_status_reports_req7(self):
        self.make_spec("demo-spec", ["示例功能A"])
        task = self.make_task(
            "demo-spec", "demo-task",
            ["| T1 | 任务 | 示例功能A | 低 | — | — | waiting | — |"],
        )
        issues = req.validate_issues(task)
        self.assertEqual([i["rule"] for i in issues], ["REQ7"])
        self.assertIn("状态非法", issues[0]["msg"])
        self.assertIn("waiting", issues[0]["msg"])

    def test_dangling_dependency_reports_req8(self):
        self.make_spec("demo-spec", ["示例功能A"])
        task = self.make_task(
            "demo-spec", "demo-task",
            ["| T1 | 任务 | 示例功能A | 低 | — | T9 | [ ] ⏳ | — |"],
        )
        issues = req.validate_issues(task)
        self.assertEqual([i["rule"] for i in issues], ["REQ8"])
        self.assertIn("T9", issues[0]["msg"])
        self.assertIn("不在 task 表中", issues[0]["msg"])

    def test_six_row_level_defects_in_one_task_report_six_distinct_issues(self):
        """1.3.2：6 种行级坏样例塞进同一 checklist 的不同行，互不遮蔽，一次 validate 报齐 6 条。"""
        self.make_spec("demo-spec", ["功能A", "重复功能", "重复功能"])
        task = self.make_task(
            "demo-spec", "demo-task",
            [
                "| T1 | 任务一 | 不存在的需求 | 低 | — | — | [ ] ⏳ | — |",
                "| T2 | 任务二 | 重复功能 | 低 | — | — | [ ] ⏳ | — |",
                "| T3 | 任务三 | 功能A |  | — | — | [ ] ⏳ | — |",
                "| T4 |  | 功能A | 低 | — | — | [ ] ⏳ | — |",
                "| T5 | 任务五 | 功能A | 低 | — | T9 | [ ] ⏳ | — |",
                "| T6 | 任务六 | 功能A | 低 | — | — | waiting | — |",
            ],
        )
        issues = req.validate_issues(task)
        self.assertEqual(
            [i["rule"] for i in issues], ["REQ5", "REQ5", "REQ4", "REQ4", "REQ8", "REQ7"]
        )
        self.assertIn("T1", issues[0]["msg"])
        self.assertIn("悬空", issues[0]["msg"])
        self.assertIn("T2", issues[1]["msg"])
        self.assertIn("重名", issues[1]["msg"])
        self.assertIn("T3", issues[2]["msg"])
        self.assertIn("风险列为空", issues[2]["msg"])
        self.assertIn("T4", issues[3]["msg"])
        self.assertIn("任务说明为空", issues[3]["msg"])
        self.assertIn("T5", issues[4]["msg"])
        self.assertIn("T9", issues[4]["msg"])
        self.assertIn("T6", issues[5]["msg"])
        self.assertIn("waiting", issues[5]["msg"])

    def test_broken_header_missing_id_and_status_columns_reports_req3(self):
        self.make_spec("demo-spec", ["示例功能A"])
        task = self.write_checklist(
            "demo-spec", "demo-task",
            "# demo-task\n\n> spec: docs/spec/demo-spec\n> risk: Q1\n\n"
            "| 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | fix |\n"
            "|---------|-------------|------|---------|------|-----|\n"
            "| 任务 | 示例功能A | 低 | — | — | — |\n",
        )
        issues = req.validate_issues(task)
        self.assertEqual([i["rule"] for i in issues], ["REQ3"])


# ---------- 1.3.1 变体 + delta spec「对照 modules.md 报差异」：diagram.md ↔ modules.md 一致性（REQ9） ----------

class TestDiagramConsistency(ReqEngineTestCase):
    def _write_modules(self, spec_dir: Path, modules: list[str]) -> None:
        rows = "\n".join(f"| {m} | 职责 | 无 | — | 低 | — | 方案确认 | — |" for m in modules)
        (spec_dir / "modules.md").write_text(
            "# modules\n\n## 模块总览\n\n"
            "| 模块 | 职责 | 依赖 | 边界类/对外契约 | 风险 | 决策回指 | 状态 | 回指 Requirement |\n"
            "|---|---|---|---|---|---|---|---|\n"
            f"{rows}\n",
            encoding="utf-8",
        )

    def test_matching_diagram_reports_zero_req9_issues(self):
        spec_dir = self.make_spec("demo-spec", ["示例功能A"])
        self._write_modules(spec_dir, ["Artifact Engine"])
        task = self.make_task(
            "demo-spec", "demo-task",
            ["| T1 | 实现 | 示例功能A | 低 | — | — | [x] ✅ | — |"],
        )
        (task / "diagram.md").write_text(
            '```mermaid\nflowchart TD\nEngine["Artifact Engine"]\n```\n', encoding="utf-8",
        )
        issues = req.validate_issues(task)
        self.assertEqual([i for i in issues if i["rule"] == "REQ9"], [])

    def test_missing_diagram_skips_req9(self):
        spec_dir = self.make_spec("demo-spec", ["示例功能A"])
        self._write_modules(spec_dir, ["Artifact Engine", "Unrendered Module"])
        task = self.make_task(
            "demo-spec", "demo-task",
            ["| T1 | 实现 | 示例功能A | 低 | — | — | [x] ✅ | — |"],
        )
        issues = req.validate_issues(task)
        self.assertEqual([i for i in issues if i["rule"] == "REQ9"], [])

    def test_diagram_module_mismatch_reports_req9_both_directions(self):
        spec_dir = self.make_spec("demo-spec", ["示例功能A"])
        self._write_modules(spec_dir, ["Artifact Engine", "Missing Module"])
        task = self.make_task(
            "demo-spec", "demo-task",
            ["| T1 | 实现 | 示例功能A | 低 | — | — | [x] ✅ | — |"],
        )
        (task / "diagram.md").write_text(
            '```mermaid\nflowchart TD\nEngine["Artifact Engine"]\nExtra["Extra Module"]\n```\n',
            encoding="utf-8",
        )
        messages = "\n".join(i["msg"] for i in req.validate_issues(task) if i["rule"] == "REQ9")
        self.assertIn("Missing Module", messages)
        self.assertIn("Extra Module", messages)


# ---------- 1.3.6 坏 E · spec 级覆盖缺口 ----------

class TestSpecCoverage(ReqEngineTestCase):
    def test_uncovered_requirement_across_multi_task_spec_reports_req6(self):
        spec_dir = self.make_spec("demo-spec", ["功能A", "功能B"])
        self.make_task("demo-spec", "task-1", ["| T1 | 做功能A | 功能A | 低 | — | — | [x] ✅ | — |"])
        issues = req.spec_requirement_coverage(spec_dir)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["rule"], "REQ6")
        self.assertIn("功能B", issues[0]["msg"])

    def test_coverage_merges_across_multiple_tasks_in_same_spec(self):
        spec_dir = self.make_spec("demo-spec", ["功能A", "功能B"])
        self.make_task("demo-spec", "task-1", ["| T1 | 做功能A | 功能A | 低 | — | — | [x] ✅ | — |"])
        self.make_task("demo-spec", "task-2", ["| T1 | 做功能B | 功能B | 低 | — | — | [x] ✅ | — |"])
        self.assertEqual(req.spec_requirement_coverage(spec_dir), [])

    def test_single_task_validate_does_not_flag_missing_coverage(self):
        self.make_spec("demo-spec", ["功能A", "功能B"])
        task = self.make_task("demo-spec", "task-1", ["| T1 | 做功能A | 功能A | 低 | — | — | [x] ✅ | — |"])
        self.assertEqual(req.validate_issues(task), [])

    def test_xdev_validate_on_spec_package_surfaces_req6(self):
        spec_dir = self.make_spec("demo-spec", ["功能A", "功能B"])
        self.make_task("demo-spec", "task-1", ["| T1 | 做功能A | 功能A | 低 | — | — | [x] ✅ | — |"])
        result = xdev.validate_pkg(spec_dir, include_legacy=False)
        self.assertEqual(result["type"], "spec2")
        self.assertIn("REQ6", {i["rule"] for i in result["issues"]})


# ---------- scaffold（req.py 唯一实现，覆盖此前散落在旧结构 test_xdev_artifacts.py 的场景） ----------

class TestScaffold(ReqEngineTestCase):
    def test_default_scaffold_creates_checklist_only_with_title(self):
        task_dir = self.root / "docs" / "spec" / "demo-spec" / "tasks" / "demo-task"
        code, stdout, stderr = capture_main(["scaffold", str(task_dir), "--json"])
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["created"], [str(task_dir / "dev-checklist.md")])
        self.assertFalse((task_dir / "README.md").exists())
        self.assertFalse((task_dir / "diagram.md").exists())
        self.assertTrue(
            (task_dir / "dev-checklist.md").read_text(encoding="utf-8").startswith("# demo-task")
        )

    def test_with_diagram_creates_optional_artifact(self):
        task_dir = self.root / "docs" / "spec" / "demo-spec" / "tasks" / "demo-task"
        code, _stdout, stderr = capture_main(["scaffold", str(task_dir), "--with-diagram"])
        self.assertEqual(code, 0, stderr)
        self.assertTrue((task_dir / "diagram.md").exists())

    def test_scaffold_keeps_existing_bytes_and_reports_lists(self):
        task_dir = self.root / "docs" / "spec" / "demo-spec" / "tasks" / "demo-task"
        task_dir.mkdir(parents=True)
        checklist = task_dir / "dev-checklist.md"
        checklist.write_bytes(b"user-owned\n\xff")
        code, stdout, stderr = capture_main(["scaffold", str(task_dir), "--with-diagram", "--json"])
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(checklist.read_bytes(), b"user-owned\n\xff")
        self.assertIn(str(checklist), payload["skipped"])
        self.assertIn(str(task_dir / "diagram.md"), payload["created"])

    def test_scaffold_rejects_paths_outside_req2_shape(self):
        task_dir = self.root / "dev-pipeline" / "tasks" / "old-shape"
        code, _stdout, stderr = capture_main(["scaffold", str(task_dir), "--json"])
        self.assertEqual(code, 2)
        self.assertIn("不支持旧结构", stderr)


# ---------- 1.3.7 坏 F · verify 无证据回指 ----------

class TestVerifyEvidence(ReqEngineTestCase):
    """verify 的验收对账：范围 = 本 task checklist 承接的 Requirement 下的 auto Scenario。"""

    def write_report(self, task: Path, scenarios: list[str]) -> None:
        blocks = "\n".join(
            "```verify\n"
            f"id: v{index}\n"
            f"scenario: {scenario}\n"
            "cmd: python3 -c \"print('ok')\"\n"
            "expect_contains: ok\n"
            "mode: auto\n"
            "```\n"
            for index, scenario in enumerate(scenarios, start=1)
        )
        (task / "dev-report.md").write_text(f"# {task.name} dev-report\n\n{blocks}", encoding="utf-8")

    def verify_json(self, task: Path) -> tuple[int, dict]:
        code, stdout, stderr = capture_main(["verify", str(task), "--json"])
        return code, json.loads(stdout) if stdout else {"stderr": stderr}

    def test_other_tasks_requirements_stay_out_of_scope(self):
        """一个 spec 拆成多个 task 时，别的 task 承接的 Scenario 不算本 task 的缺口。"""
        self.make_spec("demo-spec", ["功能A", "功能B"])
        task_a = self.make_task(
            "demo-spec", "task-a", ["| T1 | 做功能A | 功能A | 低 | — | — | [x] ✅ | — |"],
        )
        task_b = self.make_task(
            "demo-spec", "task-b", ["| T1 | 做功能B | 功能B | 低 | — | — | [x] ✅ | — |"],
        )
        self.write_report(task_a, ["功能A生效"])
        self.write_report(task_b, ["功能B生效"])

        code_a, payload_a = self.verify_json(task_a)
        self.assertEqual(code_a, 0, payload_a)
        self.assertEqual(payload_a["requirements"], ["功能A"])
        self.assertEqual(payload_a["expected_auto"], ["功能A生效"])
        self.assertEqual(payload_a["uncovered"], [])

        code_b, payload_b = self.verify_json(task_b)
        self.assertEqual(code_b, 0, payload_b)
        self.assertEqual(payload_b["expected_auto"], ["功能B生效"])
        self.assertEqual(payload_b["uncovered"], [])

    def test_missing_verify_block_inside_scope_reports_uncovered_and_exit1(self):
        """范围内的缺口照旧被抓：承接两个 Requirement 却只给一份证据。"""
        self.make_spec("demo-spec", ["功能A", "功能B"])
        task = self.make_task(
            "demo-spec", "demo-task",
            [
                "| T1 | 做功能A | 功能A | 低 | — | — | [x] ✅ | — |",
                "| T2 | 做功能B | 功能B | 低 | — | T1 | [x] ✅ | — |",
            ],
        )
        self.write_report(task, ["功能A生效"])
        code, payload = self.verify_json(task)
        self.assertEqual(code, 1, payload)
        self.assertEqual(payload["expected_auto"], ["功能A生效", "功能B生效"])
        self.assertEqual(payload["uncovered"], ["功能B生效"])

    def test_full_verify_block_coverage_keeps_scenario_out_of_uncovered(self):
        self.make_spec("demo-spec", ["功能A", "功能B"])
        task = self.make_task(
            "demo-spec", "demo-task",
            [
                "| T1 | 做功能A | 功能A | 低 | — | — | [x] ✅ | — |",
                "| T2 | 做功能B | 功能B | 低 | — | T1 | [x] ✅ | — |",
            ],
        )
        self.write_report(task, ["功能A生效", "功能B生效"])
        code, payload = self.verify_json(task)
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["uncovered"], [])

    def test_task_without_requirement_binding_only_runs_commands(self):
        """纯技术 task（Requirement 全 `—`）范围为空，只复跑命令，不承担验收覆盖。"""
        self.make_spec("demo-spec", ["功能A"])
        task = self.make_task(
            "demo-spec", "chore-task",
            ["| T1 | 重构内部工具 | — | 低 | — | — | [x] ✅ | — |"],
        )
        self.write_report(task, ["功能A生效"])
        code, payload = self.verify_json(task)
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["requirements"], [])
        self.assertEqual(payload["expected_auto"], [])
        self.assertEqual(payload["uncovered"], [])

    def test_scenario_keeps_parent_requirement(self):
        spec_dir = self.make_spec("demo-spec", ["功能A", "功能B"])
        self.assertEqual(
            req.acceptance_scenarios(spec_dir / "spec.md"),
            [
                {"requirement": "功能A", "name": "功能A生效", "mode": "auto"},
                {"requirement": "功能B", "name": "功能B生效", "mode": "auto"},
            ],
        )

    def test_scenario_without_parent_requirement_exits_2(self):
        """验收节整节无 Requirement 分层：场景不属于任何 task，verify 拒绝给结论而非算空范围放行。"""
        self.make_spec_raw("demo-spec", "#### Scenario: 孤儿场景\n\n- **THEN** ok\n- 验证: auto")
        task = self.make_task(
            "demo-spec", "demo-task", ["| T1 | 做事 | — | 低 | — | — | [x] ✅ | — |"],
        )
        self.write_report(task, ["孤儿场景"])
        code, payload = self.verify_json(task)
        self.assertEqual(code, 2, payload)
        self.assertIn("孤儿场景", payload["stderr"])

    def test_non_requirement_h3_truncates_scope_and_exits_2(self):
        """非 Requirement 的 H3 结束作用域，其后的场景掉队成无父级 → 同样拦截，只点名掉队的那条。"""
        self.make_spec_raw(
            "demo-spec",
            "### Requirement: 功能A\n\n系统 SHALL A。\n\n#### Scenario: 功能A生效\n\n- 验证: auto\n\n"
            "### 补充说明\n\n与验收无关的一段\n\n#### Scenario: 掉队场景\n\n- 验证: auto",
        )
        task = self.make_task(
            "demo-spec", "demo-task", ["| T1 | 做A | 功能A | 低 | — | — | [x] ✅ | — |"],
        )
        self.write_report(task, ["功能A生效"])
        code, payload = self.verify_json(task)
        self.assertEqual(code, 2, payload)
        self.assertIn("掉队场景", payload["stderr"])
        self.assertNotIn("功能A生效", payload["stderr"])

    def test_unparented_manual_scenario_does_not_block(self):
        """manual 场景不参与 auto 对账，缺父 Requirement 不构成拦截理由。"""
        self.make_spec_raw(
            "demo-spec",
            "### Requirement: 功能A\n\n系统 SHALL A。\n\n#### Scenario: 功能A生效\n\n- 验证: auto\n\n"
            "### 附录\n\n#### Scenario: 人工巡检\n\n- 验证: manual",
        )
        task = self.make_task(
            "demo-spec", "demo-task", ["| T1 | 做A | 功能A | 低 | — | — | [x] ✅ | — |"],
        )
        self.write_report(task, ["功能A生效"])
        code, payload = self.verify_json(task)
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["expected_auto"], ["功能A生效"])

    def test_fullwidth_colon_marker_is_recognized(self):
        """`验证：auto`（全角冒号）与半角等价：中文输入法高频误击，识别失败的代价曾是场景免检。"""
        self.make_spec_raw(
            "demo-spec",
            "### Requirement: 功能A\n\n系统 SHALL A。\n\n#### Scenario: 功能A生效\n\n- 验证：auto",
        )
        task = self.make_task(
            "demo-spec", "demo-task", ["| T1 | 做A | 功能A | 低 | — | — | [x] ✅ | — |"],
        )
        self.write_report(task, [])
        code, payload = self.verify_json(task)
        self.assertEqual(code, 1, payload)
        self.assertEqual(payload["uncovered"], ["功能A生效"])

    def test_scenario_without_validation_marker_exits_2(self):
        """漏标记的场景既不进 expected_auto 也不进 manual，等于自动免检 → 拒绝给结论。"""
        self.make_spec_raw(
            "demo-spec",
            "### Requirement: 功能A\n\n系统 SHALL A。\n\n#### Scenario: 功能A生效\n\n- **THEN** 有结果",
        )
        task = self.make_task(
            "demo-spec", "demo-task", ["| T1 | 做A | 功能A | 低 | — | — | [x] ✅ | — |"],
        )
        self.write_report(task, ["功能A生效"])
        code, payload = self.verify_json(task)
        self.assertEqual(code, 2, payload)
        self.assertIn("功能A生效", payload["stderr"])
        self.assertIn("验证", payload["stderr"])

    def test_unmarked_scenario_outside_scope_does_not_block_task(self):
        """漏标记的场景能归属，故按 task-scoped 只拦承接它的 task；兄弟 task 不受牵连。"""
        self.make_spec_raw(
            "demo-spec",
            "### Requirement: 功能A\n\n系统 SHALL A。\n\n#### Scenario: 功能A生效\n\n- 验证: auto\n\n"
            "### Requirement: 功能B\n\n系统 SHALL B。\n\n#### Scenario: 功能B生效\n\n- **THEN** 漏标记",
        )
        task_a = self.make_task(
            "demo-spec", "task-a", ["| T1 | 做A | 功能A | 低 | — | — | [x] ✅ | — |"],
        )
        self.write_report(task_a, ["功能A生效"])
        code_a, payload_a = self.verify_json(task_a)
        self.assertEqual(code_a, 0, payload_a)

        task_b = self.make_task(
            "demo-spec", "task-b", ["| T1 | 做B | 功能B | 低 | — | — | [x] ✅ | — |"],
        )
        self.write_report(task_b, ["功能B生效"])
        code_b, payload_b = self.verify_json(task_b)
        self.assertEqual(code_b, 2, payload_b)
        self.assertIn("功能B生效", payload_b["stderr"])

    def test_scenario_missing_both_parent_and_marker_is_reported(self):
        """既无父 Requirement 又无标记：不落在任何 scope 内，仍须报出而不是两头落空。"""
        self.make_spec_raw("demo-spec", "#### Scenario: 双缺场景\n\n- **THEN** 有结果")
        task = self.make_task(
            "demo-spec", "demo-task", ["| T1 | 做事 | — | 低 | — | — | [x] ✅ | — |"],
        )
        self.write_report(task, [])
        code, payload = self.verify_json(task)
        self.assertEqual(code, 2, payload)
        self.assertIn("双缺场景", payload["stderr"])

    def test_duplicate_scenario_name_in_scope_counts_once(self):
        """同一 task 承接的两个 Requirement 下有同名场景时，expected_auto 不出现重复条目。"""
        self.make_spec_raw(
            "demo-spec",
            "### Requirement: 功能A\n\n系统 SHALL A。\n\n#### Scenario: 同名场景\n\n- 验证: auto\n\n"
            "### Requirement: 功能B\n\n系统 SHALL B。\n\n#### Scenario: 同名场景\n\n- 验证: auto",
        )
        task = self.make_task(
            "demo-spec", "demo-task",
            [
                "| T1 | 做A | 功能A | 低 | — | — | [x] ✅ | — |",
                "| T2 | 做B | 功能B | 低 | — | T1 | [x] ✅ | — |",
            ],
        )
        self.write_report(task, ["同名场景"])
        code, payload = self.verify_json(task)
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["expected_auto"], ["同名场景"])

    def test_ascii_dash_requirement_is_treated_as_no_binding(self):
        """`-` 与 `—` 同为无绑定占位：不能被当成真实 Requirement 名让范围假装非空。"""
        self.make_spec("demo-spec", ["功能A"])
        task = self.make_task(
            "demo-spec", "chore-task", ["| T1 | 内部重构 | - | 低 | — | — | [x] ✅ | — |"],
        )
        self.write_report(task, ["功能A生效"])
        code, payload = self.verify_json(task)
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["requirements"], [])
        self.assertEqual(payload["expected_auto"], [])

    def test_missing_checklist_exits_2_pointing_at_checklist(self):
        """verify 新增的 checklist 依赖失败时，错误须指向 checklist 而非 dev-report。"""
        self.make_spec("demo-spec", ["功能A"])
        task = self.make_task(
            "demo-spec", "demo-task", ["| T1 | 做A | 功能A | 低 | — | — | [x] ✅ | — |"],
        )
        self.write_report(task, ["功能A生效"])
        (task / "dev-checklist.md").unlink()
        code, payload = self.verify_json(task)
        self.assertEqual(code, 2, payload)
        self.assertIn("dev-checklist.md", payload["stderr"])

    def test_checklist_missing_key_column_exits_2(self):
        self.make_spec("demo-spec", ["功能A"])
        task = self.write_checklist(
            "demo-spec", "demo-task",
            "# demo-task\n\n> spec: docs/spec/demo-spec\n> risk: Q1\n\n"
            "| 任务说明 | Requirement |\n|---------|-------------|\n| 做A | 功能A |\n",
        )
        self.write_report(task, ["功能A生效"])
        code, payload = self.verify_json(task)
        self.assertEqual(code, 2, payload)
        self.assertIn("关键列", payload["stderr"])


# ---------- 1.3.8 端到端：scaffold → 填写 → validate → status/graph → dev-report → verify ----------

class TestEndToEnd(ReqEngineTestCase):
    def test_scaffold_fill_validate_verify_round_trip(self):
        self.make_spec("demo-spec", ["示例功能A"])
        task_dir = self.root / "docs" / "spec" / "demo-spec" / "tasks" / "demo-task"

        code, stdout, stderr = capture_main(["scaffold", str(task_dir), "--json"])
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["created"], [str(task_dir / "dev-checklist.md")])

        text = (task_dir / "dev-checklist.md").read_text(encoding="utf-8")
        text = text.replace("> risk: <Q0|Q1|Q2|Q3>", "> risk: Q1")
        start = text.index("| T1 |")
        end = text.index("\n\n## 并行机会")
        filled_row = "| T1 | 实现示例功能A | 示例功能A | 低 | — | — | [x] ✅ | — |"
        text = text[:start] + filled_row + text[end:]
        (task_dir / "dev-checklist.md").write_text(text, encoding="utf-8")

        code, stdout, stderr = capture_main(["validate", str(task_dir), "--json"])
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["total_issues"], 0)
        self.assertEqual(payload["packages"][0]["type"], "req2-task")

        code, stdout, stderr = capture_main(["status", str(task_dir), "--json"])
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["progress"]["done"], 1)

        code, stdout, stderr = capture_main(["graph", str(task_dir), "--json"])
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["ready"], [])

        (task_dir / "dev-report.md").write_text(
            "# demo-task dev-report\n\n"
            "```verify\n"
            "id: v1\n"
            "scenario: 示例功能A生效\n"
            "cmd: python3 -c \"print('round-trip-ok')\"\n"
            "expect_contains: round-trip-ok\n"
            "mode: auto\n"
            "```\n",
            encoding="utf-8",
        )
        code, stdout, stderr = capture_main(["verify", str(task_dir), "--json"])
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual([item["id"] for item in payload["pass"]], ["v1"])
        self.assertEqual(payload["fail"], [])
        self.assertEqual(payload["uncovered"], [])


# ---------- 解析前置分支：REQ0（无清单文件）与 REQ3（正文无表格） ----------

class TestParseFallbacks(ReqEngineTestCase):
    def test_missing_checklist_file_reports_req0(self):
        """task 目录存在但没有 dev-checklist.md → REQ0。"""
        self.make_spec("demo-spec", ["示例功能A"])
        task_dir = self.root / "docs" / "spec" / "demo-spec" / "tasks" / "empty-task"
        task_dir.mkdir(parents=True)
        issues = req.validate_issues(task_dir)
        self.assertEqual([i["rule"] for i in issues], ["REQ0"])

    def test_checklist_without_any_table_reports_req3(self):
        """有 checklist 但正文没有任何表格 → REQ3（解析失败的另一条分支）。"""
        self.make_spec("demo-spec", ["示例功能A"])
        task = self.write_checklist(
            "demo-spec", "no-table",
            "# no-table\n\n> spec: docs/spec/demo-spec\n> risk: Q1\n\n正文没有任何表格。\n",
        )
        issues = req.validate_issues(task)
        self.assertEqual([i["rule"] for i in issues], ["REQ3"])


# ---------- 固化夹具：读 test/fixtures/req2/ 下的真实文件，不 patch、不造临时数据 ----------

FIXTURE_ROOT = ROOT / "test" / "fixtures" / "req2"
FIXTURE_SPECS = FIXTURE_ROOT / "docs" / "spec"


def fixture_task(spec_name: str, task_name: str) -> Path:
    return FIXTURE_SPECS / spec_name / "tasks" / task_name


class TestFixtureValidate(unittest.TestCase):
    """跑 `test/fixtures/req2/` 下的固化夹具——夹具清单与各自预期见该目录 README。

    不 patch PLUGIN_ROOT、不复制模板、不造临时数据。夹具位置刻意不在插件根的
    `docs/spec/` 下，因此这组用例同时锁死「归属 spec 包按 task 实际位置推定」这条契约：
    谁改回「拿插件根去拼 `spec:` 指针」，整组立刻红。
    """

    def rules(self, issues: list[dict]) -> list[str]:
        return sorted(item["rule"] for item in issues)

    # ---- 正样例：验「不误报」----

    def test_ok_task_has_zero_issues(self):
        self.assertEqual(req.validate_issues(fixture_task("demo", "ok-task")), [])

    def test_ok_spec_coverage_is_closed(self):
        self.assertEqual(req.spec_requirement_coverage(FIXTURE_SPECS / "demo"), [])

    def test_spec_dir_resolved_from_task_location(self):
        self.assertEqual(
            req.resolve_spec_dir(fixture_task("demo", "ok-task")),
            (FIXTURE_SPECS / "demo").resolve(),
        )

    def test_project_root_derived_from_task_location(self):
        self.assertEqual(
            req.project_root_of_task_dir(fixture_task("demo", "ok-task")),
            FIXTURE_ROOT.resolve(),
        )

    # ---- 坏 A：六种行级错互不遮蔽，一次全报 ----

    def test_bad_rows_reports_all_six_row_defects(self):
        issues = req.validate_issues(fixture_task("bad-rows", "bad-rows"))
        self.assertEqual(self.rules(issues), ["REQ4", "REQ4", "REQ5", "REQ5", "REQ7", "REQ8"])
        messages = " ".join(item["msg"] for item in issues)
        for expected in ("悬空", "重名", "任务说明为空", "风险列为空", "依赖", "状态非法"):
            self.assertIn(expected, messages)

    # ---- 坏 B：表头错会遮蔽行级检查，故只应报解析失败 ----

    def test_bad_header_reports_parse_issue_only(self):
        issues = req.validate_issues(fixture_task("bad-header", "bad-header"))
        self.assertEqual(self.rules(issues), ["REQ3"])

    # ---- 坏 C：归属失效降级为一条，不级联逐行回指 ----

    def test_broken_pkg_reports_single_issue_without_cascade(self):
        issues = req.validate_issues(fixture_task("broken-pkg", "orphan"))
        self.assertEqual(self.rules(issues), ["REQ1"])
        self.assertEqual(len(issues), 1, msg=f"两行悬空需求不得级联报出：{issues}")

    # ---- 坏 D：risk 非法 ----

    def test_bad_risk_reports_req2_only(self):
        issues = req.validate_issues(fixture_task("bad-risk", "bad-risk"))
        self.assertEqual(self.rules(issues), ["REQ2"])
        self.assertIn("Q9", issues[0]["msg"])

    # ---- 指针与实际归属不符（指针改作核对项后的新规则）----

    def test_pointer_mismatch_reports_req1(self):
        issues = req.validate_issues(fixture_task("pointer-mismatch", "mismatch"))
        self.assertEqual(self.rules(issues), ["REQ1"])
        self.assertIn("不符", issues[0]["msg"])

    # ---- 坏 E：覆盖缺口在 spec 级判定，单 task 不误报 ----

    def test_uncovered_spec_reports_req6(self):
        issues = req.spec_requirement_coverage(FIXTURE_SPECS / "uncovered")
        self.assertEqual(self.rules(issues), ["REQ6"])
        self.assertIn("无人认领的功能Z", issues[0]["msg"])

    def test_uncovered_single_task_is_not_flagged(self):
        self.assertEqual(req.validate_issues(fixture_task("uncovered", "partial")), [])

    # ---- diagram 与 modules.md 双向一致性 ----

    def test_bad_diagram_reports_both_directions(self):
        issues = req.validate_issues(fixture_task("bad-diagram", "bad-diagram"))
        self.assertEqual(self.rules(issues), ["REQ9", "REQ9"])
        messages = " ".join(item["msg"] for item in issues)
        self.assertIn("缺少 Mermaid 节点", messages)
        self.assertIn("未在 modules.md 模块总览声明", messages)

    # ---- 坏 F：auto 场景缺证据回指 ----

    def test_verify_gap_marks_scenario_uncovered_and_exits_1(self):
        code, stdout, stderr = capture(
            req.verify, fixture_task("verify-gap", "verify-gap"), True, None
        )
        self.assertEqual(code, 1, msg=stderr)
        payload = json.loads(stdout)
        self.assertIn(
            "功能V生效", json.dumps(payload.get("uncovered", []), ensure_ascii=False)
        )


if __name__ == "__main__":
    unittest.main()
