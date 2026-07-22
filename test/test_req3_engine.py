#!/usr/bin/env python3
"""x-req3 单文件 spec3 → task → verify 契约测试。"""

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

import req3  # noqa: E402
import verify as verify_engine  # noqa: E402
import xdev  # noqa: E402


CHECKLIST_HEADER = (
    "| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |\n"
    "|---|---|---|---|---|---|---|---|\n"
)


def capture(fn, *args, **kwargs):
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = fn(*args, **kwargs)
    return code, stdout.getvalue(), stderr.getvalue()


class Req3EngineTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        patcher = patch.object(req3, "PLUGIN_ROOT", ROOT)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_spec(self, name: str = "demo") -> Path:
        spec_dir = self.root / "docs" / "spec" / name
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec.md").write_text(
            "> spec_version: 3\n\n"
            f"# {name}\n\n"
            "## 任务目标\n\n- 返回可验证结果。\n\n"
            "## 非目标\n\n- 不访问网络。\n\n"
            "## 影响边界与不变量\n\n"
            "| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |\n"
            "|---|---|---|---|---|---|\n"
            "| Resolver | 目标 | 新增解析 | 输入被原地修改导致调用方状态污染 | 输入保持只读 | J1 |\n"
            "| Caller | 上游 | 调用公开 API | 签名漂移导致编译失败 | 错误可判定 | J1 |\n\n"
            "## 判断依据\n\n"
            "| J-ID | 判断 | 来源 | 证据或推断 | 状态 |\n"
            "|---|---|---|---|---|\n"
            "| J1 | 保持输入只读 | 用户任务 | 明确要求 | 已确认 |\n\n"
            "## 建模覆盖声明\n\n"
            "| 维度 | 覆盖位置或具体不适用理由 |\n"
            "|---|---|\n"
            "| 数据流 | Scenario 标量覆盖 |\n"
            "| 状态 | 无跨调用状态 |\n"
            "| 时序 | Scenario 真实链路 |\n"
            "| 资源 | 无外部资源 |\n"
            "| 不变量 | 影响边界与不变量 |\n"
            "| 故障 | Scenario 真实链路 |\n\n"
            "## 验收清单\n\n"
            "### 单元测试\n\n- [ ] 标量覆盖。\n\n"
            "### Smoke 测试\n\n- [ ] 公开入口。\n\n"
            "### E2E 测试\n\n- 决策：需要\n- 依据：真实调用链。\n\n"
            "## 测试驱动开发\n\n1. 先写失败测试。\n\n"
            "## Scenarios\n\n"
            "### Scenario SC_01: 标量覆盖\n\n"
            "- **GIVEN** 一个低优先级值\n"
            "- **WHEN** 解析配置\n"
            "- **THEN** 返回高优先级值\n"
            "- 测试层：unit\n"
            "- 依据：J1\n\n"
            "### Scenario SC_02: 真实链路\n\n"
            "- **GIVEN** 一个公开调用方\n"
            "- **WHEN** 调用公开 API\n"
            "- **THEN** 得到稳定结果\n"
            "- 测试层：e2e\n"
            "- 依据：J1\n",
            encoding="utf-8",
        )
        return spec_dir

    def make_task(self, spec_name: str = "demo", task_name: str = "resolver") -> Path:
        task_dir = self.root / "docs" / "spec" / spec_name / "tasks" / task_name
        task_dir.mkdir(parents=True)
        (task_dir / "dev-checklist.md").write_text(
            f"# {task_name}\n\n> spec: docs/spec/{spec_name}\n> risk: Q2\n\n"
            + CHECKLIST_HEADER
            + "| T1 | 实现覆盖 | SC_01 | J1 | resolver.py | None | [ ] ⏳ | None |\n"
            + "| T2 | 验证真实链路 | SC_02 | E2E | test_e2e.py | T1 | [ ] ⏳ | None |\n",
            encoding="utf-8",
        )
        return task_dir

    def write_report(self, task_dir: Path, unit_mode: str = "auto", include_e2e: bool = True) -> None:
        if unit_mode == "auto":
            unit = (
                "```verify\n"
                "id: V1\nscenario: SC_01\nmode: auto\n"
                "cmd: python3 -c \"print('ok')\"\nexpect_exit: 0\n```\n"
            )
        else:
            unit = (
                "```verify\n"
                "id: V1\nscenario: SC_01\nmode: manual\nsteps: 人工确认\n```\n"
            )
        e2e = (
            "```verify\n"
            "id: V2\nscenario: SC_02\nmode: manual\nsteps: 执行真实链路\n```\n"
            if include_e2e else ""
        )
        (task_dir / "dev-report.md").write_text(unit + e2e, encoding="utf-8")


class TestSpec3Profile(Req3EngineTestCase):
    def test_spec3_is_detected_and_contract_is_valid(self):
        spec_dir = self.make_spec()
        self.assertEqual(xdev.detect_type(spec_dir), "spec3")
        self.assertEqual(req3.spec3_contract_issues(spec_dir), [])
        result = xdev.validate_pkg(spec_dir, include_legacy=False)
        self.assertEqual(result["type"], "spec3")
        self.assertEqual(result["issues"], [])

    def test_spec3_requires_nonempty_module_risk(self):
        spec_dir = self.make_spec()
        spec_path = spec_dir / "spec.md"
        spec_path.write_text(
            spec_path.read_text(encoding="utf-8").replace(
                "输入被原地修改导致调用方状态污染", "",
            ),
            encoding="utf-8",
        )
        issues = req3.spec3_contract_issues(spec_dir)
        self.assertIn("V19", [item["rule"] for item in issues])
        self.assertIn("主要风险为空", " ".join(item["msg"] for item in issues))

    def test_scenario_parser_uses_stable_id_name_and_layer(self):
        spec_dir = self.make_spec()
        scenarios = req3.spec_scenarios(spec_dir / "spec.md")
        self.assertEqual(
            [(item["id"], item["name"], item["layer"]) for item in scenarios],
            [("SC_01", "标量覆盖", "unit"), ("SC_02", "真实链路", "e2e")],
        )

    def test_scenario_duplicate_id_is_rejected(self):
        spec_dir = self.make_spec()
        spec_path = spec_dir / "spec.md"
        spec_path.write_text(
            spec_path.read_text(encoding="utf-8").replace(
                "Scenario SC_02", "Scenario SC_01",
            ),
            encoding="utf-8",
        )
        issues = req3.spec3_contract_issues(spec_dir)
        self.assertIn("Scenario ID 重复：SC_01", " ".join(item["msg"] for item in issues))

    def test_scenario_id_requires_two_digit_format(self):
        spec_dir = self.make_spec()
        spec_path = spec_dir / "spec.md"
        spec_path.write_text(
            spec_path.read_text(encoding="utf-8").replace("SC_01", "SC_1"),
            encoding="utf-8",
        )
        issues = req3.spec3_contract_issues(spec_dir)
        self.assertIn(
            "Scenario 标题必须为 `### Scenario SC_01: <可判定行为名称>`",
            " ".join(item["msg"] for item in issues),
        )

    def test_scenario_id_must_increase_in_document_order(self):
        spec_dir = self.make_spec()
        spec_path = spec_dir / "spec.md"
        text = spec_path.read_text(encoding="utf-8")
        text = text.replace("Scenario SC_01", "Scenario SC_02", 1)
        text = text.replace("Scenario SC_02: 真实链路", "Scenario SC_01: 真实链路", 1)
        spec_path.write_text(text, encoding="utf-8")
        issues = req3.spec3_contract_issues(spec_dir)
        self.assertIn(
            "Scenario ID 必须从 SC_01 开始按文档顺序连续递增",
            " ".join(item["msg"] for item in issues),
        )

    def test_scenario_id_gap_is_rejected(self):
        spec_dir = self.make_spec()
        spec_path = spec_dir / "spec.md"
        spec_path.write_text(
            spec_path.read_text(encoding="utf-8").replace("SC_02", "SC_03"),
            encoding="utf-8",
        )
        issues = req3.spec3_contract_issues(spec_dir)
        self.assertIn(
            "Scenario ID 必须从 SC_01 开始按文档顺序连续递增",
            " ".join(item["msg"] for item in issues),
        )


class TestReq3Task(Req3EngineTestCase):
    def test_scaffold_dispatches_req3_template(self):
        self.make_spec()
        task_dir = self.root / "docs" / "spec" / "demo" / "tasks" / "resolver"
        code, output, error = capture(xdev.main, ["scaffold", str(task_dir), "--json"])
        self.assertEqual(code, 0, error)
        payload = json.loads(output)
        self.assertEqual(payload["profile"], "req3")
        checklist = (task_dir / "dev-checklist.md").read_text(encoding="utf-8")
        self.assertIn("| Scenario IDs |", checklist)
        self.assertNotIn("| Requirement |", checklist)

    def test_validate_and_spec_coverage_accept_complete_task(self):
        spec_dir = self.make_spec()
        task_dir = self.make_task()
        self.assertEqual(req3.validate_issues(task_dir), [])
        self.assertEqual(req3.spec_scenario_coverage(spec_dir), [])
        result = xdev.validate_target(task_dir, include_legacy=False)
        self.assertEqual(result["type"], "req3-task")
        self.assertEqual(result["issues"], [])

    def test_dangling_scenario_is_rejected(self):
        self.make_spec()
        task_dir = self.make_task()
        path = task_dir / "dev-checklist.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("SC_01 | J1", "SC_99 | J1"),
            encoding="utf-8",
        )
        issues = req3.validate_issues(task_dir)
        self.assertIn("R3Q5", [item["rule"] for item in issues])
        self.assertIn("Scenario ID 悬空", " ".join(item["msg"] for item in issues))

    def test_multiple_scenario_ids_per_task_row_are_supported(self):
        spec_dir = self.make_spec()
        task_dir = self.make_task()
        path = task_dir / "dev-checklist.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("SC_01 | J1", "SC_01, SC_02 | J1")
        text = "\n".join(line for line in text.splitlines() if "| T2 |" not in line) + "\n"
        path.write_text(text, encoding="utf-8")
        self.assertEqual(req3.validate_issues(task_dir), [])
        self.assertEqual(req3.task_scenarios(task_dir), ["SC_01", "SC_02"])
        self.assertEqual(req3.spec_scenario_coverage(spec_dir), [])


class TestReq3Verify(Req3EngineTestCase):
    def test_unit_auto_and_e2e_manual_pass(self):
        self.make_spec()
        task_dir = self.make_task()
        self.write_report(task_dir)
        code, output, error = capture(verify_engine.verify, task_dir, True, None)
        self.assertEqual(code, 0, error)
        payload = json.loads(output)
        self.assertEqual(payload["profile"], "req3")
        self.assertEqual(payload["expected_auto"], ["SC_01"])
        self.assertEqual(payload["expected_declared"], ["SC_02"])
        self.assertEqual(payload["uncovered"], [])

    def test_manual_unit_remains_uncovered(self):
        self.make_spec()
        task_dir = self.make_task()
        self.write_report(task_dir, unit_mode="manual")
        code, output, error = capture(verify_engine.verify, task_dir, True, None)
        self.assertEqual(code, 1, error)
        self.assertEqual(json.loads(output)["uncovered"], ["SC_01"])

    def test_missing_e2e_declaration_is_uncovered(self):
        self.make_spec()
        task_dir = self.make_task()
        self.write_report(task_dir, include_e2e=False)
        code, output, error = capture(verify_engine.verify, task_dir, True, None)
        self.assertEqual(code, 1, error)
        self.assertEqual(json.loads(output)["uncovered"], ["SC_02"])


if __name__ == "__main__":
    unittest.main()
