#!/usr/bin/env python3
"""iteration-7 spec 独立校验引擎测试。"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [
    str(ROOT / "skills" / "x-dev" / "scripts"),
    str(ROOT / "skills" / "x-qa-gate" / "scripts"),
    str(ROOT / "skills" / "x-verify" / "scripts"),
    str(ROOT / "skills" / "x-req" / "scripts"),
    str(ROOT / "skills" / "x-spec" / "scripts"),
]

import req  # noqa: E402
import spec as spec_engine  # noqa: E402
import validator  # noqa: E402
import xdev  # noqa: E402


def standard_spec() -> str:
    return (
        "> spec_version: 3\n"
        "> adversarial_risk_version: 3\n"
        "> complexity: 2\n"
        "> importance: 2\n"
        "> risk_average: 2.0\n"
        "> review_budget: standard\n"
        "> adversarial_review: skipped-standard\n\n"
        "# demo\n\n"
        "## 任务目标\n\n- 返回确定性结果。\n\n"
        "## 非目标\n\n- 不访问网络。\n\n"
        "## 风险评分依据\n\n"
        "- 复杂度：单模块确定性解析。\n"
        "- 重要性：局部工具链。\n"
        "- 预算升级：无。\n\n"
        "## 影响边界与不变量\n\n"
        "| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |\n"
        "|---|---|---|---|---|---|\n"
        "| Resolver | 目标 | 新增解析 | 输入变更 → 状态污染 → 调用方错误 | 输入只读 | J1 |\n\n"
        "## 判断依据\n\n"
        "| J-ID | 判断 | 来源 | 证据或推断 | 状态 |\n"
        "|---|---|---|---|---|\n"
        "| J1 | 保持输入只读 | 用户任务 | 明确要求 | 已确认 |\n\n"
        "## 建模覆盖声明\n\n"
        "| 维度 | 覆盖位置或具体不适用理由 |\n"
        "|---|---|\n"
        "| 数据流 | SC_01 |\n"
        "| 状态 | 不适用：无跨调用状态 |\n"
        "| 时序 | 不适用：同步调用 |\n"
        "| 资源 | 不适用：无外部资源 |\n"
        "| 不变量 | 影响边界与不变量 |\n"
        "| 故障 | SC_01 |\n\n"
        "## 验收清单\n\n"
        "### 单元测试\n\n- [ ] 验证输入只读。\n\n"
        "### Smoke 测试\n\n- [ ] 调用公开入口。\n\n"
        "### E2E 测试\n\n"
        "- 决策：省略\n"
        "- 依据：单进程纯函数。\n\n"
        "## 测试驱动开发\n\n1. SC_01 先写失败测试。\n\n"
        "## 对抗性审查记录（按预算填写）\n\n"
        "| Review | 预算 | 风险来源 | 查询 | 召回 ID | 复用 Scenario | 新增 Scenario | CLI |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| ARV-1 | standard | no-corpus | 无 | 无 | 无 | 无 | skipped:no-corpus |\n\n"
        "## Scenarios 模板\n\n"
        "### Scenario SC_01: 输入保持只读\n\n"
        "- **GIVEN** 一个可变输入对象\n"
        "- **WHEN** 调用解析器\n"
        "- **THEN** 输入对象保持原值\n"
        "- 测试层：unit\n"
        "- 依据：J1\n"
        "- 来源：initial-spec\n"
    )


def full_top5_spec() -> str:
    text = standard_spec()
    text = text.replace(
        "> complexity: 2\n"
        "> importance: 2\n"
        "> risk_average: 2.0\n"
        "> review_budget: standard\n"
        "> adversarial_review: skipped-standard",
        "> complexity: 4\n"
        "> importance: 4\n"
        "> risk_average: 4.0\n"
        "> review_budget: full\n"
        "> adversarial_review: complete",
    )
    text = text.replace(
        "| ARV-1 | standard | no-corpus | 无 | 无 | 无 | 无 | skipped:no-corpus |",
        "| ARV-1 | full | RAG:AR-001；assumption:nested-mutation | "
        "resolver immutable input | "
        "AR-001, AR-002, AR-003, AR-004, AR-005 | "
        "SC_01 | SC_02 | exit=0; matches=5 |",
    )
    return text + (
        "\n### Scenario SC_02: 嵌套输入保持只读\n\n"
        "- **GIVEN** 一个嵌套可变输入对象\n"
        "- **WHEN** 调用解析器\n"
        "- **THEN** 所有嵌套成员保持原值\n"
        "- 测试层：unit\n"
        "- 依据：J1\n"
        "- 来源：adversarial-review (rag:AR-001)\n"
    )


def full_no_corpus_spec() -> str:
    return full_top5_spec().replace(
        "| ARV-1 | full | RAG:AR-001；assumption:nested-mutation | "
        "resolver immutable input | "
        "AR-001, AR-002, AR-003, AR-004, AR-005 | "
        "SC_01 | SC_02 | exit=0; matches=5 |",
        "| ARV-1 | full | assumption:nested-mutation | 无 RAG 经验集 | "
        "无 | SC_01 | SC_02 | skipped:no-corpus |",
    ).replace(
        "adversarial-review (rag:AR-001)",
        "adversarial-review (assumption:nested-mutation)",
    )


def standard_recall_failure_spec() -> str:
    return standard_spec().replace(
        "| ARV-1 | standard | no-corpus | 无 | 无 | 无 | 无 | skipped:no-corpus |",
        "| ARV-1 | standard | 无 | resolver immutable input | 无 | 无 | 无 | "
        "exit=7; matches=0; error=MODEL_LOAD; message=failed |",
    )


class SpecEngineTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def write_spec(self, text: str) -> Path:
        spec_dir = self.root / "docs" / "spec" / "demo"
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "spec.md").write_text(text, encoding="utf-8")
        return spec_dir

    def messages(self, spec_dir: Path, **kwargs) -> str:
        return " ".join(
            issue["msg"] for issue in spec_engine.validate_issues(spec_dir, **kwargs)
        )


class TestCurrentSpec3Contract(SpecEngineTestCase):
    def test_standard_no_corpus_contract_is_valid_through_all_entrypoints(self):
        spec_dir = self.write_spec(standard_spec())
        self.assertEqual(spec_engine.validate_issues(spec_dir), [])
        self.assertEqual(req.spec_contract_issues(spec_dir), [])
        self.assertEqual(validator.detect_type(spec_dir), "spec")
        self.assertEqual(validator.validate_pkg(spec_dir, include_legacy=False)["issues"], [])

    def test_standalone_cli_returns_machine_readable_result(self):
        spec_dir = self.write_spec(standard_spec())
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = spec_engine.main(["validate", str(spec_dir), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["type"], "spec")
        self.assertEqual(payload["issues"], [])

    def test_completed_full_top5_and_rag_source_are_valid(self):
        spec_dir = self.write_spec(full_top5_spec())
        self.assertEqual(spec_engine.validate_issues(spec_dir), [])
        scenarios = spec_engine.spec_scenarios(spec_dir / "spec.md")
        self.assertEqual([item["id"] for item in scenarios], ["SC_01", "SC_02"])
        self.assertEqual(scenarios[1]["source"], "adversarial-review (rag:AR-001)")

    def test_completed_full_no_corpus_assumption_path_is_valid(self):
        spec_dir = self.write_spec(full_no_corpus_spec())
        self.assertEqual(spec_engine.validate_issues(spec_dir), [])

    def test_standard_recall_failure_records_error_and_still_passes(self):
        spec_dir = self.write_spec(standard_recall_failure_spec())
        self.assertEqual(spec_engine.validate_issues(spec_dir), [])

    def test_standard_recall_failure_requires_error_and_message(self):
        for suffix in ("", "; error=; message="):
            with self.subTest(suffix=suffix):
                text = standard_recall_failure_spec().replace(
                    "; error=MODEL_LOAD; message=failed", suffix,
                )
                messages = self.messages(self.write_spec(text))
                self.assertIn("非空 error=<值>", messages)
                self.assertIn("非空 message=<值>", messages)

    def test_metadata_average_budget_and_version_are_recomputed(self):
        text = standard_spec().replace(
            "> adversarial_risk_version: 3", "> adversarial_risk_version: 2",
        ).replace("> risk_average: 2.0", "> risk_average: 3.0").replace(
            "> review_budget: standard", "> review_budget: full",
        )
        messages = self.messages(self.write_spec(text))
        self.assertIn("adversarial_risk_version 为 3", messages)
        self.assertIn("risk_average 应为 2.0", messages)
        self.assertIn("review_budget 应为 standard", messages)

    def test_pending_is_structurally_valid_but_blocks_req_readiness(self):
        text = full_top5_spec().replace(
            "> adversarial_review: complete", "> adversarial_review: pending",
        )
        spec_dir = self.write_spec(text)
        self.assertIn("阻断 x-req", self.messages(spec_dir))
        structural = spec_engine.validate_issues(spec_dir, require_ready=False)
        self.assertNotIn("阻断 x-req", " ".join(item["msg"] for item in structural))

    def test_tables_model_and_e2e_decision_are_checked(self):
        text = standard_spec().replace(
            "| Resolver | 目标 | 新增解析 | 输入变更 → 状态污染 → 调用方错误 | 输入只读 | J1 |",
            "| Resolver | 目标 | 新增解析 |  | 输入只读 | J1 |",
        ).replace("| 故障 | SC_01 |\n", "").replace("- 决策：省略\n", "")
        messages = self.messages(self.write_spec(text))
        self.assertIn("主要风险为空", messages)
        self.assertIn("建模覆盖声明缺少：故障", messages)
        self.assertIn("E2E 测试必须明确写", messages)

    def test_risk_basis_and_duplicate_scenario_fields_are_checked(self):
        text = standard_spec().replace(
            "- 预算升级：无。\n", "",
        ).replace(
            "- **WHEN** 调用解析器\n",
            "- **WHEN** 调用解析器\n- **WHEN** 再次调用解析器\n",
        )
        messages = self.messages(self.write_spec(text))
        self.assertIn("风险评分依据缺少非空「预算升级」项", messages)
        self.assertIn("Scenario「输入保持只读」重复字段：WHEN", messages)

    def test_scenario_source_and_top5_record_are_cross_checked(self):
        text = full_top5_spec().replace(
            "AR-001, AR-002, AR-003, AR-004, AR-005",
            "AR-002, AR-003, AR-004, AR-005",
        )
        messages = self.messages(self.write_spec(text))
        self.assertIn("CLI matches 必须等于召回 ID 数量", messages)
        self.assertIn("引用的风险 ID 未进入 ARV-n 召回记录：AR-001", messages)

    def test_top5_accepts_one_to_five_matches(self):
        text = full_top5_spec().replace(
            "RAG:AR-001", "RAG:AR-002",
        ).replace(
            "adversarial-review (rag:AR-001)",
            "adversarial-review (rag:AR-002)",
        ).replace(
            "AR-001, AR-002, AR-003, AR-004, AR-005",
            "AR-002, AR-003, AR-004, AR-005",
        ).replace(
            "exit=0; matches=5", "exit=0; matches=4",
        )
        spec_dir = self.write_spec(text)
        self.assertEqual(spec_engine.validate_issues(spec_dir, require_ready=True), [])

    def test_standard_path_rejects_adversarial_scenario_expansion(self):
        text = standard_spec().replace(
            "- 来源：initial-spec",
            "- 来源：adversarial-review (assumption:mutation)",
        )
        messages = self.messages(self.write_spec(text))
        self.assertIn("standard 路径不允许扩张对抗性 Scenario", messages)

    def test_complete_review_rejects_failed_rag(self):
        text = full_top5_spec().replace(
            "exit=0; matches=5", "exit=7; matches=0",
        )
        messages = self.messages(self.write_spec(text))
        self.assertIn("complete 状态要求 Top5 召回成功", messages)

    def test_full_review_requires_structured_independent_assumption(self):
        text = full_top5_spec().replace(
            "assumption:nested-mutation", "garbage-assumption:",
        )
        messages = self.messages(self.write_spec(text))
        self.assertIn("风险来源必须由 RAG:AR-NNN", messages)
        self.assertIn("full 预算必须记录一个独立 assumption", messages)

    def test_no_corpus_review_rejects_rag_claims_and_rag_scenario(self):
        text = full_top5_spec().replace(
            "exit=0; matches=5", "skipped:no-corpus",
        )
        messages = self.messages(self.write_spec(text))
        self.assertIn("风险来源不得包含 RAG ID", messages)
        self.assertIn("召回 ID 必须为 无", messages)
        self.assertIn("引用的风险 ID 未进入 ARV-n 召回记录", messages)

    def test_scenario_assumption_source_rejects_whitespace_description(self):
        text = full_top5_spec().replace(
            "adversarial-review (rag:AR-001)",
            "adversarial-review (assumption:   )",
        )
        messages = self.messages(self.write_spec(text))
        self.assertIn("assumption 来源说明不能为空", messages)

    def test_fenced_scenario_example_does_not_satisfy_contract(self):
        text = standard_spec().replace(
            "## Scenarios 模板\n", "```md\n## Scenarios 模板\n",
        ) + "```\n"
        messages = self.messages(self.write_spec(text))
        self.assertIn("缺少二级节「Scenarios」", messages)

    def test_spec_root_rejects_sidecar_documents(self):
        spec_dir = self.write_spec(standard_spec())
        (spec_dir / "notes.md").write_text("# 旁路规格\n", encoding="utf-8")
        self.assertIn("单文件包根目录只允许 spec.md 和后续 tasks/", self.messages(spec_dir))

    def test_unfilled_template_placeholders_are_rejected(self):
        text = standard_spec().replace(
            "- 返回确定性结果。", "- <可观察、可验证的系统结果>",
        ).replace(
            "- **THEN** 输入对象保持原值", "- **THEN** <可观察结果>",
        )
        messages = self.messages(self.write_spec(text))
        self.assertIn("删除模板注释或占位符：<可观察、可验证的系统结果>", messages)
        self.assertIn("删除模板注释或占位符：<可观察结果>", messages)


if __name__ == "__main__":
    unittest.main()
