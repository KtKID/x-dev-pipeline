package verify

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// writeFile 写临时文件并返回路径。
func writeFile(t *testing.T, dir, name, content string) string {
	t.Helper()
	path := filepath.Join(dir, name)
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}

// newTimeFuture 返回一个未来的时间，用于让某文件 mtime 明显更新。
func newTimeFuture() time.Time {
	return time.Now().Add(1 * time.Hour)
}

// TestParseVerifyBlocksAcceptsValid 对齐 test_xdev_verify.py 的合法块解析。
func TestParseVerifyBlocksAcceptsValid(t *testing.T) {
	dir := t.TempDir()
	report := writeFile(t, dir, "dev-report.md",
		"```verify\n"+
			"id: V1\nscenario: SC_01\nmode: auto\n"+
			"cmd: python3 -c \"print('ok')\"\nexpect_exit: 0\n"+
			"expect_contains: ok\n"+
			"```\n"+
			"```verify\n"+
			"id: V2\nscenario: SC_02\nmode: manual\nsteps: 人工确认\n"+
			"```\n")
	blocks, err := ParseVerifyBlocks(report)
	if err != nil {
		t.Fatalf("parse failed: %v", err)
	}
	if len(blocks) != 2 {
		t.Fatalf("got %d blocks, want 2", len(blocks))
	}
	if blocks[0].ID != "V1" || blocks[0].Mode != "auto" {
		t.Errorf("block0 = %+v, want id=V1 mode=auto", blocks[0])
	}
	if blocks[0].ExpectExit != 0 {
		t.Errorf("block0 expect_exit = %d, want 0", blocks[0].ExpectExit)
	}
	if len(blocks[0].ExpectContains) != 1 || blocks[0].ExpectContains[0] != "ok" {
		t.Errorf("block0 expect_contains = %v, want [ok]", blocks[0].ExpectContains)
	}
	if blocks[1].Mode != "manual" || blocks[1].Steps != "人工确认" {
		t.Errorf("block1 = %+v, want mode=manual steps=人工确认", blocks[1])
	}
}

// TestParseVerifyBlocksRejectsDuplicateID 对齐 test_xdev_verify.py 的重复 id 拒绝。
func TestParseVerifyBlocksRejectsDuplicateID(t *testing.T) {
	dir := t.TempDir()
	report := writeFile(t, dir, "dev-report.md",
		"```verify\nid: V1\nmode: auto\ncmd: echo a\n```\n"+
			"```verify\nid: V1\nmode: auto\ncmd: echo b\n```\n")
	_, err := ParseVerifyBlocks(report)
	if err == nil || !strings.Contains(err.Error(), "重复") {
		t.Fatalf("expected 重复 error, got %v", err)
	}
}

// TestParseVerifyBlocksRejectsUnknownKey 对齐 test_xdev_verify.py 的未知 key 拒绝。
func TestParseVerifyBlocksRejectsUnknownKey(t *testing.T) {
	dir := t.TempDir()
	report := writeFile(t, dir, "dev-report.md",
		"```verify\nid: V1\nbogus: x\ncmd: echo a\n```\n")
	_, err := ParseVerifyBlocks(report)
	if err == nil || !strings.Contains(err.Error(), "未知 key") {
		t.Fatalf("expected 未知 key error, got %v", err)
	}
}

// TestParseVerifyBlocksRejectsManualWithoutSteps manual 模式必须有 steps。
func TestParseVerifyBlocksRejectsManualWithoutSteps(t *testing.T) {
	dir := t.TempDir()
	report := writeFile(t, dir, "dev-report.md",
		"```verify\nid: V1\nmode: manual\n```\n")
	_, err := ParseVerifyBlocks(report)
	if err == nil || !strings.Contains(err.Error(), "manual 模式缺少 steps") {
		t.Fatalf("expected manual steps error, got %v", err)
	}
}

// TestLatestDevReportPicksNewest 选最新的 dev-report（按 mtime + name）。
func TestLatestDevReportPicksNewest(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "dev-report.md", "old\n")
	// 稍后再写一个带时间戳的，确保它更新。
	newer := writeFile(t, dir, "dev-report-20260101-120000.md", "new\n")
	// 修正新文件的 mtime 为更晚的时间。
	newTime := newTimeFuture()
	if err := os.Chtimes(newer, newTime, newTime); err != nil {
		t.Fatal(err)
	}
	got, err := LatestDevReport(dir)
	if err != nil {
		t.Fatal(err)
	}
	if got != newer {
		t.Errorf("LatestDevReport = %s, want %s", got, newer)
	}
}
