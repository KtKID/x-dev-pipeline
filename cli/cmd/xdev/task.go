package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/KtKID/x-dev-pipeline/cli/internal/engine/req"
	specpkg "github.com/KtKID/x-dev-pipeline/cli/internal/engine/spec"
	"github.com/KtKID/x-dev-pipeline/cli/internal/exitcode"
)

// runTaskCmd 处理 status/graph 子命令：都需要 <task-dir> [--json]。
// 这两个命令只对 spec_version: 3 的 req-task 有效。
func runTaskCmd(args []string, which string) int {
	taskDir, asJSON, ok := parseTaskArgs(args)
	if !ok {
		return exitcode.Usage
	}
	if !isReqTask(taskDir) {
		fmt.Fprintf(os.Stderr, "错误：只支持父 spec 声明 spec_version: 3 的 docs/spec/<spec-name>/tasks/<task-name>/：%s\n", taskDir)
		return exitcode.Usage
	}
	var (
		code int
		err  error
	)
	switch which {
	case "status":
		code, err = req.Status(taskDir, asJSON)
	case "graph":
		code, err = req.Graph(taskDir, asJSON)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误：%v\n", err)
		return exitcode.Usage
	}
	return code
}

// runInstructions 处理 `instructions <artifact-id> --task <dir> [--json]`。
func runInstructions(args []string) int {
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, "错误：缺少 artifact-id")
		return exitcode.Usage
	}
	artifactID := args[0]
	taskDir := ""
	asJSON := false
	for _, a := range args[1:] {
		switch {
		case a == "--json":
			asJSON = true
		case a == "--task":
			// 两段式，由下方兜底
		case strings.HasPrefix(a, "--task="):
			taskDir = strings.TrimPrefix(a, "--task=")
		default:
			if taskDir == "" {
				taskDir = a
			}
		}
	}
	for i, a := range args {
		if a == "--task" && i+1 < len(args) {
			taskDir = args[i+1]
		}
	}
	if taskDir == "" {
		fmt.Fprintln(os.Stderr, "错误：缺少 --task <task-dir>")
		return exitcode.Usage
	}
	if !isReqTask(taskDir) {
		fmt.Fprintf(os.Stderr, "错误：task 不在合法 spec_version: 3 路径下：%s\n", taskDir)
		return exitcode.Usage
	}
	code, err := req.Instructions(artifactID, taskDir, asJSON)
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误：%v\n", err)
		return exitcode.Usage
	}
	return code
}

// runScaffold 处理 `scaffold <task-dir> [--with-diagram] [--json]`。
func runScaffold(args []string) int {
	taskDir, withDiagram, asJSON, ok := parseScaffoldArgs(args)
	if !ok {
		return exitcode.Usage
	}
	code, err := req.Scaffold(taskDir, withDiagram, asJSON)
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误：%v\n", err)
		return exitcode.Usage
	}
	return code
}

// runValidate 处理 `validate [targets...] [--include-legacy] [--json]`。
// 自动发现 docs/{spec,changes,specs}/*/ 并按类型分发到 spec 或 req 校验。
func runValidate(args []string) int {
	var targets []string
	includeLegacy := false
	asJSON := false
	for _, a := range args {
		switch a {
		case "--include-legacy":
			includeLegacy = true
		case "--json":
			asJSON = true
		default:
			targets = append(targets, a)
		}
	}
	if len(targets) == 0 {
		// 自动发现。
		var found []string
		for _, base := range []string{"docs/spec", "docs/changes", "docs/specs"} {
			dir := base
			if _, err := os.Stat(dir); err == nil {
				entries, _ := os.ReadDir(dir)
				for _, e := range entries {
					if e.IsDir() && e.Name() != "archive" {
						found = append(found, filepath.Join(dir, e.Name()))
					}
				}
			}
		}
		if len(found) == 0 {
			fmt.Fprintln(os.Stderr, "错误：未发现任何包（docs/spec|changes|specs 下无子目录），可显式传目录")
			return exitcode.Usage
		}
		targets = found
	}

	// 逐个目标校验，聚合结果。
	type result struct {
		Path    string      `json:"path"`
		Type    string      `json:"type"`
		Skipped bool        `json:"skipped"`
		Issues  []req.Issue `json:"issues"`
	}
	var results []result
	totalIssues := 0
	for _, target := range targets {
		r := result{Path: target, Issues: []req.Issue{}}
		if isReqTask(target) {
			// req-task：检查父 spec 版本。
			if resolveSpecDirForCLI(target) == "" {
				r.Type = "unsupported-task"
				r.Issues = []req.Issue{{File: target, Line: 0, Rule: "TASK_VERSION",
					Msg: "当前 task 引擎只支持父 spec 声明 spec_version: 3"}}
			} else {
				r.Type = "req-task"
				r.Issues = req.ValidateIssues(target)
				if r.Issues == nil {
					r.Issues = []req.Issue{}
				}
			}
		} else {
			// spec 包：委托 spec 引擎校验（validator.py 的 detect_type/legacy 跳过
			// 属于阶段 C 后续工作，这里先用 spec.ValidateIssues 做最小可用版）。
			r.Type = "spec"
			specIssues := specpkg.ValidateIssues(target, true)
			r.Issues = make([]req.Issue, 0, len(specIssues))
			for _, si := range specIssues {
				r.Issues = append(r.Issues, req.Issue{File: si.File, Line: si.Line, Rule: si.Rule, Msg: si.Msg})
			}
			_ = includeLegacy // TODO: validator 的 legacy 跳过逻辑
		}
		// 注意：spec 包的 Issue 与 req 包的 Issue 结构相同（file/line/rule/msg），可直接复用。
		totalIssues += len(r.Issues)
		results = append(results, r)
	}

	if asJSON {
		skipped := 0
		for _, r := range results {
			if r.Skipped {
				skipped++
			}
		}
		payload := struct {
			Packages      []result `json:"packages"`
			TotalIssues   int      `json:"total_issues"`
			SkippedLegacy int      `json:"skipped_legacy"`
		}{results, totalIssues, skipped}
		out, _ := json.MarshalIndent(payload, "", "  ")
		fmt.Println(string(out))
	} else {
		for _, r := range results {
			tag := "[" + r.Type + "]"
			if r.Skipped {
				fmt.Printf("== %s  %s  跳过（legacy；--include-legacy 可纳入）\n", r.Path, tag)
				continue
			}
			fmt.Printf("== %s  %s\n", r.Path, tag)
			if len(r.Issues) == 0 {
				fmt.Println("   ok")
			}
			for _, iss := range r.Issues {
				loc := iss.File
				if iss.Line != 0 {
					loc = fmt.Sprintf("%s:%d", iss.File, iss.Line)
				}
				fmt.Printf("   %s  %s  %s\n", loc, iss.Rule, iss.Msg)
			}
		}
		mark := "✓"
		if totalIssues > 0 {
			mark = "✗"
		}
		fmt.Printf("%s validate：%d 包，%d issue(s)\n", mark, len(results), totalIssues)
	}
	if totalIssues > 0 {
		return exitcode.Invalid
	}
	return exitcode.OK
}

// parseTaskArgs 解析 <task-dir> [--json] [--only <id>]。
func parseTaskArgs(args []string) (taskDir string, asJSON bool, ok bool) {
	for _, a := range args {
		switch a {
		case "--json":
			asJSON = true
		default:
			if taskDir == "" {
				taskDir = a
			}
		}
	}
	ok = taskDir != ""
	return
}

// parseScaffoldArgs 解析 <task-dir> [--with-diagram] [--json]。
func parseScaffoldArgs(args []string) (taskDir string, withDiagram, asJSON, ok bool) {
	for _, a := range args {
		switch a {
		case "--with-diagram":
			withDiagram = true
		case "--json":
			asJSON = true
		default:
			if taskDir == "" {
				taskDir = a
			}
		}
	}
	ok = taskDir != ""
	return
}

// isReqTask 判断目录是否是 spec_version: 3 的 req-task（task 位于 .../tasks/<name>/ 且父 spec 合法）。
func isReqTask(taskDir string) bool {
	return req.SpecOfTaskDir(taskDir) != ""
}

// resolveSpecDirForCLI 返回 task 的父 spec 目录（不带 task 段）。
func resolveSpecDirForCLI(taskDir string) string {
	return req.ResolveSpecDir(taskDir)
}
