# configresolver · 开发清单

> spec: docs/spec/configresolver
> risk: Q3

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | 创建 `go.mod`（module 名 `configresolver`）和包声明文件，定义所有导出类型 `Source`、`Field`、`Result` 和哨兵错误变量 `ErrUnknownField`、`ErrTypeMismatch`、`ErrRequiredRemoved`；定义 `Resolve` 函数签名为空实现（直接 `return Result{}, nil`） | SC_01, SC_02, SC_03, SC_04, SC_05, SC_06, SC_07, SC_08, SC_09, SC_10, SC_11, SC_12, SC_13, SC_14, SC_15, SC_16, SC_17, SC_18, SC_19, SC_20 | 公开契约；类型/名称/签名必须与任务 API 完全一致 | `go.mod`、`configresolver.go` | None | [ ] ⏳ | None |
| T2 | 编写合并语义单元测试：标量覆盖、object 递归深合并、array 整体替换、nil 删除、nil 删除后恢复（覆盖 SC_01–SC_05 的全部 THEN 断言） | SC_01, SC_02, SC_03, SC_04, SC_05 | 合并语义不变量 `J1`、`J2`、`J3` | `resolve_test.go` | T1 | [ ] ⏳ | None |
| T3 | 实现 `Resolve` 核心合并逻辑：按 schema 字段遍历，逐 source 从低到高合并；object 按 `Children` 递归，array 整体替换，标量直接覆盖，nil 删除当前值；不写入输入对象（构造新 map/slice） | SC_01, SC_02, SC_03, SC_04, SC_05 | 不可变性不变量 `J10`；深合并递归 + nil 误删风险 | `configresolver.go` | T2 | [ ] ⏳ | None |
| T4 | 编写错误路径单元测试：必填被 nil 删除（SC_06）、必填全来源缺失（SC_07）、顶层未知字段（SC_08）、嵌套未知子字段（SC_09）、标量类型不匹配（SC_10）、object 类型不匹配（SC_11）；每条用 `errors.Is` 断言对应哨兵 | SC_06, SC_07, SC_08, SC_09, SC_10, SC_11 | 三条错误路径必须可被 `errors.Is` 精确识别 | `resolve_test.go` | T3 | [ ] ⏳ | None |
| T5 | 实现错误路径：未知字段检测（逐层对比 schema keys）、类型校验（`reflect` kind 匹配五类 Type）、必填检查（合并完成后扫描 `Required` 字段是否缺失）；所有错误用 `fmt.Errorf("%w", sentinel)` 包装 | SC_06, SC_07, SC_08, SC_09, SC_10, SC_11 | 错误识别不变量；哨兵包装 | `configresolver.go` | T4 | [ ] ⏳ | None |
| T6 | 编写类型语义单元测试：number 接受 int/int64/float64（SC_12）、array 元素不校验含混合类型和 nil（SC_13）；确认 `reflect` kind 判断逻辑边界 | SC_12, SC_13 | `J6`、`J7` 类型接受边界 | `resolve_test.go` | T5 | [ ] ⏳ | None |
| T7 | 实现/补全 number 类型校验：用 `reflect.Value.Kind()` 判断是否属于整数或浮点 kind 集合（`Int`/`Uint`/`Float` 系列）；array 不校验元素 | SC_12, SC_13 | 类型不匹配误报风险 | `configresolver.go` | T6 | [ ] ⏳ | None |
| T8 | 编写 provenance 单元测试：嵌套 object 的 JSON Pointer 路径（SC_14）、含 `~` 和 `/` 字符的转义（SC_15）；同时验证 Config 键使用原始字段名不转义 | SC_14, SC_15 | `J8`、`J9` provenance 路径与转义规则 | `resolve_test.go` | T7 | [ ] ⏳ | None |
| T9 | 实现 provenance 追踪：合并过程中记录每个叶子值来源 source.Name，键为 RFC 6901 JSON Pointer 路径（`~`→`~0`、`/`→`~1` 转义）；object 非叶子不记录 | SC_14, SC_15 | provenance 键构建与转义正确性 | `configresolver.go` | T8 | [ ] ⏳ | None |
| T10 | 编写不变量与质量单元测试：输入数据深拷贝快照对比（SC_16）、Data 为 nil 来源保持 nil（SC_17）、100 goroutine 并发调用（SC_18）、相同输入两次调用结果一致（SC_19）；并发测试用 `sync.WaitGroup` + `-race` 检测 | SC_16, SC_17, SC_18, SC_19 | 不可变性 `J10`；并发安全 `J13`；确定性 | `resolve_test.go` | T9 | [ ] ⏳ | None |
| T11 | 审计并修复不可变性：确认 `Resolve` 内所有 map/slice 操作只创建新对象，绝不写入 `sources[i].Data`、`schema` 或其嵌套引用；确认 nil Data 来源不被初始化为空 map | SC_16, SC_17, SC_18, SC_19 | 不可变性不变量 `J10`；并发 data race 触发条件 | `configresolver.go` | T10 | [ ] ⏳ | None |
| T12 | 编写性能 smoke 测试：构建约 100 字段 schema + 4 个来源，循环调用 `Resolve` 10,000 次并断言总耗时 < 2 秒 | SC_20 | `J12` 性能阈值 | `bench_test.go` | T11 | [ ] ⏳ | None |
| T13 | 全量验证：运行 `go test -race ./...`、`go test ./...`、`go vet ./...`，确认全部通过；检查 TestMain 无残留调试代码 | None | None | `.` | T12 | [ ] ⏳ | None |
