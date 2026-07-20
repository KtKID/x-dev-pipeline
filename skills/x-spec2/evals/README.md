# x-spec2 eval 运行协议

## 输入隔离

- executor 只接收 `evals.json` 的 `prompt` 和该 case 的 `files`。
- `expectations` 与标记为 grader-only 的 case rubric 只交给独立 grader。
- eval 1 的 `files` 为空；`stackchan-esp32s3-voice-link.md` 是 grader-only rubric。
- with-skill executor 读取 `skills/x-spec2/SKILL.md` 与模板；without-skill executor不得读取 x-spec2 skill、模板或 eval rubric。

## 运行边界

1. 同一 eval 的两臂使用相同 prompt、模型和 repo SHA。
2. 两臂在同一轮并行启动，每个子 agent 只执行一个 eval task。
3. 子 agent 完成后优先解析与该 agent 一一对应的完成态 Codex rollout，并把该显式路径交给 collector；完成通知直接提供 `agent_id`、`total_tokens` 与 `duration_ms` 时，也可立即保存为 run 目录下的 `timing.json`。
4. grader 在 executor 完成后读取 outputs、transcript 与 grader-only expectations，生成 `grading.json`。
5. 主 agent 运行 `tools/metrics.py extract --session ...` 或 `--timing ...` 生成 `measurement.json`，再运行 `aggregate-spec2`。两种来源都使用真实 provider/runtime 值，禁止字符数或人工估算代理。

## 结果位置

```text
skills/x-spec2-workspace/iteration-N/eval-<id>/
├── eval_metadata.json
├── with_skill/run-1/
│   ├── eval_metadata.json
│   ├── timing.json
│   ├── transcript.md
│   ├── grading.json
│   ├── measurement.json
│   └── outputs/
└── without_skill/run-1/
    └── ...
```

单次 paired run 只证明采集与评分链路成立；稳定效果判断需要增加不同题目与重复次数。
