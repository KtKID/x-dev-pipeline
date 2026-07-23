## Context

当前仓库事实：

- x-spec3 直接产出单文件 `spec.md`，已要求风险、不变量、测试层和 Scenario，但风险深度由同一次生成过程自行决定。
- x-req3 直接消费通过就绪门禁的 spec3 包，当前缺少独立的 Spec 风险审查状态。
- QA 能发现固定 evaluator 之外的真实问题；本轮 journal recovery baseline 已暴露 compact 多文件替换窗口、语义快照一致性、逻辑损坏分类和测试证据强度等缺口。
- skills 承担判断，Python 工具承担可重复的机械校验；运行环境要求自包含、标准库可用。

拟议行为：

- x-spec3 第一版给出风险双评分，并把第一版 Scenario 标记为 `initial-spec`。
- x-adversarial-risk 根据评分选择预算；深度与全面预算才读取独立错题集，并把新增 Scenario 标记为 `adversarial-review` 与关联 issue。
- x-req3 对采用新风险契约的 Spec 执行只读机械校验，审查仍为 `pending` 时停止交接。

## Goals / Non-Goals

**Goals:**

- 让 Spec 风险深度与任务复杂度、业务重要性匹配。
- 把已确认的历史缺口转为可检索、可复用、可追溯的对抗性测试知识。
- 清楚区分第一版测试与对抗性审查新增测试。
- 通过渐进加载和确定性校验控制 token 与重复检查。
- 保持现有 spec3 文件和活跃 Q0–Q3 开发路由兼容。

**Non-Goals:**

- 自动把所有 QA issue 写入错题集。
- 用固定规则穷尽全部业务风险或替代人工安全评审。
- 修改 task 的 Q0–Q3 字段、fix-counter 或 QA reviewer 编排。
- 为存量 Spec 批量补写风险元数据。

## Decisions

### 1. 使用独立 `x-adversarial-risk` skill

x-spec3 负责形成第一版契约，x-adversarial-risk 负责尝试推翻该契约的风险假设。职责分离让新增 Scenario 的来源清晰，也允许后续独立迭代风险知识。

备选方案是继续扩充 x-spec3 自审。该方案会把生成与反驳放在同一思路中，历史缺口也会持续占用普通 Spec 的上下文，因此不采用。

### 2. 使用双评分、平均分基础档位和单维升级规则

复杂度与重要性各取 1–5 分，平均分保留一位小数：

- `average < 3`：`standard`
- `3 <= average < 4`：`deep`
- `average >= 4`：`full`

安全升级规则：

- 任一维度为 4，预算至少为 `deep`。
- 任一维度为 5，预算固定为 `full`。

平均分表达总体投入，单维升级防止“实现简单但涉及隐私”或“内部工具但并发算法复杂”被另一维稀释。

备选方案是只使用平均分。该方案会低估单维极端风险，因此不采用。

### 3. 在 Spec 顶部写机器可读风险元数据

采用以下显式字段：

```text
> adversarial_risk_version: 1
> complexity: 1..5
> importance: 1..5
> risk_average: 1.0..5.0
> review_budget: standard|deep|full
> adversarial_review: pending|skipped-standard|complete
```

`## 风险评分依据` 保存人类可读理由，`## 对抗性审查记录` 保存匹配 issue、被推翻假设和新增 Scenario。机器字段保持单一真源，正文只记录依据与结果。

备选方案是在 Markdown 表格中同时保存分数和状态。表格解析更易受列顺序与文案变化影响，因此不采用。

### 4. Scenario 来源使用稳定的行级字段

每个 Scenario 增加一行：

- `来源：initial-spec`
- `来源：adversarial-review (AR-001, AR-002)`

第一版已有 Scenario 保持 ID；对抗性 Scenario 从当前最大 `SC_NN` 后追加。重复执行时按行为与关联 issue 去重，已有 ID 不重排。

备选方案是分成两个 Scenario 章节。分章会增加 x-req3 和 verify 的解析分支，因此采用同一集合中的来源字段。

### 5. 错题集作为仅供风险 skill 渐进读取的独立 reference

错题集位于 `skills/x-adversarial-risk/references/risk-mistakes.md`。每项必须包含：

- issue ID 与确认状态
- 动作维度
- 数据维度
- 场景维度
- 被破坏不变量
- 最小反例
- 应补 Scenario
- 来源证据

`standard` 预算不读取该文件；`deep` 先检索标题和三维标签，再读取匹配 issue 的完整块；`full` 读取完整错题集并增加一次假设推翻。

只有带可定位证据、已确认且能写出最小反例的问题可以进入错题集。其他发现保留在 QA/fix 报告中。

备选方案是让所有 skills 常驻读取错题集。该方案会增加普通任务上下文并扩大规则误触发面，因此不采用。

### 6. 使用一个只读标准库脚本承担机械门禁

`skills/x-adversarial-risk/scripts/risk_contract.py` 提供：

- `validate-spec <spec.md> [--json]`
- `validate-corpus <risk-mistakes.md> [--json]`

退出码：

- `0`：契约通过
- `1`：文件可读且发现契约 issue
- `2`：参数、路径或 IO 错误

相同输入重复执行必须产生相同 issue 集合和退出码。x-adversarial-risk 修改 Spec 后运行 `validate-spec`；x-req3 对带版本标记的 Spec 复跑同一命令。

备选方案是立即修改全局 xdev spec3 validator。存量 Spec 尚未包含新字段，直接纳入全局契约会扩大迁移范围，因此本版采用显式版本标记与专用校验器。

## Risks / Trade-offs

- [LLM 评分可能漂移] → 固定 1–5 锚点、要求写依据，并由预算升级规则保护单维高风险。
- [错题集增长导致上下文膨胀] → deep 只读取三维标签匹配块，full 才读取全文；每项保持最小反例结构。
- [历史 issue 被机械套用] → Scenario 必须能映射当前 Spec 的模块、不变量和可观察结果，无法映射时记录为不适用。
- [独立 skill 被跳过] → 新 Spec 默认写 `pending`，x-req3 对版本化风险契约复跑门禁。
- [重复运行产生重复 Scenario] → 按来源 issue 与行为语义去重，只追加缺失场景并保持已有 ID。
- [存量 Spec 契约分裂] → 版本标记明确新旧边界，后续积累迁移证据后再评估并入全局 validator。

## Migration Plan

1. 新建 OpenSpec capability 和实现任务清单。
2. 初始化 x-adversarial-risk，并落地错题集、校验脚本和测试。
3. 更新 x-spec3 模板与流程，使新 Spec 产出风险元数据和 Scenario 来源。
4. 更新 x-req3，使带风险版本标记的 Spec 在拆解前完成门禁。
5. 更新主流程文档，运行 OpenSpec strict validate、脚本测试和仓库回归。

回滚时移除新 skill，并恢复 x-spec3/x-req3 的接入段；存量 Spec 与 task 结构保持可用。

## Open Questions

无。首版采用自动假设推翻；人工复核仍可由用户显式要求。
