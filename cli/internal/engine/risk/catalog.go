package risk

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// ParseCatalog 解析错题集文本，返回风险卡列表和校验问题。
// 对齐 risk_contract.py 的 parse_catalog。
func ParseCatalog(text string, requireRichFields bool) ([]RiskCard, []Issue) {
	lines := splitLines(text)
	type heading struct {
		index int
		id    string
	}
	var headings []heading
	for i, line := range lines {
		if m := catalogHeadingRe.FindStringSubmatch(line); m != nil {
			headings = append(headings, heading{i, m[1]})
		}
	}

	var issues []Issue
	if len(headings) == 0 {
		return nil, []Issue{newIssue("CATALOG_EMPTY", 0, "错题集缺少风险条目")}
	}

	var cards []RiskCard
	seenIDs := map[string]bool{}
	for pos, h := range headings {
		headingLine := h.index + 1
		end := len(lines)
		if pos+1 < len(headings) {
			end = headings[pos+1].index
		}
		fields := map[string][2]string{} // field -> {line, value}

		validID := riskIDRe.MatchString(h.id)
		if !validID {
			issues = append(issues, newIssue("CATALOG_ID", headingLine, fmt.Sprintf("错题 ID 必须匹配 AR-NNN：%s", h.id)))
		} else if seenIDs[h.id] {
			issues = append(issues, newIssue("CATALOG_DUPLICATE_ID", headingLine, fmt.Sprintf("错题 ID 重复：%s", h.id)))
		} else {
			seenIDs[h.id] = true
		}

		for offset := h.index + 1; offset < end; offset++ {
			line := lines[offset]
			if strings.TrimSpace(line) == "" {
				continue
			}
			m := catalogFieldRe.FindStringSubmatch(line)
			if m == nil {
				allowed := strings.Join(allCatalogFields, "、")
				issues = append(issues, newIssue("CATALOG_UNKNOWN_CONTENT", offset+1, fmt.Sprintf("%s 只允许以下字段：%s", h.id, allowed)))
				continue
			}
			// 提取字段名（catalogFieldRe 用 alternation，需重新定位是哪个字段）
			field := catalogFieldName(line)
			if field == "" {
				continue
			}
			if _, exists := fields[field]; exists {
				issues = append(issues, newIssue("CATALOG_DUPLICATE_FIELD", offset+1, fmt.Sprintf("%s 字段重复：%s", h.id, field)))
				continue
			}
			fields[field] = [2]string{strconv.Itoa(offset + 1), strings.TrimSpace(m[1])}
		}

		required := requiredCatalogFields
		if requireRichFields {
			required = richRequiredFields
		}
		for _, field := range required {
			entry, ok := fields[field]
			if !ok || entry[1] == "" {
				issues = append(issues, newIssue("CATALOG_MISSING_FIELD", headingLine, fmt.Sprintf("%s 缺少非空字段：%s", h.id, field)))
			}
		}

		if validID {
			kwEntry, hasKw := fields["关键词"]
			riskEntry, hasRisk := fields["Risk"]
			if hasKw && hasRisk && kwEntry[1] != "" && riskEntry[1] != "" {
				cards = append(cards, RiskCard{ID: h.id, Keywords: kwEntry[1], Risk: riskEntry[1]})
			}
		}
	}
	return cards, issues
}

// catalogFieldName 从一行提取字段名（关键词/Risk/...），用于 alternation 正则后定位。
func catalogFieldName(line string) string {
	for _, f := range allCatalogFields {
		prefix := f + "："
		if strings.HasPrefix(strings.TrimSpace(line), prefix) {
			return f
		}
	}
	return ""
}

// ValidateCorpus 校验错题集文本。对齐 validate_corpus。
func ValidateCorpus(text string, requireRichFields bool) []Issue {
	lines := splitLines(text)
	_, issues := ParseCatalog(text, requireRichFields)
	for i, line := range lines {
		for _, marker := range forbiddenCatalogMarkers {
			if strings.Contains(line, marker) {
				issues = append(issues, newIssue("CATALOG_EVIDENCE_PATH", i+1, fmt.Sprintf("错题集包含发布环境外的证据标记：%s", marker)))
			}
		}
	}
	return issues
}

// ValidateTraceability 校验 spec 中 rag:AR-NNN 来源是否都在 catalog 中。对齐 validate_traceability。
func ValidateTraceability(specText, catalogText string) []Issue {
	lines := splitLines(specText)
	metadata, _ := parseMetadata(lines)
	if metadata["adversarial_risk_version"] != currentVersion {
		return nil
	}
	cards, _ := ParseCatalog(catalogText, false)
	catalogIDs := map[string]bool{}
	for _, c := range cards {
		catalogIDs[c.ID] = true
	}
	var issues []Issue
	for i, line := range lines {
		m := sourceRe.FindStringSubmatch(line)
		if m == nil {
			continue
		}
		source := m[1]
		am := adversarialSrcRe.FindStringSubmatch(source)
		if am == nil {
			continue
		}
		rid := namedGroup(adversarialSrcRe, source, "risk_id")
		if rid == "" {
			continue
		}
		if !catalogIDs[rid] {
			issues = append(issues, newIssue("SPEC_SOURCE_CATALOG", i+1, fmt.Sprintf("来源引用的 %s 不在错题集中", rid)))
		}
	}
	return issues
}

// --- CLI ---

// ReadTargetForCLI 读目标文件，IO 错误时返回 issue。对齐 _read_target。
func ReadTargetForCLI(path string) (string, *Issue) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", &Issue{Code: "IO_ERROR", Line: 0, Message: fmt.Sprintf("%s: %v", path, err)}
	}
	return string(data), nil
}

// Emit 输出校验结果，返回 stdout 内容（不含末尾换行，由调用方决定）和退出码。
func Emit(command, target string, issues []Issue, asJSON bool) (string, int) {
	// 与 Python 一致：空 issues 序列化为 [] 而非 null。
	emitIssues := issues
	if emitIssues == nil {
		emitIssues = []Issue{}
	}
	payload := struct {
		Command string  `json:"command"`
		Target  string  `json:"target"`
		Valid   bool    `json:"valid"`
		Issues  []Issue `json:"issues"`
	}{command, target, len(issues) == 0, emitIssues}

	var out strings.Builder
	if asJSON {
		b, _ := json.MarshalIndent(payload, "", "  ")
		// 保持字段顺序与 Python 一致（Go struct 字段顺序即 JSON 顺序，已匹配）
		out.Write(b)
	} else {
		if len(issues) == 0 {
			fmt.Fprintf(&out, "PASS %s: %s", command, target)
		} else {
			for _, iss := range issues {
				location := ""
				if iss.Line != 0 {
					location = fmt.Sprintf(":%d", iss.Line)
				}
				fmt.Fprintf(&out, "%s%s [%s] %s\n", target, location, iss.Code, iss.Message)
			}
			outStr := out.String()
			out.Reset()
			out.WriteString(strings.TrimRight(outStr, "\n"))
		}
	}
	return out.String(), ExitCode(issues)
}

// ExitCode 返回校验结果对应的退出码：0 通过，1 失败。
func ExitCode(issues []Issue) int {
	if len(issues) == 0 {
		return 0
	}
	return 1
}

// --- helpers ---

func splitLines(s string) []string {
	s = strings.ReplaceAll(s, "\r\n", "\n")
	s = strings.ReplaceAll(s, "\r", "\n")
	return strings.Split(s, "\n")
}

func atoi(s string) int {
	n, _ := strconv.Atoi(s)
	return n
}

func parseFloat(s string) float64 {
	f, _ := strconv.ParseFloat(s, 64)
	return f
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
