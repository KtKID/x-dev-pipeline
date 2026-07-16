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

import xdev  # noqa: E402


def capture_main(args: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = xdev.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def readme(*scenarios: tuple[str, str]) -> str:
    body = "\n\n".join(
        f"#### Scenario: {name}\n\n- **WHEN** 执行验证\n- **THEN** 得到预期结果\n- 验证: {mode}"
        for name, mode in scenarios
    )
    return f"""# verify-task

risk: Q2

## 核心目标

- 验证引擎工作。

## 需求要点

- 验证证据可复跑。

## 涉及模块

- tools/xdev.py

## 架构拆分策略

- 引擎负责机械事实。

## 技术设计

- verify 块是输入。

## 验收

### Requirement: 证据验证

{body}

### 自动化测试责任

- x-dev 写 verify 块。
"""


class TestVerifyCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = Path(self.tmp.name) / "task"
        self.task.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write_task(self, report: str, *scenarios: tuple[str, str]) -> None:
        (self.task / "README.md").write_text(readme(*scenarios), encoding="utf-8")
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

    def test_dev_report_template_uses_supported_manual_path(self):
        template = (ROOT / "skills/x-dev/templates/dev-report-template.md").read_text(encoding="utf-8")
        self.assertNotIn("no-test-framework", template)
        self.assertIn("验证: manual", template)
        self.assertIn("steps:", template)


if __name__ == "__main__":
    unittest.main()
