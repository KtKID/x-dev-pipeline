# x-spec2 eval 运行协议

## 输入隔离

- executor 只接收 case 的 `prompt_file` 和 `files`。
- `evals/problems/` 只放可直接交给 executor 的题面，每个 case 使用一个独立文件。
- `evals/answers/<case>/` 只放 rubric、expectations、grader 等答案相关资料，只交给独立 grader。
- eval 1 的 `files` 为空；executor 的唯一题目输入是 `evals/problems/stackchan-esp32s3-voice-link.md`。
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

## Scenario 精简配对评测

Eval 3-7 衡量 `pipeline-self-evolution` 的 Scenario 从 31 条压缩到 15 条后，是否仍能驱动完整的下游 task contract。

- `with_skill` 是 viewer/metrics 的兼容标签，实际 variant 为 `compact_spec`。
- `without_skill` 是 viewer/metrics 的兼容标签，实际 variant 为 `verbose_spec`。
- orchestrator 将对应快照复制为各 run 私有的 `inputs/spec.md`；两臂 executor 看到相同路径和相同 prompt。
- executor 只读取 `prompt_file` 与 `inputs/spec.md`，输出唯一 `task-contract.md`，不读取 `evals.json`、rubric、另一版 spec 或历史对话。
- `expectations`、`grader.rubric`、variant 映射与源快照路径属于 grader/orchestrator 输入。
- 首轮执行 spec-to-task-contract，评测通过后再选择高风险 case 进入实现级 dev eval。

## 指令表达 A/B/C 微评测

Eval 8 比较三种语义目标一致的规则表达：

- `arm_a_do`：只描述目标行为。
- `arm_b_dont`：只描述禁止行为。
- `arm_c_do_reason_assertion`：描述目标行为、原因和可执行断言。

每个 executor run 一次处理 10 个边界微任务，每种配置使用 3 个独立 rollout。相同 repetition 的三臂共享 case 内容和顺序；只有 `inputs/rules.md` 不同。确定性 grader 对每个 case 的最终状态做严格 JSON 等值校验，形成每配置 30 个观测点。

运行入口：

```bash
python3 evals/scripts/instruction_form_abc.py prepare \
  --workspace skills/x-spec2-workspace/iteration-4

python3 evals/scripts/instruction_form_abc.py grade \
  --run-dir skills/x-spec2-workspace/iteration-4/eval-8-instruction-form-adherence/<arm>/run-<n>

python3 evals/scripts/instruction_form_abc.py aggregate \
  --workspace skills/x-spec2-workspace/iteration-4
```

矩阵、固定顺序、控制变量和指标定义见 `evals/instruction-form-abc.json`。executor 无权读取 `evals/answers/instruction-form-adherence/`。

## x-spec3 / x-spec2 规格质量配对评测

Eval 9 使用 `task-01-configresolver` 比较冻结的 x-spec2 与 x-spec3：

- 两臂读取同一题面、使用同一模型与 repo SHA，在同一轮并行启动。
- x-spec3 生成单一 `spec.md`；x-spec2-frozen 按原契约生成 2+1 包。
- executor 只生成规格，不实现代码，不运行 xdev，不读取隐藏答案或 rubric。
- 独立 grader 按隐藏 `EVALUATION.md` 评分 20 条任务语义，并单独评分 8 条规格结构。
- blind comparator 只读取匿名 A/B 产物，完成判断后再揭盲。
- `tools/metrics.py` 从两个完成态 Codex rollout 采集完整 executor Token 与耗时。

结果、限制与缺口见 `skills/x-spec3-workspace/iteration-1/result.md`；静态评审页位于同目录的 `review.html`。
