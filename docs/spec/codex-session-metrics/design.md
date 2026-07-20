# 动态模型

## 数据流

1. CLI 接收 `--codex-session <path>` 或兼容的 `--session <path>`，并与 `--timing` 做互斥校验（`D7`）。
2. Codex Session Source Parser 顺序读取调用方明确指定的 JSONL，第一条有效 `session_meta` 形成活动 header：session ID、repo SHA、派发时间与 Codex source 信息（`D1`）。
3. Parser 在 header 之后识别首个活动 `turn_context`。该事件之前的累计 `token_count` 形成 fork 基线；从该 turn 开始进入活动执行窗口（`D2`、`D3`）。
4. Parser 扫描活动执行窗口内全部回合，确认模型唯一、最后活动回合已完成，并定位最后一个 `task_complete`。Token 最终快照取该完成事件之前最后一条累计 `token_count`（`D4`）。
5. Parser 对 input、cached input、output、reasoning output 和 total 分别执行 `final - baseline`，保留 provider 分桶语义；reasoning 不再次加到 total（`D3`）。
6. Parser 在首个活动 turn 之后、最终完成事件之前定位最后一条 assistant 回复，将 header 派发时间到该回复时间作为生命周期耗时（`D2`）。
7. grader-only 输入只在活动执行窗口的原始文本中查找；继承前缀退出泄漏判定范围（`D6`）。
8. Parser 输出 normalized source。Measurement Core 只消费该对象与 metadata/grading，生成现有 schema 的 `measurement.json`（`D5`）。

窗口关系：

```text
文件首 active session_meta（任务派发 / duration start）
  ├─ fork 继承前缀与累计 Token 基线
  └─ 首个 active turn_context（execution start）
       ├─ turn 1 -> assistant reply -> task_complete
       ├─ 等待主 agent 反馈
       └─ turn N -> 最后 assistant reply（duration end）
                     -> 最终 token_count -> 最后 task_complete（execution end）
```

## 状态流转

状态所有者为 Codex Session Source Parser：

```text
reading_header -> inherited_prefix -> active_execution -> completed -> normalized
       |                 |                 |              |
       +-----------------+-----------------+-----------> invalid
```

- `reading_header -> inherited_prefix`：首条有效 metadata 解析出活动 session ID、repo SHA 和派发时间。
- `inherited_prefix -> active_execution`：遇到首个有效 `turn_context`；冻结此前最后累计 Token 为基线。
- `active_execution -> completed`：最后活动回合拥有 assistant 回复、最终累计 Token 快照和其后的 `task_complete`。
- `completed -> normalized`：模型唯一、快照各分桶单调、时间顺序合法、grader-only 扫描通过。
- 任一阶段遇到 JSON/schema 错误进入 schema error（退出码 2）；结构可读但活动边界、计数器或隐私条件不成立进入 invalid sample（退出码 1）。

活动 session 中间可出现多个 `turn_context/task_complete`；这些事件扩展同一 active execution，不创建新的 measurement。重复的同 ID `session_meta` 作为活动元数据重复记录接受；不同 ID metadata 仅在首个活动 turn 之前作为继承前缀接受，活动执行中出现新的不同 ID 时样本无效。

## 时序

### 多回合 Codex 子 agent

1. 主 agent 派发任务，Codex 创建当前文件的首个活动 `session_meta`；记录 `started_at`。
2. fork 内容注入文件，其中可能含父 `session_meta`、父 `token_count`、父 `task_complete` 和 grader 路径文本。
3. 首个活动 `turn_context` 到达；Parser 以此前最后 Token 快照为基线，并开始模型/隐私执行窗口。
4. 子 agent 完成首次生成，产生 assistant 回复、最终快照和 `task_complete`；session 可以暂时等待后续消息。
5. 主 agent 发送修复反馈；相同活动 session 产生新的 turn，Token 计数继续累计。
6. 子 agent 给出最后 assistant 回复；该时间写入 `ended_at`。随后最后 Token 快照与 `task_complete`证明最后回合闭合。
7. Parser 使用最后累计快照减基线，使用 `ended_at - started_at` 计算 duration，并生成单一 normalized source。

### 时间与顺序约束

- `started_at` 必须来自文件首个活动 metadata，`ended_at` 必须来自首个活动 turn 之后、最后完成事件之前的最后 assistant 回复。
- `ended_at >= started_at`；最终 Token 快照位于最后完成事件之前，且不得早于首个活动 turn。
- 最后活动 `turn_context` 后必须存在 assistant 回复与 `task_complete`；缺失任一项时 measurement 不成立。
- 活动 turn 可跨越等待期；duration 保留该等待期，表达从派发到最终回复的用户可感知端到端耗时。

## 故障与恢复

| 失败入口 | 处理 | 对 measurement 的影响 | 恢复方式 |
|---|---|---|---|
| 首行缺少有效 Codex `session_meta` | 报 schema/边界错误 | 不写 measurement | 调用方提供完整 Codex rollout |
| fork 前缀含不同父 session ID | 作为继承内容隔离 | 活动 source ID/repo SHA保持首 header 值 | 无需恢复 |
| 活动执行中出现新的不同 session ID | 报无效样本 | 防止跨 session 混算 | 拆分或提供正确单 session 文件 |
| 多个 turn 使用不同模型 | 报无效样本 | 防止一个 measurement 混合模型 | 按模型边界拆分运行 |
| 最后 turn 缺 assistant 回复或完成事件 | 报无效样本 | 防止截断运行进入 benchmark | 等待 session 完成后重提取 |
| 活动前无 Token 基线 | 使用全零基线 | 独立 session 仍可提取 | 无需恢复 |
| 最终任一 Token 分桶小于基线 | 报无效样本并指出分桶 | 防止计数器重置产生负用量 | 按重置点拆分或升级 parser 契约 |
| 活动窗口读取 grader-only 输入 | 报 rubric exposure | 样本退出 benchmark | 重新运行隔离后的 executor |
| grader-only 文本只在继承前缀 | 排除该前缀后继续 | 避免假阳性 | 无需恢复 |
| `--session` 旧调用 | 路由到 Codex 兼容入口 | 结果与 `--codex-session` 一致 | 后续逐步迁移调用方 |

## 迁移

1. 新增 Codex 命名 parser 与内部 helper；所有新增 Codex 专用函数均含 `codex`。
2. 让旧 `parse_rollout_source` 仅委托到 Codex parser，保持现有直接调用兼容。
3. CLI 增加 `--codex-session`，把 `--session` 作为同一目标字段的兼容别名。
4. 先运行现有 14 项 metrics 测试确认单回合行为不变，再加入真实 fork、多回合与窗口隐私 fixture。
5. 用真实子 agent session 验证 total Token `784,530`、reasoning Token `3,906`、duration `466,265 ms`。
6. 完成仓库内调用方迁移后保留旧别名；移除旧入口属于后续破坏性版本决策。

回滚点：新增 parser 可在保持旧函数签名的前提下回退到原实现；若真实 Codex fixture 失败，停止启用 `--codex-session`，现有 `--timing` 与 aggregate 行为继续保持。
