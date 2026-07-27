## Context

当前仓库事实：

- iteration-6 的错题集位于 `repo:skills/x-pipeline-efficiency-workspace/iteration-6/skills/x-adversarial-risk/references/risk-mistakes.md`。
- 当前文件包含五条 `AR-001` 至 `AR-005` 风险示例卡，每条包含标签、信号、不变量、最小反例和检查项。
- 当前 `x-adversarial-risk` 在同一读取轮次中读取整份错题集，再由当前模型判断适用风险。
- 当前 `risk_contract.py` 校验旧错题字段和 `AR-nnn` Scenario 来源。
- 仓库没有现成的 Python Embedding、Transformers、Torch 或 NumPy 依赖。
- iteration-6 的全部 skills 已原样复制到 iteration-7；iteration-6 作为只读基线。

拟议行为：

- 所有优化文件均位于 iteration-7；其余已复制 skills 保持基线内容。
- 错题集继续使用一个 Markdown 文件，每个二级标题块代表一条独立向量记录。
- 每条新记录只保存稳定 ID、关键词和 Risk。
- 当前风险审查从 Spec 或需求中提炼关键词和 Risk，调用本地脚本完成向量匹配。
- 脚本在内存中编码查询和全部错题，按相似度排序并返回 TopN。
- 当前 agent 直接获得 TopN 正文并继续原有对抗分析。

## Goals / Non-Goals

**Goals:**

- 跑通“功能关键词 + Risk → 向量计算 → TopN 错题”的最小链路。
- 保持 iteration-6 为冻结基线，让 iteration-7 承载本轮全部优化。
- 让错题身份与检索文本各自保持稳定职责。
- 使用纯文本 Markdown 作为错题源。
- 让公开输出保持最少字段。
- 为后续扩大错题集保留稳定 CLI 入口。

**Non-Goals:**

- LLM 精排 TopN。
- 把错题集拆成多个文件或三份数据。
- 持久化向量索引或引入向量数据库。
- 输出相似度分数、模型内部向量或调试字段。
- 本轮评估召回率、精确率或确定最佳 TopN。
- 自动把召回错题改写成开发任务。

## Decisions

### 1. 使用稳定 ID 作为 key

每条错题使用下列标题：

```text
## AR-001
```

ID 满足 `AR-<三位序号>`。代码把完整 ID 当作不透明字符串。ID 用于唯一定位、输出结果、Scenario 来源和后续更新；校验器只要求格式正确且全库唯一，不限定首条编号。

关键词可能重复，也会随着表达优化而变化，因此关键词进入可修改的检索文本。

### 2. 使用“关键词 + Risk”作为 value

每条错题采用以下最小格式：

```text
## AR-001

关键词：日志恢复、状态迁移、完整性校验
Risk：物理校验通过的日志记录仍可能违反状态转换或序列规则。
```

向量输入严格按以下顺序拼接：

```text
关键词：<原文>
Risk：<原文>
```

标题 ID 不进入向量文本，避免编号影响相似度。Markdown 标题和空行只承担分块作用。

### 3. 第一版使用真实本地 Embedding，全部向量在内存中计算

实现采用 `sentence-transformers`，默认模型为 `Qwen/Qwen3-Embedding-0.6B`，默认读取 iteration-7 的独立模型目录。查询使用模型自带的 `query` 提示模板，错题正文按普通文档编码；两侧编码都启用归一化，程序通过点积完成余弦相似度排序。

错题集当前规模很小，首版每次调用同时编码查询和全部错题。该方案省去索引文件、缓存失效和数据库生命周期。后续只有测量证明模型加载或重复编码成为主要成本时，才增加缓存或持久化索引。

第三方依赖与本地模型说明保存在 iteration-7 工作区内。模型构造使用 `local_files_only=True`；单元测试通过可注入的假 Embedding 后端保持离线和确定性。`Qwen/Qwen3-Embedding-0.6B` 已按固定 revision 下载并通过权重完整性校验，独立 Smoke 的 Top1 返回 `AR-003`。

### 4. 相似度属于内部排序状态

相似度只参与以下排序：

1. 相似度从高到低。
2. 相似度相同时按 ID 升序。

公开 JSON 只包含：

```json
{
  "matches": [
    {
      "id": "AR-001",
      "text": "关键词：...\nRisk：..."
    }
  ]
}
```

第一版没有相似度阈值。有效且非空的错题集在 `top-n >= 1` 时返回 `min(top-n, 错题数)` 条记录。

### 5. 使用一个最小查询 CLI

CLI 形态：

```text
python3 <skill-dir>/scripts/risk_retrieve.py query \
  --catalog <skill-dir>/references/risk-mistakes.md \
  --keywords "<功能、模块、动作关键词>" \
  --risk "<具体风险描述>" \
  [--top-n 1] \
  --json
```

退出码：

- `0`：成功返回匹配。
- `1`：错题集可读，但格式非法或没有有效错题。
- `2`：参数、路径、模型加载或运行环境错误。

JSON 成功输出固定只有 `matches`；每个元素固定只有 `id` 和 `text`。错误输出固定包含 `error` 与 `message`。

### 6. 召回后直接进入现有对抗分析

`x-adversarial-risk` 在读取当前 Spec 后提炼一组功能关键词和一句具体 Risk，调用召回 CLI。工具返回结果后，当前 agent 直接使用匹配正文检查现有 Scenario，并构造最小反例。

检索阶段没有独立 LLM 精排，也没有根据 ID 再读取错题文件。TopN 结果已经携带完整的关键词与 Risk 文本。

### 7. 使用单一当前 ID 契约

iteration-7 的错题集、ARV 记录和新 Scenario 来源统一使用 `AR-NNN`。`risk_contract.py` 只接受 `adversarial_risk_version: 3`、`RAG:AR-NNN` 与 `adversarial-review (rag:AR-NNN)`，从当前运行规则中删除版本兼容分支。

## Risks / Trade-offs

- [本地模型资产漂移或损坏] → 固定仓库 revision，并在验证清单中检查权重长度、SHA-256 与真实 Top1。
- [Top1 始终会返回某条记录] → 第一阶段只证明技术链路；第二条验收使用已知查询断言预期错题位于 Top1。
- [极短关键词导致语义不足] → CLI 同时要求非空关键词和非空 Risk，向量文本始终包含具体风险句子。
- [ID 规则漂移] → 校验器、Skill、模板和测试共享 `AR-NNN`，残留扫描拒绝 namespace 规则。
- [第三方依赖扩大运行条件] → 依赖限制在 iteration-7 工作区，错误通过退出码 2 清晰暴露。

## Migration Plan

1. 将 iteration-6 的全部 skills 原样复制到 iteration-7，并用目录 diff 验证副本完整。
2. 在 iteration-7 创建最小错题格式 parser 和契约测试。
3. 将 iteration-7 的五条现有风险卡压缩为 `AR-001` 起始的关键词与 Risk。
4. 在 iteration-7 实现向量召回 CLI 和假后端单元测试。
5. 保持模型延迟加载和本地文件模式；下载固定 revision，校验权重完整性并运行真实 Top1 Smoke。
6. 更新 iteration-7 `x-adversarial-risk` 的读取与分析说明。
7. 更新 iteration-7 风险来源校验，只保留 v3 与 `AR-NNN` 当前契约。
8. 运行 iteration-7 回归、OpenSpec strict validate 和变更范围检查。

回滚范围只包含 iteration-7：用冻结的 iteration-6 skills 恢复 iteration-7 基线内容；历史 Spec 保持可读。

## Open Questions

无。首版默认 `top-n=1`，默认模型采用 `Qwen/Qwen3-Embedding-0.6B`。
