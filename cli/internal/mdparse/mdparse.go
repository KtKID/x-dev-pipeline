// Package mdparse 提供 xdev 各 engine 共享的 Markdown 解析能力。
//
// 收敛 Python 版散落在 req/spec/validator/flag/risk_contract/corpus 等 7 个脚本里
// 各自重复实现的表格、围栏块、元数据解析逻辑，提供语义一致的单一实现。
package mdparse

import (
	"regexp"
	"strings"
)

// Table 表示一个 Markdown 表格，与 validate_report.py 的 Table dataclass 对齐。
type Table struct {
	Headers  []string
	Rows     [][]string
	Severity string // 当前所在的 ### Pn 段落（可选），由调用方语义注入
}

// Cells 拆分一行 Markdown 表格为单元格，与 Python 版 _cells 对齐：
// 先去首尾空白、再 strip 两端的竖线、最后按 | 切分并 strip 每段。
func Cells(line string) []string {
	trimmed := strings.TrimSpace(line)
	trimmed = strings.TrimPrefix(trimmed, "|")
	trimmed = strings.TrimSuffix(trimmed, "|")
	parts := strings.Split(trimmed, "|")
	out := make([]string, len(parts))
	for i, p := range parts {
		out[i] = strings.TrimSpace(p)
	}
	return out
}

// SepCellRe 匹配表格分隔行单元格（:?-{3,}:?），与 _is_separator 对齐。
var SepCellRe = regexp.MustCompile(`^:?-{3,}:?$`)

// IsSeparator 判断一组单元格是否构成表格分隔行。
func IsSeparator(cells []string) bool {
	if len(cells) == 0 {
		return false
	}
	for _, c := range cells {
		if !SepCellRe.MatchString(c) {
			return false
		}
	}
	return true
}

// IsTableSepLine 判断一整行是否是表格分隔行（带前后 |）。
// 对齐 flag.py 的 TABLE_SEP_RE: ^\s*\|[\s:|-]+\|\s*$。
var TableSepLineRe = regexp.MustCompile(`^\s*\|[\s:|-]+\|\s*$`)

// IsTableSepLine 判断一行是否为表格分隔行（仅基于字符集，与 flag.py 一致）。
func IsTableSepLine(line string) bool {
	return TableSepLineRe.MatchString(line)
}

// RowValue 按表头名取行单元格值，列不存在返回空串与 false。
// 对齐 Python 版 _row_value（找不到时返回 None）。
func RowValue(t *Table, row []string, header string) (string, bool) {
	for i, h := range t.Headers {
		if h == header {
			if i < len(row) {
				return row[i], true
			}
			return "", true
		}
	}
	return "", false
}

// Section 提取 `## <heading>` 到下一个 `## ` 或文末之间的内容（不含标题行）。
// 对齐 validate_report.py / spec.py 的 _section：^## heading\s*$ 后的非贪婪内容。
//
// 注意：headings 不做正则转义以外的处理；调用方应传入字面标题文本。
func Section(text, heading string) (string, bool) {
	pattern := `(?ms)^## ` + regexp.QuoteMeta(heading) + `\s*$([\s\S]*?)(?:^## |\z)`
	re := regexp.MustCompile(pattern)
	m := re.FindStringSubmatch(text)
	if m == nil {
		return "", false
	}
	return m[1], true
}

// Tables 提取一个 section 文本中的所有 Markdown 表格。
// 与 validate_report.py 的 _tables 对齐：连续以 | 开头的行块，首行是表头，
// 第二行必须是分隔行；列数与表头不一致的行被丢弃。
func Tables(section string) []*Table {
	lines := strings.Split(section, "\n")
	var result []*Table
	i := 0
	for i < len(lines) {
		if !strings.HasPrefix(strings.TrimLeft(lines[i], " \t"), "|") {
			i++
			continue
		}
		var block [][]string
		for i < len(lines) && strings.HasPrefix(strings.TrimLeft(lines[i], " \t"), "|") {
			block = append(block, Cells(lines[i]))
			i++
		}
		if len(block) >= 2 && IsSeparator(block[1]) {
			width := len(block[0])
			rows := make([][]string, 0, len(block)-2)
			for _, row := range block[2:] {
				if len(row) == width {
					rows = append(rows, row)
				}
			}
			result = append(result, &Table{Headers: block[0], Rows: rows})
		}
	}
	return result
}
