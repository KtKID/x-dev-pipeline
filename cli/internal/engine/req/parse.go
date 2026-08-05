package req

import (
	"os"
	"regexp"
	"strings"
)

// readText 以 UTF-8 读取文件，非法字节用替代字符保持校验流程可继续。
// 对齐 req.py 的 read_text（errors="replace"）。
func readText(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// cells 拆分一行 markdown 表格为单元格。对齐 req.py 的 cells。
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

// tableRow 是带原始行号（1-based）的表格数据行。对齐 req.py 的 (line_no, cells)。
type tableRow struct {
	line  int
	cells []string
}

// firstTable 返回文本中第一个 markdown 表格的表头和数据行。
// 定位规则：找到以 | 开头、且下一行是分隔行（tableSepRe）的位置。
// 无表返回 (nil, nil)。对齐 req.py 的 first_table。
func firstTable(text string) ([]string, []tableRow) {
	lines := strings.Split(strings.ReplaceAll(strings.ReplaceAll(text, "\r\n", "\n"), "\r", "\n"), "\n")
	for i := 0; i < len(lines)-1; i++ {
		if !strings.HasPrefix(strings.TrimLeft(lines[i], " \t"), "|") {
			continue
		}
		if !tableSepRe.MatchString(lines[i+1]) {
			continue
		}
		header := cells(lines[i])
		var rows []tableRow
		j := i + 2
		for j < len(lines) && strings.HasPrefix(strings.TrimLeft(lines[j], " \t"), "|") {
			rows = append(rows, tableRow{line: j + 1, cells: cells(lines[j])})
			j++
		}
		return header, rows
	}
	return nil, nil
}

// colIdx 在表头里按关键词组定位列索引。任一关键词命中即返回。
// 用于表头列顺序不固定时按语义定位。对齐 req.py 的 col_idx。
func colIdx(header []string, keywords ...string) int {
	for _, kw := range keywords {
		for i, c := range header {
			if strings.Contains(c, kw) {
				return i
			}
		}
	}
	return -1
}

// parseDeps 解析依赖列文本，返回归一化的 T-id 列表。
// 容错支持 'T1' / 'T2,T3' / 'T2/T3' / '#1 #2' / 'None' / ''。
// 对齐 req.py 的 parse_deps。
func parseDeps(raw string) []string {
	if raw == "" || strings.TrimSpace(raw) == "None" {
		return nil
	}
	var ids []string
	for _, m := range taskIDRe.FindAllStringSubmatch(raw, -1) {
		ids = append(ids, "T"+m[1])
	}
	return ids
}

// taskEngineStatus 从状态列文本判定引擎状态（done/todo/blocked）。
// 判定顺序：先看 [x]/[!] token，再看 emoji，最后默认 todo。
// 对齐 req.py 的 task_engine_status。
func taskEngineStatus(rawStatus string) string {
	if m := tokenRe.FindStringSubmatch(rawStatus); m != nil {
		switch m[1] {
		case "x":
			return StatusDone
		case "!":
			return StatusBlocked
		default:
			return StatusTodo
		}
	}
	for emoji, status := range statusEmojiMap {
		if strings.Contains(rawStatus, emoji) {
			return status
		}
	}
	return StatusTodo
}

// isLegalStatus 判定状态列文本是否落在引擎复用的词表内。
// 已定义 token（[x]/[ ]/[!]）或兼容 emoji 之一都算合法。用于 R3Q7。
// 对齐 req.py 的 is_legal_status。
func isLegalStatus(rawStatus string) bool {
	if tokenRe.MatchString(rawStatus) {
		return true
	}
	for emoji := range statusEmojiMap {
		if strings.Contains(rawStatus, emoji) {
			return true
		}
	}
	return false
}

// normalizeModuleName 归一化模块标签，供 R3Q9 做边界表↔mermaid 词法双向比对。
// 去掉 <br>、·分隔、冒号后缀、代码标记，只保留字母数字和 CJK，转小写。
// 对齐 req.py 的 normalize_module_name。
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

// mermaidModules 提取所有 ```mermaid 围栏块里的节点标签。
// 返回 normalized → original 的映射，供 diagram 一致性检查比对。
// 对齐 req.py 的 mermaid_modules。
func mermaidModules(text string) map[string]string {
	lines := strings.Split(strings.ReplaceAll(strings.ReplaceAll(text, "\r\n", "\n"), "\r", "\n"), "\n")
	names := map[string]string{}
	inMermaid := false
	for _, line := range lines {
		stripped := strings.TrimLeft(line, " \t")
		if strings.HasPrefix(stripped, "```") {
			marker := strings.TrimSpace(stripped[3:])
			if inMermaid {
				inMermaid = false
			} else if strings.ToLower(marker) == "mermaid" {
				inMermaid = true
			}
			continue
		}
		if !inMermaid {
			continue
		}
		for _, m := range mermaidLabelRe.FindAllStringSubmatch(line, -1) {
			// 4 个捕获组对应 4 种括号语法，取第一个非空的。
			for _, g := range m[1:] {
				if g != "" {
					original := strings.TrimSpace(g)
					normalized := normalizeModuleName(original)
					if normalized != "" {
						names[normalized] = original
					}
					break
				}
			}
		}
	}
	return names
}

// parsedRow 是 parseChecklist 解析出的单行任务结构。
// 对齐 req.py parse_checklist 返回的 dict。
type parsedRow struct {
	ID        string   // 归一化 T-id（如 T1）
	Title     string   // 任务说明列
	Scenario  *string  // Scenario IDs 列（nil 表示表头无此列，区别于空串）
	Risk      string   // 风险列
	Deps      []string // 解析后的依赖 T-id 列表
	RawStatus string   // 状态列原始文本
	Product   string   // 从涉及文件列提取的 product: 锚点（空表示无锚点）
	Line      int      // 原始行号（1-based）
}

// parseScenarioIDs 解析 checklist 的 Scenario IDs 单元格。
// 格式必须是 SC_01 或 SC_01, SC_02；纯技术行写 None。
// 对齐 req.py 的 parse_scenario_ids（遇错抛出，由调用方转成 issue）。
func parseScenarioIDs(value string) ([]string, error) {
	value = strings.TrimSpace(value)
	if value == "None" {
		return nil, nil
	}
	if !scenarioIDsCellRe.MatchString(value) {
		return nil, errf("Scenario IDs 必须为 SC_01 或 SC_01, SC_02；纯技术行写 None")
	}
	parts := strings.Split(value, ",")
	ids := make([]string, 0, len(parts))
	seen := map[string]bool{}
	for _, p := range parts {
		id := strings.TrimSpace(p)
		if seen[id] {
			return nil, errf("Scenario IDs 单元格存在重复 ID")
		}
		seen[id] = true
		ids = append(ids, id)
	}
	return ids, nil
}

// parseChecklist 解析 dev-checklist.md 的任务表。
// 表头缺关键列（id/status）时抛错；Scenario 列缺失会在每行的 Scenario 字段保留 nil。
// 对齐 req.py 的 parse_checklist。
func parseChecklist(taskDir string) ([]parsedRow, error) {
	checklist := taskDir + "/dev-checklist.md"
	info, err := os.Stat(checklist)
	if err != nil || info.IsDir() {
		return nil, errf("缺少 dev-checklist.md：%s", taskDir)
	}
	text, err := readText(checklist)
	if err != nil {
		return nil, err
	}
	header, rows := firstTable(text)
	if header == nil {
		return nil, errf("dev-checklist.md 无可解析表格：%s", checklist)
	}

	// 按语义关键词定位每列的索引（-1 表示该列不存在）。
	indexes := map[string]int{}
	for key, keywords := range checklistHeaderKeywords {
		indexes[key] = colIdx(header, keywords...)
	}
	if indexes["id"] == -1 || indexes["status"] == -1 {
		var missing []string
		if indexes["id"] == -1 {
			missing = append(missing, "#/编号 列")
		}
		if indexes["status"] == -1 {
			missing = append(missing, "状态 列")
		}
		return nil, errf("dev-checklist.md 表头缺关键列：%s", strings.Join(missing, ", "))
	}

	// cell 安全取单元格：列索引越界或列不存在时返回空串。
	cell := func(values []string, index int) string {
		if index >= 0 && index < len(values) {
			return strings.TrimSpace(values[index])
		}
		return ""
	}

	var parsed []parsedRow
	for _, row := range rows {
		rawID := cell(row.cells, indexes["id"])
		if rawID == "" || rawID == "None" {
			continue
		}
		match := idColRe.FindStringSubmatch(rawID)
		if match == nil {
			continue
		}
		rawFiles := cell(row.cells, indexes["file"])
		product := ""
		if rawFiles != "" {
			if pm := productRe.FindStringSubmatch(rawFiles); pm != nil {
				product = pm[1]
			}
		}
		// Scenario 列：表头无此列时 Scenario=nil（区别于"有列但空"，后者是空串）。
		var scenario *string
		if indexes["scenario"] >= 0 {
			val := cell(row.cells, indexes["scenario"])
			scenario = &val
		}
		parsed = append(parsed, parsedRow{
			ID:        "T" + match[1],
			Title:     cell(row.cells, indexes["title"]),
			Scenario:  scenario,
			Risk:      cell(row.cells, indexes["risk"]),
			Deps:      parseDeps(cell(row.cells, indexes["dep"])),
			RawStatus: cell(row.cells, indexes["status"]),
			Product:   product,
			Line:      row.line,
		})
	}
	return parsed, nil
}

// errf 是便捷的错误构造（包内专用），格式化中文错误信息。
func errf(format string, args ...any) error {
	return &parseError{msg: sprintf(format, args...)}
}

// parseError 是 parseChecklist 抛出的可识别错误，携带中文消息。
type parseError struct{ msg string }

func (e *parseError) Error() string { return e.msg }
