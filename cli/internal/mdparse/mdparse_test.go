package mdparse

import (
	"strings"
	"testing"
)

func TestCells(t *testing.T) {
	cases := []struct {
		in   string
		want []string
	}{
		{"| a | b | c |", []string{"a", "b", "c"}},
		{"|a|b|c|", []string{"a", "b", "c"}},
		{"  |  spaced  |  ", []string{"spaced"}},
		{"|INV-SPEC-01 | 审批范围只能收窄 | 破坏 | B1 |", []string{"INV-SPEC-01", "审批范围只能收窄", "破坏", "B1"}},
	}
	for _, c := range cases {
		got := Cells(c.in)
		if len(got) != len(c.want) {
			t.Fatalf("Cells(%q) = %v (len %d), want %v (len %d)", c.in, got, len(got), c.want, len(c.want))
		}
		for i := range got {
			if got[i] != c.want[i] {
				t.Errorf("Cells(%q)[%d] = %q, want %q", c.in, i, got[i], c.want[i])
			}
		}
	}
}

func TestIsSeparator(t *testing.T) {
	ok := []string{"|----|----|----|", "|:---|:---:|---:|", "|------|", "|:----:|"}
	bad := []string{"| a | b |", "|--|x|", "", "| - |", "|:--|:-:|--:|"}
	for _, s := range ok {
		cells := Cells(s)
		if !IsSeparator(cells) {
			t.Errorf("IsSeparator(%q) = false, want true", s)
		}
	}
	for _, s := range bad {
		cells := Cells(s)
		if IsSeparator(cells) {
			t.Errorf("IsSeparator(%q) = true, want false", s)
		}
	}
}

func TestSection(t *testing.T) {
	text := "## 不变量覆盖\n\n| INV-ID | 结论 |\n|---|---|\n| INV-SPEC-01 | 破坏 |\n\n## 审查结论\n\nbody\n"
	body, ok := Section(text, "不变量覆盖")
	if !ok {
		t.Fatal("section not found")
	}
	if !strings.Contains(body, "INV-SPEC-01") {
		t.Errorf("section body lost table: %q", body)
	}
	if strings.Contains(body, "审查结论") {
		t.Errorf("section leaked into next heading: %q", body)
	}

	if _, ok := Section(text, "不存在"); ok {
		t.Error("missing section should not be found")
	}
}

func TestTables(t *testing.T) {
	section := "| ID | 状态 |\n|----|------|\n| B1 | ❌   |\n| B2 | ⚠️   |\n\nsome prose\n\n| INV-ID | 结论 |\n|---|---|\n| INV-SPEC-01 | 破坏 |\n"
	tables := Tables(section)
	if len(tables) != 2 {
		t.Fatalf("got %d tables, want 2", len(tables))
	}
	if got := tables[0].Headers; len(got) != 2 || got[0] != "ID" {
		t.Errorf("first table headers = %v, want [ID 状态]", got)
	}
	if len(tables[0].Rows) != 2 {
		t.Errorf("first table rows = %d, want 2", len(tables[0].Rows))
	}
	val, ok := RowValue(tables[0], tables[0].Rows[0], "状态")
	if !ok || val != "❌" {
		t.Errorf("RowValue(状态) = %q (%v), want ❌", val, ok)
	}
	if _, ok := RowValue(tables[0], tables[0].Rows[0], "不存在列"); ok {
		t.Error("RowValue on missing column should return false")
	}
}

func TestTablesDropsWrongWidthRows(t *testing.T) {
	section := "| H1 | H2 |\n|----|----|\n| a | b |\n| c |\n"
	tables := Tables(section)
	if len(tables) != 1 {
		t.Fatalf("got %d tables, want 1", len(tables))
	}
	if len(tables[0].Rows) != 1 {
		t.Errorf("rows = %d, want 1 (wrong-width row should be dropped)", len(tables[0].Rows))
	}
}
