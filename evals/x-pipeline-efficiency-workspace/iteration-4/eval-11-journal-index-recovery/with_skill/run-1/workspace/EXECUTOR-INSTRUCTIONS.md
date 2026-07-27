# Executor protocol

Work only inside this directory. Read `PROMPT.md` and complete the task end to end with the workspace skills and tools.

- Use `skills/x-spec3`, `skills/x-req3`, `skills/x-dev`, and `skills/x-verify` in order; follow risk routing into `skills/x-qa-gate` and `skills/x-fix`.
- Do not read any evaluator, rubric, answer, oracle, prior result, sibling run, or file outside this workspace.
- Create every required reviewer as a fresh child with `fork_turns: "none"`. Assemble its complete prompt once from workspace paths and facts. Never reuse, reactivate, follow up, or message a completed reviewer.
- Work autonomously and finish with artifact paths, verification results, and remaining risks.
