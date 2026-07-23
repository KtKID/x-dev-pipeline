# Iteration 2 findings

## Outcome

| Metric | Frozen baseline | Iteration 1 | Iteration 2 | Iteration 2 vs baseline |
|---|---:|---:|---:|---:|
| Hidden quality | 30/100 | 95/100 | 100/100 | +70 points |
| Passed assertions | 6/20 | 19/20 | 20/20 | +14 |
| Critical assertions 1–19 | fail | fail | pass | pass |
| Agent-tree total tokens | 31,381,550 | 28,488,619 | 10,518,383 | -20,863,167 (-66.48%) |
| Wall time | 3,002.429 s | 2,856.016 s | 2,426.838 s | -575.591 s (-19.17%) |

The promotion gate passes: quality is at least 90, critical assertions 1–19 pass, and total tokens are at least 5% below baseline.

## Attribution

- Reviewer sessions fell from 18,198,326 tokens in iteration 1 to 963,020 in iteration 2, a 94.71% reduction. Each reviewer used one turn and one completion.
- Main-executor tokens fell from 10,290,293 to 9,555,363, a 7.14% reduction.
- Explicit original/minimal-config replay prevented the compatibility regression observed in the formal baseline.
- Literal `unit`, `smoke`, and `e2e` report labels closed the sole iteration-1 hidden evidence failure.
- Skill source size increased from 93,676 bytes to 96,716 bytes (+3.25%); the net gain came from execution-trace compression and higher first-pass instruction precision.

## Quality work retained

Three independent Q3 reviewers found and closed path-safety, streaming-prefix, early bad-magic, incomplete-HTTP, and nine test-evidence gaps. The final candidate passed 19 unit tests, 5 loopback Smoke/E2E tests, 11 pipeline verify blocks, and all 20 hidden assertions.

## Statistical boundary

This is one frozen case and one run per configuration on `gpt-5.6-sol`. The measured 66.48% reduction is an observed pilot result. Add at least two more self-contained cases and three repetitions per configuration before treating the percentage as a stable model-level estimate.
