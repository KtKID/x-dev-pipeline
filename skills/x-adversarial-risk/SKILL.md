---
name: x-adversarial-risk
description: |
  对 x-spec 产出的 Spec 做一次有轮次上限的风险复核：读取 Spec、生成“功能关键词 + Risk”查询，默认从本 skill 自带的风险语料召回 Top5，也接受调用方覆盖语料路径；用户确认跳过 RAG 时，按 Spec 分数执行有上限的独立对抗性检验。用于 review_budget 为 deep/full 且 adversarial_review 为 pending、上一次验证返回聚合 issue，或用户显式要求推翻 Spec 假设、补充高价值风险 Scenario 的场景。
---

# x-adversarial-risk

在 `x-spec → x-req` 之间执行一次增量审查。风险语料可用时召回相关度最高的最多五条经验；用户确认跳过 RAG 时直接从 Spec 推导故障假设。两条路径都构造能区分正确实现与常见错误实现的最小反例。

## 输入与边界

输入为一个 `docs/spec/<spec-name>/spec.md`。本轮只修改该文件。

Spec 是事实输入。Spec 证据不足以支持新行为时保留现有契约，并在回执中报告证据缺口。项目文件、任务原文、实现代码、QA 报告和脚本源码留给后续独立流程。

当前已加载的 `x-adversarial-risk/SKILL.md` 所在目录是 `ADVERSARIAL_RISK_SKILL_DIR`。默认风险语料位于 `${ADVERSARIAL_RISK_SKILL_DIR}/references/risk-catalog.md`。调用方显式提供文件或目录时使用该路径覆盖默认值；默认文件缺失、为空或不可读时报告具体问题。

当前已加载的 `x-dev-rag-call/SKILL.md` 所在目录是 `RAG_SKILL_DIR`。召回脚本固定从 `${RAG_SKILL_DIR}/scripts/rag_retrieve.py` 读取。两个根目录都来自当前 plugin 实际加载的 skill 路径，与调用项目 cwd 解耦。

`x-dev-rag-call` 读取选定语料并返回 TopN 的 `id + source + text`；当前 agent 直接使用返回正文，省去整库阅读、LLM 精排、经验改写和按 ID 二次读取。用户明确确认跳过 RAG 时进入无 RAG 路径。

agent 使用上述默认语料或调用方覆盖路径，不扫描工作区寻找其他候选语料。

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

风险语料可用时，`deep` 和 `full` 都使用默认 Top5，并按返回的最多五条正文逐条完成适用性判断；`full` 在召回候选之外，再增加一个由当前 Spec 独立推导的故障假设。

用户确认跳过 RAG 时，预算直接控制独立对抗性检验：

- `standard`：保持零对抗性 Scenario 扩张，由 x-spec 直接交接。
- `deep`：从 Spec 选择最高风险不变量，执行 1 个独立故障假设。
- `full`：从 Spec 选择两个不同故障轴，执行最多 2 个独立故障假设。

每个假设先与现有 Scenario 去重，只在存在区分缺口时新增或收紧 Scenario。

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

设置 skill 根目录和本轮语料路径。调用方显式提供路径时替换 `RISK_CORPUS`，随后调用相邻的 `x-dev-rag-call`：

```bash
ADVERSARIAL_RISK_SKILL_DIR="<当前已加载的 x-adversarial-risk/SKILL.md 所在目录>"
RAG_SKILL_DIR="<当前已加载的 x-dev-rag-call/SKILL.md 所在目录>"
RISK_CORPUS="${ADVERSARIAL_RISK_SKILL_DIR}/references/risk-catalog.md"

uv run --offline --isolated \
  --with "sentence-transformers>=2.7.0" \
  --with "transformers>=4.51.0,<5" \
  python "${RAG_SKILL_DIR}/scripts/rag_retrieve.py" \
  --source "${RISK_CORPUS}" \
  --query "功能关键词：<功能、模块、状态、动作>
Risk：<具体失败机制>" \
  --top-n 5 \
  --model "Qwen/Qwen3-Embedding-0.6B" \
  --json
```

成功输出包含最多五条 `matches[].id`、`matches[].source` 和 `matches[].text`。命令从本地模型缓存加载 `Qwen/Qwen3-Embedding-0.6B`，并通过 `local_files_only=True` 禁止联网下载。查询使用官方 `query` 提示模板，风险语料正文按普通文档编码，两侧向量都归一化。需要指定其他本地模型时替换 `--model` 的值。

召回成功后按命中顺序使用全部正文完成适用性判断、最小反例构造、Scenario 去重和最终修改集合设计，并在 Spec 审查记录中写明实际采用的 `RAG:AR-NNN`。默认语料不可用或召回失败时保持 `adversarial_review: pending`，记录实际语料路径、退出码、`error` 和 `message`，并阻断 x-req。

用户确认跳过 RAG 后，本轮省略召回命令，按 `deep` 或 `full` 上限完成独立假设，并在审查记录中写入 `CLI=skipped:no-corpus`。该确认只替代 RAG 召回，评分和对抗性预算继续生效。

### 第 3 轮：集中修改

使用一个 patch 完成全部变化，范围只包含：

1. 评分字段及“风险评分依据”中的必要纠正。
2. 新 Scenario 直接依赖的不变量或 J-ID。
3. 对应验收项与测试驱动顺序。
4. 对抗性审查记录和状态。
5. 区分缺口要求的最小新增 Scenario 集合。

每个新增 Scenario 包含 GIVEN、唯一 WHEN、可观察 THEN、测试层和依据。RAG 召回错题来源格式：

```text
- 来源：adversarial-review (rag:AR-001)
```

无 RAG 路径的独立假设使用：

```text
- 来源：adversarial-review (assumption:<短说明>)
```

### 第 4 轮：验证

RAG 路径运行：

```bash
ADVERSARIAL_RISK_SKILL_DIR="<当前已加载的 x-adversarial-risk/SKILL.md 所在目录>"
RISK_CORPUS="${ADVERSARIAL_RISK_SKILL_DIR}/references/risk-catalog.md"

python3 "${ADVERSARIAL_RISK_SKILL_DIR}/scripts/risk_contract.py" \
  validate-review docs/spec/<spec-name>/spec.md \
  --catalog "${RISK_CORPUS}" \
  --require-rich-fields \
  --json
```

调用方覆盖语料时同步替换 `RISK_CORPUS`。验证命令聚合 Spec、风险语料完整字段、来源映射和其他机械问题。验证失败时保持阻断状态，并在回执中列出完整聚合 issue。

用户确认跳过 RAG 时运行：

```bash
ADVERSARIAL_RISK_SKILL_DIR="<当前已加载的 x-adversarial-risk/SKILL.md 所在目录>"

python3 "${ADVERSARIAL_RISK_SKILL_DIR}/scripts/risk_contract.py" \
  validate-spec docs/spec/<spec-name>/spec.md --json
```

该命令验证评分、审查状态和 `assumption` 来源。验证通过后把 `adversarial_review` 设置为 `complete`。

修正调用开始新的五轮执行：读取当前 Spec 和 skill，复用上一次 issue，重新召回或复用相同查询结果，一次修完、复验并回执。

### 第 5 轮：回执

直接返回：

- 目标 Spec。
- complexity、importance、risk_average 和 review_budget。
- 查询关键词和 Risk。
- RAG 路径返回 CLI 退出码、召回 ID 和召回数量；无 RAG 路径返回 `skipped:no-corpus`。
- 复用与新增 Scenario ID。
- 读取、召回、修改和验证结果。
- x-req 交接状态或阻断 issue。

回执后结束本轮。

## 审查记录

在 `## 对抗性审查记录` 中维护：

| Review | 预算 | 风险来源 | 查询 | 召回 ID | 复用 Scenario | 新增 Scenario | CLI |
|---|---|---|---|---|---|---|---|
| ARV-1 | deep / full | RAG:AR-NNN / assumption:<短说明> | <关键词；Risk> | <AR-NNN, ...> | <SC_NN / 无> | <SC_NN / 无> | exit=0; matches=<1..5> |
| ARV-1 | deep / full | assumption:<短说明> | 无 RAG 经验集 | 无 | <SC_NN / 无> | <SC_NN / 无> | skipped:no-corpus |

重复调用依据查询、召回 ID、既有记录和 Scenario 来源判断增量。相同 Spec、查询、模型和风险语料产生相同 ID 顺序。
