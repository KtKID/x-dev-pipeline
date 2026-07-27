# x-dev-pipeline token-efficiency optimization report

## Decision

The optimized skill set passes the promotion gate on the frozen `gpt-5.6-sol` pilot:

- Hidden quality: **100/100**, 20/20 assertions, critical assertions 1–19 all passed.
- Agent-tree total tokens: **10,518,383**, down **20,863,167 (-66.48%)** from the frozen baseline.
- Wall time: **2,426.838 seconds**, down **575.591 seconds (-19.17%)**.
- Initial target: score ≥90 and token reduction ≥5%.

## Measured progression

| Stage | Changed skills | Quality | Total tokens | Token delta vs baseline | Wall time |
|---|---|---:|---:|---:|---:|
| Frozen baseline | Pre-optimization snapshot | 30/100 | 31,381,550 | — | 3,002.429 s |
| Iteration 1 | `x-qa-gate` scheduling and wait discipline | 95/100 | 28,488,619 | -9.22% | 2,856.016 s |
| Iteration 2 | reviewer lifecycle + `x-dev`/`x-fix` contract replay and evidence labels | 100/100 | 10,518,383 | -66.48% | 2,426.838 s |

Iteration 2 reduced total tokens by 63.08% relative to iteration 1. Reviewer sessions fell from 18,198,326 to 963,020 tokens (-94.71%); main-executor tokens fell from 10,290,293 to 9,555,363 (-7.14%). Skill source grew from 93,676 to 96,716 bytes (+3.25%), so the net improvement comes from fewer repeated execution turns and stronger first-pass constraints.

## What changed

### `x-qa-gate`

- Q0/Q1 deliver directly, Q2 uses one combined reviewer, and Q3 uses three sequential independent reviewers.
- Each reviewer receives one complete sliced prompt and terminates after its first final response.
- Reviewer follow-up, reactivation, same-role repeat dispatch, interruption, and short polling are excluded from the flow.
- The main executor closes issues with focused counterexamples plus one complete verify replay.

### `x-dev`

- Records original executable contract samples before implementation: config fields, CLI, fixtures, wire/schema, and layout.
- Requires compatible defaults for new fields unless the spec defines an explicit migration.
- Replays an original or minimal input through a real entry point.
- Labels report evidence literally as `unit`, `smoke`, and `e2e`.

### `x-fix`

- Preserves pre-fix minimal inputs and original fixtures.
- Requires one focused regression plus the full original smoke/verify path.
- Keeps new config fields optional with compatible defaults unless migration is specified.
- Lets the main executor close evidence-backed issues; a new sliced reviewer is reserved for expanded files or public API changes.

### Metrics and audit tooling

- `tools/metrics.py` accepts repeated `--codex-session` arguments and sums an explicit executor/reviewer tree.
- Interrupted child sessions use their last cumulative token snapshot and are disclosed in `incomplete_ids`.
- Optional `benchmark-metadata.json` makes the benchmark report reusable beyond `x-spec2`.
- 28 metrics unit tests cover tree aggregation, duplicate IDs, incomplete children, privacy, pairing, grading consistency, and custom benchmark metadata.

## Eval design

The case is self-contained and multi-module:

- Python standard library only.
- Local files, subprocesses, and `127.0.0.1` loopback networking only.
- Modules cover streaming framing, upload resume/integrity, ASR→LLM→TTS orchestration, retry/timeout/error mapping, PCM downlink, concurrency isolation, device simulation, and mock services.
- The task also requires spec3, req3, development evidence, verify, Q3 review, and bounded fix flow.

The hidden evaluator has 20 deterministic assertions worth 5 points each. It copies the candidate backend into a temporary frozen fixture and independently starts the services. It checks real TCP behavior, files, concurrency, artifacts, and replayable pipeline evidence.

## Reproducibility and isolation

- Model: `gpt-5.6-sol`.
- Repository commit: `d6d9218bf5f819be9ade8521856309f6da9613c3`.
- Prompt file SHA-256: `bff313261b35c00b30041ff1bf5bc49c90829021c30ad55c6641b79a7458e6b5`.
- Executor prompt SHA-256: `sha256:4ad9f6916ba0c0dfe1d142bb9c7f42c6928969c93df1f9264c9560a417fedb5b`.
- Input tree SHA-256: `f78ecb7e3249101aa49a432dc9957e2c0949846bb13355814a949ed32c3da251`.
- Rubric SHA-256: `880f6077b7c86a1fc1f1fda4654d640afe0193e12abdd61b456322ac24341491`.
- Evaluator SHA-256: `6bc648083d9cdf1b47708b359fd95f72c20c7bb2941954adf39fb1ffd002d38c`.
- Baseline snapshot SHA-256: `c4f98677d4920dc943ac52250b032092582389a04115a0743f0cd46a88a5ae78`.
- Final snapshot SHA-256: `93a665d20e4b97cb9f6f1cb9a7a4584afa4178afe3eb277689a950dfbaba44ba`.

Token accounting uses the last cumulative Codex `token_count` for the active execution window in each explicitly enumerated session. The tree contains the main executor and three required Q3 reviewers. Infrastructure approval-review sessions are outside the executor tree for both configurations.

## Verification commands

```bash
python3 -m unittest test.test_metrics
python3 tools/metrics.py aggregate-spec2 evals/x-pipeline-efficiency-workspace/iteration-2
python3 evals/answers/voice-chain-end-to-end/evaluate.py \
  evals/x-pipeline-efficiency-workspace/iteration-2/eval-10-voice-chain-end-to-end/with_skill/run-1/workspace \
  --output evals/x-pipeline-efficiency-workspace/iteration-2/eval-10-voice-chain-end-to-end/with_skill/run-1/grading.json
git diff --check
```

The evaluator command needs permission to bind temporary loopback ports.

## Audit artifacts

- Protocol and artifact index: `evals/x-pipeline-efficiency-workspace/README.md`
- Iteration 1 hypothesis and findings: `iteration-1/hypothesis.md`, `iteration-1/findings.md`
- Iteration 2 hypothesis and findings: `iteration-2/hypothesis.md`, `iteration-2/findings.md`
- Machine-readable benchmark: `iteration-2/benchmark.json`
- Human benchmark: `iteration-2/benchmark.md`
- Static review page: `iteration-2/review.html`
- Raw grading, measurement, timing, transcript, workspace, and frozen snapshots remain under their iteration and snapshot directories.

## Confidence boundary and next gate

This result contains one case and one run per configuration. It proves the frozen pilot outcome and the measurement pipeline. It does not estimate model variance across tasks.

Use the next promotion gate as: median token reduction ≥10%, every run ≥90/100, all critical assertions pass, and no paired run regresses quality. Run at least three repetitions on this case plus two additional self-contained cases: a multi-module CLI/config migration and a stateful file/index recovery task. Keep the current 5% threshold as the rollback floor.
