package cr

import (
	"strings"
	"testing"
)

// validReport 与 test/test_x_cr_report_validator.py 的 VALID_REPORT 逐字一致，
// 用于对拍 5 个校验用例。
const validReport = `# Correctness Review 报告

> Schema: x-cr-v2

## 不变量覆盖

| INV-ID | 不变量 | 结论 | 关联问题 |
|--------|--------|------|----------|
| INV-SPEC-01 | 审批范围只能收窄 | 破坏 | B1 |
| INV-CAND-01 | 登录主体来自服务端 | 保持 | - |

## 审查结论

### P0：阻断性正确性错误

| ID | 状态 | INV-ID | 检查项 | 置信度 |
|----|------|--------|--------|--------|
| B1 | ❌ | INV-SPEC-01 | 审批范围扩大 | 已确认 |

## 问题详情

### B1: 审批范围扩大

批准 ` + "`git status`" + ` 后错误放行了 ` + "`git push`" + `。
`

func TestAcceptsValidReport(t *testing.T) {
	if errs := ValidateText(validReport); len(errs) != 0 {
		t.Fatalf("valid report should pass; got errors: %v", errs)
	}
}

func TestRejectsMissingDetail(t *testing.T) {
	report := removeDetail(validReport)
	assertContains(t, ValidateText(report), "B1 缺少对应的 `### B1:` 详情")
}

func TestRejectsDuplicateConclusionID(t *testing.T) {
	dup := "| B1 | ❌ | INV-SPEC-01 | 第二个问题 | 高 |\n"
	report := strings.Replace(validReport,
		"| B1 | ❌ | INV-SPEC-01 | 审批范围扩大 | 已确认 |\n",
		"| B1 | ❌ | INV-SPEC-01 | 审批范围扩大 | 已确认 |\n"+dup, 1)
	assertContains(t, ValidateText(report), "审查结论中的问题 ID 重复: `B1`")
}

func TestRejectsBrokenInvariantWithoutIssue(t *testing.T) {
	report := strings.Replace(validReport,
		"| INV-SPEC-01 | 审批范围只能收窄 | 破坏 | B1 |",
		"| INV-SPEC-01 | 审批范围只能收窄 | 破坏 | - |", 1)
	assertContains(t, ValidateText(report), "INV-SPEC-01 为破坏，必须关联一个 Bn")
}

func TestRejectsInvalidSeverityConfidenceAndStatus(t *testing.T) {
	report := strings.Replace(validReport,
		"### P0：阻断性正确性错误",
		"### P3：旧严重度", 1)
	report = strings.Replace(report,
		"| B1 | ❌ | INV-SPEC-01 | 审批范围扩大 | 已确认 |",
		"| B1 | maybe | INV-SPEC-01 | 审批范围扩大 | 猜测 |", 1)
	errs := ValidateText(report)
	assertContains(t, errs, "B1 的状态非法: `maybe`")
	assertContains(t, errs, "B1 的严重度缺失或非法: ``")
	assertContains(t, errs, "B1 的置信度缺失或非法: `猜测`")
}

// --- helpers ---

func assertContains(t *testing.T, errs []string, want string) {
	t.Helper()
	for _, e := range errs {
		if e == want {
			return
		}
	}
	t.Errorf("errors %v do not contain expected %q", errs, want)
}

func removeDetail(report string) string {
	idx := strings.Index(report, "### B1:")
	if idx < 0 {
		return report
	}
	return report[:idx]
}
