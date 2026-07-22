# Task 01 规格质量评分

> 仅评测方可见。执行规格生成的模型只能读取 `evals/problems/task-01-configresolver/PROMPT.md` 与被测 skill。

## 评分方法

每条断言通过计 1，失败计 0。任务语义 20 条对应隐藏实现评分的 100 分，每条折合 5 分；规格结构 8 条单独报告。通过需要具体、可直接转成测试的证据，标题或关键词命中不计通过。

## 任务语义：合并语义 35 分

1. 明确 sources 低到高优先级，普通字段由最后一个有效高优先级值覆盖。
2. 明确 object 按 Children 递归合并，并覆盖至少三层嵌套对象。
3. 明确高优先级对象只覆盖其提供的叶子，低优先级未覆盖兄弟叶子继续保留。
4. 明确 array 整体替换，禁止逐元素或追加合并。
5. 明确 optional 字段遇到 nil 后从最终 Config 删除。
6. 明确删除对象或叶子后，相应最终叶子和 Provenance 一起消失。
7. 场景覆盖普通覆盖、递归对象、数组替换和删除四类合并路径，THEN 可直接断言具体结果。

## 任务语义：Schema 校验 20 分

8. 同时覆盖 required 字段被 nil 删除与所有来源缺失，并断言 errors.Is(..., ErrRequiredRemoved)。
9. 覆盖顶层或嵌套未知字段，并断言 errors.Is(..., ErrUnknownField)。
10. 覆盖类型错误，并断言 errors.Is(..., ErrTypeMismatch)。
11. 类型建模包含 string、全部整数/浮点 number、boolean、object、array；array 元素不校验。

## 任务语义：Provenance 15 分

12. Provenance 只记录最终叶子路径，值为提供最终叶子值的 Source.Name。
13. 递归对象场景分别断言保留叶子与覆盖叶子的来源。
14. 覆盖 RFC 6901 的 `~`→`~0`、`/`→`~1` 转义，并保持 Result.Config 原始字段名。

## 任务语义：边界条件 15 分

15. 明确 Resolve 不修改 schema、sources、Source.Data 及嵌套 map/slice，并用调用前后深比较验证。
16. 明确 Data 为 nil 的来源调用后仍为 nil，并覆盖 nil/空 schema 或 sources 的合法/错误结果。
17. 明确 Result 不共享会让输入被后续结果写入间接修改的可变别名，或用等价所有权断言封闭该风险。

## 任务语义：性能与确定性 10 分

18. 覆盖相同逻辑数据采用不同 map 插入顺序仍得到 DeepEqual 的 Config 与 Provenance。
19. 覆盖约 100 字段连续 10,000 次小于 2 秒，并用 race detector 验证共享 sources 并发调用无数据竞争。

## 任务语义：工具门禁 5 分

20. Smoke/验收命令包含 `go test ./...` 与 `go vet ./...`，并为性能和竞态给出可执行测试入口。

## 规格结构：8 条

21. 任务目标描述可观察成功结果，非目标明确实现范围。
22. 影响边界包含 configresolver 目标模块、调用方上游、结果/错误消费方下游。
23. 边界表写出输入不可变、确定性、公开 API/错误兼容和并发安全等相关不变量。
24. 判断依据只保存影响实现或验收的事实/推断，并被边界或 Scenario 引用。
25. 建模覆盖逐项声明数据流、状态、时序、资源、不变量、故障的落点或具体不适用理由。
26. 验收清单区分 unit、smoke、e2e，E2E 写明需要或省略及依据。
27. 测试驱动顺序体现 Scenario 到失败测试、最小实现、重构回归。
28. Scenario 直接使用 GIVEN/WHEN/THEN，并标出测试层和依据。

## 汇总

- `task_semantic_score = 通过的 1..20 数量 × 5`
- `structure_score = 通过的 21..28 数量 / 8`
- 正确性优先：1..20 中任一关于 required 删除、输入不可变、确定性或竞态的失败均记录为关键缺口。
