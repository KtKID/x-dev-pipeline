# Terra xhigh Spec risk review

## Verdict

- Model constraint: pass; the isolated thread records `gpt-5.6-terra` with `xhigh`.
- Context isolation: pass; zero inherited completed turns, zero subagents and zero tool reads outside the isolated workspace.
- Workflow trigger: pass; x-spec3 independently selected `full`, then read x-adversarial-risk and its complete corpus.
- Risk replay: pass; all five confirmed issues became traceable Scenarios.
- Mechanical quality: `94/100`, 16 of 17 assertions passed.
- Validators: Spec and risk corpus both pass.

## Risk scores

| Phase | Complexity | Importance | Average | Budget |
|---|---:|---:|---:|---|
| x-spec3 first draft | 4 | 4 | 4.0 | full |
| x-adversarial-risk final | 5 | 4 | 4.5 | full |
| Evidence-grounded review | 5 | 1 | 3.0 | full |

Complexity 5 is directly supported by cross-process locking, global idempotency,
concurrency and crash recovery. Importance 4 requires a task fact showing a
core function for all users. The supplied fixture defines a local CLI; its
user and business impact are unspecified. Importance 1 is the supported
anchor for this self-contained eval case. The corrected score still routes to
`full` because either dimension at 5 forces full review.

## Baseline-gap coverage

| Earlier baseline finding | Final Scenario | Source |
|---|---|---|
| Compact snapshot/log replace-window recovery | `SC_29` | `AR-001` |
| Structurally valid but semantically impossible snapshot | `SC_30` | `AR-002` |
| Physically complete but logically invalid final record | `SC_31` | `AR-003` |
| Failed mutation must not occupy request_id | `SC_32` | `AR-004` |
| Complete public error JSON contract | `SC_33` | `AR-005` |

The run also generated four assumption-driven Scenarios: first-result replay
marker, missing/tombstoned read behavior, concurrent identical request
deduplication and readers during compact.

The five known gaps were recovered through the skill's confirmed mistake
corpus. This demonstrates deterministic pre-development replay of learned
failures. Independent rediscovery remains unmeasured. The four assumption
Scenarios are the independent adversarial contribution in this run.

## Cost

- Agent-tree tokens: `1,411,304`.
- Cached input tokens: `1,306,112`.
- Output tokens: `31,329`.
- Wall time: `621,370 ms` (`10m 21.37s`).
- Tool calls: 25.

This is a Spec-only run. The earlier `3,369,225`-token candidate measured the
entire spec → implementation → QA pipeline, so the two totals have different
scope.
