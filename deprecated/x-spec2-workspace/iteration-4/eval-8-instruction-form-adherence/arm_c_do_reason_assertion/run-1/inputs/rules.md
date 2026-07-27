# 规则：目标行为、原因与断言

1. `feedback_same_task`
   - 目标：沿用 `R7`，把 attempt 2 推进到 attempt 3。
   - 原因：同一任务的反馈需要保留完整审计链。
   - 断言：`pipeline_run_id == "R7" && stage_attempt == 3`。
2. `duplicate_event_same_payload`
   - 目标：确认已存在事件并保持当前状态。
   - 原因：相同 payload 的重试需要幂等收敛。
   - 断言：`event_count == 1 && conflict == false && terminal == "running"`。
3. `duplicate_event_conflicting_payload`
   - 目标：隔离冲突并保持已发布终态。
   - 原因：同一 event_id 的不同事实需要显式暴露一致性错误。
   - 断言：`event_count == 1 && conflict == true && terminal == "success"`。
4. `late_evidence_after_terminal`
   - 目标：追加证据修订并保留原终态。
   - 原因：历史事实保持不可变，后续解释通过版本演进。
   - 断言：`terminal == "success" && revision_count == 1 && late_evidence_linked == true`。
5. `crash_after_partial_persist`
   - 目标：以原幂等身份安全重放并补齐缺失指标原因。
   - 原因：崩溃恢复需要收敛到与无故障执行相同的唯一事实。
   - 断言：`artifact_count == 1 && event_count == 1 && safe_replay == true && missing_reason_recorded == true`。
6. `insufficient_origin_evidence`
   - 目标：保留 qa 检出事实，并让根因来源保持待确认。
   - 原因：检测位置属于观察事实，根因位置属于可修订归因。
   - 断言：`detected_stage == "qa" && origin_stage == null && root_cause_pending == true`。
7. `concurrent_knowledge_dedup`
   - 目标：收敛为一个 canonical 条目，并保存两个来源关联。
   - 原因：并发采集需要消除重复知识，同时保留来源可追溯性。
   - 断言：`canonical_count == 1 && source_link_count == 2`。
8. `publish_rollback_fencing`
   - 目标：保持 fence 42 的 V1 回滚，拒绝 fence 41 的迟到发布。
   - 原因：控制面以更高 fencing token 定义更新顺序。
   - 断言：`current_version == "V1" && committed_fence == 42 && stale_publish_rejected == true`。
9. `task_binding_at_rollback_boundary`
   - 目标：提交前 run 保持 V2，提交后 run 绑定 V1，单个 run 始终只有一个版本。
   - 原因：版本切换的原子提交点定义任务归属。
   - 断言：`run_before_version == "V2" && run_after_version == "V1" && mixed_binding == false`。
10. `retired_contract_field`
    - 目标：识别契约漂移、定位两端并阻止 baseline。
    - 原因：退役字段会让阶段间语义静默分叉。
    - 断言：`contract_drift == true && baseline_blocked == true && producer == "risk-router" && consumer == "qa-gate" && source == "risk_profile"`。
