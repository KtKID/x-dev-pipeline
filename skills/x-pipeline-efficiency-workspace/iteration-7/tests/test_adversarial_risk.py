import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "x-adversarial-risk" / "scripts"
SCRIPT = SCRIPTS / "risk_contract.py"
X_ADVERSARIAL_SKILL = ROOT / "skills" / "x-adversarial-risk" / "SKILL.md"
X_SPEC_SKILL = ROOT / "skills" / "x-spec3" / "SKILL.md"
X_SPEC_TEMPLATE = ROOT / "skills" / "x-spec3" / "templates" / "spec.md"
X_REQ_SKILL = ROOT / "skills" / "x-req3" / "SKILL.md"
README = ROOT / "skills" / "README.md"
CATALOG = (
    ROOT
    / "skills"
    / "x-adversarial-risk"
    / "references"
    / "risk-mistakes.md"
)

sys.path.insert(0, str(SCRIPTS))
from risk_contract import parse_catalog  # noqa: E402


CATALOG_IDS = tuple(f"A-risk-{number:03d}" for number in range(1, 6))


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
    version: int = 3,
    complexity: int,
    importance: int,
    average: str,
    budget: str,
    status: str,
    adversarial_count: int,
    legacy_v2: bool = False,
) -> str:
    scenarios = [scenario(1, "initial-spec")]
    for offset in range(adversarial_count):
        if version == 1:
            source = f"adversarial-review (AR-{offset + 1:03d})"
        elif legacy_v2:
            source = (
                f"adversarial-review (AR-{offset + 1:03d}; "
                f"pattern:legacy-pattern-{offset + 1})"
            )
        elif version == 2:
            source = f"adversarial-review ({CATALOG_IDS[offset]})"
        else:
            source = f"adversarial-review (rag:{CATALOG_IDS[offset]})"
        scenarios.append(scenario(offset + 2, source))

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

| Review | 预算 | 召回 ID | 复用 Scenario | 新增 Scenario | CLI |
|---|---|---|---|---|---|
| ARV-1 | {budget} | {"无" if adversarial_count == 0 else CATALOG_IDS[0]} | 无 | {"无" if adversarial_count == 0 else "SC_02"} | success |

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

    def test_v2_accepts_namespaced_sources(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write_spec(
                Path(raw),
                valid_spec(
                    version=2,
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

    def test_v2_accepts_historical_ar_pattern_source(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write_spec(
                Path(raw),
                valid_spec(
                    version=2,
                    complexity=3,
                    importance=3,
                    average="3.0",
                    budget="deep",
                    status="complete",
                    adversarial_count=2,
                    legacy_v2=True,
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

    def test_v2_rejects_bare_legacy_source(self):
        with tempfile.TemporaryDirectory() as raw:
            content = valid_spec(
                version=2,
                complexity=3,
                importance=3,
                average="3.0",
                budget="deep",
                status="complete",
                adversarial_count=1,
            ).replace("A-risk-001", "AR-001")
            path = self.write_spec(Path(raw), content)
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("命名空间化风险 ID", result.stdout)

    def test_v3_requires_explicit_rag_source(self):
        with tempfile.TemporaryDirectory() as raw:
            content = valid_spec(
                complexity=3,
                importance=3,
                average="3.0",
                budget="deep",
                status="complete",
                adversarial_count=1,
            ).replace("rag:A-risk-001", "A-risk-001")
            path = self.write_spec(Path(raw), content)
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("v3 RAG 来源", result.stdout)

    def test_single_dimension_five_requires_full(self):
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

    def test_missing_file_exits_two(self):
        with tempfile.TemporaryDirectory() as raw:
            result = self.run_cli(Path(raw) / "missing.md", "--json")
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["issues"][0]["code"], "IO_ERROR")

    def test_validate_review_accepts_namespaced_traceability(self):
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

    def test_validate_review_rejects_unknown_namespaced_source(self):
        with tempfile.TemporaryDirectory() as raw:
            content = valid_spec(
                complexity=3,
                importance=3,
                average="3.0",
                budget="deep",
                status="complete",
                adversarial_count=1,
            ).replace("A-risk-001", "A-risk-999")
            path = self.write_spec(Path(raw), content)
            result = self.run_command(
                "validate-review",
                str(path),
                "--catalog",
                str(CATALOG),
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("SPEC_SOURCE_CATALOG", result.stdout)


class CatalogParserTest(unittest.TestCase):
    def test_minimal_catalog_is_valid_and_keeps_file_order(self):
        text = CATALOG.read_text(encoding="utf-8")
        cards, issues = parse_catalog(text)
        self.assertEqual(issues, [])
        self.assertEqual([card.id for card in cards], list(CATALOG_IDS))
        self.assertEqual(
            set(cards[0].__dict__),
            {"id", "keywords", "risk"},
        )

    def test_duplicate_id_is_rejected(self):
        text = """# demo

## A-risk-001

关键词：日志
Risk：风险一

## A-risk-001

关键词：快照
Risk：风险二
"""
        _, issues = parse_catalog(text)
        self.assertIn("CATALOG_DUPLICATE_ID", {issue.code for issue in issues})

    def test_missing_keywords_is_rejected(self):
        _, issues = parse_catalog("## A-risk-001\n\nRisk：具体风险\n")
        self.assertIn("CATALOG_MISSING_FIELD", {issue.code for issue in issues})

    def test_missing_risk_is_rejected(self):
        _, issues = parse_catalog("## A-risk-001\n\n关键词：日志恢复\n")
        self.assertIn("CATALOG_MISSING_FIELD", {issue.code for issue in issues})

    def test_extra_field_is_rejected(self):
        text = "## A-risk-001\n\n关键词：日志恢复\nRisk：具体风险\n标签：extra\n"
        _, issues = parse_catalog(text)
        self.assertIn("CATALOG_UNKNOWN_CONTENT", {issue.code for issue in issues})


class SkillIntegrationContractTest(unittest.TestCase):
    def test_adversarial_skill_uses_retrieval_before_analysis(self):
        text = X_ADVERSARIAL_SKILL.read_text(encoding="utf-8")
        self.assertIn("x-dev-rag-call", text)
        self.assertIn("rag_retrieve.py", text)
        self.assertIn("功能关键词 + Risk", text)
        self.assertIn("召回 ID", text)
        self.assertIn("rag:A-risk-001", text)
        self.assertIn("风险来源", text)
        self.assertNotIn("逐张检查五类短示例卡", text)
        self.assertNotIn("与本 skill 同目录的 `references/risk-mistakes.md`", text)

    def test_x_spec_handoff_uses_retrieval_flow(self):
        text = X_SPEC_SKILL.read_text(encoding="utf-8")
        template = X_SPEC_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("向量召回", text)
        self.assertIn("x-dev-rag-call", text)
        self.assertIn("rag:<risk-id>", text)
        self.assertIn("> adversarial_risk_version: 3", template)
        self.assertIn("| Review | 预算 | 风险来源 |", template)
        self.assertNotIn(
            "同时完整读取 `skills/x-adversarial-risk/SKILL.md`、目标 `spec.md`",
            text,
        )

    def test_x_req_handoff_uses_current_five_round_contract(self):
        text = X_REQ_SKILL.read_text(encoding="utf-8")
        self.assertIn("当前 x-adversarial-risk 定义的五轮契约", text)
        self.assertIn("1`、`2` 或 `3", text)
        self.assertIn("adversarial-review (rag:<risk-id>)", text)
        self.assertNotIn("重新执行四轮契约", text)

    def test_iteration_readme_describes_local_model_boundary(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("Iteration 7", text)
        self.assertIn("local_files_only", text)
        self.assertIn("真实模型 Smoke", text)


if __name__ == "__main__":
    unittest.main()
