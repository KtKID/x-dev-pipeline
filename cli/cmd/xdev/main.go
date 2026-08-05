// xdev 是 x-dev-pipeline 的确定性工具统一 CLI，由原 skills/*/scripts/*.py 移植而来。
//
// 命令树（与 Python 版子命令名 + --json + 退出码对齐）：
//
//	validate | status | graph | instructions | scaffold | verify | flag
//	spec validate | cr validate-report | risk validate-* | risk-rag query
//	corpus <sub> | corpus-home <sub> | triage | rag
//
// 退出码：0 成功；1 校验失败或依赖环；2 用法、目标或 IO 错误。
package main

import (
	"fmt"
	"os"

	"github.com/KtKID/x-dev-pipeline/cli/internal/exitcode"
)

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	if len(args) == 0 {
		printUsage(os.Stderr)
		return exitcode.Usage
	}
	cmd, rest := args[0], args[1:]
	switch cmd {
	case "-h", "--help", "help":
		printUsage(os.Stdout)
		return exitcode.OK
	case "cr":
		return runCR(rest)
	case "validate":
		return runValidate(rest)
	case "status":
		return runTaskCmd(rest, "status")
	case "graph":
		return runTaskCmd(rest, "graph")
	case "instructions":
		return runInstructions(rest)
	case "scaffold":
		return runScaffold(rest)
	case "verify":
		return runVerify(rest)
	case "flag":
		return runFlag(rest)
	case "spec":
		return runSpec(rest)
	case "risk":
		return runRisk(rest)
	case "corpus", "corpus-home", "triage", "risk-rag", "rag":
		fmt.Fprintf(os.Stderr, "xdev %s：该子命令尚未在 Go 版实现\n", cmd)
		return exitcode.Usage
	default:
		fmt.Fprintf(os.Stderr, "未知子命令：%s\n", cmd)
		printUsage(os.Stderr)
		return exitcode.Usage
	}
}

func printUsage(w *os.File) {
	fmt.Fprint(w, `xdev — x-dev-pipeline 确定性工具统一 CLI

用法：
  xdev <command> [options]

已实现命令：
  cr validate-report <report.md> [<report.md> ...]
      验证 x-cr-v2 报告契约（不变量覆盖 / 审查结论 / 问题详情 一致性）。

待实现命令（与 Python 版子命令对齐，分阶段落地）：
  validate [targets...] [--include-legacy] [--json]
  status    <task-dir> [--json]
  graph     <task-dir> [--json]
  instructions <artifact-id> --task <task-dir> [--json]
  scaffold  <task-dir> [--with-diagram] [--json]
  verify    <task-dir> [--json] [--only <id>]
  flag      <task-dir> --task T2,T3 --severity P0 --loc <p:L> --msg "..." [--new-round] [--json]
  spec validate <spec-dir> [--allow-pending] [--json]
  risk validate-spec|validate-corpus|validate-review ...
  risk-rag query --catalog --keywords --risk [--top-n] [--json]
  corpus build|rebuild|validate|validate-flat|append|read|select|search ...
  corpus-home path|init|import-existing|validate
  triage [--target] [--dry-run] [--json]
  rag --source --query [--top-n] [--json]

退出码：0 成功；1 校验失败或依赖环；2 用法、目标或 IO 错误。
`)
}
