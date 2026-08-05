// Package risk 实现 skills/x-adversarial-risk/scripts/risk_contract.py 的等价校验逻辑：
// 验证 x-adversarial-risk 的 spec 契约、错题集（风险语料）契约、以及 spec↔catalog 溯源。
//
// 本包是 1:1 移植，issue code（SPEC_*/CATALOG_*）与中文 message 逐字保留，
// 以便与 test/test_adversarial_risk.py 黑盒对拍。
package risk

import (
	"fmt"
	"regexp"
	"strings"
)

var (
	metadataFields = []string{
		"adversarial_risk_version", "complexity", "importance",
		"risk_average", "review_budget", "adversarial_review",
	}
	headerFields    = append([]string{"spec_version"}, metadataFields...)
	validBudgets    = map[string]bool{"standard": true, "deep": true, "full": true}
	validStatuses   = map[string]bool{"pending": true, "skipped-standard": true, "complete": true}
	currentVersion  = "3"
	scenarioRe      = regexp.MustCompile(`^###\s+Scenario\s+(SC_\d{2,}):\s*(.+?)\s*$`)
	sourceRe        = regexp.MustCompile(`^-\s*来源[：:]\s*(.+?)\s*$`)
	riskIDRe        = regexp.MustCompile(`^AR-\d{3}$`)
	adversarialSrcRe = regexp.MustCompile(
		`^adversarial-review\s*\((?:rag:(?P<risk_id>AR-\d{3})|assumption:(?P<assumption>[^)]+))\)$`,
	)
	catalogHeadingRe = regexp.MustCompile(`^##\s+(.+?)\s*$`)
	// 必填字段沿用初始契约；可选字段由 x-bug2rag 写入。
	requiredCatalogFields = []string{"关键词", "Risk"}
	extraCatalogFields    = []string{"场景", "错误实现", "正确实现", "可观察差异", "分类", "来源"}
	allCatalogFields      = append(append([]string{}, requiredCatalogFields...), extraCatalogFields...)
	richRequiredFields    = append(append([]string{}, requiredCatalogFields...), extraCatalogFields[:len(extraCatalogFields)-1]...)
	catalogFieldRe        = regexp.MustCompile(`^(?:关键词|Risk|场景|错误实现|正确实现|可观察差异|分类|来源)[：:]\s*(.*?)\s*$`)
	forbiddenCatalogMarkers = []string{
		"来源证据", "/Volumes/", "skills/x-pipeline-efficiency-workspace/",
	}
)

// Issue 是 risk 契约的校验问题。对齐 risk_contract.py 的 Issue dataclass。
type Issue struct {
	Code    string `json:"code"`
	Line    int    `json:"line"`
	Message string `json:"message"`
}

func newIssue(code string, line int, msg string) Issue {
	return Issue{Code: code, Line: line, Message: msg}
}

// RiskCard 是错题集中解析出的风险卡。对齐 risk_contract.py 的 RiskCard。
type RiskCard struct {
	ID       string
	Keywords string
	Risk     string
}

// Text 返回召回时用于向量化的文本，对齐 RiskCard.text。
func (c RiskCard) Text() string {
	return fmt.Sprintf("关键词：%s\nRisk：%s", c.Keywords, c.Risk)
}

// expectedBudget 根据复杂度、重要性计算 standard/deep/full 预算。对齐 risk_contract.py。
func expectedBudget(complexity, importance int) string {
	average := float64(complexity+importance) / 2
	if average >= 4 || (complexity == 5 || importance == 5) {
		return "full"
	}
	if average >= 3 || (complexity == 4 || importance == 4) {
		return "deep"
	}
	return "standard"
}

// lineNumber 返回 pattern 首次出现的 1-based 行号，未找到返回 0。对齐 _line_number。
func lineNumber(lines []string, pattern string) int {
	for i, line := range lines {
		if strings.Contains(line, pattern) {
			return i + 1
		}
	}
	return 0
}

// namedGroup 取命名捕获组的值。Go regexp 支持 (?P<name>...) 语法。
func namedGroup(re *regexp.Regexp, input, name string) string {
	match := re.FindStringSubmatch(input)
	if match == nil {
		return ""
	}
	for i, n := range re.SubexpNames() {
		if n == name && i < len(match) {
			return match[i]
		}
	}
	return ""
}

// parseMetadata 解析元数据字段并检查重复/缺失。对齐 _metadata。
func parseMetadata(lines []string) (map[string]string, []Issue) {
	found := map[string]string{}
	var issues []Issue
	fieldRe := regexp.MustCompile(`^>\s*([a-z_]+):\s*(.*?)\s*$`)
	for i, line := range lines {
		m := fieldRe.FindStringSubmatch(line)
		if m == nil {
			continue
		}
		key := m[1]
		if _, ok := contains(metadataFields, key); !ok {
			continue
		}
		if _, exists := found[key]; exists {
			issues = append(issues, newIssue("SPEC_DUPLICATE_FIELD", i+1, fmt.Sprintf("风险字段重复：%s", key)))
			continue
		}
		found[key] = m[2]
	}
	for _, key := range metadataFields {
		if _, ok := found[key]; !ok {
			issues = append(issues, newIssue("SPEC_MISSING_FIELD", 0, fmt.Sprintf("缺少风险字段：%s", key)))
		}
	}
	return found, issues
}

// ValidateSpec 校验 spec 文本的风险契约。对齐 validate_spec。
func ValidateSpec(text string) []Issue {
	lines := strings.Split(text, "\n")
	// Python 用 splitlines()，会把 \r\n 拆开后再 split；这里先归一化。
	lines = splitLines(text)
	metadata, issues := parseMetadata(lines)

	for i, key := range headerFields {
		// 每个元数据头部行必须形如 > key: <非空值>，对齐 _metadata 后续的逐行格式检查。
		expectedRe := regexp.MustCompile(fmt.Sprintf(`^>\s*%s:\s*\S.*$`, regexp.QuoteMeta(key)))
		if i >= len(lines) || !expectedRe.MatchString(lines[i]) {
			issues = append(issues, newIssue("SPEC_HEADER_FORMAT", i+1, fmt.Sprintf("第 %d 行必须使用 > %s: <值>", i+1, key)))
		}
	}
	if len(lines) > len(headerFields) && lines[len(headerFields)] != "" {
		issues = append(issues, newIssue("SPEC_HEADER_FORMAT", len(headerFields)+1, "七个元数据字段后必须保留一个空行"))
	}

	version := metadata["adversarial_risk_version"]
	if version != currentVersion {
		issues = append(issues, newIssue("SPEC_VERSION", lineNumber(lines, "adversarial_risk_version"), "adversarial_risk_version 必须为 3"))
	}

	scoreRe := regexp.MustCompile(`^[1-5]$`)
	scores := map[string]int{}
	for _, key := range []string{"complexity", "importance"} {
		val := metadata[key]
		if !scoreRe.MatchString(val) {
			issues = append(issues, newIssue("SPEC_SCORE", lineNumber(lines, key+":"), fmt.Sprintf("%s 必须是 1..5 的整数", key)))
			continue
		}
		scores[key] = atoi(val)
	}

	avgText := metadata["risk_average"]
	avgRe := regexp.MustCompile(`^[1-5]\.[05]$`)
	var declaredAvg float64
	avgValid := false
	if !avgRe.MatchString(avgText) {
		issues = append(issues, newIssue("SPEC_AVERAGE", lineNumber(lines, "risk_average:"), "risk_average 必须是一位小数，且以 .0 或 .5 结尾"))
	} else {
		declaredAvg = parseFloat(avgText)
		avgValid = true
	}

	if len(scores) == 2 {
		expectedAvg := float64(scores["complexity"]+scores["importance"]) / 2
		if avgValid && declaredAvg != expectedAvg {
			issues = append(issues, newIssue("SPEC_AVERAGE", lineNumber(lines, "risk_average:"), fmt.Sprintf("risk_average 应为 %.1f", expectedAvg)))
		}
		declaredBudget := metadata["review_budget"]
		requiredBudget := expectedBudget(scores["complexity"], scores["importance"])
		if declaredBudget != requiredBudget {
			issues = append(issues, newIssue("SPEC_BUDGET", lineNumber(lines, "review_budget:"), fmt.Sprintf("review_budget 应为 %s", requiredBudget)))
		}
	}

	budget := metadata["review_budget"]
	if !validBudgets[budget] {
		issues = append(issues, newIssue("SPEC_BUDGET", lineNumber(lines, "review_budget:"), "review_budget 必须是 standard、deep 或 full"))
	}

	status := metadata["adversarial_review"]
	if !validStatuses[status] {
		issues = append(issues, newIssue("SPEC_STATUS", lineNumber(lines, "adversarial_review:"), "adversarial_review 状态非法"))
	} else if status == "pending" {
		issues = append(issues, newIssue("SPEC_PENDING", lineNumber(lines, "adversarial_review:"), "对抗性风险审查仍为 pending，阻断 x-req"))
	} else if status == "skipped-standard" && budget != "standard" {
		issues = append(issues, newIssue("SPEC_STATUS", lineNumber(lines, "adversarial_review:"), "只有 standard 预算可以使用 skipped-standard"))
	} else if status == "complete" && budget == "standard" {
		issues = append(issues, newIssue("SPEC_STATUS", lineNumber(lines, "adversarial_review:"), "standard 预算完成后应使用 skipped-standard"))
	}

	if !containsStr(lines, "## 风险评分依据") {
		issues = append(issues, newIssue("SPEC_SECTION", 0, "缺少 ## 风险评分依据"))
	}
	if !containsStr(lines, "## 对抗性审查记录") {
		issues = append(issues, newIssue("SPEC_SECTION", 0, "缺少 ## 对抗性审查记录"))
	} else if status != "pending" {
		arvRe := regexp.MustCompile(`^\|\s*ARV-\d+\s*\|`)
		hasRecord := false
		for _, line := range lines {
			if arvRe.MatchString(line) {
				hasRecord = true
				break
			}
		}
		if !hasRecord {
			issues = append(issues, newIssue("SPEC_REVIEW_RECORD", lineNumber(lines, "## 对抗性审查记录"), "已完成审查缺少 ARV-n 记录行"))
		}
	}

	// Scenario 校验
	type scenarioStart struct {
		index int
		id    string
	}
	var scenarioStarts []scenarioStart
	for i, line := range lines {
		if m := scenarioRe.FindStringSubmatch(line); m != nil {
			scenarioStarts = append(scenarioStarts, scenarioStart{i, m[1]})
		}
	}
	if len(scenarioStarts) == 0 {
		issues = append(issues, newIssue("SPEC_SCENARIO", 0, "缺少 SC_NN Scenario"))
	}
	seenIDs := map[string]bool{}
	for pos, sc := range scenarioStarts {
		if seenIDs[sc.id] {
			issues = append(issues, newIssue("SPEC_SCENARIO_ID", sc.index+1, fmt.Sprintf("Scenario ID 重复：%s", sc.id)))
		}
		seenIDs[sc.id] = true

		end := len(lines)
		if pos+1 < len(scenarioStarts) {
			end = scenarioStarts[pos+1].index
		}
		sourceVal := ""
		sourceLine := 0
		for offset := sc.index + 1; offset < end; offset++ {
			if m := sourceRe.FindStringSubmatch(lines[offset]); m != nil {
				sourceVal = m[1]
				sourceLine = offset + 1
				break
			}
		}
		if sourceVal == "" {
			issues = append(issues, newIssue("SPEC_SCENARIO_SOURCE", sc.index+1, fmt.Sprintf("%s 缺少来源字段", sc.id)))
		} else if sourceVal == "initial-spec" {
			continue
		} else if !adversarialSrcRe.MatchString(sourceVal) {
			issues = append(issues, newIssue("SPEC_SCENARIO_SOURCE", sourceLine, fmt.Sprintf("%s 的 RAG 来源必须使用 adversarial-review (rag:AR-NNN)；独立假设使用 assumption:<说明>", sc.id)))
		}
	}

	return issues
}
