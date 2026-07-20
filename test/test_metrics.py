#!/usr/bin/env python3
"""Standard-library contract tests for tools/metrics.py."""

from __future__ import annotations

import ast
import io
import inspect
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import metrics  # noqa: E402


PROMPT = "设计一个 ESP32-S3 语音链路需求包"
REPO_SHA = "a" * 40


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def metadata(configuration: str = "with_skill") -> dict:
    return {
        "eval_id": 1,
        "eval_name": "esp32-voice",
        "configuration": configuration,
        "run_number": 1,
        "prompt": PROMPT,
        "model": "gpt-test",
        "repo_sha": REPO_SHA,
        "executor_inputs": [],
        "grader_only_inputs": ["skills/x-spec2/evals/evals.json"],
        "rubric_exposed": False,
    }


def grading(passed: int = 2, total: int = 2) -> dict:
    items = [
        {"text": f"expectation {index}", "passed": index <= passed, "evidence": f"evidence {index}"}
        for index in range(1, total + 1)
    ]
    return {
        "expectations": items,
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "pass_rate": passed / total,
        },
    }


def rollout(
    *, extra_turn: bool = False, task_complete_count: int = 1,
    second_model: str = "gpt-test",
) -> str:
    rows = [
        {
            "timestamp": "2026-07-20T00:00:00.000Z",
            "type": "session_meta",
            "payload": {
                "id": "session-1",
                "session_id": "parent-task-1",
                "git": {"commit_hash": REPO_SHA},
            },
        },
        {
            "timestamp": "2026-07-20T00:00:01.000Z",
            "type": "turn_context",
            "payload": {"model": "gpt-test"},
        },
        {
            "timestamp": "2026-07-20T00:00:02.000Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {"total_token_usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 20,
                    "output_tokens": 10,
                    "reasoning_output_tokens": 3,
                    "total_tokens": 110,
                }},
            },
        },
    ]
    if extra_turn:
        rows.extend([{
            "timestamp": "2026-07-20T00:00:03.000Z",
            "type": "response_item",
            "payload": {"type": "message", "role": "assistant", "content": []},
        }, {
            "timestamp": "2026-07-20T00:00:03.100Z",
            "type": "event_msg",
            "payload": {"type": "task_complete"},
        }, {
            "timestamp": "2026-07-20T00:00:03.500Z",
            "type": "turn_context",
            "payload": {"model": second_model},
        }])
    rows.extend([{
        "timestamp": "2026-07-20T00:00:04.800Z",
        "type": "response_item",
        "payload": {"type": "message", "role": "assistant", "content": []},
    }, {
        "timestamp": "2026-07-20T00:00:04.900Z",
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {"total_token_usage": {
                "input_tokens": 400,
                "cached_input_tokens": 250,
                "output_tokens": 50,
                "reasoning_output_tokens": 11,
                "total_tokens": 450,
            }},
        },
    }])
    for index in range(task_complete_count):
        rows.append({
            "timestamp": f"2026-07-20T00:00:0{5 + index}.000Z",
            "type": "event_msg",
            "payload": {"type": "task_complete"},
        })
    return "\n".join(json.dumps(row) for row in rows) + "\n"


def forked_multiturn_rollout(*, active_rubric: bool = False) -> str:
    rubric_path = "skills/x-spec2/evals/evals.json"
    rows = [
        {
            "timestamp": "2026-07-20T15:39:13.099Z",
            "type": "session_meta",
            "payload": {"id": "session-active", "git": {"commit_hash": REPO_SHA}},
        },
        {
            "timestamp": "2026-07-20T15:30:00.000Z",
            "type": "session_meta",
            "payload": {"id": "session-parent", "git": {"commit_hash": "b" * 40}},
        },
        {
            "timestamp": "2026-07-20T15:39:13.100Z",
            "type": "response_item",
            "payload": {"type": "message", "role": "assistant", "content": rubric_path},
        },
        {
            "timestamp": "2026-07-20T15:39:13.100Z",
            "type": "event_msg",
            "payload": {"type": "token_count", "info": {"total_token_usage": {
                "input_tokens": 1_563_360,
                "cached_input_tokens": 1_459_712,
                "output_tokens": 12_420,
                "reasoning_output_tokens": 4_191,
                "total_tokens": 1_575_780,
            }}},
        },
        {
            "timestamp": "2026-07-20T15:39:16.375Z",
            "type": "turn_context",
            "payload": {"model": "gpt-test"},
        },
        {
            "timestamp": "2026-07-20T15:42:00.000Z",
            "type": "response_item",
            "payload": {
                "type": "message", "role": "user",
                "content": rubric_path if active_rubric else "请修复 P0",
            },
        },
        {
            "timestamp": "2026-07-20T15:43:00.000Z",
            "type": "event_msg",
            "payload": {"type": "token_count", "info": {"total_token_usage": {
                "input_tokens": 2_000_000,
                "cached_input_tokens": 1_850_000,
                "output_tokens": 25_000,
                "reasoning_output_tokens": 7_000,
                "total_tokens": 2_025_000,
            }}},
        },
        {
            "timestamp": "2026-07-20T15:43:10.000Z",
            "type": "response_item",
            "payload": {"type": "message", "role": "assistant", "content": "初稿完成"},
        },
        {
            "timestamp": "2026-07-20T15:43:10.010Z",
            "type": "event_msg",
            "payload": {"type": "task_complete"},
        },
        {
            "timestamp": "2026-07-20T15:45:53.572Z",
            "type": "turn_context",
            "payload": {"model": "gpt-test"},
        },
        {
            "timestamp": "2026-07-20T15:46:59.364Z",
            "type": "response_item",
            "payload": {"type": "message", "role": "assistant", "content": "修复完成"},
        },
        {
            "timestamp": "2026-07-20T15:46:59.433Z",
            "type": "event_msg",
            "payload": {"type": "token_count", "info": {"total_token_usage": {
                "input_tokens": 2_329_026,
                "cached_input_tokens": 2_163_968,
                "output_tokens": 31_284,
                "reasoning_output_tokens": 8_097,
                "total_tokens": 2_360_310,
            }}},
        },
        {
            "timestamp": "2026-07-20T15:46:59.446Z",
            "type": "event_msg",
            "payload": {"type": "task_complete"},
        },
    ]
    return "\n".join(json.dumps(row) for row in rows) + "\n"


class MetricsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def prepare(self, configuration: str = "with_skill") -> tuple[Path, Path]:
        metadata_path = self.root / configuration / "eval_metadata.json"
        grading_path = self.root / configuration / "grading.json"
        write_json(metadata_path, metadata(configuration))
        write_json(grading_path, grading())
        return metadata_path, grading_path

    def run_main(self, args: list[str]) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = metrics.main(args)
        return code, stdout.getvalue(), stderr.getvalue()


class TestTimingExtraction(MetricsTestCase):
    def test_notification_extracts_real_total_and_duration_with_null_buckets(self):
        metadata_path, grading_path = self.prepare()
        timing_path = self.root / "timing.json"
        output = self.root / "measurement.json"
        write_json(timing_path, {"agent_id": "agent-1", "total_tokens": 84852, "duration_ms": 23332})
        code, _stdout, stderr = self.run_main([
            "extract", "--timing", str(timing_path), "--metadata", str(metadata_path),
            "--grading", str(grading_path), "--output", str(output),
        ])
        self.assertEqual(code, 0, stderr)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["source"], {"kind": "subagent_notification", "id": "agent-1"})
        self.assertEqual(result["duration_ms"], 23332)
        self.assertEqual(result["tokens"]["total"], 84852)
        self.assertIsNone(result["tokens"]["input"])
        self.assertIsNone(result["started_at"])
        self.assertEqual(result["quality"], {"passed": 2, "total": 2, "pass_rate": 1.0})

    def test_missing_notification_field_is_schema_error(self):
        metadata_path, grading_path = self.prepare()
        timing_path = self.root / "timing.json"
        write_json(timing_path, {"agent_id": "agent-1", "duration_ms": 10})
        code, _stdout, stderr = self.run_main([
            "extract", "--timing", str(timing_path), "--metadata", str(metadata_path),
            "--grading", str(grading_path), "--output", str(self.root / "out.json"),
        ])
        self.assertEqual(code, 2)
        self.assertIn("total_tokens", stderr)

    def test_identical_extract_is_byte_stable(self):
        metadata_path, grading_path = self.prepare()
        timing_path = self.root / "timing.json"
        output = self.root / "measurement.json"
        write_json(timing_path, {"agent_id": "agent-1", "total_tokens": 7, "duration_ms": 11})
        args = [
            "extract", "--timing", str(timing_path), "--metadata", str(metadata_path),
            "--grading", str(grading_path), "--output", str(output),
        ]
        self.assertEqual(self.run_main(args)[0], 0)
        first = output.read_bytes()
        self.assertEqual(self.run_main(args)[0], 0)
        self.assertEqual(output.read_bytes(), first)


class TestRolloutExtraction(MetricsTestCase):
    def test_forked_multiturn_uses_incremental_tokens_and_dispatch_duration(self):
        session = self.root / "forked.jsonl"
        session.write_text(forked_multiturn_rollout(), encoding="utf-8")
        result = metrics.parse_codex_session_source(
            session, ["skills/x-spec2/evals/evals.json"]
        )
        self.assertEqual(result["source"], {"kind": "codex_rollout", "id": "session-active"})
        self.assertEqual(result["repo_sha"], REPO_SHA)
        self.assertEqual(result["tokens"], {
            "input": 765_666,
            "cached_input": 704_256,
            "output": 18_864,
            "reasoning_output": 3_906,
            "total": 784_530,
        })
        self.assertEqual(result["started_at"], "2026-07-20T15:39:13.099Z")
        self.assertEqual(result["ended_at"], "2026-07-20T15:46:59.364Z")
        self.assertEqual(result["duration_ms"], 466_265)

    def test_uses_last_cumulative_snapshot_and_assistant_reply_duration(self):
        metadata_path, grading_path = self.prepare()
        session = self.root / "rollout.jsonl"
        output = self.root / "measurement.json"
        session.write_text(rollout(), encoding="utf-8")
        code, _stdout, stderr = self.run_main([
            "extract", "--codex-session", str(session), "--metadata", str(metadata_path),
            "--grading", str(grading_path), "--output", str(output),
        ])
        self.assertEqual(code, 0, stderr)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["tokens"], {
            "input": 400,
            "cached_input": 250,
            "output": 50,
            "reasoning_output": 11,
            "total": 450,
        })
        self.assertEqual(result["duration_ms"], 4800)
        self.assertEqual(result["started_at"], "2026-07-20T00:00:00.000Z")
        self.assertEqual(result["ended_at"], "2026-07-20T00:00:04.800Z")

    def test_multiple_turns_and_completions_are_one_measurement(self):
        metadata_path, grading_path = self.prepare()
        session = self.root / "rollout.jsonl"
        session.write_text(rollout(extra_turn=True, task_complete_count=2), encoding="utf-8")
        code, _stdout, stderr = self.run_main([
            "extract", "--session", str(session), "--metadata", str(metadata_path),
            "--grading", str(grading_path), "--output", str(self.root / "out.json"),
        ])
        self.assertEqual(code, 0, stderr)

    def test_missing_task_complete_is_invalid(self):
        metadata_path, grading_path = self.prepare()
        session = self.root / "rollout.jsonl"
        session.write_text(rollout(task_complete_count=0), encoding="utf-8")
        output = self.root / "out.json"
        output.write_text("previous measurement\n", encoding="utf-8")
        code, _stdout, stderr = self.run_main([
            "extract", "--session", str(session), "--metadata", str(metadata_path),
            "--grading", str(grading_path), "--output", str(output),
        ])
        self.assertEqual(code, 1)
        self.assertIn("task_complete", stderr)
        self.assertEqual(output.read_text(encoding="utf-8"), "previous measurement\n")

    def test_grader_only_path_in_rollout_is_invalid(self):
        metadata_path, grading_path = self.prepare()
        session = self.root / "rollout.jsonl"
        rows = [json.loads(line) for line in rollout().splitlines()]
        rows.insert(-1, {
            "timestamp": "2026-07-20T00:00:04.900Z",
            "type": "response_item",
            "payload": {
                "type": "message", "role": "user",
                "content": "skills/x-spec2/evals/evals.json",
            },
        })
        session.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        code, _stdout, stderr = self.run_main([
            "extract", "--session", str(session), "--metadata", str(metadata_path),
            "--grading", str(grading_path), "--output", str(self.root / "out.json"),
        ])
        self.assertEqual(code, 1)
        self.assertIn("grader-only", stderr)

    def test_grader_only_path_in_inherited_prefix_is_ignored(self):
        session = self.root / "forked.jsonl"
        session.write_text(forked_multiturn_rollout(), encoding="utf-8")
        result = metrics.parse_codex_session_source(
            session, ["skills/x-spec2/evals/evals.json"]
        )
        self.assertEqual(result["tokens"]["total"], 784_530)

    def test_grader_only_path_in_active_window_is_invalid(self):
        session = self.root / "forked.jsonl"
        session.write_text(forked_multiturn_rollout(active_rubric=True), encoding="utf-8")
        with self.assertRaisesRegex(metrics.InvalidSample, "grader-only"):
            metrics.parse_codex_session_source(
                session, ["skills/x-spec2/evals/evals.json"]
            )

    def test_negative_codex_counter_delta_is_invalid_for_every_bucket(self):
        baseline = {
            "input_tokens": 1_563_360,
            "cached_input_tokens": 1_459_712,
            "output_tokens": 12_420,
            "reasoning_output_tokens": 4_191,
            "total_tokens": 1_575_780,
        }
        for field, baseline_value in baseline.items():
            with self.subTest(field=field):
                rows = [json.loads(line) for line in forked_multiturn_rollout().splitlines()]
                rows[-2]["payload"]["info"]["total_token_usage"][field] = baseline_value - 1
                session = self.root / f"counter-reset-{field}.jsonl"
                session.write_text(
                    "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
                )
                with self.assertRaisesRegex(metrics.InvalidSample, field):
                    metrics.parse_codex_session_source(session, [])

    def test_active_codex_snapshots_are_monotonic_for_every_bucket(self):
        fields = (
            "input_tokens", "cached_input_tokens", "output_tokens",
            "reasoning_output_tokens", "total_tokens",
        )
        for field in fields:
            with self.subTest(field=field):
                rows = [json.loads(line) for line in rollout().splitlines()]
                first = rows[2]["payload"]["info"]["total_token_usage"][field]
                rows[4]["payload"]["info"]["total_token_usage"][field] = first - 1
                session = self.root / f"active-reset-{field}.jsonl"
                session.write_text(
                    "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
                )
                with self.assertRaisesRegex(metrics.InvalidSample, field):
                    metrics.parse_codex_session_source(session, [])

    def test_malformed_active_header_does_not_fall_back_to_parent(self):
        rows = [json.loads(line) for line in forked_multiturn_rollout().splitlines()]
        rows[0]["payload"].pop("git")
        session = self.root / "malformed-header.jsonl"
        session.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(metrics.MetricsError, "commit_hash"):
            metrics.parse_codex_session_source(session, [])

    def test_final_turn_requires_well_formed_token_snapshot_after_reply(self):
        base_rows = [json.loads(line) for line in forked_multiturn_rollout().splitlines()]
        cases = {
            "missing": base_rows[:-2] + base_rows[-1:],
            "malformed": [json.loads(json.dumps(row)) for row in base_rows],
        }
        cases["malformed"][-2]["payload"]["info"] = {}
        for name, rows in cases.items():
            with self.subTest(name=name):
                session = self.root / f"final-token-{name}.jsonl"
                session.write_text(
                    "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
                )
                expected = metrics.InvalidSample if name == "missing" else metrics.MetricsError
                with self.assertRaises(expected):
                    metrics.parse_codex_session_source(session, [])

    def test_corrupt_json_and_invalid_timestamp_are_schema_errors(self):
        metadata_path, grading_path = self.prepare()
        cases = {
            "corrupt": rollout() + "{broken\n",
            "timestamp": rollout().replace(
                '"2026-07-20T00:00:00.000Z"', '"invalid-time"', 1
            ),
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                session = self.root / f"{name}.jsonl"
                session.write_text(content, encoding="utf-8")
                code, _stdout, _stderr = self.run_main([
                    "extract", "--session", str(session), "--metadata", str(metadata_path),
                    "--grading", str(grading_path), "--output", str(self.root / f"{name}.json"),
                ])
                self.assertEqual(code, 2)

    def test_active_session_change_and_missing_tokens_are_invalid(self):
        metadata_path, grading_path = self.prepare()
        rows = [json.loads(line) for line in rollout().splitlines()]
        second_session = {
            "timestamp": "2026-07-20T00:00:01.500Z",
            "type": "session_meta",
            "payload": {"id": "session-2", "git": {"commit_hash": REPO_SHA}},
        }
        multiple = self.root / "multiple-session.jsonl"
        multiple.write_text(
            "\n".join(json.dumps(row) for row in [*rows[:2], second_session, *rows[2:]]) + "\n",
            encoding="utf-8",
        )
        no_tokens = self.root / "no-tokens.jsonl"
        no_tokens.write_text(
            "\n".join(
                json.dumps(row)
                for row in rows
                if not (
                    row["type"] == "event_msg"
                    and row["payload"].get("type") == "token_count"
                )
            ) + "\n",
            encoding="utf-8",
        )
        for session, expected in ((multiple, "session ID"), (no_tokens, "token_count")):
            with self.subTest(session=session.name):
                code, _stdout, stderr = self.run_main([
                    "extract", "--session", str(session), "--metadata", str(metadata_path),
                    "--grading", str(grading_path), "--output", str(self.root / "out.json"),
                ])
                self.assertEqual(code, 1)
                self.assertIn(expected, stderr)

    def test_model_change_and_trailing_unfinished_turn_are_invalid(self):
        metadata_path, grading_path = self.prepare()
        cases = {
            "model": (rollout(extra_turn=True, second_model="gpt-other"), "模型数量"),
            "unfinished": (
                rollout() + json.dumps({
                    "timestamp": "2026-07-20T00:00:06.000Z",
                    "type": "turn_context",
                    "payload": {"model": "gpt-test"},
                }) + "\n",
                "task_complete",
            ),
        }
        for name, (content, expected) in cases.items():
            with self.subTest(name=name):
                session = self.root / f"{name}.jsonl"
                session.write_text(content, encoding="utf-8")
                code, _stdout, stderr = self.run_main([
                    "extract", "--session", str(session), "--metadata", str(metadata_path),
                    "--grading", str(grading_path), "--output", str(self.root / f"{name}.json"),
                ])
                self.assertEqual(code, 1)
                self.assertIn(expected, stderr)

    def test_session_alias_matches_canonical_codex_option(self):
        metadata_path, grading_path = self.prepare()
        session = self.root / "rollout.jsonl"
        session.write_text(rollout(), encoding="utf-8")
        outputs = []
        for option in ("--codex-session", "--session"):
            output = self.root / f"{option[2:]}.json"
            code, _stdout, stderr = self.run_main([
                "extract", option, str(session), "--metadata", str(metadata_path),
                "--grading", str(grading_path), "--output", str(output),
            ])
            self.assertEqual(code, 0, stderr)
            outputs.append(output.read_bytes())
        self.assertEqual(outputs[0], outputs[1])

    def test_codex_function_names_and_compatibility_delegate(self):
        source = inspect.getsource(metrics)
        tree = ast.parse(source)
        lower = metrics.parse_timing_source.__code__.co_firstlineno
        upper = metrics.build_measurement.__code__.co_firstlineno
        parser_functions = [
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and lower < node.lineno < upper
        ]
        self.assertIn("parse_codex_session_source", parser_functions)
        self.assertTrue(all(
            "codex" in name
            for name in parser_functions
            if name != "parse_rollout_source"
        ))

        session = self.root / "rollout.jsonl"
        session.write_text(rollout(), encoding="utf-8")
        self.assertEqual(
            metrics.parse_rollout_source(session, []),
            metrics.parse_codex_session_source(session, []),
        )


class TestMetadataAndPrivacy(MetricsTestCase):
    def test_prompt_is_hashed_and_private_content_is_absent(self):
        metadata_path, grading_path = self.prepare()
        timing_path = self.root / "timing.json"
        output = self.root / "measurement.json"
        write_json(timing_path, {"agent_id": "agent-private", "total_tokens": 1, "duration_ms": 2})
        self.assertEqual(self.run_main([
            "extract", "--timing", str(timing_path), "--metadata", str(metadata_path),
            "--grading", str(grading_path), "--output", str(output),
        ])[0], 0)
        raw = output.read_text(encoding="utf-8")
        result = json.loads(raw)
        self.assertEqual(result["prompt_sha256"], metrics.prompt_hash(PROMPT))
        self.assertNotIn(PROMPT, raw)
        self.assertNotIn(str(timing_path), raw)

    def test_rubric_overlap_is_invalid_sample(self):
        value = metadata()
        value["executor_inputs"] = ["skills/x-spec2/evals/evals.json"]
        metadata_path = self.root / "eval_metadata.json"
        grading_path = self.root / "grading.json"
        timing_path = self.root / "timing.json"
        write_json(metadata_path, value)
        write_json(grading_path, grading())
        write_json(timing_path, {"agent_id": "agent-1", "total_tokens": 1, "duration_ms": 2})
        code, _stdout, stderr = self.run_main([
            "extract", "--timing", str(timing_path), "--metadata", str(metadata_path),
            "--grading", str(grading_path), "--output", str(self.root / "out.json"),
        ])
        self.assertEqual(code, 1)
        self.assertIn("输入重叠", stderr)


class TestAggregate(MetricsTestCase):
    def make_measurement(self, configuration: str, *, model: str = "gpt-test") -> Path:
        run_dir = self.root / "eval-1" / configuration / "run-1"
        metadata_value = metadata(configuration)
        metadata_value["model"] = model
        measurement = {
            "schema_version": 1,
            "eval_id": 1,
            "eval_name": "esp32-voice",
            "configuration": configuration,
            "run_number": 1,
            "source": {"kind": "subagent_notification", "id": f"agent-{configuration}"},
            "model": model,
            "repo_sha": REPO_SHA,
            "prompt_sha256": metrics.prompt_hash(PROMPT),
            "started_at": None,
            "ended_at": None,
            "duration_ms": 2000 if configuration == "with_skill" else 1000,
            "tokens": {
                "input": None, "cached_input": None, "output": None,
                "reasoning_output": None, "total": 200 if configuration == "with_skill" else 100,
            },
            "quality": {"passed": 2 if configuration == "with_skill" else 1, "total": 2,
                        "pass_rate": 1.0 if configuration == "with_skill" else 0.5},
        }
        write_json(run_dir / "measurement.json", measurement)
        write_json(run_dir / "grading.json", grading(2 if configuration == "with_skill" else 1))
        return run_dir / "measurement.json"

    def test_paired_aggregate_uses_real_values_and_is_idempotent(self):
        self.make_measurement("with_skill")
        self.make_measurement("without_skill")
        args = ["aggregate-spec2", str(self.root)]
        code, _stdout, stderr = self.run_main(args)
        self.assertEqual(code, 0, stderr)
        result = json.loads((self.root / "benchmark.json").read_text(encoding="utf-8"))
        self.assertTrue(result["metadata"]["pilot"])
        self.assertEqual(result["metadata"]["sample_size_per_configuration"], 1)
        self.assertEqual(result["run_summary"]["delta"]["tokens"], "+100")
        first_json = (self.root / "benchmark.json").read_bytes()
        first_md = (self.root / "benchmark.md").read_bytes()
        self.assertEqual(self.run_main(args)[0], 0)
        self.assertEqual((self.root / "benchmark.json").read_bytes(), first_json)
        self.assertEqual((self.root / "benchmark.md").read_bytes(), first_md)

    def test_model_mismatch_is_invalid_pair(self):
        self.make_measurement("with_skill")
        self.make_measurement("without_skill", model="different")
        code, _stdout, stderr = self.run_main(["aggregate-spec2", str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("model", stderr)

    def test_grading_rubrics_must_match(self):
        self.make_measurement("with_skill")
        without_path = self.make_measurement("without_skill")
        grading_path = without_path.parent / "grading.json"
        value = json.loads(grading_path.read_text(encoding="utf-8"))
        value["expectations"][0]["text"] = "different expectation"
        write_json(grading_path, value)
        code, _stdout, stderr = self.run_main(["aggregate-spec2", str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("评分断言不一致", stderr)


if __name__ == "__main__":
    unittest.main()
