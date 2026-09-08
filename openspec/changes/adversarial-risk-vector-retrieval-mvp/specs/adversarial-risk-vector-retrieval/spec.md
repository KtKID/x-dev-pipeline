## ADDED Requirements

### Requirement: 最小错题 key/value 契约

向量错题集 SHALL 使用一个 Markdown 文件保存多条错题。每条错题 SHALL 以唯一的 `AR-<三位序号>` 作为 key，并 SHALL 只包含非空的 `关键词` 与 `Risk` 两个 value 字段。校验器 SHALL NOT 限定首条编号。

向量输入 SHALL 由 `关键词：<原文>` 与 `Risk：<原文>` 按固定顺序拼接。ID、Markdown 标题和空行 SHALL NOT 进入向量输入。

#### Scenario: 解析最小错题

- **GIVEN** 错题集包含 `AR-001`、非空关键词和非空 Risk
- **WHEN** 召回脚本解析该错题集
- **THEN** 脚本得到 key 为 `AR-001` 的一条记录，并使用关键词与 Risk 拼成向量文本

#### Scenario: 拒绝缺少 Risk 的错题

- **GIVEN** 一个错题块包含合法 ID 和关键词
- **WHEN** 该错题块缺少非空 Risk
- **THEN** 召回命令退出 1，并报告可定位到该 ID 的格式错误

### Requirement: 纯文本向量召回

系统 SHALL 接收非空的功能关键词与非空 Risk，将两者拼成查询文本，并使用与错题相同的 Embedding 模型和归一化方式生成向量。系统 SHALL 计算查询与全部错题的向量相似度，按相似度降序排列；相似度相同时 SHALL 按 ID 升序排列。

默认模型 SHALL 为 `Qwen/Qwen3-Embedding-0.6B`，并 SHALL 从 iteration-7 的独立模型目录读取。查询编码 SHALL 使用模型自带的 `query` 提示模板，错题正文 SHALL 按普通文档编码，两侧 SHALL 使用归一化向量。第一版 SHALL 延迟加载 Embedding 模型并只允许读取本地模型文件。第一版 SHALL 在每次调用中以内存方式计算查询和全部错题向量，SHALL NOT 要求向量数据库或持久化索引。

#### Scenario: 已知日志风险召回语义末条记录

- **GIVEN** 错题集包含“物理完整但语义非法的末条记录”对应的 `AR-003`
- **WHEN** 查询关键词包含日志恢复、状态迁移和完整性校验，Risk 描述校验和正确但状态转换非法
- **THEN** 真实 Embedding Smoke 的 Top1 返回 `AR-003`

#### Scenario: 相同相似度保持稳定顺序

- **GIVEN** 假 Embedding 后端让两条错题获得相同相似度
- **WHEN** 请求返回 Top2
- **THEN** 两条结果按 ID 升序返回

### Requirement: 最小 TopN 输出

召回 CLI SHALL 默认返回 Top1，并 SHALL 支持正整数 `--top-n`。成功结果 SHALL 使用顶层 `matches` 数组，每个元素 SHALL 精确包含 `id` 和 `text`；`text` SHALL 是该错题的关键词与 Risk 原文。

公开成功结果 SHALL NOT 包含相似度、向量、模型名、查询回显或调试字段。有效非空错题集 SHALL 返回 `min(top-n, 错题数)` 条结果。

#### Scenario: 默认返回一条最小结果

- **GIVEN** 错题集包含至少一条有效错题
- **WHEN** 调用方省略 `--top-n`
- **THEN** 命令退出 0，`matches` 只包含一条记录，记录只包含 `id` 和 `text`

#### Scenario: TopN 大于错题总数

- **GIVEN** 错题集包含五条有效错题
- **WHEN** 调用方请求 Top10
- **THEN** 命令退出 0，并返回五条按内部相似度排序的记录

### Requirement: 确定的 CLI 错误契约

召回命令成功 SHALL 退出 0。错题文件可读但格式非法或没有有效错题时 SHALL 退出 1。参数、路径、模型加载或运行环境错误时 SHALL 退出 2。

JSON 错误输出 SHALL 精确包含 `error` 与 `message`。相同输入、相同模型和相同错题集的重复调用 SHALL 返回相同 ID 顺序。

#### Scenario: 非法 TopN

- **GIVEN** 调用方提供了本地错题路径和查询文本
- **WHEN** `--top-n` 小于 1
- **THEN** 命令退出 2，并返回只包含 `error` 与 `message` 的 JSON

#### Scenario: 模型加载失败

- **GIVEN** 调用方提供合法查询与错题集
- **WHEN** 默认 Embedding 模型无法加载
- **THEN** 命令退出 2，并返回可识别模型加载阶段的错误消息

### Requirement: x-adversarial-risk 召回接入

iteration-7 的 `x-adversarial-risk` SHALL 在进入对抗分析前，从当前 Spec 或需求中提炼功能关键词和一句 Risk，并调用向量召回 CLI。召回结果 SHALL 直接携带错题正文，当前 agent SHALL 使用该正文检查 Scenario 覆盖和构造最小反例。

运行环境没有可用的本地 Embedding 模型（模型目录缺失，或召回 CLI 按 CLI 错误契约返回可识别的模型加载阶段失败）时，调用方 SHALL 自动绕过本次召回并转入无 RAG 路径：SHALL NOT 因此中止审查，SHALL NOT 触发联网下载或重试加载，也 SHALL NOT 要求用户预先确认。绕过 SHALL 在审查记录中写明原因（如 `CLI=skipped:no-embedding-model`），本轮 Scenario 来源 SHALL NOT 标注 `rag:AR-NNN`。绕过只替代召回，评分与对抗性预算 SHALL 继续生效。参数、路径等其他 exit 2 错误 SHALL NOT 触发绕过，仍按失败处理。

该检索阶段 SHALL NOT 启动 LLM 精排、经验改写或按 ID 二次读取。Scenario 来源 SHALL 统一使用召回结果的 `AR-NNN` ID。风险契约校验器 SHALL 只接受 `adversarial_risk_version: 3`。

#### Scenario: 一条召回结果进入对抗分析

- **GIVEN** 向量召回成功返回一条 `AR-003`
- **WHEN** x-adversarial-risk 开始检查当前 Spec 的日志恢复风险
- **THEN** 当前 agent 直接使用返回正文构造最小反例，并记录复用或新增的 Scenario

#### Scenario: Embedding 模型不可用时自动绕过

- **GIVEN** 本地模型缓存中没有可加载的 Embedding 模型
- **WHEN** x-adversarial-risk 调用向量召回 CLI，命令按错误契约返回模型加载阶段的失败
- **THEN** 调用方把该失败识别为环境降级，转入无 RAG 路径按预算完成独立对抗检验，并在审查记录写入绕过原因

#### Scenario: 绕过时不伪造召回来源

- **GIVEN** 本轮因 Embedding 模型不可用而绕过召回
- **WHEN** 审查记录写入本次新增的 Scenario 来源
- **THEN** 来源只写独立对抗推导，不出现 `rag:AR-NNN`

#### Scenario: 非模型类错误不触发绕过

- **GIVEN** 调用方向召回 CLI 提供了不存在的错题集路径
- **WHEN** 命令返回路径类 exit 2 错误
- **THEN** 调用方按失败处理，不进入无 RAG 路径

#### Scenario: 旧 namespace 来源被拒绝

- **GIVEN** 一个 Spec 的 Scenario 来源引用 `A-risk-003`
- **WHEN** 更新后的风险契约校验器校验该 Spec
- **THEN** 校验失败并提示来源必须使用 `adversarial-review (rag:AR-NNN)`
