# tech-design 要不要用户确认

你是执行管线的 agent。只读下面四个文件，不读仓库里的其他任何文件：

1. `skills/x-tech-design/SKILL.md`
2. `skills/x-req/SKILL.md`（重点读“就绪检查”）
3. `skills/x-qdev/SKILL.md`（重点读第 3 节）
4. 题目：`evals/problems/td-confirm/cases.json`

每道题是一个情况，按规则判断下一步。`action` 只能取下面六个值之一：

`直接交给 x-req`、`单独问用户这一项，其余照常交接`、`停下等用户确认整份设计`、`可以拆任务`、`受影响的部分等答复，其余先拆`、`继续开发，交付时一起告知`

把结果写成一个 JSON 数组，保存到调用方给你的输出路径。不要输出别的文件。格式：

```json
[
  {"id": "T00", "action": "<六个值之一>", "reason": "一句话理由"}
]
```
