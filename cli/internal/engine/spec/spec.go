package spec

import (
	"encoding/json"
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
)

// ValidateIssues 聚合全部 iteration-7 spec 机械校验；默认同时执行 x-req 就绪门禁。
// 对齐 spec.py 的 validate_issues。
func ValidateIssues(specDir string, requireReady bool) []Issue {
	specMD := specDir + "/spec.md"
	info, err := os.Stat(specMD)
	if err != nil || info.IsDir() {
		return []Issue{issue("(package)", 0, "V19", "spec 包缺少 spec.md")}
	}
	text, err := readText(specMD)
	if err != nil {
		return []Issue{issue("(package)", 0, "V19", fmt.Sprintf("spec 包缺少 spec.md: %v", err))}
	}
	lines := outsideFences(splitLines(text))
	md, issues := metadataIssues(lines, requireReady)
	issues = append(issues, packageIssues(specDir)...)
	issues = append(issues, requiredSectionIssues(lines)...)
	issues = append(issues, templatePlaceholderIssues(lines)...)
	issues = append(issues, riskBasisIssues(lines)...)
	issues = append(issues, tableIssues(lines, requireReady)...)
	issues = append(issues, acceptanceIssues(lines)...)
	reviewIss, recalled := reviewIssues(lines, md)
	issues = append(issues, reviewIss...)
	issues = append(issues, scenarioIssues(lines, md, recalled)...)
	return issues
}

// ValidateCommand 执行一次目录校验，输出文本或 JSON，并按结果返回 0、1、2 退出码。
// 对齐 spec.py 的 validate_command。
func ValidateCommand(specDir string, asJSON, requireReady bool) int {
	issues := ValidateIssues(specDir, requireReady)
	// 与 Python 一致：空 issues 序列化为 [] 而非 null。
	emitIssues := issues
	if emitIssues == nil {
		emitIssues = []Issue{}
	}
	payload := struct {
		Path         string  `json:"path"`
		Type         string  `json:"type"`
		RequireReady bool    `json:"require_ready"`
		Issues       []Issue `json:"issues"`
	}{specDir, "spec", requireReady, emitIssues}
	if asJSON {
		out, _ := json.MarshalIndent(payload, "", "  ")
		fmt.Println(string(out))
	} else {
		fmt.Printf("== %s  [spec]\n", specDir)
		if len(issues) == 0 {
			fmt.Println("   ok")
		}
		for _, item := range issues {
			location := item.File
			if item.Line != 0 {
				location = fmt.Sprintf("%s:%d", item.File, item.Line)
			}
			fmt.Printf("   %s  %s  %s\n", location, item.Rule, item.Msg)
		}
		mark := "✓"
		if len(issues) > 0 {
			mark = "✗"
		}
		fmt.Printf("%s validate：%d issue(s)\n", mark, len(issues))
	}
	if len(issues) == 0 {
		return 0
	}
	return 1
}

// SpecScenarios 读取 spec.md，排除代码围栏后返回结构化 Scenario 列表。
// 对齐 spec.py 的 spec_scenarios（供 req engine 复用）。
func SpecScenarios(specMD string) []Scenario {
	info, err := os.Stat(specMD)
	if err != nil || info.IsDir() {
		return nil
	}
	text, err := readText(specMD)
	if err != nil {
		return nil
	}
	return parseScenarios(outsideFences(splitLines(text)))
}

// HasSpecMarker 判断目录中的 spec.md 是否包含代码围栏外的 spec_version: 3 标记。
func HasSpecMarker(specDir string) bool {
	specMD := specDir + "/spec.md"
	info, err := os.Stat(specMD)
	if err != nil || info.IsDir() {
		return false
	}
	text, err := readText(specMD)
	if err != nil {
		return false
	}
	for _, line := range outsideFences(splitLines(text)) {
		if specMarkerRe.MatchString(strings.TrimSpace(line)) {
			return true
		}
	}
	return false
}

// BoundaryModuleNames 从影响边界表提取模块名，返回标准化名称到原始名称的映射。
func BoundaryModuleNames(specDir string) map[string]string {
	specMD := specDir + "/spec.md"
	info, err := os.Stat(specMD)
	if err != nil || info.IsDir() {
		return nil
	}
	text, err := readText(specMD)
	if err != nil {
		return nil
	}
	lines := outsideFences(splitLines(text))
	header, rows := sectionTable(lines, "影响边界与不变量")
	if !sliceEq(header, boundaryHeader) {
		return nil
	}
	modules := map[string]string{}
	for _, row := range rows {
		if len(row.cols) == 0 {
			continue
		}
		original := strings.TrimSpace(row.cols[0])
		normalized := normalizeModuleName(original)
		if normalized != "" {
			modules[normalized] = original
		}
	}
	return modules
}

// --- 辅助函数 ---

func splitLines(s string) []string {
	// 与 Python splitlines() 对齐：兼容 \n、\r\n、\r，且不保留分隔符。
	s = strings.ReplaceAll(s, "\r\n", "\n")
	s = strings.ReplaceAll(s, "\r", "\n")
	return strings.Split(s, "\n")
}

func atoi(s string) (int, error) {
	return strconv.Atoi(s)
}

func parseFloat(s string) (float64, error) {
	return strconv.ParseFloat(s, 64)
}

func contains(slice []string, v string) (string, bool) {
	for _, x := range slice {
		if x == v {
			return x, true
		}
	}
	return "", false
}

func containsStr(slice []string, v string) bool {
	for _, x := range slice {
		if x == v {
			return true
		}
	}
	return false
}

func removeStr(slice []string, v string) []string {
	out := make([]string, 0, len(slice))
	for _, x := range slice {
		if x != v {
			out = append(out, x)
		}
	}
	return out
}

func uniqueStrs(slice []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, s := range slice {
		if !seen[s] {
			seen[s] = true
			out = append(out, s)
		}
	}
	return out
}

func sliceEq(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func repeatEmpty(n int) []string {
	out := make([]string, n)
	for i := range out {
		out[i] = ""
	}
	return out
}

// splitSemicolon 按 ; 或 ；（全角分号）切分并 trim，丢弃空段。
// 对齐 spec.py review 解析里的 re.split(r"[；;]", ...)。
func splitSemicolon(s string) []string {
	var out []string
	for _, part := range regexp.MustCompile(`[；;]`).Split(s, -1) {
		if t := strings.TrimSpace(part); t != "" {
			out = append(out, t)
		}
	}
	return out
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

// jidTokenRe 匹配文档中所有 J 开头的标识符 token（J 后跟数字），
// 用于等价替代 Python 的 (?<![A-Za-z0-9_-])J\d+(?![A-Za-z0-9_-]) 断言计数。
var jidTokenRe = regexp.MustCompile(`J\d+`)

// countJIDRefs 统计 jID 在 text 中作为完整标识符 token 出现的次数。
// 与 Python 的负向断言正则语义等价：J1 不会匹配 J10/J11 的一部分。
func countJIDRefs(text, jID string) int {
	count := 0
	for _, tok := range jidTokenRe.FindAllString(text, -1) {
		if tok == jID {
			count++
		}
	}
	return count
}
