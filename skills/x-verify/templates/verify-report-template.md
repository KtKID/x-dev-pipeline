# Verify Report — <task-name> — YYYYMMDD-HHmmss

**Status:** pass / fail
**dev-report 来源:** dev-pipeline/tasks/<task>/dev-report.md
**fix-attempts:** N / 6

## 命令复跑结果

| # | 命令 | 预期 exit | 实际 exit | 预期输出片段 | 输出含此片段? | 结果 |
|---|------|----------|----------|------------|--------------|------|
| 1 | `npm run build` | 0 | 0 | `Compiled successfully` | ✓ | ✅ pass |
| 2 | `npm test` | 0 | 1 | `Tests: 42 passed` | ✗ | ❌ fail |

## 失败命令详情

### 命令 #2: `npm test`
- **stdout 摘录** (前 50 行):
  ```
  ...
  ```
- **stderr 摘录**:
  ```
  ...
  ```

## 下游动作

- [ ] 全部 pass → 触发 x-qua-gate
- [ ] 任一 fail → 触发 x-fix（mode: verify-fix），fix-attempts +1
