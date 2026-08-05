package flag

import (
	"fmt"
	"regexp"
	"strings"
)

// cells 拆分 markdown 表格行。对齐 flag.py 的 cells。
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

// taskEngineStatus 把 token/emoji 状态压缩为 done/todo/blocked。
// 对齐 flag.py 的 task_engine_status。
func taskEngineStatus(rawStatus string) string {
	if m := tokenRe.FindStringSubmatch(rawStatus); m != nil {
		switch strings.ToLower(m[1]) {
		case "x":
			return "done"
		case "!":
			return blocked
		default:
			return "todo"
		}
	}
	if strings.Contains(rawStatus, "🔴") {
		return blocked
	}
	if strings.Contains(rawStatus, "🟢") || strings.Contains(rawStatus, "✅") {
		return "done"
	}
	return "todo"
}

// checklistLayout 解析 checklist 文本，返回保留换行的行切片、首个表数据起点、ID 列、状态列。
// 对齐 flag.py 的 _checklist_layout。
func checklistLayout(text string) ([]string, int, int, int, error) {
	lines := splitLinesKeepEnds(text)
	for index := 0; index < len(lines)-1; index++ {
		if !strings.HasPrefix(strings.TrimLeft(lines[index], " \t"), "|") {
			continue
		}
		// 下一行必须是表格分隔行。
		nextTrimmed := strings.TrimRight(strings.TrimRight(lines[index+1], "\n"), "\r")
		if !tableSepRe.MatchString(nextTrimmed) {
			continue
		}
		header := cells(lines[index])
		// 按关键词定位 ID 列和状态列。
		idIdx := colIdx(header, "#", "编号")
		statusIdx := colIdx(header, "状态")
		if idIdx == -1 || statusIdx == -1 {
			return nil, 0, 0, 0, newFlagError("dev-checklist.md 表头缺少 #/编号 或状态列")
		}
		// 表数据从 index+2 开始（跳过表头和分隔行）。
		return lines, index + 2, idIdx, statusIdx, nil
	}
	return nil, 0, 0, 0, newFlagError("dev-checklist.md 无可解析表格")
}

// colIdx 在表头里按关键词定位列索引。对齐 flag.py 内的 col_idx 闭包。
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

// targetChecklistRows 定位目标 task 的唯一表格行；重复或缺失都作为调用错误。
// 返回 (lines, statusIdx, {taskID: lineIndex})。对齐 flag.py 的 _target_checklist_rows。
func targetChecklistRows(text string, taskIDs []string) ([]string, int, map[string]int, error) {
	lines, rowStart, idIdx, statusIdx, err := checklistLayout(text)
	if err != nil {
		return nil, 0, nil, err
	}
	found := map[string][]int{}
	for _, id := range taskIDs {
		found[id] = nil
	}
	for lineIndex := rowStart; lineIndex < len(lines); lineIndex++ {
		if !strings.HasPrefix(strings.TrimLeft(lines[lineIndex], " \t"), "|") {
			break
		}
		rowCells := cells(lines[lineIndex])
		if idIdx >= len(rowCells) {
			continue
		}
		rawID := regexp.MustCompile("[`*]").ReplaceAllString(rowCells[idIdx], "")
		rawID = strings.TrimSpace(rawID)
		m := idColRe.FindStringSubmatch(rawID)
		if m == nil {
			continue
		}
		// fullmatch 语义：整个 rawID 必须匹配。
		if !fullMatch(idColRe, rawID) {
			continue
		}
		taskID := "T" + m[1]
		if _, ok := found[taskID]; ok {
			found[taskID] = append(found[taskID], lineIndex)
		}
	}
	var missing, duplicate []string
	for _, id := range taskIDs {
		if len(found[id]) == 0 {
			missing = append(missing, id)
		}
		if len(found[id]) > 1 {
			duplicate = append(duplicate, id)
		}
	}
	if len(missing) > 0 {
		return nil, 0, nil, newFlagError("checklist 缺少目标 task：%s", strings.Join(missing, ", "))
	}
	if len(duplicate) > 0 {
		return nil, 0, nil, newFlagError("checklist 目标 task 重复：%s", strings.Join(duplicate, ", "))
	}
	targetRows := map[string]int{}
	for _, id := range taskIDs {
		targetRows[id] = found[id][0]
	}
	return lines, statusIdx, targetRows, nil
}

// downgradeTaskRows 把目标 task 状态单元格降为 `[!] 🔴`，保持行内其他内容与已 blocked 状态。
// 返回 (新文本, 被降级的 task 列表)。对齐 flag.py 的 downgrade_task_rows。
func downgradeTaskRows(text string, taskIDs []string) (string, []string, error) {
	lines, statusIdx, targetRows, err := targetChecklistRows(text, taskIDs)
	if err != nil {
		return "", nil, err
	}
	var downgraded []string
	for _, taskID := range taskIDs {
		lineIndex := targetRows[taskID]
		rawLine := lines[lineIndex]
		newline := ""
		// 保留行尾换行符。
		if strings.HasSuffix(rawLine, "\r\n") {
			rawLine = rawLine[:len(rawLine)-2]
			newline = "\r\n"
		} else if strings.HasSuffix(rawLine, "\n") {
			rawLine = rawLine[:len(rawLine)-1]
			newline = "\n"
		} else if strings.HasSuffix(rawLine, "\r") {
			rawLine = rawLine[:len(rawLine)-1]
			newline = "\r"
		}
		parts := strings.Split(rawLine, "|")
		segmentIndex := statusIdx + 1 // 表格行以 | 开头，首段为空，所以状态列对应 statusIdx+1
		if segmentIndex >= len(parts)-1 {
			return "", nil, newFlagError("checklist 的 %s 状态单元格缺失", taskID)
		}
		oldSegment := parts[segmentIndex]
		oldStatus := strings.TrimSpace(oldSegment)
		if taskEngineStatus(oldStatus) == blocked {
			continue // 已 blocked 的行不重复降级
		}
		// 提取原前导/尾随空白，保持对齐。
		spacing := regexp.MustCompile(`(\s*).*?(\s*)`).FindStringSubmatch(oldSegment)
		leading := " "
		trailing := " "
		if spacing != nil {
			if spacing[1] != "" {
				leading = spacing[1]
			}
			if spacing[2] != "" {
				trailing = spacing[2]
			}
		}
		parts[segmentIndex] = leading + "[!] 🔴" + trailing
		lines[lineIndex] = strings.Join(parts, "|") + newline
		downgraded = append(downgraded, taskID)
	}
	return strings.Join(lines, ""), downgraded, nil
}

// splitLinesKeepEnds 保留换行符的拆行。对齐 Python splitlines(keepends=True)。
func splitLinesKeepEnds(text string) []string {
	// Python 的 keepends 保留每行结尾的换行符（含最后一行若没有换行则不保留）。
	// 这里手动实现以精确匹配 \n / \r\n / \r。
	var lines []string
	start := 0
	for i := 0; i < len(text); i++ {
		c := text[i]
		if c == '\n' {
			lines = append(lines, text[start:i+1])
			start = i + 1
		} else if c == '\r' {
			if i+1 < len(text) && text[i+1] == '\n' {
				lines = append(lines, text[start : i+2])
				start = i + 2
				i++
			} else {
				lines = append(lines, text[start:i+1])
				start = i + 1
			}
		}
	}
	if start < len(text) {
		lines = append(lines, text[start:])
	}
	return lines
}

// _ 占位引用（避免删错 helper）。
var _ = fmt.Sprintf
