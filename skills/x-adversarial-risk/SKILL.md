---
name: x-adversarial-risk
description: |
  对 x-spec3 产出的 Spec 做独立风险评分复核和对抗性检验，并把适用风险补成带来源的可执行 Scenario。用于 Spec 含 adversarial_risk_version 且审查状态为 pending、用户要求检查 Spec 风险/推翻假设/补充风险测试，或需要把已有证据和最小反例的 QA 缺口录入风险错题集时。
---

# x-adversarial-risk

在 `x-spec3 → x-req3` 之间运行。把第一版 Spec 当作待推翻假设，按风险预算增加最少且有区分力的反例；保持已有 Scenario ID 和需求语义稳定。

## 输入与边界

接收一个 `docs/spec/<spec-name>/spec.md`。优先读取该文件一次；只有判断会改变评分或反例时，才读取它明确引用的任务或仓库事实。

本 skill 独占读取 `references/risk-mistakes.md`。x-spec3、x-req3、x-dev、x-verify 和 x-qa-gate 均不读取该文件。

执行期间只修改目标 `spec.md`；录入已确认 issue 时才修改错题集。保持 task、实现代码和 QA 报告原样。

## 1. 复核双评分

按实现难度评复杂度：

| 分数 | 锚点 |
|---|---|
| 1 | 简单 CRUD；无复杂状态、事务或外部交互 |
| 2 | 单体校验和简单业务规则 |
| 3 | 状态流转、多条件分支或明显状态机 |
| 4 | 支付、交易、权限等核心链路或高损失一致性 |
| 5 | 多服务、锁、幂等、高并发、崩溃恢复或核心算法 |

按影响评重要性：

| 分数 | 锚点 |
|---|---|
| 1 | 内部工具或管理后台非核心功能 |
| 2 | 面向内部用户的日常功能 |
| 3 | 面向全部用户的非核心功能 |
| 4 | 面向全部用户的核心功能 |
| 5 | 资金、隐私或合规生命线 |

把依据写入 `## 风险评分依据`。计算：

```text
risk_average = (complexity + importance) / 2
```

平均分保留一位小数。预算映射：

- `average < 3` → `standard`
- `3 <= average < 4` → `deep`
- `average >= 4` → `full`
- 任一维度为 4 → 至少 `deep`
- 任一维度为 5 → `full`

更新顶部的 `complexity`、`importance`、`risk_average` 和 `review_budget`，保持字段单一。

## 2. 按预算执行

### standard

检查每项主要风险是否由不变量、验收项或 Scenario 承接，检查所有 Scenario 已标来源。保持错题集未读，保持 Scenario 集合不扩张。

在审查记录写一行 `ARV-n`，将状态改为 `skipped-standard`。

### deep

从当前 Spec 提取动作、数据、场景关键词。先只读取错题索引：

```bash
rg -n '^## AR-|^- (动作维度|数据维度|场景维度)[：:]' \
  skills/x-adversarial-risk/references/risk-mistakes.md
```

读取三个维度至少一个匹配的完整 issue 块。对每个匹配 issue：

1. 映射到当前模块、数据和业务时刻。
2. 构造破坏当前不变量的最小反例。
3. 判断现有 Scenario 能否区分正确与错误实现。
4. 为仍未覆盖且适用的风险追加一个 Scenario。

完成一轮后写审查记录，将状态改为 `complete`。

### full

完整读取 `references/risk-mistakes.md`，先执行 deep 的 issue 回放，再执行一次假设推翻：

1. 列出 Spec 默认成立却缺少证据的假设。
2. 依次尝试状态跳跃、崩溃窗口、重复/乱序、权限绕过、敏感数据泄露、并发交错、资源耗尽和部分失败。
3. 为每个适用假设构造最小反例。
4. 只把能改变实现或验收、且有可观察 THEN 的反例写入 Scenario。

默认由当前 agent 完成两轮判断。用户显式要求人工复核时，把假设清单保留为待确认，维持 `pending`。

## 3. 写入可追溯 Scenario

保留已有 `SC_NN`。从当前最大 ID 后连续追加；按行为和关联 issue 去重。

每个第一版 Scenario 保持：

```text
- 来源：initial-spec
```

错题回放新增 Scenario 使用：

```text
- 来源：adversarial-review (rag:AR-001)
```

同一 Scenario 可引用多个 issue。独立假设推翻使用：

```text
- 来源：adversarial-review (assumption:<简短说明>)
```

每个新增 Scenario 同时补齐 GIVEN、唯一 WHEN、可观察 THEN、测试层和依据，并更新验收清单与测试驱动顺序。风险描述写成“触发条件 → 事故 → 影响”，明确对应不变量。

## 4. 记录审查增量

在 `## 对抗性审查记录` 中维护：

| Review | 预算 | 匹配 issue | 被推翻假设 | 新增 Scenario |
|---|---|---|---|---|
| ARV-1 | deep / full / standard | RAG:AR-NNN / 无 | <结论或无> | SC_NN / 无 |

重复执行时先检查既有记录和 Scenario 来源。相同输入、评分和错题集产生相同 Scenario 集合；无新增风险时记录“无适用新增”，不复制已有内容。

## 5. 机械门禁

修改完成后运行：

```bash
python3 skills/x-adversarial-risk/scripts/risk_contract.py \
  validate-spec docs/spec/<spec-name>/spec.md --json
```

deep/full 还要运行：

```bash
python3 skills/x-adversarial-risk/scripts/risk_contract.py \
  validate-corpus skills/x-adversarial-risk/references/risk-mistakes.md --json
```

退出 1 时在同一编辑批次修完全部 issue，再整体复跑。退出 2 时修正参数、路径或 IO 问题。门禁通过后交接 x-req3。

## 6. 录入已确认错题

只录入同时具备可定位证据和可复现最小反例的问题。证据保存在 QA 或 fix 报告，错题集只保存检索所需内容。先检索相同动作、数据、场景和根因；相同根因更新原条目。

新条目使用下列字段：

```text
## AR-NNN

关键词：<功能、模块、状态、动作>
Risk：<触发条件、失败机制和影响>
```

录入后运行 `validate-corpus`。风险猜测继续留在 QA/fix 证据中，直到证据与反例完整。

## 回执

返回目标 Spec、复杂度/重要性/平均分、预算、错题集读取范围、匹配 issue、被推翻假设、新增或复用的 Scenario ID、门禁结果和 x-req3 交接状态。
