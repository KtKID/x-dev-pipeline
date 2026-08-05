package flag

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"
)

// ===== issue ledger 编号 =====

// nextIssueID 扫描 report 文本里所有 issue 行首，返回本轮下一个 issue ID。
// 对齐 flag.py 的 next_issue_id。
func nextIssueID(reportText string) string {
	maxNum := 0
	for _, m := range issueLineRe.FindAllStringSubmatch(reportText, -1) {
		n := atoiSafe(m[1])
		if n > maxNum {
			maxNum = n
		}
	}
	return fmt.Sprintf("issue-%d", maxNum+1)
}

// atoiSafe 解析整数，失败返回 0。
func atoiSafe(s string) int {
	var n int
	_, err := fmt.Sscanf(s, "%d", &n)
	if err != nil {
		return 0
	}
	return n
}

// renderIssueReport 创建新轮 issue ledger 的固定骨架。对齐 flag.py 的 render_issue_report。
func renderIssueReport(reportPath string) string {
	stem := strings.TrimSuffix(filepath.Base(reportPath), ".md")
	return fmt.Sprintf("# QA Gate Issue Ledger — %s\n\n", stem) +
		"> 由 `x-dev/scripts/xdev.py flag` 生成和维护；issue 行归代码所有；本轮首条由代码分配为 `issue-1`。\n\n" +
		"## Issues\n"
}

// appendIssueLine 把一条 issue 追加到 ledger 文本。对齐 flag.py 的 append_issue_line。
func appendIssueLine(reportText string, issue issueEntry) string {
	prefix := reportText
	if !strings.HasSuffix(reportText, "\n") {
		prefix = reportText + "\n"
	}
	taskText := strings.Join(issue.Tasks, ",")
	return fmt.Sprintf("%s- %s | %s | %s | %s | %s\n",
		prefix, issue.Issue, issue.Severity, taskText, issue.Loc, issue.Msg)
}

// issueEntry 是一条 issue 记录。
type issueEntry struct {
	Issue    string
	Tasks    []string
	Severity string
	Loc      string
	Msg      string
}

// ===== report 解析 =====

// reportSortKey 从文件名提取排序键 (timestamp, suffix)。对齐 flag.py 的 _report_sort_key。
func reportSortKey(name string) (string, int, error) {
	m := reportNameRe.FindStringSubmatch(name)
	if m == nil {
		return "", 0, newFlagError("非法 QA Gate report 文件名：%s", name)
	}
	timestamp := m[1]
	suffix := 0
	if m[2] != "" {
		suffix = atoiSafe(m[2])
	}
	return timestamp, suffix, nil
}

// resolveCurrentReport 选择本轮 ledger。
// new_round=true 或无候选时创建新文件；否则选最大的现有 report。
// 返回 (report_path, report_text, before_sha256_or_empty)。
// 对齐 flag.py 的 resolve_current_report。
func resolveCurrentReport(reportsDir string, newRound bool, now time.Time) (string, string, string, error) {
	var candidates []string
	if entries, err := os.ReadDir(reportsDir); err == nil {
		for _, e := range entries {
			if e.IsDir() {
				continue
			}
			if fullMatch(reportNameRe, e.Name()) {
				candidates = append(candidates, filepath.Join(reportsDir, e.Name()))
			}
		}
	}
	if newRound || len(candidates) == 0 {
		timestamp := now.Format("20060102-150405")
		base := filepath.Join(reportsDir, fmt.Sprintf("qa-gate-report-%s.md", timestamp))
		if _, err := os.Stat(base); os.IsNotExist(err) {
			return base, renderIssueReport(base), "", nil
		}
		// 同秒冲突时加数字后缀。
		suffix := 1
		for {
			candidate := filepath.Join(reportsDir, fmt.Sprintf("qa-gate-report-%s-%02d.md", timestamp, suffix))
			if _, err := os.Stat(candidate); os.IsNotExist(err) {
				return candidate, renderIssueReport(candidate), "", nil
			}
			suffix++
		}
	}
	// 选最大的（按 timestamp + suffix）。
	sort.Slice(candidates, func(i, j int) bool {
		ti, si, _ := reportSortKey(filepath.Base(candidates[i]))
		tj, sj, _ := reportSortKey(filepath.Base(candidates[j]))
		if ti != tj {
			return ti < tj
		}
		return si < sj
	})
	best := candidates[len(candidates)-1]
	data, err := os.ReadFile(best)
	if err != nil {
		return "", "", "", newFlagError("读取 QA Gate ledger 失败：%v", err)
	}
	return best, string(data), sha256Bytes(data), nil
}

// fullMatchReportName 用 reportNameRe 完整匹配（fullmatch 语义）。
func fullMatchReportName(name string) bool {
	return fullMatch(reportNameRe, name)
}

// _ 占位引用。
var _ = regexp.MustCompile
