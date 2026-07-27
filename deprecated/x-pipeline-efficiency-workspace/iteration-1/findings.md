# Iteration 1 findings

## Outcome

| Metric | Baseline | Candidate | Delta |
|---|---:|---:|---:|
| Hidden quality | 30/100 | 95/100 | +65 points |
| Passed assertions | 6/20 | 19/20 | +13 |
| Agent-tree total tokens | 31,381,550 | 28,488,619 | -2,892,931 (-9.22%) |
| Wall time | 3,002.429 s | 2,856.016 s | -146.413 s (-4.88%) |

The user gate is met: quality is at least 90 and total token reduction is at least 5%.

## Improvement attribution

- Consolidated QA scheduling reduced total agent-tree tokens by 9.22% while preserving all three risk roles.
- Q2 review found and fixed the baseline's original-config compatibility regression, raising hidden quality from 30 to 95.
- Complete agent-tree accounting includes main, Q1, Q2, and Q3 Codex sessions; guardian review sessions remain outside the executor tree.

## Remaining audit findings

- The iteration-1 reviewer wording allowed Q1 and Q2 follow-up turns. Iteration 2 makes the one-turn lifecycle terminal after the first final response.
- Assertion 19 requires an explicit `e2e` label in `dev-report.md`. Iteration 2 adds literal `unit`, `smoke`, and `e2e` report labels.
- One paired sample establishes this observed result. Repeated seeds or cases are required to estimate variance and stable model-level gain.
