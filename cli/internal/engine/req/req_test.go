package req

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// makeSpec 在临时目录构造一个合法的 iteration-7 spec 包（standard 预算、2 个 Scenario）。
// 与 test/test_req_engine.py 的 Req3EngineTestCase.make_spec 内容一致，用于对拍。
func makeSpec(t *testing.T, root, name string) string {
	t.Helper()
	specDir := filepath.Join(root, "docs", "spec", name)
	mustMkdir(t, specDir)
	specMD := filepath.Join(specDir, "spec.md")
	mustWrite(t, specMD,
		"> spec_version: 3\n"+
			"> adversarial_risk_version: 3\n"+
			"> complexity: 2\n"+
			"> importance: 2\n"+
			"> risk_average: 2.0\n"+
			"> review_budget: standard\n"+
			"> adversarial_review: skipped-standard\n\n"+
			"# "+name+"\n\n"+
			"## 任务目标\n\n- 返回可验证结果。\n\n"+
			"## 非目标\n\n- 不访问网络。\n\n"+
			"## 风险评分依据\n\n"+
			"- 复杂度：单模块确定性解析。\n"+
			"- 重要性：局部工具链。\n"+
			"- 预算升级：无。\n\n"+
			"## 影响边界与不变量\n\n"+
			"| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |\n"+
			"|---|---|---|---|---|---|\n"+
			"| Resolver | 目标 | 新增解析 | 输入被原地修改导致调用方状态污染 | 输入保持只读 | J1 |\n"+
			"| Caller | 上游 | 调用公开 API | 签名漂移导致编译失败 | 错误可判定 | J1 |\n\n"+
			"## 判断依据\n\n"+
			"| J-ID | 判断 | 来源 | 证据或推断 | 状态 |\n"+
			"|---|---|---|---|---|\n"+
			"| J1 | 保持输入只读 | 用户任务 | 明确要求 | 已确认 |\n\n"+
			"## 建模覆盖声明\n\n"+
			"| 维度 | 覆盖位置或具体不适用理由 |\n"+
			"|---|---|\n"+
			"| 数据流 | Scenario 标量覆盖 |\n"+
			"| 状态 | 无跨调用状态 |\n"+
			"| 时序 | Scenario 真实链路 |\n"+
			"| 资源 | 无外部资源 |\n"+
			"| 不变量 | 影响边界与不变量 |\n"+
			"| 故障 | Scenario 真实链路 |\n\n"+
			"## 验收清单\n\n"+
			"### 单元测试\n\n- [ ] 标量覆盖。\n\n"+
			"### Smoke 测试\n\n- [ ] 公开入口。\n\n"+
			"### E2E 测试\n\n- 决策：需要\n- 依据：真实调用链。\n\n"+
			"## 测试驱动开发\n\n1. 先写失败测试。\n\n"+
			"## 对抗性审查记录\n\n"+
			"| Review | 预算 | 风险来源 | 查询 | 召回 ID | 复用 Scenario | 新增 Scenario | CLI |\n"+
			"|---|---|---|---|---|---|---|---|\n"+
			"| ARV-1 | standard | no-corpus | 无 | 无 | 无 | 无 | skipped:no-corpus |\n\n"+
			"## Scenarios\n\n"+
			"### Scenario SC_01: 标量覆盖\n\n"+
			"- **GIVEN** 一个低优先级值\n"+
			"- **WHEN** 解析配置\n"+
			"- **THEN** 返回高优先级值\n"+
			"- 测试层：unit\n"+
			"- 依据：J1\n"+
			"- 来源：initial-spec\n\n"+
			"### Scenario SC_02: 真实链路\n\n"+
			"- **GIVEN** 一个公开调用方\n"+
			"- **WHEN** 调用公开 API\n"+
			"- **THEN** 得到稳定结果\n"+
			"- 测试层：e2e\n"+
			"- 依据：J1\n"+
			"- 来源：initial-spec\n",
	)
	return specDir
}

const checklistHeader = "| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |\n" +
	"|---|---|---|---|---|---|---|---|\n"

// makeTask 在 spec 下构造一个合法的 task（2 行任务，T2 依赖 T1）。
// 与 test_req_engine.py 的 make_task 一致。
func makeTask(t *testing.T, root, specName, taskName string) string {
	t.Helper()
	taskDir := filepath.Join(root, "docs", "spec", specName, "tasks", taskName)
	mustMkdir(t, taskDir)
	mustWrite(t, filepath.Join(taskDir, "dev-checklist.md"),
		"# "+taskName+"\n\n> spec: docs/spec/"+specName+"\n> risk: Q2\n\n"+
			checklistHeader+
			"| T1 | 实现覆盖 | SC_01 | J1 | resolver.py | None | [ ] ⏳ | None |\n"+
			"| T2 | 验证真实链路 | SC_02 | E2E | test_e2e.py | T1 | [ ] ⏳ | None |\n",
	)
	return taskDir
}

func mustMkdir(t *testing.T, path string) {
	t.Helper()
	if err := os.MkdirAll(path, 0o755); err != nil {
		t.Fatal(err)
	}
}

func mustWrite(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func rulesOf(issues []Issue) string {
	var rs []string
	for _, iss := range issues {
		rs = append(rs, iss.Rule)
	}
	return strings.Join(rs, ",")
}

func msgsOf(issues []Issue) string {
	var ms []string
	for _, iss := range issues {
		ms = append(ms, iss.Msg)
	}
	return strings.Join(ms, " ")
}

func assertInMsg(t *testing.T, issues []Issue, want string) {
	t.Helper()
	if !strings.Contains(msgsOf(issues), want) {
		t.Errorf("issues %v do not contain %q", issues, want)
	}
}

// ===== 校验测试 =====

func TestValidateAcceptsCompleteTask(t *testing.T) {
	root := t.TempDir()
	makeSpec(t, root, "demo")
	taskDir := makeTask(t, root, "demo", "resolver")
	if issues := ValidateIssues(taskDir); len(issues) != 0 {
		t.Fatalf("complete task should pass; got %d: %v", len(issues), issues)
	}
}

func TestValidateDanglingScenarioRejected(t *testing.T) {
	root := t.TempDir()
	makeSpec(t, root, "demo")
	taskDir := makeTask(t, root, "demo", "resolver")
	path := filepath.Join(taskDir, "dev-checklist.md")
	text, _ := os.ReadFile(path)
	mustWrite(t, path, strings.Replace(string(text), "SC_01 | J1", "SC_99 | J1", 1))
	issues := ValidateIssues(taskDir)
	if !strings.Contains(rulesOf(issues), "R3Q5") {
		t.Errorf("expected R3Q5 in rules: %s", rulesOf(issues))
	}
	assertInMsg(t, issues, "Scenario ID 悬空")
}

func TestValidateRejectsPendingJudgment(t *testing.T) {
	root := t.TempDir()
	specDir := makeSpec(t, root, "demo")
	makeTask(t, root, "demo", "resolver")
	// 把 spec 里的判断状态改成"待确认"，应触发 R3Q10。
	specPath := filepath.Join(specDir, "spec.md")
	text, _ := os.ReadFile(specPath)
	mustWrite(t, specPath, strings.Replace(string(text),
		"| J1 | 保持输入只读 | 用户任务 | 明确要求 | 已确认 |",
		"| J1 | 保持输入只读 | 用户任务 | 明确要求 | 待确认 |", 1))
	issues := ValidateIssues(filepath.Join(root, "docs", "spec", "demo", "tasks", "resolver"))
	if !strings.Contains(rulesOf(issues), "R3Q10") {
		t.Errorf("expected R3Q10: %s", rulesOf(issues))
	}
	assertInMsg(t, issues, "判断 J1 仍为待确认")
}

func TestValidateRequiresDiagramForThreeModules(t *testing.T) {
	root := t.TempDir()
	specDir := makeSpec(t, root, "demo")
	// 加第三个模块触发 R3Q9 的"≥3 模块必须有 diagram.md"。
	specPath := filepath.Join(specDir, "spec.md")
	text, _ := os.ReadFile(specPath)
	mustWrite(t, specPath, strings.Replace(string(text),
		"| Caller | 上游 | 调用公开 API |",
		"| Store | 下游 | 保存解析结果 | 写入失败导致结果丢失 | 失败可重试 | J1 |\n"+
			"| Caller | 上游 | 调用公开 API |", 1))
	taskDir := makeTask(t, root, "demo", "resolver")
	issues := ValidateIssues(taskDir)
	if !strings.Contains(rulesOf(issues), "R3Q9") {
		t.Errorf("expected R3Q9: %s", rulesOf(issues))
	}
	assertInMsg(t, issues, "缺少必需的 diagram.md")
}

// ===== status / graph 测试 =====

func TestStatusProgress(t *testing.T) {
	root := t.TempDir()
	makeSpec(t, root, "demo")
	taskDir := makeTask(t, root, "demo", "resolver")
	// 直接调内部 resolveTaskList + computeProgress 验证进度（不经过 CLI 输出）。
	tasks, _, err := resolveTaskList(taskDir)
	if err != nil {
		t.Fatal(err)
	}
	progress := computeProgress(tasks)
	want := map[string]int{"total": 2, "done": 0, "todo": 2, "blocked": 0}
	for k, v := range want {
		if progress[k] != v {
			t.Errorf("progress[%s] = %d, want %d", k, progress[k], v)
		}
	}
	var ids []string
	for _, tk := range tasks {
		ids = append(ids, tk.ID)
	}
	if strings.Join(ids, ",") != "T1,T2" {
		t.Errorf("task ids = %v, want [T1 T2]", ids)
	}
}

func TestGraphTopoOrder(t *testing.T) {
	root := t.TempDir()
	makeSpec(t, root, "demo")
	taskDir := makeTask(t, root, "demo", "resolver")
	tasks, _, err := resolveTaskList(taskDir)
	if err != nil {
		t.Fatal(err)
	}
	result := computeGraph(tasks)
	if strings.Join(result.Order, ",") != "T1,T2" {
		t.Errorf("order = %v, want [T1 T2]", result.Order)
	}
	if strings.Join(result.Ready, ",") != "T1" {
		t.Errorf("ready = %v, want [T1]", result.Ready)
	}
	if len(result.Blocked) != 1 || result.Blocked[0]["id"] != "T2" {
		t.Errorf("blocked = %v, want [{id:T2 missing:[T1]}]", result.Blocked)
	}
	missing, _ := result.Blocked[0]["missing"].([]string)
	if strings.Join(missing, ",") != "T1" {
		t.Errorf("T2 missing = %v, want [T1]", missing)
	}
}

func TestGraphDetectsCycle(t *testing.T) {
	// 手工构造环：T1 依赖 T2，T2 依赖 T1。
	tasks := []taskEntry{
		{ID: "T1", Title: "a", Status: StatusTodo, Deps: []string{"T2"}},
		{ID: "T2", Title: "b", Status: StatusTodo, Deps: []string{"T1"}},
	}
	result := computeGraph(tasks)
	if len(result.Cycle) != 2 {
		t.Fatalf("cycle = %v, want 2 nodes [T1 T2]", result.Cycle)
	}
	// 环上的节点顺序应稳定（按 id 排序）。
	if strings.Join(result.Cycle, ",") != "T1,T2" {
		t.Errorf("cycle = %v, want [T1 T2]", result.Cycle)
	}
	if len(result.Order) != 0 {
		t.Errorf("order should be empty for cyclic graph; got %v", result.Order)
	}
}

// ===== scaffold 测试 =====

func TestScaffoldCreatesChecklist(t *testing.T) {
	root := t.TempDir()
	makeSpec(t, root, "demo")
	taskDir := filepath.Join(root, "docs", "spec", "demo", "tasks", "resolver")
	code, err := Scaffold(taskDir, false, true)
	if err != nil || code != 0 {
		t.Fatalf("scaffold failed: code=%d err=%v", code, err)
	}
	checklist := filepath.Join(taskDir, "dev-checklist.md")
	text, err := os.ReadFile(checklist)
	if err != nil {
		t.Fatalf("dev-checklist.md not created: %v", err)
	}
	if !strings.Contains(string(text), "| Scenario IDs |") {
		t.Errorf("checklist missing Scenario IDs column")
	}
	if strings.Contains(string(text), "| Requirement |") {
		t.Errorf("checklist should not contain legacy Requirement column")
	}
}

func TestScaffoldAutoCreatesDiagramForThreeModules(t *testing.T) {
	root := t.TempDir()
	specDir := makeSpec(t, root, "demo")
	specPath := filepath.Join(specDir, "spec.md")
	text, _ := os.ReadFile(specPath)
	mustWrite(t, specPath, strings.Replace(string(text),
		"| Caller | 上游 | 调用公开 API |",
		"| Store | 下游 | 保存解析结果 | 写入失败导致结果丢失 | 失败可重试 | J1 |\n"+
			"| Caller | 上游 | 调用公开 API |", 1))
	taskDir := filepath.Join(specDir, "tasks", "resolver")
	code, err := Scaffold(taskDir, false, true)
	if err != nil || code != 0 {
		t.Fatalf("scaffold failed: code=%d err=%v", code, err)
	}
	if !fileExists(filepath.Join(taskDir, "diagram.md")) {
		t.Errorf("diagram.md should be auto-created for ≥3 modules")
	}
}
