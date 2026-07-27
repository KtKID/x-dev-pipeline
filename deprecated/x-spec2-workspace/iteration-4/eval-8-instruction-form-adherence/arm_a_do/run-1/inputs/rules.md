# 规则：目标行为

1. `feedback_same_task`：沿用 `R7`，把已完成的 attempt 2 推进到 attempt 3。
2. `duplicate_event_same_payload`：确认已存在事件，保持事件数 1、冲突为 false、终态为 running。
3. `duplicate_event_conflicting_payload`：隔离冲突，保持事件数 1 和已发布 success 终态，冲突为 true。
4. `late_evidence_after_terminal`：保持 success 终态，追加 1 个关联迟到证据的修订。
5. `crash_after_partial_persist`：使用原幂等身份安全重放，使 artifact/event 数都收敛为 1，并记录缺失指标原因。
6. `insufficient_origin_evidence`：保持 detected_stage 为 qa，把 origin_stage 留为 null，并保持根因待确认为 true。
7. `concurrent_knowledge_dedup`：通过 insert-or-return-existing 收敛为 1 个 canonical 条目，并保留 2 个来源关联。
8. `publish_rollback_fencing`：让 fence 42 的 V1 回滚保持生效，拒绝 fence 41 的迟到发布。
9. `task_binding_at_rollback_boundary`：提交前创建的 run 保持 V2，提交后创建的 run 绑定 V1，两个 run 都保持单一版本。
10. `retired_contract_field`：将旧字段读取识别为契约漂移，记录 producer `risk-router`、consumer `qa-gate`、有效 source `risk_profile`，阻止 candidate 进入 baseline。
