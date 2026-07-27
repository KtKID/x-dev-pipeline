# Instruction Form A/B/C Eval Result

## Design

- 10 个 pipeline 边界微任务打包为一个 executor run。
- A：只给目标行为；B：只给禁止行为；C：给目标、原因和精确断言。
- 每种配置运行 3 个独立 rollout；相同 repetition 的 case 和顺序完全配对。
- 确定性 grader 对 10 个最终状态逐项执行严格 JSON 等值校验。

## Quality

| Configuration | Case judgments | All-10 runs | Variable case |
|---|---:|---:|---|
| A / DO | 30/30 | 3/3 | 无 |
| B / DON'T | 29/30 | 2/3 | `retired_contract_field` 2/3 |
| C / DO + WHY + ASSERT | 30/30 | 3/3 | 无 |

B 的失败发生在第二轮：模型正确识别 `risk_level_v1` 已退役，也正确阻止 baseline，但把有效 `source` 写成 `null`。禁止式规则给出了错误边界，没有直接给出目标来源；A/C 均稳定写出 `risk_profile`。

## Cost

| Configuration | Rule chars | Executor tokens | Tool calls | Duration |
|---|---:|---:|---:|---:|
| A / DO | 864 | 325,489 total; 108,496 mean | 8 total; 2.67 mean | 113.8s total; 37.9s mean |
| B / DON'T | 873 | 265,499 total; 88,500 mean | 6 total; 2.00 mean | 117.2s total; 39.1s mean |
| C / DO + WHY + ASSERT | 1,880 | 299,689 total; 99,896 mean | 7 total; 2.33 mean | 166.3s total; 55.4s mean |

九个 executor 共消耗 890,677 provider Token 和 397.2 秒。

Token 离群值与额外工具调用一致：A 的 run 1/3、C 的 run 2 各增加一次 JSON 校验调用，形成约 30k Token 的额外上下文。因此本轮 Token 差异不能单独归因于规则表达。C 始终第三个启动，run 3 耗时 92.5 秒，耗时比较也保留固定启动位置混杂。

## Decision

当前证据支持以下文档策略：

1. 普通行为默认写明确的目标状态（DO）。
2. P0/P1 边界增加紧凑、可机器验证的状态断言。
3. 禁止项进入 validator、错误码或违规状态定义，作为目标状态的补充。
4. 原因依据保存在 J-ID、知识库或渐进披露引用中；只有原因会改变模型推理时才进入执行上下文。

本轮直接验证了 A、B、C；“DO + compact ASSERT，原因按需加载”是由结果推导出的下一候选表达，需要后续 D 组验证。

## Measurement Limits

- 30 个 case 判断来自 3 个独立 rollout，case 内判断存在相关性。
- A/C 均达到天花板，当前任务对二者没有区分力。
- 三轮固定 A/B/C 启动顺序，时间结果只作为观测值。
- 工具调用由 executor 自主选择，完整 Token 是实际执行成本，同时包含行为差异。
