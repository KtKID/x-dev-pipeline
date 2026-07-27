# Iteration 0：Baseline

## 目标

测量当前冻结 pipeline 在自包含多模块任务上的完整执行成本与正确性，建立后续单变量优化的对照。

## 冻结变量

- Case：`voice-chain-end-to-end`。
- 输入：题面、三份规范、后端骨架、设备模拟器、确定性假服务与音频素材。
- 执行范围：spec3 → req3 → dev → verify → 风险路由。
- 评分：20 条等权隐藏断言，100 分制，核心功能单独设门禁。
- 环境：Python 标准库、本地文件、本地进程、回环 socket。

## Baseline 假设

当前 pipeline 能识别协议、服务编排、并发与验证风险；完整端到端任务会暴露上下文重复读取、过度文档化、待确认阻断或验证链成本。Iteration 0 只测量与归因，保持冻结 skill 原样。

## 晋级目标

- 质量分至少 90。
- 核心功能断言全部通过。
- 相对 baseline 的 executor 总 token 至少下降 5%。
- 每次改动均关联 baseline 失败或 transcript 中的可见浪费。
