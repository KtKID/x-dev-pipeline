# spec 归属判断

你是一名 agent。只读下面三个文件，不读仓库里的其他任何文件：

1. 规则：`skills/x-explore-for-spec/references/spec-scope.md`
2. 题目项目的 spec 索引：`evals/problems/spec-scope/project-spec-index.md`
3. 题目：`evals/problems/spec-scope/cases.json`

对每一道题，按规则判断这个需求要写进哪些 spec、每份 spec 怎么写。

- `action` 只能取三种值：
  - `append`：在这份已有 spec 里新增或修改场景（或 feat）。
  - `new`：新建一份 spec 并写场景。`spec` 填你给新 spec 起的名字。
  - `log-only`：只在这份 spec 的变更记录里记一行，不写场景。
- 只列出要写场景或要记变更记录的 spec。只在主 spec 的 C 里写一句依赖、自己不写场景的 spec，不要列出来。

把结果写成一个 JSON 数组，保存到调用方给你的输出路径。不要输出别的文件。格式：

```json
[
  {"id": "S00", "writes": [{"spec": "<spec 名>", "action": "<append|new|log-only>"}], "reason": "一句话理由"}
]
```
