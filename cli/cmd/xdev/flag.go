package main

import (
	"fmt"
	"os"

	"github.com/KtKID/x-dev-pipeline/cli/internal/engine/flag"
	"github.com/KtKID/x-dev-pipeline/cli/internal/exitcode"
)

// runFlag 处理 `flag <task-dir> --task T2,T3 --severity P0 --loc <p:L> --msg "..." [--new-round] [--json]`。
// 登记 QA Gate issue 并执行 checklist 状态降级（双文件原子事务）。
func runFlag(args []string) int {
	taskDir := ""
	taskArg := ""
	severity := ""
	loc := ""
	msg := ""
	newRound := false
	asJSON := false

	i := 0
	for i < len(args) {
		a := args[i]
		switch {
		case a == "--json":
			asJSON = true
		case a == "--new-round":
			newRound = true
		case a == "--task":
			i++
			if i < len(args) {
				taskArg = args[i]
			}
		case len(a) > 7 && a[:7] == "--task=":
			taskArg = a[7:]
		case a == "--severity":
			i++
			if i < len(args) {
				severity = args[i]
			}
		case len(a) > 11 && a[:11] == "--severity=":
			severity = a[11:]
		case a == "--loc":
			i++
			if i < len(args) {
				loc = args[i]
			}
		case len(a) > 6 && a[:6] == "--loc=":
			loc = a[6:]
		case a == "--msg":
			i++
			if i < len(args) {
				msg = args[i]
			}
		case len(a) > 6 && a[:6] == "--msg=":
			msg = a[6:]
		default:
			if taskDir == "" {
				taskDir = a
			}
		}
		i++
	}

	if taskDir == "" {
		fmt.Fprintln(os.Stderr, "错误：缺少 task 目录")
		return exitcode.Usage
	}
	if taskArg == "" || severity == "" || loc == "" || msg == "" {
		fmt.Fprintln(os.Stderr, "错误：--task --severity --loc --msg 均为必填")
		return exitcode.Usage
	}
	return flag.FlagCommand(taskDir, taskArg, severity, loc, msg, newRound, asJSON)
}
