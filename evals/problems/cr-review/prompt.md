# 查代码对不对

你是执行管线的 agent。只读下面这些文件，不读仓库里的其他任何文件：

1. `skills/x-cr/SKILL.md`
2. `skills/x-cr/references/report-template.md`
3. `skills/x-cr/references/invariant-review.md`
4. `skills/x-cr/references/bayesian-review.md`
5. 题目：`evals/problems/cr-review/cases.json`

每道题是一个情况和一个问题，按规则回答。`answer` 只能取下面32个值之一：

`C2`、`INV-SPEC-01`、`P0`、`P1`、`P2`、`docs/spec/loan/tasks/task-renew-limit/reports/cr/`、`loan:C2`、`loan:D04`、`loan:feat03-场景2`、`reports/cr/`、`不做原因排查`、`不报`、`不改 spec，报告里提醒用户补`、`不改代码，给报告；用户要修再交 x-fix`、`不用开问题`、`不能直接判守住了，自己走代码或跑反例`、`写 commit 哈希`、`写文件、函数和行`、`列 2–4 个可能原因逐个排除`、`守住了`、`新1`、`来源不一`、`查当前 git diff`、`查整个仓库`、`没法验证`、`没走到`、`测试全绿，判守住了`、`直接修掉`、`直接把规则补进 spec`、`被打破`、`要开一个问题，一般是 P2`、`问用户要查什么`

把结果写成一个 JSON 数组，保存到调用方给你的输出路径。不要输出别的文件。格式：

```json
[
  {"id": "R00", "answer": "<上面的值之一>", "reason": "一句话理由"}
]
```
