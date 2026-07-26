# Journal Index Recovery 隐藏评分

> 仅 grader 可见。执行者只接收题面与 fixture。
>
> `rubric_version: 3`

## 评分与门禁

共 25 条断言，每条 4 分，总分 100。质量门禁为 100 分，业务行为、运行边界与历史风险回归断言 1—24 全部通过。

## CLI、记录与状态：28 分

1. CLI JSON 成功/失败结构和稳定退出码符合契约。
2. put/get/list 跨进程重启保持值、version 和排序。
3. 同 request_id 同内容重试返回原 seq 且不追加日志。
4. 同 request_id 不同内容返回 IDEMPOTENCY_CONFLICT 且不写入。
5. expected_version 冲突返回 VERSION_CONFLICT 且状态稳定。
6. delete tombstone、NOT_FOUND 与 tombstone version 语义正确。
7. events.log 使用规范 JSON、精确字段和可独立校验的 CRC-32。

## 恢复与压缩：28 分

8. 截断的最后记录触发 RECOVERY_REQUIRED，recover 精确截断并恢复服务。
9. 最后记录 CRC 错误可由 recover 删除，既有状态保持。
10. 中间记录损坏产生 CORRUPT_LOG，recover 保持只读拒绝。
11. compact 后 snapshot + 空 log 能跨重启恢复 live/tombstone 状态。
12. compact 保留幂等账本并保持后续 seq 单调。
13. 遗留 snapshot.json.tmp 被忽略，损坏的已提交 snapshot 被拒绝。
14. 多进程并发写不同 key 无丢失且 seq 唯一。

## 并发与实现边界：8 分

15. 同 key 同 expected_version 并发更新只有一个成功。
16. backend 运行时代码只依赖 Python 标准库与本地模块。

## 接口完整性与存储边界：12 分

17. put/delete/replay/list/compact/recover 的成功 JSON 字段和值符合公开契约。
18. 健康日志上的 recover 可重复执行，返回零截断且不改变 journal 与状态。
19. 状态目录只保留声明的持久化文件，compact/recover 完成后无临时文件残留。

## 历史风险回归：20 分

20. compact 发布 snapshot 后保留旧 journal 的崩溃窗口可安全重启，重叠前缀只计入一次。
21. JSON 与字段结构合法、但无法由合法 mutation 历史生成的 snapshot 被只读拒绝。
22. 物理完整且 CRC 正确、但状态转换非法的最后 journal record 被判定为 `CORRUPT_LOG`。
23. `NOT_FOUND` 或 `VERSION_CONFLICT` 失败不会占用 request_id，修正后的请求可使用同一 ID 成功提交。
24. 七类公开错误全部保持精确 JSON envelope、字符串 message、稳定 code 与退出码。

## 运行边界：4 分

25. 只修改声明范围，临时文件和锁状态清理符合约定。

## 计量

- `quality_score = passed_assertions * 4`
- `token_delta = (candidate_total_tokens - baseline_total_tokens) / baseline_total_tokens`
- 晋级条件：每次 candidate `quality_score = 100`、断言 1—24 全过、两案例聚合 token 中位数至少下降 10%。
