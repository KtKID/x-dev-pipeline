package req

import "regexp"

// ===== 状态常量 =====
//
// task 引擎把状态列文本压缩为三种引擎状态，供 status/graph 复用。
// 对齐 req.py 的 DONE/TODO/BLOCKED 常量。

const (
	StatusDone    = "done"
	StatusTodo    = "todo"
	StatusBlocked = "blocked"
)

// RISK_VALUES 是 dev-checklist 头部 `> risk:` 的合法取值。
// Q0/Q1 = 低风险（可跳过对抗审查）；Q2/Q3 = 高风险（需走完整流程）。
var riskValues = map[string]bool{"Q0": true, "Q1": true, "Q2": true, "Q3": true}

// ===== 正则 =====
//
// 与 req.py 顶层编译逐字对齐。命名沿用 Python 语义，便于对照源码。

var (
	// tableSepRe 匹配 markdown 表格分隔行（仅基于字符集），用于 first_table 定位表头。
	// 对齐 TABLE_SEP_RE: ^\s*\|[\s:|-]+\|\s*$
	tableSepRe = regexp.MustCompile(`^\s*\|[\s:|-]+\|\s*$`)

	// specLineRe / riskLineRe 匹配 checklist 头部的 `> spec:` / `> risk:` 指针行。
	// spec 指针必须指向含 spec_version: 3 的单文件规格包；risk 决定该 task 走哪条审查路径。
	specLineRe = regexp.MustCompile(`(?i)^>\s*spec:\s*(\S+)\s*$`)
	riskLineRe = regexp.MustCompile(`(?i)^>\s*risk:\s*(\S+)\s*$`)

	// taskIDRe 匹配依赖列里的 task id（T1/#1 等都算），用于 parse_deps 容错解析。
	taskIDRe = regexp.MustCompile(`(?i)(?:T|#)(\d+)`)
	// idColRe 匹配表格 ID 列单元格里的数字（兼容 T1/#1/1 等写法）。
	idColRe = regexp.MustCompile(`(?i)(?:T|#)?(\d+)`)

	// productRe 从"涉及文件"列里提取 product:<path> 锚点。
	// 用于 resolve_task_list 的产物交叉验证：done 但 product 缺失 → missing；todo 但 product 已存在 → stale。
	productRe = regexp.MustCompile(`product:\s*([^\s,;]+)`)

	// tokenRe 匹配状态列的 [x]/[ ]/[!] 复选框 token。对齐 TOKEN_RE。
	tokenRe = regexp.MustCompile(`\[(?P<box>[ x!])\]`)

	// scenarioIDsCellRe 校验 checklist 的 Scenario IDs 单元格格式：
	// 必须是 SC_01 或 SC_01, SC_02（逗号分隔、两位数字）。纯技术行写 None。
	scenarioIDsCellRe = regexp.MustCompile(`^SC_[0-9]{2}(?:\s*,\s*SC_[0-9]{2})*$`)

	// mermaidLabelRe 提取 mermaid 图里的节点标签，用于 diagram 一致性检查（R3Q9）。
	// 匹配 Node["label"] / Node[label] / Node("label") / Node(label) 等形态。
	mermaidLabelRe = regexp.MustCompile(
		`\b[A-Za-z_][A-Za-z0-9_]*\s*(?:\[\s*"([^"]+)"\s*\]|\[\s*([^\]]+)\s*\]|\(\s*"([^"]+)"\s*\)|\(\s*([^\)]+)\s*\))`,
	)
)

// statusEmojiMap 把 emoji 映射到引擎状态（token 优先、emoji 降级兼容）。
// 对齐 req.py 的 STATUS_EMOJI_MAP。
var statusEmojiMap = map[string]string{
	"🟢": StatusDone,
	"✅": StatusDone,
	"🔴": StatusBlocked,
}

// checklistHeaderKeywords 描述 checklist 表头列名的关键词匹配规则。
// 每个逻辑列允许一组同义词（如 id 列可以是 "#" 或 "编号"），
// 用于在表头顺序不固定时按语义定位列。
// 对齐 req.py 的 CHECKLIST_HEADER_KEYWORDS。
var checklistHeaderKeywords = map[string][]string{
	"id":       {"#", "编号"},
	"title":    {"任务说明", "任务", "标题"},
	"scenario": {"Scenario"},
	"risk":     {"风险"},
	"file":     {"涉及文件", "文件"},
	"dep":      {"依赖"},
	"status":   {"状态"},
}

// Issue 是 req 引擎的校验问题对象。对齐 req.py 的 issue() dict。
// 字段名（file/line/rule/msg）与 spec.py 一致，便于 validator 统一聚合。
type Issue struct {
	File string `json:"file"`
	Line int    `json:"line"`
	Rule string `json:"rule"`
	Msg  string `json:"msg"`
}

// newIssue 构造一个 Issue。对齐 req.py 的 issue() 辅助函数。
func newIssue(file string, line int, rule, msg string) Issue {
	return Issue{File: file, Line: line, Rule: rule, Msg: msg}
}
