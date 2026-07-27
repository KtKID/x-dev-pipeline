# configresolver · 开发清单

> spec: docs/spec/configresolver
> risk: Q3

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | 定义导出类型 `Source`/`Field`/`Result`、三个错误变量；实现 schema 字段类型校验与未知字段检测（顶层 + 递归 object）。类型校验需覆盖 number 接受所有整数/浮点 Go 类型 | 类型不匹配报错；未知字段报错；嵌套对象未知字段报错；number类型接受多种数值类型 | `J1` number 类型接受多数值；`J6` 校验阶段不可修改输入 | `configresolver.go` `resolve.go` | None | [ ] ⏳ | None |
| T2 | 实现合并引擎核心：scalar 高优先级覆盖、object 按 Children 递归合并、array 整体替换、nil 删除语义（顶层 + 嵌套）。合并全程深拷贝，不触碰输入。先写会失败的测试 | 基本字段覆盖；对象递归合并；数组整体替换；nil删除字段；嵌套对象中nil删除子字段；空schema与空sources | `J2` nil=删除；`J5` 数组整体替换；`J9` object 递归按 Children；`J6` 输入不可变 | `resolve.go` | T1 | [ ] ⏳ | None |
| T3 | 实现必填字段保护：合并完成后遍历 schema，检测 Required 字段是否缺失或被 nil 删除，返回 `ErrRequiredRemoved` 包装错误。需区分顶层与嵌套 object | 必填字段被删除报错；必填字段缺失报错 | `J10` 必填违规两种路径均返回可 `errors.Is` 识别的错误 | `resolve.go` | T2 | [ ] ⏳ | None |
| T4 | 在合并过程中追踪每个叶子值的来源，生成 Provenance。路径用 JSON Pointer（RFC 6901），`/`→`~1`、`~`→`~0` 转义只发生在 Provenance 键。Config 键保持原始字段名。object 容器不单独记录 | Provenance生成JSONPointer路径；JSONPointer转义 | `J3` 只记叶子；`J4` 转义只在 Provenance 键；`J8` 确定性 | `resolve.go` | T2 | [ ] ⏳ | None |
| T5 | 保证输入不可变性：Data 为 nil 的来源保持 nil；任意层级 map/slice 不被原地修改。确保相同输入确定性输出。验证 100 goroutine 共享 sources 并发无数据竞争（`go test -race`） | 输入不可变性；nil来源保持nil；确定性输出；并发安全 | `J6` nil 保持 nil + 深层不可变；`J7` 并发无竞态；`J8` 确定性 | `resolve.go` `resolve_test.go` | T2 T3 T4 | [ ] ⏳ | None |
| T6 | 编写性能基准测试：schema 约 100 字段（含嵌套 object），sources 4 个，连续调用 10,000 次，验证总耗时 < 2 秒 | 性能基准 | 用户任务性能阈值；`J8` 确定性 | `resolve_bench_test.go` | T2 T3 T4 T5 | [ ] ⏳ | None |
