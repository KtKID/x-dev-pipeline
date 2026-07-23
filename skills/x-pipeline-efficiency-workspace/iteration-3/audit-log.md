# Iteration 3 audit log

## Frozen protocol

- model: `gpt-5.6-sol`
- repository SHA: `1a461b9852180e74b983f4a933e7dd45f2855a57`
- repetitions: two fresh runs per case and configuration
- execution: serial top-level executors with `fork_turns:none`
- isolation: every reviewer is a fresh child inside its executor task subtree
- scoring: frozen evaluator per case; evaluator revisions are recorded in `grader-revision.md`
- token source: final cumulative telemetry from every completed session in the executor tree
- formal scope: the newly added self-contained `journal-index-recovery` case, two fresh runs per configuration

## Protocol repairs

- Candidate snapshot metadata originally recorded `0748d3...`. An independent read-only audit recomputed the frozen snapshot and both candidate workspaces with the manifest's own command as `bc0437...`. The run trees were byte-consistent; metadata and manifest were corrected without changing evaluated skill files.
- Candidate `changed_files` originally omitted `skills/x-fix/references/qa-gate-fix-mode.md`; the list now records all six files that differ from the frozen baseline.
- The evaluator rejected representation choices that the public task did not constrain. These checks were generalized before the second baseline run, all existing outputs were regraded with the frozen evaluator, and the original scores remain preserved. This iteration is therefore marked `protocol-repaired-before-baseline-run-2`.

## Valid formal runs

| Case | Configuration | Run | Score | Critical | Total tokens | Status |
|---|---|---:|---:|---|---:|---|
| journal-index-recovery | candidate | 1 | 100 | pass | 6,606,699 | valid |
| journal-index-recovery | candidate | 2 | 100 | pass | 9,427,504 | valid |
| journal-index-recovery | baseline | 1 | 95 | fail | 19,136,529 | valid |
| journal-index-recovery | baseline | 2 | 95 | fail | 25,090,716 | valid; pipeline blocked after QA fix limit |

Journal candidate median: `8,017,101.5` tokens.
Journal baseline median: `22,113,622.5` tokens.
Median token delta: `-14,096,521` tokens (`-63.75%`).

## Exclusions

| Attempt | Reason | Evidence |
|---|---|---|
| journal baseline run 2, first attempt | reused a pre-existing voice reviewer after agent-pool contention | `invalid-attempts/iteration-3/eval-11-journal-baseline-run-2-contaminated/invalid-reason.md` |

Excluded attempts remain available for audit and never enter grading, token aggregation, or promotion decisions.

## Matrix status

- Formal journal-index-recovery matrix: complete, two fresh candidate and two fresh baseline runs

## Promotion decision

- Candidate quality: `100/100` in both runs; every critical assertion passed.
- Baseline quality: `95/100` in both runs; both missed the literal unit/smoke/e2e evidence-label assertion.
- Candidate mean/median tokens: `8,017,101.5`.
- Baseline mean/median tokens: `22,113,622.5`.
- Token reduction: `63.75%`, exceeding the predeclared `10%` gate.
- Mean wall-time reduction: `63.06%`.
- Decision: promote the batched tri-lens candidate for this task family. Do not generalize the exact percentage beyond comparable self-contained local multi-module tasks without another case replication.
