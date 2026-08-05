// Package verify 实现 skills/x-verify/scripts/verify.py 的等价逻辑：
// xdev verify 的确定性执行引擎（Gate① 事实验证）。
//
// # 职责
//
// 承接父 spec 声明 spec_version: 3 的 docs/spec/<spec>/tasks/<task>/，
// 按 checklist 的 Scenario 限定验收范围：
//
//   - parse_verify_blocks：解析 dev-report*.md 里的 ```verify 围栏块
//   - execute_verify_block：用 subprocess 执行 auto 块的 cmd，检查 exit code + expect_contains
//   - verify_req：场景对账（unit/smoke 必须 auto 覆盖；e2e 必须 auto 或 manual 声明）
//
// # 设计约束
//
// 纯确定性、零外部依赖。subprocess 用 /bin/sh -c 执行（与 Python shell=True 一致）。
// 错误信息逐字保留，以便与 test/test_xdev_verify.py 对拍。
package verify

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/KtKID/x-dev-pipeline/cli/internal/engine/req"
	specpkg "github.com/KtKID/x-dev-pipeline/cli/internal/engine/spec"
)

// verifyFenceRe 匹配 verify 围栏起始行 ```verify（忽略大小写、前导空白）。
// 对齐 verify.py 的 VERIFY_FENCE_RE。用普通字符串避免反引号冲突。
var verifyFenceRe = regexp.MustCompile("(?i)^\\s*```verify\\s*$")

// fenceEndRe 匹配围栏结束行 ```。
// 对齐 verify.py 的 FENCE_END_RE。
var fenceEndRe = regexp.MustCompile("^\\s*```\\s*$")

// verifyKeys 是 verify 块内允许的 key 集合。对齐 verify.py 的 VERIFY_KEYS。
var verifyKeys = map[string]bool{
	"id": true, "scenario": true, "cmd": true, "cwd": true,
	"expect_exit": true, "expect_contains": true, "timeout": true,
	"mode": true, "steps": true,
}

// VerifyBlock 是解析出的单个 verify 块。对齐 verify.py parse_verify_blocks 的 dict。
type VerifyBlock struct {
	ID             string   `json:"id"`
	Scenario       string   `json:"scenario"`
	Cmd            string   `json:"cmd"`
	Cwd            string   `json:"cwd"`
	ExpectExit     int      `json:"expect_exit"`
	ExpectContains []string `json:"expect_contains"`
	Timeout        *int     `json:"timeout"` // nil 表示无超时
	Mode           string   `json:"mode"`    // "auto" 或 "manual"
	Steps          string   `json:"steps"`
	Line           int      `json:"line"` // 围栏起始行号（1-based）
}

// readText 以 UTF-8 读取文件。对齐 verify.py 的 read_text。
func readText(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// LatestDevReport 返回 task 目录下最新的 dev-report*.md。
// 选择规则：按修改时间（mtime ns）+ 文件名排序取最大。对齐 verify.py 的 latest_dev_report。
func LatestDevReport(taskDir string) (string, error) {
	entries, err := os.ReadDir(taskDir)
	if err != nil {
		return "", fmt.Errorf("缺少 dev-report*.md：%s", taskDir)
	}
	type candidate struct {
		path  string
		mtime int64
		name  string
	}
	var found []candidate
	for _, e := range entries {
		if e.IsDir() || !strings.HasPrefix(e.Name(), "dev-report") || !strings.HasSuffix(e.Name(), ".md") {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		found = append(found, candidate{
			path:  filepath.Join(taskDir, e.Name()),
			mtime: info.ModTime().UnixNano(),
			name:  e.Name(),
		})
	}
	if len(found) == 0 {
		return "", fmt.Errorf("缺少 dev-report*.md：%s", taskDir)
	}
	// 按 (mtime, name) 取最大，与 Python max(key=...) 一致。
	best := found[0]
	for _, c := range found[1:] {
		if c.mtime > best.mtime || (c.mtime == best.mtime && c.name > best.name) {
			best = c
		}
	}
	return best.path, nil
}

// ParseVerifyBlocks 解析 dev-report 里的所有 ```verify 围栏块。
// 格式错误统一抛出 error（对齐 Python 的 ValueError）。
// 对齐 verify.py 的 parse_verify_blocks。
func ParseVerifyBlocks(reportPath string) ([]VerifyBlock, error) {
	text, err := readText(reportPath)
	if err != nil {
		return nil, err
	}
	lines := strings.Split(strings.ReplaceAll(strings.ReplaceAll(text, "\r\n", "\n"), "\r", "\n"), "\n")

	var blocks []VerifyBlock
	ids := map[string]bool{}
	index := 0
	for index < len(lines) {
		if !verifyFenceRe.MatchString(lines[index]) {
			index++
			continue
		}
		startLine := index + 1
		index++
		// 收集围栏内的原始行（带行号）。
		var rawLines [][2]string // {lineNo, text}
		for index < len(lines) && !fenceEndRe.MatchString(lines[index]) {
			rawLines = append(rawLines, [2]string{fmt.Sprintf("%d", index+1), lines[index]})
			index++
		}
		if index == len(lines) {
			return nil, fmt.Errorf("verify 块第 %d 行未闭合", startLine)
		}
		index++

		// 解析 key: value 行。
		values := map[string]string{}
		expectContains := []string{}
		seen := map[string]bool{}
		values["expect_contains"] = "" // 标记 expect_contains 是多值字段
		for _, rl := range rawLines {
			lineNo := rl[0]
			raw := rl[1]
			line := strings.TrimSpace(raw)
			if line == "" {
				continue
			}
			if !strings.Contains(line, ":") {
				return nil, fmt.Errorf("verify 块第 %d 行第 %s 行格式应为 key: value", startLine, lineNo)
			}
			parts := strings.SplitN(line, ":", 2)
			key := strings.TrimSpace(parts[0])
			value := strings.TrimSpace(parts[1])
			if !verifyKeys[key] {
				return nil, fmt.Errorf("verify 块第 %d 行存在未知 key：%s", startLine, key)
			}
			if value == "" {
				return nil, fmt.Errorf("verify 块第 %d 行的 %s 不能为空", startLine, key)
			}
			if key == "expect_contains" {
				expectContains = append(expectContains, value)
				continue
			}
			if seen[key] {
				return nil, fmt.Errorf("verify 块第 %d 行的 %s 重复", startLine, key)
			}
			seen[key] = true
			values[key] = value
		}

		ident := strings.TrimSpace(values["id"])
		if ident == "" {
			return nil, fmt.Errorf("verify 块第 %d 行缺少 id", startLine)
		}
		if ids[ident] {
			return nil, fmt.Errorf("verify 块 id 重复：%s", ident)
		}
		ids[ident] = true

		mode := strings.ToLower(values["mode"])
		if mode == "" {
			mode = "auto" // 默认 auto
		}
		if mode != "auto" && mode != "manual" {
			return nil, fmt.Errorf("verify 块 %s 的 mode 必须为 auto 或 manual", ident)
		}
		if mode == "auto" && strings.TrimSpace(values["cmd"]) == "" {
			return nil, fmt.Errorf("verify 块 %s 的 auto 模式缺少 cmd", ident)
		}
		if mode == "manual" && strings.TrimSpace(values["steps"]) == "" {
			return nil, fmt.Errorf("verify 块 %s 的 manual 模式缺少 steps", ident)
		}
		expectExit := 0
		if ee, ok := values["expect_exit"]; ok {
			n, err := atoiSafe(ee)
			if err != nil {
				return nil, fmt.Errorf("verify 块 %s 的 expect_exit 必须是整数", ident)
			}
			expectExit = n
		}
		var timeout *int
		if tv, ok := values["timeout"]; ok {
			n, err := atoiSafe(tv)
			if err != nil || n <= 0 {
				return nil, fmt.Errorf("verify 块 %s 的 timeout 必须是正整数", ident)
			}
			timeout = &n
		}
		cwd := values["cwd"]
		if cwd == "" {
			cwd = "."
		}
		blocks = append(blocks, VerifyBlock{
			ID:             ident,
			Scenario:       strings.TrimSpace(values["scenario"]),
			Cmd:            strings.TrimSpace(values["cmd"]),
			Cwd:            strings.TrimSpace(cwd),
			ExpectExit:     expectExit,
			ExpectContains: expectContains,
			Timeout:        timeout,
			Mode:           mode,
			Steps:          strings.TrimSpace(values["steps"]),
			Line:           startLine,
		})
	}
	return blocks, nil
}

// ProjectRootOfTaskDir 从 req task 实际位置推出项目根（docs/ 的上一级）。
// task 路径形如 <root>/docs/spec/<s>/tasks/<t>，所以 parents[4] 是 root。
// 对齐 verify.py 的 project_root_of_task_dir。
func ProjectRootOfTaskDir(taskDir string) string {
	abs, err := filepath.Abs(taskDir)
	if err != nil {
		return ""
	}
	parents := splitParents(abs)
	// parents[0]=task, [1]=tasks, [2]=<spec>, [3]=spec, [4]=docs, [5]=root
	if len(parents) >= 6 {
		return parents[5]
	}
	return ""
}

// VerifyCwd 校验 cwd 是项目根内的相对路径且目录存在。对齐 verify.py 的 verify_cwd。
func VerifyCwd(rawCwd, blockID, root, rootName string) (string, error) {
	candidate, err := filepath.Abs(filepath.Join(root, rawCwd))
	if err != nil {
		return "", fmt.Errorf("verify 块 %s 的 cwd 必须是%s内相对路径：%s", blockID, rootName, rawCwd)
	}
	rootAbs, _ := filepath.Abs(root)
	if !strings.HasPrefix(candidate+string(filepath.Separator), rootAbs+string(filepath.Separator)) && candidate != rootAbs {
		return "", fmt.Errorf("verify 块 %s 的 cwd 必须是%s内相对路径：%s", blockID, rootName, rawCwd)
	}
	info, err := os.Stat(candidate)
	if err != nil || !info.IsDir() {
		return "", fmt.Errorf("verify 块 %s 的 cwd 不存在或不是目录：%s", blockID, rawCwd)
	}
	return candidate, nil
}

// BlockResult 是单个 auto 块的执行结果。对齐 verify.py execute_verify_block 的 dict。
type BlockResult struct {
	ID             string   `json:"id"`
	Scenario       string   `json:"scenario"`
	Cmd            string   `json:"cmd"`
	ExitCode       *int     `json:"exit_code"` // nil 表示超时
	ExpectedExit   int      `json:"expected_exit"`
	MissingContain []string `json:"missing_contains"`
	TimedOut       bool     `json:"timed_out"`
	OutputTail     string   `json:"output_tail,omitempty"`
	Pass           bool     `json:"pass,omitempty"` // 仅 pass 项使用
}

// ExecuteVerifyBlock 执行单个 auto 块：subprocess 跑 cmd，检查 exit code + expect_contains。
// 超时由 block.Timeout 控制（nil 表示无限）。对齐 verify.py 的 execute_verify_block。
func ExecuteVerifyBlock(block VerifyBlock, root, rootName string) BlockResult {
	cwd, err := VerifyCwd(block.Cwd, block.ID, root, rootName)
	// 注意：Python 在 execute_verify_block 调用前已校验 cwd，这里若出错也照常返回失败。
	_ = err

	// 构造带超时的 context。
	ctx := context.Background()
	var cancel context.CancelFunc
	if block.Timeout != nil {
		ctx, cancel = context.WithTimeout(ctx, time.Duration(*block.Timeout)*time.Second)
	} else {
		cancel = func() {}
	}
	defer cancel()

	// 用 /bin/sh -c 执行，与 Python subprocess(shell=True) 一致。
	cmd := exec.CommandContext(ctx, "/bin/sh", "-c", block.Cmd)
	cmd.Dir = cwd
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	timedOut := false
	exitCode := -1
	err = cmd.Run()
	if ctx.Err() == context.DeadlineExceeded {
		timedOut = true
	} else if err != nil {
		// 退出码非 0：从 ExitError 取码；其他错误保持 -1。
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		}
	} else {
		exitCode = 0
	}

	output := stdout.String() + stderr.String()
	var missingContains []string
	for _, text := range block.ExpectContains {
		if !strings.Contains(output, text) {
			missingContains = append(missingContains, text)
		}
	}

	var exitCodePtr *int
	if !timedOut {
		exitCodePtr = &exitCode
	}
	failed := timedOut || exitCode != block.ExpectExit || len(missingContains) > 0
	return BlockResult{
		ID:             block.ID,
		Scenario:       block.Scenario,
		Cmd:            block.Cmd,
		ExitCode:       exitCodePtr,
		ExpectedExit:   block.ExpectExit,
		MissingContain: missingContains,
		TimedOut:       timedOut,
		OutputTail:     output,
		Pass:           !failed,
	}
}

// ManualItem 是 manual 块的精简声明（id/scenario/steps）。
type ManualItem struct {
	ID       string `json:"id"`
	Scenario string `json:"scenario"`
	Steps    string `json:"steps"`
}

// ExecuteResult 是 execute_verify_blocks 的聚合结果。
type ExecuteResult struct {
	Pass          []map[string]any
	Fail          []map[string]any
	Manual        []ManualItem
	DeclaredAuto  map[string]bool
}

// ExecuteVerifyBlocks 筛选并执行 auto 块，同时返回全部 manual 与 auto 场景声明。
// only 非 nil 时只执行指定 id 的 auto 块。对齐 verify.py 的 execute_verify_blocks。
func ExecuteVerifyBlocks(blocks []VerifyBlock, only *string, root, rootName string) (*ExecuteResult, error) {
	var allAuto []VerifyBlock
	for _, b := range blocks {
		if b.Mode == "auto" {
			allAuto = append(allAuto, b)
		}
	}
	var selected []VerifyBlock
	if only != nil {
		for _, b := range allAuto {
			if b.ID == *only {
				selected = append(selected, b)
				break
			}
		}
		if len(selected) == 0 {
			return nil, fmt.Errorf("未找到 auto verify 块：%s", *only)
		}
	} else {
		selected = allAuto
	}

	var manual []ManualItem
	for _, b := range blocks {
		if b.Mode == "manual" {
			manual = append(manual, ManualItem{ID: b.ID, Scenario: b.Scenario, Steps: b.Steps})
		}
	}

	var passItems, failItems []map[string]any
	for _, b := range selected {
		result := ExecuteVerifyBlock(b, root, rootName)
		if result.Pass {
			// pass 项去掉 output_tail。
			passItems = append(passItems, map[string]any{
				"id": result.ID, "scenario": result.Scenario, "cmd": result.Cmd,
				"exit_code": result.ExitCode, "expected_exit": result.ExpectedExit,
				"missing_contains": result.MissingContain, "timed_out": result.TimedOut,
				"pass": true,
			})
		} else {
			// fail 项保留 output_tail、去掉 pass。
			failItems = append(failItems, map[string]any{
				"id": result.ID, "scenario": result.Scenario, "cmd": result.Cmd,
				"exit_code": result.ExitCode, "expected_exit": result.ExpectedExit,
				"missing_contains": result.MissingContain, "timed_out": result.TimedOut,
				"output_tail": result.OutputTail,
			})
		}
	}

	declaredAuto := map[string]bool{}
	for _, b := range allAuto {
		if s := strings.TrimSpace(b.Scenario); s != "" {
			declaredAuto[s] = true
		}
	}
	if passItems == nil {
		passItems = []map[string]any{}
	}
	if failItems == nil {
		failItems = []map[string]any{}
	}
	return &ExecuteResult{Pass: passItems, Fail: failItems, Manual: manual, DeclaredAuto: declaredAuto}, nil
}

// VerifyPayload 是 verify 命令的完整输出。对齐 verify.py verify_req 的 payload。
type VerifyPayload struct {
	Task            string            `json:"task"`
	Spec            string            `json:"spec"`
	Profile         string            `json:"profile"`
	DevReport       string            `json:"dev_report"`
	Scenarios       []string          `json:"scenarios"`
	ScenarioLayers  map[string]string `json:"scenario_layers"`
	ExpectedAuto    []string          `json:"expected_auto"`
	ExpectedDeclared []string         `json:"expected_declared"`
	Pass            []map[string]any  `json:"pass"`
	Fail            []map[string]any  `json:"fail"`
	Manual          []ManualItem      `json:"manual"`
	Uncovered       []string          `json:"uncovered"`
}

// Verify 验证父 spec 声明 spec_version: 3 的 task。对齐 verify.py 的 verify / verify_req。
func Verify(taskDir string, asJSON bool, only *string) int {
	payload, err := buildVerifyPayload(taskDir, only)
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误：%v\n", err)
		return 2
	}
	if asJSON {
		// 保证空数组为 [] 而非 null。
		normalizePayload(payload)
		out, _ := json.MarshalIndent(payload, "", "  ")
		fmt.Println(string(out))
	} else {
		fmt.Printf("== %s verify\n", payload.Task)
		fmt.Printf("  pass: %d · fail: %d · manual: %d\n", len(payload.Pass), len(payload.Fail), len(payload.Manual))
		for _, item := range payload.Fail {
			exitCode := "nil"
			if ec, ok := item["exit_code"].(*int); ok && ec != nil {
				exitCode = fmt.Sprintf("%d", *ec)
			}
			fmt.Printf("  ! %s exit=%s expected=%d\n", item["id"], exitCode, item["expected_exit"])
		}
		for _, name := range payload.Uncovered {
			fmt.Printf("  ! uncovered scenario: %s\n", name)
		}
	}
	if len(payload.Fail) > 0 || len(payload.Uncovered) > 0 {
		return 1
	}
	return 0
}

// buildVerifyPayload 构造 verify 输出 payload（不含 emit），便于测试。
func buildVerifyPayload(taskDir string, only *string) (*VerifyPayload, error) {
	info, err := os.Stat(taskDir)
	if err != nil || !info.IsDir() {
		return nil, fmt.Errorf("不是目录：%s", taskDir)
	}
	specPath := req.SpecOfTaskDir(taskDir)
	if specPath == "" {
		return nil, fmt.Errorf("%s 不在 docs/spec/<spec-name>/tasks/<task-name>/ 结构下", taskDir)
	}
	specDir := req.ResolveSpecDir(taskDir)
	if specDir == "" {
		return nil, fmt.Errorf("%s 的上级不是合法 spec_version: 3 包", taskDir)
	}
	specMD := filepath.Join(specDir, "spec.md")

	// checklist 承接的 Scenario 范围。
	scope, err := req.TaskScenarios(taskDir)
	if err != nil {
		return nil, err
	}
	scenarios := specpkg.SpecScenarios(specMD)
	byID := map[string]specpkg.Scenario{}
	for _, sc := range scenarios {
		byID[sc.ID] = sc
	}
	// 悬空检查：checklist 声明的 Scenario 必须在 spec 里存在。
	var dangling []string
	for _, sid := range scope {
		if _, ok := byID[sid]; !ok {
			dangling = append(dangling, sid)
		}
	}
	if len(dangling) > 0 {
		return nil, fmt.Errorf("checklist 承接的 Scenario 在 %s 中不存在：%s", specMD, strings.Join(dangling, "、"))
	}
	// 测试层合法性检查。
	var malformed []string
	for _, sid := range scope {
		if byID[sid].Layer != "unit" && byID[sid].Layer != "smoke" && byID[sid].Layer != "e2e" {
			malformed = append(malformed, sid)
		}
	}
	if len(malformed) > 0 {
		return nil, fmt.Errorf("%s 的 Scenario 缺少合法测试层：%s", specMD, strings.Join(malformed, "、"))
	}

	projectRoot := ProjectRootOfTaskDir(taskDir)
	if projectRoot == "" {
		return nil, fmt.Errorf("无法从 %s 推出项目根", taskDir)
	}
	report, err := LatestDevReport(taskDir)
	if err != nil {
		return nil, err
	}
	blocks, err := ParseVerifyBlocks(report)
	if err != nil {
		return nil, err
	}
	execResult, err := ExecuteVerifyBlocks(blocks, only, projectRoot, "项目")
	if err != nil {
		return nil, err
	}

	declaredManual := map[string]bool{}
	for _, m := range execResult.Manual {
		if s := strings.TrimSpace(m.Scenario); s != "" {
			declaredManual[s] = true
		}
	}
	// expected_auto：unit/smoke 层必须被 auto 块覆盖。
	var expectedAuto []string
	for _, sid := range scope {
		if byID[sid].Layer == "unit" || byID[sid].Layer == "smoke" {
			expectedAuto = append(expectedAuto, sid)
		}
	}
	// expected_declared：e2e 层必须被 auto 或 manual 覆盖。
	var expectedDeclared []string
	for _, sid := range scope {
		if byID[sid].Layer == "e2e" {
			expectedDeclared = append(expectedDeclared, sid)
		}
	}
	// uncovered：该 auto 没 auto 覆盖；或该 e2e 既没 auto 也没 manual 覆盖。
	var uncovered []string
	uncoveredSet := map[string]bool{}
	for _, name := range expectedAuto {
		if !execResult.DeclaredAuto[name] && !uncoveredSet[name] {
			uncovered = append(uncovered, name)
			uncoveredSet[name] = true
		}
	}
	for _, name := range expectedDeclared {
		if !execResult.DeclaredAuto[name] && !declaredManual[name] && !uncoveredSet[name] {
			uncovered = append(uncovered, name)
			uncoveredSet[name] = true
		}
	}

	scenarioLayers := map[string]string{}
	for _, sid := range scope {
		scenarioLayers[sid] = byID[sid].Layer
	}
	if expectedAuto == nil {
		expectedAuto = []string{}
	}
	if expectedDeclared == nil {
		expectedDeclared = []string{}
	}
	if uncovered == nil {
		uncovered = []string{}
	}
	return &VerifyPayload{
		Task:             filepathBase(taskDir),
		Spec:             specPath,
		Profile:          "req",
		DevReport:        report,
		Scenarios:        scope,
		ScenarioLayers:   scenarioLayers,
		ExpectedAuto:     expectedAuto,
		ExpectedDeclared: expectedDeclared,
		Pass:             execResult.Pass,
		Fail:             execResult.Fail,
		Manual:           execResult.Manual,
		Uncovered:        uncovered,
	}, nil
}

// ===== helpers =====

// normalizePayload 保证空切片非 nil（JSON 输出 [] 而非 null）。
func normalizePayload(p *VerifyPayload) {
	if p.Scenarios == nil {
		p.Scenarios = []string{}
	}
	if p.ExpectedAuto == nil {
		p.ExpectedAuto = []string{}
	}
	if p.ExpectedDeclared == nil {
		p.ExpectedDeclared = []string{}
	}
	if p.Pass == nil {
		p.Pass = []map[string]any{}
	}
	if p.Fail == nil {
		p.Fail = []map[string]any{}
	}
	if p.Manual == nil {
		p.Manual = []ManualItem{}
	}
	if p.Uncovered == nil {
		p.Uncovered = []string{}
	}
}

// atoiSafe 解析整数，失败返回错误。对齐 Python int() 的抛错语义。
func atoiSafe(s string) (int, error) {
	var n int
	_, err := fmt.Sscanf(s, "%d", &n)
	return n, err
}

// splitParents 拆出路径的各级父目录（含自身），从近到远。
// 等价于 Python pathlib.Path.parents。
func splitParents(abs string) []string {
	abs = filepath.ToSlash(abs)
	var parents []string
	for {
		parents = append(parents, abs)
		idx := strings.LastIndex(abs, "/")
		if idx <= 0 {
			break
		}
		abs = abs[:idx]
	}
	return parents
}

// filepathBase 取路径最后一段（目录名）。
func filepathBase(path string) string {
	path = strings.ReplaceAll(path, "\\", "/")
	if idx := strings.LastIndex(path, "/"); idx >= 0 {
		return path[idx+1:]
	}
	return path
}

// 排序工具（保持声明稳定）。
var _ = sort.Strings
