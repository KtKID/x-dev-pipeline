package spec

import (
	"os"
	"regexp"
	"strings"
)

// readText 以 UTF-8 读取，非法字节用替代字符保持校验流程可继续。
// 对齐 spec.py 的 read_text（errors="replace"）。
func readText(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// outsideFences 保留原行号，把 fenced code 及 fence 行替换为空行。
// 对齐 spec.py 的 _outside_fences。
func outsideFences(lines []string) []string {
	visible := make([]string, len(lines))
	var activeMarker string
	for i, line := range lines {
		stripped := strings.TrimLeft(line, " \t")
		var marker string
		if strings.HasPrefix(stripped, "```") {
			marker = "```"
		} else if strings.HasPrefix(stripped, "~~~") {
			marker = "~~~"
		}
		if marker != "" {
			if activeMarker == "" {
				activeMarker = marker
			} else if activeMarker == marker {
				activeMarker = ""
			}
			visible[i] = ""
			continue
		}
		if activeMarker != "" {
			visible[i] = ""
		} else {
			visible[i] = line
		}
	}
	return visible
}

// cells 把 Markdown 表格行拆成去除首尾空白的单元格列表。对齐 spec.py 的 _cells。
func cells(row string) []string {
	trimmed := strings.TrimSpace(row)
	trimmed = strings.TrimPrefix(trimmed, "|")
	trimmed = strings.TrimSuffix(trimmed, "|")
	parts := strings.Split(trimmed, "|")
	out := make([]string, len(parts))
	for i, p := range parts {
		out[i] = strings.TrimSpace(p)
	}
	return out
}

// tableRow 是带原始行号（1-based）的数据行。对齐 spec.py 的 (number, list[str])。
type tableRow struct {
	line int // 1-based，与 spec.py 的 cursor+1 一致
	cols []string
}

// sectionBounds 按 H2 标题前缀定位二级章节，返回该 H2 行的索引（0-based）。
// 对齐 spec.py 的 _section_bounds 的 start 部分（前缀匹配 startswith）。
func sectionBounds(lines []string, prefix string) (start int, found bool) {
	for i, line := range lines {
		if m := h2Re.FindStringSubmatch(line); m != nil && strings.HasPrefix(strings.TrimSpace(m[1]), prefix) {
			return i, true
		}
	}
	return len(lines), false
}

// sectionRange 返回 [h2Index+1, nextH2OrEnd) 的内容区间，未找到时返回 ok=false。
// 对齐 spec.py 的 _section_bounds 返回的 (start+1, end) 用法。
func sectionRange(lines []string, prefix string) (start, end int, ok bool) {
	h2Idx, found := sectionBounds(lines, prefix)
	if !found {
		return 0, 0, false
	}
	return h2Idx + 1, endOfSection(lines, h2Idx), true
}

func endOfSection(lines []string, start int) int {
	for i := start + 1; i < len(lines); i++ {
		if h2Re.MatchString(lines[i]) {
			return i
		}
	}
	return len(lines)
}

// sectionOccurrences 返回指定二级章节前缀的全部出现位置（0-based）。
// 对齐 spec.py 的 _section_occurrences。
func sectionOccurrences(lines []string, prefix string) []int {
	var out []int
	for i, line := range lines {
		if m := h2Re.FindStringSubmatch(line); m != nil && strings.HasPrefix(strings.TrimSpace(m[1]), prefix) {
			out = append(out, i)
		}
	}
	return out
}

// firstTable 解析指定行区间 [start, end) 内的第一张 Markdown 表格，保留数据行行号。
// 对齐 spec.py 的 _first_table。
func firstTable(lines []string, start, end int) (header []string, rows []tableRow) {
	limit := start + 1
	if end-1 > limit {
		limit = end - 1
	}
	for index := start + 1; index < limit; index++ {
		if !strings.HasPrefix(strings.TrimLeft(lines[index], " \t"), "|") {
			continue
		}
		if index+1 >= end || !tableSepRe.MatchString(lines[index+1]) {
			continue
		}
		header = cells(lines[index])
		cursor := index + 2
		for cursor < end && strings.HasPrefix(strings.TrimLeft(lines[cursor], " \t"), "|") {
			rows = append(rows, tableRow{line: cursor + 1, cols: cells(lines[cursor])})
			cursor++
		}
		return header, rows
	}
	return nil, nil
}

// sectionTable 定位指定二级章节并返回该章节中的第一张 Markdown 表格。
// 对齐 spec.py 的 _section_table。
func sectionTable(lines []string, prefix string) (header []string, rows []tableRow) {
	start, end, ok := sectionRange(lines, prefix)
	if !ok {
		return nil, nil
	}
	return firstTable(lines, start-1, end)
}

// sectionHasContent 判断指定二级章节是否包含三级标题之外的非空正文。
// 对齐 spec.py 的 _section_has_content。
func sectionHasContent(lines []string, prefix string) bool {
	start, end, ok := sectionRange(lines, prefix)
	if !ok {
		return false
	}
	for _, line := range lines[start:end] {
		if strings.TrimSpace(line) != "" && !h3Re.MatchString(line) {
			return true
		}
	}
	return false
}

// parseScenarios 解析 Scenarios 章节，汇总每个场景的标题、GWT、测试层、依据和来源。
// 对齐 spec.py 的 _parse_scenarios。
func parseScenarios(lines []string) []Scenario {
	start, _, ok := sectionRange(lines, "Scenarios")
	if !ok {
		return nil
	}
	end := endOfSection(lines, start-1)
	var scenarios []Scenario
	var current *Scenario
	var body [][2]string // (line, value)

	closeCurrent := func() {
		if current == nil {
			return
		}
		gwt := map[string]string{}
		gwtCounts := map[string]int{}
		var layers, evidences, sources []string
		for _, bv := range body {
			if m := gwtRe.FindStringSubmatch(bv[1]); m != nil {
				key := strings.ToUpper(m[1])
				val := strings.TrimSpace(m[2])
				gwt[key] = val
				gwtCounts[key]++
				continue
			}
			if m := layerRe.FindStringSubmatch(bv[1]); m != nil {
				layers = append(layers, strings.ToLower(m[1]))
				continue
			}
			if m := evidenceRe.FindStringSubmatch(bv[1]); m != nil {
				evidences = append(evidences, strings.TrimSpace(m[1]))
				continue
			}
			if m := sourceRe.FindStringSubmatch(bv[1]); m != nil {
				sources = append(sources, strings.TrimSpace(m[1]))
			}
		}
		current.GWT = gwt
		current.GWTCounts = gwtCounts
		if len(layers) > 0 {
			current.Layer = layers[0]
		}
		current.LayerCount = len(layers)
		if len(evidences) > 0 {
			current.Evidence = evidences[0]
		}
		current.EvidenceCount = len(evidences)
		if len(sources) > 0 {
			current.Source = sources[0]
		}
		current.SourceCount = len(sources)
		scenarios = append(scenarios, *current)
		current = nil
		body = nil
	}

	for index := start; index < end; index++ {
		line := lines[index]
		if m := scenarioRe.FindStringSubmatch(line); m != nil {
			closeCurrent()
			current = &Scenario{
				ID:   m[1],
				Name: strings.TrimSpace(m[2]),
				Line: index + 1,
			}
			body = nil
		} else if h3Re.MatchString(line) {
			closeCurrent()
		} else if current != nil {
			body = append(body, [2]string{line, line})
		}
	}
	closeCurrent()
	return scenarios
}

// normalizeModuleName 归一化 Markdown/Mermaid 模块标签，供 spec 边界图做词法比对。
// 对齐 spec.py 的 normalize_module_name。
func normalizeModuleName(value string) string {
	value = regexp.MustCompile(`(?i)<br\s*/?>.*$`).ReplaceAllString(value, "")
	if idx := strings.Index(value, "·"); idx >= 0 {
		value = value[:idx]
	}
	if parts := regexp.MustCompile(`[：:]`).Split(value, 2); len(parts) > 0 {
		value = parts[0]
	}
	value = regexp.MustCompile("[`*_]").ReplaceAllString(value, "")
	value = regexp.MustCompile(`[^0-9A-Za-z一-鿿]+`).ReplaceAllString(value, "")
	return strings.ToLower(value)
}

// expectedBudget 根据复杂度、重要性及单维升级规则计算 standard/deep/full 预算。
// 对齐 spec.py 的 expected_budget。
func expectedBudget(complexity, importance int) string {
	average := float64(complexity+importance) / 2
	if average >= 4 || max(complexity, importance) == 5 {
		return "full"
	}
	if average >= 3 || max(complexity, importance) == 4 {
		return "deep"
	}
	return "standard"
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
