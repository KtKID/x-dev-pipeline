# 验收路由与架构约束

你是执行管线的 agent。只读下面五个文件，不读仓库里的其他任何文件：

1. `skills/x-verify-spec/SKILL.md`
2. `skills/x-verify-spec/references/feature-check.md`
3. `skills/x-tech-design/SKILL.md`
4. `skills/x-ask-spec/templates/spec.md`（重点读「关键约束」一节和里面的注释）
5. 题目：`evals/problems/verify-route/cases.json`

每道题是一个情况和一个问题，按规则回答。`answer` 只能取下面20个值之一：

`只跑 xdev check，不做功能检查`、`派一个子 agent 做一次功能检查，再跑 xdev check`、`不报，交给定期架构巡检`、`P1`、`P0`、`不做，xdev check 已核对`、`不加，照派工单模板只填路径`、`不另存，只留 evidence/feature-check.md 一份`、`重跑 xdev coverage，重做功能检查，再跑 xdev check`、`在问题与处置登记，不修`、`不报，记账由主 agent 和 xdev check 管`、`单独问用户这一项`、`不写，只记用户说过的约束`、`写进 engineering spec 的关键约束并注明来源`、`派两个子 agent，一个查测试、一个查功能`、`发回原检查员复审`、`照常做，再核一遍`、`直接改约束再按新方案做`、`另派一个 reviewer 做独立审查`、`P2`

把结果写成一个 JSON 数组，保存到调用方给你的输出路径。不要输出别的文件。格式：

```json
[
  {"id": "V00", "answer": "<上面的值之一>", "reason": "一句话理由"}
]
```
