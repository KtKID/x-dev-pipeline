#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/../.." && pwd)
case_dir="$repo_dir/evals/problems/x-dev-receipt"
benchmark="$repo_dir/skills/pipeline-efficiency-benchmark/scripts"
runs_dir="$repo_dir/evals/x-dev-receipt-runs"
mkdir -p "$runs_dir"
run_dir=$(mktemp -d "$runs_dir/run-XXXXXX")
workspace="$run_dir/workspace"
printf 'Run: %s\n' "$run_dir"

mkdir -p "$workspace/skills"
cp -R "$repo_dir/skills/x-dev" "$workspace/skills/x-dev"
python3 "$benchmark/prepare_workspace.py" --profile public_task_only --allow-existing \
  --workspace "$workspace" --task-source "$case_dir/project" \
  --prompt-source "$case_dir/PROMPT.md" --json > "$run_dir/prepare.json"
python3 "$benchmark/validate_workspace.py" "$workspace" \
  --manifest "$run_dir/executor-package-manifest.json" --json > "$run_dir/preflight.json"

if [[ ${1:-} == --prepare-only ]]; then
  exit 0
fi

node -e "require('playwright')"
if ! codex exec --ignore-user-config --ephemeral --skip-git-repo-check --sandbox workspace-write \
  --cd "$workspace" --json -o "$run_dir/receipt.md" - < "$workspace/PROMPT.md" \
  > "$run_dir/execution.jsonl" 2> "$run_dir/executor.log"; then
  printf 'Codex execution failed. See %s\n' "$run_dir/executor.log" >&2
  exit 1
fi
node "$repo_dir/evals/answers/x-dev-receipt/grade.cjs" "$run_dir"
