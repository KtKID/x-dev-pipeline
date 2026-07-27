import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "x-adversarial-risk" / "scripts" / "risk_contract.py"
X_ADVERSARIAL_SKILL = ROOT / "skills" / "x-adversarial-risk" / "SKILL.md"
X_SPEC_SKILL = ROOT / "skills" / "x-spec3" / "SKILL.md"
CATALOG = (
    ROOT
    / "skills"
    / "x-adversarial-risk"
    / "references"
    / "risk-mistakes.md"
)
CATALOG_TAGS = (
    "phased-commit",
    "semantic-snapshot",
    "semantic-tail",
    "failed-idempotency",
    "error-contract",
)
ITERATION_5_FINAL_SPEC = (
    ROOT.parent
    / "iteration-5"
    / "eval-11-journal-index-recovery-spec-risk"
    / "terra"
    / "run-1"
    / "workspace"
    / "artifacts"
    / "spec.final.md"
)


def scenario(number: int, source: str) -> str:
    return f"""### Scenario SC_{number:02d}: 可判定行为 {number}

- **GIVEN** 一个有效初始状态
- **WHEN** 执行唯一动作
- **THEN** 返回可观察结果
- 测试层：unit
- 依据：J1
- 来源：{source}
"""


def valid_spec(
    *,
    version: int = 2,
    complexity: int,
    importance: int,
    average: str,
    budget: str,
    status: str,
    adversarial_count: int,
) -> str:
    scenarios = [scenario(1, "initial-spec")]
    for offset in range(adversarial_count):
        if version == 1:
            source = f"adversarial-review (AR-{offset + 1:03d})"
        else:
            source = (
                f"adversarial-review (AR-{offset + 1:03d}; "
                f"pattern:{CATALOG_TAGS[offset]})"
            )
        scenarios.append(
            scenario(
                offset + 2,
                source,
            )
        )

    return f"""> spec_version: 3
> adversarial_risk_version: {version}
> complexity: {complexity}
> importance: {importance}
> risk_average: {average}
> review_budget: {budget}
> adversarial_review: {status}

# demo

## 风险评分依据

- 复杂度：当前任务证据。
- 重要性：当前任务证据。

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | 可观察行为保持稳定 | 用户任务 | 任务直接定义 | 已确认 |

## 对抗性审查记录

| Review | 预算 | 检查候选 | 被推翻假设 | 新增 Scenario |
|---|---|---|---|---|
| ARV-1 | {budget} | failure-window | 无 | {"无" if adversarial_count == 0 else "SC_02"} |

## Scenarios

{"".join(scenarios)}
"""


class RiskContractCliTest(unittest.TestCase):
    def run_command(self, *args: str):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_cli(self, path: Path, *extra: str):
        return self.run_command("validate-spec", str(path), *extra)

    def write_spec(self, directory: Path, content: str) -> Path:
        path = directory / "spec.md"
        path.write_text(content, encoding="utf-8")
        return path

    def test_standard_accepts_zero_adversarial_scenarios(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write_spec(
                Path(raw),
                valid_spec(
                    complexity=2,
                    importance=2,
                    average="2.0",
                    budget="standard",
                    status="skipped-standard",
                    adversarial_count=0,
                ),
            )
            result = self.run_cli(path, "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["valid"])

    def test_v2_accepts_more_than_four_adversarial_scenarios(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write_spec(
                Path(raw),
                valid_spec(
                    complexity=4,
                    importance=4,
                    average="4.0",
                    budget="full",
                    status="complete",
                    adversarial_count=5,
                ),
            )
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_v1_legacy_source_is_accepted(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write_spec(
                Path(raw),
                valid_spec(
                    version=1,
                    complexity=3,
                    importance=3,
                    average="3.0",
                    budget="deep",
                    status="complete",
                    adversarial_count=2,
                ),
            )
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_v1_rejects_v2_pattern_source(self):
        with tempfile.TemporaryDirectory() as raw:
            content = valid_spec(
                version=1,
                complexity=3,
                importance=3,
                average="3.0",
                budget="deep",
                status="complete",
                adversarial_count=1,
            ).replace(
                "adversarial-review (AR-001)",
                "adversarial-review (AR-001; pattern:phased-commit)",
            )
            path = self.write_spec(Path(raw), content)
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("v1 对抗性来源必须引用 AR-nnn", result.stdout)

    def test_v2_rejects_v1_legacy_source(self):
        with tempfile.TemporaryDirectory() as raw:
            content = valid_spec(
                complexity=3,
                importance=3,
                average="3.0",
                budget="deep",
                status="complete",
                adversarial_count=1,
            ).replace(
                "adversarial-review (AR-001; pattern:phased-commit)",
                "adversarial-review (AR-001)",
            )
            path = self.write_spec(Path(raw), content)
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn(
                "v2 对抗性来源必须使用 AR-nnn; pattern:<标签>",
                result.stdout,
            )

    def test_v2_rejects_bare_pattern_source(self):
        with tempfile.TemporaryDirectory() as raw:
            content = valid_spec(
                complexity=3,
                importance=3,
                average="3.0",
                budget="deep",
                status="complete",
                adversarial_count=1,
            ).replace(
                "adversarial-review (AR-001; pattern:phased-commit)",
                "adversarial-review (pattern:phased-commit)",
            )
            path = self.write_spec(Path(raw), content)
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("AR-nnn; pattern:<标签>", result.stdout)

    def test_iteration_5_v1_final_spec_remains_valid(self):
        self.assertTrue(ITERATION_5_FINAL_SPEC.is_file())
        result = self.run_cli(ITERATION_5_FINAL_SPEC, "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])

    def test_single_dimension_five_still_requires_full(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write_spec(
                Path(raw),
                valid_spec(
                    complexity=5,
                    importance=1,
                    average="3.0",
                    budget="deep",
                    status="complete",
                    adversarial_count=1,
                ),
            )
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("review_budget 应为 full", result.stdout)

    def test_unsupported_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            content = valid_spec(
                version=3,
                complexity=3,
                importance=3,
                average="3.0",
                budget="deep",
                status="complete",
                adversarial_count=1,
            )
            path = self.write_spec(Path(raw), content)
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("adversarial_risk_version 必须为 1 或 2", result.stdout)

    def test_pending_status_blocks_handoff(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write_spec(
                Path(raw),
                valid_spec(
                    complexity=3,
                    importance=3,
                    average="3.0",
                    budget="deep",
                    status="pending",
                    adversarial_count=0,
                ),
            )
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("阻断 x-req3", result.stdout)

    def test_yaml_frontmatter_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            content = valid_spec(
                complexity=5,
                importance=1,
                average="3.0",
                budget="full",
                status="complete",
                adversarial_count=1,
            )
            lines = content.splitlines()
            content = "\n".join([line.removeprefix("> ") for line in lines[:7]] + lines[7:])
            path = self.write_spec(Path(raw), content)
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("SPEC_HEADER_FORMAT", result.stdout)

    def test_missing_file_exits_two(self):
        with tempfile.TemporaryDirectory() as raw:
            result = self.run_cli(Path(raw) / "missing.md", "--json")
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["issues"][0]["code"], "IO_ERROR")

    def test_compact_catalog_is_valid(self):
        result = self.run_command(
            "validate-corpus",
            str(CATALOG),
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])

    def test_catalog_rejects_evidence_paths(self):
        with tempfile.TemporaryDirectory() as raw:
            catalog = Path(raw) / "risk-mistakes.md"
            catalog.write_text(
                CATALOG.read_text(encoding="utf-8")
                + "\n- 来源证据：/Volumes/private/report.md\n",
                encoding="utf-8",
            )
            result = self.run_command("validate-corpus", str(catalog))
            self.assertEqual(result.returncode, 1)
            self.assertIn("CATALOG_EVIDENCE_PATH", result.stdout)

    def test_validate_review_aggregates_spec_catalog_and_traceability(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write_spec(
                Path(raw),
                valid_spec(
                    complexity=5,
                    importance=1,
                    average="3.0",
                    budget="full",
                    status="complete",
                    adversarial_count=5,
                ),
            )
            result = self.run_command(
                "validate-review",
                str(path),
                "--catalog",
                str(CATALOG),
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["valid"])

    def test_validate_review_rejects_mismatched_pattern(self):
        with tempfile.TemporaryDirectory() as raw:
            content = valid_spec(
                complexity=5,
                importance=1,
                average="3.0",
                budget="full",
                status="complete",
                adversarial_count=1,
            ).replace(
                "AR-001; pattern:phased-commit",
                "AR-001; pattern:semantic-tail",
            )
            path = self.write_spec(Path(raw), content)
            result = self.run_command(
                "validate-review",
                str(path),
                "--catalog",
                str(CATALOG),
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("SPEC_SOURCE_CATALOG", result.stdout)


class FourRoundContractTest(unittest.TestCase):
    def test_x_spec_handoff_batches_all_three_inputs(self):
        text = X_SPEC_SKILL.read_text(encoding="utf-8")
        self.assertIn(
            "使用一个批量工具调用同时完整读取 "
            "`skills/x-adversarial-risk/SKILL.md`、目标 `spec.md` 和同 skill 目录的 "
            "`references/risk-mistakes.md`",
            text,
        )
        self.assertIn("该调用计为对抗审查第 1 轮", text)
        self.assertIn("每行以 `> ` 开头", text)
        self.assertIn("锁/幂等/跨进程并发/崩溃恢复", text)
        self.assertIn("本地单用户内部 CLI 归入 1", text)
        self.assertNotIn("对抗性审查记录保持 pending", text)

    def test_adversarial_skill_has_one_bounded_execution_path(self):
        text = X_ADVERSARIAL_SKILL.read_text(encoding="utf-8")
        for round_number in range(1, 5):
            self.assertEqual(text.count(f"### 第 {round_number} 轮："), 1)
        self.assertIn("该批量调用是对抗审查唯一读取轮次", text)
        self.assertIn("聚合 issue 仍可触发该修正调用", text)
        self.assertIn("独立重算 complexity、importance", text)
        self.assertIn("validate-review", text)
        self.assertIn("AR-001; pattern:<短标签>", text)
        self.assertNotIn("最多新增", text)

    def test_validator_has_no_total_scenario_cap(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("ADVERSARIAL_SCENARIO_CAPS", text)
        self.assertNotIn("SPEC_ADVERSARIAL_CAP", text)

    def test_catalog_is_compact_traceable_and_publishable(self):
        text = CATALOG.read_text(encoding="utf-8")
        for number, tag in enumerate(CATALOG_TAGS, start=1):
            self.assertEqual(text.count(f"## AR-{number:03d}:"), 1)
            self.assertEqual(text.count(f"- 标签：{tag}"), 1)
        self.assertNotIn("来源证据", text)
        self.assertNotIn("/Volumes/", text)
        self.assertNotIn("skills/x-pipeline-efficiency-workspace/", text)


if __name__ == "__main__":
    unittest.main()
