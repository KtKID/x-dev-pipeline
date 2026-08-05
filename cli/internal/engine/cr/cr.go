// Package cr 实现 skills/x-cr/scripts/validate_report.py 的等价校验逻辑：
// 验证 x-cr-v2 报告契约（不变量覆盖 / 审查结论 / 问题详情 三段一致性）。
//
// 本包是 1:1 移植，规则码与中文错误信息逐字保留，以便与
// test/test_x_cr_report_validator.py 对拍。
package cr

import (
	"fmt"
	"os"
	"regexp"
	"sort"
	"strings"

	"github.com/KtKID/x-dev-pipeline/cli/internal/mdparse"
)

var (
	issueIDRe    = regexp.MustCompile(`^B\d+$`)
	invIDRe      = regexp.MustCompile(`^INV-(?:SPEC|CAND)-\d+$`)
	detailRe     = regexp.MustCompile(`(?m)^### (B\d+):`)
	severityRe   = regexp.MustCompile(`^### P([012])(?:：|:)`)
	schemaRe     = regexp.MustCompile(`(?m)^> Schema: x-cr-v2\s*$`)
	shortestReRe = regexp.MustCompile(`最短(?:补证|确认|取证)`)
)

var (
	allowedStatuses = map[string]bool{
		"❌": true, "⚠️": true, "✅": true,
		"✅已修复": true, "➖无需修复": true, "⏭已跳过": true,
	}
	allowedSeverities        = map[string]bool{"P0": true, "P1": true, "P2": true}
	allowedConfidence        = map[string]bool{"低": true, "中": true, "高": true, "已确认": true}
	allowedInvariantResults  = map[string]bool{"保持": true, "破坏": true, "未验证": true, "来源冲突": true, "未触达": true}
)

// hasShortestEvidenceAction 判断文本中 inv_id 附近 400 字符内是否出现
// "最短补证/确认/取证" 关键词。对齐 Python 版 _has_shortest_evidence_action。
func hasShortestEvidenceAction(text, invID string) bool {
	escaped := regexp.QuoteMeta(invID)
	re1 := regexp.MustCompile(fmt.Sprintf(`%s[\s\S]{0,400}最短(?:补证|确认|取证)`, escaped))
	if re1.MatchString(text) {
		return true
	}
	re2 := regexp.MustCompile(fmt.Sprintf(`最短(?:补证|确认|取证)[\s\S]{0,400}%s`, escaped))
	return re2.MatchString(text)
}

// issueAtMost400CharLongestIssue matches between inv_id and the keyword within 400 chars.
// （占位：Python 版用 [\s\S]{0,400} 实现就近窗口，已在 hasShortestEvidenceAction 中复刻。）

// ValidateText 对整篇报告文本执行契约校验，返回错误信息列表（空表示通过）。
// 与 validate_report.py 的 validate_text 一致。
func ValidateText(text string) []string {
	var errors []string

	if !schemaRe.MatchString(text) {
		errors = append(errors, "缺少 `> Schema: x-cr-v2`")
	}

	required := map[string]string{}
	missingAny := false
	for _, name := range []string{"不变量覆盖", "审查结论", "问题详情"} {
		body, ok := mdparse.Section(text, name)
		if !ok {
			errors = append(errors, fmt.Sprintf("缺少 `## %s`", name))
			missingAny = true
		} else {
			required[name] = body
		}
	}
	if missingAny {
		return errors
	}

	invariantSection := required["不变量覆盖"]
	conclusionSection := required["审查结论"]
	detailSection := required["问题详情"]

	// --- 不变量覆盖段 ---
	invariantIDs := map[string]bool{}
	var invariantTables []*mdparse.Table
	for _, tbl := range tablesInSection(invariantSection) {
		if hasHeader(tbl, "INV-ID") && hasHeader(tbl, "结论") {
			invariantTables = append(invariantTables, tbl)
		}
	}
	if len(invariantTables) == 0 {
		errors = append(errors, "`不变量覆盖` 缺少含 INV-ID 与结论列的表格")
	}

	for _, tbl := range invariantTables {
		for _, row := range tbl.Rows {
			invID, _ := mdparse.RowValue(tbl, row, "INV-ID")
			result, _ := mdparse.RowValue(tbl, row, "结论")
			issue, hasIssue := mdparse.RowValue(tbl, row, "关联问题")

			if !invIDRe.MatchString(invID) {
				errors = append(errors, fmt.Sprintf("不变量 ID 非法: `%s`", invID))
				continue
			}
			if invariantIDs[invID] {
				errors = append(errors, fmt.Sprintf("不变量 ID 重复: `%s`", invID))
			}
			invariantIDs[invID] = true

			if !allowedInvariantResults[result] {
				errors = append(errors, fmt.Sprintf("%s 的结论非法: `%s`", invID, result))
			}

			mappedIssue := hasIssue && issueIDRe.MatchString(issue)
			if result == "破坏" && !mappedIssue {
				errors = append(errors, fmt.Sprintf("%s 为破坏，必须关联一个 Bn", invID))
			}
			if result == "未验证" || result == "来源冲突" {
				if !mappedIssue && !hasShortestEvidenceAction(text, invID) {
					errors = append(errors, fmt.Sprintf("%s 为%s，必须关联 Bn 或记录最短补证/确认动作", invID, result))
				}
			}
		}
	}

	// --- 审查结论段 ---
	conclusionIDs := map[string]bool{}
	conclusionInvIDs := map[string]string{}
	var conclusionTables []*mdparse.Table
	for _, tbl := range tablesInSection(conclusionSection) {
		if hasHeader(tbl, "ID") {
			conclusionTables = append(conclusionTables, tbl)
		}
	}
	if len(conclusionTables) == 0 {
		errors = append(errors, "`审查结论` 缺少含 ID 列的表格")
	}

	for _, tbl := range conclusionTables {
		for _, row := range tbl.Rows {
			issueID, _ := mdparse.RowValue(tbl, row, "ID")
			if issueID == "-" {
				continue
			}
			if !issueIDRe.MatchString(issueID) {
				errors = append(errors, fmt.Sprintf("问题 ID 非法: `%s`", issueID))
				continue
			}
			if conclusionIDs[issueID] {
				errors = append(errors, fmt.Sprintf("审查结论中的问题 ID 重复: `%s`", issueID))
			}
			conclusionIDs[issueID] = true

			status, _ := mdparse.RowValue(tbl, row, "状态")
			if !allowedStatuses[status] {
				errors = append(errors, fmt.Sprintf("%s 的状态非法: `%s`", issueID, status))
			}

			severity, hasSev := mdparse.RowValue(tbl, row, "严重度")
			if !hasSev || severity == "" {
				severity = tbl.Severity
			}
			if !allowedSeverities[severity] {
				errors = append(errors, fmt.Sprintf("%s 的严重度缺失或非法: `%s`", issueID, severity))
			}

			confidence, _ := mdparse.RowValue(tbl, row, "置信度")
			if !allowedConfidence[confidence] {
				errors = append(errors, fmt.Sprintf("%s 的置信度缺失或非法: `%s`", issueID, confidence))
			}

			invID, hasInv := mdparse.RowValue(tbl, row, "INV-ID")
			if !hasInv {
				errors = append(errors, fmt.Sprintf("%s 缺少 INV-ID 列", issueID))
			} else if invID != "-" && !invIDRe.MatchString(invID) {
				errors = append(errors, fmt.Sprintf("%s 的 INV-ID 非法: `%s`", issueID, invID))
			} else if invID != "-" {
				conclusionInvIDs[issueID] = invID
			}
		}
	}

	// --- 问题详情段 ---
	detailAll := detailRe.FindAllString(detailSection, -1)
	// 还原 detailAll 为 Bn 列表
	detailIDs := make([]string, 0, len(detailAll))
	for _, m := range detailAll {
		detailIDs = append(detailIDs, strings.TrimSuffix(strings.TrimPrefix(m, "### "), ":"))
	}
	detailCount := map[string]int{}
	for _, id := range detailIDs {
		detailCount[id]++
	}
	detailIDSet := map[string]bool{}
	for id := range detailCount {
		detailIDSet[id] = true
	}
	for _, id := range sortedKeys(detailCount) {
		if detailCount[id] > 1 {
			errors = append(errors, fmt.Sprintf("问题详情标题重复: `%s`", id))
		}
	}

	// conclusion - detail
	conclOnly := sortedDiff(conclusionIDs, detailIDSet)
	for _, id := range conclOnly {
		errors = append(errors, fmt.Sprintf("%s 缺少对应的 `### %s:` 详情", id, id))
	}
	detailOnly := sortedDiff(detailIDSet, conclusionIDs)
	for _, id := range detailOnly {
		errors = append(errors, fmt.Sprintf("`### %s:` 在审查结论中没有对应行", id))
	}

	// 引用一致性
	for _, issueID := range sortedKeys(conclusionInvIDs) {
		invID := conclusionInvIDs[issueID]
		if !invariantIDs[invID] {
			errors = append(errors, fmt.Sprintf("%s 引用的 %s 不在不变量覆盖表中", issueID, invID))
		}
	}

	return errors
}

// ValidatePath 读取并校验一个报告文件，IO 错误时返回单条错误信息。
func ValidatePath(path string) []string {
	data, err := os.ReadFile(path)
	if err != nil {
		return []string{fmt.Sprintf("无法读取报告: %v", err)}
	}
	return ValidateText(string(data))
}

// --- 内部工具 ---

func hasHeader(t *mdparse.Table, h string) bool {
	for _, x := range t.Headers {
		if x == h {
			return true
		}
	}
	return false
}

func sortedKeys[V any](m map[string]V) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func sortedDiff(set, excl map[string]bool) []string {
	out := make([]string, 0, len(set))
	for k := range set {
		if !excl[k] {
			out = append(out, k)
		}
	}
	sort.Strings(out)
	return out
}

// _ 占位，保留 shortestReRe 以便后续 §不变量覆盖 段落补证关键词扩展时复用。
var _ = shortestReRe

// tablesInSection 解析 section 文本中的所有表格，并捕获每个表格所在 `### Pn:` 段落
// 写入 Table.Severity。这是 validate_report.py 的 _tables 语义：severity 在遍历时
// 由前置的 SEVERITY_RE 行确定，后续表格继承该 severity 直到遇到新的 ### Pn:。
func tablesInSection(section string) []*mdparse.Table {
	lines := strings.Split(section, "\n")
	var result []*mdparse.Table
	severity := ""
	i := 0
	for i < len(lines) {
		if m := severityRe.FindStringSubmatch(strings.TrimSpace(lines[i])); m != nil {
			severity = "P" + m[1]
		}
		if !strings.HasPrefix(strings.TrimLeft(lines[i], " \t"), "|") {
			i++
			continue
		}
		var block [][]string
		for i < len(lines) && strings.HasPrefix(strings.TrimLeft(lines[i], " \t"), "|") {
			block = append(block, mdparse.Cells(lines[i]))
			i++
		}
		if len(block) >= 2 && mdparse.IsSeparator(block[1]) {
			width := len(block[0])
			rows := make([][]string, 0, len(block)-2)
			for _, row := range block[2:] {
				if len(row) == width {
					rows = append(rows, row)
				}
			}
			result = append(result, &mdparse.Table{Headers: block[0], Rows: rows, Severity: severity})
		}
	}
	return result
}
