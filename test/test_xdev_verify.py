#!/usr/bin/env python3
"""xdev verify 子命令的标准库测试。"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import req  # noqa: E402
import verify as verify_engine  # noqa: E402
import xdev  # noqa: E402


def capture_main(args: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = xdev.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def spec_md(*scenarios: tuple[str, str]) -> str:
    body = "\n\n".join(
        f"#### Scenario: {name}\n\n- **WHEN** 执行验证\n- **THEN** 得到预期结果\n- 验证: {mode}"
        for name, mode in scenarios
    )
    return f"""# verify-spec

> spec_version: 2

## 验收

### Requirement: 证据验证

{body}

"""


class TestVerifyCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.spec = self.root / "docs" / "spec" / "verify-spec"
        self.task = self.spec / "tasks" / "task"
        self.task.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write_task(self, report: str, *scenarios: tuple[str, str]) -> None:
        (self.spec / "spec.md").write_text(spec_md(*scenarios), encoding="utf-8")
        (self.spec / "modules.md").write_text("# modules\n", encoding="utf-8")
        (self.task / "dev-checklist.md").write_text(
            "# task\n\n"
            "> spec: docs/spec/verify-spec\n"
            "> risk: Q1\n\n"
            "| # | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix |\n"
            "|---|---------|-------------|------|----------|------|------|-----|\n"
            "| T1 | 验证证据 | 证据验证 | 低 | None | None | [x] ✅ | None |\n",
            encoding="utf-8",
        )
        (self.task / "dev-report.md").write_text(report, encoding="utf-8")

    def verify_json(self, *extra: str) -> tuple[int, dict, str]:
        code, stdout, stderr = capture_main(["verify", str(self.task), "--json", *extra])
        return code, json.loads(stdout), stderr

    def test_auto_and_manual_evidence_passes(self):
        self.write_task(
            """# report

```verify
id: S1
scenario: 自动验证
cmd: python3 -c "print('green')"
expect_contains: green
expect_contains: ree
```

```verify
id: M1
scenario: 人工验证
mode: manual
steps: 打开页面并检查结果
```
""",
            ("自动验证", "auto"),
            ("人工验证", "manual"),
        )
        code, payload, stderr = self.verify_json()
        self.assertEqual(code, 0, stderr)
        self.assertEqual([item["id"] for item in payload["pass"]], ["S1"])
        self.assertEqual([item["id"] for item in payload["manual"]], ["M1"])
        self.assertEqual(payload["fail"], [])
        self.assertEqual(payload["uncovered"], [])

    def test_reports_exit_contains_and_uncovered_failures(self):
        self.write_task(
            """# report

```verify
id: S1
scenario: 有失败的场景
cmd: python3 -c "import sys; print('actual'); sys.exit(3)"
expect_exit: 0
expect_contains: expected
```
""",
            ("有失败的场景", "auto"),
            ("没有回指的场景", "auto"),
        )
        code, payload, stderr = self.verify_json()
        self.assertEqual(code, 1, stderr)
        self.assertEqual(payload["fail"][0]["id"], "S1")
        self.assertEqual(payload["fail"][0]["exit_code"], 3)
        self.assertEqual(payload["fail"][0]["missing_contains"], ["expected"])
        self.assertEqual(payload["uncovered"], ["没有回指的场景"])

    def test_parse_errors_return_two(self):
        self.write_task(
            """```verify
id: S1
cmd: python3 -c "print('one')"
```

```verify
id: S1
mode: auto
```
""",
            ("任意", "manual"),
        )
        code, _stdout, stderr = capture_main(["verify", str(self.task), "--json"])
        self.assertEqual(code, 2)
        self.assertIn("重复", stderr)

    def test_unknown_key_and_manual_without_steps_return_two(self):
        self.write_task(
            """```verify
id: S1
mode: manual
unknown: value
```
""",
            ("任意", "manual"),
        )
        code, _stdout, stderr = capture_main(["verify", str(self.task), "--json"])
        self.assertEqual(code, 2)
        self.assertIn("unknown", stderr)

    def test_timeout_and_only_filter(self):
        self.write_task(
            """```verify
id: slow
scenario: 慢命令
cmd: python3 -c "import time; time.sleep(2)"
timeout: 1
```

```verify
id: fast
scenario: 快命令
cmd: python3 -c "print('fast')"
expect_contains: fast
```
""",
            ("慢命令", "auto"),
            ("快命令", "auto"),
        )
        code, payload, stderr = self.verify_json("--only", "fast")
        self.assertEqual(code, 0, stderr)
        self.assertEqual([item["id"] for item in payload["pass"]], ["fast"])

        code, payload, stderr = self.verify_json()
        self.assertEqual(code, 1, stderr)
        self.assertTrue(payload["fail"][0]["timed_out"])

    def test_legacy_task_path_is_rejected(self):
        legacy_task = self.root / "dev-pipeline" / "tasks" / "legacy-task"
        legacy_task.mkdir(parents=True)
        (legacy_task / "README.md").write_text("# legacy\n", encoding="utf-8")
        (legacy_task / "dev-report.md").write_text("# report\n", encoding="utf-8")

        code, stdout, stderr = capture_main(["verify", str(legacy_task), "--json"])
        self.assertEqual(code, 2, stdout)
        self.assertIn("不在 docs/spec/<spec-name>/tasks/<task-name>/ 结构下", stderr)

    def test_dev_report_template_uses_supported_manual_path(self):
        template = (ROOT / "skills/x-dev/templates/dev-report-template.md").read_text(encoding="utf-8")
        self.assertNotIn("no-test-framework", template)
        self.assertIn("验证: manual", template)
        self.assertIn("steps:", template)

    def test_verify_implementation_has_single_module_owner(self):
        owned_names = {
            "latest_dev_report",
            "parse_verify_blocks",
            "acceptance_scenarios",
            "acceptance_defects",
            "task_requirements",
            "project_root_of_task_dir",
            "verify_cwd",
            "execute_verify_block",
            "verify_req2",
            "verify",
        }
        for name in owned_names:
            self.assertTrue(hasattr(verify_engine, name), name)
            self.assertFalse(hasattr(xdev, name), f"xdev.{name}")
            self.assertFalse(hasattr(req, name), f"req.{name}")
        for removed_name in {"legacy_acceptance_scenarios", "verify_legacy"}:
            self.assertFalse(hasattr(verify_engine, removed_name), removed_name)
        self.assertIs(xdev.verify_engine, verify_engine)


if __name__ == "__main__":
    unittest.main()
