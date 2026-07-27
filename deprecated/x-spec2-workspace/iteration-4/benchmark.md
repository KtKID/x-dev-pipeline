# Instruction Form A/B/C Benchmark

## Three-arm summary

| Configuration | Exact match | All-10 runs | Tokens | Time | Tool calls | Instruction chars |
|---|---:|---:|---:|---:|---:|---:|
| arm_a_do | 100.0% ± 0.0% | 100.0% | 108496 ± 14675 | 37.9s ± 3.5s | 2.67 ± 0.47 | 864 |
| arm_b_dont | 96.7% ± 4.7% | 66.7% | 88500 ± 48 | 39.1s ± 0.3s | 2.00 ± 0.00 | 873 |
| arm_c_do_reason_assertion | 100.0% ± 0.0% | 100.0% | 99896 ± 15480 | 55.4s ± 26.4s | 2.33 ± 0.47 | 1880 |

## Pairwise deltas

| Pair | Quality points | Token delta | Token ratio | Time delta | Time ratio |
|---|---:|---:|---:|---:|---:|
| arm_a_do_minus_arm_b_dont | +3.3 | +19997 | +22.6% | -1.1s | -2.9% |
| arm_a_do_minus_arm_c_do_reason_assertion | +0.0 | +8600 | +8.6% | -17.5s | -31.6% |
| arm_b_dont_minus_arm_c_do_reason_assertion | -3.3 | -11397 | -11.4% | -16.4s | -29.5% |

## Per-case pass frequency

| Case | arm_a_do | arm_b_dont | arm_c_do_reason_assertion |
|---|---:|---:|---:|
| concurrent_knowledge_dedup | 3/3 | 3/3 | 3/3 |
| crash_after_partial_persist | 3/3 | 3/3 | 3/3 |
| duplicate_event_conflicting_payload | 3/3 | 3/3 | 3/3 |
| duplicate_event_same_payload | 3/3 | 3/3 | 3/3 |
| feedback_same_task | 3/3 | 3/3 | 3/3 |
| insufficient_origin_evidence | 3/3 | 3/3 | 3/3 |
| late_evidence_after_terminal | 3/3 | 3/3 | 3/3 |
| publish_rollback_fencing | 3/3 | 3/3 | 3/3 |
| retired_contract_field | 3/3 | 2/3 | 3/3 |
| task_binding_at_rollback_boundary | 3/3 | 3/3 | 3/3 |

## Analyzer notes

- arm_a_do: exact-match 100.0% ± 0.0%, all-10 run rate 100.0%, mean 108496 tokens, mean 37.9s, mean 2.67 tool calls.
- arm_b_dont: exact-match 96.7% ± 4.7%, all-10 run rate 66.7%, mean 88500 tokens, mean 39.1s, mean 2.00 tool calls.
- arm_c_do_reason_assertion: exact-match 100.0% ± 0.0%, all-10 run rate 100.0%, mean 99896 tokens, mean 55.4s, mean 2.33 tool calls.
- arm_b_dont 的随机波动 case: retired_contract_field。
- arm_a_do_minus_arm_b_dont: quality +3.3 points, tokens +22.6%, time -2.9%.
- arm_a_do_minus_arm_c_do_reason_assertion: quality +0.0 points, tokens +8.6%, time -31.6%.
- arm_b_dont_minus_arm_c_do_reason_assertion: quality -3.3 points, tokens -11.4%, time -29.5%.
