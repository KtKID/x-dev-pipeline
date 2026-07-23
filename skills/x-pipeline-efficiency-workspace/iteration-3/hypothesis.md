# Iteration 3 hypothesis

## Hypothesis

高级模型能在单个长上下文中同时维护硬约束、模块边界、反例和验证映射。把独立读取、关联编辑和机械验证合并为批次，可以减少主 agent 的上下文重放；把 Q3 的三个 lens 放入一个完整 reviewer turn，可以保留结构化审查范围并消除多 reviewer 的重复取证。

## Changes under test

- x-spec3：一次宽读取、一次成稿、批量修复 validate issue。
- x-req3：一次读取和写入，validate/status/graph 合成验证批次。
- x-dev：Scenario → code → counterexample → verify 矩阵、批量编辑、递增验证链。
- x-qa-gate：Q3 单个 tri-lens reviewer，三个 lens 独立列候选后再合并根因。
- x-fix：路由术语与 tri-lens 对齐。

## Falsification

新增的 `journal-index-recovery` case 中，任一 candidate run 低于 100 分、关键断言失败、同一 lens 被跳过，或两次 candidate 的 token 中位数未比两次 frozen baseline 的中位数降低 10%，该候选不晋级。
