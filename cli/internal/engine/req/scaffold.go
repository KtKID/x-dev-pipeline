package req

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	specpkg "github.com/KtKID/x-dev-pipeline/cli/internal/engine/spec"
)

// InstructionPayload 是 instructions 命令返回的产物填写说明。
// 对齐 req.py 的 artifact_payload dict。
type InstructionPayload struct {
	Artifact     string   `json:"artifact"`
	OutputPath   string   `json:"output_path"`
	Exists       bool     `json:"exists"`
	Template     string   `json:"template"`
	Instruction  string   `json:"instruction"`
	Requires     []string `json:"requires"`
	Dependencies []string `json:"dependencies"`
	Profile      string   `json:"profile"`
}

// Instructions 返回某产物的填写说明（模板内容 + 指令）。
// artifactID 必须是 "dev-checklist" 或 "diagram"。
// 对齐 req.py 的 instructions（as_json=false 分支由调用方 CLI 决定）。
func Instructions(artifactID, taskDir string, asJSON bool) (int, error) {
	entry, ok := artifacts[artifactID]
	if !ok {
		return 2, fmt.Errorf("req 不支持 artifact「%s」", artifactID)
	}
	payload := InstructionPayload{
		Artifact:     artifactID,
		OutputPath:   filepath.Join(taskDir, entry.generates),
		Exists:       fileExists(filepath.Join(taskDir, entry.generates)),
		Template:     entry.template,
		Instruction:  entry.instruction,
		Requires:     []string{},
		Dependencies: []string{},
		Profile:      "req",
	}
	if asJSON {
		out, _ := json.MarshalIndent(payload, "", "  ")
		fmt.Println(string(out))
	} else {
		fmt.Printf("== %s instructions [req]\n\n", artifactID)
		fmt.Println(payload.Template)
		fmt.Printf("\n== instruction\n\n%s\n", payload.Instruction)
	}
	return 0, nil
}

// ScaffoldResult 是 scaffold 命令返回的创建结果。
type ScaffoldResult struct {
	Task    string   `json:"task"`
	Spec    string   `json:"spec"`
	Profile string   `json:"profile"`
	Created []string `json:"created"`
	Skipped []string `json:"skipped"`
}

// Scaffold 为 task 目录增量创建骨架文件（dev-checklist.md、可选 diagram.md）。
//
// 前置门禁：必须位于含 spec_version: 3 的 docs/spec/<spec>/tasks/<task>/，
// 且归属 spec 已通过就绪门禁（spec_contract_issues 为空），否则拒绝创建。
//
// diagram 自动创建规则：当 spec 的影响边界表声明 ≥3 个模块时，强制生成 diagram.md。
// 对齐 req.py 的 scaffold。
func Scaffold(taskDir string, withDiagram, asJSON bool) (int, error) {
	specPath := specOfTaskDir(taskDir)
	specDir := resolveSpecDir(taskDir)
	if specPath == "" || specDir == "" {
		return 2, fmt.Errorf("%s 必须位于含 spec_version: 3 的 docs/spec/<spec>/tasks/<task>/", taskDir)
	}

	// 就绪门禁：spec 自己必须先通过 spec 校验（含 pending 阻断、判断待确认等）。
	readinessIssues := specpkg.ValidateIssues(specDir, true)
	if len(readinessIssues) > 0 {
		var msgs []string
		for _, iss := range readinessIssues {
			msgs = append(msgs, iss.Msg)
		}
		return 2, fmt.Errorf("spec 未通过就绪门禁：%s", strings.Join(msgs, "；"))
	}

	// diagram 必要性：影响边界 ≥3 个模块时强制生成（R3Q9 会检查一致性）。
	declaredModules := specpkg.BoundaryModuleNames(specDir)
	diagramRequired := len(declaredModules) >= 3

	artifactIDs := []string{"dev-checklist"}
	if withDiagram || diagramRequired {
		artifactIDs = append(artifactIDs, "diagram")
	}

	result := ScaffoldResult{
		Task:    taskDir,
		Spec:    specPath,
		Profile: "req",
		Created: []string{},
		Skipped: []string{},
	}

	// 增量创建：已存在的文件跳过（skipped），不覆盖。
	if err := os.MkdirAll(taskDir, 0o755); err != nil {
		return 2, fmt.Errorf("scaffold 无法写入 %s：%v", taskDir, err)
	}
	for _, id := range artifactIDs {
		entry := artifacts[id]
		path := filepath.Join(taskDir, entry.generates)
		if fileExists(path) {
			result.Skipped = append(result.Skipped, path)
			continue
		}
		content := entry.template
		if id == "dev-checklist" {
			// dev-checklist 模板里的占位符替换为实际值：标题用 task 目录名，spec 指针用归属路径。
			content = strings.Replace(content, "# <task-name>", "# "+filepath.Base(taskDir), 1)
			content = strings.Replace(content, "> spec: docs/spec/<spec-name>", "> spec: "+specPath, 1)
		} else {
			// diagram 模板用 <TASK_NAME> 占位符。
			content = strings.Replace(content, "<TASK_NAME>", filepath.Base(taskDir), 1)
		}
		if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
			return 2, fmt.Errorf("scaffold 无法写入 %s：%v", taskDir, err)
		}
		result.Created = append(result.Created, path)
	}

	if asJSON {
		// 保持 created/skipped 非 nil（JSON [] 而非 null）。
		out, _ := json.MarshalIndent(result, "", "  ")
		fmt.Println(string(out))
	} else {
		fmt.Printf("== scaffold %s [req]\n", taskDir)
		for _, p := range result.Created {
			fmt.Printf("  created: %s\n", p)
		}
		for _, p := range result.Skipped {
			fmt.Printf("  skipped: %s\n", p)
		}
	}
	return 0, nil
}

// fileExists 判断路径是否是已存在的普通文件。
func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}
