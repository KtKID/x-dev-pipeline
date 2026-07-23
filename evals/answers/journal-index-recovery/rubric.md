# Journal Index Recovery 隐藏评分

> 仅 grader 可见。Executor 只接收题面、fixture 与被测 pipeline 快照。

## 评分与门禁

共 20 条断言，每条 5 分，总分 100。质量门禁为 100 分，运行时与 pipeline 证据断言 1—19 全部通过。

## CLI、记录与状态：35 分

1. CLI JSON 成功/失败结构和稳定退出码符合契约。
2. put/get/list 跨进程重启保持值、version 和排序。
3. 同 request_id 同内容重试返回原 seq 且不追加日志。
4. 同 request_id 不同内容返回 IDEMPOTENCY_CONFLICT 且不写入。
5. expected_version 冲突返回 VERSION_CONFLICT 且状态稳定。
6. delete tombstone、NOT_FOUND 与 tombstone version 语义正确。
7. events.log 使用规范 JSON、精确字段和可独立校验的 CRC-32。

## 恢复与压缩：35 分

8. 截断的最后记录触发 RECOVERY_REQUIRED，recover 精确截断并恢复服务。
9. 最后记录 CRC 错误可由 recover 删除，既有状态保持。
10. 中间记录损坏产生 CORRUPT_LOG，recover 保持只读拒绝。
11. compact 后 snapshot + 空 log 能跨重启恢复 live/tombstone 状态。
12. compact 保留幂等账本并保持后续 seq 单调。
13. 遗留 snapshot.json.tmp 被忽略，损坏的已提交 snapshot 被拒绝。
14. 多进程并发写不同 key 无丢失且 seq 唯一。

## 并发与实现边界：10 分

15. 同 key 同 expected_version 并发更新只有一个成功。
16. backend 运行时代码只依赖 Python 标准库与本地模块。

## Pipeline 产物与证据：20 分

17. spec3 覆盖状态机、持久化边界、损坏分类、并发不变量、测试层与稳定 Scenario ID。
18. req3 checklist 可解析，完整回指 spec Scenario，依赖图与风险路由有效。
19. dev-report 的 unit、smoke、e2e 证据可由 xdev verify 复跑。
20. 只修改声明范围，临时文件和锁状态清理符合约定。

## 计量

- `quality_score = passed_assertions * 5`
- `token_delta = (candidate_total_tokens - baseline_total_tokens) / baseline_total_tokens`
- 晋级条件：每次 candidate `quality_score = 100`、断言 1—19 全过、两案例聚合 token 中位数至少下降 10%。

