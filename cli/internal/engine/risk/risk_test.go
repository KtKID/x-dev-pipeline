package risk

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// validSpec 与 test/test_adversarial_risk.py 的 valid_spec() 参数化一致。
func validSpec(complexity, importance int, average, budget, status, source string) string {
	return "> spec_version: 3\n" +
		"> adversarial_risk_version: 3\n" +
		fmt.Sprintf("> complexity: %d\n", complexity) +
		fmt.Sprintf("> importance: %d\n", importance) +
		fmt.Sprintf("> risk_average: %s\n", average) +
		fmt.Sprintf("> review_budget: %s\n", budget) +
		fmt.Sprintf("> adversarial_review: %s\n\n", status) +
		"# demo\n\n" +
		"## 风险评分依据\n\n" +
		"- 复杂度：包含状态恢复。\n" +
		"- 重要性：影响全部用户数据。\n\n" +
		"## 对抗性审查记录\n\n" +
		"| Review | 预算 | 匹配 issue | 被推翻假设 | 新增 Scenario |\n" +
		"|---|---|---|---|---|\n" +
		fmt.Sprintf("| ARV-1 | %s | AR-001 | 多文件替换具有崩溃窗口 | SC_01 |\n\n", budget) +
		"## Scenarios\n\n" +
		"### Scenario SC_01: 恢复一致状态\n\n" +
		"- **GIVEN** 新 snapshot 与旧 journal 同时存在\n" +
		"- **WHEN** 服务重启\n" +
		"- **THEN** 系统恢复一致状态\n" +
		"- 测试层：unit\n" +
		"- 依据：用户任务\n" +
		fmt.Sprintf("- 来源：%s\n", source)
}

func defaultValidSpec() string {
	return validSpec(4, 4, "4.0", "full", "complete", "initial-spec")
}

func validCorpus() string {
	return "# 风险错题集\n\n" +
		"## AR-001\n\n" +
		"关键词：持久化替换、崩溃恢复\n" +
		"Risk：分阶段替换中途崩溃可能留下部分完成状态。\n"
}

func writeFile(t *testing.T, dir, name, content string) string {
	t.Helper()
	path := filepath.Join(dir, name)
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}

func assertInMsg(t *testing.T, issues []Issue, want string) {
	t.Helper()
	for _, iss := range issues {
		if strings.Contains(iss.Message, want) {
			return
		}
	}
	t.Errorf("issues %v do not contain message %q", issues, want)
}

func TestValidSpecPasses(t *testing.T) {
	if issues := ValidateSpec(defaultValidSpec()); len(issues) != 0 {
		t.Fatalf("valid spec should pass; got %d: %v", len(issues), issues)
	}
}

func TestSingleDimensionFiveForcesFullBudget(t *testing.T) {
	text := validSpec(5, 1, "3.0", "deep", "complete", "initial-spec")
	issues := ValidateSpec(text)
	// Python 断言退出码 1 + "review_budget 应为 full"
	found := false
	for _, iss := range issues {
		if strings.Contains(iss.Message, "review_budget 应为 full") {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected 'review_budget 应为 full' in issues: %v", issues)
	}
}

func TestPendingStatusBlocksContract(t *testing.T) {
	text := validSpec(4, 4, "4.0", "full", "pending", "initial-spec")
	issues := ValidateSpec(text)
	// pending 会让该 spec 缺 ARV 记录被跳过；但 pending 本身产 SPEC_PENDING issue
	assertInMsg(t, issues, "阻断 x-req")
}

func TestScenarioSourceIsRequired(t *testing.T) {
	text := strings.Replace(defaultValidSpec(), "- 来源：initial-spec\n", "", 1)
	issues := ValidateSpec(text)
	assertInMsg(t, issues, "SC_01 缺少来源字段")
}

func TestAdversarialSourceRequiresRagOrAssumption(t *testing.T) {
	text := validSpec(4, 4, "4.0", "full", "complete", "adversarial-review (rag:AR-001)")
	if issues := ValidateSpec(text); len(issues) != 0 {
		t.Fatalf("rag source should pass; got %d: %v", len(issues), issues)
	}
}

func TestValidCorpusPasses(t *testing.T) {
	if issues := ValidateCorpus(validCorpus(), false); len(issues) != 0 {
		t.Fatalf("valid corpus should pass; got %d: %v", len(issues), issues)
	}
}

func TestRichFieldGateRejectsLegacyTwoFieldCard(t *testing.T) {
	issues := ValidateCorpus(validCorpus(), true)
	msgs := map[string]bool{}
	for _, iss := range issues {
		msgs[iss.Message] = true
	}
	for _, want := range []string{
		"AR-001 缺少非空字段：场景",
		"AR-001 缺少非空字段：错误实现",
		"AR-001 缺少非空字段：正确实现",
		"AR-001 缺少非空字段：可观察差异",
		"AR-001 缺少非空字段：分类",
	} {
		if !msgs[want] {
			t.Errorf("missing expected issue %q; got %v", want, msgs)
		}
	}
}

func TestCorpusRejectsDuplicateIdAndMissingField(t *testing.T) {
	broken := strings.Replace(validCorpus(), "关键词：持久化替换、崩溃恢复\n", "", 1)
	broken += strings.Replace(validCorpus(), "# 风险错题集\n\n", "", 1)
	issues := ValidateCorpus(broken, false)
	assertInMsg(t, issues, "错题 ID 重复：AR-001")
	assertInMsg(t, issues, "AR-001 缺少非空字段：关键词")
}

func TestNamespacedIdIsRejected(t *testing.T) {
	text := strings.Replace(validCorpus(), "AR-001", "A-risk-001", 1)
	issues := ValidateCorpus(text, false)
	assertInMsg(t, issues, "错题 ID 必须匹配 AR-NNN")
}
