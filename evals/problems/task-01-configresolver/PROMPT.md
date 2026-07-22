# 实现多来源配置解析器

<!-- 草案状态：待评测负责人确认后替换 PROMPT.md 生效为 task-01@v2；
     v2 相对 v1 的全部变更见文末"v2 契约冻结说明"。 -->

使用 Go 标准库实现一个多来源配置解析器，将多个配置来源合并成最终配置，并输出每个字段的来源。实现不得依赖网络、数据库或 UI。

## 交付物结构（必须严格遵守）

- Go module 名必须为 `configresolver`（`go.mod` 首行 `module configresolver`）。
- 包 `configresolver` 位于 module 根目录（根目录下的 `.go` 文件声明 `package configresolver`）。
- 下方 API 中的类型、函数与错误变量必须以完全一致的名称从该包导出。

## API

```go
type Source struct {
    Name string
    Data map[string]any
}

type Field struct {
    Type     string
    Required bool
    Children map[string]Field
}

type Result struct {
    Config     map[string]any
    Provenance map[string]string
}

var (
    ErrUnknownField    = errors.New("configresolver: unknown field")
    ErrTypeMismatch    = errors.New("configresolver: type mismatch")
    ErrRequiredRemoved = errors.New("configresolver: required field removed")
)

func Resolve(
    schema map[string]Field,
    sources []Source,
) (Result, error)
```

`Field.Type` 的合法取值固定为以下五个字符串，语义对应 JSON 类型：

| Type 值 | 接受的 Go 值 |
|---|---|
| `string` | `string` |
| `number` | 任意整数与浮点类型（`int`、`int64`、`float64` 等） |
| `boolean` | `bool` |
| `object` | `map[string]any`，子字段由 `Children` 描述 |
| `array` | `[]any`，元素不做类型校验 |

## 合并规则

`sources` 从低优先级到高优先级排列，例如：

```text
default -> config_file -> environment -> runtime
```

实现必须满足：

1. 普通字段由高优先级来源覆盖低优先级来源。
2. 对象类型递归合并。
3. 数组整体替换，不按元素合并。
4. `nil` 表示删除字段。
5. 必填字段不能被删除，也不能在所有来源中缺失；违反时返回的错误必须能被
   `errors.Is(err, ErrRequiredRemoved)` 识别。
6. Schema 中不存在的字段必须报错，错误能被 `errors.Is(err, ErrUnknownField)` 识别。
7. 字段类型与 Schema 不一致时必须报错，错误能被 `errors.Is(err, ErrTypeMismatch)` 识别。
8. 输入数据不得被修改（包括 `Data` 为 `nil` 的来源：`nil` 必须保持 `nil`）。
9. `Result.Config` 的键是原始字段名；`Result.Provenance` 使用 JSON Pointer
   路径（RFC 6901，`/`→`~1`、`~`→`~0` 转义只发生在 Provenance 键中）记录每个
   最终叶子值的来源，例如：

```json
{
  "/server/port": "environment",
  "/server/host": "config_file"
}
```

10. 相同输入必须得到完全一致的输出。

## 性能要求

对包含约 100 个字段的配置连续解析 10,000 次：

- 总耗时小于 2 秒。
- 不得出现数据竞争（包括多个 goroutine 共享同一 `sources` 切片并发调用）。
- 不得修改任何输入对象。

## 交付要求

- 提供完整、可编译的实现和必要测试。
- 确保 `go test ./...` 和 `go vet ./...` 通过。

---
