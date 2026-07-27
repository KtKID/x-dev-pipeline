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
    / "tests"
    / "fixtures"
    / "risk-catalog.md"
)
PROMPT = ROOT / "skills" / "x-adversarial-risk" / "agents" / "prompt.yaml"
LEGACY_PROMPT = ROOT / "skills" / "x-adversarial-risk" / "agents" / "openai.yaml"

sys.path.insert(0, str(SCRIPTS))
from risk_contract import parse_catalog  # noqa: E402


CATALOG_IDS = tuple(f"AR-{number:03d}" for number in range(1, 6))


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
) -> str:
    scenarios = [scenario(1, "initial-spec")]
    for offset in range(adversarial_count):
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

    def test_retired_versions_are_rejected(self):
        for version in (1, 2):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as raw:
                path = self.write_spec(
                    Path(raw),
                    valid_spec(
                        version=version,
                        complexity=3,
                        importance=3,
                        average="3.0",
                        budget="deep",
                        status="complete",
                        adversarial_count=1,
                    ),
                )
                result = self.run_cli(path)
                self.assertEqual(result.returncode, 1)
                self.assertIn("adversarial_risk_version 必须为 3", result.stdout)

    def test_namespaced_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            content = valid_spec(
                complexity=3,
                importance=3,
                average="3.0",
                budget="deep",
                status="complete",
                adversarial_count=1,
            ).replace("AR-001", "A-risk-001")
            path = self.write_spec(Path(raw), content)
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("adversarial-review (rag:AR-NNN)", result.stdout)

    def test_v3_requires_explicit_rag_source(self):
        with tempfile.TemporaryDirectory() as raw:
            content = valid_spec(
                complexity=3,
                importance=3,
                average="3.0",
                budget="deep",
                status="complete",
                adversarial_count=1,
            ).replace("rag:AR-001", "AR-001")
            path = self.write_spec(Path(raw), content)
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("RAG 来源必须使用", result.stdout)

    def test_v3_accepts_score_only_assumption_source(self):
        with tempfile.TemporaryDirectory() as raw:
            content = valid_spec(
                complexity=3,
                importance=3,
                average="3.0",
                budget="deep",
                status="complete",
                adversarial_count=1,
            ).replace(
                "rag:AR-001",
                "assumption:score-only-highest-risk",
            )
            path = self.write_spec(Path(raw), content)
            result = self.run_cli(path, "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["valid"])

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

    def test_validate_review_accepts_ar_traceability(self):
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

    def test_validate_review_rejects_unknown_ar_source(self):
        with tempfile.TemporaryDirectory() as raw:
            content = valid_spec(
                complexity=3,
                importance=3,
                average="3.0",
                budget="deep",
                status="complete",
                adversarial_count=1,
            ).replace("AR-001", "AR-999")
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

## AR-001

关键词：日志
Risk：风险一

## AR-001

关键词：快照
Risk：风险二
"""
        _, issues = parse_catalog(text)
        self.assertIn("CATALOG_DUPLICATE_ID", {issue.code for issue in issues})

    def test_catalog_does_not_require_a_fixed_first_id(self):
        text = "## AR-007\n\n关键词：日志恢复\nRisk：具体风险\n"
        cards, issues = parse_catalog(text)
        self.assertEqual(issues, [])
        self.assertEqual([card.id for card in cards], ["AR-007"])

    def test_namespaced_catalog_id_is_rejected(self):
        text = "## A-risk-001\n\n关键词：日志恢复\nRisk：具体风险\n"
        _, issues = parse_catalog(text)
        self.assertIn("CATALOG_ID", {issue.code for issue in issues})

    def test_missing_keywords_is_rejected(self):
        _, issues = parse_catalog("## AR-001\n\nRisk：具体风险\n")
        self.assertIn("CATALOG_MISSING_FIELD", {issue.code for issue in issues})

    def test_missing_risk_is_rejected(self):
        _, issues = parse_catalog("## AR-001\n\n关键词：日志恢复\n")
        self.assertIn("CATALOG_MISSING_FIELD", {issue.code for issue in issues})

    def test_extra_field_is_rejected(self):
        text = "## AR-001\n\n关键词：日志恢复\nRisk：具体风险\n标签：extra\n"
        _, issues = parse_catalog(text)
        self.assertIn("CATALOG_UNKNOWN_CONTENT", {issue.code for issue in issues})


class SkillIntegrationContractTest(unittest.TestCase):
    def test_adversarial_skill_uses_retrieval_before_analysis(self):
        text = X_ADVERSARIAL_SKILL.read_text(encoding="utf-8")
        self.assertIn("x-dev-rag-call", text)
        self.assertIn("rag_retrieve.py", text)
        self.assertIn("功能关键词 + Risk", text)
        self.assertIn("--top-n 5", text)
        self.assertIn("默认 Top5", text)
        self.assertIn("matches=<1..5>", text)
        self.assertIn("召回 ID", text)
        self.assertIn("rag:AR-001", text)
        self.assertIn("风险来源", text)
        self.assertIn("调用方提供的风险语料路径", text)
        self.assertIn("停下当前工作并向用户询问", text)
        self.assertIn("请确认跳过 RAG 召回", text)
        self.assertIn("`deep`：从 Spec 选择最高风险不变量，执行 1 个", text)
        self.assertIn("`full`：从 Spec 选择两个不同故障轴，执行最多 2 个", text)
        self.assertIn("validate-spec", text)
        self.assertIn("skipped:no-corpus", text)
        self.assertNotIn("references/", text)
        self.assertNotIn("逐张检查五类短示例卡", text)

    def test_adversarial_prompt_uses_chinese_prompt_yaml(self):
        text = PROMPT.read_text(encoding="utf-8")
        self.assertTrue(PROMPT.is_file())
        self.assertFalse(LEGACY_PROMPT.exists())
        self.assertIn('display_name: "Spec 对抗性风险审查"', text)
        self.assertIn('short_description: "执行一次有边界的 Spec 对抗性审查"', text)
        self.assertIn("使用 $x-adversarial-risk", text)

    def test_x_spec_handoff_uses_retrieval_flow(self):
        text = X_SPEC_SKILL.read_text(encoding="utf-8")
        template = X_SPEC_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("向量召回", text)
        self.assertIn("x-dev-rag-call", text)
        self.assertIn("Top5 向量召回", text)
        self.assertIn("所有预算都执行一次 Top5", text)
        self.assertIn("停下当前工作并向用户询问", text)
        self.assertIn("请确认跳过 RAG 召回", text)
        self.assertIn("`deep` 交给 x-adversarial-risk 执行 1 个", text)
        self.assertIn("`full` 交给 x-adversarial-risk 执行最多 2 个", text)
        self.assertIn("skipped:no-corpus", text)
        self.assertIn("standard` 只记录召回与适用性结果", text)
        self.assertIn("保持 Scenario 集合不扩张", text)
        self.assertIn("rag:AR-NNN", text)
        self.assertIn("> adversarial_risk_version: 3", template)
        self.assertIn("\n## 对抗性审查记录\n", template)
        self.assertNotIn("## 对抗性审查记录（", template)
        self.assertIn("| Review | 预算 | 风险来源 |", template)
        self.assertNotIn(
            "同时完整读取 `skills/x-adversarial-risk/SKILL.md`、目标 `spec.md`",
            text,
        )

    def test_x_req_handoff_uses_current_five_round_contract(self):
        text = X_REQ_SKILL.read_text(encoding="utf-8")
        self.assertIn("当前 x-adversarial-risk 定义的五轮契约", text)
        self.assertIn("adversarial_risk_version: 3", text)
        self.assertIn("adversarial-review (rag:AR-NNN)", text)
        self.assertNotIn("存量 spec3 沿用原门禁", text)
        self.assertNotIn("spec2 包继续使用", text)
        self.assertNotIn("重新执行四轮契约", text)

    def test_iteration_readme_describes_local_model_boundary(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("Iteration 7", text)
        self.assertIn("local_files_only", text)
        self.assertIn("真实模型 Smoke", text)


if __name__ == "__main__":
    unittest.main()
