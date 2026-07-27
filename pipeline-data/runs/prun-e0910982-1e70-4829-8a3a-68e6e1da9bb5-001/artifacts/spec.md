> spec_version: 3

# config-resolver

## 任务目标

- 在 `configresolver` 包（module 名 `configresolver`，根目录 `.go` 文件声明 `package configresolver`）中实现 `Resolve(schema map[string]Field, sources []Source) (Result, error)`，将按优先级从低到高排列的多个配置来源合并为单一结果，并为最终结果中每个叶子值标注其来源（JSON Pointer 路径 → source 名）。
- 可观察成功结果：
  - 给定 schema 与按优先级排列的 sources，`Resolve` 返回的 `Result.Config` 与 `Result.Provenance` 满足任务文档规定的 10 条合并规则。
  - 三类校验失败（未知字段 / 类型不匹配 / 必填字段被删除）分别返回可被 `errors.Is` 识别的哨兵错误。
  - 相同输入多次调用输出完全一致；调用前后所有输入对象（含 `nil` 的 `Data`）不被修改。
  - 100 字段规模配置连续调用 10,000 次总耗时 < 2 秒；多个 goroutine 共享同一 `sources` 切片并发调用时 `go test -race` 无数据竞争报告。

## 非目标

- 不实现任何配置文件格式（YAML/TOML/JSON/环境变量字符串等）的解析——`Source.Data` 由调用方预先构造为 `map[string]any`，本任务只做内存中的合并与校验。
- 不实现网络、数据库或 UI 相关能力（任务已明确排除）。
- 不实现配置热更新、监听或缓存失效机制——`Resolve` 是无副作用的纯函数，每次调用独立。
- 不扩展 `Field` 之外的校验能力（如正则、枚举、最大最小值），只实现 `Type`/`Required`/`Children` 三个维度。
- 不提供命令行入口或 `main` 包。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|
| `configresolver`（module 根目录，package `configresolver`） | 目标 | 新建 `Source`/`Field`/`Result` 类型、`ErrUnknownField`/`ErrTypeMismatch`/`ErrRequiredRemoved` 三个哨兵错误与 `Resolve` 导出函数 | 相同输入产出相同输出；不修改任何输入（含 `Data` 为 `nil` 的 Source）；不同调用之间无共享可变状态；三个错误可被 `errors.Is` 识别（含被 `fmt.Errorf("%w", ...)` 包裹后） | 用户任务 |
| 调用方（测试代码 / 未来集成方，通过公开 API 构造 `schema` 与 `sources`） | 上游 | 顺序或并发调用 `Resolve`，可能在多个 goroutine 间共享同一个 `sources` 切片 | 调用方持有的 `schema`、`sources` 及其可达的嵌套 map/slice，在调用前后必须保持原值（引用与内容）不变 | 用户任务 |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | `number` 类型的校验覆盖 Go 内建全部整数与浮点 `reflect.Kind`（`Int*`/`Uint*`/`Float32`/`Float64`），不含 `Complex64/128` | LLM 推断 | 任务原文只列举 `int`、`int64`、`float64` 作为示例并以"等"结尾，未穷举；按"整数与浮点类型"字面含义外推到全部整数/浮点 Kind，排除复数 | 已确认 |
| J2 | `array` 类型使用类型断言 `[]any`，非 `[]any` 的具体 slice 类型（如 `[]string`）判定为 `ErrTypeMismatch`，不使用反射兼容任意 slice kind | LLM 推断 | 任务原文表格明确"接受的 Go 值"为 `[]any`，未提及兼容其他 slice 类型 | 已确认 |
| J3 | 字段在某一 source 中"键不存在"与"键存在但值为 `nil`"是两种不同语义：前者表示该层未提供，合并时跳过；后者才触发规则 4 的删除语义 | 外部规范推导 | 规则 4（`nil` 表示删除）与规则 5（必填字段不能被删除/缺失，两者并列）组合的必然含义，否则两条规则无法同时自洽 | 已确认 |
| J4 | 必填字段判定为"被删除"覆盖两条独立触发路径：①字段在某层被显式设为 `nil` 且此后未被更高优先级来源的非 `nil` 值恢复；②字段在全部 sources 中从未出现过 | 外部规范 | 规则 5 原文"不能被删除，也不能在所有来源中缺失"用"也"并列两个条件 | 已确认 |
| J5 | `object` 类型字段若被显式 `nil` 删除且未被更高优先级恢复，其 `Children` 中标记 `Required` 的子字段一并视为缺失，同样返回 `ErrRequiredRemoved` | LLM 推断 | 规则 5 未直接覆盖嵌套场景；父对象不存在时其必填子字段不可能独立存在，按不变量传递性合理外推 | 已确认 |
| J6 | 类型校验对"任一 source 中出现的非 `nil` 值"逐一生效，不论该值最终是否被更高优先级覆盖；只要有一层提供了类型错误的值就返回 `ErrTypeMismatch` | LLM 推断 | 与规则 6（未知字段检测需扫描全部来源，否则无法发现"只在低优先级出现过一次"的未知字段）保持同一扫描范围的一致性外推 | 已确认 |
| J7 | `Provenance` 只记录叶子值的来源：`object` 节点本身不产生条目（其子字段各自产生条目）；`array` 整体视为一个叶子值，在自身路径下记录来源 | 外部规范 | 规则 9 的 JSON 示例只展示 `/server/port`、`/server/host` 两个叶子路径，未展示对象节点自身路径 | 已确认 |
| J8 | 未知字段检测与类型校验的扫描范围一致，覆盖 schema 递归定义的所有层级（含 `Children` 内的子字段路径） | 外部规范直接推导 | 规则 6 原文未限定层级，`Field.Children` 本身即递归定义 | 已确认 |
| J9 | 性能验收（"连续解析 10,000 次总耗时 < 2 秒"）通过普通 `go test` 用例内用 `time.Now()`/`time.Since` 顺序调用并断言总耗时来验证，而非 `go test -bench` 统计学基准；测试固定构造约 100 个叶子字段（含嵌套 object 与 4 层 sources）的夹具 | LLM 推断 | 任务原文措辞是"总耗时小于 2 秒"的硬性阈值，而非每次操作的统计分布要求 | 已确认 |
| J10 | 并发场景下 `schema` 参数与 `sources` 参数同等享有"调用方共享、只读、不可变"约束，即便任务原文只点名了 `sources` 切片 | LLM 推断 | 与不修改任何输入的总原则一致的外推；`schema` 同样可能被多个 goroutine 共享传入 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `Scenario: 标量字段被更高优先级来源覆盖` / `Scenario: 对象字段递归合并保留未被覆盖的子字段` / `Scenario: 数组字段整体替换不逐元素合并` |
| 状态 | 不适用：`Resolve` 为无内部持久状态的纯函数，每次调用独立计算，不存在跨调用状态迁移 |
| 时序 | `sources` 按声明顺序从低优先级到高优先级依次应用覆盖，无异步回调；见 `Scenario: 相同输入多次调用得到完全一致的输出` |
| 资源 | 不适用：任务明确排除网络、数据库、UI 依赖，无文件句柄或外部资源生命周期需要管理 |
| 不变量 | `影响边界与不变量` |
| 故障 | `Scenario: Schema 未声明字段返回 ErrUnknownField` / `Scenario: 字段类型与 Schema 不一致返回 ErrTypeMismatch` / `Scenario: 必填字段被删除且未恢复返回 ErrRequiredRemoved` / `Scenario: 多 goroutine 共享同一 sources 并发调用无数据竞争` |

## 验收清单

### 单元测试

- [ ] 标量覆盖、对象递归合并、数组整体替换三条核心合并语义均有断言
- [ ] 布尔值 `false`、数字 `0` 等零值不被误判为删除信号
- [ ] 未知字段（含嵌套 `Children` 内）在任一来源出现即返回可被 `errors.Is` 识别的 `ErrUnknownField`
- [ ] 类型不匹配（含被覆盖层、含 `number` 的多种 Go 数值类型、含 `array` 的非 `[]any` 类型）均返回可被 `errors.Is` 识别的 `ErrTypeMismatch`
- [ ] 删除语义（显式 `nil`）与必填字段缺失的三种触发路径（删除未恢复、全程缺失、删除后恢复不报错、嵌套必填随父删除）均返回或不返回符合预期的 `ErrRequiredRemoved`
- [ ] 输入 `sources`（含嵌套结构与 `nil` Data）在调用前后保持不变
- [ ] `Provenance` 键使用 RFC 6901 JSON Pointer 转义（`/`→`~1`、`~`→`~0`）
- [ ] 相同输入连续多次调用返回深度相等的结果

### Smoke 测试

- [ ] 一次贯穿 `default → config_file → environment → runtime` 四层、覆盖五种 `Field.Type` 的真实调用链，验证 `Result` 整体结构符合预期
- [ ] 约 100 叶子字段规模配置连续调用 10,000 次，总耗时 < 2 秒
- [ ] 多个 goroutine 共享同一 `sources` 切片并发调用 `Resolve`，`go test -race` 无数据竞争报告

### E2E 测试

- 决策：省略
- 依据：`Resolve` 是不依赖网络、数据库、UI 或其他进程边界的纯内存库函数，不存在真实跨进程/跨服务链路，单元测试与 Smoke 测试已足以覆盖其全部可观察行为

## 测试驱动开发

1. `标量字段被更高优先级来源覆盖` → 先写会失败的 `TestResolve_ScalarOverride`。
2. `布尔与零值不被误判为删除信号` → 先写会失败的 `TestResolve_ZeroValueNotDeletion`。
3. `对象字段递归合并保留未被覆盖的子字段` → 先写会失败的 `TestResolve_ObjectMerge`。
4. `数组字段整体替换不逐元素合并` → 先写会失败的 `TestResolve_ArrayReplace`。
5. `Schema 未声明字段返回 ErrUnknownField`（含嵌套） → 先写会失败的 `TestResolve_UnknownField`。
6. `字段类型与 Schema 不一致返回 ErrTypeMismatch`（含被覆盖层、多数值类型、array 类型） → 先写会失败的 `TestResolve_TypeMismatch`。
7. 删除与必填字段缺失全部路径 → 先写会失败的 `TestResolve_RequiredRemoved`。
8. `输入 Source.Data 与其嵌套结构在 Resolve 后保持不变` → 先写会失败的 `TestResolve_InputImmutable`。
9. `Provenance 使用 JSON Pointer 转义特殊字符字段名` → 先写会失败的 `TestResolve_ProvenanceEscaping`。
10. `相同输入多次调用得到完全一致的输出` → 先写会失败的 `TestResolve_Deterministic`。
11. 实现满足以上测试的最小代码，重构后复跑全部单元测试。
12. `大型配置连续解析满足性能阈值` 与 `多 goroutine 共享同一 sources 并发调用无数据竞争` → 最后补齐 `TestResolve_PerformanceAndRace`（`go test -race` 运行）。

## Scenarios

### Scenario: 标量字段被更高优先级来源覆盖

- **GIVEN** schema 定义 `string` 字段 `name`；`sources = [default:{name:"a"}, runtime:{name:"b"}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Config["name"] == "b"`，`Provenance["/name"] == "runtime"`，无错误
- 测试层：unit
- 依据：用户任务（合并规则 1）

### Scenario: 布尔与零值不被误判为删除信号

- **GIVEN** schema 定义 `boolean` 字段 `enabled` 与 `number` 字段 `retries`；`sources = [default:{enabled:true, retries:5}, runtime:{enabled:false, retries:0}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Config["enabled"] == false`，`Config["retries"] == 0`，`Provenance` 中两者均指向 `runtime`，无错误（`false`/`0` 是正常覆盖值，不是删除信号）
- 测试层：unit
- 依据：合并规则 4（对照组，防止将零值误判为 `nil`）

### Scenario: 对象字段递归合并保留未被覆盖的子字段

- **GIVEN** schema 定义 `object` 字段 `server`（`Children` 含 `host: string`、`port: number`）；`sources = [default:{server:{host:"a",port:1}}, runtime:{server:{port:2}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Config["server"] == {"host":"a","port":2}`；`Provenance["/server/host"] == "default"`，`Provenance["/server/port"] == "runtime"`，且 `Provenance` 不含 `"/server"` 键（对象节点自身不产生 Provenance 条目，只有叶子值产生）
- 测试层：unit
- 依据：用户任务（合并规则 2）；`J7`

### Scenario: 数组字段整体替换不逐元素合并

- **GIVEN** schema 定义 `array` 字段 `tags`；`sources = [default:{tags: []any{"a","b"}}, runtime:{tags: []any{"c"}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Config["tags"]` 深度等于 `[]any{"c"}`（而非 `["c","b"]` 之类的逐元素合并），`Provenance["/tags"] == "runtime"`
- 测试层：unit
- 依据：用户任务（合并规则 3）

### Scenario: 显式 nil 删除非必填字段

- **GIVEN** schema 定义非必填 `string` 字段 `nickname`；`sources = [default:{nickname:"x"}, runtime:{nickname:nil}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Config` 不含 `"nickname"` 键，`Provenance` 不含对应路径，无错误
- 测试层：unit
- 依据：用户任务（合并规则 4）；`J3`

### Scenario: 必填字段被删除且未恢复返回 ErrRequiredRemoved

- **GIVEN** schema 定义 `Required=true` 的 `string` 字段 `id`；`sources = [default:{id:"x"}, runtime:{id:nil}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回的 `err` 满足 `errors.Is(err, ErrRequiredRemoved)`
- 测试层：unit
- 依据：用户任务（合并规则 5）；`J4`

### Scenario: 必填字段在所有来源中从未出现返回 ErrRequiredRemoved

- **GIVEN** schema 定义 `Required=true` 的 `number` 字段 `port`；全部 `sources` 均不包含 `"port"` 键
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回的 `err` 满足 `errors.Is(err, ErrRequiredRemoved)`
- 测试层：unit
- 依据：用户任务（合并规则 5）；`J4`

### Scenario: 必填字段被更高优先级恢复不报错

- **GIVEN** schema 定义 `Required=true` 的 `string` 字段 `id`；`sources = [default:{id:"x"}, config_file:{id:nil}, runtime:{id:"y"}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 无错误，`Config["id"] == "y"`，`Provenance["/id"] == "runtime"`
- 测试层：unit
- 依据：`J4`（恢复路径）

### Scenario: 嵌套对象内必填子字段随父对象删除一并判定为缺失

- **GIVEN** schema 定义 `object` 字段 `server`（`Children` 含 `Required=true` 的 `port`）；`sources = [default:{server:{port:1}}, runtime:{server:nil}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回的 `err` 满足 `errors.Is(err, ErrRequiredRemoved)`
- 测试层：unit
- 依据：`J5`

### Scenario: Schema 未声明字段返回 ErrUnknownField

- **GIVEN** schema 只声明 `name`；`sources = [default:{name:"a", extra:"b"}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回的 `err` 满足 `errors.Is(err, ErrUnknownField)`
- 测试层：unit
- 依据：用户任务（合并规则 6）；`J8`

### Scenario: 嵌套子字段未在 Children 中声明返回 ErrUnknownField

- **GIVEN** schema 定义 `object` 字段 `server`（`Children` 只含 `host`）；`sources = [default:{server:{host:"a", port:1}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回的 `err` 满足 `errors.Is(err, ErrUnknownField)`
- 测试层：unit
- 依据：`J8`

### Scenario: 字段类型与 Schema 不一致返回 ErrTypeMismatch

- **GIVEN** schema 定义 `number` 字段 `port`；`sources = [default:{port:"not-a-number"}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回的 `err` 满足 `errors.Is(err, ErrTypeMismatch)`
- 测试层：unit
- 依据：用户任务（合并规则 7）

### Scenario: 被覆盖来源中的类型错误值同样返回 ErrTypeMismatch

- **GIVEN** schema 定义 `number` 字段 `port`；`sources = [default:{port:"bad"}, runtime:{port:9090}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回的 `err` 满足 `errors.Is(err, ErrTypeMismatch)`（即使 `default` 层已被 `runtime` 覆盖）
- 测试层：unit
- 依据：`J6`

### Scenario: number 类型接受多种 Go 整数与浮点具体类型

- **GIVEN** schema 定义 `number` 字段 `a`、`b`、`c`；`sources` 分别提供 `int`、`int64`、`float64` 具体类型的值
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 三者均通过校验，无错误，`Config` 中保留各自原始值
- 测试层：unit
- 依据：`J1`

### Scenario: array 字段提供非 []any 具体类型判定为类型不匹配

- **GIVEN** schema 定义 `array` 字段 `tags`；`sources = [default:{tags: []string{"a"}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回的 `err` 满足 `errors.Is(err, ErrTypeMismatch)`
- 测试层：unit
- 依据：`J2`

### Scenario: 输入 Source.Data 与其嵌套结构在 Resolve 后保持不变

- **GIVEN** `sources` 含多层嵌套 `object`/`array` 数据，且其中一个 `Source.Data` 为 `nil`
- **WHEN** 调用 `Resolve(schema, sources)` 后，深度比较调用前后的 `sources`
- **THEN** 调用前后完全一致（无字段被增删改），`Data` 为 `nil` 的 `Source` 其 `Data` 仍为 `nil`
- 测试层：unit
- 依据：用户任务（合并规则 8）

### Scenario: Provenance 使用 JSON Pointer 转义特殊字符字段名

- **GIVEN** schema 定义字段名包含 `/` 和 `~` 的字段（如 `a/b`、`a~b`）
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Provenance` 键使用转义后路径（分别为 `/a~1b`、`/a~0b`）
- 测试层：unit
- 依据：用户任务（合并规则 9）；`J7`

### Scenario: 相同输入多次调用得到完全一致的输出

- **GIVEN** 固定的 schema 与 `sources`
- **WHEN** 连续多次调用 `Resolve(schema, sources)`
- **THEN** 各次返回的 `Result`（`Config` 与 `Provenance`）深度相等
- 测试层：unit
- 依据：用户任务（合并规则 10）

### Scenario: 大型配置连续解析满足性能阈值

- **GIVEN** 约 100 个叶子字段（含嵌套 `object`）的 schema 与 `default/config_file/environment/runtime` 四层 `sources`
- **WHEN** 顺序调用 `Resolve` 10,000 次
- **THEN** 总耗时 < 2 秒
- 测试层：smoke
- 依据：用户任务（性能要求）；`J9`

### Scenario: 多 goroutine 共享同一 sources 并发调用无数据竞争

- **GIVEN** 固定 schema 与同一个 `sources` 切片被多个 goroutine 共享持有
- **WHEN** 多个 goroutine 并发调用 `Resolve(schema, sources)`（在 `go test -race` 下运行）
- **THEN** 无数据竞争报告，且每个 goroutine 各自获得正确、彼此一致的结果
- 测试层：smoke
- 依据：用户任务（性能要求：并发部分）；`J10`

### Scenario: 最小真实调用链验证整体可用性

- **GIVEN** 一份贯穿 `default/config_file/environment/runtime` 四层、覆盖 `string`/`number`/`boolean`/`object`/`array` 五种类型的真实示例配置
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回的 `Config` 与 `Provenance` 整体结构符合预期，无错误
- 测试层：smoke
- 依据：用户任务（交付要求）
