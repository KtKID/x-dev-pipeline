# Iteration 1：QA 调度去重

## 观察

诊断基线在 Q3 审查阶段出现以下可见浪费：

- 主 agent 至少执行 9 次 20—30 秒 `wait_agent` 短轮询；后期每个等待 turn 约产生 9.4—9.9 万 total token。
- 运行中 reviewer 收到补充消息后中断并重启，已完成的上下文读取与推理重复发生。
- reviewer 返回完整候选后又接收严重度复判和修复复审 follow-up，继续携带上一轮全部上下文。

三路审查同时证明了质量价值：q2-correctness 找到总 HTTP deadline 缺失的 P1，并推动慢速滴流反例与修复。因此本轮保留 Q3 的 q1-intent、q2-correctness、q3-evidence 三位独立 reviewer。

## 单变量改动

只修改 `skills/x-qa-gate/SKILL.md`：

1. 明确 Q0/Q1、Q2、Q3 的既有路由，消除原路由段落歧义。
2. reviewer prompt 一次完整派发。
3. reviewer 运行期间保持 turn 连续，禁止消息、follow-up、interrupt 与重复派发。
4. 等待窗口统一为 60 秒，省略 `list_agents` 轮询。
5. 主 agent 直接复核候选严重度，P2 在三路完成后批量处理。
6. 同根因候选合并为一个 x-fix 批次，集中编辑后只执行一个聚焦测试命令和一次 verify。

## 预期

- 隐藏质量分保持至少 90，核心断言保持全绿。
- 完整 agent-tree total token 相对冻结 baseline 至少下降 5%。
- reviewer 独立性、问题登记、x-fix 回流和最终 Gate ② 语义保持不变。

## 归因边界

Case、prompt、模型、题面、fixture、评分器、baseline skill 快照和除 `x-qa-gate/SKILL.md` 外的 executor 文件保持冻结。正式 baseline 与 candidate 均使用全新隔离工作区，root 不向运行中的 executor 发送状态消息。
