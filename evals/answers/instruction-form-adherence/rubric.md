# Instruction Form Adherence Rubric

此 rubric 只交给确定性 grader，不进入 executor 上下文。

- 从 `outputs/decisions.json` 读取 `decisions`。
- 每个 case 独立形成一条二元断言。
- `case_id` 必须唯一、完整。
- `result` 的键集合和值必须与 `expected.json` 对应对象完全相等。
- 缺失、额外字段、类型变化、非法 JSON 或重复 case 均判该 case 失败。
- 每个 run 共 10 条断言；每个配置重复 3 次，形成 30 个观测点。
- A/B/C 只改变 `rules.md`；prompt、case 内容、case 顺序、模型、repo、权限和评分器按 repetition 配对一致。
