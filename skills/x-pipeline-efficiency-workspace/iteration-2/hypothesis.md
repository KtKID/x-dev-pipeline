# Iteration 2：契约回放与单轮审查闭环

## Iteration 1 evidence

- Candidate reached 95/100 and reduced agent-tree total tokens by 9.22%.
- Q1 and Q2 received follow-up turns after their first final response.
- The only hidden failure was the missing literal `e2e` label in `dev-report.md`.
- Q2 found a compatibility regression introduced by direct access to newly added config fields.

## Changes

1. `x-qa-gate`: a reviewer's first final response terminates that role; the main executor closes candidates with focused counterexamples and the full verify command.
2. `x-dev`: record original executable contract samples, keep new config fields compatible by default, replay one original/minimal configuration through the real entry point, and label report evidence as `unit`, `smoke`, and `e2e`.
3. `x-fix`: preserve pre-fix minimal inputs and require both a focused counterexample and the original smoke/verify path.
4. `x-fix/references/qa-gate-fix-mode.md`: use the same evidence closure and terminal reviewer lifecycle.

## Expected result

- Hidden quality reaches at least 90; assertions 1–19 pass.
- Agent-tree total tokens stay at least 5% below the frozen formal baseline.
- Reviewer follow-up turns drop to zero.

## Attribution boundary

Case, prompt, model, input fixtures, evaluator, rubric, repository commit, and baseline measurement remain frozen. The candidate runs in a fresh workspace. Iteration 2 reuses the formal baseline artifact bit-for-bit and records that reuse explicitly.
