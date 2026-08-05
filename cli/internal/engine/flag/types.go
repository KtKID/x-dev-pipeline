// Package flag 实现 skills/x-qa-gate/scripts/flag.py 的等价逻辑：
// QA Gate issue 登记与双文件可恢复事务引擎。
//
// # 职责
//
// 由 xdev flag 子命令调用，独立拥有：
//   - 输入校验（normalize_flag_inputs）
//   - checklist 状态降级（downgrade_task_rows：把目标行状态降为 [!] 🔴）
//   - issue ledger 编号（next_issue_id：分配下一个 issue-N）
//   - 双文件原子事务（commit_flag_transaction：marker + os.Link/fsync/os.Rename）
//   - 崩溃恢复（recover_flag_transaction：幂等前滚 pending 事务）
//
// # 设计约束
//
// 纯标准库（crypto/sha256 + syscall.Fsync + os.Link/os.Rename）。
// 中文错误信息逐字保留，以便与 test/test_xdev_flag.py 对拍。
// 事务语义与 Python 版完全一致：marker 文件保证崩溃安全。
package flag

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"regexp"
	"strings"
)

// ===== 正则（与 flag.py 顶层编译逐字对齐）=====

var (
	// tableSepRe 匹配 markdown 表格分隔行（字符集判定）。对齐 TABLE_SEP_RE。
	tableSepRe = regexp.MustCompile(`^\s*\|[\s:|-]+\|\s*$`)
	// idColRe 匹配 ID 列单元格里的数字（兼容 T1/#1/1）。对齐 ID_COL_RE。
	idColRe = regexp.MustCompile(`(?i)(?:T|#)?(\d+)`)
	// tokenRe 匹配状态列的 [x]/[ ]/[!] 复选框。对齐 TOKEN_RE。
	tokenRe = regexp.MustCompile(`\[(?P<box>[ x!])\]`)
	// flagTaskRe 校验 --task 参数格式（T1、T2...）。对齐 FLAG_TASK_RE。
	flagTaskRe = regexp.MustCompile(`T[1-9][0-9]*`)
	// issueLineRe 匹配 ledger 里的 issue 行首，用于 next_issue_id。对齐 ISSUE_LINE_RE。
	issueLineRe = regexp.MustCompile(`(?m)^- issue-([0-9]+) \|`)
	// reportNameRe 校验 QA Gate report 文件名并提取时间戳/后缀。对齐 REPORT_NAME_RE。
	reportNameRe = regexp.MustCompile(`^qa-gate-report-(?P<timestamp>[0-9]{8}-[0-9]{6})(?:-(?P<suffix>[0-9]+))?\.md$`)
)

// ===== 常量 =====

const (
	blocked            = "blocked"
	flagMarkerName     = ".flag-transaction.json"
	flagMarkerVersion  = 1
)

// ===== FlagError =====

// FlagError 是 flag 可操作错误，CLI 统一映射为退出码 2。对齐 flag.py 的 FlagError。
type FlagError struct{ msg string }

func (e *FlagError) Error() string { return e.msg }
func newFlagError(format string, args ...any) *FlagError {
	return &FlagError{msg: fmt.Sprintf(format, args...)}
}

// ===== SHA-256 helpers（对齐 _sha256_bytes / _sha256_file）=====

// sha256Bytes 返回字节序列的十六进制 SHA-256。
func sha256Bytes(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

// sha256File 返回文件内容的十六进制 SHA-256；文件不存在返回空串与 false。
func sha256File(path string) (string, bool) {
	f, err := os.Open(path)
	if err != nil {
		return "", false
	}
	defer f.Close()
	digest := sha256.New()
	buf := make([]byte, 1024*1024)
	for {
		n, err := f.Read(buf)
		if n > 0 {
			digest.Write(buf[:n])
		}
		if err != nil {
			break
		}
	}
	return hex.EncodeToString(digest.Sum(nil)), true
}

// ===== normalize_flag_inputs =====

// NormalizeInputs 校验并归一化 flag 参数（不接触文件系统）。
// 返回 (task_ids, severity, loc, msg)。对齐 flag.py 的 normalize_flag_inputs。
func NormalizeInputs(taskArg, severity, loc, msg string) ([]string, string, string, string, error) {
	rawTasks := strings.Split(taskArg, ",")
	var taskIDs []string
	for _, item := range rawTasks {
		taskIDs = append(taskIDs, strings.TrimSpace(item))
	}
	if len(taskIDs) == 0 {
		return nil, "", "", "", newFlagError("--task 含空项")
	}
	for _, item := range taskIDs {
		if item == "" {
			return nil, "", "", "", newFlagError("--task 含空项")
		}
	}
	// 校验每个 task id 格式（必须是 T1、T2...）。
	var invalid []string
	for _, item := range taskIDs {
		if !fullMatch(flagTaskRe, item) {
			invalid = append(invalid, item)
		}
	}
	if len(invalid) > 0 {
		return nil, "", "", "", newFlagError("--task 仅接受 T1、T2 形式：%s", strings.Join(invalid, ", "))
	}
	// 检查重复。
	seen := map[string]bool{}
	var duplicates []string
	for _, item := range taskIDs {
		if seen[item] {
			duplicates = append(duplicates, item)
		}
		seen[item] = true
	}
	if len(duplicates) > 0 {
		// 去重后排序，与 Python sorted(set(...)) 一致。
		dupSet := map[string]bool{}
		for _, d := range duplicates {
			dupSet[d] = true
		}
		var sortedDup []string
		for d := range dupSet {
			sortedDup = append(sortedDup, d)
		}
		sortStrings(sortedDup)
		return nil, "", "", "", newFlagError("--task 含重复项：%s", strings.Join(sortedDup, ", "))
	}

	// severity 校验。
	severity = strings.ToUpper(strings.TrimSpace(severity))
	if severity != "P0" && severity != "P1" && severity != "P2" {
		return nil, "", "", "", newFlagError("--severity 仅接受 P0、P1、P2")
	}

	// loc 校验：单行 path:正整数，不含竖线。
	loc = strings.TrimSpace(loc)
	if loc == "" || strings.Contains(loc, "|") || strings.Contains(loc, "\r") || strings.Contains(loc, "\n") {
		return nil, "", "", "", newFlagError("--loc 必须是单行 path:正整数，且不能包含竖线")
	}
	idx := strings.LastIndex(loc, ":")
	if idx <= 0 {
		return nil, "", "", "", newFlagError("--loc 必须是 path:正整数")
	}
	pathPart := loc[:idx]
	linePart := loc[idx+1:]
	if !fullMatch(regexp.MustCompile(`[1-9][0-9]*`), linePart) {
		return nil, "", "", "", newFlagError("--loc 必须是 path:正整数")
	}
	_ = pathPart

	// msg 归一化：换行转空格、去首尾空白、校验可打印。
	msg = strings.ReplaceAll(msg, "\r\n", " ")
	msg = strings.ReplaceAll(msg, "\r", " ")
	msg = strings.ReplaceAll(msg, "\n", " ")
	msg = strings.TrimSpace(msg)
	if msg == "" {
		return nil, "", "", "", newFlagError("--msg 归一化后不能为空")
	}
	for _, r := range msg {
		if !isPrintable(r) {
			return nil, "", "", "", newFlagError("--msg 只能包含可打印字符")
		}
	}
	return taskIDs, severity, loc, msg, nil
}

// fullMatch 判断正则是否完整匹配整个字符串（Python re.fullmatch 语义）。
func fullMatch(re *regexp.Regexp, s string) bool {
	loc := re.FindStringIndex(s)
	return loc != nil && loc[0] == 0 && loc[1] == len(s)
}

// isPrintable 判断 rune 是否可打印（对齐 Python str.isprintable）。
// Python: 不含 Other 或 Separator 类别，且不是 \t \n \r \x0b \x0c。
func isPrintable(r rune) bool {
	if r == '\t' || r == '\n' || r == '\r' || r == '\x0b' || r == '\x0c' {
		return false
	}
	// 简化：控制字符（< 0x20 或 0x7f-0x9f）算不可打印。
	if r < 0x20 || (r >= 0x7f && r <= 0x9f) {
		return false
	}
	return true
}

// sortStrings 是 sort.Strings 的薄封装（避免在 types.go 引入 sort 包）。
func sortStrings(s []string) {
	// 插入排序足够（列表很短）。
	for i := 1; i < len(s); i++ {
		for j := i; j > 0 && s[j-1] > s[j]; j-- {
			s[j-1], s[j] = s[j], s[j-1]
		}
	}
}

// errors.Is 的兜底引用（避免未使用）。
var _ = errors.Is
