#!/usr/bin/env python3
"""xdev 薄 CLI 的模块所有权、当前 task 分流和旧路径退役测试。"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [
    str(ROOT / "skills" / "x-dev" / "scripts"),
    str(ROOT / "skills" / "x-qa-gate" / "scripts"),
    str(ROOT / "skills" / "x-verify" / "scripts"),
    str(ROOT / "skills" / "x-req" / "scripts"),
    str(ROOT / "skills" / "x-spec" / "scripts"),
]

import flag as flag_engine  # noqa: E402
import req  # noqa: E402
import validator  # noqa: E402
import verify as verify_engine  # noqa: E402
import xdev  # noqa: E402


def capture(*args: str) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = xdev.main(list(args))
    return code, stdout.getvalue(), stderr.getvalue()


class TestModuleOwnership(unittest.TestCase):
    def test_xdev_is_thin_router(self):
        line_count = len((ROOT / "skills" / "x-dev" / "scripts" / "xdev.py").read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(line_count, 400)
        for removed_name in {
            "detect_type",
            "validate_pkg",
            "scenario_contract_issues",
            "parse_checklist",
            "topo_sort",
            "flag_command",
            "FlagError",
            "has_spec_marker",
        }:
            self.assertFalse(hasattr(xdev, removed_name), removed_name)
        self.assertIs(xdev.validator, validator)
        self.assertIs(xdev.flag_engine, flag_engine)
        self.assertIs(xdev.verify_engine, verify_engine)
        self.assertIs(xdev.req, req)

    def test_engines_own_moved_functions(self):
        self.assertTrue(hasattr(validator, "detect_type"))
        self.assertTrue(hasattr(validator, "validate_pkg"))
        self.assertTrue(hasattr(flag_engine, "flag_command"))
        self.assertTrue(hasattr(flag_engine, "recover_flag_transaction"))


class TestChangeValidation(unittest.TestCase):
    def test_removed_requirement_does_not_require_scenario(self):
        with tempfile.TemporaryDirectory() as tmp:
            change = Path(tmp) / "change"
            delta = change / "specs" / "demo"
            delta.mkdir(parents=True)
            (change / "proposal.md").write_text("# Proposal\n", encoding="utf-8")
            (change / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
            (delta / "spec.md").write_text(
                """## ADDED Requirements

### Requirement: Active

#### Scenario: Valid

- **GIVEN** active input
- **WHEN** validation runs
- **THEN** the scenario passes

## REMOVED Requirements

### Requirement: Historical

**Reason**: retired
""",
                encoding="utf-8",
            )

            result = validator.validate_pkg(change, include_legacy=False)

        self.assertEqual(result["type"], "change")
        self.assertEqual(result["issues"], [])


class TestCurrentTaskRouting(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.spec = self.root / "docs" / "spec" / "demo"
        self.task = self.spec / "tasks" / "implementation"
        self.spec.mkdir(parents=True)
        (self.spec / "spec.md").write_text(
            "> spec_version: 3\n\n# demo\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_req_instructions_uses_current_registry(self):
        code, output, error = capture(
            "instructions",
            "dev-checklist",
            "--task",
            str(self.task),
            "--json",
        )
        self.assertEqual(code, 0, error)
        payload = json.loads(output)
        self.assertEqual(payload["profile"], "req")
        self.assertEqual(payload["artifact"], "dev-checklist")
        self.assertEqual(payload["requires"], [])
        self.assertIn("Scenario IDs", payload["template"])

    def test_spec2_task_commands_are_rejected(self):
        (self.spec / "spec.md").write_text(
            "> spec_version: 2\n\n# demo\n",
            encoding="utf-8",
        )
        code, _output, error = capture(
            "instructions",
            "dev-checklist",
            "--task",
            str(self.task),
            "--json",
        )
        self.assertEqual(code, 2)
        self.assertIn("spec_version: 3", error)

        code, output, error = capture("validate", str(self.spec), "--json")
        self.assertEqual(code, 1, error)
        result = json.loads(output)["packages"][0]
        self.assertEqual(result["type"], "unsupported-spec2")
        self.assertIn("已废除", result["issues"][0]["msg"])

    def test_legacy_task_commands_are_rejected(self):
        legacy = self.root / "dev-pipeline" / "tasks" / "old"
        legacy.mkdir(parents=True)
        (legacy / "README.md").write_text("# old\n", encoding="utf-8")
        (legacy / "dev-checklist.md").write_text("| # | 状态 |\n|---|---|\n", encoding="utf-8")

        code, _output, error = capture("status", str(legacy), "--json")
        self.assertEqual(code, 2)
        self.assertIn("spec_version: 3", error)

        code, output, error = capture("validate", str(legacy), "--json")
        self.assertEqual(code, 1, error)
        payload = json.loads(output)
        result = payload["packages"][0]
        self.assertEqual(result["type"], "unknown")
        self.assertNotIn("V8", {item["rule"] for item in result["issues"]})
        self.assertNotIn("V12", {item["rule"] for item in result["issues"]})


if __name__ == "__main__":
    unittest.main()
