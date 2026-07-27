# Execution transcript

## Isolation

- Fresh executor context: `fork_turns:none`.
- Baseline snapshot: `baseline-20260723`.
- Executor inputs excluded evaluator, rubric, oracle, prior results and sibling runs.

## Execution shape

- Main executor produced spec3, req3, implementation, tests and verify evidence.
- Q3 used three reviewer sessions. q1 ran two turns, q2 ran two turns, and q3 ran four turns because fixes were sent back for incremental review.
- Final executor suite: 19/19 tests; `xdev verify`: 16/16 scenarios; Q3 P0/P1: zero after four repair batches.

## Hidden grading

- Final frozen evaluator: 95/100, 19/20 assertions.
- Assertion 19 failed because dev-report lacks literal `unit`, `smoke`, and `e2e` evidence labels even though its commands replay successfully.
- The representation-only full-path failure from the first grade is preserved in `grading.pre-path-revision.json` and excluded from formal scoring.

## Cost shape

- Main: 12,630,701 tokens.
- q1-intent: 1,262,201 tokens across two turns.
- q2-correctness: 1,222,687 tokens across two turns.
- q3-evidence: 4,020,940 tokens across four turns.
- Agent-tree total: 19,136,529 tokens; wall time: 4,760.751 seconds.
