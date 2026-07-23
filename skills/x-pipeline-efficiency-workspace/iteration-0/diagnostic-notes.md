# Diagnostic baseline notes

Run: `eval-10-voice-chain-end-to-end/without_skill/run-1`

- Hidden score after evaluator isolation fix: 100/100; 20/20 assertions passed.
- Pipeline result: 18/18 automated tests, Gate 1 13/13, Gate 2 P0=0/P1=0, three non-blocking P2.
- Explicit agent-tree total: 15,273,913 tokens; wall time 2,800,111 ms.
- Agent tree: one root executor plus q1-intent, interrupted q2-correctness, q2 retry, and q3-evidence.
- Visible waste: short wait polling repeatedly recharged the root context; messages interrupted reviewer turns; severity/fix follow-ups reused full reviewer context; post-review fixes used many one-command turns.
- Validity: diagnostic only. A root status message reached the running executor and its q1 reviewer, so the sample is excluded from promotion comparison.

Formal paired runs live in `iteration-1/eval-10-voice-chain-end-to-end/` and receive no root messages while active.
