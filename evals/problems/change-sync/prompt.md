# 需求变化同步判断

你是一名 agent。只读下面五个文件，不读仓库里的其他任何文件：

1. 规则：`skills/x-tech-design/references/change-sync.md`
2. 题目项目的 spec：`evals/problems/change-sync/fixture/spec.md`
3. 技术设计：`evals/problems/change-sync/fixture/tech-design.md`
4. 开发清单：`evals/problems/change-sync/fixture/dev-checklist.md`
5. 题目：`evals/problems/change-sync/cases.json`

每道题是一处独立的 spec 变化（题与题之间互不影响，都从上面这三份文件的原样出发）。按规则判断，下游哪些东西要动、怎么动。

- `item` 写编号或路径：D 写 `D01` 这样的编号，用例写 `T3`，任务行写 `任务行2`，测试文件写清单里的路径（如 `tests/renew.test.ts`）。新增的 D 或 T 还没有编号，写 `新D`、`新T`；新增的任务行写 `新任务行`。
- `action` 只能取五种值：`改`、`新增`、`退役`、`重开`、`重跑`。
- 只列要动的项。不动的项不要列出来。没有任何项要动时，`changes` 填空数组。

把结果写成一个 JSON 数组，保存到调用方给你的输出路径。不要输出别的文件。格式：

```json
[
  {"id": "C00", "changes": [{"item": "<编号或路径>", "action": "<改|新增|退役|重开|重跑>"}], "reason": "一句话理由"}
]
```
