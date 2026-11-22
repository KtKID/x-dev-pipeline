# 独立审查与架构约束

你是执行管线的 agent。只读下面五个文件，不读仓库里的其他任何文件：

1. `skills/x-qa-gate/SKILL.md`
2. `skills/x-tech-design/SKILL.md`
3. `skills/x-ask-spec/templates/spec.md`（重点读「关键约束」一节和里面的注释）
4. `skills/x-ask-spec/references/spec-scope.md`
5. 题目：`evals/problems/review-route/cases.json`

每道题是一个情况和一个问题，按规则回答。`answer` 只能取下面16个值之一：

`不派 reviewer`、`q1 q3 q4`、`q1 q2 q3 q4`、`q1 q2 q3 q4 逐 lens 回执`、`q4-design P1`、`q3-evidence P1`、`q2-correctness P0`、`q1-intent P2`、`不做，xdev check 已核对`、`单独问用户这一项`、`不写，只记用户说过的约束`、`写进 engineering spec 的关键约束并注明来源`、`不发回，用反例测试和 xdev check 关闭`、`发回原 reviewer 复审`、`直接改约束再按新方案做`、`照常做，reviewer 自己再核一遍`

lens 简写：q1 = q1-intent，q2 = q2-correctness，q3 = q3-evidence，q4 = q4-design。

把结果写成一个 JSON 数组，保存到调用方给你的输出路径。不要输出别的文件。格式：

```json
[
  {"id": "R00", "answer": "<上面的值之一>", "reason": "一句话理由"}
]
```
