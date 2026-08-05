package main

import (
	"fmt"
	"os"

	"github.com/KtKID/x-dev-pipeline/cli/internal/engine/verify"
	"github.com/KtKID/x-dev-pipeline/cli/internal/exitcode"
)

// runVerify 处理 `verify <task-dir> [--json] [--only <id>]`。
// 复跑 dev-report 的 auto verify 块并对账 Scenario 覆盖。对齐 xdev.py 的 verify 子命令。
func runVerify(args []string) int {
	taskDir := ""
	asJSON := false
	var only *string
	for i, a := range args {
		switch {
		case a == "--json":
			asJSON = true
		case a == "--only":
			if i+1 < len(args) {
				v := args[i+1]
				only = &v
			} else {
				fmt.Fprintln(os.Stderr, "错误：--only 需要参数")
				return exitcode.Usage
			}
		case len(a) > 8 && a[:8] == "--only=":
			v := a[8:]
			only = &v
		default:
			if taskDir == "" {
				taskDir = a
			}
		}
	}
	if taskDir == "" {
		fmt.Fprintln(os.Stderr, "错误：缺少 task 目录")
		return exitcode.Usage
	}
	return verify.Verify(taskDir, asJSON, only)
}
