package spec

import (
	"fmt"
	"os"
	"regexp"
	"strings"
)

// metadata 解析顶部七个固定元数据字段，并检查顺序、重复、空行和一级标题。
// 对齐 spec.py 的 _metadata。
func metadata(lines []string) (map[string]string, []Issue) {
	values := map[string]string{}
	var issues []Issue
	for number, line := range lines {
		m := fieldRe.FindStringSubmatch(line)
		if m == nil {
			continue
		}
		key := m[1]
		if _, ok := contains(HeaderFields, key); !ok {
			continue
		}
		value := strings.TrimSpace(m[2])
		if _, exists := values[key]; exists {
			issues = append(issues, issue("spec.md", number+1, "V19", fmt.Sprintf("元数据字段重复：%s", key)))
		} else {
			values[key] = value
		}
	}
	for index, key := range HeaderFields {
		number := index + 1
		if index >= len(lines) {
			issues = append(issues, issue("spec.md", number, "V19", fmt.Sprintf("第 %d 行必须为 > %s: <值>", number, key)))
			continue
		}
		m := fieldRe.FindStringSubmatch(lines[index])
		if m == nil || m[1] != key || strings.TrimSpace(m[2]) == "" {
			issues = append(issues, issue("spec.md", number, "V19", fmt.Sprintf("第 %d 行必须为 > %s: <值>", number, key)))
		}
	}
	if len(lines) < 8 || lines[7] != "" {
		issues = append(issues, issue("spec.md", 8, "V19", "七个元数据字段后第八行必须为空行"))
	}
	if len(lines) < 9 {
		issues = append(issues, issue("spec.md", 9, "V19", "第九行必须为已填写的 # <spec-name>"))
	} else {
		title := h1Re.FindStringSubmatch(lines[8])
		if title == nil || strings.TrimSpace(title[1]) == "<spec-name>" {
			issues = append(issues, issue("spec.md", 9, "V19", "第九行必须为已填写的 # <spec-name>"))
		}
	}
	return values, issues
}

// metadataIssues 校验版本、双评分、平均分、预算和审查状态。对齐 _metadata_issues。
func metadataIssues(lines []string, requireReady bool) (map[string]string, []Issue) {
	md, issues := metadata(lines)
	version := md["spec_version"]
	if version != "3" {
		issues = append(issues, issue("spec.md", 1, "V19", "spec_version 必须为 3"))
	}
	if md["adversarial_risk_version"] != "3" {
		issues = append(issues, issue("spec.md", 2, "V19", "当前 iteration-7 要求 adversarial_risk_version 为 3"))
	}

	scores := map[string]int{}
	scoreRe := regexp.MustCompile(`^[1-5]$`)
	for _, kv := range []struct{ key, line string }{
		{"complexity", "3"}, {"importance", "4"},
	} {
		number, _ := atoi(kv.line)
		val := md[kv.key]
		if !scoreRe.MatchString(val) {
			issues = append(issues, issue("spec.md", number, "V19", fmt.Sprintf("%s 必须为 1..5 的整数", kv.key)))
		} else {
			n, _ := atoi(val)
			scores[kv.key] = n
		}
	}

	avgText := md["risk_average"]
	avgRe := regexp.MustCompile(`^[1-5]\.[05]$`)
	var average float64
	avgValid := false
	if !avgRe.MatchString(avgText) {
		issues = append(issues, issue("spec.md", 5, "V19", "risk_average 必须为 1.0..5.0 且以 .0 或 .5 结尾"))
	} else {
		average, _ = parseFloat(avgText)
		avgValid = true
	}

	budget := md["review_budget"]
	if !validBudgets[budget] {
		issues = append(issues, issue("spec.md", 6, "V19", "review_budget 必须为 standard、deep 或 full"))
	}
	if len(scores) == 2 {
		expectedAvg := float64(scores["complexity"]+scores["importance"]) / 2
		if avgValid && average != expectedAvg {
			issues = append(issues, issue("spec.md", 5, "V19", fmt.Sprintf("risk_average 应为 %.1f", expectedAvg)))
		}
		required := expectedBudget(scores["complexity"], scores["importance"])
		if budget != "" && budget != required {
			issues = append(issues, issue("spec.md", 6, "V19", fmt.Sprintf("review_budget 应为 %s", required)))
		}
	}

	status := md["adversarial_review"]
	if !validStatuses[status] {
		issues = append(issues, issue("spec.md", 7, "V19", "adversarial_review 必须为 pending、skipped-standard 或 complete"))
	} else if status == "skipped-standard" && budget != "standard" {
		issues = append(issues, issue("spec.md", 7, "V19", "skipped-standard 只适用于 standard 预算"))
	} else if status == "complete" && budget == "standard" {
		issues = append(issues, issue("spec.md", 7, "V19", "standard 预算完成态必须为 skipped-standard"))
	} else if status == "pending" && requireReady {
		issues = append(issues, issue("spec.md", 7, "V19", "对抗性风险审查仍为 pending，阻断 x-req"))
	}
	return md, issues
}

// packageIssues 检查 spec 根目录保持单文件结构。对齐 _package_issues。
func packageIssues(specDir string) []Issue {
	var issues []Issue
	entries, err := os.ReadDir(specDir)
	if err != nil {
		return issues
	}
	for _, entry := range entries {
		name := entry.Name()
		if strings.HasPrefix(name, ".") || name == "spec.md" {
			continue
		}
		if entry.IsDir() && name == "tasks" {
			continue
		}
		issues = append(issues, issue(
			name, 0, "V19",
			fmt.Sprintf("spec 单文件包根目录只允许 spec.md 和后续 tasks/：%s", name),
		))
	}
	return issues
}

// requiredSectionIssues 检查固定二级章节的存在性、唯一性和关键章节非空要求。对齐 _required_section_issues。
func requiredSectionIssues(lines []string) []Issue {
	var issues []Issue
	for _, section := range requiredSections {
		occ := sectionOccurrences(lines, section)
		if len(occ) == 0 {
			issues = append(issues, issue("spec.md", 0, "V19", fmt.Sprintf("缺少二级节「%s」", section)))
		} else if len(occ) > 1 {
			issues = append(issues, issue("spec.md", occ[1]+1, "V19", fmt.Sprintf("二级节「%s」重复", section)))
		}
	}
	for _, section := range []string{"任务目标", "非目标", "风险评分依据", "测试驱动开发"} {
		if len(sectionOccurrences(lines, section)) > 0 && !sectionHasContent(lines, section) {
			issues = append(issues, issue("spec.md", 0, "V19", fmt.Sprintf("二级节「%s」内容为空", section)))
		}
	}
	return issues
}

// templatePlaceholderIssues 检测反引号代码之外仍未替换的尖括号模板占位符。对齐 _template_placeholder_issues。
func templatePlaceholderIssues(lines []string) []Issue {
	var issues []Issue
	placeholderRe := regexp.MustCompile(`<[^>\n]+>`)
	backtickRe := regexp.MustCompile("`[^`]*`")
	for number, line := range lines {
		prose := backtickRe.ReplaceAllString(line, "")
		placeholders := placeholderRe.FindAllString(prose, -1)
		if len(placeholders) > 0 {
			issues = append(issues, issue("spec.md", number+1, "V19", fmt.Sprintf("删除模板注释或占位符：%s", strings.Join(placeholders, "、"))))
		}
	}
	return issues
}

// riskBasisIssues 检查风险评分依据包含非空的复杂度、重要性和预算升级说明。对齐 _risk_basis_issues。
func riskBasisIssues(lines []string) []Issue {
	start, end, ok := sectionRange(lines, "风险评分依据")
	if !ok {
		return nil
	}
	var issues []Issue
	for _, field := range riskBasisFields {
		fieldReLine := regexp.MustCompile(fmt.Sprintf(`^\s*[-*+]\s*%s\s*[：:]\s*(.+?)\s*$`, regexp.QuoteMeta(field)))
		fieldMarker := regexp.MustCompile(fmt.Sprintf(`^\s*[-*+]\s*%s\s*[：:]`, regexp.QuoteMeta(field)))
		found := false
		for index := start; index < end; index++ {
			if !fieldMarker.MatchString(lines[index]) {
				continue
			}
			if m := fieldReLine.FindStringSubmatch(lines[index]); m != nil && strings.TrimSpace(m[1]) != "" {
				found = true
			}
			break
		}
		if !found {
			issues = append(issues, issue("spec.md", start, "V19", fmt.Sprintf("风险评分依据缺少非空「%s」项", field)))
		}
	}
	return issues
}

// tableIssues 校验影响边界、判断依据和建模覆盖三张核心表及其就绪条件。对齐 _table_issues。
func tableIssues(lines []string, requireReady bool) []Issue {
	var issues []Issue

	// 影响边界与不变量
	bh, br := sectionTable(lines, "影响边界与不变量")
	if !sliceEq(bh, boundaryHeader) {
		issues = append(issues, issue("spec.md", 0, "V19", "影响边界表必须使用固定六列表头"))
	} else if len(br) == 0 {
		issues = append(issues, issue("spec.md", 0, "V19", "影响边界表至少需要一个模块"))
	} else {
		for _, row := range br {
			var missing []string
			for i, h := range boundaryHeader {
				if i >= len(row.cols) || strings.TrimSpace(row.cols[i]) == "" {
					missing = append(missing, h)
				}
			}
			if containsStr(missing, "主要风险") {
				issues = append(issues, issue("spec.md", row.line, "V19", "影响边界模块的主要风险为空"))
				missing = removeStr(missing, "主要风险")
			}
			if len(missing) > 0 {
				issues = append(issues, issue("spec.md", row.line, "V19", fmt.Sprintf("影响边界行存在空字段：%s", strings.Join(missing, "、"))))
			}
		}
	}

	// 判断依据
	jh, jr := sectionTable(lines, "判断依据")
	if !sliceEq(jh, judgmentHeader) {
		issues = append(issues, issue("spec.md", 0, "V19", "判断依据表必须使用固定五列表头"))
	} else if len(jr) == 0 {
		issues = append(issues, issue("spec.md", 0, "V19", "判断依据表至少需要一个判断"))
	} else {
		ids := map[string]int{}
		for _, row := range jr {
			values := append(append([]string{}, row.cols...), repeatEmpty(len(judgmentHeader)-len(row.cols))...)
			values = values[:5]
			jID, status := values[0], values[4]
			if !judgmentIDRe.MatchString(jID) {
				issues = append(issues, issue("spec.md", row.line, "V19", "判断 J-ID 必须为 J1、J2 等稳定编号"))
			}
			ids[jID]++
			var empty []string
			for i, v := range values {
				if strings.TrimSpace(v) == "" {
					empty = append(empty, judgmentHeader[i])
				}
			}
			if len(empty) > 0 {
				issues = append(issues, issue("spec.md", row.line, "V19", fmt.Sprintf("判断依据行存在空字段：%s", strings.Join(empty, "、"))))
			}
			if status != "已确认" && status != "待确认" {
				label := jID
				if label == "" {
					label = "(未知 J-ID)"
				}
				issues = append(issues, issue("spec.md", row.line, "V19", fmt.Sprintf("判断 %s 状态必须为 已确认 或 待确认", label)))
			} else if status == "待确认" && requireReady {
				issues = append(issues, issue("spec.md", row.line, "V19", fmt.Sprintf("判断 %s 仍为待确认，spec 不可交接 x-req", jID)))
			}
		}
		for jID, count := range ids {
			if jID == "" {
				continue
			}
			if count > 1 {
				issues = append(issues, issue("spec.md", 0, "V19", fmt.Sprintf("判断 J-ID 重复：%s", jID)))
			}
			if count == 1 {
				// Python 用 (?<![A-Za-z0-9_-])J1(?![A-Za-z0-9_-]) 断言计数；
				// RE2 不支持 lookbehind/lookahead，改为提取所有 J-标识符 token 再比较相等，
				// 语义等价（避免 J1 误匹配 J10/J11 等）。
				if countJIDRefs(strings.Join(lines, "\n"), jID) < 2 {
					issues = append(issues, issue("spec.md", 0, "V19", fmt.Sprintf("判断 %s 没有被边界或 Scenario 消费", jID)))
				}
			}
		}
	}

	// 建模覆盖声明
	mh, mr := sectionTable(lines, "建模覆盖声明")
	if !sliceEq(mh, modelHeader) {
		issues = append(issues, issue("spec.md", 0, "V19", "建模覆盖声明必须使用固定两列表头"))
	} else {
		counts := map[string]int{}
		for _, row := range mr {
			if len(row.cols) == 0 {
				continue
			}
			counts[strings.TrimSpace(row.cols[0])]++
		}
		var missing []string
		for _, name := range modelTuple {
			if counts[name] == 0 {
				missing = append(missing, name)
			}
		}
		if len(missing) > 0 {
			issues = append(issues, issue("spec.md", 0, "V19", fmt.Sprintf("建模覆盖声明缺少：%s", strings.Join(missing, "、"))))
		}
		for _, row := range mr {
			if len(row.cols) == 0 {
				continue
			}
			dim := strings.TrimSpace(row.cols[0])
			if _, isModel := contains(modelTuple, dim); isModel && (len(row.cols) < 2 || strings.TrimSpace(row.cols[1]) == "") {
				issues = append(issues, issue("spec.md", row.line, "V19", fmt.Sprintf("建模覆盖「%s」缺少锚点或不适用理由", dim)))
			}
		}
		var dups []string
		for _, name := range modelTuple {
			if counts[name] > 1 {
				dups = append(dups, name)
			}
		}
		if len(dups) > 0 {
			issues = append(issues, issue("spec.md", 0, "V19", fmt.Sprintf("建模覆盖维度重复：%s", strings.Join(dups, "、"))))
		}
	}
	return issues
}

// acceptanceIssues 校验单元、Smoke、E2E 三层验收结构以及 E2E 决策和依据。对齐 _acceptance_issues。
func acceptanceIssues(lines []string) []Issue {
	var issues []Issue
	start, _, ok := sectionRange(lines, "验收清单")
	if !ok {
		return issues
	}
	end := endOfSection(lines, start-1)
	type h3 struct {
		index int
		name  string
	}
	var h3s []h3
	for index := start; index < end; index++ {
		if m := h3Re.FindStringSubmatch(lines[index]); m != nil {
			h3s = append(h3s, h3{index, strings.TrimSpace(m[1])})
		}
	}
	headings := map[string][2]int{}
	for pos, h := range h3s {
		subEnd := end
		if pos+1 < len(h3s) {
			subEnd = h3s[pos+1].index
		}
		headings[h.name] = [2]int{h.index, subEnd}
	}
	for _, name := range []string{"单元测试", "Smoke 测试", "E2E 测试"} {
		if _, ok := headings[name]; !ok {
			issues = append(issues, issue("spec.md", start, "V19", fmt.Sprintf("验收清单缺少 ### %s", name)))
		}
	}
	for _, name := range []string{"单元测试", "Smoke 测试"} {
		rng, ok := headings[name]
		if !ok {
			continue
		}
		hasContent := false
		for _, line := range lines[rng[0]+1 : rng[1]] {
			if strings.TrimSpace(line) != "" {
				hasContent = true
				break
			}
		}
		if !hasContent {
			issues = append(issues, issue("spec.md", rng[0]+1, "V19", fmt.Sprintf("%s验收内容为空", name)))
		}
	}
	if rng, ok := headings["E2E 测试"]; ok {
		body := lines[rng[0]+1 : rng[1]]
		decisionRe := regexp.MustCompile(`^\s*[-*+]?\s*决策\s*[：:]\s*(需要|省略)\s*$`)
		evidenceRe2 := regexp.MustCompile(`^\s*[-*+]?\s*依据\s*[：:]\s*(.+?)\s*$`)
		decisionFound := false
		evidenceFound := false
		for _, line := range body {
			if !decisionFound && decisionRe.MatchString(line) {
				decisionFound = true
			}
			if !evidenceFound {
				if m := evidenceRe2.FindStringSubmatch(line); m != nil {
					evidenceFound = strings.TrimSpace(m[1]) != ""
				}
			}
		}
		if !decisionFound {
			issues = append(issues, issue("spec.md", rng[0]+1, "V19", "E2E 测试必须明确写 决策：需要 或 决策：省略"))
		}
		if !evidenceFound {
			issues = append(issues, issue("spec.md", rng[0]+1, "V19", "E2E 测试必须填写判定依据"))
		}
	}
	return issues
}

// reviewIssues 校验 ARV 审查记录、Top5/no-corpus/失败路径，并返回成功召回的风险 ID。对齐 _review_issues。
func reviewIssues(lines []string, md map[string]string) ([]Issue, map[string]bool) {
	var issues []Issue
	recalled := map[string]bool{}
	header, rows := sectionTable(lines, "对抗性审查记录")
	if !sliceEq(header, reviewHeader) {
		issues = append(issues, issue("spec.md", 0, "V19", "对抗性审查记录必须使用固定八列表头"))
		return issues, recalled
	}
	status := md["adversarial_review"]
	budget := md["review_budget"]
	var completedRows []tableRow
	for _, row := range rows {
		if len(row.cols) == 0 {
			continue
		}
		if reviewIDRe.MatchString(strings.TrimSpace(row.cols[0])) {
			completedRows = append(completedRows, row)
		}
	}
	if (status == "skipped-standard" || status == "complete") && len(completedRows) == 0 {
		issues = append(issues, issue("spec.md", 0, "V19", "已完成审查缺少 ARV-n 记录行"))
	}

	for _, row := range completedRows {
		values := append(append([]string{}, row.cols...), repeatEmpty(len(reviewHeader)-len(row.cols))...)
		values = values[:len(reviewHeader)]
		empty := false
		for _, v := range values {
			if strings.TrimSpace(v) == "" {
				empty = true
				break
			}
		}
		if empty {
			issues = append(issues, issue("spec.md", row.line, "V19", "ARV-n 记录的八个字段必须全部填写"))
		}
		hasPlaceholder := false
		for _, v := range values {
			if strings.Contains(v, "<") && strings.Contains(v, ">") {
				hasPlaceholder = true
				break
			}
		}
		if hasPlaceholder {
			issues = append(issues, issue("spec.md", row.line, "V19", "ARV-n 记录仍含模板占位符"))
		}
		if values[1] != budget {
			issues = append(issues, issue("spec.md", row.line, "V19", fmt.Sprintf("ARV-n 预算必须与 review_budget=%s 一致", budget)))
		}
		recalledTokens := riskIDRe.FindAllString(values[4], -1)
		cli := values[7]
		cliFields := map[string]string{}
		for _, segment := range strings.Split(cli, ";") {
			if kv := strings.SplitN(segment, "=", 2); len(kv) == 2 {
				cliFields[strings.TrimSpace(kv[0])] = strings.TrimSpace(kv[1])
			}
		}
		noCorpus := strings.Contains(cli, "skipped:no-corpus")
		exitMatch := regexp.MustCompile(`\bexit\s*=\s*(\d+)\b`).FindStringSubmatch(cli)
		exitCode := -1
		exitZero := false
		recallFailed := false
		if exitMatch != nil {
			exitCode, _ = atoi(exitMatch[1])
			exitZero = exitCode == 0
			recallFailed = exitCode != 0
		}
		sourceTokens := splitSemicolon(values[2])
		var assumptionSources []string
		for _, token := range sourceTokens {
			if token == "no-corpus" {
				if !noCorpus {
					issues = append(issues, issue("spec.md", row.line, "V19", "风险来源 no-corpus 只适用于 CLI=skipped:no-corpus"))
				}
				continue
			}
			if token == "无" {
				if !noCorpus && !recallFailed {
					issues = append(issues, issue("spec.md", row.line, "V19", "风险来源 无 只适用于无语料或召回失败路径"))
				}
				continue
			}
			if m := reviewRagSourceRe.FindStringSubmatch(token); m != nil {
				rid := m[1]
				if noCorpus {
					issues = append(issues, issue("spec.md", row.line, "V19", "CLI=skipped:no-corpus 时风险来源不得包含 RAG ID"))
				}
				if !containsStr(recalledTokens, rid) {
					issues = append(issues, issue("spec.md", row.line, "V19", fmt.Sprintf("风险来源引用的 RAG ID 未进入召回 ID 列：%s", rid)))
				}
				continue
			}
			if m := reviewAssumptionSource.FindStringSubmatch(token); m != nil {
				if a := strings.TrimSpace(m[1]); a != "" {
					assumptionSources = append(assumptionSources, a)
					continue
				}
			}
			issues = append(issues, issue("spec.md", row.line, "V19", "风险来源必须由 RAG:AR-NNN、assumption:<非空说明>、无 或 no-corpus 组成"))
		}
		if exitZero {
			for _, r := range recalledTokens {
				recalled[r] = true
			}
			unique := uniqueStrs(recalledTokens)
			if len(recalledTokens) < 1 || len(recalledTokens) > 5 || len(unique) != len(recalledTokens) {
				issues = append(issues, issue("spec.md", row.line, "V19", "Top5 成功召回必须记录一至五个唯一风险 ID"))
			}
			matchesVal := cliFields["matches"]
			if !regexp.MustCompile(`^\d+$`).MatchString(matchesVal) {
				issues = append(issues, issue("spec.md", row.line, "V19", "Top5 成功召回的 CLI matches 必须等于召回 ID 数量"))
			} else if n, _ := atoi(matchesVal); n != len(recalledTokens) {
				issues = append(issues, issue("spec.md", row.line, "V19", "Top5 成功召回的 CLI matches 必须等于召回 ID 数量"))
			}
		} else if !noCorpus && !regexp.MustCompile(`\bexit\s*=\s*\d+\b`).MatchString(cli) {
			issues = append(issues, issue("spec.md", row.line, "V19", "CLI 必须记录 exit=<code> 与 matches，或写 skipped:no-corpus"))
		}
		if noCorpus && values[4] != "无" {
			issues = append(issues, issue("spec.md", row.line, "V19", "CLI=skipped:no-corpus 时召回 ID 必须为 无"))
		}
		if recallFailed {
			if values[4] != "无" {
				issues = append(issues, issue("spec.md", row.line, "V19", "召回失败时召回 ID 必须为 无"))
			}
			if !regexp.MustCompile(`\bmatches\s*=\s*0\b`).MatchString(cli) {
				issues = append(issues, issue("spec.md", row.line, "V19", "召回失败时 CLI 必须记录 matches=0"))
			}
			for _, field := range []string{"error", "message"} {
				if cliFields[field] == "" {
					issues = append(issues, issue("spec.md", row.line, "V19", fmt.Sprintf("召回失败时 CLI 必须记录非空 %s=<值>", field)))
				}
			}
		}
		if status == "complete" {
			if !noCorpus && !exitZero {
				issues = append(issues, issue("spec.md", row.line, "V19", "deep/full 的 complete 状态要求 Top5 召回成功或 CLI=skipped:no-corpus"))
			}
			if noCorpus && len(assumptionSources) == 0 {
				issues = append(issues, issue("spec.md", row.line, "V19", "deep/full 无语料路径必须在风险来源记录 assumption:<短说明>"))
			}
			if budget == "full" && len(assumptionSources) == 0 {
				issues = append(issues, issue("spec.md", row.line, "V19", "full 预算必须记录一个独立 assumption 故障假设"))
			}
		}
		if status == "skipped-standard" && values[6] != "无" {
			issues = append(issues, issue("spec.md", row.line, "V19", "standard 路径必须保持新增 Scenario 为 无"))
		}
	}
	return issues, recalled
}

// scenarioIssues 校验 Scenario 编号、唯一字段、测试层、来源及 RAG 召回交叉引用。对齐 _scenario_issues。
func scenarioIssues(lines []string, md map[string]string, recalled map[string]bool) []Issue {
	var issues []Issue
	start, _, ok := sectionRange(lines, "Scenarios")
	if !ok {
		return issues
	}
	end := endOfSection(lines, start-1)
	for index := start; index < end; index++ {
		if scenarioHeadRe.MatchString(lines[index]) && !scenarioRe.MatchString(lines[index]) {
			issues = append(issues, issue("spec.md", index+1, "V20", "Scenario 标题必须为 `### Scenario SC_01: <可判定行为名称>`"))
		}
	}
	scenarios := parseScenarios(lines)
	if len(scenarios) == 0 {
		return append(issues, issue("spec.md", 0, "V20", "Scenarios 节至少需要一个 Scenario"))
	}

	idCount := map[string]int{}
	nameCount := map[string]int{}
	for _, s := range scenarios {
		idCount[s.ID]++
		nameCount[s.Name]++
	}
	expectedIDs := make([]string, len(scenarios))
	for i := range scenarios {
		expectedIDs[i] = fmt.Sprintf("SC_%02d", i+1)
	}
	actualIDs := make([]string, len(scenarios))
	for i, s := range scenarios {
		actualIDs[i] = s.ID
	}
	if !sliceEq(actualIDs, expectedIDs) {
		issues = append(issues, issue("spec.md", 0, "V20", "Scenario ID 必须从 SC_01 开始按文档顺序连续递增"))
	}

	status := md["adversarial_review"]
	for _, s := range scenarios {
		name := s.Name
		if name == "" {
			name = "(空)"
		}
		if idCount[s.ID] > 1 {
			issues = append(issues, issue("spec.md", s.Line, "V20", fmt.Sprintf("Scenario ID 重复：%s", s.ID)))
		}
		if nameCount[s.Name] > 1 {
			issues = append(issues, issue("spec.md", s.Line, "V20", fmt.Sprintf("Scenario 名重名：%s", name)))
		}
		var missingGWT []string
		for _, key := range []string{"GIVEN", "WHEN", "THEN"} {
			if s.GWT[key] == "" {
				missingGWT = append(missingGWT, key)
			}
		}
		if len(missingGWT) > 0 {
			issues = append(issues, issue("spec.md", s.Line, "V20", fmt.Sprintf("Scenario「%s」缺少非空：%s", name, strings.Join(missingGWT, "、"))))
		}
		var dupGWT []string
		for _, key := range []string{"GIVEN", "WHEN", "THEN"} {
			if s.GWTCounts[key] > 1 {
				dupGWT = append(dupGWT, key)
			}
		}
		if len(dupGWT) > 0 {
			issues = append(issues, issue("spec.md", s.Line, "V20", fmt.Sprintf("Scenario「%s」重复字段：%s", name, strings.Join(dupGWT, "、"))))
		}
		if s.LayerCount != 1 {
			issues = append(issues, issue("spec.md", s.Line, "V20", fmt.Sprintf("Scenario「%s」缺少唯一测试层 unit|smoke|e2e", name)))
		}
		if s.EvidenceCount != 1 || s.Evidence == "" {
			issues = append(issues, issue("spec.md", s.Line, "V20", fmt.Sprintf("Scenario「%s」必须填写唯一依据", name)))
		}
		if s.SourceCount != 1 {
			issues = append(issues, issue("spec.md", s.Line, "V20", fmt.Sprintf("Scenario「%s」必须填写唯一来源", name)))
			continue
		}
		if s.Source == "initial-spec" {
			continue
		}
		m := v3SourceRe.FindStringSubmatch(s.Source)
		if m == nil {
			issues = append(issues, issue("spec.md", s.Line, "V20", fmt.Sprintf("Scenario「%s」来源必须为 initial-spec、adversarial-review (rag:AR-NNN) 或 adversarial-review (assumption:<短说明>)", name)))
			continue
		}
		assumption := namedGroup(v3SourceRe, s.Source, "assumption")
		if assumption != "" && strings.TrimSpace(assumption) == "" {
			issues = append(issues, issue("spec.md", s.Line, "V20", fmt.Sprintf("Scenario「%s」的 assumption 来源说明不能为空", name)))
			continue
		}
		if status == "skipped-standard" {
			issues = append(issues, issue("spec.md", s.Line, "V20", "standard 路径不允许扩张对抗性 Scenario"))
		}
		rid := namedGroup(v3SourceRe, s.Source, "risk_id")
		if rid != "" && !recalled[rid] {
			issues = append(issues, issue("spec.md", s.Line, "V20", fmt.Sprintf("Scenario「%s」引用的风险 ID 未进入 ARV-n 召回记录：%s", name, rid)))
		}
	}
	return issues
}
