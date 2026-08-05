package req

import (
	"path/filepath"
	"strings"

	specpkg "github.com/KtKID/x-dev-pipeline/cli/internal/engine/spec"
)

// specOfTaskDir 校验 taskDir 是否落在 docs/spec/<spec-name>/tasks/<task-name>/。
// 命中则返回归属 spec 的相对路径（docs/spec/<spec-name>），否则返回空串。
// 对齐 req.py 的 spec_of_task_dir。
//
// 注意：用 filepath.Abs 解析后再逐级找 docs/spec/.../tasks/ 段，
// 兼容调用方传入相对或绝对路径。
// SpecOfTaskDir 是 specOfTaskDir 的导出包装，供 CLI 判定目录是否是 req-task。
func SpecOfTaskDir(taskDir string) string { return specOfTaskDir(taskDir) }

// ResolveSpecDir 是 resolveSpecDir 的导出包装，供 CLI 获取父 spec 目录。
func ResolveSpecDir(taskDir string) string { return resolveSpecDir(taskDir) }

func specOfTaskDir(taskDir string) string {
	abs, err := filepath.Abs(taskDir)
	if err != nil {
		return ""
	}
	parts := splitPath(abs)
	// 模式：.../docs/spec/<spec-name>/tasks/<task-name>
	// 即存在 i 使 parts[i]=="docs", parts[i+1]=="spec", parts[i+3]=="tasks"。
	for i := 0; i+3 < len(parts)-1; i++ {
		if parts[i] == "docs" && parts[i+1] == "spec" && parts[i+3] == "tasks" {
			return strings.Join([]string{"docs", "spec", parts[i+2]}, "/")
		}
	}
	return ""
}

// resolveSpecDir 返回 task 所属的 spec 包绝对路径。
// 通过检查 task 目录的上两级是否有合法 spec_version: 3 的 spec.md 来判定。
// 结构或版本不匹配返回空串。对齐 req.py 的 resolve_spec_dir + has_spec_marker。
func resolveSpecDir(taskDir string) string {
	abs, err := filepath.Abs(taskDir)
	if err != nil {
		return ""
	}
	// task 目录的上两级 = spec 包目录。
	candidate := filepath.Dir(filepath.Dir(abs))
	if !hasSpecMarker(candidate) {
		return ""
	}
	return candidate
}

// hasSpecMarker 判断目录中的 spec.md 是否含 spec_version: 3 标记。
// 委托给 spec 引擎（与 req.py 一致，复用同一解析逻辑）。
func hasSpecMarker(specDir string) bool {
	return specpkg.HasSpecMarker(specDir)
}

// headerValue 读取 dev-checklist.md 头部 `> spec:` / `> risk:` 行的取值。
// 缺失返回空串。对齐 req.py 的 header_value。
func headerValue(text, key string) string {
	re := riskLineRe
	if key == "spec" {
		re = specLineRe
	}
	for _, line := range splitLines(text) {
		if m := re.FindStringSubmatch(strings.TrimSpace(line)); m != nil {
			return m[1]
		}
	}
	return ""
}

// splitPath 把绝对路径拆成路径段（去空），等价于 Python 的 Path.parts。
func splitPath(abs string) []string {
	abs = filepath.ToSlash(abs)
	// 去掉开头的卷标/根（如 / 或 C:），保留其余段。
	abs = strings.TrimPrefix(abs, "/")
	parts := strings.Split(abs, "/")
	out := parts[:0]
	for _, p := range parts {
		if p != "" {
			out = append(out, p)
		}
	}
	return out
}
