# Journal Index Recovery 验收报告

## 结论

**验收未通过，质量分 96/100，critical gate 失败，promotion 失败。**

候选实现通过 27 个公开测试、23 个 Gate① verify 块、spec/task 机械校验和 24/25 条隐藏 rubric v3 断言。唯一业务阻断是“完整、带换行、CRC 错误的最后一条 journal record”的恢复分类。

## Run 身份

| 字段 | 值 |
|---|---|
| iteration | 8 |
| run | `minimax-glm52-20260725` |
| workspace | `/Volumes/machub_app/proj/x-dev-world/minimax/journal-index-recovery` |
| scope | `full_pipeline` |
| provider | `builtin:bigmodel-coding-plan` |
| model / reasoning | `GLM-5.2 / max` |
| root session | `sess_6625cddf-684e-42f4-8605-06bc47508a8b` |
| Q3 reviewer | `sess_subagent_agent_835967fc-f86c-467f-941b-1f06e642f376` |
| excluded follow-up | `sess_f71adcaa-4e99-44cc-ae55-e2230b173546` |

## 验收结果

| 检查 | 结果 | 证据 |
|---|---|---|
| 公开 unittest | PASS | `python3 -m unittest discover -s tests -v`：27/27 OK |
| Gate① verify | PASS | `python3 tools/xdev.py verify ... --json`：23 pass / 0 fail / 0 manual / 0 uncovered |
| req3 task validate | PASS | 0 issues |
| spec risk contract | PASS | `valid: true` |
| 隐藏 rubric v3 | FAIL | 24/25，96 分，critical gate false |
| checklist 终态 | FAIL | T5 仍为 `[!] 🔴`；`xdev graph` 显示 ready=[T5] |
| grader isolation | PASS | workspace 与候选 trace 均无 oracle/rubric/grader/answers |
| benchmark preflight 证明 | FAIL | 原执行未保存 candidate preflight 与 pre-execution package manifest |
| 严格 workspace-only 读取 | FAIL | RAG 使用 workspace 外的 Qwen3 embedding model 路径 |
| benchmark skill 自测 | PASS | Python 3.12：6/6 OK |

公开测试输出包含若干 `ResourceWarning`，来源为测试代码中的未闭合文件句柄。它们未影响退出码与功能评分。

## 唯一业务阻断

题面 `PROMPT.md:66` 明确规定：最后一条物理记录的字段错误或 CRC 不匹配属于可恢复尾部；普通命令返回 `RECOVERY_REQUIRED`，`recover` 截断该记录。

当前实现形成了相反分类：

- `fixture/backend/store.py:33` 的 `RECOVERABLE_KINDS` 只含 `truncation/no_newline/json`，缺少 `field/crc`。
- `fixture/backend/store.py:247-250` 把最后一条 `field/crc` 归为 `CORRUPT_LOG`。
- `fixture/backend/store.py:580-582` 让 `recover` 对该现场保持只读失败。

隐藏 grader 构造一条完整、CRC 被修改、保留换行的 seq=2 record。候选 `list` 返回 exit 7 / `CORRUPT_LOG`；契约要求 exit 6 / `RECOVERY_REQUIRED`，随后 `recover` 成功截断并保留 seq=1 状态。

公开测试的覆盖缺口位于 `tests/test_journal.py:220-234`：SC_10 只追加 `b"\xff\xfe partial"`，覆盖截断 UTF-8 尾部；`tests/test_journal.py:247-258` 覆盖中间物理损坏。测试集缺少“末条完整 CRC 错误 + 换行”的精确回归。

## 产物一致性

执行会话最终回复声明“全流程完成、checklist 全部 `[x] ✅`”。当前落盘事实为：

- `dev-checklist.md:14` 的 T5 是 `[!] 🔴`。
- `xdev graph` 输出 `ready: T5`。
- fix 报告记录 P0 已关闭，隐藏 rubric v3 仍发现同一恢复分类域内的 CRC 尾部缺口。

验收以当前文件、复跑结果和隐藏 grader 为准。

## Token 总量

ZCode DB 的 `model_usage` 按 root session + Q3 reviewer child 聚合：

| 指标 | Tokens | 口径 |
|---|---:|---|
| Input | 12,357,980 | 包含 cached input |
| Cached input | 12,167,104 | Input 子集；占 Input 98.46% |
| Uncached input | 190,876 | Input - Cached input |
| Output | 88,941 | Reasoning output 为其子集 |
| Reasoning output | 0 | provider 遥测值 |
| **Total / all-in** | **12,446,921** | Input + Output |
| **Effective** | **279,817** | Uncached input + Output |

Input 占 all-in `99.29%`，cached input 占 all-in `97.75%`，uncached input 占 `1.53%`，output 占 `0.71%`，effective 占 `2.25%`。

主执行会话为 `10,315,924` tokens（82.88%）；Q3 reviewer 为 `2,130,997` tokens（17.12%）。all-in 包含 160 tokens 自动标题开销。15:21 创建的“查找当前 session 聊天记录路径”会话属于后续查询，统计已排除。

## 金额

Z.ai 官方 GLM-5.2 API 单价按每 100 万 Tokens 计：未缓存 Input `$1.40`、Cached input `$0.26`、Output `$4.40`。价格来源为 [Z.ai Pricing](https://docs.z.ai/guides/overview/pricing)，查询日期为 2026-07-25。

| 计费项 | Tokens | 单价 / 1M | API 等价成本 |
|---|---:|---:|---:|
| Uncached input | 190,876 | $1.40 | $0.267226 |
| Cached input | 12,167,104 | $0.26 | $3.163447 |
| Output | 88,941 | $4.40 | $0.391340 |
| **合计** | **12,446,921 all-in** | — | **$3.822014** |

计算公式：

```text
190,876 × $1.40 / 1,000,000
+ 12,167,104 × $0.26 / 1,000,000
+ 88,941 × $4.40 / 1,000,000
= $3.82201384
```

无缓存时的 API 等价成本为 `$17.692512`；缓存节省 `$13.870499`，降幅 `78.40%`。主执行会话的 API 等价成本为 `$3.120148`（81.64%），Q3 reviewer 为 `$0.701866`（18.36%）。

本次 provider 为 `builtin:bigmodel-coding-plan`，属于 Coding Plan 套餐额度调用。Z.ai [Coding Plan FAQ](https://docs.z.ai/devpack/faq) 说明套餐内 GLM 调用只消耗额度，账户余额不会按单次 API 用量扣款，因此本次运行的**实际现金增量为 `$0.00`**；`$3.822014` 用作跨运行的 API 等价成本指标。

ZCode DB 记录的模型调用发生于 2026-07-25 14:25:37–15:03:55（UTC+8），完整落在官方定义的 14:00–18:00 峰值时段。Z.ai [Coding Plan Overview](https://docs.z.ai/devpack/overview) 规定 GLM-5.2 峰值时段按 `3×` 扣减套餐额度，因此本次对应的额度权重为 `3×`，折合 `$11.466042` API 等价额度。该数表示套餐额度权重，现金增量扣款仍为 `$0.00`。

## Phase Token 分布

| Phase | LLM calls | Tokens | Share | Effective | Tool calls |
|---|---:|---:|---:|---:|---:|
| bootstrap + x-spec3 + risk | 43 | 1,980,931 | 15.92% | 82,435 | 62 |
| x-req3 | 9 | 653,356 | 5.25% | 8,300 | 9 |
| x-dev + tests + dev-report | 38 | 3,813,884 | 30.64% | 79,804 | 38 |
| Gate① verify | 5 | 595,598 | 4.79% | 3,214 | 5 |
| Gate② orchestration | 2 | 246,708 | 1.98% | 6,580 | 2 |
| Gate② reviewer | 44 | 2,130,997 | 17.12% | 78,197 | 49 |
| x-fix + reverify + closeout | 23 | 3,025,447 | 24.31% | 21,287 | 22 |
| **Total** | **164** | **12,446,921** | **100.00%** | **279,817** | **187** |

最大阶段为 `x-dev + tests + dev-report`（30.64%）；`x-fix + reverify + closeout` 为第二大阶段（24.31%）；Gate② orchestration + reviewer 合计 `2,377,705` tokens（19.10%）。

工具调用共 187 次，185 completed、2 error。两次 error 分别为用户打断造成的 Bash cancellation，以及 Write 在 read-before-write 门禁上的失败。

## 时间

| 指标 | 数值 |
|---|---:|
| 主任务 active | 1,954.928 s |
| 嵌套 Q3 reviewer | 424.420 s |
| Executor time sum | 2,379.348 s |
| Root session wall | 2,298.000 s |

主任务 active 来自两条 root `turn_usage` 的 duration 求和；首条 turn 被用户中断，已产生的 token 与 active time继续计入真实任务成本。Executor time sum 在主任务 active 上增加嵌套 reviewer 时间。

## 横向比较与晋级

冻结 Terra baseline 为 `gpt-5.6-terra/xhigh`、rubric v2、20,619,230 tokens。当前 candidate 为 `GLM-5.2/max`、rubric v3、12,446,921 tokens。Provider、模型、reasoning 和 rubric 均不同，直接 Token 降幅不进入晋级判定。两者的算术差为 `-39.63%`，仅作背景展示。

本次 `comparison.json` 按 skill 文本的完整门禁显式加入 provider/model/reasoning 与 rubric 检查。当前 `compare_runs.py` 的自动 comparability 只检查 scope 和 Token convention；本次报告采用更严格的 skill 契约，并由 `validate_comparison.py` 校验结构与公式。

晋级门禁：

- PASS：相同 `full_pipeline` scope 与 Token 公式。
- FAIL：同 provider/model/reasoning。
- FAIL：同一当前 rubric 历史重评分。
- FAIL：质量 100；当前 96。
- FAIL：critical gate；当前 false。
- FAIL：同口径 all-in Token 至少下降 10%。
- FAIL：preflight 证明。
- PASS：grader-only 材料隔离。

`promotion_passed: false`。

## 验收命令

```bash
env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 tools/xdev.py validate docs/spec/journal-index-recovery/tasks/implementation --json
python3 tools/xdev.py verify docs/spec/journal-index-recovery/tasks/implementation --json
python3 skills/x-adversarial-risk/scripts/risk_contract.py validate-spec docs/spec/journal-index-recovery/spec.md --json
env PYTHONDONTWRITEBYTECODE=1 python3 evals/answers/journal-index-recovery/evaluate.py \
  /Volumes/machub_app/proj/x-dev-world/minimax/journal-index-recovery
python3.12 -m unittest skills.pipeline-efficiency-benchmark.tests.test_pipeline_efficiency_benchmark
python3 skills/pipeline-efficiency-benchmark/scripts/normalize_run.py \
  --run-id minimax-glm52-20260725 \
  --label "MiniMax ZCode GLM-5.2 full pipeline" \
  --iteration 8 \
  --scope full_pipeline \
  --metrics skills/x-pipeline-efficiency-workspace/iteration-8/runs/minimax-glm52-20260725/full-pipeline-metrics.json \
  --timing skills/x-pipeline-efficiency-workspace/iteration-8/runs/minimax-glm52-20260725/timing.json \
  --full-grading skills/x-pipeline-efficiency-workspace/iteration-8/runs/minimax-glm52-20260725/grading.json \
  --metadata skills/x-pipeline-efficiency-workspace/iteration-8/runs/minimax-glm52-20260725/eval_metadata.json \
  --pricing skills/x-pipeline-efficiency-workspace/iteration-8/runs/minimax-glm52-20260725/pricing.json \
  --output skills/x-pipeline-efficiency-workspace/iteration-8/runs/minimax-glm52-20260725/benchmark-run.json
```

验收建议：保持当前版本为失败样本；修复末条 `field/crc` 可恢复分类，增加完整带换行 CRC 错误的回归测试，关闭 T5 红灯，复跑 rubric v3；随后用 `GLM-5.2/max` 建立 clean baseline/candidate 配对，再判断 Token 晋级。
