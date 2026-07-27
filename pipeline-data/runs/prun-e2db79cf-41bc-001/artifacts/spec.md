> spec_version: 3

# configresolver

## 任务目标

- 实现 `Resolve(schema, sources)` 函数，将按优先级升序排列的多个配置来源递归合并为单一配置树，并为每个叶子值输出来源标记（JSON Pointer 路径 → Source.Name）。
- 纯 Go 标准库实现，不依赖网络、数据库或 UI。
- `go test ./...` 和 `go vet ./...` 通过。

## 非目标

- 不实现配置文件解析（JSON/YAML/TOML 等）；输入已经是 `map[string]any`。
- 不实现环境变量自动采集或类型转换；来源数据由调用方构造。
- 不实现配置热更新、watch 或回调。
- 不实现配置加密或敏感字段脱敏。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|
| `configresolver` | 目标 | 新建包：导出 `Source`/`Field`/`Result` 类型、`Resolve` 函数、三个错误变量 | ① 输入任何参数不被修改（含 nil 保持 nil）；② 相同输入产出完全一致的 Result；③ 多 goroutine 共享同一 sources 切片并发调用无数据竞争 | 用户任务 / `J6` / `J8` / `J7` |
| 调用方 | 上游 | 通过 `schema map[string]Field` 和 `sources []Source` 传入配置数据 | Field.Type 取值限定五个字符串；sources 按低→高优先级排列 | 用户任务 |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | `number` 类型接受所有整数和浮点 Go 类型（int, int8…int64, uint*, float32, float64） | 用户任务 | task.md "任意整数与浮点类型" | 已确认 |
| J2 | source 中某字段值为 `nil` 语义为"删除该字段"，与"字段不存在于该 source"不同 | 用户任务 | task.md 合并规则第 4 条 | 已确认 |
| J3 | `Provenance` 只记录叶子值来源；非叶子（object 容器本身）不单独记录 | 用户任务 | task.md 第 9 条"每个最终叶子值的来源" | 已确认 |
| J4 | JSON Pointer 转义（`/`→`~1`、`~`→`~0`）只发生在 Provenance 键中，Config 键保持原始字段名 | 用户任务 | task.md 第 9 条末尾括号说明 | 已确认 |
| J5 | 数组整体替换，不做元素级合并；数组元素不做类型校验 | 用户任务 | task.md 合并规则第 3 条 | 已确认 |
| J6 | 输入不可变包括 `Data` 为 `nil` 的来源其 `Data` 保持 `nil`，且任意层级的 map/slice 不被原地修改 | 用户任务 | task.md 第 8 条 | 已确认 |
| J7 | 多 goroutine 共享同一 sources 切片并发调用 Resolve 必须无数据竞争 | 用户任务 | task.md 性能要求 | 已确认 |
| J8 | 合并和 Provenance 生成必须确定性，相同输入完全一致输出 | 用户任务 | task.md 第 10 条 | 已确认 |
| J9 | `object` 类型必须按 schema.Children 递归合并并校验子字段 | 用户任务 | task.md 合并规则第 2 条 + Field.Children | 已确认 |
| J10 | 必填字段违规分两种：被 nil 显式删除、所有来源中均缺失——两种均返回可被 `errors.Is(err, ErrRequiredRemoved)` 识别的错误 | 用户任务 | task.md 第 5 条 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `Scenario: 基本字段覆盖` — sources → merge → Result.Config + Result.Provenance |
| 状态 | 不适用：纯函数，无持久状态，每次调用独立 |
| 时序 | 不适用：纯函数，无时序依赖，sources 按索引顺序处理即可 |
| 资源 | 不适用：无外部资源（文件/网络/锁），内存分配由 GC 管理 |
| 不变量 | `影响边界与不变量` 表 — 输入不可变、确定性、并发安全 |
| 故障 | `Scenario: 必填字段被删除报错` / `Scenario: 未知字段报错` / `Scenario: 类型不匹配报错` |

## 验收清单

### 单元测试

- [ ] 5 种类型（string/number/boolean/object/array）的校验与合并
- [ ] 对象递归合并，包括深层嵌套
- [ ] 数组整体替换
- [ ] nil 删除语义（顶层 + 嵌套）
- [ ] 必填字段删除/缺失 → `errors.Is(err, ErrRequiredRemoved)`
- [ ] 未知字段（顶层 + 嵌套） → `errors.Is(err, ErrUnknownField)`
- [ ] 类型不匹配 → `errors.Is(err, ErrTypeMismatch)`
- [ ] number 类型接受多种 Go 数值类型
- [ ] Provenance 正确生成 JSON Pointer 路径，含 `~` 和 `/` 转义
- [ ] 输入不可变性验证（调用前后输入深层对比）
- [ ] 确定性输出（重复调用对比）
- [ ] 空边界：空 schema + 空 sources

### Smoke 测试

- [ ] 完整 Resolve 调用链：schema 含 string/number/boolean/object/array + 嵌套 object，sources 含 3 个来源（default/config_file/environment），验证 Config 和 Provenance 均符合预期

### E2E 测试

- 决策：省略
- 依据：纯函数库，无跨进程、跨服务或真实基础设施链路

## 测试驱动开发

1. `基本字段覆盖` → 先写会失败的 `TestResolve_ScalarOverride`。
2. `对象递归合并` → 先写会失败的 `TestResolve_ObjectRecursiveMerge`。
3. `数组整体替换` → 先写会失败的 `TestResolve_ArrayReplace`。
4. `nil删除字段` → 先写会失败的 `TestResolve_NilDeletesField`。
5. `必填字段被删除报错` → 先写会失败的 `TestResolve_RequiredFieldDeleted`。
6. `必填字段缺失报错` → 先写会失败的 `TestResolve_RequiredFieldMissing`。
7. `未知字段报错` → 先写会失败的 `TestResolve_UnknownField`。
8. `类型不匹配报错` → 先写会失败的 `TestResolve_TypeMismatch`。
9. `number类型接受多种数值类型` → 先写会失败的 `TestResolve_NumberTypes`。
10. `Provenance生成JSONPointer路径` → 先写会失败的 `TestResolve_ProvenancePath`。
11. `JSONPointer转义` → 先写会失败的 `TestResolve_ProvenanceEscaping`。
12. `输入不可变性` → 先写会失败的 `TestResolve_InputImmutability`。
13. `确定性输出` → 先写会失败的 `TestResolve_Deterministic`。
14. `并发安全` → 先写会失败的 `TestResolve_ConcurrentSafe`。
15. `性能基准` → 先写会失败的 `BenchmarkResolve_100Fields`。
16. 实现满足测试的最小代码，重构后复跑全部已选测试层。

## Scenarios

### Scenario: 基本字段覆盖

- **GIVEN** schema `{name: {Type:"string"}, port: {Type:"number"}, debug: {Type:"boolean"}}`，sources `[{Name:"default", Data:{name:"a", port:80, debug:false}}, {Name:"env", Data:{port:8080, debug:true}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Config == {name:"a", port:8080, debug:true}` 且 `Result.Provenance == {"/name":"default", "/port":"env", "/debug":"env"}`，无错误
- 测试层：unit
- 依据：用户任务 / `J8`

### Scenario: number类型接受多种数值类型

- **GIVEN** schema `{a:{Type:"number"}, b:{Type:"number"}, c:{Type:"number"}, d:{Type:"number"}}`，sources `[{Name:"s1", Data:{a:int(42), b:int64(100), c:float64(3.14), d:uint(7)}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Config` 中 a/b/c/d 值分别等于 42(int)、100(int64)、3.14(float64)、7(uint)，无错误
- 测试层：unit
- 依据：`J1`

### Scenario: 对象递归合并

- **GIVEN** schema `{server:{Type:"object", Children:{host:{Type:"string"}, port:{Type:"number"}}}}`，sources `[{Name:"file", Data:{server:{host:"localhost"}}}, {Name:"env", Data:{server:{port:8080}}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Config == {server:{host:"localhost", port:8080}}` 且 `Result.Provenance == {"/server/host":"file", "/server/port":"env"}`
- 测试层：unit
- 依据：`J9`

### Scenario: 数组整体替换

- **GIVEN** schema `{items:{Type:"array"}}`，sources `[{Name:"s1", Data:{items:[1,2,3]}}, {Name:"s2", Data:{items:[4,5]}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Config == {items:[4,5]}` 且 `Result.Provenance == {"/items":"s2"}`
- 测试层：unit
- 依据：`J5`

### Scenario: nil删除字段

- **GIVEN** schema `{a:{Type:"string"}, b:{Type:"string"}}`，sources `[{Name:"s1", Data:{a:"x", b:"y"}}, {Name:"s2", Data:{b:nil}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Config == {a:"x"}`，Config 中不存在键 `b`，无错误
- 测试层：unit
- 依据：`J2`

### Scenario: 嵌套对象中nil删除子字段

- **GIVEN** schema `{obj:{Type:"object", Children:{x:{Type:"string"}, y:{Type:"string"}}}}`，sources `[{Name:"s1", Data:{obj:{x:"1", y:"2"}}}, {Name:"s2", Data:{obj:{y:nil}}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Config == {obj:{x:"1"}}`，obj 中不存在键 `y`，无错误
- 测试层：unit
- 依据：`J2` / `J9`

### Scenario: 必填字段被删除报错

- **GIVEN** schema `{a:{Type:"string", Required:true}}`，sources `[{Name:"s1", Data:{a:"x"}}, {Name:"s2", Data:{a:nil}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回错误且 `errors.Is(err, ErrRequiredRemoved) == true`
- 测试层：unit
- 依据：`J10`

### Scenario: 必填字段缺失报错

- **GIVEN** schema `{a:{Type:"string", Required:true}}`，sources `[{Name:"s1", Data:{}}]`（所有来源均未提供字段 `a`）
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回错误且 `errors.Is(err, ErrRequiredRemoved) == true`
- 测试层：unit
- 依据：`J10`

### Scenario: 未知字段报错

- **GIVEN** schema `{a:{Type:"string"}}`，sources `[{Name:"s1", Data:{a:"x", unknown:"val"}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回错误且 `errors.Is(err, ErrUnknownField) == true`
- 测试层：unit
- 依据：用户任务第 6 条

### Scenario: 嵌套对象未知字段报错

- **GIVEN** schema `{obj:{Type:"object", Children:{x:{Type:"string"}}}}`，sources `[{Name:"s1", Data:{obj:{x:"1", unknown:"val"}}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回错误且 `errors.Is(err, ErrUnknownField) == true`
- 测试层：unit
- 依据：用户任务第 6 条

### Scenario: 类型不匹配报错

- **GIVEN** schema `{a:{Type:"number"}}`，sources `[{Name:"s1", Data:{a:"not-a-number"}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** 返回错误且 `errors.Is(err, ErrTypeMismatch) == true`
- 测试层：unit
- 依据：用户任务第 7 条

### Scenario: 空schema与空sources

- **GIVEN** schema `{}`，sources `[]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Config == {}` 且 `Result.Provenance == {}`，无错误
- 测试层：unit
- 依据：用户任务

### Scenario: Provenance生成JSONPointer路径

- **GIVEN** schema `{server:{Type:"object", Children:{port:{Type:"number"}}}, debug:{Type:"boolean"}}`，sources `[{Name:"default", Data:{server:{port:80}, debug:false}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Provenance` 包含键 `"/server/port"` 值 `"default"` 和键 `"/debug"` 值 `"default"`；Provenance 中不包含 `"/server"` 本身（object 容器不记录）
- 测试层：unit
- 依据：`J3` / `J4`

### Scenario: JSONPointer转义

- **GIVEN** schema `{"a/b":{Type:"string"}, "c~d":{Type:"string"}}`，sources `[{Name:"s1", Data:{"a/b":"1", "c~d":"2"}}]`
- **WHEN** 调用 `Resolve(schema, sources)`
- **THEN** `Result.Provenance` 包含键 `"/a~1b"` 和 `"/c~0d"`；`Result.Config` 包含原始键 `"a/b"` 和 `"c~d"`（未被转义）
- 测试层：unit
- 依据：`J4`

### Scenario: 输入不可变性

- **GIVEN** schema `{a:{Type:"string"}, obj:{Type:"object", Children:{x:{Type:"string"}}}}`，sources `[{Name:"s1", Data:{a:"x", obj:{x:"1"}}}]`；调用前对 sources 做深快照
- **WHEN** 调用 `Resolve(schema, sources)` 后对比 sources 深快照
- **THEN** sources 的每一层（Data map、嵌套 map、slice）与调用前完全一致，Resolve 未修改任何输入对象
- 测试层：unit
- 依据：`J6`

### Scenario: nil来源保持nil

- **GIVEN** schema `{a:{Type:"string"}}`，sources `[{Name:"s1", Data:nil}]`（Data 字段为 nil）
- **WHEN** 调用 `Resolve(schema, sources)` 后检查 `sources[0].Data`
- **THEN** `sources[0].Data == nil`（未被替换为空 map）
- 测试层：unit
- 依据：`J6`

### Scenario: 确定性输出

- **GIVEN** 相同的 schema（含 object/array 多层嵌套）和 sources
- **WHEN** 连续调用 `Resolve` 两次
- **THEN** 两次返回的 `Result.Config` 和 `Result.Provenance` 分别 `reflect.DeepEqual` 相等
- 测试层：unit
- 依据：`J8`

### Scenario: 并发安全

- **GIVEN** schema 约 20 个字段（含嵌套 object），sources 含 3 个来源
- **WHEN** 启动 100 个 goroutine 共享同一 sources 切片并发调用 `Resolve(schema, sources)`，使用 `go test -race` 运行
- **THEN** 无 panic、无数据竞争报告，所有 goroutine 返回 `reflect.DeepEqual` 相同的 Result
- 测试层：unit
- 依据：`J7`

### Scenario: 性能基准

- **GIVEN** schema 约 100 个字段（含嵌套 object），sources 含 4 个来源
- **WHEN** 连续调用 `Resolve` 10,000 次
- **THEN** 总耗时 < 2 秒
- 测试层：smoke
- 依据：用户任务性能要求
