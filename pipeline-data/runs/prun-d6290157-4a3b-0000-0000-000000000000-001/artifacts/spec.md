> spec_version: 3

# configresolver

## 任务目标

- 使用 Go 标准库实现多来源配置解析器，将按优先级排列的多个 `Source` 合并为最终 `Result`。
- `Resolve(schema, sources)` 返回合并后的 `Config` 和以 JSON Pointer 路径为键的 `Provenance`，或返回可被 `errors.Is` 识别的哨兵错误。
- `go test ./...`、`go vet ./...` 和 `go test -race ./...` 全部通过。

## 非目标

- 不实现配置文件解析、环境变量读取或网络/数据库/UI 集成。
- 不实现 schema 自校验（调用方负责传入合法 schema）。
- 不支持 array 元素级别的合并或类型校验。
- 不做 Schema 版本管理或配置热更新。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `Resolve` | 目标 | 新建导出函数；接收 `schema` + `sources`，执行 schema 驱动的逐层合并、校验与 provenance 追踪，返回 `Result` 或哨兵错误 | 深合并递归未正确处理 nil 删除 → 必填字段被误删 → 调用方拿到 nil/缺失值 panic 或逻辑错误 | ① 相同输入产生完全一致的输出 ② 任何输入对象（`schema`、`sources`、`Source.Data`、`Field.Children`）在调用前后内容不变 | 用户任务 |
| `Source` / `Field` / `Result` | 目标 | 新建导出类型，构成 `Resolve` 的输入输出契约 | 类型定义与任务 API 不一致 → 编译失败或语义偏差 → 无法通过评测 | 名称、字段、类型与任务 API 表完全一致 | 用户任务 |
| 哨兵错误变量 | 目标 | 新建 `ErrUnknownField` / `ErrTypeMismatch` / `ErrRequiredRemoved`，所有错误路径通过 `errors.Is` 可识别 | 错误未包装哨兵 → `errors.Is` 返回 false → 调用方无法精确处理错误 | 三种错误路径分别可被对应哨兵 `errors.Is` 识别 | 用户任务 |
| 调用方 | 上游 | 构造 `schema` 与 `sources` 切片；可能多 goroutine 共享同一 `sources` 并发调用 | 并发调用时实现意外写入共享输入 → data race → 输出不一致或 panic | 调用前后 `sources` 和 `schema` 的所有内容不变；并发调用互不干扰 | 用户任务 |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | object 类型无条件递归合并；合并以 schema `Children` 为驱动，`Children` 中没有的子键报 `ErrUnknownField` | 用户任务 | 任务规则 2 + 规则 6 | 已确认 |
| J2 | array 类型整体替换，不做按元素合并；最终值来自最后提供该字段且值非 nil 的 source | 用户任务 | 任务规则 3 | 已确认 |
| J3 | `nil` 表示显式删除字段，与"字段不存在"语义不同：字段不存在时该 source 对该字段无影响，`nil` 时删除已有值 | 用户任务 | 任务规则 4 | 已确认 |
| J4 | 必填字段被 nil 删除或在所有来源中缺失，均返回可被 `errors.Is(err, ErrRequiredRemoved)` 识别的错误 | 用户任务 | 任务规则 5 | 已确认 |
| J5 | `Field.Type` 固定五值；source 值的 Go 类型与 `Type` 不一致时报 `ErrTypeMismatch` | 用户任务 | 任务 API 表 + 规则 7 | 已确认 |
| J6 | `number` 类型接受 `int`、`int8`、`int16`、`int32`、`int64`、`uint` 系列、`float32`、`float64` 等所有数值 kinds | 用户任务 | 任务 API 表："任意整数与浮点类型" | 已确认 |
| J7 | array 元素不做任何类型校验；`[]any` 即通过 | 用户任务 | 任务 API 表："元素不做类型校验" | 已确认 |
| J8 | Provenance 只记录最终叶子值的来源；叶子值 = 标量（string/number/boolean）和 array；object 不作为叶子，其每个子字段分别记录 | 用户任务 + LLM 推断 | 任务规则 9 示例只含标量路径；array 整体替换后无子级可展开，视为叶子 | 已确认 |
| J9 | Provenance 键使用 RFC 6901 JSON Pointer 路径，转义仅发生在 Provenance 键中：`~` → `~0`，`/` → `~1`；`Result.Config` 的键使用原始字段名不做转义 | 用户任务 | 任务规则 9 | 已确认 |
| J10 | 输入数据不得被修改，包括 `Data` 为 `nil` 的来源——`nil` 必须保持 `nil`（不能初始化为空 map） | 用户任务 | 任务规则 8 | 已确认 |
| J11 | `Field.Type` 为 `object` 但 `Children` 为空（nil 或长度 0）时，子字段不校验，但仍递归合并 | LLM 推断 | `Children` 为可选字段，空 Children 允许自由结构是合理默认；不影响递归合并语义 | 待确认 |
| J12 | 性能阈值：约 100 字段的配置连续解析 10,000 次总耗时 < 2 秒 | 用户任务 | 任务性能要求 | 已确认 |
| J13 | 多 goroutine 共享同一 `sources` 切片并发调用 `Resolve` 时不得出现数据竞争 | 用户任务 | 任务性能要求："不得出现数据竞争" | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | 影响边界 `Resolve` 行；`SC_01`–`SC_05` 覆盖合并数据流，`SC_14`–`SC_15` 覆盖 provenance 数据流 |
| 状态 | 不适用：`Resolve` 为纯函数，不维护跨调用状态，每次调用独立 |
| 时序 | `SC_01`（sources 从低到高覆盖）、`SC_04`（nil 删除）、`SC_05`（删除后恢复）覆盖来源处理顺序依赖 |
| 资源 | 不适用：仅内存分配（map/slice），无外部资源（网络/DB/文件句柄），无资源泄漏风险 |
| 不变量 | 影响边界与不变量表：输入不可变性、确定性、并发安全 |
| 故障 | `SC_06`–`SC_07`（必填字段）、`SC_08`–`SC_09`（未知字段）、`SC_10`–`SC_11`（类型不匹配）覆盖三种错误路径 |

## 验收清单

### 单元测试

- [ ] 标量字段高优先级来源覆盖低优先级来源（`SC_01`）
- [ ] object 类型递归深合并，子字段分别覆盖（`SC_02`）
- [ ] array 类型整体替换，不按元素合并（`SC_03`）
- [ ] nil 删除标量字段，结果不含该字段（`SC_04`）
- [ ] nil 删除后高优先级来源重新提供则字段恢复（`SC_05`）
- [ ] 必填字段被 nil 删除返回 `ErrRequiredRemoved`（`SC_06`）
- [ ] 必填字段在所有来源缺失返回 `ErrRequiredRemoved`（`SC_07`）
- [ ] 顶层未知字段返回 `ErrUnknownField`（`SC_08`）
- [ ] 嵌套 object 中未知子字段返回 `ErrUnknownField`（`SC_09`）
- [ ] 标量类型不匹配返回 `ErrTypeMismatch`（`SC_10`）
- [ ] object 类型不匹配返回 `ErrTypeMismatch`（`SC_11`）
- [ ] number 类型接受 int/int64/float64 等多种数值类型（`SC_12`）
- [ ] array 元素不做类型校验（`SC_13`）
- [ ] Provenance 使用 JSON Pointer 路径记录叶子值来源（`SC_14`）
- [ ] Provenance 键正确转义 `~` 和 `/` 字符（`SC_15`）
- [ ] 调用后输入 map/slice 内容不被修改（`SC_16`）
- [ ] `Data` 为 nil 的来源调用后仍为 nil（`SC_17`）
- [ ] 多 goroutine 并发调用无数据竞争（`SC_18`，`go test -race`）
- [ ] 相同输入两次调用得到值完全一致的 Result（`SC_19`）

### Smoke 测试

- [ ] 约 100 字段的配置连续解析 10,000 次总耗时 < 2 秒（`SC_20`，benchmark 或计时循环）

### E2E 测试

- 决策：省略
- 依据：本任务是纯内存库函数，无跨进程、跨服务、真实基础设施或用户链路；全部行为可由 unit + smoke 覆盖

## 测试驱动开发

1. `SC_01`–`SC_05` → 先写会失败的合并语义测试（标量覆盖、object 深合并、array 替换、nil 删除与恢复）。
2. `SC_06`–`SC_11` → 先写会失败的错误路径测试（必删、未知字段、类型不匹配）。
3. `SC_12`–`SC_15` → 先写会失败的类型语义与 provenance 测试。
4. `SC_16`–`SC_19` → 先写会失败的不可变性、并发安全与确定性测试。
5. `SC_20` → 实现功能后补写性能基准，确认 < 2 秒。
6. 实现满足测试的最小代码，重构后复跑全部测试层含 `-race`。

## Scenarios

### Scenario SC_01: 标量字段高优先级覆盖

- **GIVEN** schema `{ "port": { Type: "number", Required: false } }`，sources `[{ Name: "default", Data: { "port": 8080 } }, { Name: "env", Data: { "port": 9090 } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Config["port"]` 等于 `9090`，`Result.Provenance["/port"]` 等于 `"env"`，error 为 nil
- 测试层：unit
- 依据：用户任务

### Scenario SC_02: object 类型递归合并

- **GIVEN** schema `{ "server": { Type: "object", Children: { "host": { Type: "string" }, "port": { Type: "number" } } } }`，sources `[{ Name: "file", Data: { "server": { "host": "0.0.0.0", "port": 8080 } } }, { Name: "env", Data: { "server": { "port": 9090 } } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Config["server"]` 等于 `{ "host": "0.0.0.0", "port": 9090 }`（host 保留自 file，port 被覆盖为 9090），`Provenance["/server/host"]` 等于 `"file"`，`Provenance["/server/port"]` 等于 `"env"`
- 测试层：unit
- 依据：用户任务，`J1`

### Scenario SC_03: array 类型整体替换

- **GIVEN** schema `{ "tags": { Type: "array" } }`，sources `[{ Name: "file", Data: { "tags": []any{ "a", "b" } } }, { Name: "env", Data: { "tags": []any{ "x" } } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Config["tags"]` 等于 `[]any{ "x" }`（整体替换非按元素合并），`Provenance["/tags"]` 等于 `"env"`
- 测试层：unit
- 依据：用户任务，`J2`

### Scenario SC_04: nil 删除标量字段

- **GIVEN** schema `{ "debug": { Type: "boolean", Required: false } }`，sources `[{ Name: "file", Data: { "debug": true } }, { Name: "runtime", Data: { "debug": nil } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Config` 不含键 `"debug"`，`Result.Provenance` 不含键 `"/debug"`，error 为 nil
- 测试层：unit
- 依据：用户任务，`J3`

### Scenario SC_05: nil 删除后高优先级来源重新提供则恢复

- **GIVEN** schema `{ "port": { Type: "number" } }`，sources `[{ Name: "s1", Data: { "port": 8080 } }, { Name: "s2", Data: { "port": nil } }, { Name: "s3", Data: { "port": 9090 } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Config["port"]` 等于 `9090`，`Provenance["/port"]` 等于 `"s3"`
- 测试层：unit
- 依据：用户任务，`J3`

### Scenario SC_06: 必填字段被 nil 删除返回 ErrRequiredRemoved

- **GIVEN** schema `{ "port": { Type: "number", Required: true } }`，sources `[{ Name: "file", Data: { "port": 8080 } }, { Name: "runtime", Data: { "port": nil } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** error 不为 nil 且 `errors.Is(err, ErrRequiredRemoved)` 为 true
- 测试层：unit
- 依据：用户任务，`J4`

### Scenario SC_07: 必填字段在所有来源缺失返回 ErrRequiredRemoved

- **GIVEN** schema `{ "port": { Type: "number", Required: true }, "host": { Type: "string" } }`，sources `[{ Name: "file", Data: { "host": "localhost" } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** error 不为 nil 且 `errors.Is(err, ErrRequiredRemoved)` 为 true
- 测试层：unit
- 依据：用户任务，`J4`

### Scenario SC_08: 顶层未知字段返回 ErrUnknownField

- **GIVEN** schema `{ "port": { Type: "number" } }`，sources `[{ Name: "file", Data: { "port": 8080, "unknown_key": 123 } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** error 不为 nil 且 `errors.Is(err, ErrUnknownField)` 为 true
- 测试层：unit
- 依据：用户任务

### Scenario SC_09: 嵌套 object 中未知子字段返回 ErrUnknownField

- **GIVEN** schema `{ "server": { Type: "object", Children: { "host": { Type: "string" } } } }`，sources `[{ Name: "file", Data: { "server": { "host": "0.0.0.0", "bogus": true } } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** error 不为 nil 且 `errors.Is(err, ErrUnknownField)` 为 true
- 测试层：unit
- 依据：用户任务，`J1`

### Scenario SC_10: 标量类型不匹配返回 ErrTypeMismatch

- **GIVEN** schema `{ "port": { Type: "number" } }`，sources `[{ Name: "file", Data: { "port": "8080" } }]`（port 是 string 而非 number）
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** error 不为 nil 且 `errors.Is(err, ErrTypeMismatch)` 为 true
- 测试层：unit
- 依据：用户任务，`J5`

### Scenario SC_11: object 类型不匹配返回 ErrTypeMismatch

- **GIVEN** schema `{ "server": { Type: "object", Children: { "host": { Type: "string" } } } }`，sources `[{ Name: "file", Data: { "server": "not-a-map" } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** error 不为 nil 且 `errors.Is(err, ErrTypeMismatch)` 为 true
- 测试层：unit
- 依据：用户任务，`J5`

### Scenario SC_12: number 类型接受多种数值类型

- **GIVEN** schema `{ "a": { Type: "number" }, "b": { Type: "number" }, "c": { Type: "number" } }`，sources `[{ Name: "s", Data: { "a": int(42), "b": int64(99), "c": float64(3.14) } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** error 为 nil，`Config["a"]` 等于 `42`，`Config["b"]` 等于 `int64(99)`，`Config["c"]` 等于 `3.14`
- 测试层：unit
- 依据：用户任务，`J6`

### Scenario SC_13: array 元素不做类型校验

- **GIVEN** schema `{ "tags": { Type: "array" } }`，sources `[{ Name: "s", Data: { "tags": []any{ 1, "two", true, nil } } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** error 为 nil，`Config["tags"]` 等于 `[]any{ 1, "two", true, nil }`
- 测试层：unit
- 依据：用户任务，`J7`

### Scenario SC_14: Provenance 使用 JSON Pointer 路径记录来源

- **GIVEN** schema `{ "server": { Type: "object", Children: { "host": { Type: "string" }, "port": { Type: "number" } } } }`，sources `[{ Name: "config_file", Data: { "server": { "host": "0.0.0.0", "port": 8080 } } }, { Name: "environment", Data: { "server": { "port": 9090 } } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Provenance` 包含 `"/server/host": "config_file"` 和 `"/server/port": "environment"`，不包含 `"/server"` 键（object 非叶子）
- 测试层：unit
- 依据：用户任务，`J8`，`J9`

### Scenario SC_15: Provenance 键正确转义波浪号和斜杠

- **GIVEN** schema `{ "a/b": { Type: "string" }, "c~d": { Type: "number" } }`，sources `[{ Name: "s", Data: { "a/b": "hello", "c~d": 42 } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Provenance` 包含键 `"/a~1b": "s"` 和 `"/c~0d": "s"`（`/` 转义为 `~1`，`~` 转义为 `~0`）；`Config` 的键为原始字段名 `"a/b"` 和 `"c~d"`（不转义）
- 测试层：unit
- 依据：用户任务，`J9`

### Scenario SC_16: 调用后输入数据不被修改

- **GIVEN** schema `{ "server": { Type: "object", Children: { "host": { Type: "string" }, "port": { Type: "number" } } }, "tags": { Type: "array" } }`，sources `[{ Name: "s", Data: { "server": { "host": "0.0.0.0", "port": 8080 }, "tags": []any{ "a" } } }]`，调用前对 `sources[0].Data` 及其嵌套 map/slice 做深拷贝快照
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 调用后 `sources[0].Data` 及其所有嵌套 map/slice 的内容与快照完全一致（无任何修改）
- 测试层：unit
- 依据：用户任务，`J10`

### Scenario SC_17: Data 为 nil 的来源调用后仍为 nil

- **GIVEN** schema `{ "port": { Type: "number" } }`，sources `[{ Name: "empty", Data: nil }, { Name: "s", Data: { "port": 8080 } }]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** error 为 nil，`Config["port"]` 等于 `8080`，且调用后 `sources[0].Data` 仍为 `nil`（未被初始化为空 map）
- 测试层：unit
- 依据：用户任务，`J10`

### Scenario SC_18: 多 goroutine 并发调用无数据竞争

- **GIVEN** schema 定义约 10 个字段（含嵌套 object 和 array），sources 含 3 个来源；准备完成后不再修改
- **WHEN** 启动 100 个 goroutine 共享同一 `sources` 切片并发调用 `Resolve(schema, sources)`，等待全部完成
- **THEN** 所有调用返回 nil error 且 Config 值完全一致；`go test -race ./...` 不报告任何 data race
- 测试层：unit
- 依据：用户任务，`J13`

### Scenario SC_19: 相同输入产生完全一致的输出

- **GIVEN** schema 定义含嵌套 object、array、标量的约 20 字段配置，sources 含 4 个来源
- **WHEN** 使用相同 `schema` 和 `sources` 连续调用 `Resolve` 两次
- **THEN** 两次返回的 `Result.Config` 和 `Result.Provenance` 的所有键值对完全一致
- 测试层：unit
- 依据：用户任务

### Scenario SC_20: 性能基准——100 字段 × 10,000 次解析 < 2 秒

- **GIVEN** schema 定义约 100 个字段（含 2 层嵌套 object 和若干 array），sources 含 4 个来源
- **WHEN** 连续调用 `Resolve` 10,000 次
- **THEN** 总耗时 < 2 秒（可通过 benchmark 或计时断言验证）
- 测试层：smoke
- 依据：用户任务，`J12`
