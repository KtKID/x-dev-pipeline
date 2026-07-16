<p align="center">
  <img src="assets/pic.png" alt="x-dev-pipeline" />
</p>

# x-dev-pipeline

[中文说明](./README_zh.md)

**Current release:** v0.3.6

> A recordable, auditable, and reviewable workflow framework for AI-assisted development.

Most of the time, AI coding agents can write code, yet they drift off track mid-task and leave behind little useful process information:

- Why was this change made?
- What exactly was modified?
- What decisions were made along the way?
- Which issues have already been addressed?
- Which risks are still unresolved?

When someone picks up the work later, they're forced to re-ask, re-read, and re-analyze from scratch.

`x-dev-pipeline` exists to solve this problem.

It turns throwaway, chat-style development into an engineering process: get things done, leave a clear trail, and keep reviewing, fixing, and iterating.

> Battle-tested on Claude Code. Ships with Claude Code and Codex plugin manifests.

## Start with `/x-qdev`

If this is your first time using this repo, start with the lightweight path.

Try `/x-qdev` first:

```bash
/x-qdev add dark mode toggle to the settings page
```

It's best for:

- Adding a small feature to a page
- Making a localized optimization
- Modifying a small module
- Filling in an interaction detail
- Running a lightweight validation

What you get is a process closer to real development:

1. AI understands the task scope
2. Creates a task directory
3. Generates a task description and dev checklist
4. Implements items one by one, recording key changes
5. Closes the task with targeted validation and a DoD evidence matrix
6. Adds one combined reviewer for medium risk and promotes high-risk work to the full pipeline

Typical output looks like this:

```text
dev-pipeline/tasks/<task-name>/
├── README.md
├── changelog.md
└── dev-report.md
```

`dev-report.md` records risk level, the actual diff, real validation results, and evidence for every DoD item. Verify, QA-gate, and fix reports appear when the user selects the full gate or the task is promoted.

This is the best way to experience `x-dev-pipeline` for the first time:

**Complete a small feature smoothly, and leave an engineering trail behind.**

## Reliability Over One-Off Code Generation

Common problems when using AI coding agents directly:

- The task is small, but the process is messy
- Changes are made, but no clear record is left
- Reviews are ad-hoc and inconsistent in quality
- Work ends after the fix, with no feedback loop
- The next person picking it up has no idea what happened before

`x-dev-pipeline` gives AI coding work a stable, traceable, engineering-grade rhythm:

**How to make AI work at a more stable, traceable, engineering-grade pace.**

## Recommended Daily Loop: Build → Validate → Close with Evidence

For day-to-day development, this is the path I recommend most:

```text
/x-qdev -> targeted validation -> DoD evidence closure -> complete
                                      ├─ Q2: one combined reviewer
                                      └─ Q3: promote to the full pipeline
```

### `/x-qdev`

Quickly ship a small feature, tweak, or module. Q0/Q1 closes in the main agent using the original request, actual diff, and real validation evidence.

### `/x-verify`

Gate ① fact verification for the x-dev full pipeline, or when the user explicitly sends qdev through the full gate.

### `/x-qa-gate`

Gate ② pipeline quality gate for Q3 and full development tasks. Risk-routed: one unified reviewer (RC) by default; high-risk changes run R1 spec, R2 boundary, and R3 test-integrity review serially.

### `/x-fix`

Fix issues from verify / qa-gate / CR reports; batch-fixes the full findings list in one round, then hands back for an incremental re-review.

The default qdev path is great for:

- Small feature iterations
- UI interaction additions
- Module tweaks
- Localized optimizations
- Small-scale refactors

The point is to give small tasks direct, traceable correctness evidence with less context overhead.

## What You Get

With `x-dev-pipeline`, you get a set of artifacts you can continue using, tracking, and reviewing.

Typically, you'll get:

- Task directory
- Task description
- Dev checklist
- Changelog
- Code review report
- Fix report or fix note

These artifacts mean:

- **Recorded**: you know what changed
- **Auditable**: you know why it changed
- **Reviewable**: you can pick up where you left off
- **Retrospectable**: you can look back at decisions and issues

This is one of the core values of this repo:

**Get things done and turn the development process into truly traceable engineering assets.**

## For Complex Tasks, Use the Full Pipeline

`x-dev-pipeline` includes `/x-qdev` and the full spec-to-gate pipeline.

For more complex tasks, it provides a full development flow:

```text
x-spec -> x-req -> x-dev -> x-verify -> x-qa-gate -> x-fix

x-qdev -> targeted validation -> DoD evidence closure
                                      ├─ Q2 combined reviewer
                                      └─ Q3 promotion to the full pipeline above
```

Independent audits run on demand outside the main flow:

- `/x-cr` — Bayesian software correctness investigation for known issues, modules, diffs, and PRs
- `/x-audit-perf` — performance audit (manual / milestone)
- `/x-audit-style` — style audit (manual / periodic)
- `/x-audit-arch` — architecture audit: architecture consistency + single source of truth (manual / milestone / post-refactor)

Alignment utilities also run on demand:

- `/x-multi-llm-align` - two-subagent protocol, data-structure, and process alignment

Think of it this way:

### Small Tasks

Start directly with `/x-qdev` — fast to complete, fast to ship.

### Medium Tasks

Start with `/x-req -> /x-dev` — when you need clear requirements and an execution plan.

### Large Tasks

Walk the full pipeline — for system design, complex modules, and architecture-level changes.

Recommended shape:

- Keep it light for small things
- Keep it solid for big things
- Close every task with evidence; use review and fix for high-risk work

## What Each Command Does

### `/x-qdev`

Lightweight quick development entry point. It preserves the original request, routes work across Q0-Q3 risk levels, runs targeted validation, and builds a DoD evidence matrix. Q0/Q1 closes in the main agent, Q2 uses one combined reviewer, and Q3 promotes to the full pipeline.

### `/x-verify`

Gate ① fact verification. Reads the validation command list in `dev-pipeline/tasks/<task>/dev-report.md` plus the Smoke/E2E acceptance cases in the task README, re-runs each command, compares actual vs declared exit codes and key output fragments (manual cases go to a pending-manual-acceptance list). On any mismatch, generates `reports/verify/verify-report-*.md` and triggers a batch x-fix.

### `/x-qa-gate`

Gate ② pipeline quality gate. Risk-routed: the default lane dispatches one unified reviewer (RC) that exhaustively lists all spec / boundary / test-integrity findings in a single round; the high-risk lane serially dispatches R1 spec correctness → R2 boundary coverage → R3 test integrity. The aggregated report is written to `reports/qa-gate/qa-gate-report-*.md`, and a graded findings receipt is posted in the conversation.

### `/x-cr`

Bayesian software correctness investigation. It handles known user-reported issues and module correctness reviews through cause hypotheses, evidence updates, root-cause classification, and spec alignment. The report is written to `reports/cr/cr-report-*.md`.

### `/x-fix`

Fix by verify / qa-gate / CR reports. Under the pipeline gate, x-fix batch-fixes the full findings list in one round (every P0 fix must leave a re-runnable counter-example), then hands back for an incremental re-review; the fix-attempts counter counts batch rounds, shared with verify/qa-gate at a 3-round cap.

### `/x-audit-perf` (independent audit)

Performance audit skill outside the main flow. Triggered manually or at milestones, outputs `reports/audit/audit-perf-*.md`.

### `/x-audit-style` (independent audit)

Style audit skill outside the main flow. Triggered manually or periodically, outputs `reports/audit/audit-style-*.md`.

### `/x-audit-arch` (independent audit)

Architecture audit skill outside the main flow. Focuses on architecture consistency (module ownership, layering, boundary-class reuse, naming semantics, dependency health) and single source of truth (duplicated schemas/enums/defaults/rules that have drifted). Triggered manually, at milestones, or after refactors; outputs `reports/audit/audit-arch-*.md`.

### `/x-req`

Requirements analysis. Turns a development task into a clear, structured requirements spec.

### `/x-plan` (deprecated alias)

Compatibility entry that redirects to `/x-req`. The former planning output now lives in the x-req task README, `dev-checklist.md`, and `diagram.md`.

### `/x-dev`

Execute the plan. Development with a checklist, status tracking, and a changelog.

### Orchestration engine (`tools/xdev.py`)

A deterministic tool layer (the "legislative layer") that backs the skills with machine-checkable mechanics instead of prose. Three subcommands:

- **`xdev.py validate [pkg...]`** — structural validation of spec/change packages (rules V0–V7: file completeness, link safety, Requirement/Scenario structure, delta markers, task backrefs, module consistency, status vocab).
- **`xdev.py status <task-dir> [--json]`** — parse a task's `dev-checklist.md`, resolve each task to an engine state (`done`/`todo`/`blocked`) from a token+emoji dual-track status column, and emit a progress JSON. Pure-emoji legacy checklists degrade automatically.
- **`xdev.py graph <task-dir> [--json]`** — Kahn topological sort over the dependency column, emitting `ready` / `blocked` / `order` / `parallel_batches`. Detects dependency cycles (exit 1, lists cycle nodes).

`/x-dev` reads `status` + `graph` before dispatching sub-agents, so "what to run next" and "what can run in parallel" are computed rather than inferred from prose. Exit codes: 0 ok · 1 findings or cycle · 2 usage/IO.

### `/x-spec`

System architecture planning. For larger projects, complex modules, architecture design, or long-term evolution tasks.

### `/x-multi-llm-align`

Two-subagent protocol, data-structure, and process alignment. Use it for contract review, implementation-side feedback, and multi-round agreement between two subagents representing separate implementation sides.

## Installation

This repo ships v0.3.6 plugin metadata for both hosts:

```text
.claude-plugin/plugin.json          # Claude Code plugin manifest
.claude-plugin/marketplace.json     # Claude Code local marketplace
.codex-plugin/plugin.json           # Codex plugin manifest
.agents/plugins/marketplace.json    # Codex repo-scoped marketplace
```

### Quick Install (Recommended)

Installs the Claude Code plugin from the GitHub `main` branch:

```bash
curl -fsSL https://raw.githubusercontent.com/KtKID/x-dev-pipeline/main/install.sh | bash
```

### Claude Code (Manual)

```bash
git clone https://github.com/KtKID/x-dev-pipeline.git ~/.claude/plugins/x-dev-pipeline
```

Register the local marketplace:

```bash
cd ~/.claude/plugins/x-dev-pipeline
claude plugin marketplace add ./.claude-plugin/marketplace.json
```

Install the plugin:

```bash
claude plugin install x-dev-pipeline@x-dev-pipeline --scope user
```

### Codex

This repo ships a repo-scoped Codex marketplace at `.agents/plugins/marketplace.json` and a Codex plugin manifest at `.codex-plugin/plugin.json`.

Open the repo in Codex and Local can discover `x-dev-pipeline` directly from the workspace.

Clone to the local plugin directory:

```bash
mkdir -p ~/.codex/plugins
git clone https://github.com/KtKID/x-dev-pipeline.git ~/.codex/plugins/x-dev-pipeline
```

On Windows, sync the current checkout into Codex and refresh the user-level marketplace files with:

```powershell
./install-codex.ps1
```

The script updates:

- `~/.agents/plugins/marketplace.json`
- `~/.codex/marketplace.json`
- `~/.codex/plugins/marketplace.json`

Directory layout:

```text
~/
├── .agents/
│   └── plugins/
│       └── marketplace.json
└── .codex/
    ├── marketplace.json
    └── plugins/
        ├── marketplace.json
        └── x-dev-pipeline/
```

Codex local plugin installation uses the interactive plugin directory after the user-level marketplace files contain the local marketplace entry:

```bash
codex
/plugins
```

Manual marketplace entry:

```json
{
  "name": "local-plugins",
  "interface": {
    "displayName": "Local Plugins"
  },
  "plugins": [
    {
      "name": "x-dev-pipeline",
      "source": {
        "source": "local",
        "path": "./.codex/plugins/x-dev-pipeline"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

Reference example:

```text
examples/codex-marketplace.json
```

Path rules:

- `source.path` is resolved relative to the root directory where `~/.agents/plugins/marketplace.json` lives
- For personal marketplaces, the common pattern in the official docs is `./.codex/plugins/<plugin-name>`
- The repo-scoped marketplace in this repo uses `../..` so Codex can resolve the plugin root from `.agents/plugins/marketplace.json`

If `~/.agents/plugins/marketplace.json` already exists, append the plugin entry above to the `plugins` array and preserve existing plugins. Save, restart Codex, then run:

```bash
codex
/plugins
```

Find `x-dev-pipeline` in the plugin directory and install it. (You may need to switch to Local.)

After installation, try this to get started:

```bash
/x-qdev add dark mode toggle to the settings page
```

## Who Is This For

This repo is especially suited for:

- Developers using AI coding agents daily who want a more disciplined process
- People who want AI development to feel like engineering collaboration
- Anyone who wants every change to leave a clear record
- Those who want review and fix to form a real feedback loop
- People looking to build a stable, repeatable development rhythm

## Current Fit Boundaries

This repo currently fits teams and individuals who accept a lightweight workflow layer. A different tool may fit better for:

- A zero-config, plug-and-play general-purpose coding assistant
- A heavy enterprise process management platform

## Adapting to Other Tools

`x-dev-pipeline`'s workflow design works across AI coding tools. Claude Code has the deepest validation today, and the core principles apply to all AI coding agents:

- Small tasks should ship fast
- Every change should be recorded
- Every decision should be traceable
- Reviews should leave written artifacts
- Fixes should close the loop

If you're using another tool (Cursor, Codex, Windsurf, Cline, etc.), just tell your AI:

> "Keep the x-dev-pipeline workflow intact, but adapt it to Cursor (or whatever tool you're using)."

The AI will adjust task directory locations and trigger mechanisms based on the target tool's conventions, while preserving the full workflow chain.

> **Note**: The default task output directory in the skills is `dev-pipeline/tasks/`. During adaptation, the AI may ask whether you'd like to change it to a different path (e.g., `.codex/tasks/`) — just confirm based on your setup.

## Shared Status Markers

All skills share a unified task status system:

| Symbol | Status | Description |
|--------|--------|-------------|
| ⏳ | Not started | Waiting to be picked up |
| ▶️ | In progress | Currently being worked on |
| 🟡 | Pending test | Development done, awaiting verification |
| 🔴 | Test failed | Needs fix |
| 🟢 | Test passed | Verified, awaiting review confirmation |
| ✅ | Completed | Confirmed after review |

### Priority Levels

| Priority | Description |
|----------|-------------|
| P0 | Blocker — must be addressed immediately |
| P1 | Important — must be completed |
| P2 | Enhancement — can be deferred |

## Core Philosophy

The goal is development that stays:

**Structured for complex work, lightweight for simple tasks.**

Use it as a workflow toolkit you can pick from based on task complexity.

## Roadmap

We'll continue strengthening these areas:

- Smoother `/x-qdev` first-time experience
- Clearer task artifact structure
- Stronger review / fix feedback loops
- More real-world usage examples
- Better multi-language, multi-stack support
- Stronger Claude Code and Codex adapter polish
- Official adapters for more tools (Cursor, Windsurf, etc.)

## License

MIT
