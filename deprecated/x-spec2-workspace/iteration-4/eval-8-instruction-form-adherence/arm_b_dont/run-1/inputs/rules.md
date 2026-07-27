# 规则：禁止行为

1. `feedback_same_task`：不得为同一任务反馈创建 R8，也不得复用已完成的 attempt 2。
2. `duplicate_event_same_payload`：不得追加重复事件，不得报告冲突，不得改变 running 终态。
3. `duplicate_event_conflicting_payload`：不得接受冲突 payload，不得增加事件数，不得改写已发布 success 终态，不得把冲突保留为 false。
4. `late_evidence_after_terminal`：不得覆盖 success 终态，不得丢弃迟到证据，不得让 revision_count 保持为 0。
5. `crash_after_partial_persist`：不得重复创建 artifact，不得重复提交 event，不得把不确定写入当成全新提交，不得遗漏缺失指标原因。
6. `insufficient_origin_evidence`：不得改变 qa 检出阶段，不得在证据缺失时写入 origin_stage，不得把根因标为已确认。
7. `concurrent_knowledge_dedup`：不得生成两个 canonical 条目，不得丢失任一 writer 的来源关联。
8. `publish_rollback_fencing`：不得让 fence 41 覆盖 fence 42，不得把 current_version 推回 V2，不得接受迟到 publish。
9. `task_binding_at_rollback_boundary`：不得重绑提交前已经创建的 run，不得让提交后创建的 run 继续使用 V2，不得产生混合版本绑定。
10. `retired_contract_field`：不得把 `risk_level_v1` 当作有效 source，不得让 candidate 进入 baseline，不得遗漏 producer 和 consumer 的漂移定位。
