package main

import (
	"fmt"
	"os"
	"strings"

	"github.com/KtKID/x-dev-pipeline/cli/internal/engine/risk"
	"github.com/KtKID/x-dev-pipeline/cli/internal/exitcode"
)

// runRisk 实现 `xdev risk validate-spec|validate-corpus|validate-review ...`。
// 与 risk_contract.py 的 main 一致：读目标 → 校验 → 输出 → 退出码（0/1/2）。
func runRisk(args []string) int {
	if len(args) == 0 || args[0] == "-h" || args[0] == "--help" {
		fmt.Fprint(os.Stderr, `xdev risk <command> [options]

命令：
  validate-spec <target> [--json]
  validate-corpus <target> [--require-rich-fields] [--json]
  validate-review <target> --catalog <path> [--require-rich-fields] [--json]

退出码：0 通过；1 校验失败；2 IO 错误。
`)
		return exitcode.OK
	}
	cmd := args[0]
	rest := args[1:]
	switch cmd {
	case "validate-spec":
		return runRiskValidateSpec(rest)
	case "validate-corpus":
		return runRiskValidateCorpus(rest)
	case "validate-review":
		return runRiskValidateReview(rest)
	default:
		fmt.Fprintf(os.Stderr, "未知 risk 子命令：%s\n", cmd)
		return exitcode.Usage
	}
}

// parseRiskCommon 解析 <target> [--json] 共同参数。
func parseRiskCommon(args []string) (target string, asJSON bool, ok bool) {
	for _, a := range args {
		switch a {
		case "--json":
			asJSON = true
		case "--require-rich-fields":
			// validate-corpus/review 自己处理，这里忽略
		default:
			if target == "" {
				target = a
			}
		}
	}
	ok = target != ""
	return
}

func runRiskValidateSpec(args []string) int {
	target, asJSON, ok := parseRiskCommon(args)
	if !ok {
		fmt.Fprintln(os.Stderr, "错误：缺少目标文件")
		return exitcode.Usage
	}
	text, ioIssue := risk.ReadTargetForCLI(target)
	if ioIssue != nil {
		out, _ := risk.Emit("validate-spec", target, []risk.Issue{*ioIssue}, asJSON)
		fmt.Println(out)
		return exitcode.Usage // IO 错误退出码 2
	}
	issues := risk.ValidateSpec(text)
	out, _ := risk.Emit("validate-spec", target, issues, asJSON)
	fmt.Println(out)
	return risk.ExitCode(issues)
}

func runRiskValidateCorpus(args []string) int {
	target, asJSON, ok := parseRiskCommon(args)
	requireRich := false
	for _, a := range args {
		if a == "--require-rich-fields" {
			requireRich = true
		}
	}
	if !ok {
		fmt.Fprintln(os.Stderr, "错误：缺少目标文件")
		return exitcode.Usage
	}
	text, ioIssue := risk.ReadTargetForCLI(target)
	if ioIssue != nil {
		out, _ := risk.Emit("validate-corpus", target, []risk.Issue{*ioIssue}, asJSON)
		fmt.Println(out)
		return exitcode.Usage
	}
	issues := risk.ValidateCorpus(text, requireRich)
	out, _ := risk.Emit("validate-corpus", target, issues, asJSON)
	fmt.Println(out)
	return risk.ExitCode(issues)
}

func runRiskValidateReview(args []string) int {
	target, asJSON, ok := parseRiskCommon(args)
	requireRich := false
	catalogPath := ""
	for _, a := range args {
		switch {
		case a == "--require-rich-fields":
			requireRich = true
		case strings.HasPrefix(a, "--catalog="):
			catalogPath = strings.TrimPrefix(a, "--catalog=")
		case a == "--catalog":
			// 单独处理会在下方兜底
		default:
			if target == "" {
				target = a
			} else if catalogPath == "" {
				catalogPath = a
			}
		}
	}
	// 处理 --catalog <path> 两段式
	for i, a := range args {
		if a == "--catalog" && i+1 < len(args) {
			catalogPath = args[i+1]
		}
	}
	if !ok || catalogPath == "" {
		fmt.Fprintln(os.Stderr, "错误：validate-review 需要 <target> 和 --catalog <path>")
		return exitcode.Usage
	}
	specText, specIO := risk.ReadTargetForCLI(target)
	if specIO != nil {
		out, _ := risk.Emit("validate-review", target+" + "+catalogPath, []risk.Issue{*specIO}, asJSON)
		fmt.Println(out)
		return exitcode.Usage
	}
	catalogText, catalogIO := risk.ReadTargetForCLI(catalogPath)
	if catalogIO != nil {
		out, _ := risk.Emit("validate-review", target+" + "+catalogPath, []risk.Issue{*catalogIO}, asJSON)
		fmt.Println(out)
		return exitcode.Usage
	}
	var issues []risk.Issue
	issues = append(issues, risk.ValidateSpec(specText)...)
	issues = append(issues, risk.ValidateCorpus(catalogText, requireRich)...)
	issues = append(issues, risk.ValidateTraceability(specText, catalogText)...)
	out, _ := risk.Emit("validate-review", target+" + "+catalogPath, issues, asJSON)
	fmt.Println(out)
	return risk.ExitCode(issues)
}
