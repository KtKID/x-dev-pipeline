# x-dev-pipeline efficiency audit

## Objective

Optimize the editable pipeline skills for a high-capability executor model while preserving implementation quality. Promotion requires a hidden score of at least 90/100 and an agent-tree total-token reduction of at least 5% from the frozen baseline.

## Evaluation contract

- Case: `evals/problems/voice-chain-end-to-end/PROMPT.md`
- Inputs: `cases/voice-chain/task/` and `cases/voice-chain/fixture/`
- Runtime boundary: Python standard library, local files, local subprocesses, and loopback networking
- Complexity: upload framing/resume/integrity, ASR-LLM-TTS orchestration, PCM downlink, concurrency isolation, specs, tasks, development evidence, verification, QA, and fix flow
- Quality: 20 frozen hidden assertions, 5 points each
- Cost: cumulative Codex telemetry summed across the explicitly enumerated executor agent tree
- Pairing keys: prompt hash, model, repository commit, input tree, evaluator hash, rubric hash, and run number

## Audit map

| Stage | Artifact | Purpose |
|---|---|---|
| Frozen inputs | `iteration-1/eval-manifest.json` | Hashes prompt, rubric, evaluator, input tree, and snapshots |
| Baseline | `iteration-1/eval-10-voice-chain-end-to-end/without_skill/run-1/` | Raw grading, timing, transcript, and measurement |
| Iteration 1 | `iteration-1/` | QA scheduling hypothesis, candidate result, benchmark, and findings |
| Iteration 2 | `iteration-2/` | Contract-replay hypothesis, frozen candidate snapshot, candidate result, and benchmark |
| Snapshots | `snapshots/` | Immutable executor skill/tool inputs for attribution |

## Interpretation boundary

Each iteration contains one paired sample. It proves the observed quality and token outcome for this frozen case and model run. Repeated runs across seeds and additional self-contained cases are required to estimate variance and generalize the gain.
