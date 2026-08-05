package spec

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// standardSpec 与 test/test_spec_engine.py 的 standard_spec() 逐字一致。
func standardSpec() string {
	return "> spec_version: 3\n" +
		"> adversarial_risk_version: 3\n" +
		"> complexity: 2\n" +
		"> importance: 2\n" +
		"> risk_average: 2.0\n" +
		"> review_budget: standard\n" +
		"> adversarial_review: skipped-standard\n\n" +
		"# demo\n\n" +
		"## 任务目标\n\n- 返回确定性结果。\n\n" +
		"## 非目标\n\n- 不访问网络。\n\n" +
		"## 风险评分依据\n\n" +
		"- 复杂度：单模块确定性解析。\n" +
		"- 重要性：局部工具链。\n" +
		"- 预算升级：无。\n\n" +
		"## 影响边界与不变量\n\n" +
		"| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |\n" +
		"|---|---|---|---|---|---|\n" +
		"| Resolver | 目标 | 新增解析 | 输入变更 → 状态污染 → 调用方错误 | 输入只读 | J1 |\n\n" +
		"## 判断依据\n\n" +
		"| J-ID | 判断 | 来源 | 证据或推断 | 状态 |\n" +
		"|---|---|---|---|---|\n" +
		"| J1 | 保持输入只读 | 用户任务 | 明确要求 | 已确认 |\n\n" +
		"## 建模覆盖声明\n\n" +
		"| 维度 | 覆盖位置或具体不适用理由 |\n" +
		"|---|---|\n" +
		"| 数据流 | SC_01 |\n" +
		"| 状态 | 不适用：无跨调用状态 |\n" +
		"| 时序 | 不适用：同步调用 |\n" +
		"| 资源 | 不适用：无外部资源 |\n" +
		"| 不变量 | 影响边界与不变量 |\n" +
		"| 故障 | SC_01 |\n\n" +
		"## 验收清单\n\n" +
		"### 单元测试\n\n- [ ] 验证输入只读。\n\n" +
		"### Smoke 测试\n\n- [ ] 调用公开入口。\n\n" +
		"### E2E 测试\n\n" +
		"- 决策：省略\n" +
		"- 依据：单进程纯函数。\n\n" +
		"## 测试驱动开发\n\n1. SC_01 先写失败测试。\n\n" +
		"## 对抗性审查记录（按预算填写）\n\n" +
		"| Review | 预算 | 风险来源 | 查询 | 召回 ID | 复用 Scenario | 新增 Scenario | CLI |\n" +
		"|---|---|---|---|---|---|---|---|\n" +
		"| ARV-1 | standard | no-corpus | 无 | 无 | 无 | 无 | skipped:no-corpus |\n\n" +
		"## Scenarios 模板\n\n" +
		"### Scenario SC_01: 输入保持只读\n\n" +
		"- **GIVEN** 一个可变输入对象\n" +
		"- **WHEN** 调用解析器\n" +
		"- **THEN** 输入对象保持原值\n" +
		"- 测试层：unit\n" +
		"- 依据：J1\n" +
		"- 来源：initial-spec\n"
}

// writeSpec 把 spec 文本写入临时目录，返回 spec 目录路径。
func writeSpec(t *testing.T, text string) string {
	t.Helper()
	root := t.TempDir()
	specDir := filepath.Join(root, "docs", "spec", "demo")
	if err := os.MkdirAll(specDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(specDir, "spec.md"), []byte(text), 0o644); err != nil {
		t.Fatal(err)
	}
	return specDir
}

// messages 把校验结果的所有 msg 拼成一个字符串，便于 assertIn。
func messages(specDir string, requireReady bool) string {
	var parts []string
	for _, iss := range ValidateIssues(specDir, requireReady) {
		parts = append(parts, iss.Msg)
	}
	return strings.Join(parts, " ")
}

func assertIn(t *testing.T, haystack, needle string) {
	t.Helper()
	if !strings.Contains(haystack, needle) {
		t.Errorf("messages do not contain %q\nfull: %s", needle, haystack)
	}
}

func TestStandardNoCorpusContractIsValid(t *testing.T) {
	specDir := writeSpec(t, standardSpec())
	if errs := ValidateIssues(specDir, true); len(errs) != 0 {
		t.Fatalf("standard spec should pass; got %d issues: %v", len(errs), errs)
	}
}

func TestMetadataAverageBudgetVersionRecomputed(t *testing.T) {
	text := strings.Replace(standardSpec(), "> adversarial_risk_version: 3", "> adversarial_risk_version: 2", 1)
	text = strings.Replace(text, "> risk_average: 2.0", "> risk_average: 3.0", 1)
	text = strings.Replace(text, "> review_budget: standard", "> review_budget: full", 1)
	msgs := messages(writeSpec(t, text), true)
	assertIn(t, msgs, "adversarial_risk_version 为 3")
	assertIn(t, msgs, "risk_average 应为 2.0")
	assertIn(t, msgs, "review_budget 应为 standard")
}

func TestRiskBasisEmptyFieldChecked(t *testing.T) {
	text := strings.Replace(standardSpec(), "- 预算升级：无。\n", "", 1)
	msgs := messages(writeSpec(t, text), true)
	assertIn(t, msgs, "风险评分依据缺少非空「预算升级」项")
}

func TestDuplicateScenarioFieldChecked(t *testing.T) {
	text := strings.Replace(standardSpec(),
		"- **WHEN** 调用解析器\n",
		"- **WHEN** 调用解析器\n- **WHEN** 再次调用解析器\n", 1)
	msgs := messages(writeSpec(t, text), true)
	assertIn(t, msgs, "Scenario「输入保持只读」重复字段：WHEN")
}

func TestSpecRootRejectsSidecarDocuments(t *testing.T) {
	specDir := writeSpec(t, standardSpec())
	if err := os.WriteFile(filepath.Join(specDir, "notes.md"), []byte("# 旁路规格\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	msgs := messages(specDir, true)
	assertIn(t, msgs, "单文件包根目录只允许 spec.md 和后续 tasks/")
}

func TestUnfilledTemplatePlaceholdersRejected(t *testing.T) {
	text := strings.Replace(standardSpec(), "- 返回确定性结果。", "- <可观察、可验证的系统结果>", 1)
	text = strings.Replace(text, "- **THEN** 输入对象保持原值", "- **THEN** <可观察结果>", 1)
	msgs := messages(writeSpec(t, text), true)
	assertIn(t, msgs, "删除模板注释或占位符：<可观察、可验证的系统结果>")
	assertIn(t, msgs, "删除模板注释或占位符：<可观察结果>")
}

func TestFencedScenarioExampleDoesNotSatisfyContract(t *testing.T) {
	text := strings.Replace(standardSpec(), "## Scenarios 模板\n", "```md\n## Scenarios 模板\n", 1) + "```\n"
	msgs := messages(writeSpec(t, text), true)
	assertIn(t, msgs, "缺少二级节「Scenarios」")
}

func TestStandardPathRejectsAdversarialScenarioExpansion(t *testing.T) {
	text := strings.Replace(standardSpec(),
		"- 来源：initial-spec",
		"- 来源：adversarial-review (assumption:mutation)", 1)
	msgs := messages(writeSpec(t, text), true)
	assertIn(t, msgs, "standard 路径不允许扩张对抗性 Scenario")
}

func TestTablesModelAndE2EDecisionChecked(t *testing.T) {
	text := strings.Replace(standardSpec(),
		"| Resolver | 目标 | 新增解析 | 输入变更 → 状态污染 → 调用方错误 | 输入只读 | J1 |",
		"| Resolver | 目标 | 新增解析 |  | 输入只读 | J1 |", 1)
	text = strings.Replace(text, "| 故障 | SC_01 |\n", "", 1)
	text = strings.Replace(text, "- 决策：省略\n", "", 1)
	msgs := messages(writeSpec(t, text), true)
	assertIn(t, msgs, "主要风险为空")
	assertIn(t, msgs, "建模覆盖声明缺少：故障")
	assertIn(t, msgs, "E2E 测试必须明确写")
}

// --- 完整对抗审查路径 (full_top5 / no_corpus / recall_failure) ---

func fullTop5Spec() string {
	text := strings.Replace(standardSpec(),
		"> complexity: 2\n> importance: 2\n> risk_average: 2.0\n> review_budget: standard\n> adversarial_review: skipped-standard",
		"> complexity: 4\n> importance: 4\n> risk_average: 4.0\n> review_budget: full\n> adversarial_review: complete", 1)
	text = strings.Replace(text,
		"| ARV-1 | standard | no-corpus | 无 | 无 | 无 | 无 | skipped:no-corpus |",
		"| ARV-1 | full | RAG:AR-001；assumption:nested-mutation | resolver immutable input | AR-001, AR-002, AR-003, AR-004, AR-005 | SC_01 | SC_02 | exit=0; matches=5 |", 1)
	return text +
		"\n### Scenario SC_02: 嵌套输入保持只读\n\n" +
			"- **GIVEN** 一个嵌套可变输入对象\n" +
			"- **WHEN** 调用解析器\n" +
			"- **THEN** 所有嵌套成员保持原值\n" +
			"- 测试层：unit\n" +
			"- 依据：J1\n" +
			"- 来源：adversarial-review (rag:AR-001)\n"
}

func fullNoCorpusSpec() string {
	return strings.Replace(fullTop5Spec(),
		"| ARV-1 | full | RAG:AR-001；assumption:nested-mutation | resolver immutable input | AR-001, AR-002, AR-003, AR-004, AR-005 | SC_01 | SC_02 | exit=0; matches=5 |",
		"| ARV-1 | full | assumption:nested-mutation | 无 RAG 经验集 | 无 | SC_01 | SC_02 | skipped:no-corpus |", 1)
	// 注意：此 replace 之后的 source 仍为 rag:AR-001，测试期望里 no_corpus 的 scenario
	// 来源应改为 assumption；test_spec_engine.py 还做了第二处 replace，调用方按需处理。
}

func standardRecallFailureSpec() string {
	return strings.Replace(standardSpec(),
		"| ARV-1 | standard | no-corpus | 无 | 无 | 无 | 无 | skipped:no-corpus |",
		"| ARV-1 | standard | 无 | resolver immutable input | 无 | 无 | 无 | exit=7; matches=0; error=MODEL_LOAD; message=failed |", 1)
}

func TestCompletedFullTop5AndRagSourceAreValid(t *testing.T) {
	specDir := writeSpec(t, fullTop5Spec())
	if errs := ValidateIssues(specDir, true); len(errs) != 0 {
		t.Fatalf("full top5 spec should pass; got %d issues: %v", len(errs), errs)
	}
	scenarios := SpecScenarios(filepath.Join(specDir, "spec.md"))
	if len(scenarios) != 2 || scenarios[0].ID != "SC_01" || scenarios[1].ID != "SC_02" {
		t.Fatalf("scenarios = %+v, want [SC_01 SC_02]", scenarios)
	}
	if scenarios[1].Source != "adversarial-review (rag:AR-001)" {
		t.Errorf("SC_02 source = %q, want adversarial-review (rag:AR-001)", scenarios[1].Source)
	}
}

func TestCompletedFullNoCorpusAssumptionPathIsValid(t *testing.T) {
	text := strings.Replace(fullNoCorpusSpec(),
		"adversarial-review (rag:AR-001)",
		"adversarial-review (assumption:nested-mutation)", 1)
	if errs := ValidateIssues(writeSpec(t, text), true); len(errs) != 0 {
		t.Fatalf("full no-corpus spec should pass; got %d issues: %v", len(errs), errs)
	}
}

func TestStandardRecallFailureRecordsErrorAndStillPasses(t *testing.T) {
	if errs := ValidateIssues(writeSpec(t, standardRecallFailureSpec()), true); len(errs) != 0 {
		t.Fatalf("recall-failure spec should pass; got %d issues: %v", len(errs), errs)
	}
}

func TestStandardRecallFailureRequiresErrorAndMessage(t *testing.T) {
	for _, suffix := range []string{"", "; error=; message="} {
		text := strings.Replace(standardRecallFailureSpec(),
			"; error=MODEL_LOAD; message=failed", suffix, 1)
		msgs := messages(writeSpec(t, text), true)
		assertIn(t, msgs, "非空 error=<值>")
		assertIn(t, msgs, "非空 message=<值>")
	}
}

func TestPendingBlocksReqReadinessButStructurallyValid(t *testing.T) {
	text := strings.Replace(fullTop5Spec(), "> adversarial_review: complete", "> adversarial_review: pending", 1)
	specDir := writeSpec(t, text)
	assertIn(t, messages(specDir, true), "阻断 x-req")
	structural := ValidateIssues(specDir, false)
	for _, iss := range structural {
		if strings.Contains(iss.Msg, "阻断 x-req") {
			t.Errorf("require_ready=false should not block: %s", iss.Msg)
		}
	}
}

func TestScenarioSourceAndTop5RecordCrossChecked(t *testing.T) {
	text := strings.Replace(fullTop5Spec(),
		"AR-001, AR-002, AR-003, AR-004, AR-005",
		"AR-002, AR-003, AR-004, AR-005", 1)
	msgs := messages(writeSpec(t, text), true)
	assertIn(t, msgs, "CLI matches 必须等于召回 ID 数量")
	assertIn(t, msgs, "引用的风险 ID 未进入 ARV-n 召回记录：AR-001")
}

func TestTop5AcceptsOneToFiveMatches(t *testing.T) {
	text := strings.Replace(fullTop5Spec(), "RAG:AR-001", "RAG:AR-002", 1)
	text = strings.Replace(text, "adversarial-review (rag:AR-001)", "adversarial-review (rag:AR-002)", 1)
	text = strings.Replace(text, "AR-001, AR-002, AR-003, AR-004, AR-005", "AR-002, AR-003, AR-004, AR-005", 1)
	text = strings.Replace(text, "exit=0; matches=5", "exit=0; matches=4", 1)
	if errs := ValidateIssues(writeSpec(t, text), true); len(errs) != 0 {
		t.Fatalf("top5 4-match spec should pass; got %d issues: %v", len(errs), errs)
	}
}

func TestCompleteReviewRejectsFailedRag(t *testing.T) {
	text := strings.Replace(fullTop5Spec(), "exit=0; matches=5", "exit=7; matches=0", 1)
	msgs := messages(writeSpec(t, text), true)
	assertIn(t, msgs, "complete 状态要求 Top5 召回成功")
}

func TestFullReviewRequiresStructuredIndependentAssumption(t *testing.T) {
	text := strings.Replace(fullTop5Spec(), "assumption:nested-mutation", "garbage-assumption:", 1)
	msgs := messages(writeSpec(t, text), true)
	assertIn(t, msgs, "风险来源必须由 RAG:AR-NNN")
	assertIn(t, msgs, "full 预算必须记录一个独立 assumption")
}

func TestNoCorpusReviewRejectsRagClaimsAndRagScenario(t *testing.T) {
	text := strings.Replace(fullTop5Spec(), "exit=0; matches=5", "skipped:no-corpus", 1)
	msgs := messages(writeSpec(t, text), true)
	assertIn(t, msgs, "风险来源不得包含 RAG ID")
	assertIn(t, msgs, "召回 ID 必须为 无")
	assertIn(t, msgs, "引用的风险 ID 未进入 ARV-n 召回记录")
}

func TestScenarioAssumptionSourceRejectsWhitespaceDescription(t *testing.T) {
	text := strings.Replace(fullTop5Spec(),
		"adversarial-review (rag:AR-001)",
		"adversarial-review (assumption:   )", 1)
	msgs := messages(writeSpec(t, text), true)
	assertIn(t, msgs, "assumption 来源说明不能为空")
}
