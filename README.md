<p align="center">
  <img src="assets/pic.png" alt="x-dev-pipeline" />
</p>

# x-dev-pipeline

[中文说明](./README_zh.md)

**Current release:** v0.3.0

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
5. Leaves artifacts ready for follow-up review and fix

Typical output looks like this:

```text
dev-pipeline/tasks/<task-name>/
├── README.md
├── changelog.md
├── dev-report.md
└── reports/
    ├── cr/cr-report-*.md
    ├── verify/verify-report-*.md
    ├── qa-gate/qa-gate-report-*.md
    ├── fix/fix-verify-*.md
    ├── fix/fix-r1-spec-*.md
    ├── fix/fix-r2-boundary-*.md
    └── fix/fix-r3-test-*.md
```

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

## Recommended Loop: Build → Review → Fix

For day-to-day development, this is the path I recommend most:

```text
/x-qdev -> /x-verify -> /x-qa-gate -> /x-fix
```

### `/x-qdev`

Quickly ship a small feature, tweak, or module.

### `/x-verify`

Gate ① fact verification. Re-runs the command list declared in `dev-report.md`, compares actual exit codes and key output fragments. **Fact-only verification.**

### `/x-qa-gate`

Gate ② pipeline quality gate. Serially dispatches 3 subagent reviewers: R1 spec correctness/conformance → R2 boundary correctness/coverage → R3 test integrity.

### `/x-fix`

Fix issues from verify / qa-gate / CR reports; uses routing rules to decide which node or report should be rechecked after a fix.

This path is great for:

- Small feature iterations
- UI interaction additions
- Module tweaks
- Localized optimizations
- Small-scale refactors

The point is to give even small tasks a sense of engineering discipline.

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
                 ^
              x-qdev
```

Independent audits run on demand outside the main flow:

- `/x-cr` — Bayesian software correctness investigation for known issues, modules, diffs, and PRs
- `/x-audit-perf` — performance audit (manual / milestone)
- `/x-audit-style` — style audit (manual / periodic)

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
- Always close with review and fix

## What Each Command Does

### `/x-qdev`

Lightweight quick development entry point. Best for small features, localized optimizations, and module tweaks. The recommended way to start.

### `/x-verify`

Gate ① fact verification. Reads the validation command list in `dev-pipeline/tasks/<task>/dev-report.md`, re-runs each command, compares actual vs declared exit codes and key output fragments. On any mismatch, generates `reports/verify/verify-report-*.md` and triggers x-fix.

### `/x-qa-gate`

Gate ② pipeline quality gate. Serially dispatches 3 subagent reviewers: R1 spec correctness/conformance → R2 boundary correctness/coverage → R3 test integrity. The aggregated report is written to `reports/qa-gate/qa-gate-report-*.md`.

### `/x-cr`

Bayesian software correctness investigation. It handles known user-reported issues and module correctness reviews through cause hypotheses, evidence updates, root-cause classification, and spec alignment. The report is written to `reports/cr/cr-report-*.md`.

### `/x-fix`

Fix by verify / qa-gate / CR reports. Under the pipeline gate, 4 routing rules decide which node a fix returns to; the fix-attempts counter is shared with verify/qa-gate at a 6-attempt cap.

### `/x-audit-perf` (independent audit)

Performance audit skill outside the main flow. Triggered manually or at milestones, outputs `reports/audit/audit-perf-*.md`.

### `/x-audit-style` (independent audit)

Style audit skill outside the main flow. Triggered manually or periodically, outputs `reports/audit/audit-style-*.md`.

### `/x-req`

Requirements analysis. Turns a development task into a clear, structured requirements spec.

### `/x-plan` (deprecated alias)

Compatibility entry that redirects to `/x-req`. The former planning output now lives in the x-req task README, `dev-checklist.md`, and `diagram.md`.

### `/x-dev`

Execute the plan. Development with a checklist, status tracking, and a changelog.

### `/x-spec`

System architecture planning. For larger projects, complex modules, architecture design, or long-term evolution tasks.

### `/x-multi-llm-align`

Two-subagent protocol, data-structure, and process alignment. Use it for contract review, implementation-side feedback, and multi-round agreement between two subagents representing separate implementation sides.

## Installation

This repo ships v0.3.0 plugin metadata for both hosts:

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
