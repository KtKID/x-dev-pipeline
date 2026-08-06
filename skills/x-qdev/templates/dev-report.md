# Qdev Report — <task-name> — YYYYMMDD-HHmmss

<!--
收尾文档。DoD 证据闭环时产出，记录实际改动与真实验证结果。
时间戳格式：YYYYMMDD-HHmmss。
-->

## 风险与审查路线

- 风险等级：Q0 / Q1 / Q2 / Q3（已升级）
- 触发因素：<风险事实>
- 审查路线：主 agent 闭环 / 综合 reviewer / 用户指定完整门禁

## 改动文件

- `<path>` — <改动内容>

## DoD 证据矩阵

<!--
规范 5 的实际证据：每条 DoD 的运行结果。
证据强度：真实运行/用户可见验收 > 定向测试 > 公开契约与调用链 > 静态检查 > agent 自述。
仅 agent 自述不算证据，对应 DoD 标记未完成。
-->

| DoD | 证据类型 | 命令 / 测试 / 代码路径 / 人工步骤 | 实际结果 | 状态 |
|-----|----------|-----------------------------------|----------|------|
| D1 | 定向测试 | `<command>` | exit 0，关键结果：`...` | pass |

## 实际验证命令

| 命令 | 工作目录 | 实际 exit | 关键输出 |
|------|----------|-----------|----------|
| `<command>` | `<cwd>` | 0 | `<output>` |

项目没有测试框架时填写：

```text
no-test-framework: true
reason: <原因>
manual-check: <真实执行的人工验收步骤和结果>
```

## Diff 审查

- 任务起点基线：<status / name-only / stat 摘要>
- `git diff --stat`：<摘要>
- 实际范围与声明范围：一致 / 有差异（说明）
- 成功路径证据：<证据>
- 关键失败路径证据：<证据 / N/A + 原因>
- 用户既有改动保护：<检查结果>

## 综合 Reviewer（仅 Q2）

- Status：pass / fail / N/A
- Evidence：<文件位置与结论>
- P0：<问题 / none>
- P1：<问题 / none；逐条填写 resolved / accepted-with-evidence / promoted>

## 最终结论

- [ ] 每条 DoD 都有真实证据
- [ ] 实际 diff 与任务范围一致
- [ ] 成功路径已验证
- [ ] 适用的关键失败路径已验证
- [ ] Q2 综合 reviewer 已通过或当前路线为 Q0/Q1

结论：complete / blocked / promoted-to-full-pipeline

升级完整流程时填写：

```text
promotion-target: dev-pipeline/tasks/<task-name>-full
source-qdev: dev-pipeline/tasks/<task-name>
```
