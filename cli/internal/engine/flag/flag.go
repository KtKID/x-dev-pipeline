package flag

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// CommandResult 是 FlagCommand 的输出。
type CommandResult struct {
	Issue      string   `json:"issue"`
	Downgraded []string `json:"downgraded"`
	Report     string   `json:"report"`
	Recovered  bool     `json:"recovered"`
}

// emitResult 输出结果到 stdout（文本或 JSON）。对齐 flag.py 的 _emit_flag_result。
func emitResult(result *transactionResult, asJSON bool) {
	if asJSON {
		out, _ := json.Marshal(CommandResult{
			Issue:      result.Issue,
			Downgraded: result.Downgraded,
			Report:     result.Report,
			Recovered:  result.Recovered,
		})
		fmt.Println(string(out))
		return
	}
	verb := "已登记"
	if result.Recovered {
		verb = "已恢复"
	}
	downgraded := joinStr(result.Downgraded, ",")
	if downgraded == "" {
		downgraded = "无"
	}
	fmt.Printf("%s %s → %s；降级：%s\n", verb, result.Issue, result.Report, downgraded)
}

// FlagCommand 是 flag 子命令的主入口：恢复 → 校验 → 生成 → 双目标事务提交。
// 返回退出码：0 成功；2 用法/校验/IO 错误。对齐 flag.py 的 flag_command。
func FlagCommand(
	taskDir, taskArg, severity, loc, msg string,
	newRound bool, asJSON bool,
) int {
	// 1. 优先恢复 pending 事务（幂等）。
	recovered, err := recoverFlagTransaction(taskDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误：%v\n", err)
		return 2
	}
	if recovered != nil {
		emitResult(recovered, asJSON)
		return 0
	}

	// 2. 校验 task 目录存在。
	info, err := os.Stat(taskDir)
	if err != nil || !info.IsDir() {
		fmt.Fprintf(os.Stderr, "错误：不是 task 目录：%s\n", taskDir)
		return 2
	}

	// 3. 归一化 + 校验参数。
	taskIDs, sev, normalizedLoc, normalizedMsg, err := NormalizeInputs(taskArg, severity, loc, msg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误：%v\n", err)
		return 2
	}

	// 4. 读 checklist。
	checklistPath := filepath.Join(taskDir, "dev-checklist.md")
	checklistBytes, err := os.ReadFile(checklistPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误：读取 dev-checklist.md 失败：%v\n", err)
		return 2
	}
	checklistText := string(checklistBytes)

	// 5. 定位目标行（P2 也需要校验目标唯一性）。
	if _, _, _, err := targetChecklistRows(checklistText, taskIDs); err != nil {
		fmt.Fprintf(os.Stderr, "错误：%v\n", err)
		return 2
	}

	// 6. 降级状态（仅 P0/P1；P2 只登记不降级）。
	var newChecklist string
	var downgraded []string
	if sev == "P0" || sev == "P1" {
		newChecklist, downgraded, err = downgradeTaskRows(checklistText, taskIDs)
		if err != nil {
			fmt.Fprintf(os.Stderr, "错误：%v\n", err)
			return 2
		}
	} else {
		newChecklist = checklistText
		downgraded = nil
	}

	// 7. 解析/创建 report ledger。
	reportPath, reportText, reportBeforeSHA, err := resolveCurrentReport(
		filepath.Join(taskDir, "reports", "qa-gate"), newRound, time.Now())
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误：%v\n", err)
		return 2
	}

	// 8. 分配 issue id 并追加行。
	issueID := nextIssueID(reportText)
	entry := issueEntry{
		Issue:    issueID,
		Tasks:    taskIDs,
		Severity: sev,
		Loc:      normalizedLoc,
		Msg:      normalizedMsg,
	}
	newReport := appendIssueLine(reportText, entry)
	result := transactionResult{
		Issue:      issueID,
		Downgraded: downgraded,
		Report:     filepath.Base(reportPath),
		Recovered:  false,
	}

	// 9. 双目标原子提交。
	checklistBeforeSHA := sha256Bytes(checklistBytes)
	committed, err := commitFlagTransaction(
		taskDir, checklistPath, newChecklist,
		reportPath, newReport, result,
		checklistBeforeSHA, reportBeforeSHA,
	)
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误：%v\n", err)
		return 2
	}
	if downgraded == nil {
		committed.Downgraded = []string{} // 保证 JSON []
	}
	emitResult(committed, asJSON)
	return 0
}
