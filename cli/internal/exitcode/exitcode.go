// Package exitcode 定义 xdev CLI 的统一退出码，与 Python 版保持一致。
//
// 0 成功；1 校验失败或依赖环；2 用法、目标或 IO 错误。
package exitcode

const (
	OK      = 0
	Invalid = 1 // 校验失败、依赖环
	Usage   = 2 // 用法、目标或 IO 错误
)
