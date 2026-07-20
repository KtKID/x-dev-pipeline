#!/usr/bin/env python3
"""xdev V8-V12 旧结构校验 + instructions 产物依赖事实的标准库测试。

scaffold 已整体委托 req.py（不再有旧结构分支），其测试见 test_req_engine.py。
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import xdev  # noqa: E402


def capture_main(args: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = xdev.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def valid_readme(modules: tuple[str, ...] = ()) -> str:
    module_lines = "\n".join(f"- {module}" for module in modules)
    return f"""# task

risk: Q2

## 核心目标：可验证的目标

## 需求要点

- 一个需求

## 涉及模块

{module_lines}

## 架构拆分策略

- 边界明确

## 技术设计

- 架构归属明确

## 验收

### Requirement: task 可验证

task SHALL 有可复跑证据。

#### Scenario: 单元测试通过

- **WHEN** 开发者执行单元测试
- **THEN** 测试退出码为 0
- 验证: auto

### 自动化测试责任

- x-dev 在 dev-report.md verify 块记录验证命令。
"""


def valid_q0_readme() -> str:
    return """# task

risk: Q0

## 核心目标

- 最小目标

## 验收

### Requirement: 最小行为

#### Scenario: 人工检查

- **WHEN** 用户执行操作
- **THEN** 看到预期结果
- 验证: manual

### 自动化测试责任

- 不需要自动化测试。
"""


def valid_checklist(status: str = "[ ] ⏳", dependency: str = "—") -> str:
    return f"""# task

| # | 任务 | 涉及文件 | 依赖 | 状态 | fix |
|---|------|---------|------|------|-----|
| T1 | 实现 | tools/xdev.py | {dependency} | {status} | — |
"""


def write_valid_task(task_dir: Path, with_diagram: bool = False) -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    modules = ("Artifact Engine", "Task Validator") if with_diagram else ()
    (task_dir / "README.md").write_text(valid_readme(modules), encoding="utf-8")
    (task_dir / "dev-checklist.md").write_text(valid_checklist(), encoding="utf-8")
    if with_diagram:
        (task_dir / "diagram.md").write_text(
            """```mermaid
flowchart TD
Engine[\"Artifact Engine<br/>registry\"]
Validator[\"Task Validator\"]
```
""",
            encoding="utf-8",
        )


class TestInstructions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = Path(self.tmp.name) / "task"
        self.task.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_json_contains_complete_contract(self):
        code, stdout, stderr = capture_main([
            "instructions", "readme", "--task", str(self.task), "--json",
        ])
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["artifact"], "readme")
        self.assertEqual(payload["requires"], [])
        self.assertFalse(payload["exists"])
        self.assertTrue(payload["template"])
        self.assertTrue(payload["instruction"])
        self.assertEqual(payload["dependencies"], [])

    def test_missing_dependency_is_fact(self):
        code, stdout, stderr = capture_main([
            "instructions", "dev-checklist", "--task", str(self.task), "--json",
        ])
        self.assertEqual(code, 0, stderr)
        dependency = json.loads(stdout)["dependencies"][0]
        self.assertEqual(dependency["id"], "readme")
        self.assertFalse(dependency["exists"])

    def test_unknown_artifact_returns_usage_error(self):
        code, _stdout, stderr = capture_main([
            "instructions", "unknown", "--task", str(self.task), "--json",
        ])
        self.assertEqual(code, 2)
        self.assertIn("readme", stderr)
        self.assertIn("dev-checklist", stderr)

    def test_human_output_and_cwd_independent_template(self):
        previous = Path.cwd()
        try:
            os.chdir(self.task)
            code, stdout, stderr = capture_main([
                "instructions", "diagram", "--task", str(self.task),
            ])
        finally:
            os.chdir(previous)
        self.assertEqual(code, 0, stderr)
        self.assertIn("== diagram instructions", stdout)
        self.assertIn("== template", stdout)
        self.assertIn("== instruction", stdout)


class TestTaskValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def validate(self, task: Path) -> list[dict]:
        result = xdev.validate_pkg(task, include_legacy=False)
        self.assertEqual(result["type"], "task")
        return result["issues"]

    def test_accepts_valid_task_and_historical_changelog(self):
        task = self.root / "valid"
        write_valid_task(task)
        (task / "changelog.md").write_text("history", encoding="utf-8")
        self.assertEqual(self.validate(task), [])

    def test_standard_path_without_checklist_runs_v8(self):
        task = self.root / "dev-pipeline" / "tasks" / "missing-checklist"
        task.mkdir(parents=True)
        (task / "README.md").write_text(valid_readme(), encoding="utf-8")
        issues = self.validate(task)
        self.assertIn("V8", {item["rule"] for item in issues})
        self.assertIn("dev-checklist.md", " ".join(item["msg"] for item in issues))

    def test_v9_reports_header_status_and_missing_dependency(self):
        task = self.root / "broken-checklist"
        write_valid_task(task)
        (task / "dev-checklist.md").write_text(
            """| # | 任务 | 文件 | 依赖 | 状态 | fix |
|---|------|------|------|------|-----|
| T1 | x | x | T9 | waiting | — |
""",
            encoding="utf-8",
        )
        issues = self.validate(task)
        self.assertTrue(any(item["rule"] == "V9" and "表头" in item["msg"] for item in issues))

        (task / "dev-checklist.md").write_text(
            valid_checklist(status="waiting", dependency="T9"), encoding="utf-8"
        )
        issues = self.validate(task)
        messages = "\n".join(item["msg"] for item in issues if item["rule"] == "V9")
        self.assertIn("非法状态", messages)
        self.assertIn("T9", messages)

    def test_v9_accepts_legacy_emoji_status(self):
        task = self.root / "emoji"
        write_valid_task(task)
        (task / "dev-checklist.md").write_text(valid_checklist(status="🟢 测试通过"), encoding="utf-8")
        self.assertEqual(self.validate(task), [])

    def test_v10_reports_both_directions(self):
        task = self.root / "diagram"
        write_valid_task(task, with_diagram=True)
        (task / "README.md").write_text(valid_readme(("Artifact Engine", "Missing Module")), encoding="utf-8")
        (task / "diagram.md").write_text(
            """```mermaid
flowchart TD
Engine[\"Artifact Engine\"]
Extra[\"Extra Module\"]
```
""",
            encoding="utf-8",
        )
        messages = "\n".join(item["msg"] for item in self.validate(task) if item["rule"] == "V10")
        self.assertIn("Missing Module", messages)
        self.assertIn("Extra Module", messages)

    def test_v11_reports_missing_structure_and_accepts_manual(self):
        task = self.root / "readme"
        write_valid_task(task)
        (task / "README.md").write_text("# task\n\nrisk: Q2\n\n## 核心目标\n", encoding="utf-8")
        issues = self.validate(task)
        self.assertTrue(any(item["rule"] == "V11" for item in issues))

        (task / "README.md").write_text(
            valid_q0_readme(),
            encoding="utf-8",
        )
        self.assertFalse(any(item["rule"] == "V11" for item in self.validate(task)))

    def test_v11_reports_missing_technical_design(self):
        task = self.root / "missing-technical-design"
        write_valid_task(task)
        readme = valid_readme().replace("## 技术设计\n\n- 架构归属明确\n\n", "")
        (task / "README.md").write_text(readme, encoding="utf-8")

        messages = "\n".join(item["msg"] for item in self.validate(task) if item["rule"] == "V11")
        self.assertIn("技术设计", messages)

    def test_v11_accepts_q0_lite_and_rejects_missing_or_invalid_risk(self):
        task = self.root / "risk"
        write_valid_task(task)
        (task / "README.md").write_text(valid_q0_readme(), encoding="utf-8")
        self.assertEqual(self.validate(task), [])

        (task / "README.md").write_text(valid_q0_readme().replace("risk: Q0\n\n", ""), encoding="utf-8")
        messages = "\n".join(item["msg"] for item in self.validate(task) if item["rule"] == "V11")
        self.assertIn("risk", messages)

        (task / "README.md").write_text(valid_q0_readme().replace("risk: Q0", "risk: trivial"), encoding="utf-8")
        messages = "\n".join(item["msg"] for item in self.validate(task) if item["rule"] == "V11")
        self.assertIn("risk", messages)

    def test_v12_reports_incomplete_requirement_and_scenario(self):
        task = self.root / "acceptance"
        write_valid_task(task)
        broken = valid_readme().replace("- **WHEN** 开发者执行单元测试\n", "")
        broken = broken.replace("- 验证: auto", "- 验证: maybe")
        (task / "README.md").write_text(broken, encoding="utf-8")
        messages = "\n".join(item["msg"] for item in self.validate(task) if item["rule"] == "V12")
        self.assertIn("WHEN", messages)
        self.assertIn("验证", messages)

        no_scenario = valid_readme().replace(
            "#### Scenario: 单元测试通过\n\n- **WHEN** 开发者执行单元测试\n- **THEN** 测试退出码为 0\n- 验证: auto\n",
            "",
        )
        (task / "README.md").write_text(no_scenario, encoding="utf-8")
        messages = "\n".join(item["msg"] for item in self.validate(task) if item["rule"] == "V12")
        self.assertIn("Requirement", messages)

    def test_spec_regression_uses_existing_v1_to_v7_path(self):
        spec = ROOT / "openspec" / "specs" / "xdev-task-artifact-engine"
        result = xdev.validate_pkg(spec, include_legacy=False)
        self.assertEqual(result["type"], "capability")
        self.assertEqual(result["issues"], [])
