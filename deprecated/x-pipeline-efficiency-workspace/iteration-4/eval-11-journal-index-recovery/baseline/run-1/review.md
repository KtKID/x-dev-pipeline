# Terra xhigh baseline review

## Verdict

- Quality target: pass, `95/100 >= 90`.
- Clean-context requirement: pass; four session traces contain zero tool calls outside the isolated workspace and zero grader-only reads.
- Model constraint: pass; root and all three reviewers used `gpt-5.6-terra` with `xhigh`.
- Baseline gate status: blocked after the frozen three-round fix cap, with two P1 test-assertion gaps retained.
- Hidden critical gate: fail on the dev-report E2E disposition requirement.

## Candidate comparison

| Run | Quality | Agent-tree tokens | Wall time | Reviewer design |
|---|---:|---:|---:|---|
| Frozen baseline | 95 | 20,619,230 | 2,517,661 ms | 3 sequential reviewers, `fork_turns:all` |
| Latest candidate | 95 | 3,369,225 | 1,325,411 ms | 1 tri-lens reviewer, `fork_turns:none` |
| Candidate delta | 0 | -17,250,005 (-83.66%) | -1,192,250 ms (-47.36%) | 2 fewer reviewer sessions |

The paired run uses the same task input tree, Terra model, xhigh reasoning and hidden evaluator. It measures the combined effect of the skill changes, including consolidated review, isolated reviewer context, fewer fix/re-review turns and narrower verification replay.

## Baseline token distribution

| Role | Tokens | Share |
|---|---:|---:|
| Main | 8,307,600 | 40.29% |
| Q1 intent | 2,389,925 | 11.59% |
| Q2 correctness | 4,044,696 | 19.62% |
| Q3 evidence | 5,877,009 | 28.50% |

Reviewers consumed 59.71% of the baseline tree. Each reviewer inherited the growing parent trace, including large full-workspace diffs returned after patches, then re-entered after its fix for incremental review. Cached input reached 19,493,120 tokens; this confirms repeated context replay as the dominant token source.

## What the baseline review added

The sequential reviewers found and closed three meaningful persistence-integrity gaps: compact replace-window recovery, semantic snapshot consistency and logical corruption classification. R3 also made the public tests harder to game. The latest candidate retained the same hidden score with one tri-lens reviewer, showing that consolidated lenses preserved the tested quality while removing repeated context and reviewer setup.

The next optimization decision should use the latest candidate as the working version and keep a deterministic dev-report E2E disposition rule so the 95 score can reach the full critical gate.
