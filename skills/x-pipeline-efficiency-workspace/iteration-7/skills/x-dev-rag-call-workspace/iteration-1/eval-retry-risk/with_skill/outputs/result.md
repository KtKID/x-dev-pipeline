# eval-retry-risk 召回结果

- `source`：`skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references/risk-mistakes.md`
- `key_content`：

  ```text
  功能关键词：订单接口、request_id、幂等请求、失败重试、唯一业务副作用
  Risk：失败发生在业务结果持久化之前时，幂等标识的占用状态可能阻止同一 request_id 的合法重试，导致唯一副作用丢失。
  ```

- `top_n`：`1`
- CLI 退出码：`0`
- 召回数量：`1`

## 命中 1

- `id`：`A-risk-004`
- `source`：`/Volumes/machub_app/proj/x-dev-pipeline/skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references/risk-mistakes.md`
- 完整原文：

  ```markdown
  ## A-risk-004

  关键词：幂等请求、失败重试、请求历史、去重标识
  Risk：失败请求提前占用幂等标识时，同一标识的后续合法请求可能被错误拒绝或丢失应产生的唯一副作用。
  ```

## 召回内容用途

命中内容用于检查 Spec 的幂等记录时机：系统需要在业务结果成功持久化后再确认幂等标识已完成，失败状态需要允许同一 `request_id` 合法重试，并验证最终只产生一次有效业务副作用。
