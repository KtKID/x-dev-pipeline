// Package spec 实现 skills/x-spec/scripts/spec.py 的等价校验逻辑：
// iteration-7 x-spec 确定性文档校验引擎（元数据、章节、表格、Scenario、对抗性审查）。
//
// 本包是 1:1 移植，规则码（V19/V20）与中文错误信息逐字保留，以便与
// test/test_spec_engine.py 对拍。职责边界：只读，不生成或修改 spec/task 文件。
package spec

import "regexp"

// 与 spec.py 顶层常量逐字对齐。
var (
	HeaderFields = []string{
		"spec_version", "adversarial_risk_version", "complexity",
		"importance", "risk_average", "review_budget", "adversarial_review",
	}
	validBudgets  = map[string]bool{"standard": true, "deep": true, "full": true}
	validStatuses = map[string]bool{"pending": true, "skipped-standard": true, "complete": true}
	modelTuple    = []string{"数据流", "状态", "时序", "资源", "不变量", "故障"}
	requiredSections = []string{
		"任务目标", "非目标", "风险评分依据", "影响边界与不变量",
		"判断依据", "建模覆盖声明", "验收清单", "测试驱动开发",
		"对抗性审查记录", "Scenarios",
	}
	boundaryHeader = []string{"模块", "角色", "本次影响", "主要风险", "必须保持的不变量", "依据"}
	judgmentHeader = []string{"J-ID", "判断", "来源", "证据或推断", "状态"}
	modelHeader    = []string{"维度", "覆盖位置或具体不适用理由"}
	riskBasisFields = []string{"复杂度", "重要性", "预算升级"}
	reviewHeader    = []string{
		"Review", "预算", "风险来源", "查询", "召回 ID",
		"复用 Scenario", "新增 Scenario", "CLI",
	}
)

// 正则与 spec.py 顶层编译逐字对齐。
var (
	specMarkerRe  = regexp.MustCompile(`(?i)^>\s*spec_version:\s*3\s*$`)
	fieldRe       = regexp.MustCompile(`^>\s*([a-z_]+):\s*(.*?)\s*$`)
	h1Re          = regexp.MustCompile(`^#\s+(.+?)\s*$`)
	h2Re          = regexp.MustCompile(`^##\s+(.+?)\s*$`)
	h3Re          = regexp.MustCompile(`^###\s+(.+?)\s*$`)
	tableSepRe    = regexp.MustCompile(`^\s*\|(?:\s*:?-+:?\s*\|)+\s*$`)
	scenarioRe    = regexp.MustCompile(`^###\s+Scenario\s+(SC_[0-9]{2})\s*:\s*(.+?)\s*$`)
	scenarioHeadRe = regexp.MustCompile(`(?i)^###\s+Scenario\b`)
	gwtRe         = regexp.MustCompile(`(?i)^\s*[-*+]\s*\*\*(GIVEN|WHEN|THEN)\*\*\s*[：:]?\s*(.*?)\s*$`)
	layerRe       = regexp.MustCompile(`(?i)^\s*[-*+]?\s*测试层\s*[：:]\s*(unit|smoke|e2e)\s*$`)
	evidenceRe    = regexp.MustCompile(`^\s*[-*+]?\s*依据\s*[：:]\s*(.+?)\s*$`)
	sourceRe      = regexp.MustCompile(`^\s*[-*+]?\s*来源\s*[：:]\s*(.+?)\s*$`)
	v3SourceRe    = regexp.MustCompile(
		`^adversarial-review\s*\((?:rag:(?P<risk_id>AR-\d{3})|assumption:(?P<assumption>[^)]+))\)$`,
	)
	riskIDRe               = regexp.MustCompile(`\bAR-\d{3}\b`)
	reviewRagSourceRe      = regexp.MustCompile(`^RAG:(?P<risk_id>AR-\d{3})$`)
	reviewAssumptionSource = regexp.MustCompile(`^assumption:(?P<assumption>.+)$`)
	reviewIDRe             = regexp.MustCompile(`^ARV-\d+$`)
	judgmentIDRe           = regexp.MustCompile(`^J\d+$`)
)

// Issue 是稳定的校验问题对象，供 CLI 和测试统一消费。对齐 spec.py 的 issue()。
type Issue struct {
	File string `json:"file"`
	Line int    `json:"line"`
	Rule string `json:"rule"`
	Msg  string `json:"msg"`
}

func issue(file string, line int, rule, msg string) Issue {
	return Issue{File: file, Line: line, Rule: rule, Msg: msg}
}

// Scenario 是 _parse_scenarios 解析出的结构化场景。对齐 spec.py 的 dict 形态。
type Scenario struct {
	ID            string
	Name          string
	Line          int
	GWT           map[string]string
	GWTCounts     map[string]int
	Layer         string
	LayerCount    int
	Evidence      string
	EvidenceCount int
	Source        string
	SourceCount   int
}
