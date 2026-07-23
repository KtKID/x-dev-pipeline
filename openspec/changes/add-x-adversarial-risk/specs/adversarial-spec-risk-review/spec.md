## ADDED Requirements

### Requirement: Spec 风险双评分

采用 adversarial risk v1 契约的新 Spec SHALL 分别记录 1–5 的复杂度和重要性评分、两者平均分、审查预算与审查状态。复杂度 SHALL 描述实现和状态空间难度；重要性 SHALL 描述用户、资金、隐私与合规影响。

复杂度评分 SHALL 使用以下锚点：

1. 简单 CRUD，无复杂状态机、事务或外部系统交互。
2. 带校验的单体逻辑，包含简单业务规则或格式校验。
3. 状态流转或多条件分支，存在明确状态机或复杂分支。
4. 核心业务链路，涉及支付、交易、权限或高损失一致性问题。
5. 分布式、并发、核心算法，涉及多服务协同、锁、幂等、高并发或自定义算法。

重要性评分 SHALL 使用以下锚点：

1. 内部工具或管理后台非核心功能。
2. 面向内部用户的日常功能。
3. 面向全部用户的非核心功能。
4. 面向全部用户的核心功能。
5. 涉及资金、隐私或合规的生命线功能。

#### Scenario: 登录链路得到高重要性

- **GIVEN** 一个待评分的 Spec 面向全部用户并处理登录会话
- **WHEN** Spec 涉及所有用户的登录和会话 Token
- **THEN** 重要性评分至少为 4，并记录用户范围与敏感数据依据

#### Scenario: 并发算法得到高复杂度

- **GIVEN** 一个待评分的 Spec 定义持久化状态与跨进程并发
- **WHEN** Spec 涉及跨进程锁、幂等和崩溃恢复
- **THEN** 复杂度评分为 5，并记录相关状态空间依据

### Requirement: 动态审查预算

系统 SHALL 以 `(complexity + importance) / 2` 计算一位小数平均分。平均分低于 3 SHALL 选择 `standard`，3 到低于 4 SHALL 选择 `deep`，4 及以上 SHALL 选择 `full`；任一维度为 4 时预算 SHALL 至少为 `deep`，任一维度为 5 时预算 SHALL 为 `full`。

`standard` SHALL 完成评分、现有风险与 Scenario 来源检查，并 SHALL NOT 读取错题集或增加额外审查轮。`deep` SHALL 执行一次对抗性检查并读取动作、数据或场景维度匹配的完整 issue。`full` SHALL 执行全面风险生成、读取完整错题集，并额外执行一次假设推翻。

#### Scenario: 单维高重要性触发全面预算

- **GIVEN** 一个 Spec 的复杂度为 1 且重要性为 5
- **WHEN** 复杂度为 1 且重要性为 5
- **THEN** 平均分为 3.0，预算按单维升级规则选择 `full`

#### Scenario: 低风险 Spec 跳过错题集

- **GIVEN** 一个 Spec 已完成第一版风险评分且尚未执行独立风险审查
- **WHEN** 复杂度为 2、重要性为 2 且风险状态为 `pending`
- **THEN** x-adversarial-risk 不读取错题集，将状态更新为 `skipped-standard` 并保留原 Scenario 集合

### Requirement: Scenario 来源与稳定 ID

采用 adversarial risk v1 契约的每个 Scenario SHALL 标记 `initial-spec` 或 `adversarial-review` 来源。对抗性来源 SHALL 引用至少一个错题 issue ID 或写明本轮假设推翻记录；新增 Scenario SHALL 从当前最大 `SC_NN` 后追加，已有 Scenario ID SHALL 保持稳定。

#### Scenario: 第一版 Scenario 被标记

- **GIVEN** x-spec3 正在生成带 adversarial risk v1 标记的第一版 Spec
- **WHEN** x-spec3 写出第一版 Spec
- **THEN** 每个第一版 Scenario 包含 `来源：initial-spec`

#### Scenario: 对抗性 Scenario 可追溯

- **GIVEN** 当前 Spec 的 compact 流程与 AR-001 的动作、数据和场景维度匹配
- **WHEN** AR-001 的 compact 崩溃窗口适用于当前 Spec
- **THEN** x-adversarial-risk 追加可判定 Scenario，并标记 `来源：adversarial-review (AR-001)`

#### Scenario: 重复审查保持幂等

- **GIVEN** Spec 已完成一次审查且已有 Scenario 保存稳定来源
- **WHEN** 对同一完整 Spec 和同一错题集再次运行相同预算的审查
- **THEN** 已覆盖的行为不生成重复 Scenario，已有 Scenario ID 和来源保持不变

### Requirement: 独立错题集与三维 issue

错题集 SHALL 位于 x-adversarial-risk 自身 reference 中，其他 pipeline skill SHALL NOT 读取该文件。每个确认 issue SHALL 包含唯一 ID、确认状态、动作维度、数据维度、场景维度、被破坏不变量、最小反例、应补 Scenario 和来源证据。

只有已确认且具有可定位证据与可复现最小反例的问题 SHALL 进入错题集。相同根因 SHALL 更新既有 issue，SHALL NOT 新建语义重复条目。

#### Scenario: 安全问题以三维方式记录

- **GIVEN** QA 已确认一个具有日志位置与最小复现的会话泄漏
- **WHEN** 已确认问题是在登录时把会话 Token 输出到日志
- **THEN** issue 的动作维度记录“输出到日志”，数据维度记录“会话 Token”，场景维度记录“登录”

#### Scenario: 未确认候选不进入错题集

- **GIVEN** QA 提交的问题候选缺少稳定位置或复现步骤
- **WHEN** QA 只提出无法定位或复现的风险猜测
- **THEN** 该候选保留在 QA 证据中，错题集不新增 confirmed issue

### Requirement: Spec 对抗性审查记录

x-adversarial-risk SHALL 在 Spec 中记录预算、匹配 issue、被推翻假设和新增 Scenario。`deep` 或 `full` 审查完成后状态 SHALL 为 `complete`；`standard` 完成轻量检查后状态 SHALL 为 `skipped-standard`。任何 `pending` 状态 SHALL 阻断采用该契约的 Spec 进入 x-req3。

#### Scenario: 深度审查完成交接

- **GIVEN** 一个 deep 预算 Spec 已完成错题回放和 Scenario 更新
- **WHEN** deep 审查已补齐所有适用的对抗性 Scenario 并通过机械校验
- **THEN** Spec 状态为 `complete`，审查记录列出匹配 issue 与新增 Scenario

#### Scenario: pending 阻断任务拆解

- **GIVEN** x-req3 准备从一个版本化风险 Spec 生成 task
- **WHEN** x-req3 读取带 `adversarial_risk_version: 1` 且状态为 `pending` 的 Spec
- **THEN** x-req3 停止 scaffold 和任务拆解，并报告风险审查尚未完成

### Requirement: 风险契约校验 CLI

仓库 SHALL 提供只读、标准库实现的风险契约校验器，支持 `validate-spec <spec.md> [--json]` 与 `validate-corpus <risk-mistakes.md> [--json]`。契约通过 SHALL 退出 0；文件可读但存在契约 issue SHALL 退出 1；参数、路径或 IO 错误 SHALL 退出 2。JSON 模式 SHALL 输出稳定的命令、目标、valid、issues 字段。

相同文件内容重复校验 SHALL 返回相同顺序的 issue、相同 JSON 和相同退出码；校验器 SHALL NOT 修改目标文件。

未带 `adversarial_risk_version: 1` 的存量 Spec SHALL 保持现有 x-req3 行为；显式调用 `validate-spec` 校验该文件时 SHALL 报缺少风险版本标记。

#### Scenario: 合法 Spec 校验通过

- **GIVEN** 一个风险元数据、审查记录和 Scenario 来源完整一致的本地 Spec
- **WHEN** 对评分、预算、状态、审查记录和 Scenario 来源一致的 Spec 运行 `validate-spec --json`
- **THEN** 命令退出 0，输出 `valid: true` 与空 issues

#### Scenario: 预算计算错误

- **GIVEN** 一个 Spec 声明的评分可计算出确定预算
- **WHEN** Spec 的复杂度为 5、重要性为 1，却声明 `review_budget: deep`
- **THEN** 命令退出 1，并在 issues 中报告预算应为 `full`

#### Scenario: IO 错误

- **GIVEN** 调用方传入一个本地目标路径
- **WHEN** 校验目标路径不存在
- **THEN** 命令退出 2，并输出可定位的路径错误

#### Scenario: 存量 Spec 兼容

- **GIVEN** 一个既有 spec3 已通过原就绪门禁且没有 adversarial risk 版本标记
- **WHEN** x-req3 消费未带 adversarial risk 版本标记的既有 Spec
- **THEN** 它沿用既有就绪门禁，不要求新风险字段
