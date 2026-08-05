package flag

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"syscall"
)

// ===== 路径校验 =====

// relativeTransactionPath 返回 path 相对 taskDir 的相对路径；越界抛错。
// 对齐 flag.py 的 _relative_transaction_path。
func relativeTransactionPath(taskDir, path string) (string, error) {
	absPath, err := filepath.Abs(path)
	if err != nil {
		return "", newFlagError("事务路径越出 task 目录：%s", path)
	}
	absTask, err := filepath.Abs(taskDir)
	if err != nil {
		return "", newFlagError("事务路径越出 task 目录：%s", path)
	}
	rel, err := filepath.Rel(absTask, absPath)
	if err != nil || strings.HasPrefix(rel, "..") {
		return "", newFlagError("事务路径越出 task 目录：%s", path)
	}
	// filepath.Rel 用反斜杠（Windows），统一成正斜杠。
	return filepath.ToSlash(rel), nil
}

// resolveTransactionPath 校验 marker 里的相对路径，防止路径逃逸。对齐 _resolve_transaction_path。
func resolveTransactionPath(taskDir, raw string) (string, error) {
	if raw == "" || filepath.IsAbs(raw) {
		return "", newFlagError("事务标记包含非法相对路径：%q", raw)
	}
	absTask, _ := filepath.Abs(taskDir)
	resolved := filepath.Join(absTask, raw)
	resolvedAbs, err := filepath.Abs(resolved)
	if err != nil {
		return "", newFlagError("事务标记路径越出 task 目录：%s", raw)
	}
	rel, err := filepath.Rel(absTask, resolvedAbs)
	if err != nil || strings.HasPrefix(rel, "..") {
		return "", newFlagError("事务标记路径越出 task 目录：%s", raw)
	}
	return resolvedAbs, nil
}

// ===== fsync 封装（跨平台）=====

// fsyncDirectory 对目录执行 fsync，保证目录条目变更落盘。对齐 _fsync_directory。
// darwin/linux: 用 syscall.Open 拿只读 fd，再 Fsync。
func fsyncDirectory(dir string) error {
	fd, err := syscall.Open(dir, syscall.O_RDONLY, 0)
	if err != nil {
		return err
	}
	defer syscall.Close(fd)
	return syscall.Fsync(fd)
}

// writeDurableTemp 以 O_EXCL 创建临时文件、写入、flush + fsync。
// 对齐 flag.py 的 _write_durable_temp。
func writeDurableTemp(path string, data []byte) error {
	fd, err := syscall.Open(path, syscall.O_WRONLY|syscall.O_CREAT|syscall.O_EXCL, 0o600)
	if err != nil {
		return err
	}
	f := os.NewFile(uintptr(fd), path)
	_, err = f.Write(data)
	if err == nil {
		err = f.Sync() // fsync
	}
	if cerr := f.Close(); err == nil {
		err = cerr
	}
	return err
}

// ===== 事务 marker 结构 =====

// transactionTarget 描述事务的一个目标文件。
type transactionTarget struct {
	Target       string `json:"target"`         // 相对 taskDir 的目标路径
	Temp         string `json:"temp"`            // 临时文件相对路径
	SHA256       string `json:"sha256"`          // 目标期望内容的 SHA-256
	BeforeSHA256 string `json:"before_sha256"`   // 目标原内容 SHA-256（新建时为空）
}

// transactionResult 是 marker 里的 result 字段。
type transactionResult struct {
	Issue      string   `json:"issue"`
	Downgraded []string `json:"downgraded"`
	Report     string   `json:"report"`
	Recovered  bool     `json:"recovered"`
}

// transactionMarker 是 .flag-transaction.json 的完整结构。
type transactionMarker struct {
	Version     int                  `json:"version"`
	Transaction string               `json:"transaction"`
	MarkerTemp  string               `json:"marker_temp"`
	Targets     []transactionTarget  `json:"targets"`
	Result      transactionResult    `json:"result"`
}

// ===== 崩溃恢复 =====

// recoverFlagTransaction 幂等前滚 pending flag 事务；成功后返回原 issue 结果。
// marker 不存在返回 (nil, nil)。对齐 flag.py 的 recover_flag_transaction。
func recoverFlagTransaction(taskDir string) (*transactionResult, error) {
	markerPath := filepath.Join(taskDir, "reports", "qa-gate", flagMarkerName)
	data, err := os.ReadFile(markerPath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, newFlagError("读取事务标记失败，marker 已保留：%v", err)
	}
	var marker transactionMarker
	if err := json.Unmarshal(data, &marker); err != nil {
		return nil, newFlagError("读取事务标记失败，marker 已保留：%v", err)
	}
	if marker.Version != flagMarkerVersion {
		return nil, newFlagError("不支持的事务标记版本：%d", marker.Version)
	}
	if len(marker.Targets) != 2 {
		return nil, newFlagError("事务标记必须包含两个目标")
	}
	shaRe := regexp.MustCompile(`^[0-9a-f]{64}$`)

	for _, entry := range marker.Targets {
		target, err := resolveTransactionPath(taskDir, entry.Target)
		if err != nil {
			return nil, err
		}
		temp, err := resolveTransactionPath(taskDir, entry.Temp)
		if err != nil {
			return nil, err
		}
		if !shaRe.MatchString(entry.SHA256) {
			return nil, newFlagError("事务标记目标哈希非法：%s", target)
		}
		if entry.BeforeSHA256 != "" && !shaRe.MatchString(entry.BeforeSHA256) {
			return nil, newFlagError("事务标记旧目标哈希非法：%s", target)
		}
		current, existed := sha256File(target)
		if existed && current == entry.SHA256 {
			continue // 已提交
		}
		if !existed {
			current = ""
		}
		if current != entry.BeforeSHA256 {
			return nil, newFlagError("事务目标已被其他写入修改：%s；当前 %s，事务读取时 %s", target, current, entry.BeforeSHA256)
		}
		// 需要 temp 文件前滚。
		if _, err := os.Stat(temp); err != nil {
			return nil, newFlagError("事务恢复材料缺失：%s；目标 %s 期望 SHA-256 %s", temp, target, entry.SHA256)
		}
		if err := os.Rename(temp, target); err != nil {
			// Rename 在源不存在时会失败；检查目标是否已是期望状态。
			cur, ex := sha256File(target)
			if !ex || cur != entry.SHA256 {
				return nil, err
			}
		}
		if err := fsyncDirectory(filepath.Dir(target)); err != nil {
			return nil, newFlagError("事务恢复失败，marker 已保留：%v", err)
		}
		cur, ex := sha256File(target)
		if !ex || cur != entry.SHA256 {
			return nil, newFlagError("事务恢复后哈希不匹配：%s；期望 %s", target, entry.SHA256)
		}
	}

	// 清理 marker（marker_temp + marker 本身）。
	markerTempPath, _ := resolveTransactionPath(taskDir, marker.MarkerTemp)
	markerDir := filepath.Dir(markerPath)
	if marker.MarkerTemp != "" {
		_ = os.Remove(markerTempPath)
	}
	if err := os.Remove(markerPath); err != nil {
		return nil, newFlagError("事务目标已完成，但 marker 清理失败：%v", err)
	}
	_ = fsyncDirectory(markerDir)
	result := marker.Result
	result.Recovered = true
	return &result, nil
}

// ===== 提交事务 =====

// commitFlagTransaction 完整发布 marker 后提交两个目标；竞争者转入既有事务恢复。
// 对齐 flag.py 的 commit_flag_transaction。
func commitFlagTransaction(
	taskDir, checklistPath, checklistText string,
	reportPath, reportText string,
	result transactionResult,
	checklistBeforeSHA, reportBeforeSHA string,
) (*transactionResult, error) {
	transactionID := newTransactionID()
	reportsDir := filepath.Join(taskDir, "reports", "qa-gate")
	_ = os.MkdirAll(reportsDir, 0o755)
	_ = os.MkdirAll(filepath.Dir(checklistPath), 0o755)
	_ = os.MkdirAll(filepath.Dir(reportPath), 0o755)

	checklistContent := []byte(checklistText)
	reportContent := []byte(reportText)

	type targetContent struct {
		path    string
		content []byte
		before  string
	}
	targetContents := []targetContent{
		{checklistPath, checklistContent, checklistBeforeSHA},
		{reportPath, reportContent, reportBeforeSHA},
	}

	var prepared []string // 已创建的临时文件（失败时回滚）
	var targets []transactionTarget
	markerTemp := filepath.Join(reportsDir, fmt.Sprintf(".%s.%s.tmp", flagMarkerName, transactionID))
	markerPath := filepath.Join(reportsDir, flagMarkerName)
	markerPublished := false

	// 1. 为每个目标写 durable temp + 算 sha。
	for _, tc := range targetContents {
		temp := filepath.Join(filepath.Dir(tc.path), fmt.Sprintf(".%s.flag-%s.tmp", filepath.Base(tc.path), transactionID))
		if err := writeDurableTemp(temp, tc.content); err != nil {
			cleanupFiles(prepared)
			return nil, newFlagError("flag 事务 IO 失败（业务文件未提交）：%v", err)
		}
		prepared = append(prepared, temp)
		relTarget, _ := relativeTransactionPath(taskDir, tc.path)
		relTemp, _ := relativeTransactionPath(taskDir, temp)
		targets = append(targets, transactionTarget{
			Target:       relTarget,
			Temp:         relTemp,
			SHA256:       sha256Bytes(tc.content),
			BeforeSHA256: tc.before,
		})
	}

	// 2. 写 marker temp 并发布（os.Link 原子创建 marker）。
	marker := transactionMarker{
		Version:     flagMarkerVersion,
		Transaction: transactionID,
		MarkerTemp:  mustRel(taskDir, markerTemp),
		Targets:     targets,
		Result:      result,
	}
	markerBytes, _ := json.Marshal(marker)
	if err := writeDurableTemp(markerTemp, markerBytes); err != nil {
		cleanupFiles(prepared)
		return nil, newFlagError("flag 事务 IO 失败（业务文件未提交）：%v", err)
	}
	prepared = append(prepared, markerTemp)

	if err := os.Link(markerTemp, markerPath); err != nil {
		// marker 已存在 → 有并发事务，尝试恢复它。
		if os.IsExist(err) {
			cleanupFiles(prepared)
			recovered, recErr := recoverFlagTransaction(taskDir)
			if recErr != nil {
				return nil, recErr
			}
			if recovered == nil {
				return nil, newFlagError("事务标记竞争后消失，请重试 flag")
			}
			return recovered, nil
		}
		cleanupFiles(prepared)
		return nil, newFlagError("flag 事务 IO 失败（业务文件未提交）：%v", err)
	}
	markerPublished = true
	_ = os.Remove(markerTemp)
	_ = fsyncDirectory(reportsDir)

	// 3. stale 检查：提交前确认目标未被其他写入改过。
	var staleTargets []string
	for _, entry := range targets {
		target, _ := resolveTransactionPath(taskDir, entry.Target)
		current, existed := sha256File(target)
		if !existed {
			current = ""
		}
		if current != entry.BeforeSHA256 && current != entry.SHA256 {
			staleTargets = append(staleTargets, target)
		}
	}
	if len(staleTargets) > 0 {
		_ = os.Remove(markerPath)
		_ = fsyncDirectory(reportsDir)
		markerPublished = false
		cleanupFiles(prepared)
		return nil, newFlagError("事务读取后目标发生变化，请重试 flag：%s", joinStr(staleTargets, ", "))
	}

	// 4. 逐个 replace temp → target，每个 fsync 目录。
	for _, entry := range targets {
		target, _ := resolveTransactionPath(taskDir, entry.Target)
		temp, _ := resolveTransactionPath(taskDir, entry.Temp)
		current, existed := sha256File(target)
		if !existed {
			current = ""
		}
		if current == entry.SHA256 {
			continue
		}
		if err := os.Rename(temp, target); err != nil {
			cur, ex := sha256File(target)
			if !ex || cur != entry.SHA256 {
				cleanupOnFailure(prepared, markerPath, reportsDir, markerPublished)
				return nil, newFlagError("flag 事务 IO 失败（marker 已保留，可由下次 flag 恢复）：%v", err)
			}
		}
		_ = fsyncDirectory(filepath.Dir(target))
		cur, ex := sha256File(target)
		if !ex || cur != entry.SHA256 {
			cleanupOnFailure(prepared, markerPath, reportsDir, markerPublished)
			return nil, newFlagError("事务提交后哈希不匹配：%s", target)
		}
	}

	// 5. 提交完成，删 marker。
	_ = os.Remove(markerPath)
	_ = fsyncDirectory(reportsDir)
	resultCopy := result
	return &resultCopy, nil
}

// cleanupFiles 删除一组临时文件（失败回滚）。
func cleanupFiles(paths []string) {
	for _, p := range paths {
		_ = os.Remove(p)
	}
}

// cleanupOnFailure 在提交阶段失败时按 markerPublished 状态清理。
func cleanupOnFailure(prepared []string, markerPath, reportsDir string, markerPublished bool) {
	if !markerPublished {
		cleanupFiles(prepared)
	}
}

// mustRel 是 relativeTransactionPath 的 panic 版（仅用于 marker_temp，路径已知合法）。
func mustRel(taskDir, path string) string {
	rel, err := relativeTransactionPath(taskDir, path)
	if err != nil {
		return filepath.Base(path) // 兜底
	}
	return rel
}

// joinStr 用 sep 连接字符串。
func joinStr(parts []string, sep string) string {
	return strings.Join(parts, sep)
}

// newTransactionID 生成一个 32 字符的十六进制事务 ID（等价于 Python uuid4().hex）。
// 用 crypto/rand 保持零外部依赖。
func newTransactionID() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	// 设置 version 4 和 variant 位，与 RFC 4122 uuid4 一致。
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return hex.EncodeToString(b)
}
