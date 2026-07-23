# x-dev-pipeline 高能力模型 Token 优化报告

## 结论

在新增的自包含多模块 case `journal-index-recovery` 上，`gpt-5.6-sol` 使用冻结 baseline 与候选 skill 各独立运行两次：

| 配置 | 两次质量分 | Token | 中位数/均值 | 相对 baseline |
|---|---|---|---:|---:|
| Candidate | 100, 100 | 6,606,699 / 9,427,504 | 8,017,101.5 | -63.75% |
| Baseline | 95, 95 | 19,136,529 / 25,090,716 | 22,113,622.5 | — |

Candidate 同时达到两次 100 分和预先声明的 Token 至少降低 10% 门槛。平均墙钟时间从 4,618.4 秒降到 1,705.9 秒，降低 63.06%。

本结果证明的是：在这一类“本地、自包含、多模块、含规格—拆解—实现—验证—QA”的任务上，新的编排方式能在冻结评分契约内提高质量并显著减少完整 agent tree Token。两次重复和单一 case 仍不足以把 63.75% 外推成所有开发任务的稳定收益。

## 改了什么，为什么有效

### 1. 宽读取和一次性约束矩阵

x-spec3 首轮同时读取题面、fixture、相关代码和模板，建立“硬约束 → 模块/不变量 → 最小反例 → Scenario”矩阵；文件不变时不重复读取。

高级模型擅长在一个长上下文中关联多处约束。旧流程把这种关联拆成许多串行 turn，每个 turn 都要重放大量输入。候选把关联工作放回同一上下文，减少上下文重播，同时用最小反例防止长上下文中的约束遗漏。

### 2. 批量写入和批量消费校验错误

x-spec3、x-req3 和 x-dev 都改成一次成稿或一次关联编辑，再运行完整校验；校验返回多个 issue 时按根因一次修全。

这利用了高级模型从完整诊断集合中识别共同根因的能力。逐 issue 修复会反复打开相同文件、重复解释相同契约，还容易出现“刚修 A 又破坏 B”的局部最优。

### 3. 递增且不重复的验证链

x-dev 固定使用“聚焦反例 → 当前 task 完整测试 → xdev verify”。每层绿灯只跑一次；失败时消费完整输出后批量修复。

这样保留了快速定位和最终全量证明，但删除了绿灯后的重复证明。确定性工具承担事实检查，LLM 不需要靠多轮自述维持信心。

### 4. Q3 从三个 reviewer 改为一个 tri-lens reviewer

候选仍保留 q1-intent、q2-correctness、q3-evidence 三个独立视角，但把共同输入只交给一个 reviewer，在一个 turn 内分别列候选，再按根因合并。

这符合高级模型可在同一上下文中维持多个显式检查框架的特性。为避免注意力合并导致漏检，skill 要求每个 lens 独立声明检查范围和剩余 P0/P1，而不是只给一个综合印象。

Baseline run-2 展示了旧编排的代价：主 agent 之外启动 8 个 reviewer session，三轮修复后仍因 q3-evidence 持续扩展既有 issue 的样本矩阵而触发 fix 上限。Candidate 每次只有主 agent + 1 个 tri-lens reviewer，并由聚焦反例和完整 verify 关闭问题。

### 5. 状态更新只传新证据

过程消息不复述已读题面、已写章节和已通过命令，只报告新证据、失败和决策变化。

LLM turn 的主要成本不是最终文字，而是每次 turn 再次携带历史上下文。减少无信息增量的回合，比单纯压缩几段说明更有效。

## 与 LLM 特性的关系

- **强项：长上下文综合。** 高级模型能在一个上下文中处理跨模块约束，因此适合宽读取、批量推理和一次性关联编辑。
- **强项：从结构化全集找共同根因。** 完整 issue 列表、Scenario 映射和验证输出比逐条提示更容易形成全局修复。
- **弱点：多轮上下文重放昂贵。** 本轮 Token 中 cached input 占大多数；重复 turn/reviewer 会把相同上下文反复计入完整 agent tree。
- **弱点：清单可能造成视角塌缩。** tri-lens 必须保留三个独立输出和“无其他 P0/P1”回执，不能只说“综合检查完成”。
- **弱点：自我复审可能不断扩展范围。** 冻结单轮 reviewer 的问题集合，由确定性反例和 verify 关闭，能阻止“每次复审发明更强标准”的无界循环。

## 审计与限制

- 四次正式 executor 都使用 `fork_turns:none`，同一模型、prompt、case 输入和 repo SHA。
- Baseline/candidate tools 相同，技能差异冻结为六个文件；snapshot 树哈希已复算并记录。
- Grader 的三次协议修复只移除了题面未规定的表示假设，旧结果保留；正式样本统一由最终 evaluator 重评。
- 每次运行保存 grading、measurement、timing、transcript 和 rollout SHA provenance。
- 原始 rollout 位于本机 Codex session 目录，仓库保存文件名与 SHA-256；因此 Token 可在当前机器复核，但仅凭仓库 clone 不能重建原始 telemetry。
- `skill-creator` quick validation 对 x-spec3、x-req3、x-qa-gate、x-fix 通过；评测快照中的 x-dev 因旧触发示例使用尖括号而被元数据规则拒绝。正式结果提交后，live x-dev 已用单独的元数据提交去除尖括号并通过验证；评测 snapshot 保持字节不变，这项规范化不计入性能结论。
- Candidate 的 100 分表示冻结的 20 项契约全部通过，不代表穷尽所有可能的 mutation 强度。Baseline 的深层证据循环确实发现了 grader 之外的测试覆盖要求；候选选择以单轮 reviewer + 确定性回归限制这种无界扩张。
