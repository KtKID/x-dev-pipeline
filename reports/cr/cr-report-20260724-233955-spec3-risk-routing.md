# Correctness Review 报告

> Report ID: 20260724-233955
> Mode: module-review
> Scope: module
> Review 日期：2026-07-24
> 审查范围：iteration-7 的 x-spec3、x-adversarial-risk、风险契约 validator 与交接门禁

## 调查对象

| 字段 | 内容 |
|---|---|
| 模式 | 模块正确性 review |
| 用户现象 | `templates/spec.md` 固定出现 RAG 审查字段，LLM 容易把所有 Spec 都扩展成 RAG 对抗流程；对抗审查缺少严格成本上限 |
| 期望行为 | 复杂度与重要性先决定审查预算；低风险任务保持轻量；deep/full 的对抗推理具有机械上限；低成本风险查询可以独立执行 |
| 实际行为 | standard 的路由已经跳过对抗 Scenario 扩展；模板仍固定暴露 RAG 查询、召回和 CLI 字段；deep/full 的 Scenario 扩展数量缺少 validator 上限 |
| 原始 spec 来源 | 用户消息；iteration-7 的 x-spec3 与 x-adversarial-risk 契约 |

## 修改文件 / 审查范围

| 文件 | 角色 | 说明 |
|---|---|---|
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-spec3/templates/spec.md` | docs/template | Spec 输出模板 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-spec3/SKILL.md` | workflow | 评分、预算与交接规则 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/SKILL.md` | workflow | 检索、对抗分析、修改与验证轮次 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/scripts/risk_contract.py` | validator | 评分、状态、来源与审查记录门禁 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/tests/test_adversarial_risk.py` | test | 风险契约回归测试 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-req3/SKILL.md` | downstream | x-req3 交接门禁 |

---

## 贝叶斯根因调查

| H | 先验 | 证据 E | 影响 | 更新后置信度 | 下一步 |
|---|---|---|---|---|---|
| H1：评分路由缺失，导致所有任务进入对抗审查 | 中 | `x-spec3/SKILL.md:78-81` 已定义 standard/deep/full，standard 使用 `skipped-standard`；validator 测试通过 | 削弱 | 低 | 保留评分路由 |
| H2：RAG 实现细节进入 Spec 稳定模板，形成流程诱导 | 高 | `templates/spec.md:70-74` 固定包含风险来源、查询、召回 ID、CLI；`x-spec3/SKILL.md:107,122,128` 重复强化 RAG 流程 | 支持 | 已确认 | 把检索过程移出 Spec 模板 |
| H3：deep/full 缺少可执行的工作量上限 | 高 | `risk_contract.py:249-337` 只检查审查记录存在、Scenario 来源格式与 ID；内存构造的 deep + 5 条对抗 Scenario 返回零 issue | 支持 | 已确认 | validator 强制候选、反例和新增 Scenario 上限 |
| H4：RAG 本身构成主要 token 成本 | 中 | 错题集当前只有 5 条、1388 字节；Top1 只返回一条短正文；run-summary 缺少 token telemetry | 削弱 | 低 | 把 RAG 视作低成本候选查询，单独控制后续推理成本 |
| H5：失败后的五轮重启放大重复成本 | 中 | `x-adversarial-risk/SKILL.md:119-121` 要求修正调用重新开始五轮，包含重新召回或复用判断 | 支持 | 高 | 机械修复复用同一次查询与候选，禁止新增语义审查轮 |

### 已排除假设

| H | 排除证据 |
|---|---|
| 评分完全失效 | `expected_budget()` 与 standard 零对抗 Scenario 测试均正常；当前问题集中在模板耦合和预算上限 |

---

## Spec 对照

| 项 | 原始 spec / 契约 | 当前实现 / 行为 | 分类 | 证据 |
|---|---|---|---|---|
| 低风险路由 | 低分任务保持轻量 | standard 使用 `skipped-standard` 且允许零对抗 Scenario | 符合 spec | `x-spec3/SKILL.md:78-81`；`test_adversarial_risk.py:121-136` |
| Spec 模板职责 | Spec 保存实现与验收契约 | 模板保存查询文本、召回 ID、CLI 结果等执行遥测 | spec 缺口 | `templates/spec.md:70-74` |
| deep/full 成本上限 | 对抗检查按任务分数限制规模 | validator 接受 deep + 5 条对抗 Scenario | spec 缺口 | `risk_contract.py:249-337`；内存验证输出 `[]` |
| 检索失败语义 | 检索是风险候选来源 | deep/full 检索失败会保持 pending 并阻断 x-req3 | 需重新定义 | `x-adversarial-risk/SKILL.md:85` |
| 修复重试 | 修复机械问题 | 修正调用重新进入五轮执行 | 实现过程偏移 | `x-adversarial-risk/SKILL.md:119-121` |

---

## 审查结论

### P0：已确认正确性错误

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|---|---|---|---|---|---|---|
| ✅ | 代码路径 | 核心路由 | - | 高 | 符合 spec | standard 已能跳过对抗 Scenario 扩展 |

### P1：生产正确性风险

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|---|---|---|---|---|---|---|
| ⚠️ | 模板与 workflow | 稳定契约耦合执行机制 | `templates/spec.md:70-74` | 已确认 | spec 缺口 | RAG 查询、召回与 CLI 字段固定进入每份 Spec，诱导模型执行具体流程并污染下游契约 |
| ⚠️ | validator | 对抗审查数量上限 | `risk_contract.py:249-337` | 已确认 | spec 缺口 | deep/full 没有候选、反例、新增 Scenario 的机械上限，预算只有标签 |
| ⚠️ | workflow | 失败修复轮次 | `x-adversarial-risk/SKILL.md:119-121` | 高 | 实现过程偏移 | validator 修复可以重启完整语义审查，产生重复检索、推理和 patch |

### P2：正确性证据缺口

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|---|---|---|---|---|---|---|
| ⚠️ | benchmark artifact | token 成本 | `artifacts/run-summary.json` | 高 | 证据不足 | 当前 run-summary 记录 RAG 命中与 Scenario 变化，缺少各阶段 token 和耗时 |
| ⚠️ | 评分语义 | importance 锚点 | `x-spec3/SKILL.md:76-79` | 中 | spec 缺口 | importance 主要按受众范围评分，单用户数据损坏等高损失场景容易低估 |

---

## 问题详情

### B1：Spec 模板泄漏检索实现细节

**严重程度**：P1
**根因分类**：spec 缺口
**置信度**：已确认

`spec.md` 是目标、边界、不变量、Scenario 与验收的长期事实源。查询文本、召回命中、CLI 退出码属于一次执行的过程遥测。当前模板把两类信息固定在同一文档中，使 LLM 先看到 RAG 形态，再判断任务是否需要风险审查。

**修复建议**：

- `spec.md` 只保留 `review_budget`、`adversarial_review` 和经过审查后真正改变契约的 Scenario 来源。
- 查询、命中、CLI、复用/新增计数写入 `artifacts/risk-review.json`。
- Scenario 来源使用机制中立格式 `adversarial-review (risk:<id>)`，检索实现可以在直接读取、关键词匹配和向量 RAG 之间替换。

### B2：预算标签缺少工作量上限

**严重程度**：P1
**根因分类**：spec 缺口
**置信度**：已确认

当前 validator 能验证分数映射、状态与来源格式，也能接受 deep 预算附带 5 条对抗 Scenario。模型收到“Scenario 数量由实际区分缺口决定”后拥有开放式扩张空间。

**修复建议**：

| 预算 | 风险候选查询 | 对抗 challenge | 独立假设 | 新增或收紧 Scenario |
|---|---:|---:|---:|---:|
| standard | 1 | 0 | 0 | 0 |
| deep | 1 | 最多 1 | 0 | 最多 1 |
| full | 1 | 最多 2 | 最多 1 | 最多 2 |

已有 Scenario 能区分正确与错误实现时只记录复用。候选需要同时满足语义相关、路径可达、会破坏当前不变量三个条件，才占用 challenge 名额。validator 直接校验上表计数。

### B3：检索与对抗推理需要两阶段决策

**严重程度**：P1
**根因分类**：spec 缺口
**置信度**：高

一次 Top1 候选查询的上下文成本很小。把候选转成最小反例、扩展不变量、修改 Scenario、重跑验证构成主要推理成本。

**修复建议**：

1. 先按任务事实计算初始分数。
2. 每次执行一次低成本风险候选查询。
3. standard 只做适用性判断；相关候选揭示新事实时重算分数。
4. deep/full 按上表消耗 challenge 名额。
5. 机械验证失败复用同一候选与同一审查结论，只修格式和一致性。

### B4：评分应表达预期损失

**严重程度**：P2
**根因分类**：spec 缺口
**置信度**：中

复杂度可作为缺陷概率代理，重要性应表达失败损失。受众数量只是损失的一项证据。

**建议映射**：

- 基础分使用 `complexity + importance`：2–5 为 standard，6–7 为 deep，8–10 为 full。
- complexity=5 或 importance=4 时至少 deep。
- importance=5，或资金、隐私、合规、安全、广泛不可逆数据损失时为 full。
- 并发、崩溃恢复、迁移、鉴权边界至少 deep。
- 检索命中只能在“当前路径可达且影响可观察不变量”时改变复杂度；importance 继续由任务实际损失决定。

---

## 推荐目标流程

```text
任务事实
  → 初始 complexity + importance
  → 一次低成本 risk lookup
  → 适用性门禁
      → standard：记录 lookup，零对抗扩展
      → deep：一个最小反例，最多一条 Scenario 变化
      → full：两个互异 challenge，最多两条 Scenario 变化
  → 一次集中 patch
  → 一次语义验证
  → 机械修复复用原审查证据
  → x-req3
```

当前错题集只有 5 条、1388 字节。现阶段可以一次读取全部风险卡；目录增长后切换 Top1 向量召回。调用接口保持 `risk lookup`，Spec 模板无需感知检索实现。

## 实施顺序

1. 修改 `x-spec3/templates/spec.md`：移除固定 RAG 表格，只保留结果状态。
2. 修改 `x-spec3/SKILL.md`：明确“两阶段决策”和 standard/deep/full 数量上限。
3. 修改 `x-adversarial-risk/SKILL.md`：固定 challenge 名额；机械修复复用已有检索结果。
4. 修改 `risk_contract.py`：校验预算上限、状态与 sidecar 计数。
5. 修改 `x-req3/SKILL.md`：按审查结果和上限门禁，解除对 `rag:` 来源格式的强绑定。
6. 更新 `test_adversarial_risk.py`：增加 standard 零扩展、deep 超 1 拒绝、full 超 2 拒绝、修复轮不重新召回。
7. 运行 iteration-7 全部测试与一个 standard、deep、full 对照 eval，记录每阶段 token、耗时、Scenario 变化数。

## 汇总

| 等级 | 数量 |
|---|---:|
| P0 | 0 |
| P1 | 3 |
| P2 | 2 |

## 最终结论

- 评分路由主体可保留。
- 一次低成本风险查询适合默认执行。
- 对抗推理按 standard/deep/full 设置机械数量上限。
- Spec 保存契约结果，sidecar 保存查询与执行遥测。
- 当前优先修复模板耦合、预算上限和失败重启三处。
