> spec: docs/spec/config-resolver
> risk: Q3

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | 建立 module 与导出类型脚手架：`go.mod`（`module configresolver`）、`Source`/`Field`/`Result` 类型、`ErrUnknownField`/`ErrTypeMismatch`/`ErrRequiredRemoved` 三个哨兵错误变量、`Resolve` 函数签名（空实现） | None | 建立公开契约本身，无行为逻辑 | go.mod, resolver.go | None | [ ] ⏳ | None |
| T2 | 实现核心合并算法：标量覆盖、布尔/零值防误判、对象递归合并、数组整体替换 | 标量字段被更高优先级来源覆盖 / 布尔与零值不被误判为删除信号 / 对象字段递归合并保留未被覆盖的子字段 / 数组字段整体替换不逐元素合并 | 合并规则 1-4（核心公开契约行为） | resolver.go, resolver_test.go | T1 | [ ] ⏳ | None |
| T3 | 实现 Schema 校验：未知字段（含嵌套 Children）与类型不匹配（含被覆盖层、number 多数值类型、array 非 []any） | Schema 未声明字段返回 ErrUnknownField / 嵌套子字段未在 Children 中声明返回 ErrUnknownField / 字段类型与 Schema 不一致返回 ErrTypeMismatch / 被覆盖来源中的类型错误值同样返回 ErrTypeMismatch / number 类型接受多种 Go 整数与浮点具体类型 / array 字段提供非 []any 具体类型判定为类型不匹配 | `J1`/`J2`/`J6`/`J8`，合并规则 6-7 | resolver.go, resolver_test.go | T2 | [ ] ⏳ | None |
| T4 | 实现删除与必填字段缺失判定：显式 nil 删除、全程缺失、删除后恢复、嵌套必填随父删除一并判定 | 显式 nil 删除非必填字段 / 必填字段被删除且未恢复返回 ErrRequiredRemoved / 必填字段在所有来源中从未出现返回 ErrRequiredRemoved / 必填字段被更高优先级恢复不报错 / 嵌套对象内必填子字段随父对象删除一并判定为缺失 | `J3`/`J4`/`J5`，合并规则 5（关键不变量） | resolver.go, resolver_test.go | T2 | [ ] ⏳ | None |
| T5 | 实现 Provenance 的 JSON Pointer 路径生成（含 `/`→`~1`、`~`→`~0` 转义） | Provenance 使用 JSON Pointer 转义特殊字符字段名 | `J7`，合并规则 9 | resolver.go, resolver_test.go | T2 | [ ] ⏳ | None |
| T6 | 校验关键不变量：输入（含嵌套结构与 nil Data）不被修改、相同输入多次调用结果确定性一致 | 输入 Source.Data 与其嵌套结构在 Resolve 后保持不变 / 相同输入多次调用得到完全一致的输出 | 合并规则 8、10（关键不变量） | resolver.go, resolver_test.go | T3, T4, T5 | [ ] ⏳ | None |
| T7 | 编写性能与并发（数据竞争）验证测试：100 字段规模连续调用 10,000 次计时；多 goroutine 共享同一 sources 并发调用下 `go test -race` | 大型配置连续解析满足性能阈值 / 多 goroutine 共享同一 sources 并发调用无数据竞争 | `J9`/`J10`，性能要求（并发/竞态，Q3 信号） | resolver_test.go | T6 | [ ] ⏳ | None |
| T8 | 编写最小真实调用链 smoke 测试，并完成 `go test ./...`、`go vet ./...`、`go test -race ./...` 全量收尾 | 最小真实调用链验证整体可用性 | 用户任务（交付要求） | resolver_test.go | T6 | [ ] ⏳ | None |
