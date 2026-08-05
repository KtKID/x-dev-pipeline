package flag

import (
	"strings"
	"testing"
)

// TestNormalizeAcceptsValid 对齐 test_xdev_flag.py 的合法输入归一化。
func TestNormalizeAcceptsValid(t *testing.T) {
	ids, sev, loc, msg, err := NormalizeInputs("T2,T3", "p0", "src/a.py:10", "空输入未处理")
	if err != nil {
		t.Fatalf("valid input rejected: %v", err)
	}
	if len(ids) != 2 || ids[0] != "T2" || ids[1] != "T3" {
		t.Errorf("task ids = %v, want [T2 T3]", ids)
	}
	if sev != "P0" {
		t.Errorf("severity = %q, want P0", sev)
	}
	if loc != "src/a.py:10" {
		t.Errorf("loc = %q, want src/a.py:10", loc)
	}
	if msg != "空输入未处理" {
		t.Errorf("msg = %q", msg)
	}
}

// TestNormalizeRejectsEmptyTasks 对齐 --task 含空项。
func TestNormalizeRejectsEmptyTasks(t *testing.T) {
	_, _, _, _, err := NormalizeInputs("T2,", "P0", "a.py:1", "x")
	if err == nil || !strings.Contains(err.Error(), "空项") {
		t.Fatalf("expected 空项 error, got %v", err)
	}
}

// TestNormalizeRejectsDuplicateTasks 对齐 --task 含重复项。
func TestNormalizeRejectsDuplicateTasks(t *testing.T) {
	_, _, _, _, err := NormalizeInputs("T2,T2", "P0", "a.py:1", "x")
	if err == nil || !strings.Contains(err.Error(), "重复") {
		t.Fatalf("expected 重复 error, got %v", err)
	}
}

// TestNormalizeRejectsBadTaskFormat 对齐 --task 仅接受 T1 形式。
func TestNormalizeRejectsBadTaskFormat(t *testing.T) {
	_, _, _, _, err := NormalizeInputs("X1", "P0", "a.py:1", "x")
	if err == nil || !strings.Contains(err.Error(), "T1、T2") {
		t.Fatalf("expected T1/T2 format error, got %v", err)
	}
}

// TestNormalizeRejectsBadSeverity 对齐 --severity 仅接受 P0/P1/P2。
func TestNormalizeRejectsBadSeverity(t *testing.T) {
	_, _, _, _, err := NormalizeInputs("T1", "P9", "a.py:1", "x")
	if err == nil || !strings.Contains(err.Error(), "P0、P1、P2") {
		t.Fatalf("expected P0/P1/P2 error, got %v", err)
	}
}

// TestNormalizeRejectsBadLoc 对齐 --loc 必须是 path:正整数。
func TestNormalizeRejectsBadLoc(t *testing.T) {
	cases := []string{"a.py", "a.py:0", "a.py:abc", "a.py:1|x"}
	for _, loc := range cases {
		_, _, _, _, err := NormalizeInputs("T1", "P0", loc, "x")
		if err == nil {
			t.Errorf("loc %q should be rejected", loc)
		}
	}
}

// TestNormalizeRejectsEmptyMsg 对齐 --msg 归一化后不能为空。
func TestNormalizeRejectsEmptyMsg(t *testing.T) {
	_, _, _, _, err := NormalizeInputs("T1", "P0", "a.py:1", "  \n  ")
	if err == nil || !strings.Contains(err.Error(), "不能为空") {
		t.Fatalf("expected empty msg error, got %v", err)
	}
}

// TestDowngradeTaskRows 对齐 test_xdev_flag.py 的状态降级。
func TestDowngradeTaskRows(t *testing.T) {
	text := "| # | 任务 | 状态 |\n|---|---|---|\n| T1 | a | [ ] ⏳ |\n| T2 | b | [ ] ⏳ |\n"
	newText, downgraded, err := downgradeTaskRows(text, []string{"T2"})
	if err != nil {
		t.Fatalf("downgrade failed: %v", err)
	}
	if len(downgraded) != 1 || downgraded[0] != "T2" {
		t.Errorf("downgraded = %v, want [T2]", downgraded)
	}
	if !strings.Contains(newText, "[!] 🔴") {
		t.Errorf("downgraded text missing [!] 🔴:\n%s", newText)
	}
	// T1 应保持不变。
	if !strings.Contains(newText, "| T1 | a | [ ] ⏳ |") {
		t.Errorf("T1 should be unchanged:\n%s", newText)
	}
}

// TestDowngradeSkipsAlreadyBlocked 对齐 test_xdev_flag.py 的已 blocked 不重复降级。
func TestDowngradeSkipsAlreadyBlocked(t *testing.T) {
	text := "| # | 任务 | 状态 |\n|---|---|---|\n| T1 | a | [!] 🔴 |\n"
	newText, downgraded, err := downgradeTaskRows(text, []string{"T1"})
	if err != nil {
		t.Fatalf("downgrade failed: %v", err)
	}
	if len(downgraded) != 0 {
		t.Errorf("already-blocked should not be downgraded: %v", downgraded)
	}
	if newText != text {
		t.Errorf("text should be unchanged for blocked row:\ngot: %s", newText)
	}
}

// TestNextIssueID 对齐 test_xdev_flag.py 的 issue 编号。
func TestNextIssueID(t *testing.T) {
	// 空 ledger → issue-1。
	if id := nextIssueID(""); id != "issue-1" {
		t.Errorf("empty ledger: id = %s, want issue-1", id)
	}
	// 有 issue-1, issue-3 → issue-4。
	report := "- issue-1 | P0 | T1 | a | x\n- issue-3 | P1 | T2 | b | y\n"
	if id := nextIssueID(report); id != "issue-4" {
		t.Errorf("id = %s, want issue-4", id)
	}
}
