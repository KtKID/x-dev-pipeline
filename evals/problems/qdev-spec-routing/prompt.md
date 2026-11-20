# x-qdev 路由判断

你是一名准备执行 x-qdev 的 agent。只读下面四个文件，不读仓库里的其他任何文件：

1. `skills/x-qdev/SKILL.md`
2. `skills/x-explore-for-spec/references/spec-scope.md`
3. 题目项目的 spec 索引：`evals/problems/qdev-spec-routing/project-spec-index.md`
4. 题目：`evals/problems/qdev-spec-routing/cases.json`

每道题给出用户的要求和计划改动的源码文件。不要真的改代码，只按 x-qdev 的规则回答下面五个字段：

- `route`：`qdev`（留在 x-qdev）或 `mainline`（转完整主线）。
- `writes`：要写哪些 spec、怎么写。格式同下，`action` 只能是 `append`、`new`、`log-only`；只在主 spec 的 C 里写依赖的 spec 不列。`route` 为 `mainline` 时填空数组。
- `task_spec`：task 放在哪份 spec 的 `tasks/` 下（新建的 spec 填你起的名字）。`route` 为 `mainline` 时填 `null`。
- `confirm`：写完 spec 后是否要停下来给用户确认，`true` 或 `false`。`route` 为 `mainline` 时填 `null`。
- `tech_design`：`x-tech-design` 或 `task`（在 task 的②里简写）。`route` 为 `mainline` 时填 `null`。

把结果写成一个 JSON 数组，保存到调用方给你的输出路径。不要输出别的文件。格式：

```json
[
  {"id": "Q00", "route": "qdev", "writes": [{"spec": "<spec 名>", "action": "<append|new|log-only>"}], "task_spec": "<spec 名>", "confirm": true, "tech_design": "<x-tech-design|task>", "reason": "一句话理由"}
]
```
