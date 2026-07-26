#!/usr/bin/env python3
"""req3 verify 块解析、执行边界和模块所有权测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(ROOT / "tools"))

import req3  # noqa: E402
import verify as verify_engine  # noqa: E402
import xdev  # noqa: E402


class TestVerifyBlocks(unittest.TestCase):
    def write_report(self, root: Path, content: str) -> Path:
        report = root / "dev-report.md"
        report.write_text(content, encoding="utf-8")
        return report

    def test_parse_auto_and_manual_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = self.write_report(
                Path(temporary),
                "```verify\n"
                "id: V1\nscenario: SC_01\nmode: auto\n"
                "cmd: python3 -c \"print('ok')\"\nexpect_contains: ok\n```\n\n"
                "```verify\n"
                "id: V2\nscenario: SC_02\nmode: manual\nsteps: 执行真实链路\n```\n",
            )
            blocks = verify_engine.parse_verify_blocks(report)
        self.assertEqual([item["id"] for item in blocks], ["V1", "V2"])
        self.assertEqual([item["mode"] for item in blocks], ["auto", "manual"])

    def test_duplicate_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = self.write_report(
                Path(temporary),
                "```verify\nid: V1\ncmd: true\n```\n"
                "```verify\nid: V1\ncmd: true\n```\n",
            )
            with self.assertRaisesRegex(ValueError, "重复"):
                verify_engine.parse_verify_blocks(report)

    def test_unknown_key_and_manual_without_steps_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = self.write_report(
                Path(temporary),
                "```verify\nid: V1\nmode: manual\nunknown: value\n```\n",
            )
            with self.assertRaisesRegex(ValueError, "unknown"):
                verify_engine.parse_verify_blocks(report)

            report = self.write_report(
                Path(temporary),
                "```verify\nid: V1\nmode: manual\nscenario: SC_01\n```\n",
            )
            with self.assertRaisesRegex(ValueError, "steps"):
                verify_engine.parse_verify_blocks(report)

    def test_only_filter_executes_selected_auto_block(self):
        blocks = [
            {
                "id": "slow",
                "scenario": "SC_01",
                "cmd": "python3 -c \"import time; time.sleep(2)\"",
                "cwd": ".",
                "expect_exit": 0,
                "expect_contains": [],
                "timeout": 1,
                "mode": "auto",
                "steps": "",
            },
            {
                "id": "fast",
                "scenario": "SC_02",
                "cmd": "python3 -c \"print('fast')\"",
                "cwd": ".",
                "expect_exit": 0,
                "expect_contains": ["fast"],
                "timeout": None,
                "mode": "auto",
                "steps": "",
            },
        ]
        with tempfile.TemporaryDirectory() as temporary:
            passed, failed, manual, declared = verify_engine.execute_verify_blocks(
                blocks, "fast", Path(temporary), "项目",
            )
        self.assertEqual([item["id"] for item in passed], ["fast"])
        self.assertEqual(failed, [])
        self.assertEqual(manual, [])
        self.assertEqual(declared, {"SC_01", "SC_02"})


class TestVerifyOwnership(unittest.TestCase):
    def test_verify_has_single_module_owner(self):
        owned_names = {
            "latest_dev_report",
            "parse_verify_blocks",
            "project_root_of_task_dir",
            "verify_cwd",
            "execute_verify_block",
            "verify_req3",
            "verify",
        }
        for name in owned_names:
            self.assertTrue(hasattr(verify_engine, name), name)
            self.assertFalse(hasattr(xdev, name), f"xdev.{name}")
            self.assertFalse(hasattr(req3, name), f"req3.{name}")
        for removed_name in {
            "acceptance_scenarios",
            "acceptance_defects",
            "task_requirements",
            "verify_req2",
        }:
            self.assertFalse(hasattr(verify_engine, removed_name), removed_name)
        self.assertIs(xdev.verify_engine, verify_engine)


if __name__ == "__main__":
    unittest.main()
