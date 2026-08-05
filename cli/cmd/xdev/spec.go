package main

import (
	"fmt"
	"os"

	"github.com/KtKID/x-dev-pipeline/cli/internal/engine/spec"
	"github.com/KtKID/x-dev-pipeline/cli/internal/exitcode"
)

// runSpec 实现 `xdev spec validate <spec-dir> [--json] [--allow-pending]`。
// 与 spec.py 的 main + validate_command 一致。
func runSpec(args []string) int {
	if len(args) == 0 || args[0] == "-h" || args[0] == "--help" {
		fmt.Fprint(os.Stderr, `xdev spec validate <spec-dir> [--json] [--allow-pending]

校验 iteration-7 x-spec 单文件包（结构契约 + 可选 x-req 就绪门禁）。
退出码：0 通过；1 校验失败；2 用法错误。
`)
		return exitcode.OK
	}
	if args[0] != "validate" {
		fmt.Fprintf(os.Stderr, "未知 spec 子命令：%s（仅支持 validate）\n", args[0])
		return exitcode.Usage
	}
	rest := args[1:]
	if len(rest) == 0 {
		fmt.Fprintln(os.Stderr, "错误：缺少 spec 目录")
		return exitcode.Usage
	}
	specDir := ""
	asJSON := false
	allowPending := false
	for _, a := range rest {
		switch a {
		case "--json":
			asJSON = true
		case "--allow-pending":
			allowPending = true
		default:
			if specDir == "" {
				specDir = a
			} else {
				fmt.Fprintf(os.Stderr, "未知参数：%s\n", a)
				return exitcode.Usage
			}
		}
	}
	if specDir == "" {
		fmt.Fprintln(os.Stderr, "错误：缺少 spec 目录")
		return exitcode.Usage
	}
	return spec.ValidateCommand(specDir, asJSON, !allowPending)
}
