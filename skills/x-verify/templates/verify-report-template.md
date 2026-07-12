# Verify Report — <task-name> — YYYYMMDD-HHmmss

**Status:** pass / fail
**Completed by model:** <actual model id>
**dev-report 来源:** dev-pipeline/tasks/<task>/dev-report.md
**fix-attempts:** N / 3

## 命令复跑结果

| # | 来源 | 命令 | 预期 exit | 实际 exit | 预期输出片段 | 输出含此片段? | 结果 |
|---|------|------|----------|----------|------------|--------------|------|
| 1 | dev-report | `npm run build` | 0 | 0 | `Compiled successfully` | ✓ | ✅ pass |
| 2 | dev-report | `npm test` | 0 | 1 | `Tests: 42 passed` | ✗ | ❌ fail |
| 3 | README smoke S1 | `bash scripts/smoke.sh` | 0 | 0 | `smoke passed` | ✓ | ✅ pass |

## 待人工验收（manual 用例）

| ID | 用例 | 步骤摘要 | 状态 |
|----|------|---------|------|
| E2 | 拖拽上传出错提示 | 打开页面拖入超大文件 | ⏳ 待人工 |

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

- [ ] 全部 pass → 对话输出回执 → 触发 x-qa-gate
- [ ] 任一 fail → 对话输出回执（列全部 fail 项）→ 触发 x-fix（mode: verify-fix，批量修），由 x-fix 按轮递增 fix-counter
