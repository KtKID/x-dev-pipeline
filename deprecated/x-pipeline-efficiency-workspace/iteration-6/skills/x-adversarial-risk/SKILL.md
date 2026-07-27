---
name: x-adversarial-risk
description: |
  对 x-spec3 产出的 Spec 做一次有轮次上限的风险复核：读取一次、集中修改一次、验证一次、回执一次。用于 review_budget 为 deep/full 且 adversarial_review 为 pending、上一次 validate-review 返回聚合 issue，或用户显式要求推翻 Spec 假设、补充高价值风险 Scenario 的场景。
---

# x-adversarial-risk

在 `x-spec3 → x-req3` 之间执行一次增量审查。目标是找出少量能区分正确实现与常见错误实现的反例，同时保持已有需求语义和 Scenario ID 稳定。

## 输入与边界

输入为一个 `docs/spec/<spec-name>/spec.md`。本轮只修改该文件。

Spec 是本轮唯一事实输入。Spec 证据不足以支持新行为时保留现有契约，并在回执中报告证据缺口。项目文件、任务原文、实现代码、QA 报告和脚本源码留给后续独立流程。

`references/risk-mistakes.md` 是五类通用风险的短示例卡。`deep` 和 `full` 在读取轮次中与 Spec 一起读取；示例卡只提供候选构造方法，适用性与可观察结果均由当前 Spec 决定。

## 对抗性定义

对抗性检查按以下算法生成候选：

1. 选择损失最高或最容易被错误实现破坏的不变量。
2. 写出该不变量成立依赖的前提。
3. 每次只破坏一个前提，构造最小输入、状态、时序或故障窗口。
4. 比较正确实现与最可能错误实现的可观察结果。
5. 现有 Scenario 已能区分两者时复用；仍有区分缺口时才新增。

候选按“影响 × 发生可能性 × 区分能力”排序，优先覆盖状态跳跃、崩溃窗口、重复或乱序、权限边界、敏感数据、并发交错、资源耗尽和部分失败。

## 风险预算

根据 Spec 已记录事实独立重算 complexity、importance、risk_average 和 review_budget，以重算结果更新 Spec：

| 分数 | complexity 锚点 | importance 锚点 |
|---:|---|---|
| 1 | 单点数据改写或简单 CRUD | 本地、单用户、内部非核心工具 |
| 2 | 单体校验或少量顺序分支 | 小范围内部日常能力 |
| 3 | 状态机、复杂分支或外部交互 | 全用户可用的非核心能力 |
| 4 | 核心高损失链路或多组件一致性 | 全用户核心链路 |
| 5 | 锁、幂等、跨进程并发、崩溃恢复、多阶段持久化提交或核心算法任一项 | 资金、隐私、合规或生命线 |

本地单用户内部 CLI 归入 importance 1；“所有调用者都依赖”描述依赖强度，用户影响范围仍按实际受众评分。预算映射为：

- `average < 3` → `standard`
- `3 <= average < 4` → `deep`
- `average >= 4` → `full`
- 任一维度为 4 → 至少 `deep`
- 任一维度为 5 → `full`

预算决定单次推理中的候选搜索深度：

- `standard`：由 x-spec3 直接完成，不调用本 skill。
- `deep`：逐张检查五类短示例卡，聚焦适用的最高损失不变量，统一生成、去重和排序候选。
- `full`：逐张检查五类短示例卡，并增加一个由当前 Spec 独立推导的故障假设，再统一去重和排序。

Scenario 数量由区分缺口决定。已有 Scenario 足够区分正确实现与常见错误实现时直接复用；存在缺口时只增加可改变实现或验证决策的最小 Scenario 集合。

对每张适用示例卡，必须记录一个已有或新增 Scenario ID。候选不适用时记录当前 Spec 中缺少该卡触发信号的具体理由。示例卡 ID 用于追踪覆盖，卡片内容本身不产生需求。

## 四轮执行契约

### 第 1 轮：一次读取

调用方使用一个批量工具调用完整读取以下三份内容：

1. 本 `SKILL.md`。
2. 目标 Spec。
3. 与本 skill 同目录的 `references/risk-mistakes.md`。

该批量调用是对抗审查唯一读取轮次。已经由调用方放入本轮上下文的内容直接复用，skill 内不再读取。

这一轮直接读取正文，省略 `wc`、`find`、`rg` 索引、分段预览和路径探测。相同文件在本轮保持单次读取。

读取完成后在当前推理中完成：

- 评分一致性复核。
- 模板头部格式复核：前七个元数据字段保持 `> key: value` 形式。
- 现有 Scenario 覆盖判断。
- 五张示例卡的适用性、候选反例、覆盖 Scenario、去重和排序。
- 最终修改集合设计。

### 第 2 轮：一次集中修改

使用一个 patch 完成全部变化。修改范围只包含：

1. 评分字段及“风险评分依据”中的必要纠正。
2. 新 Scenario 直接依赖的不变量或 J-ID。
3. 对应验收项与测试驱动顺序。
4. 对抗性审查记录和状态。
5. 区分缺口要求的最小新增 Scenario 集合。

每个新增 Scenario 包含 GIVEN、唯一 WHEN、可观察 THEN、测试层和依据。示例卡来源格式为：

```text
- 来源：adversarial-review (AR-001; pattern:<短标签>)
```

独立假设使用：

```text
- 来源：adversarial-review (assumption:<短说明>)
```

### 第 3 轮：一次验证

使用一个工具调用运行：

```bash
python3 <skill-dir>/scripts/risk_contract.py \
  validate-review docs/spec/<spec-name>/spec.md \
  --catalog <skill-dir>/references/risk-mistakes.md --json
```

验证命令聚合 Spec、示例卡和 v2 来源映射的全部机械问题。该轮省略额外的计数、diff、cmp、JSON 格式化和脚本源码读取。

验证通过时进入回执。验证失败时保持阻断状态，在回执中列出完整聚合 issue，并给出携带这些 issue 重新显式调用 `$x-adversarial-risk` 的修正入口。本轮结束。

修正调用属于新的四轮执行。第 1 轮读取当前 Spec、skill 与示例，并把上一次聚合 issue 作为已知输入；第 2 轮一次修完全部 issue；第 3 轮复跑同一验证命令；第 4 轮回执。当前 Spec 即使已经写入 `complete`，聚合 issue 仍可触发该修正调用。

### 第 4 轮：一次回执

直接返回：

- 目标 Spec。
- complexity、importance、risk_average 和 review_budget。
- 检查候选数与新增/复用 Scenario ID。
- 单次读取、单次修改、单次验证的执行结果。
- x-req3 交接状态或阻断 issue。
- 验证失败时的下一次显式修正调用输入。

回执后结束本轮，不再调用工具。

## 审查记录

在 `## 对抗性审查记录` 中维护：

| Review | 预算 | 检查候选 | 被推翻假设 | 新增 Scenario |
|---|---|---|---|---|
| ARV-1 | deep / full | <AR-nnn / pattern 或无> | <结论或无> | SC_NN / 无 |

重复调用先依据既有记录和 Scenario 来源判断增量。相同 Spec 内容与 skill 版本产生相同结果。
