---
name: x-adversarial-risk
description: |
  对 x-spec3 产出的 Spec 做一次有轮次上限的风险复核：读取 Spec、生成“功能关键词 + Risk”查询、通过 x-dev-rag-call 从指定错题集 RAG 召回一条风险、显式记录风险来源、集中修改、验证并回执。用于 review_budget 为 deep/full 且 adversarial_review 为 pending、上一次 validate-review 返回聚合 issue，或用户显式要求推翻 Spec 假设、补充高价值风险 Scenario 的场景。
compatibility: Requires Python 3. Semantic retrieval requires sentence-transformers and an embedding model already available on local disk.
---

# x-adversarial-risk

在 `x-spec3 → x-req3` 之间执行一次增量审查。目标是用语义匹配召回最相关的一条历史错题，再构造能区分正确实现与常见错误实现的最小反例。

## 输入与边界

输入为一个 `docs/spec/<spec-name>/spec.md`。本轮只修改该文件。

Spec 是事实输入。Spec 证据不足以支持新行为时保留现有契约，并在回执中报告证据缺口。项目文件、任务原文、实现代码、QA 报告和脚本源码留给后续独立流程。

`references/risk-mistakes.md` 是纯文本错题集。`x-dev-rag-call` 读取指定路径并返回 TopN 的 `id + source + text`；当前 agent 直接使用返回正文，省去整库阅读、LLM 精排、经验改写和按 ID 二次读取。

## 对抗性定义

1. 选择损失最高或最容易被错误实现破坏的不变量。
2. 从 Spec 提炼一组功能关键词和一句具体 Risk。
3. 使用“功能关键词 + Risk”做向量召回。
4. 用召回正文破坏一个关键前提，构造最小输入、状态、时序或故障窗口。
5. 比较正确实现与常见错误实现的可观察结果。
6. 现有 Scenario 已能区分两者时复用；仍有区分缺口时新增最小 Scenario。

候选按“影响 × 发生可能性 × 区分能力”排序。重点关注状态跳跃、崩溃窗口、重复或乱序、权限边界、敏感数据、并发交错、资源耗尽和部分失败。

## 风险预算

根据 Spec 已记录事实独立重算 complexity、importance、risk_average 和 review_budget：

| 分数 | complexity 锚点 | importance 锚点 |
|---:|---|---|
| 1 | 单点数据改写或简单 CRUD | 本地、单用户、内部非核心工具 |
| 2 | 单体校验或少量顺序分支 | 小范围内部日常能力 |
| 3 | 状态机、复杂分支或外部交互 | 全用户可用的非核心能力 |
| 4 | 核心高损失链路或多组件一致性 | 全用户核心链路 |
| 5 | 锁、幂等、跨进程并发、崩溃恢复、多阶段持久化提交或核心算法任一项 | 资金、隐私、合规或生命线 |

预算映射：

- `average < 3` → `standard`
- `3 <= average < 4` → `deep`
- `average >= 4` → `full`
- 任一维度为 4 → 至少 `deep`
- 任一维度为 5 → `full`

`deep` 和 `full` 首版都使用默认 Top1。`full` 在召回候选之外，再增加一个由当前 Spec 独立推导的故障假设。Scenario 数量由实际区分缺口决定。

## 五轮执行契约

### 第 1 轮：读取并生成查询

调用方使用一个批量工具调用完整读取：

1. 本 `SKILL.md`。
2. 目标 Spec。

读取完成后：

- 重算评分和预算。
- 复核前七个 `> key: value` 元数据字段。
- 检查现有 Scenario 覆盖。
- 从功能、模块、状态和关键动作提炼一组关键词。
- 把最高价值的具体失败机制写成一句 Risk。

### 第 2 轮：向量召回

调用相邻的 `x-dev-rag-call`，运行：

```bash
python3 <iteration-7-skills>/x-dev-rag-call/scripts/rag_retrieve.py \
  --source <skill-dir>/references/risk-mistakes.md \
  --query "功能关键词：<功能、模块、状态、动作>
Risk：<具体失败机制>" \
  --top-n 1 \
  --json
```

成功输出包含 `matches[].id`、`matches[].source` 和 `matches[].text`。默认模型为 `iteration-7/models/Qwen3-Embedding-0.6B/` 下的 `Qwen/Qwen3-Embedding-0.6B`，运行时只加载本地文件。查询使用官方 `query` 提示模板，错题正文按普通文档编码，两侧向量都归一化。需要指定其他本地模型时增加 `--model <本地路径或本地模型名>`。

召回成功后直接使用正文完成适用性判断、最小反例构造、Scenario 去重和最终修改集合设计，并在 Spec 审查记录中写明 `RAG:<risk-id>`。召回失败时保持 `adversarial_review: pending`，记录退出码、`error` 和 `message`，并阻断 x-req3。

### 第 3 轮：集中修改

使用一个 patch 完成全部变化，范围只包含：

1. 评分字段及“风险评分依据”中的必要纠正。
2. 新 Scenario 直接依赖的不变量或 J-ID。
3. 对应验收项与测试驱动顺序。
4. 对抗性审查记录和状态。
5. 区分缺口要求的最小新增 Scenario 集合。

每个新增 Scenario 包含 GIVEN、唯一 WHEN、可观察 THEN、测试层和依据。RAG 召回错题来源格式：

```text
- 来源：adversarial-review (rag:A-risk-001)
```

历史 Spec 中的 `AR-nnn; pattern:<标签>` 来源继续有效。独立假设使用：

```text
- 来源：adversarial-review (assumption:<短说明>)
```

### 第 4 轮：验证

运行：

```bash
python3 <skill-dir>/scripts/risk_contract.py \
  validate-review docs/spec/<spec-name>/spec.md \
  --catalog <skill-dir>/references/risk-mistakes.md --json
```

验证命令聚合 Spec、错题格式和来源映射的全部机械问题。验证失败时保持阻断状态，并在回执中列出完整聚合 issue。

修正调用开始新的五轮执行：读取当前 Spec 和 skill，复用上一次 issue，重新召回或复用相同查询结果，一次修完、复验并回执。

### 第 5 轮：回执

直接返回：

- 目标 Spec。
- complexity、importance、risk_average 和 review_budget。
- 查询关键词和 Risk。
- CLI 退出码、召回 ID 和召回数量。
- 复用与新增 Scenario ID。
- 读取、召回、修改和验证结果。
- x-req3 交接状态或阻断 issue。

回执后结束本轮。

## 审查记录

在 `## 对抗性审查记录` 中维护：

| Review | 预算 | 风险来源 | 查询 | 召回 ID | 复用 Scenario | 新增 Scenario | CLI |
|---|---|---|---|---|---|---|---|
| ARV-1 | deep / full | RAG:<A-risk-nnn> / assumption:<短说明> | <关键词；Risk> | <A-risk-nnn> | <SC_NN / 无> | <SC_NN / 无> | exit=0; matches=1 |

重复调用依据查询、召回 ID、既有记录和 Scenario 来源判断增量。相同 Spec、查询、模型和错题集产生相同 ID 顺序。
