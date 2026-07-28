import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "x-adversarial-risk" / "scripts" / "risk_contract.py"
DEFAULT_CORPUS = (
    ROOT
    / "skills"
    / "x-adversarial-risk"
    / "references"
    / "risk-catalog.md"
)
RAG_FIXTURE = (
    ROOT
    / "skills"
    / "x-dev-rag-call"
    / "evals"
    / "fixtures"
    / "risk-catalog.md"
)


def valid_spec(
    *,
    complexity: int = 4,
    importance: int = 4,
    average: str = "4.0",
    budget: str = "full",
    status: str = "complete",
    source: str = "initial-spec",
) -> str:
    return f"""> spec_version: 3
> adversarial_risk_version: 3
> complexity: {complexity}
> importance: {importance}
> risk_average: {average}
> review_budget: {budget}
> adversarial_review: {status}

# demo

## 风险评分依据

- 复杂度：包含状态恢复。
- 重要性：影响全部用户数据。

## 对抗性审查记录

| Review | 预算 | 匹配 issue | 被推翻假设 | 新增 Scenario |
|---|---|---|---|---|
| ARV-1 | {budget} | AR-001 | 多文件替换具有崩溃窗口 | SC_01 |

## Scenarios

### Scenario SC_01: 恢复一致状态

- **GIVEN** 新 snapshot 与旧 journal 同时存在
- **WHEN** 服务重启
- **THEN** 系统恢复一致状态
- 测试层：unit
- 依据：用户任务
- 来源：{source}
"""


def valid_corpus() -> str:
    return """# 风险错题集

## AR-001

关键词：持久化替换、崩溃恢复
Risk：分阶段替换中途崩溃可能留下部分完成状态。
"""


class RiskContractCliTest(unittest.TestCase):
    def run_cli(self, command: str, path: Path, *extra: str):
        return subprocess.run(
            [sys.executable, str(SCRIPT), command, str(path), *extra],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def write(self, directory: Path, name: str, content: str) -> Path:
        path = directory / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_valid_spec_json_is_stable_and_read_only(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write(Path(raw), "spec.md", valid_spec())
            before = path.read_bytes()
            first = self.run_cli("validate-spec", path, "--json")
            second = self.run_cli("validate-spec", path, "--json")

            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(path.read_bytes(), before)
            payload = json.loads(first.stdout)
            self.assertEqual(
                list(payload),
                ["command", "target", "valid", "issues"],
            )
            self.assertTrue(payload["valid"])
            self.assertEqual(payload["issues"], [])

    def test_single_dimension_five_forces_full_budget(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write(
                Path(raw),
                "spec.md",
                valid_spec(
                    complexity=5,
                    importance=1,
                    average="3.0",
                    budget="deep",
                ),
            )
            result = self.run_cli("validate-spec", path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("review_budget 应为 full", result.stdout)

    def test_pending_status_blocks_contract(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write(
                Path(raw),
                "spec.md",
                valid_spec(status="pending"),
            )
            result = self.run_cli("validate-spec", path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("阻断 x-req", result.stdout)

    def test_scenario_source_is_required(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write(
                Path(raw),
                "spec.md",
                valid_spec().replace("- 来源：initial-spec\n", ""),
            )
            result = self.run_cli("validate-spec", path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("SC_01 缺少来源字段", result.stdout)

    def test_adversarial_source_requires_rag_or_assumption(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write(
                Path(raw),
                "spec.md",
                valid_spec(source="adversarial-review (rag:AR-001)"),
            )
            result = self.run_cli("validate-spec", path)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_valid_corpus_passes(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write(Path(raw), "risk-mistakes.md", valid_corpus())
            result = self.run_cli("validate-corpus", path, "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["valid"])

    def test_rich_field_gate_rejects_legacy_two_field_card(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write(Path(raw), "risk-mistakes.md", valid_corpus())
            result = self.run_cli(
                "validate-corpus",
                path,
                "--require-rich-fields",
                "--json",
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["valid"])
            self.assertEqual(
                {issue["message"] for issue in payload["issues"]},
                {
                    "AR-001 缺少非空字段：场景",
                    "AR-001 缺少非空字段：错误实现",
                    "AR-001 缺少非空字段：正确实现",
                    "AR-001 缺少非空字段：可观察差异",
                    "AR-001 缺少非空字段：分类",
                },
            )

    def test_default_and_eval_corpora_have_expected_rich_cards(self):
        expected_counts = (
            (DEFAULT_CORPUS, 6),
            (RAG_FIXTURE, 5),
        )
        for path, expected_count in expected_counts:
            with self.subTest(path=path, expected_count=expected_count):
                result = self.run_cli(
                    "validate-corpus",
                    path,
                    "--require-rich-fields",
                    "--json",
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    result.stdout + result.stderr,
                )
                self.assertTrue(json.loads(result.stdout)["valid"])
                self.assertEqual(
                    path.read_text(encoding="utf-8").count("\n## AR-"),
                    expected_count,
                )

    def test_corpus_rejects_duplicate_id_and_missing_field(self):
        with tempfile.TemporaryDirectory() as raw:
            broken = valid_corpus().replace("关键词：持久化替换、崩溃恢复\n", "")
            broken += valid_corpus().replace("# 风险错题集\n\n", "")
            path = self.write(Path(raw), "risk-mistakes.md", broken)
            result = self.run_cli("validate-corpus", path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("错题 ID 重复：AR-001", result.stdout)
            self.assertIn("AR-001 缺少非空字段：关键词", result.stdout)

    def test_namespaced_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write(
                Path(raw),
                "risk-mistakes.md",
                valid_corpus().replace("AR-001", "A-risk-001"),
            )
            result = self.run_cli("validate-corpus", path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("错题 ID 必须匹配 AR-NNN", result.stdout)

    def test_missing_file_exits_two(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "missing.md"
            result = self.run_cli("validate-spec", path, "--json")
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["valid"])
            self.assertEqual(payload["issues"][0]["code"], "IO_ERROR")


if __name__ == "__main__":
    unittest.main()
