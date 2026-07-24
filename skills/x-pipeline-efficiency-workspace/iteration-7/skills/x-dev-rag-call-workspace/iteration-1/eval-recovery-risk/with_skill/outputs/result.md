# eval-recovery-risk 召回结果

- `source`：`skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references`
- `key_content`：

  ```text
  功能关键词：追加日志、启动恢复、末条记录、序列连续性、状态转换
  Risk：编码和校验和合法的日志记录仍可能违反序列连续性或状态转换规则，恢复过程可能接受语义非法状态。
  ```

- `top_n`：`1`
- CLI 退出码：`0`
- 召回数量：`1`

## 命中 1

- `id`：`A-risk-003`
- `source`：`/Volumes/machub_app/proj/x-dev-pipeline/skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references/risk-mistakes.md`
- 完整原文：

  ```markdown
  ## A-risk-003

  关键词：日志恢复、末条记录、校验和、状态迁移、序列完整性
  Risk：编码、字段和校验和都完整的日志末条记录仍可能违反序列或状态转换规则，恢复过程可能把语义非法记录当成有效状态。
  ```

## 召回内容用途

命中内容用于确认 Spec 已覆盖恢复语义检查，并把验收重点落到末条记录：即使编码和校验和完整，恢复器仍需拒绝序列不连续或违反状态转换规则的记录，避免产生不可能状态。
