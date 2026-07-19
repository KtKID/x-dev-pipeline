#!/usr/bin/env python3
"""xdev flag 子命令的标准库契约测试。"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import xdev  # noqa: E402


def checklist(*rows: str) -> str:
    return """# task

| # | 任务 | 涉及文件 | 依赖 | 状态 | fix |
|---|------|---------|------|------|-----|
""" + "".join(f"{row}\n" for row in rows)


def capture_flag(task: Path, *extra: str) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    args = ["flag", str(task), *extra]
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = xdev.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def default_args(*extra: str) -> list[str]:
    return [
        "--task", "T2,T3",
        "--severity", "P0",
        "--loc", "src/a.py:10",
        "--msg", "空输入未处理",
        *extra,
    ]


class FlagTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make_task(self, name: str = "task", content: str | None = None) -> Path:
        task = self.root / name
        task.mkdir()
        if content is None:
            content = checklist(
                "| T1 | 已完成 | a.py | — | [x] 🟢 | keep-1 |",
                "| T2 | 待处理 | b.py | T1 | [x] ✅ | keep-2 |",
                "| T3 | 开发中 | c.py | T1 | [ ] ⏳ | keep-3 |",
            )
        (task / "dev-checklist.md").write_text(content, encoding="utf-8")
        return task


class TestFlagInputValidation(FlagTestCase):
    def test_normalizes_valid_parameters_and_preserves_pipe(self):
        values = xdev.normalize_flag_inputs(
            " T2,T3 ", "p1", "src/a.py:10", " 第一行 | A\r\n第二行 "
        )
        self.assertEqual(values, (["T2", "T3"], "P1", "src/a.py:10", "第一行 | A 第二行"))

    def test_rejects_invalid_parameter_matrix(self):
        cases = [
            ("T2,,T3", "P0", "a.py:1", "msg"),
            ("T2,T2", "P0", "a.py:1", "msg"),
            ("t2", "P0", "a.py:1", "msg"),
            ("T0", "P0", "a.py:1", "msg"),
            ("T2", "P3", "a.py:1", "msg"),
            ("T2", "P0", "a.py:0", "msg"),
            ("T2", "P0", "a.py:1|x", "msg"),
            ("T2", "P0", "a.py:1\nnext", "msg"),
            ("T2", "P0", "a.py:1", " \n "),
            ("T2", "P0", "a.py:1", "tab\there"),
        ]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(xdev.FlagError):
                xdev.normalize_flag_inputs(*values)

    def test_validation_errors_leave_all_files_unchanged(self):
        cases = [
            ["--task", "T9", "--severity", "P0", "--loc", "a.py:1", "--msg", "x"],
            ["--task", "T2,T2", "--severity", "P0", "--loc", "a.py:1", "--msg", "x"],
            ["--task", "T2", "--severity", "P0", "--loc", "a.py:0", "--msg", "x"],
            ["--task", "T2", "--severity", "P0", "--loc", "a.py:1", "--msg", "\n"],
        ]
        for index, args in enumerate(cases):
            task = self.make_task(f"invalid-{index}")
            before = (task / "dev-checklist.md").read_bytes()
            code, stdout, stderr = capture_flag(task, *args, "--json")
            self.assertEqual(code, 2, (stdout, stderr))
            self.assertEqual((task / "dev-checklist.md").read_bytes(), before)
            self.assertFalse((task / "reports").exists())

    def test_duplicate_target_row_is_rejected_without_writes(self):
        task = self.make_task(
            content=checklist(
                "| T2 | one | a.py | — | [x] 🟢 | a |",
                "| T2 | two | b.py | — | [ ] ⏳ | b |",
            )
        )
        before = (task / "dev-checklist.md").read_bytes()
        args = ["--task", "T2", "--severity", "P0", "--loc", "a.py:1", "--msg", "x"]
        code, _stdout, stderr = capture_flag(task, *args)
        self.assertEqual(code, 2)
        self.assertIn("重复", stderr)
        self.assertEqual((task / "dev-checklist.md").read_bytes(), before)
        self.assertFalse((task / "reports").exists())


class TestIssueLedger(FlagTestCase):
    def test_next_issue_id_uses_only_anchored_code_lines(self):
        report = """# ledger

- issue-1 | P0 | T1 | a.py:1 | mentions issue-999
summary issue-400
 - issue-300 | P0 | T1 | a.py:1 | indented
- issue-2 | P2 | T2 | b.py:2 | ok
"""
        self.assertEqual(xdev.next_issue_id(report), "issue-3")

    def test_same_second_rounds_use_numeric_suffixes(self):
        reports = self.root / "reports"
        reports.mkdir()
        fixed = datetime(2026, 7, 18, 15, 30, 45)
        base = reports / "qa-gate-report-20260718-153045.md"
        base.write_text("base", encoding="utf-8")
        (reports / "qa-gate-report-20260718-153045-01.md").write_text("one", encoding="utf-8")
        path, text, before_hash = xdev.resolve_current_report(reports, True, now=fixed)
        self.assertEqual(path.name, "qa-gate-report-20260718-153045-02.md")
        self.assertIn("## Issues", text)
        self.assertIsNone(before_hash)

    def test_latest_report_sorts_suffix_as_integer(self):
        reports = self.root / "reports"
        reports.mkdir()
        for suffix in ("-02", "-10", ""):
            path = reports / f"qa-gate-report-20260718-153045{suffix}.md"
            path.write_text(suffix or "base", encoding="utf-8")
        path, text, before_hash = xdev.resolve_current_report(reports, False)
        self.assertEqual(path.name, "qa-gate-report-20260718-153045-10.md")
        self.assertEqual(text, "-10")
        self.assertEqual(before_hash, xdev._sha256_bytes(b"-10"))

    def test_first_p0_flag_generates_issue_and_only_status_cells(self):
        task = self.make_task()
        code, stdout, stderr = capture_flag(task, *default_args("--json"))
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(list(payload), ["issue", "downgraded", "report", "recovered"])
        self.assertEqual(payload["issue"], "issue-1")
        self.assertEqual(payload["downgraded"], ["T2", "T3"])
        self.assertFalse(payload["recovered"])

        updated = (task / "dev-checklist.md").read_text(encoding="utf-8")
        self.assertIn("| T1 | 已完成 | a.py | — | [x] 🟢 | keep-1 |", updated)
        self.assertIn("| T2 | 待处理 | b.py | T1 | [!] 🔴 | keep-2 |", updated)
        self.assertIn("| T3 | 开发中 | c.py | T1 | [!] 🔴 | keep-3 |", updated)
        report = task / "reports" / "qa-gate" / payload["report"]
        ledger = report.read_text(encoding="utf-8")
        self.assertIn("由 `tools/xdev.py flag` 生成和维护", ledger)
        self.assertIn("- issue-1 | P0 | T2,T3 | src/a.py:10 | 空输入未处理", ledger)

    def test_p2_appends_issue_and_keeps_checklist_bytes(self):
        task = self.make_task()
        args = ["--task", "T3", "--severity", "P2", "--loc", "c.py:3", "--msg", "note | pipe"]
        before = (task / "dev-checklist.md").read_bytes()
        first = capture_flag(task, *args, "--json")
        second = capture_flag(task, *args, "--json")
        self.assertEqual(first[0], 0, first[2])
        self.assertEqual(second[0], 0, second[2])
        self.assertEqual((task / "dev-checklist.md").read_bytes(), before)
        self.assertEqual(json.loads(first[1])["downgraded"], [])
        self.assertEqual(json.loads(second[1])["issue"], "issue-2")
        report_name = json.loads(second[1])["report"]
        ledger = (task / "reports" / "qa-gate" / report_name).read_text(encoding="utf-8")
        self.assertIn("note | pipe", ledger)

    def test_already_blocked_target_stays_unchanged_but_gets_issue(self):
        content = checklist("| T2 | blocked | a.py | — | [!] 🔴 | keep |")
        task = self.make_task(content=content)
        before = (task / "dev-checklist.md").read_bytes()
        args = ["--task", "T2", "--severity", "P1", "--loc", "a.py:1", "--msg", "still broken"]
        code, stdout, stderr = capture_flag(task, *args, "--json")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["downgraded"], [])
        self.assertEqual((task / "dev-checklist.md").read_bytes(), before)

    def test_same_second_cli_new_round_resets_issue_number(self):
        task = self.make_task()
        args = ["--task", "T3", "--severity", "P2", "--loc", "c.py:3", "--msg", "note", "--new-round", "--json"]
        fixed = datetime(2026, 7, 18, 15, 30, 45)
        with patch.object(xdev, "datetime") as mocked_datetime:
            mocked_datetime.now.return_value = fixed
            outputs = [json.loads(capture_flag(task, *args)[1]) for _ in range(3)]
        self.assertEqual([item["issue"] for item in outputs], ["issue-1"] * 3)
        self.assertEqual(
            [item["report"] for item in outputs],
            [
                "qa-gate-report-20260718-153045.md",
                "qa-gate-report-20260718-153045-01.md",
                "qa-gate-report-20260718-153045-02.md",
            ],
        )

    def test_pure_emoji_checklist_remains_status_compatible(self):
        task = self.make_task(content=checklist("| T2 | legacy | a.py | — | ✅ | keep |"))
        args = ["--task", "T2", "--severity", "P0", "--loc", "a.py:1", "--msg", "broken"]
        code, _stdout, stderr = capture_flag(task, *args)
        self.assertEqual(code, 0, stderr)
        tasks, _issues = xdev.resolve_task_list(task)
        self.assertEqual(tasks[0]["status"], xdev.BLOCKED)


class TestFlagTransactionRecovery(FlagTestCase):
    def interrupt_after_first_replace(self, task: Path) -> tuple[int, str, str]:
        real_replace = os.replace
        calls = 0

        def flaky_replace(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated interruption")
            return real_replace(source, target)

        with patch.object(xdev.os, "replace", side_effect=flaky_replace):
            return capture_flag(task, *default_args("--json"))

    def test_interrupted_transaction_rolls_forward_before_new_issue(self):
        task = self.make_task()
        first = self.interrupt_after_first_replace(task)
        self.assertEqual(first[0], 2)
        marker = task / "reports" / "qa-gate" / xdev.FLAG_MARKER_NAME
        self.assertTrue(marker.exists())
        self.assertIn("[!] 🔴", (task / "dev-checklist.md").read_text(encoding="utf-8"))

        new_args = ["--task", "T1", "--severity", "P2", "--loc", "new.py:1", "--msg", "new", "--json"]
        code, stdout, stderr = capture_flag(task, *new_args)
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["issue"], "issue-1")
        self.assertTrue(payload["recovered"])
        self.assertFalse(marker.exists())
        ledger = (task / "reports" / "qa-gate" / payload["report"]).read_text(encoding="utf-8")
        self.assertIn("空输入未处理", ledger)
        self.assertNotIn("| new", ledger)

    def test_recovery_precedes_value_validation(self):
        task = self.make_task()
        self.assertEqual(self.interrupt_after_first_replace(task)[0], 2)
        marker = task / "reports" / "qa-gate" / xdev.FLAG_MARKER_NAME
        self.assertTrue(marker.exists())

        bad_args = ["--task", "T0", "--severity", "P1", "--loc", "x.py:1", "--msg", "bad", "--json"]
        code, stdout, stderr = capture_flag(task, *bad_args)
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["issue"], "issue-1")
        self.assertTrue(payload["recovered"])
        self.assertFalse(marker.exists())
        ledger = (task / "reports" / "qa-gate" / payload["report"]).read_text(encoding="utf-8")
        self.assertNotIn("bad", ledger)

    def test_missing_recovery_temp_keeps_marker_and_returns_two(self):
        task = self.make_task()
        self.assertEqual(self.interrupt_after_first_replace(task)[0], 2)
        marker_path = task / "reports" / "qa-gate" / xdev.FLAG_MARKER_NAME
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        report_entry = next(item for item in marker["targets"] if "qa-gate-report" in item["target"])
        (task / report_entry["temp"]).unlink()
        code, _stdout, stderr = capture_flag(task, *default_args("--json"))
        self.assertEqual(code, 2)
        self.assertIn("恢复材料缺失", stderr)
        self.assertTrue(marker_path.exists())

    def test_marker_publication_competition_recovers_winner(self):
        task = self.make_task()
        checklist_path = task / "dev-checklist.md"
        report_path = task / "reports" / "qa-gate" / "qa-gate-report-20260718-153045.md"
        report_path.parent.mkdir(parents=True)
        winner_checklist = checklist("| T1 | winner | a.py | — | [!] 🔴 | keep |")
        winner_report = xdev.append_issue_line(
            xdev.render_issue_report(report_path),
            {"issue": "issue-7", "tasks": ["T1"], "severity": "P0", "loc": "a.py:7", "msg": "winner"},
        )
        winner_result = {
            "issue": "issue-7", "downgraded": ["T1"], "report": report_path.name, "recovered": False,
        }
        real_link = os.link

        def publish_winner(_source, marker_path):
            transaction = "winner"
            target_data = [
                (checklist_path, winner_checklist.encode()),
                (report_path, winner_report.encode()),
            ]
            targets = []
            for target, data in target_data:
                temp = target.parent / f".{target.name}.{transaction}.tmp"
                xdev._write_durable_temp(temp, data)
                targets.append({
                    "target": xdev._relative_transaction_path(task, target),
                    "temp": xdev._relative_transaction_path(task, temp),
                    "sha256": xdev._sha256_bytes(data),
                    "before_sha256": xdev._sha256_file(target),
                })
            winner_marker_temp = report_path.parent / ".winner-marker.tmp"
            marker = {
                "version": xdev.FLAG_MARKER_VERSION,
                "transaction": transaction,
                "marker_temp": xdev._relative_transaction_path(task, winner_marker_temp),
                "targets": targets,
                "result": winner_result,
            }
            xdev._write_durable_temp(
                winner_marker_temp,
                json.dumps(marker, ensure_ascii=False, separators=(",", ":")).encode(),
            )
            real_link(winner_marker_temp, marker_path)
            raise FileExistsError("winner published first")

        ours = {
            "issue": "issue-1", "downgraded": [], "report": report_path.name, "recovered": False,
        }
        with patch.object(xdev.os, "link", side_effect=publish_winner):
            result = xdev.commit_flag_transaction(
                task,
                checklist_path,
                checklist_path.read_text(encoding="utf-8"),
                report_path,
                xdev.render_issue_report(report_path),
                ours,
                xdev._sha256_file(checklist_path),
                None,
            )
        self.assertEqual(result["issue"], "issue-7")
        self.assertTrue(result["recovered"])
        self.assertEqual(checklist_path.read_text(encoding="utf-8"), winner_checklist)
        self.assertEqual(report_path.read_text(encoding="utf-8"), winner_report)
        self.assertFalse((report_path.parent / xdev.FLAG_MARKER_NAME).exists())

    def test_stale_new_round_cannot_overwrite_completed_round(self):
        task = self.make_task()
        checklist_path = task / "dev-checklist.md"
        report_path = task / "reports" / "qa-gate" / "qa-gate-report-20260718-153045.md"
        report_path.parent.mkdir(parents=True)
        completed = "# completed by an earlier transaction\n"
        report_path.write_text(completed, encoding="utf-8")
        result = {
            "issue": "issue-1", "downgraded": [], "report": report_path.name, "recovered": False,
        }
        with self.assertRaises(xdev.FlagError) as ctx:
            xdev.commit_flag_transaction(
                task,
                checklist_path,
                checklist_path.read_text(encoding="utf-8"),
                report_path,
                "# stale slower transaction\n",
                result,
                xdev._sha256_file(checklist_path),
                None,
            )
        self.assertIn("目标发生变化", str(ctx.exception))
        self.assertEqual(report_path.read_text(encoding="utf-8"), completed)
        self.assertFalse((report_path.parent / xdev.FLAG_MARKER_NAME).exists())

    def test_marker_rejects_path_escape(self):
        task = self.make_task()
        reports = task / "reports" / "qa-gate"
        reports.mkdir(parents=True)
        marker = {
            "version": xdev.FLAG_MARKER_VERSION,
            "targets": [
                {"target": "../outside", "temp": "tmp-a", "sha256": "0" * 64},
                {
                    "target": "dev-checklist.md",
                    "temp": "tmp-b",
                    "sha256": "0" * 64,
                    "before_sha256": None,
                },
            ],
            "result": {"issue": "issue-1", "downgraded": [], "report": "x.md", "recovered": False},
        }
        marker_path = reports / xdev.FLAG_MARKER_NAME
        marker_path.write_text(json.dumps(marker), encoding="utf-8")
        code, _stdout, stderr = capture_flag(task, *default_args())
        self.assertEqual(code, 2)
        self.assertIn("越出 task", stderr)
        self.assertTrue(marker_path.exists())


if __name__ == "__main__":
    unittest.main()
