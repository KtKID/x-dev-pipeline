package main

import (
	"fmt"
	"os"

	"github.com/KtKID/x-dev-pipeline/cli/internal/engine/cr"
	"github.com/KtKID/x-dev-pipeline/cli/internal/exitcode"
)

// runCR 实现 `xdev cr validate-report <report>...`。
// 与 validate_report.py 的 main 一致：每个报告 OK/FAIL 一行，错误列在下方；
// 任一报告 FAIL 则整体退出码 1。
func runCR(args []string) int {
	if len(args) == 0 || args[0] == "-h" || args[0] == "--help" {
		fmt.Fprint(os.Stderr, `xdev cr validate-report <report.md> [<report.md> ...]

验证 x-cr-v2 报告契约。每个报告一行结果；任一 FAIL 则退出码 1。
`)
		return exitcode.OK
	}
	if args[0] != "validate-report" {
		fmt.Fprintf(os.Stderr, "未知 cr 子命令：%s（仅支持 validate-report）\n", args[0])
		return exitcode.Usage
	}
	reports := args[1:]
	if len(reports) == 0 {
		fmt.Fprintln(os.Stderr, "错误：至少需要一个报告路径")
		return exitcode.Usage
	}

	failed := false
	for _, path := range reports {
		errs := cr.ValidatePath(path)
		if len(errs) > 0 {
			failed = true
			fmt.Printf("FAIL %s\n", path)
			for _, e := range errs {
				fmt.Printf("  - %s\n", e)
			}
		} else {
			fmt.Printf("OK   %s\n", path)
		}
	}
	if failed {
		return exitcode.Invalid
	}
	return exitcode.OK
}
