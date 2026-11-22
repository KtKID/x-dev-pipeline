# qdev 对账：spec 确认记录检查

你是执行 x-verify-spec 的 agent，只做 qdev 的“spec 确认记录”这一项人工检查。只读下面两个文件，不读仓库里的其他任何文件：

1. 规则：`skills/x-verify-spec/SKILL.md`
2. 题目：`evals/problems/qdev-confirm-check/cases.json`

每道题给出这次 task 的 spec 改动（`spec_diff`）和 task ①里“spec 归属与确认”的记录（`task_record`）。按规则判断这一项检查的结论。

- `result` 只能取三种值：`核对通过`、`核对未完成`、`核对不通过`。

把结果写成一个 JSON 数组，保存到调用方给你的输出路径。不要输出别的文件。格式：

```json
[
  {"id": "V00", "result": "<核对通过|核对未完成|核对不通过>", "reason": "一句话理由"}
]
```
