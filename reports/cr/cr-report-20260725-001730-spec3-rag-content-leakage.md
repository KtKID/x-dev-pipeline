# Correctness Review 报告

> Report ID: 20260725-001730
> Mode: module-review
> Scope: module
> Task ID: spec3-rag-content-leakage
> Review 日期：2026-07-25
> 审查范围：iteration-7 的 `x-spec3`、`x-adversarial-risk` 及直接 RAG 检索链路

## 调查对象

| 字段 | 内容 |
|------|------|
| 模式 | 模块正确性 review |
| 用户现象 | 通用于各类功能开发的 skill 可能包含特定功能的风险描述，诱导 LLM 命中特定题目答案 |
| 期望行为 | skill 正文保持跨功能通用；具体功能只能作为明确标注的反向思考示例；RAG 只提供与当前任务相关且可判为适用的经验 |
| 实际行为 | `risk-mistakes.md` 的 5 条内容集中对应 Journal Index Recovery；Top5 在五条语料上会返回全部内容，且检索器无最低相关度门槛 |
| 原始 spec 来源 | 用户当前消息；iteration-7 的目标 skill 与检索实现 |

## 修改文件 / 审查范围

| 文件 | 角色 | 说明 |
|------|------|------|
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-spec3/SKILL.md` | skill | Spec 生成与风险召回路由 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-spec3/templates/spec.md` | template | Spec 固定输出形态 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/SKILL.md` | skill | 对抗性审查执行契约 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references/risk-mistakes.md` | data | RAG 错题语料 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-dev-rag-call/scripts/rag_retrieve.py` | implementation | TopN 排序与返回 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/scripts/risk_contract.py` | validator | 错题集机械校验 |

## 贝叶斯根因调查

| H | 先验 | 证据 E | 影响 | 更新后置信度 | 下一步 |
|---|------|--------|------|--------------|--------|
| H1：`x-spec3` 正文直接包含某道题的风险答案 | 中 | 正文只出现通用的恢复、幂等、并发、故障等风险类别 | 削弱 | 低 | 保留为通用反向思考示例 |
| H2：`x-adversarial-risk` 的 RAG 语料集中绑定 Journal Index Recovery | 高 | 五条分别覆盖多阶段持久化、snapshot、log tail、request_id、CLI error contract，并与题面逐项对应 | 支持 | 已确认 | 拆分通用 skill 与领域语料 |
| H3：Top5 只返回与当前任务足够相关的条目 | 中 | 语料总数为 5；检索器直接截取 `min(top_n, len(ranked))`，不返回 score，也无阈值 | 削弱 | 已确认不成立 | 增加足够大的跨领域语料和适用性门禁 |
| H4：现有 validator 能阻止任务语义进入语料 | 低 | validator 仅禁止证据路径标记，未检查领域集中度或题面重合 | 削弱 | 低 | 增加 corpus 通用性/来源隔离检查 |

### 已排除假设

| H | 排除证据 |
|---|----------|
| `x-spec3/templates/spec.md` 包含 Journal Index Recovery 答案 | 模板只定义 RAG 查询、来源和 Scenario 追踪字段，没有 snapshot、log、request_id 等具体答案 |
| `x-adversarial-risk/SKILL.md` 中的风险类别已经构成特定题答案 | 状态跳跃、崩溃窗口、乱序、权限、敏感数据、并发和部分失败属于跨领域反向思考类别 |

## Spec 对照

| 项 | 原始 spec / 契约 | 当前实现 / 行为 | 分类 | 证据 |
|----|------------------|----------------|------|------|
| skill 跨功能复用 | 不指定某个功能，具体内容只作为明确示例 | 运行时错题集全部来自同一持久化恢复功能族 | 原始 spec 不一致 | `risk-mistakes.md:5-28` |
| Top5 语义 | 返回当前任务最相关的五条经验 | 五条语料时每次返回全库，相关度只决定顺序 | 实现过程偏移 | `rag_retrieve.py:215-248` |
| RAG 内容边界 | 经验只能作为反向检查候选 | skill 要求按顺序使用全部返回正文；语料未标记为“仅作思考触发、需独立证据确认” | spec 缺口 | `x-adversarial-risk/SKILL.md:51,85` |
| 过程可审计 | 记录查询、来源、CLI 和 Scenario 映射 | 模板与 skill 明确记录 RAG 过程 | 符合 spec | `templates/spec.md:70-74` |

## 审查结论

### P0：已确认正确性错误

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ❌ | spec 对照 | 通用 skill 的任务语义隔离 | `risk-mistakes.md:5` | 已确认 | 原始 spec 不一致 | 五条运行时语料集中对应同一 Journal Index Recovery 功能，Top5 会向每个任务返回全部五条 |

### P1：生产正确性风险

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ⚠️ | 调用链 | 无相关度门槛的 Top5 | `rag_retrieve.py:215` | 已确认 | 实现过程偏移 | 无关任务也会收到五条持久化恢复风险，产生注意力污染和无效对抗分析 |

### P2：正确性证据缺口

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ⚠️ | validator | 语料通用性门禁 | `risk_contract.py:58` | 已确认 | spec 缺口 | 当前校验只禁止本地路径等标记，无法阻止单一题目语义集中进入通用 skill |

## 问题详情

### B1：RAG 全库构成 Journal Index Recovery 的定向风险提示

**来源**：用户契约 + 文件对照 + 检索调用链
**文件**：`skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references/risk-mistakes.md`
**位置**：第 5-28 行
**严重程度**：P0
**根因分类**：原始 spec 不一致
**置信度**：已确认

**问题描述**：
五条语料分别描述多阶段持久化崩溃、snapshot 语义状态、log tail 状态迁移、request_id 失败重试和 CLI error response。公开题面分别在 `02-recovery-and-compaction.md`、`01-record-and-state.md`、`03-cli-and-concurrency.md` 定义同一组功能。语料以运行时知识源参与生成，不属于旁观式示例。

**反证检查**：
`x-spec3/SKILL.md`、`templates/spec.md` 和 `x-adversarial-risk/SKILL.md` 正文中的通用风险分类没有出现 Journal Index Recovery 名称、文件名或接口名。具体语义集中位于 RAG 语料。

**影响**：
在该 benchmark 上形成答案提示；在其他功能上形成领域偏置。Top5 等于全库，检索只改变五条内容的顺序。

**修复建议**：
把通用 skill、跨领域通用错题库、benchmark/项目私有语料分层。通用库覆盖多个互不相关领域，每条标注 `example` 与适用条件；任务私有语料由调用方显式传入，避免随通用 skill 分发。

### B2：Top5 缺少相关度和适用性门禁

**来源**：代码路径
**文件**：`skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-dev-rag-call/scripts/rag_retrieve.py`
**位置**：第 215-248 行
**严重程度**：P1
**根因分类**：实现过程偏移
**置信度**：已确认

**问题描述**：
检索器计算 dot-product 后直接返回前 N 条正文；score 只用于内部排序。语料少于或等于 N 时全量返回。

**影响**：
“Top5”表达固定数量，无法表达“最多五条且必须相关”。无关条目仍进入 LLM 上下文和对抗分析。

**修复建议**：
继续保留 Top5 上限，同时返回 score 并加入最低相关度或相对差距门槛。skill 对每条执行 `applicable / irrelevant` 判断，只允许 `applicable` 条目影响 Scenario。

### B3：语料校验缺少领域集中度规则

**来源**：validator
**文件**：`skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/scripts/risk_contract.py`
**位置**：第 58-62、434-449 行
**严重程度**：P2
**根因分类**：spec 缺口
**置信度**：已确认

**问题描述**：
校验器能发现本地证据路径，无法发现语料全部来自一个功能、与 benchmark 题面逐项重合、缺少示例标记和适用条件。

**修复建议**：
为共享语料增加来源域、风险族、适用条件和示例标记；测试至少验证多领域分布、Top5 非全库和无关任务不会把单一领域风险标记为适用。

## 汇总

| 等级 | 数量 |
|------|------|
| P0 | 1 |
| P1 | 1 |
| P2 | 1 |

## 最终结论

- 当前 `x-spec3` 正文与模板暴露 RAG 流程和追踪字段，没有暴露具体 Journal Index Recovery 答案。
- 当前 `x-adversarial-risk` 的运行时语料暴露了与该任务逐项对应的五条风险内容。
- 通用反向思考示例可以保留；运行时语料需要跨领域化、明确示例身份，并增加相关度与适用性门禁。
- 源码保持未修改。
