# DeepSeek Harness ACP · 评测操作协议

考生材料与评分材料分别放在 `evals/problems/deepseek-acp/` 和 `evals/answers/deepseek-acp/`。考生工作区从固定的 Harness 提交打包，含题面、真实源码、离线驱动和指定版本的本地 skills。答案补丁、评分器、工作区源路径、另一臂和历史结果均留在操作者侧。

## 准备配对工作区

在 `x-dev-pipeline` 仓库根目录运行（Python 3.10+、Git、Node 24；`--offline-tsx` 需要本机 Harness 已安装 tsx 及对应 esbuild）：

```bash
harness=/Volumes/machub_app/proj/agent/deepseek-harness
pair=$(mktemp -d /tmp/dsh-acp-pair.XXXXXX)
python3 evals/scripts/prepare_deepseek_acp.py --harness "$harness" \
  --run-dir "$pair/baseline" --pipeline-ref HEAD --offline-tsx
python3 evals/scripts/prepare_deepseek_acp.py --harness "$harness" \
  --run-dir "$pair/candidate" --offline-tsx
```

正式比较时，把 `HEAD` 换成所测修改之前的冻结 SHA；候选省略 `--pipeline-ref` 时打包当前工作区（含未提交 skill）。两臂必须有相同的 `task/` 和 `PROMPT.md` 文件清单及 SHA，允许变化的路径限定在此次测试的 skills 及其文件。`executor-package-manifest.json` 和 `preflight.json` 写在 `workspace/` 外。运行时脚本取自每臂同一快照内的 skills，例如 `skills/x-dev/scripts/xdev.py`，预检会调用其 CLI。

`--offline-tsx` 复制本机平台的 tsx/esbuild，足以启动夹具并使用 `node --import tsx --test`。要运行旧仓库的完整 Vitest/类型检查，可省略该选项，在隔离的准备阶段用 Node 24 和 Yarn 4.14.1 按 `task/yarn.lock` 预装依赖；两臂使用同一依赖层，把包版本与哈希记入运行清单。随后关闭考生的 shell 网络。清洁考生运行只挂载本臂的 `workspace/`；另外提供独立 HOME、无历史会话与全局 skill 注入的执行环境。模型接入由外部运行器负责。单设 `cwd` 或工作区写入限制仍可能读到宿主源码与答案，正式得分要求文件读取与网络隔离。

## 执行与评分

两臂使用同一模型版本、推理档位、工具配置、初始上下文、超时和确认规则；每臂用新会话，在同一会话继续后续阶段。向考生发送 `PROMPT.md` 原文。收到规格与技术设计的确认请求后，操作者按题面分别审查，再发送 `确认这份规格/技术设计，确认版本：<产物 SHA-256>；继续下一阶段。` 未满足题面的地方以公开需求指出，并保留本轮反馈和消耗。评审答案与隐藏用例在运行期间不进入会话。风险复核依赖的语料环境在两臂保持一致，QA 子会话也遵守同一隔离边界。主线范围为 `full_pipeline`，包含必经阶段及实际触发的风险复核/修复，`x-qdev` 属于另一条评测路径。

执行结束后，将候选项目交给独立 grader。在独立的测试环境运行候选子进程，隔离宿主源代码、凭据和网络；对正式盲评，子进程的文件访问仅限候选项目、运行依赖和临时存储。核对 `task/eval-support/` 与输入清单一致，保留完整产物快照：

```bash
python3 evals/answers/deepseek-acp/grade.py "$pair/candidate/workspace/task" \
  --output "$pair/candidate/wire-grading.json"
```

`wire-grading.json` 和 `wire-evidence.json` 是独立运行证据。按 [RUBRIC.md](RUBRIC.md) 补齐流水线评分，记录最早引入错误的阶段与发现阶段，区分执行结束、质量通过和允许晋级。评分器默认在本机启动子进程；正式隔离应由运行环境强制。参考答案复跑见下文。

## Token 预算与判定

每臂计入从初始任务到最终交付的执行者全会话，包括确认消息后的轮次，以及该次运行启动的风险、QA、修复子会话。grader 和外部分析用量另计。使用 provider/runtime 原始用量：`all-in = input + output`，`effective = input - cached_input + output`。缓存输入和推理输出分别为输入和输出的子集；离线夹具用量仅作协议验证。超时或质量失败的消耗仍入账，保留运行终态。遥测缺失写 `null` 和原因。

先冻结至少三次 baseline 的 `all-in` 中位数 `B`。候选每次运行的预算线为 `ceil(1.05 × B)`，用来发现超过 5% 的消耗回归。优化晋级线为候选中位数 `≤ 0.90 × B`，同时要求各候选运行满分且全部 P0 通过。5% 和 10% 是本题初始策略；在正式候选运行前可记录不同预算与停止条件。预算线用于判定，执行时是否硬停止以运行器可提供的实时用量为准。

保留原始会话、子会话树、确认轮次、模型及推理档位、各 Token 桶、耗时、价格快照和各阶段可定位的消耗边界。可用 `skills/pipeline-efficiency-benchmark/scripts/metrics.py` 的 Codex rollout 解析器或 provider 真源提取，再交给同目录的 `normalize_run.py` 和 `compare_runs.py`；Codex 解析器要求 rollout 带 Git SHA，可在隔离工作区先建立相同的纯公开输入 Git 基线，也可以使用其他 provider 的原始遥测。阶段记录按 `skills/pipeline-eval-report/` 的 run 产物契约归档。一次 A/B 只校验采集链路；稳定结论用同 scope 的重复样本。跨 provider 或统计口径的结果单列。

归一化输入：`metrics.json` 使用 `tokens` 对象（`input`、`cached_input`、`output`、`reasoning_output`、`total`）；`eval_metadata.json` 记录 `model` 与 `reasoning_effort`；`grading.json` 记录完整的 `quality_score`、`critical_gate_passed` 和 `rubric_version`。用同一命令处理两臂：

```bash
run="$pair/candidate"
python3 skills/pipeline-efficiency-benchmark/scripts/normalize_run.py \
  --run-id candidate-01 --label 'Candidate 01' --scope full_pipeline \
  --metrics "$run/metrics.json" --metadata "$run/eval_metadata.json" \
  --full-grading "$run/grading.json" --output "$run/benchmark-run.json"
```

有价格证据时追加 `--pricing "$run/pricing.json"`；缺失时归一化结果保留 `unknown`。用各次 `benchmark-run.json` 的 `usage.total_tokens` 计算中位数；缺完整执行遥测的样本单独记录并重跑，保留已发生的消耗。

## 复跑官方参考

只在评审侧使用完整、原始的父版本归档；考生包省略了上游 RFC 和全局 skill 等材料。

```bash
reference=$(mktemp -d /tmp/dsh-acp-reference.XXXXXX)
git -C "$harness" archive add59a3336f0ab61c55499418081aab76cb550f8 | tar -xf - -C "$reference"
gzip -dc evals/answers/deepseek-acp/official-reference.patch.gz | git -C "$reference" apply --binary
cp -R evals/problems/deepseek-acp/eval-support "$reference/eval-support"
(cd "$reference" && YARN_ENABLE_SCRIPTS=0 yarn install --immutable)
python3 evals/answers/deepseek-acp/grade.py "$reference" --output "$pair/reference/grading.json"
```

参考运行的锁定 SDK 是 0.25.1。本机离线校准使用已安装的 SDK 1.4.0 和 Node 24.14.0，8 项协议检查通过；原始锁文件的安装还需要依赖缓存或 registry 访问。官方参考校准与考生 A/B 分开记录。
