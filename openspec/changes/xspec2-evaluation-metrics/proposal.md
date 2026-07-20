# xspec2-evaluation-metrics

## Why

x-spec2 已有 with-skill / without-skill benchmark，但当前 `tokens` 使用输出字符数代理，`time_seconds` 固定为 0，无法回答一次真实运行消耗了多少模型 token、持续多久、交付质量是否达标。先为 x-spec2 建立最小且可复核的观测闭环，可以用一个配对样本跑通采集、评分与汇总，再决定是否扩展到整条 pipeline。

## What Changes

- 新增标准库工具 `tools/metrics.py`，支持从用户明确指定的 Codex rollout JSONL 提取真实 token 累计值与 session duration，也支持读取子 agent 完成通知即时保存的 `timing.json`；不自动猜测 session。
- 为每个 x-spec2 eval run 生成 `measurement.json`，固定记录 run 身份、可复现指纹、真实 total token、duration、可用时的 token 分桶和 grading 结果。
- 规定最小配对评测协议：同一 eval prompt、同一模型、同一仓库版本，各运行一次 `with_skill` 与 `without_skill`；执行者输入不含 grading expectations，评分阶段独立读取 rubric。
- 聚合生成 x-spec2 benchmark JSON/Markdown，比较质量通过率、total token 与 duration；单样本结果必须标记为 pilot，只证明采集链路可用。
- 首版明确排除人工等待时间、active/tool/queue 时间拆分、金额换算、Claude session、父子 agent 聚合、自动 session 扫描和全 pipeline stage 埋点。

## Capabilities

### New Capabilities

- `xspec2-evaluation-metrics`: x-spec2 单次 eval 的最小观测 schema、Codex session/子 agent 通知提取、质量关联、配对汇总与 pilot 有效性规则。

### Modified Capabilities

无。

## Impact

- 新增：`tools/metrics.py`、对应标准库单元测试、x-spec2 eval 运行说明与最小 measurement schema。
- 更新：`skills/x-spec2-workspace/` 的 benchmark 生成链路；现有 `metrics.json` 继续承载工具调用等执行统计，新增 `measurement.json` 承载真实 token、duration 与质量摘要。
- 前置依赖：`xspec-v2` change 的 skill、eval case 与 workspace 结构保持可用；本 change 不修改 x-spec2 产物契约。
- 后续阶段：扩展 Claude adapter、父子 session 聚合、完整 pipeline stage 事件、人工等待拆分、金额与预算线。
