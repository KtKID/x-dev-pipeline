package req

import _ "embed"

// 模板文件内嵌到二进制，等价于 Python 版通过 SKILL_ROOT/templates/<name> 读取。
// 好处：单二进制自包含，git clone 后无需额外放置模板文件。

//go:embed templates/dev-checklist.md
var devChecklistTemplate string

//go:embed templates/diagram.md
var diagramTemplate string

// artifactEntry 描述一个可 scaffold 的产物。对齐 req.py 的 ARTIFACTS dict。
type artifactEntry struct {
	generates    string // 产物落盘文件名
	template     string // 内嵌模板内容
	instruction  string // 给 agent 的填写说明
}

// artifacts 是 req 引擎能 scaffold 的产物表。
// 键名（"dev-checklist"/"diagram"）是 artifact_id，由 instructions/scaffold 子命令引用。
var artifacts = map[string]artifactEntry{
	"dev-checklist": {
		generates:   "dev-checklist.md",
		template:    devChecklistTemplate,
		instruction: "按 spec Scenario 拆任务；只保存执行信息、风险证据和精确回指。",
	},
	"diagram": {
		generates:   "diagram.md",
		template:    diagramTemplate,
		instruction: "把影响边界表投影为模块图，每个声明模块恰好一个节点。",
	},
}
