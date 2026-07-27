---
name: pipeline-efficiency-benchmark
description: |
  把 x-dev-pipeline 的 skill 优化做成可重复 benchmark：迁移公开任务包到隔离 workspace，完整打包候选 skills 与 tools 脚本，预检考生输入，执行 baseline/candidate，归一化 Token、耗时、工具调用、评分和金额，生成跨 iteration 横向对比并判断晋级。用户提到 pipeline efficiency、任务包迁移、干净上下文评测、baseline/iteration 对比、Token/费用优化、计费金额、横向报告或 skills/x-pipeline-efficiency-workspace 时使用。
metadata:
  compatibility: Requires Python 3.10+ and local readable task, skill, tool, run telemetry, and grader artifacts.
---

# Pipeline Efficiency Benchmark

把一次 pipeline skill 优化拆成可复跑、可审计的七个阶段。执行器只接触公开任务、候选 skill 和运行工具；评分材料始终留在 grader 侧。

## 适用边界

用于优化和评测 pipeline skill，不用于普通产品开发任务。一个独立模型运行对应一个 run；同一 run 的后续 Req3、Dev、Verify、QA、Fix 延续原 run 身份。独立重放创建新 run。

## 固定产物

每个 iteration 至少保存：

```text
iteration-N/
├── benchmark-manifest.json
├── runs/
│   └── <run-id>/
│       ├── workspace/
│       ├── executor-package-manifest.json
│       ├── eval_metadata.json
│       ├── timing.json
│       ├── grading.json
│       ├── pricing.json
│       └── benchmark-run.json
├── comparison.json
├── comparison.md
└── acceptance-report.md
```

`benchmark-run.json` 是跨版本比较的唯一输入。原始 session、评分和报告继续保留为证据。

所有人类可读报告都保留金额章节。金额证据不足时写 `unknown` 和原因，继续保存报告；禁止静默省略金额。

## 阶段 1：prepare

两种迁移 profile：

- `pipeline_candidate`：创建全新 x-dev-pipeline 候选 workspace，复制公开考题、七个阶段 skills、共享 `x-dev-rag-call` 和六个运行 tools。
- `public_task_only`：向已有的其他框架 workspace 只添加公开考题，保留其现有环境，不注入 x-dev skills/tools。

创建全新 pipeline candidate：

```bash
python3 skills/pipeline-efficiency-benchmark/scripts/prepare_workspace.py \
  --workspace <run-dir>/workspace \
  --task-source <public-task-dir> \
  --fixture-source <public-fixture-dir> \
  --prompt-source <public-prompt> \
  --skills-root <candidate-skill-snapshot> \
  --json
```

向已有 OpenSpec 等候选工程放公开考题包：

```bash
python3 skills/pipeline-efficiency-benchmark/scripts/prepare_workspace.py \
  --profile public_task_only \
  --allow-existing \
  --workspace <candidate-workspace> \
  --task-source <public-task-dir> \
  --fixture-source <public-fixture-dir> \
  --prompt-source <public-prompt> \
  --manifest-output <run-dir>/executor-package-manifest.json \
  --json
```

`--allow-existing` 只允许保留已有文件；`task/`、`fixture/`、`PROMPT.md` 或 manifest 目标发生冲突时拒绝覆盖。

`--skills-root` 目录必须包含：

- `x-spec3`
- `x-adversarial-risk`
- `x-req3`
- `x-dev`
- `x-verify`
- `x-qa-gate`
- `x-fix`

共享 skill：

- `x-dev-rag-call`

skill 包的 `assets/executor-tools/` 包含七个工具。prepare 向考生 workspace 复制六个运行工具：

- `xdev.py`
- `validator.py`
- `flag.py`
- `req3.py`
- `spec.py`
- `verify.py`

`metrics.py` 保留在本 skill 包内，只供 collect 阶段读取 session，不进入考生 workspace。迁移成功以目标 workspace 中的文件和 run 目录侧车 manifest 的 SHA 校验为准。源路径、benchmark 身份、skill 的 `evals/`/`tests/` 和 grader 元数据留在 workspace 外。

## 阶段 2：preflight

在启动模型前运行：

```bash
python3 skills/pipeline-efficiency-benchmark/scripts/validate_workspace.py \
  <run-dir>/workspace \
  --manifest <run-dir>/executor-package-manifest.json \
  --json
```

preflight 检查：

1. 公开 task 和 workspace 外的 package manifest 均存在。
2. `pipeline_candidate` 额外要求完整七阶段 skill、共享 `x-dev-rag-call` 和六个运行 tools；`public_task_only` 保持原框架环境。
3. pipeline candidate 的 tools 与 skill 内 bundled 版本 SHA 一致。
4. `xdev.py` 的本地导入依赖齐全且 CLI 可启动。
5. package manifest 中的所有文件保持原 hash。
6. workspace 不含 `oracle`、`rubric`、`grader`、`answers` 等 grader-only 路径。

exit 0 才能启动执行器。exit 1 保持阻断并修复打包问题。

## 阶段 3：execute

执行器使用干净上下文：

- 新 thread 或 session，继承轮次为 0。
- cwd 固定为本 run 的 `workspace/`。
- 可读范围只含 workspace。
- 提示词描述真实任务和可用 skills；执行器提示词不出现 hidden answer、rubric 或 oracle 信息。
- baseline 使用相同模型、reasoning、公开输入和运行工具；baseline 只移除待测 skill 影响。
- candidate 按 workspace `skills/README.md` 的链路执行。

运行链：

```text
x-spec3
  → 按风险预算调用 x-adversarial-risk
  → x-req3
  → x-dev
  → x-verify
  → x-qa-gate
  → x-fix 与增量复验
```

阶段切片必须写入 `scope`，例如 `spec_risk_only` 或 `full_pipeline`。不同 scope 的总 Token 不进入同一降幅计算。

## 阶段 4：collect

先保留原始遥测，再归一化：

1. 查询执行日期的官方模型价格页，将价格、来源 URL、查询日期和账单/套餐口径写入 `<run-dir>/pricing.json`。不要把价格长期硬编码在 skill 中。
2. 使用 `assets/report-templates/pricing.json` 建立价格快照；完整字段说明见 `references/pricing-schema.md`。
3. 运行归一化：

```bash
python3 skills/pipeline-efficiency-benchmark/scripts/normalize_run.py \
  --run-id iter6-terra-run1 \
  --label "Iteration 6 Terra" \
  --scope full_pipeline \
  --metrics <run-dir>/full-pipeline-metrics.json \
  --timing <run-dir>/timing.json \
  --full-grading <run-dir>/full-pipeline-grading.json \
  --spec-risk-grading <run-dir>/grading.json \
  --metadata <run-dir>/eval_metadata.json \
  --pricing <run-dir>/pricing.json \
  --output <run-dir>/benchmark-run.json
```

优先保存：

- Input、Cached input、Uncached input、Output、Reasoning output、Total。
- 主任务活跃时间、嵌套 reviewer 时间、执行器时间和。
- 工具调用、LLM 调用、失败命令。
- phase Token 分布。
- 原生评分和统一 rubric 重评分。
- 官方价格来源、查询日期和每 1M Tokens 单价。
- API 等价成本、cache-write 上界、无缓存成本和缓存节省。
- 实际现金增量、套餐额度倍数和套餐额度等价金额。

`--timing` 用于 Token 文件与耗时文件分离的 run；耗时已包含在 `--metrics` 时可以省略。

Token 公式：

```text
total_tokens = input_tokens + output_tokens
uncached_input_tokens = input_tokens - cached_input_tokens
effective_tokens = uncached_input_tokens + output_tokens
```

Cached input 是 Input 子集，Reasoning output 是 Output 子集。跨 provider 口径不同的 run 标记为不可直接比较。

金额公式：

```text
api_equivalent
= regular_uncached_input × uncached_input_rate
+ cache_write_input × cache_write_input_rate
+ cached_input × cached_input_rate
+ output × output_rate

no_cache_api_equivalent
= all_input × uncached_input_rate
+ output × output_rate

cache_savings
= no_cache_api_equivalent - api_equivalent

quota_equivalent
= api_equivalent × quota_multiplier
```

provider 未单列 cache-write Tokens 时，基础金额把全部 uncached input 按普通输入单价计算；金额上界把全部 uncached input 按 cache-write 单价计算。API 等价成本、实际现金增量和套餐额度等价金额是三个独立指标。

## 阶段 5：grade

grader 在执行结束后读取隐藏评分器。每次保存：

- grader/rubric 版本。
- 逐项通过、失败和证据。
- 原生分。
- 同一当前 rubric 下的历史重评分。
- critical gate。

同一根因触发多条 assertion 时保留每条扣分，另在根因字段标注关联。

## 阶段 6：compare

只把 `benchmark-run.json` 交给比较脚本：

```bash
python3 skills/pipeline-efficiency-benchmark/scripts/compare_runs.py \
  --run <baseline>/benchmark-run.json \
  --run <iteration-5>/benchmark-run.json \
  --run <iteration-6>/benchmark-run.json \
  --run <latest>/benchmark-run.json \
  --baseline baseline \
  --candidate latest \
  --output-json <iteration>/comparison.json \
  --output-md <iteration>/comparison.md
```

比较脚本按 scope 分组，输出：

- 统一质量分、阶段评分和门禁。
- all-in、effective、I/O 与 cache 比例。
- 主动耗时与执行器时间和。
- tools、LLM calls 和失败调用。
- phase 分布。
- 每个 run 的价格快照和 API 等价成本。
- cache-write 上界、无缓存成本与缓存节省。
- 实际现金增量、套餐额度权重和金额缺失原因。
- 相对 baseline 与上一 iteration 的金额绝对变化和百分比。
- 相对 baseline 与上一 iteration 的绝对值和百分比。
- 缺失指标及原因。

## 阶段 7：validate 与 promote

```bash
python3 skills/pipeline-efficiency-benchmark/scripts/validate_comparison.py \
  <iteration>/comparison.json \
  --report <iteration>/comparison.md \
  --acceptance-report <iteration>/acceptance-report.md \
  --json
```

默认晋级条件：

1. candidate 完整流水线质量分达到 100。
2. critical gate 通过。
3. 与 baseline 相同 scope、模型、reasoning 和 Token 口径。
4. all-in Token 至少下降 10%。
5. workspace preflight 通过。
6. grader-only 材料未暴露。

任何一项失败都保留 iteration 产物，并把结果标为 `promotion_passed: false`。

validator 同时检查 Token 与金额公式、价格来源、查询日期、套餐额度公式，以及 `comparison.md` / `acceptance-report.md` 的金额章节。金额缺失允许用结构化 `unknown` 表达；报告缺少金额章节时直接判为无效。

## 报告模板

- `assets/report-templates/acceptance-report.md`：单次 run 验收报告，固定包含 Token、调用、金额、Phase、横向比较和晋级门禁。
- `assets/report-templates/comparison-report.md`：横向报告字段契约。`compare_runs.py` 是 comparison.md 的权威生成器，模板用于审查或手工恢复。
- `assets/report-templates/pricing.json`：每个 run 的价格与账单输入模板。

生成 `acceptance-report.md` 时完整读取验收模板并填充。金额章节至少包含：

1. 币种、模型、官方价格 URL、查询日期和每 1M Tokens 单价。
2. uncached/cached/cache-write/output 的 Tokens、单价和金额。
3. API 等价成本、cache-write 上界、无缓存成本和缓存节省。
4. 实际现金增量及其账单证据。
5. 套餐额度倍数和套餐额度等价金额。
6. 历史 run 的金额绝对变化、百分比和可比性说明。

## 工具版本更新

仓库根 `tools/*.py` 更新后，维护者运行：

```bash
python3 skills/pipeline-efficiency-benchmark/scripts/refresh_bundled_tools.py \
  --source-tools tools
```

该命令集中更新七个 bundled tools 和 `assets/executor-tools/manifest.json`。随后运行本 skill 的测试，确认迁移包和 SHA 门禁同步。

## 完成回执

每次返回：

- iteration 和 run 身份。
- workspace preflight 结果。
- 执行 scope 与终态。
- 质量、Token、耗时、工具调用。
- API 等价成本、实际现金增量、套餐额度权重和价格来源。
- comparison.md 和 comparison.json 路径。
- acceptance-report.md 和 pricing.json 路径。
- promotion 结果及阻断项。
