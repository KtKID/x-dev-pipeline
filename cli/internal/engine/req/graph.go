package req

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
)

// ===== 任务状态解析 + 产物交叉验证 =====

// taskEntry 是 resolveTaskList 返回的单个任务结构（status/graph/status 共用）。
// 对齐 req.py resolve_task_list 返回的 task dict。
type taskEntry struct {
	ID           string   `json:"id"`
	Title        string   `json:"title"`
	Status       string   `json:"status"`
	Deps         []string `json:"deps"`
	Product      string   `json:"product,omitempty"`
	ProductCheck string   `json:"product_check,omitempty"` // "missing" 或 "stale"，无锚点则省略
}

// productIssue 是产物交叉验证发现的问题。对齐 req.py 的 product_issues dict。
type productIssue struct {
	ID   string `json:"id"`
	Rule string `json:"rule"`
	Msg  string `json:"msg"`
}

// resolveTaskList 解析 checklist 并判定引擎状态 + 产物锚点交叉验证。
// 返回 (tasks, product_issues)。product_check 规则：
//   - done 但 product 文件缺失 → "missing"
//   - todo 但 product 文件已存在 → "stale"
//   - 无 product 锚点 → 不设该字段
//
// 对齐 req.py 的 resolve_task_list。
func resolveTaskList(taskDir string) ([]taskEntry, []productIssue, error) {
	rows, err := parseChecklist(taskDir)
	if err != nil {
		return nil, nil, err
	}
	var tasks []taskEntry
	var productIssues []productIssue
	for _, t := range rows {
		status := taskEngineStatus(t.RawStatus)
		entry := taskEntry{
			ID:      t.ID,
			Title:   t.Title,
			Status:  status,
			Deps:    t.Deps,
			Product: t.Product,
		}
		// 有 product 锚点时做文件存在性交叉验证。
		if t.Product != "" {
			exists := fileExists(taskDir + "/" + t.Product)
			if status == StatusDone && !exists {
				entry.ProductCheck = "missing"
				productIssues = append(productIssues, productIssue{
					ID: t.ID, Rule: "product",
					Msg: fmt.Sprintf("标记 done 但产物缺失：%s", t.Product),
				})
			} else if status == StatusTodo && exists {
				entry.ProductCheck = "stale"
				productIssues = append(productIssues, productIssue{
					ID: t.ID, Rule: "product",
					Msg: fmt.Sprintf("标记 todo 但产物已存在：%s", t.Product),
				})
			}
		}
		tasks = append(tasks, entry)
	}
	return tasks, productIssues, nil
}

// computeProgress 统计 done/todo/blocked 进度。
// todo = total - done - blocked（blocked 是显式 [!] 状态，不计入 todo）。
// 对齐 req.py 的 compute_progress。
func computeProgress(tasks []taskEntry) map[string]int {
	total := len(tasks)
	done := 0
	blocked := 0
	for _, t := range tasks {
		switch t.Status {
		case StatusDone:
			done++
		case StatusBlocked:
			blocked++
		}
	}
	return map[string]int{
		"total":   total,
		"done":    done,
		"todo":    total - done - blocked,
		"blocked": blocked,
	}
}

// ===== Status 命令 =====

// Status 输出 task 当前状态和进度。对齐 req.py 的 status。
func Status(taskDir string, asJSON bool) (int, error) {
	tasks, productIssues, err := resolveTaskList(taskDir)
	if err != nil {
		return 2, err
	}
	progress := computeProgress(tasks)
	// 构造 payload（注意空数组用 [] 而非 nil，保持 JSON 一致）。
	payload := map[string]any{
		"task":     filepathBase(taskDir),
		"tasks":    tasks,
		"progress": progress,
	}
	if len(productIssues) > 0 {
		payload["product_issues"] = productIssues
	}
	if asJSON {
		out, _ := json.MarshalIndent(payload, "", "  ")
		fmt.Println(string(out))
	} else {
		fmt.Printf("== %s  status\n", filepathBase(taskDir))
		marks := map[string]string{StatusDone: "✓", StatusTodo: "·", StatusBlocked: "!"}
		for _, t := range tasks {
			deps := ""
			if len(t.Deps) > 0 {
				deps = " ← " + strings.Join(t.Deps, ",")
			}
			fmt.Printf("  %s %s  %s%s\n", marks[t.Status], t.ID, t.Title, deps)
		}
		p := progress
		fmt.Printf("  进度：%d/%d done · %d todo · %d blocked\n", p["done"], p["total"], p["todo"], p["blocked"])
	}
	return 0, nil
}

// ===== Graph 命令：依赖拓扑排序 =====

// topoSort 是 Kahn 拓扑排序 + 环检测。返回 (order, cycle_nodes)。
//
// 算法：
//  1. 算每个节点的入度（依赖数）
//  2. 入度 0 的进队列（按 id 排序，保证输出稳定）
//  3. 出队 → 加入 order → 它指向的后继入度减 1 → 新入度 0 的进队列
//  4. 没进过 order 的节点就是环上的节点（cycle）
//
// 关键性质：环上的节点永远不会变成入度 0，所以必然进不了 order。
// 对齐 req.py 的 topo_sort。
func topoSort(taskIDs []string, depsMap map[string][]string) ([]string, []string) {
	valid := map[string]bool{}
	for _, id := range taskIDs {
		valid[id] = true
	}
	// adj: dep → 依赖它的节点列表（边的方向：dep 完成后解锁后继）。
	adj := map[string][]string{}
	indeg := map[string]int{}
	for _, id := range taskIDs {
		adj[id] = nil
		indeg[id] = 0
	}
	for _, tid := range taskIDs {
		for _, dep := range depsMap[tid] {
			if valid[dep] {
				adj[dep] = append(adj[dep], tid)
				indeg[tid]++
			}
		}
	}
	// 入度 0 的初始队列（排序保证稳定输出）。
	var queue []string
	for _, id := range taskIDs {
		if indeg[id] == 0 {
			queue = append(queue, id)
		}
	}
	sort.Strings(queue)

	var order []string
	for len(queue) > 0 {
		node := queue[0]
		queue = queue[1:]
		order = append(order, node)
		// 释放后继：入度减 1，新入度 0 的收集后排序入队。
		var nexts []string
		for _, nxt := range adj[node] {
			indeg[nxt]--
			if indeg[nxt] == 0 {
				nexts = append(nexts, nxt)
			}
		}
		sort.Strings(nexts)
		queue = append(queue, nexts...)
	}
	// 没进 order 的 = 环上节点。
	inOrder := map[string]bool{}
	for _, id := range order {
		inOrder[id] = true
	}
	var cycle []string
	for _, id := range taskIDs {
		if !inOrder[id] {
			cycle = append(cycle, id)
		}
	}
	return order, cycle
}

// graphResult 是 computeGraph 的输出结构。
type graphResult struct {
	Ready          []string          `json:"ready"`
	Blocked        []map[string]any  `json:"blocked"`
	Order          []string          `json:"order"`
	ParallelBatches [][]string       `json:"parallel_batches"`
	Cycle          []string          `json:"cycle,omitempty"`
}

// computeGraph 算 ready / blocked / order / parallel_batches / cycle。
// 对齐 req.py 的 compute_graph。
func computeGraph(tasks []taskEntry) graphResult {
	byID := map[string]taskEntry{}
	var ids []string
	depsMap := map[string][]string{}
	for _, t := range tasks {
		byID[t.ID] = t
		ids = append(ids, t.ID)
		depsMap[t.ID] = t.Deps
	}
	order, cycle := topoSort(ids, depsMap)

	// ready：未 done 且依赖全部已 done 的节点。
	// blocked：未 done 且依赖有未完成或缺失的节点。
	var ready []string
	var blocked []map[string]any
	for _, t := range tasks {
		if t.Status == StatusDone {
			continue
		}
		var missing []string
		for _, dep := range t.Deps {
			depTask, ok := byID[dep]
			if !ok {
				missing = append(missing, dep)
			} else if depTask.Status != StatusDone {
				missing = append(missing, dep)
			}
		}
		if len(missing) > 0 {
			blocked = append(blocked, map[string]any{"id": t.ID, "missing": missing})
		} else {
			ready = append(ready, t.ID)
		}
	}

	// parallel_batches：按拓扑序分层，同一层的节点互相无依赖、可并行。
	// done 节点直接放入 placed，不占批次。
	doneIDs := map[string]bool{}
	for _, t := range tasks {
		if t.Status == StatusDone {
			doneIDs[t.ID] = true
		}
	}
	placed := map[string]bool{}
	for id := range doneIDs {
		placed[id] = true
	}
	var batches [][]string
	// 最多迭代 len(order) 轮，每轮收集一批可并行的节点。
	for range order {
		var layer []string
		for _, tid := range order {
			if placed[tid] {
				continue
			}
			if byID[tid].Status == StatusDone {
				placed[tid] = true
				continue
			}
			// 该节点所有依赖都已 placed 且依赖都在 byID（避免依赖悬空时误判）。
			allPlaced := true
			allKnown := true
			for _, dep := range depsMap[tid] {
				if _, ok := byID[dep]; !ok {
					allKnown = false
					break
				}
				if !placed[dep] {
					allPlaced = false
				}
			}
			if allKnown && allPlaced {
				layer = append(layer, tid)
			}
		}
		if len(layer) == 0 {
			break
		}
		for _, tid := range layer {
			placed[tid] = true
		}
		batches = append(batches, layer)
	}

	// 保证非 nil 切片（JSON 输出 [] 而非 null）。
	if ready == nil {
		ready = []string{}
	}
	if order == nil {
		order = []string{}
	}
	return graphResult{
		Ready:           ready,
		Blocked:         blocked,
		Order:           order,
		ParallelBatches: batches,
		Cycle:           cycle,
	}
}

// Graph 输出 task 的依赖拓扑（ready/blocked/order/parallel_batches/cycle）。
// 检测到环时退出码 1（阻断开发流程）。对齐 req.py 的 graph。
func Graph(taskDir string, asJSON bool) (int, error) {
	tasks, _, err := resolveTaskList(taskDir)
	if err != nil {
		return 2, err
	}
	result := computeGraph(tasks)

	// 环检测：cycle 非空时输出错误并返回退出码 1。
	if len(result.Cycle) > 0 {
		// 保证 parallel_batches 非 nil（JSON [] 而非 null，与 Python 一致）。
		batches := result.ParallelBatches
		if batches == nil {
			batches = [][]string{}
		}
		if asJSON {
			payload := map[string]any{
				"task":             filepathBase(taskDir),
				"error":            "dependency_cycle",
				"cycle_nodes":      result.Cycle,
				"ready":            result.Ready,
				"blocked":          result.Blocked,
				"order":            result.Order,
				"parallel_batches": batches,
			}
			out, _ := json.MarshalIndent(payload, "", "  ")
			fmt.Println(string(out))
			return 1, nil
		}
		return 1, fmt.Errorf("检测到依赖环：%s", strings.Join(result.Cycle, ", "))
	}

	if asJSON {
		payload := map[string]any{
			"task":             filepathBase(taskDir),
			"ready":            result.Ready,
			"blocked":          result.Blocked,
			"order":            result.Order,
			"parallel_batches": result.ParallelBatches,
		}
		out, _ := json.MarshalIndent(payload, "", "  ")
		fmt.Println(string(out))
	} else {
		fmt.Printf("== %s  graph\n", filepathBase(taskDir))
		fmt.Printf("  拓扑序：%s\n", strings.Join(result.Order, " → "))
		if len(result.Ready) > 0 {
			fmt.Printf("  可执行 (ready)：%s\n", strings.Join(result.Ready, ", "))
		}
		for _, b := range result.Blocked {
			missing, _ := b["missing"].([]string)
			id, _ := b["id"].(string)
			fmt.Printf("  阻塞 %s：缺 %s\n", id, strings.Join(missing, ", "))
		}
		for i, batch := range result.ParallelBatches {
			fmt.Printf("  并行批次 %d：%s\n", i+1, strings.Join(batch, ", "))
		}
	}
	return 0, nil
}

// ===== helpers =====

// readDirSorted 返回目录下子目录名（排序）。对齐 Python sorted(iterdir())。
func readDirSorted(dir string) ([]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var names []string
	for _, e := range entries {
		if e.IsDir() {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)
	return names, nil
}

// filepathBase 是 filepath.Base 的薄封装，便于 mock。
func filepathBase(path string) string {
	// 用 / 和 \ 都切，兼容 Windows 路径。
	path = strings.ReplaceAll(path, "\\", "/")
	if idx := strings.LastIndex(path, "/"); idx >= 0 {
		return path[idx+1:]
	}
	return path
}

// toUpperCase 是 strings.ToUpper 的薄封装。
func toUpperCase(s string) string { return strings.ToUpper(s) }

// splitLines 按通用换行符拆行（\r\n / \r → \n 后 split）。
func splitLines(s string) []string {
	s = strings.ReplaceAll(s, "\r\n", "\n")
	s = strings.ReplaceAll(s, "\r", "\n")
	return strings.Split(s, "\n")
}

// sprintf 是 fmt.Sprintf 的包内别名，供 errf 等处构造中文错误信息。
var sprintf = fmt.Sprintf
