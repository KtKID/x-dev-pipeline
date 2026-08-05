package req

import (
	"fmt"
	"path/filepath"

	specpkg "github.com/KtKID/x-dev-pipeline/cli/internal/engine/spec"
)

// ValidateIssues 聚合 task 目录的全部 R3Q 机械校验。
// 这是 xdev validate <task-dir> 对 req-task 的核心入口。
// 对齐 req.py 的 validate_issues。
func ValidateIssues(taskDir string) []Issue {
	checklist := filepath.Join(taskDir, "dev-checklist.md")
	if !fileExists(checklist) {
		// R3Q0：task 目录必须有 dev-checklist.md。
		return []Issue{newIssue(taskDir, 0, "R3Q0", "缺少 dev-checklist.md")}
	}
	text, _ := readText(checklist)
	var issues []Issue

	// R3Q1：头部 `> spec:` 指针必须存在、且与 task 实际归属 spec 一致。
	specValue := headerValue(text, "spec")
	specDir := resolveSpecDir(taskDir)
	declared := specOfTaskDir(taskDir)
	if specValue == "" {
		issues = append(issues, newIssue(checklist, 0, "R3Q1", "头部缺少 spec: 指针"))
	} else if specDir == "" {
		issues = append(issues, newIssue(checklist, 0, "R3Q1", "task 上级缺少合法 spec_version: 3 spec.md"))
	} else if declared != "" && specValue != declared {
		// 指针写 docs/spec/a 但 task 实际在 docs/spec/b → 指针不一致。
		issues = append(issues, newIssue(checklist, 0, "R3Q1",
			fmt.Sprintf("spec: 指针与 task 实际归属不符：头部写「%s」，实际位于「%s」", specValue, declared)))
	}

	// R3Q2：头部 `> risk:` 必须是 Q0/Q1/Q2/Q3 之一。
	riskValue := headerValue(text, "risk")
	if riskValue == "" {
		issues = append(issues, newIssue(checklist, 0, "R3Q2", "头部缺少 risk: 取值"))
	} else if !riskValues[toUpperCase(riskValue)] {
		issues = append(issues, newIssue(checklist, 0, "R3Q2", fmt.Sprintf("risk: 取值非法：%s", riskValue)))
	}

	// R3Q10：归属 spec 自己必须先通过 spec 校验（透传 spec 的所有 issue）。
	if specDir != "" {
		for _, specIss := range specpkg.ValidateIssues(specDir, true) {
			issues = append(issues, newIssue(checklist, 0, "R3Q10",
				fmt.Sprintf("归属 spec 未就绪：%s", specIss.Msg)))
		}
	}

	// R3Q3-R3Q8：解析任务表，逐行校验。
	rows, err := parseChecklist(taskDir)
	if err != nil {
		// 表头缺关键列或无表 → R3Q3。
		issues = append(issues, newIssue(checklist, 0, "R3Q3", err.Error()))
		return issues
	}

	// 统计 spec.md 中每个 Scenario ID 的出现次数，用于 R3Q5 悬空/重复检查。
	var scenarioCounts map[string]int
	if specDir != "" {
		scenarioCounts = specpkg.ScenarioIDCounts(filepath.Join(specDir, "spec.md"))
	}
	knownIDs := map[string]bool{}
	for _, row := range rows {
		knownIDs[row.ID] = true
	}

	for _, row := range rows {
		// R3Q4：任务说明、风险列不能空。
		if row.Title == "" {
			issues = append(issues, newIssue(checklist, row.Line, "R3Q4", fmt.Sprintf("%s 任务说明为空", row.ID)))
		}
		if row.Risk == "" {
			issues = append(issues, newIssue(checklist, row.Line, "R3Q4", fmt.Sprintf("%s 风险列为空", row.ID)))
		}
		// R3Q8：依赖列指向的 task 必须在表里。
		for _, dep := range row.Deps {
			if !knownIDs[dep] {
				issues = append(issues, newIssue(checklist, row.Line, "R3Q8",
					fmt.Sprintf("%s 依赖「%s」不在 task 表中", row.ID, dep)))
			}
		}
		// R3Q7：状态列必须是合法 token/emoji。
		if !isLegalStatus(row.RawStatus) {
			status := row.RawStatus
			if status == "" {
				status = "(空)"
			}
			issues = append(issues, newIssue(checklist, row.Line, "R3Q7",
				fmt.Sprintf("%s 状态非法：%s", row.ID, status)))
		}
		// R3Q5：Scenario IDs 列的格式与悬空/重复检查。
		if row.Scenario == nil {
			// 表头无 Scenario 列。
			issues = append(issues, newIssue(checklist, row.Line, "R3Q3", "表头缺 Scenario IDs 列"))
			continue
		}
		if *row.Scenario == "" {
			issues = append(issues, newIssue(checklist, row.Line, "R3Q5",
				fmt.Sprintf("%s Scenario IDs 为空；纯技术行须写 None", row.ID)))
			continue
		}
		referenced, perr := parseScenarioIDs(*row.Scenario)
		if perr != nil {
			issues = append(issues, newIssue(checklist, row.Line, "R3Q5",
				fmt.Sprintf("%s %s", row.ID, perr.Error())))
			continue
		}
		if len(referenced) == 0 || scenarioCounts == nil {
			// None 行（纯技术任务）或无 spec 上下文 → 跳过悬空检查。
			continue
		}
		for _, sid := range referenced {
			count := scenarioCounts[sid]
			if count == 0 {
				// checklist 声明了 spec 里不存在的 Scenario。
				issues = append(issues, newIssue(checklist, row.Line, "R3Q5",
					fmt.Sprintf("%s Scenario ID 悬空：「%s」不在 %s/spec.md 中", row.ID, sid, specValue)))
			} else if count > 1 {
				// spec.md 里同 ID 出现多次（spec 自己的重复，这里只上报）。
				issues = append(issues, newIssue(checklist, row.Line, "R3Q5",
					fmt.Sprintf("%s Scenario ID 重复：「%s」在 spec.md 中出现 %d 次", row.ID, sid, count)))
			}
		}
	}

	// R3Q9：diagram.md 的 mermaid 节点必须与 spec 影响边界表一致。
	issues = append(issues, diagramConsistencyIssues(taskDir, specDir)...)
	return issues
}

// diagramConsistencyIssues 校验 diagram.md 与 spec 影响边界表的一致性。
// 规则：影响边界 ≥3 模块时必须有 diagram.md；有 diagram.md 时节点集合必须与边界表一致。
// 对齐 req.py 的 diagram_consistency_issues。
func diagramConsistencyIssues(taskDir string, specDir string) []Issue {
	if specDir == "" {
		return nil
	}
	diagram := filepath.Join(taskDir, "diagram.md")
	declared := specpkg.BoundaryModuleNames(specDir)
	if len(declared) >= 3 && !fileExists(diagram) {
		return []Issue{newIssue(taskDir, 0, "R3Q9",
			fmt.Sprintf("影响边界包含 %d 个模块，task 缺少必需的 diagram.md", len(declared)))}
	}
	if !fileExists(diagram) {
		return nil
	}
	text, _ := readText(diagram)
	rendered := mermaidModules(text)
	var issues []Issue
	// 边界表声明了但 mermaid 没画 → 缺节点。
	for name := range declared {
		if _, ok := rendered[name]; !ok {
			issues = append(issues, newIssue(diagram, 0, "R3Q9",
				fmt.Sprintf("影响边界模块「%s」缺少 Mermaid 节点", declared[name])))
		}
	}
	// mermaid 画了但边界表没声明 → 多余节点。
	for name := range rendered {
		if _, ok := declared[name]; !ok {
			issues = append(issues, newIssue(diagram, 0, "R3Q9",
				fmt.Sprintf("Mermaid 节点「%s」未在影响边界表声明", rendered[name])))
		}
	}
	return issues
}

// SpecScenarioCoverage 检查 spec 的每个 Scenario 是否被其下任一 task 承接。
// 防止"spec 定义了 5 个场景但 task 只覆盖 3 个"。
// 对齐 req.py 的 spec_scenario_coverage。
func SpecScenarioCoverage(specDir string) []Issue {
	specMD := filepath.Join(specDir, "spec.md")
	// spec 场景列表（去重保序，取自 specpkg.Scenarios）。
	var scenarioIDs []string
	seen := map[string]bool{}
	for _, sc := range specpkg.SpecScenarios(specMD) {
		if !seen[sc.ID] {
			seen[sc.ID] = true
			scenarioIDs = append(scenarioIDs, sc.ID)
		}
	}
	covered := map[string]bool{}
	tasksDir := filepath.Join(specDir, "tasks")
	entries, err := readDirSorted(tasksDir)
	if err != nil {
		return nil
	}
	// 遍历每个 task 目录，收集它们承接的 Scenario ID。
	for _, taskName := range entries {
		rows, perr := parseChecklist(filepath.Join(tasksDir, taskName))
		if perr != nil {
			continue
		}
		for _, row := range rows {
			if row.Scenario == nil || *row.Scenario == "" || *row.Scenario == "None" {
				continue
			}
			ids, perr := parseScenarioIDs(*row.Scenario)
			if perr != nil {
				continue
			}
			for _, id := range ids {
				covered[id] = true
			}
		}
	}
	var issues []Issue
	for _, sid := range scenarioIDs {
		if !covered[sid] {
			issues = append(issues, newIssue(specMD, 0, "R3Q6",
				fmt.Sprintf("Scenario「%s」未被该 spec 下任何 task 承接", sid)))
		}
	}
	return issues
}

// TaskScenarios 返回 task checklist 里所有行声明的 Scenario ID（去重保序）。
// 对齐 req.py 的 task_scenarios。
func TaskScenarios(taskDir string) ([]string, error) {
	rows, err := parseChecklist(taskDir)
	if err != nil {
		return nil, err
	}
	var ids []string
	seen := map[string]bool{}
	for _, row := range rows {
		if row.Scenario == nil {
			return nil, fmt.Errorf("dev-checklist.md 表头缺 Scenario IDs 列：%s", taskDir)
		}
		if *row.Scenario == "" {
			return nil, fmt.Errorf("dev-checklist.md 第 %d 行 %s 的 Scenario IDs 为空；纯技术行须显式写 None", row.Line, row.ID)
		}
		parsed, perr := parseScenarioIDs(*row.Scenario)
		if perr != nil {
			return nil, perr
		}
		for _, id := range parsed {
			if !seen[id] {
				seen[id] = true
				ids = append(ids, id)
			}
		}
	}
	return ids, nil
}
