# Verify Report — qa-gate-pipeline-smoke — 20260427-150500

**Status:** fail
**dev-report 来源:** dev-pipeline/tasks/qa-gate-pipeline/_smoke/dev-report-sample.md
**fix-attempts:** 1 / 6

## 命令复跑结果

| # | 命令 | 预期 exit | 实际 exit | 预期输出片段 | 输出含此片段? | 结果 |
|---|------|----------|----------|------------|--------------|------|
| 1 | `echo passing-command` | 0 | 0 | `passing-command` | ✓ | ✅ pass |
| 2 | `false` | 0 | 1 | (none) | n/a | ❌ fail |

## 失败命令详情

### 命令 #2: `false`
- **stdout 摘录** (前 50 行):
  ```
  (empty)
  ```
- **stderr 摘录**:
  ```
  (empty)
  ```
- **不一致原因**: 预期 exit=0，实际 exit=1。

## 下游动作

- [x] 任一 fail → 触发 x-fix（mode: verify-fix），fix-attempts +1
- [ ] 全部 pass → 触发 x-qua-gate
