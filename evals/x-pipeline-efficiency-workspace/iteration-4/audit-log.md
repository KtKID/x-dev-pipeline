# Iteration 4 audit log

## Change under test

- Consolidated the duplicated x-dev batch discipline into one ordered block.
- Added an explicit low-freedom instruction to x-qa-gate: assemble one complete reviewer prompt and spawn with `fork_turns:"none"`.
- Froze the exact skills and tools in `snapshots/candidate-fork-none-terra-20260723`.

## Valid run

- Model: `gpt-5.6-terra`.
- Reasoning effort: `xhigh`.
- Root session: `019f8d9f-76a1-78b3-bfac-f152cac66684`.
- Reviewer session: `019f8dad-852b-74b3-ac17-3049f6d85d06`.
- Hidden score: 95/100.
- Tokens: 3,369,225.
- Duration: 1,325,411 ms.
- Reviewer protocol: one `fork_turns:none` spawn, one final answer, zero follow-ups.

## Audit finding

The run meets the requested score threshold and observed token-reduction threshold. It also exposes one report-generation gap: dev-report contained 11 valid verify blocks and explicit unit/smoke evidence, while the E2E omission decision stayed in spec.md. This single missing report field reduced the score by five points and failed the evaluator's critical gate.

## Validity boundary

- Each arm currently has one Terra run.
- Previous comparison runs used Sol, so those historical percentages include model and variance effects.
- The invalid preflight attempt below is excluded from all metrics.

## Same-model paired baseline

- Frozen baseline snapshot: `baseline-20260723`.
- Model and reasoning: `gpt-5.6-terra`, `xhigh`.
- Root plus reviewers: `019f8e1b-8326-7b82-b447-c7f86bea2dc3`, `019f8e29-810d-7922-a5e6-fc9bda681fee`, `019f8e2f-cc91-7721-89ef-3c51a072d2af`, `019f8e36-67cb-7dd2-8c34-a84c18d787f3`.
- Hidden score: 95/100.
- Tokens: 20,619,230.
- Duration: 2,517,661 ms.
- Reviewer protocol: three sequential `fork_turns:all` reviewers with fix/re-review follow-ups and a frozen three-round repair cap.
- Clean-context audit: four traces, zero external-path or grader-only tool reads.

## Paired result

| Metric | Frozen baseline | Candidate | Candidate delta |
|---|---:|---:|---:|
| Quality | 95 | 95 | 0 |
| Agent-tree tokens | 20,619,230 | 3,369,225 | -17,250,005 (-83.66%) |
| Wall time | 2,517,661 ms | 1,325,411 ms | -1,192,250 ms (-47.36%) |

The paired sample holds the task input tree, model, reasoning level and hidden evaluator constant. The treatment combines the iteration-4 skill changes: one tri-lens reviewer, `fork_turns:none`, fewer fix/re-review turns and narrower verification replay. One paired run establishes the observed effect for this case; repeated paired runs are required for a stability interval.
