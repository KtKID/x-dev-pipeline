# Verify Failure Report — <task-name> — YYYYMMDD-HHmmss

**Status:** fail
**dev-report 来源:** dev-pipeline/tasks/<task>/dev-report.md
**fix-attempts:** N / 3

## 失败 verify 块

| ID | 命令 | 预期 exit | 实际 exit | 缺失输出 | 超时 | 诊断 |
|----|------|----------|----------|----------|------|------|
| S1 | `...` | 0 | 1 | `...` | 否 | [基于 output_tail 的事实诊断] |

## 未覆盖自动场景

| README Scenario | 缺失的 verify 回指 | 修复动作 |
|-----------------|---------------------|----------|
| ... | `scenario:` | 补充或改正 verify 块 |

## 下游动作

- [ ] 将本轮全部 failure 与 uncovered 交 x-fix（mode: verify-fix）。
