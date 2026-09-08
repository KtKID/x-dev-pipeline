<p align="center">
  <img src="assets/pic.png" alt="x-dev-pipeline" />
</p>

# x-dev-pipeline

[中文说明](./README_zh.md)

**Current release:** v1.0.0

> An auditable development workflow for AI coding agents: requirement contracts, implementation evidence, deterministic checks, and risk-matched review.

`x-dev-pipeline` lets a spec own requirement scenarios, a dev-checklist own execution state, and a dev-report own verification conclusions. Every delivery can be traced, reconciled, and returned to the exact step that broke.

## Two working paths

Large work follows the four-step main line; small tasks close in a single document:

```text
Full flow:  x-spec → x-req → x-dev → x-verify (Gate ①) → x-qa-gate (Gate ②) → delivered
              write       split      line-by-line     delivery            quality
              requirements tasks      TDD              reconciliation      review

Small task: x-qdev (one task doc: requirements → tests → implementation → verification)
```

## Main line: spec → req → dev → verify

### 1. x-spec · Write requirements

Turn an agreed conversation into a purely functional spec: `docs/spec/<spec-name>/spec.md`.

- Fixed structure: title + overview + a `featNN` list, where each feat is a feature the user can name.
- Every feat carries Given/When/Then scenarios covering normal, boundary, and error cases; THEN describes only what the user can observe.
- No technical vocabulary anywhere (no "database", "API", "cache") — the user can read every line.
- Defaults chosen where the request was silent go into a closing "to confirm" list for one-shot review.

```markdown
## feat02: Search books by title

Users can quickly find books by searching for a title.

Scenario 1: Match found
- GIVEN the home page lists "Three-Body" and "Three-Body II"
- WHEN the user types "Three-Body" into the search box
- THEN both books are shown

Scenario 2: No match
- GIVEN no book on the home page contains "novel" in its title
- WHEN the user searches for "novel"
- THEN a "no matching books" message is shown
```

### 2. x-req · Split into tasks

Group feats into tasks, one development checklist per task: `docs/spec/<spec-name>/tasks/<task-name>/dev-checklist.md`.

- Task rows only reference scenarios as `featNN scenarioM` and never copy the GIVEN/WHEN/THEN — the spec stays the single source of truth.
- Row order is implementation order; no dependency graph. Merged together, all task rows cover every feat and every scenario in the spec.
- Risk column: rows touching auth, persistence, concurrency, or irreversible operations are marked `高:` (high) and demand real-chain verification.
- Below the table sits an affected-files tree (`U` add / `M` modify / `D` delete) that matches the "files involved" column one to one.

````markdown
| # | Task | Scenario refs | Files | Risk | Status |
|---|------|---------------|-------|------|--------|
| T1 | Group data structure and creation | feat01 sc.1-3 | src/groups.py | None | [ ] ⏳ |
| T2 | Join group via invite code | feat02 sc.1-5 | src/groups.py, src/join.py | None | [ ] ⏳ |

## Affected files

```text
reading-club/
├── src/groups.py        M  # group data structure, creation checks, invite codes
└── src/join.py          U  # add: join via invite code, nickname checks, limits
```
````

### 3. x-dev · Line-by-line TDD

x-dev executes a single task: from T1 downward, tests first, implementation second — never the reverse.

- Mark the current row `[ ] ▶️`, write a test for each scenario it references (the scenario's THEN is the assertion), watch it fail, implement until green, then mark `[x] 🟢`.
- Changes stay inside the affected-files tree — no drive-by edits. Rows marked `高:` require smoke-or-above real-chain verification.
- After every row is 🟢, run the task's full test suite plus one regression pass over existing tests.
- `dev-report.md` records conclusions only — all green or N 🔴, regression result, high-risk row coverage — never pasted test output.

### 4. x-verify · Gate ① delivery reconciliation

x-verify audits the delivery evidence chain. It does not re-run tests and does not judge implementation quality: with spec scenarios as the source of truth, it reconciles the checklist against the dev-report —

1. Valid refs: every `featNN scenarioM` exists in the spec;
2. Tree consistency: no off-tree files, no missing files;
3. Closed row state: every task row is `[x] 🟢` with no ⏳ / ▶️ / 🔴 leftovers;
4. High-risk rows: the dev-report declares real-chain verification;
5. Consistent conclusions: the dev-report matches the checklist state.

A full pass prints only a receipt. Problems are returned by origin — spec structure to x-spec, refs/tree to x-req, report contradictions to x-dev, known failures to x-fix.

```text
🛡️ Gate① verify ✅ · task-group-management · rows 3/3 🟢 · refs 8/8 valid · tree consistent · high-risk 1 (declared) · conclusions consistent
```

## Check flow: two gates

Gate ① (x-verify above) guards the consistency of the document evidence chain; Gate ② (x-qa-gate) guards the quality of the implementation itself. After verify passes, routing follows the task's risk:

| Risk | Typical scope | Gate ② route |
|------|---------------|--------------|
| Q0/Q1 | Single-file tweak / local feature or fix | Deliver directly, no reviewers |
| Q2 | New feature, multiple files, contract or state change | One lean tri-lens reviewer |
| Q3 | Security, irreversible writes, public API/schema, concurrency or state-machine change | One full tri-lens reviewer |

### Gate ② x-qa-gate: tri-lens review

A reviewer exhaustively checks three independent lenses in a single round; no lens can substitute for another:

- **q1-intent**: does the implementation align with user intent, acceptance scenarios, existing public contracts, and the declared scope;
- **q2-correctness**: illegal input, boundaries, failure paths, state transitions, concurrency, idempotency, resource cleanup;
- **q3-evidence**: do tests and verify evidence truly reach the changed paths, and could the assertions kill a broken implementation.

Reviewers are read-only and return problem candidates only (`lens` + `task` + `severity` P0/P1/P2 + `loc` + `msg`), never edits. The main agent double-checks each candidate, then registers them one by one through `xdev.py flag` into an issue ledger with `issue-<n>` IDs, downgrading checklist rows as it goes: P0/P1 become `[!] 🔴`; P2 is logged without blocking.

### Rework loop: flag → x-fix → incremental review

```text
Gate ①/② findings
   ├─ document inconsistency → returned to x-spec / x-req / x-dev by origin
   └─ P0/P1 → flag registers issues → x-fix batch-fixes them all at once
                → focused counterexample + one full verify re-run → incremental review
                → at most 3 rounds (fix-counter); on pass the checklist rises to [x] ✅
```

- x-fix processes the complete issue list in one batch — no drip-feeding; every P0 solidifies one re-runnable counterexample.
- The main agent closes issues with regression evidence and never sends fixes back to the original reviewer.
- When a fix expands into new files or public API signatures, a trimmed reviewer checks only the new boundary.
- Gate ① and Gate ② share the three-round fix counter; it resets to zero after a final quality-review pass.

## x-qdev: single-doc loop for small tasks

Concrete, well-scoped single changes — "add a search box", "fix the export bug" — skip the four-step main line. x-qdev first searches `docs/spec/*/spec.md` for an owning spec: if found, the task doc lives at `docs/spec/<spec-name>/tasks/task-<task-name>.md` and references its feat; if the user confirms no spec is needed, it creates a standalone doc at `docs/task/task-<task-name>.md`.

It then completes four sections in **one task document** — the document is the deliverable:

1. **① Requirements** — functional language: direction, boundaries (do / don't), invariants that must not break;
2. **② Test cases** — written first and failing at this point: unit + smoke, e2e as needed, boundaries mandatory;
3. **③ Implementation** — steps and files involved, turning ② green;
4. **④ Verification results** — real pasted output plus invariant regression results; the four conclusion checkboxes must match the actual content.

Before delivery it runs a five-item self-check gate on the document itself: structure, valid refs, closed coverage, consistent conclusions, boundary audit — no other skill required. Out-of-scope tasks (multi-module, requirements still open, high risk) are redirected to the full x-spec + x-req flow.

```text
✅ x-qdev done · task-todo-search · tests 5/5 passed · invariant regression passed · files changed 1
```

## Optional: adversarial spec risk review

A spec package can pass an independent risk gate before task decomposition (`x-spec → x-adversarial-risk → x-req`):

x-spec records 1–5 complexity and importance scores; `x-bug2rag/scripts/home_corpus.py` initializes `~/.x-dev-pipeline/rag/` and copies the plugin seed corpus to `risk-catalog.md` as a separate operation. Risk review and bug ingestion share that user-global corpus across projects, and an explicit caller path can override it. `x-adversarial-risk` performs one Top5 vector lookup per budget, using retrieved experience to build minimal counterexamples that distinguish a correct implementation from a common wrong one, and adds scenarios with `adversarial-review` provenance to the spec. x-req blocks decomposition while the versioned spec's review status is still pending.

## Commands

| Command | Purpose |
|---------|---------|
| `/x-spec` | Write requirements as a purely functional spec (feats + GWT scenarios) |
| `/x-req` | Split feats into tasks and generate scenario-ref dev-checklists |
| `/x-dev` | Execute one task line by line with TDD and write a conclusions-only dev-report |
| `/x-verify` | Gate ①: reconcile the delivery evidence chain and triage by origin |
| `/x-qa-gate` | Gate ②: tri-lens quality review and flag issue ledgers |
| `/x-qdev` | Single-doc loop for small tasks: requirements → tests → implementation → verification |
| `/x-fix` | Batch-fix the issue list found by verify, gates, or CR |
| `/x-cr` | Investigate a reported correctness issue, module, diff, or PR |
| `/x-adversarial-risk` | Challenge a spec's risk assumptions and add traceable counterexample scenarios |
| `/x-multi-llm-align` | Align a protocol, data structure, or process across agents |
| `/x-audit-perf` | Run an independent performance audit |
| `/x-audit-style` | Run an independent style audit |
| `/x-audit-arch` | Run an independent architecture audit |

## Deterministic engine

`skills/x-dev/scripts/xdev.py` is the thin unified CLI for mechanical rules outside skill prose.
Its engines live with their owning skills: package validation in
`skills/x-spec/scripts/validator.py`, task planning in `skills/x-req/scripts/req.py`, verification
in `skills/x-verify/scripts/verify.py`, and QA issue transactions in
`skills/x-qa-gate/scripts/flag.py`:

```text
validate [pkg...]                 validate specs, changes, and task contracts
status <task-dir> [--json]        parse checklist progress
graph <task-dir> [--json]         calculate ready work and parallel batches
instructions <artifact> --task    return task artifact instructions
scaffold <task-dir>               create only missing task artifacts
verify <task-dir> [--json]        execute evidence and reconcile Scenarios
flag <task-dir> --task T2,T3 --severity P0 --loc src/a.py:10 --msg "..." [--new-round] [--json]
```

Task commands only accept `docs/spec/<spec-name>/tasks/<task-name>/`. Historical
`dev-pipeline/tasks/` directories remain readable artifacts and have no runtime validation or
orchestration support.

As of v1.0.0, Gate ① is the x-verify skill's delivery reconciliation; the verify engine remains for legacy `spec_version: 3` contract packages, while the v6 chain relies on `status` (progress) and `flag` (issue ledger). `flag` coordinates the issue ledger with the single durable `dev-checklist.md` per task through a persistent transaction: unchanged content creates no temp file, a recovered pending transaction returns `recovered:true`, and the caller retries the intended issue.

## x-spec2 pilot metrics

`skills/pipeline-efficiency-benchmark/scripts/metrics.py` records a completed x-spec2 eval from either one explicit Codex rollout JSONL or a saved subagent completion notification. The minimum measurement contains the execution source ID, model, repository SHA, prompt hash, duration, real provider total tokens, and independently graded expectation pass rate.

```bash
python3 skills/pipeline-efficiency-benchmark/scripts/metrics.py extract \
  --timing <run-dir>/timing.json \
  --metadata <run-dir>/eval_metadata.json \
  --grading <run-dir>/grading.json \
  --output <run-dir>/measurement.json

python3 skills/pipeline-efficiency-benchmark/scripts/metrics.py aggregate-spec2 deprecated/x-spec2-workspace/iteration-2
```

Exit 0 means extraction or aggregation succeeded; exit 1 means a readable run violates the fresh-session, rubric-isolation, or paired-comparison boundary; exit 2 means usage, IO, JSON, or schema failure. A one-pair result is marked `pilot: true`: it proves the measurement flow and remains insufficient for a stable skill-effect estimate.

## Installation

The repository contains manifests for Claude Code and Codex:

```text
.claude-plugin/plugin.json
.claude-plugin/marketplace.json
.codex-plugin/plugin.json
.agents/plugins/marketplace.json
```

For Claude Code:

```bash
git clone https://github.com/KtKID/x-dev-pipeline.git ~/.claude/plugins/x-dev-pipeline
claude plugin marketplace add ~/.claude/plugins/x-dev-pipeline/.claude-plugin/marketplace.json
claude plugin install x-dev-pipeline@x-dev-pipeline --scope user
```

For Codex, add the repo entry from `.agents/plugins/marketplace.json` to your marketplace, restart Codex, and install `x-dev-pipeline` from the local plugin directory.

## Status markers

| Marker | Meaning |
|--------|---------|
| `[ ] ⏳` | Not started |
| `[ ] ▶️` | In progress |
| `[!] 🔴` | Verification failed / P0-P1 issue downgrade |
| `[x] 🟢` | Verification passed |
| `[x] ✅` | Quality review passed |

## License

MIT
