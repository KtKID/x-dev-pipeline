from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
SCRIPTS = SKILL_ROOT / "scripts"


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run_script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class PipelineEfficiencyBenchmarkTests(unittest.TestCase):
    def test_bundled_tools_match_repository_sources(self) -> None:
        bundle = SKILL_ROOT / "assets" / "executor-tools"
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        entries = {entry["name"]: entry["sha256"] for entry in manifest["tools"]}
        self.assertEqual(
            set(entries),
            {
                "xdev.py",
                "validator.py",
                "flag.py",
                "req3.py",
                "spec.py",
                "verify.py",
                "metrics.py",
            },
        )
        for name, expected in entries.items():
            self.assertEqual(sha256(bundle / name), expected)
            self.assertEqual(sha256(REPO_ROOT / "tools" / name), expected)

    def test_prepare_copies_all_skills_and_tools_then_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / "public-task"
            task.mkdir()
            (task / "00-overview.md").write_text("# Public task\n", encoding="utf-8")
            workspace = root / "workspace"

            prepared = run_script(
                "prepare_workspace.py",
                "--workspace",
                str(workspace),
                "--task-source",
                str(task),
                "--skills-root",
                str(REPO_ROOT / "skills"),
                "--json",
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            payload = json.loads(prepared.stdout)
            self.assertTrue(payload["valid"])
            self.assertEqual(len(payload["skills"]), 8)
            self.assertIn("x-dev-rag-call", payload["skills"])
            self.assertEqual(len(payload["tools"]), 6)
            manifest = Path(payload["manifest"])
            self.assertEqual(manifest, (root / "executor-package-manifest.json").resolve())
            self.assertFalse((workspace / "executor-package-manifest.json").exists())
            for name in payload["tools"]:
                self.assertTrue((workspace / "tools" / name).is_file())
            self.assertFalse((workspace / "tools" / "metrics.py").exists())
            self.assertFalse(any(workspace.glob("skills/*/evals")))

            valid = run_script(
                "validate_workspace.py",
                str(workspace),
                "--manifest",
                str(manifest),
                "--json",
            )
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
            self.assertTrue(json.loads(valid.stdout)["valid"])

            xdev = workspace / "tools" / "xdev.py"
            xdev.write_text(xdev.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
            invalid = run_script(
                "validate_workspace.py",
                str(workspace),
                "--manifest",
                str(manifest),
                "--json",
            )
            self.assertEqual(invalid.returncode, 1)
            issues = json.loads(invalid.stdout)["issues"]
            self.assertIn("W006", {issue["code"] for issue in issues})

    def test_normalize_compare_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline_metrics = root / "baseline-metrics.json"
            candidate_metrics = root / "candidate-metrics.json"
            baseline_grading = root / "baseline-grading.json"
            candidate_grading = root / "candidate-grading.json"
            baseline_run = root / "baseline.json"
            candidate_run = root / "candidate.json"
            baseline_pricing = root / "baseline-pricing.json"
            candidate_pricing = root / "candidate-pricing.json"
            comparison = root / "comparison.json"
            report = root / "comparison.md"
            acceptance_report = root / "acceptance-report.md"

            baseline_metrics.write_text(
                json.dumps(
                    {
                        "input_tokens": 900,
                        "cached_input_tokens": 500,
                        "output_tokens": 100,
                        "reasoning_output_tokens": 20,
                        "total_tokens": 1000,
                        "duration_ms": 2000
                    }
                ),
                encoding="utf-8",
            )
            candidate_metrics.write_text(
                json.dumps(
                    {
                        "input_tokens": 700,
                        "cached_input_tokens": 400,
                        "output_tokens": 100,
                        "reasoning_output_tokens": 20,
                        "total_tokens": 800,
                        "duration_ms": 1500
                    }
                ),
                encoding="utf-8",
            )
            baseline_grading.write_text(
                json.dumps(
                    {
                        "quality_score": 100,
                        "critical_gate_passed": True,
                        "summary": {"passed": 25, "total": 25}
                    }
                ),
                encoding="utf-8",
            )
            candidate_grading.write_text(
                json.dumps(
                    {
                        "quality_score": 100,
                        "critical_gate_passed": True,
                        "summary": {"passed": 25, "total": 25}
                    }
                ),
                encoding="utf-8",
            )
            pricing_payload = {
                "schema_version": 1,
                "currency": "USD",
                "model": "test-model",
                "source_url": "https://example.com/official-pricing",
                "queried_at": "2026-07-26",
                "rates_per_million_tokens": {
                    "uncached_input": 2.0,
                    "cached_input": 0.2,
                    "cache_write_input": 2.5,
                    "output": 10.0,
                },
                "telemetry": {"cache_write_tokens": None},
                "billing": {
                    "mode": "subscription_quota",
                    "actual_cash_increment": 0.0,
                    "quota_multiplier": 3.0,
                    "note": "fixture",
                },
            }
            baseline_pricing.write_text(json.dumps(pricing_payload), encoding="utf-8")
            candidate_pricing.write_text(json.dumps(pricing_payload), encoding="utf-8")

            for run_id, label, metrics, grading, pricing, output in (
                (
                    "baseline",
                    "Baseline",
                    baseline_metrics,
                    baseline_grading,
                    baseline_pricing,
                    baseline_run,
                ),
                (
                    "latest",
                    "Latest",
                    candidate_metrics,
                    candidate_grading,
                    candidate_pricing,
                    candidate_run,
                ),
            ):
                normalized = run_script(
                    "normalize_run.py",
                    "--run-id",
                    run_id,
                    "--label",
                    label,
                    "--scope",
                    "full_pipeline",
                    "--metrics",
                    str(metrics),
                    "--pricing",
                    str(pricing),
                    "--full-grading",
                    str(grading),
                    "--output",
                    str(output),
                )
                self.assertEqual(normalized.returncode, 0, normalized.stderr)

            compared = run_script(
                "compare_runs.py",
                "--run",
                str(baseline_run),
                "--run",
                str(candidate_run),
                "--baseline",
                "baseline",
                "--candidate",
                "latest",
                "--output-json",
                str(comparison),
                "--output-md",
                str(report),
            )
            self.assertEqual(compared.returncode, 0, compared.stderr)
            comparison_payload = json.loads(comparison.read_text(encoding="utf-8"))
            self.assertTrue(comparison_payload["promotion"]["passed"])
            self.assertEqual(
                comparison_payload["comparisons"]["latest"]["metrics"]["total_tokens"]["delta_pct"],
                -20.0,
            )
            baseline_cost = comparison_payload["runs"][0]["cost"]
            candidate_cost = comparison_payload["runs"][1]["cost"]
            self.assertEqual(baseline_cost["status"], "priced")
            self.assertAlmostEqual(
                baseline_cost["calculation"]["api_equivalent"],
                0.0019,
            )
            self.assertAlmostEqual(
                baseline_cost["calculation"]["cache_write_upper_bound"],
                0.0021,
            )
            self.assertAlmostEqual(
                candidate_cost["calculation"]["api_equivalent"],
                0.00168,
            )
            self.assertAlmostEqual(
                candidate_cost["billing"]["quota_equivalent"],
                0.00504,
            )
            amount_delta = comparison_payload["comparisons"]["latest"]["cost"]
            self.assertTrue(amount_delta["comparable"])
            self.assertAlmostEqual(amount_delta["delta"], -0.00022)
            self.assertEqual(amount_delta["delta_pct"], -11.58)
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("## 金额", report_text)
            self.assertIn("API 等价成本", report_text)
            self.assertIn("$0.001900", report_text)
            self.assertIn("https://example.com/official-pricing", report_text)
            acceptance_report.write_text(
                "\n".join(
                    [
                        "# Acceptance",
                        "",
                        "## 金额",
                        "",
                        "- 价格来源：https://example.com/official-pricing",
                        "- API 等价成本：$0.001680",
                        "- 实际现金增量：$0.000000",
                        "- 套餐额度：3× / $0.005040",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            validated = run_script(
                "validate_comparison.py",
                str(comparison),
                "--report",
                str(report),
                "--acceptance-report",
                str(acceptance_report),
                "--json",
            )
            self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
            self.assertTrue(json.loads(validated.stdout)["valid"])

    def test_missing_pricing_is_explicit_in_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            metrics = root / "metrics.json"
            grading = root / "grading.json"
            run_path = root / "run.json"
            latest_path = root / "latest.json"
            comparison = root / "comparison.json"
            report = root / "comparison.md"
            metrics.write_text(
                json.dumps(
                    {
                        "input_tokens": 90,
                        "cached_input_tokens": 50,
                        "output_tokens": 10,
                        "reasoning_output_tokens": 2,
                        "total_tokens": 100,
                        "duration_ms": 100,
                    }
                ),
                encoding="utf-8",
            )
            grading.write_text(
                json.dumps(
                    {
                        "quality_score": 100,
                        "critical_gate_passed": True,
                        "summary": {"passed": 1, "total": 1},
                    }
                ),
                encoding="utf-8",
            )
            normalized = run_script(
                "normalize_run.py",
                "--run-id",
                "only",
                "--label",
                "Only",
                "--scope",
                "full_pipeline",
                "--metrics",
                str(metrics),
                "--full-grading",
                str(grading),
                "--output",
                str(run_path),
            )
            self.assertEqual(normalized.returncode, 0, normalized.stderr)
            run_payload = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(run_payload["cost"]["status"], "unknown")
            self.assertEqual(
                run_payload["cost"]["unknown_reason"],
                "pricing_not_provided",
            )
            latest_payload = json.loads(json.dumps(run_payload))
            latest_payload["run_id"] = "latest"
            latest_payload["label"] = "Latest"
            latest_path.write_text(json.dumps(latest_payload), encoding="utf-8")

            compared = run_script(
                "compare_runs.py",
                "--run",
                str(run_path),
                "--run",
                str(latest_path),
                "--baseline",
                "only",
                "--candidate",
                "latest",
                "--output-json",
                str(comparison),
                "--output-md",
                str(report),
            )
            self.assertEqual(compared.returncode, 0, compared.stderr)
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("## 金额", report_text)
            self.assertIn("pricing_not_provided", report_text)
            self.assertIn("unknown", report_text)
            validated = run_script(
                "validate_comparison.py",
                str(comparison),
                "--report",
                str(report),
                "--json",
            )
            self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)

    def test_report_templates_require_amount_fields(self) -> None:
        templates = SKILL_ROOT / "assets" / "report-templates"
        acceptance = (templates / "acceptance-report.md").read_text(encoding="utf-8")
        comparison = (templates / "comparison-report.md").read_text(encoding="utf-8")
        pricing = json.loads((templates / "pricing.json").read_text(encoding="utf-8"))
        for text in (acceptance, comparison):
            self.assertIn("## 金额", text)
            self.assertIn("API 等价成本", text)
            self.assertIn("实际现金增量", text)
            self.assertIn("套餐额度", text)
        self.assertIn("rates_per_million_tokens", pricing)
        self.assertIn("billing", pricing)

    def test_public_task_only_preserves_existing_framework(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            existing = workspace / ".codex" / "skills" / "openspec-propose" / "SKILL.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("# OpenSpec\n", encoding="utf-8")
            task = root / "public-task"
            fixture = root / "public-fixture"
            task.mkdir()
            fixture.mkdir()
            (task / "00-overview.md").write_text("# Task\n", encoding="utf-8")
            (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")

            prepared = run_script(
                "prepare_workspace.py",
                "--profile",
                "public_task_only",
                "--allow-existing",
                "--workspace",
                str(workspace),
                "--task-source",
                str(task),
                "--fixture-source",
                str(fixture),
                "--json",
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            payload = json.loads(prepared.stdout)
            self.assertEqual(payload["skills"], [])
            self.assertEqual(payload["tools"], [])
            self.assertEqual(existing.read_text(encoding="utf-8"), "# OpenSpec\n")
            self.assertTrue((workspace / "task" / "00-overview.md").is_file())
            self.assertTrue((workspace / "fixture" / "README.md").is_file())
            self.assertFalse((workspace / "tools").exists())

            valid = run_script(
                "validate_workspace.py",
                str(workspace),
                "--manifest",
                payload["manifest"],
                "--json",
            )
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)


if __name__ == "__main__":
    unittest.main()
