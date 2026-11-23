# 开发收尾与验收：覆盖率之后做什么

你是执行 x-dev 或 x-qdev 的 agent。只读下面六个文件，不读仓库里的其他任何文件：

1. `skills/x-dev/SKILL.md`
2. `skills/x-dev/references/test-reporting.md`
3. `skills/x-qdev/SKILL.md`（重点读第 4、5 节）
4. `skills/x-verify-spec/SKILL.md`
5. `skills/x-verify-spec/references/feature-check.md`
6. 题目：`evals/problems/dev-delivery/cases.json`

每道题是一个当前状态，按规则判断下一步。`action` 只能取下面16个值之一：

`补测试后重跑 xdev coverage`、`修好失败的测试再重跑 xdev coverage`、`在问题与处置写理由`、`重跑 xdev coverage`、`按 change-sync 同步后 xdev baseline`、`写测试并登记到用例对应表`、`写人工记录到 evidence 并记人工通过`、`升为已完成并交付`、`交 x-verify-spec 验收`、`运行 xdev start 记代码基线`、`退回开发者修，修完重跑 coverage 再重做功能检查`、`重跑 xdev coverage 后重做功能检查`、`查是不是自己改坏的，不删不跳过`、`另写一份测试报告`、`运行 xdev usage fill 填这一期的用量`、`先运行 xdev usage start 在用量表加一行`

把结果写成一个 JSON 数组，保存到调用方给你的输出路径。不要输出别的文件。格式：

```json
[
  {"id": "D00", "action": "<上面的值之一>", "reason": "一句话理由"}
]
```
