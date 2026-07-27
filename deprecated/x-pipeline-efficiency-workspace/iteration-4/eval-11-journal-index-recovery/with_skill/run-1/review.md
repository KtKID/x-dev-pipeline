# Terra xhigh run review

## Verdict

- Quality target: pass, `95/100 >= 90`.
- Token target: observed pass against the prior candidate measurements.
- Critical gate: fail, because the dev-report omitted the literal E2E disposition required by the hidden evidence check.
- Model constraint: pass; root and reviewer both used `gpt-5.6-terra` with `xhigh`.
- Reviewer isolation: pass; one reviewer, `fork_turns:none`, one completed turn.

## Comparison

| Run | Model | Quality | Agent-tree tokens |
|---|---|---:|---:|
| iteration-3 candidate run 1 | gpt-5.6-sol | 100 | 6,606,699 |
| iteration-3 candidate run 2 | gpt-5.6-sol | 100 | 9,427,504 |
| iteration-4 run 1 | gpt-5.6-terra | 95 | 3,369,225 |

The Terra run used 49.00% fewer tokens than the lower-token prior candidate run and 57.97% fewer than the prior candidate median. This is an observed cross-model result; the model change, run variance, x-dev cleanup and reviewer isolation all contribute, so the percentage does not isolate a single causal effect.

## What improved

1. `fork_turns:none` eliminated reviewer inheritance: the reviewer consumed 146,135 tokens, 4.34% of the tree.
2. One tri-lens reviewer caught a real P1 snapshot invariant breach while staying within a single isolated turn.
3. The main agent closed the P1 with one focused counterexample plus one complete Gate① replay.
4. Total tree tokens cleared the requested 5% reduction margin by a wide observed margin.

## Remaining issue

The report contract needs one deterministic E2E disposition line even when E2E is intentionally omitted. The current run kept that decision in spec.md, while the hidden evaluator checks dev-report.md directly. The next skill change should make x-dev copy the unit/smoke/E2E evidence disposition into dev-report without adding another model turn.
