# Correctness Review 报告

> Report ID: 20260730-113820
> Schema: x-cr-v1 (legacy)
> Mode: module-review
> Scope: module
> Task ID: N/A
> Review 日期：2026-07-30
> 审查范围：`skills/x-cr/`、`skills/x-fix/references/cr-fix-mode.md`、相关仓库契约
> Repository HEAD: `b0debd5`

## 调查对象

| 字段 | 内容 |
|------|------|
| 模式 | 模块正确性 review |
| 用户现象 | 当前 x-cr 模块 review 缺少“模块不变量是否被破坏”的显式检查 |
| 期望行为 | x-cr 能提取模块不变量，追踪变更是否触达其执行路径，用最小反例验证保持或破坏，并把结论写入可供 x-fix 稳定消费的报告 |
| 实际行为 | 当前流程从模块契约直接进入候选根因；权限、状态和并发只作为对抗性输入类别；报告没有不变量登记与覆盖结论 |
| 原始 spec 来源 | 用户当前消息；`skills/x-spec/templates/spec.md`；`skills/x-qa-gate/SKILL.md`；`CLAUDE.md` |

## 修改文件 / 审查范围

| 文件 | 角色 | 说明 |
|------|------|------|
| `skills/x-cr/SKILL.md` | producer contract | 触发、流程、严重度、报告路径 |
| `skills/x-cr/references/bayesian-review.md` | review method | 候选根因与证据更新 |
| `skills/x-cr/references/checklist-general.md` | decision rules | P0/P1/P2 检查清单 |
| `skills/x-cr/references/report-template.md` | artifact schema | CR 报告标题、表格和问题详情 |
| `skills/x-fix/references/cr-fix-mode.md` | downstream consumer | CR 定位、解析、处置和回写 |
| `skills/x-qa-gate/SKILL.md` | neighboring contract | 已把 spec 的影响边界与不变量作为正确性输入 |
| `skills/x-spec/templates/spec.md` | upstream contract | 已定义“影响边界与不变量”六列表 |
| `CLAUDE.md` | repository contract | 当前 task 路径与 skill 间契约 |

仓库版与已安装 Codex 插件缓存版的 `skills/x-cr/SKILL.md` SHA-256 均为
`5d9c8d25348f9b8331795a4ee83fd0aa6f2900156e066a2011f4f232742deeee`，本次结论针对当前实际生效版本。

---

## 贝叶斯根因调查

| H | 先验 | 证据 E | 影响 | 更新后置信度 | 结论 |
|---|------|--------|------|--------------|------|
| H1：当前对抗性检查已经完整覆盖模块不变量 | 中 | `SKILL.md:117-123` 只列输入、状态、依赖、权限、缓存、并发和测试过拟合；流程与报告均无不变量登记、触达判断和覆盖状态 | 削弱 | 低 | 对抗性候选提供攻击角度，缺少稳定规则与覆盖闭环 |
| H2：当前报告路径仍符合 task 契约 | 中 | `SKILL.md:71` 指向历史 `dev-pipeline/tasks/`；`CLAUDE.md:10-11,19-26` 声明当前 task 位于 `docs/spec/<spec>/tasks/<task>/` | 削弱 | 已确认 | 路径契约已漂移 |
| H3：当前报告可被 x-fix 无歧义关联 | 中 | 报告结论表没有 Bn ID；`cr-fix-mode.md:27-30` 要求把表格条目与 Bn 详情关联 | 削弱 | 高 | 多个相似问题可发生错配 |
| H4：严重度和置信度已经独立 | 中 | `SKILL.md:165-167` 与 `checklist-general.md:5-46` 用置信度直接定义 P0/P1/P2 | 削弱 | 已确认 | 影响等级和证据强度相互耦合 |
| H5：仓库版与插件缓存漂移造成行为差异 | 中 | 两份 SKILL.md SHA-256 相同 | 削弱 | 低 | 已排除 |

### 已排除假设

| H | 排除证据 |
|---|----------|
| H5：仓库版与插件缓存漂移 | `cmp -s` 成功，SHA-256 完全一致 |

---

## Spec 对照

| 项 | 原始 spec / 契约 | 当前实现 / 行为 | 分类 | 证据 |
|----|------------------|----------------|------|------|
| 模块不变量 | 模块 review 应判断“修改前后持续成立的规则”是否保持 | 只要求找契约、入口、状态流和对抗性候选 | spec 缺口 | 用户消息；`x-spec/templates/spec.md:25-29`；`x-cr/SKILL.md:49-61,102-145` |
| task 报告路径 | 当前 task 位于 `docs/spec/<spec>/tasks/<task>/` | x-cr 写历史 `dev-pipeline/tasks/<task>/reports/cr/` | 原始 spec 不一致 | `CLAUDE.md:10-11,19-26`；`x-cr/SKILL.md:69-72` |
| CR 问题关联 | x-fix 需要把结论项与 Bn 详情稳定关联 | 结论表缺少 Bn ID | 实现过程偏移 | `report-template.md:61-90`；`cr-fix-mode.md:25-30` |
| 严重度 | P0/P1/P2 表达影响与阻断程度，置信度表达证据强度 | 当前定义使用“已确认、高、中高置信”决定严重度 | spec 缺口 | `x-cr/SKILL.md:159-167`；`bayesian-review.md:102-107` |
| 相邻 skill 边界 | 可触发错误结果的结构性问题归正确性调查；纯结构治理归架构巡检 | 当前文字把架构一致性和单一事实源整体移交 x-audit-arch | spec 缺口 | `x-cr/SKILL.md:20`；`x-audit-arch/SKILL.md:120-143` |

---

## 不变量覆盖

| INV-ID | 模块不变量 | 来源 | 本次触达 | 最小反例 | 结论 | 关联问题 |
|--------|------------|------|----------|----------|------|----------|
| INV-XCR-01 | 模块 review 对每条受影响的稳定规则给出保持、破坏或证据缺口结论 | 用户消息；`x-spec/templates/spec.md:25-29` | `x-cr/SKILL.md` 的模块 review 全流程 | 审查权限 matcher 时只检查非法输入，遗漏子命令审批扩张成根命令能力 | 破坏 | B2、B6 |
| INV-XCR-02 | CR 报告写入当前工作流可发现的固定路径 | `CLAUDE.md:10-11,19-26`；x-cr/x-fix 交接 | `x-cr/SKILL.md:69-72` | 在当前 spec task 中按技能指引写报告，产物进入历史 `dev-pipeline/tasks/` | 破坏 | B1 |
| INV-XCR-03 | 每个结论项与问题详情保持稳定一一对应 | `x-fix/references/cr-fix-mode.md:25-30` | `report-template.md:61-90` | 两个同文件同严重度问题使用相近描述，x-fix 依赖文本推断 Bn | 未验证 | B4 |
| INV-XCR-04 | 手动 x-cr 与流水线 x-qa-gate 保持独立入口和产物 | `x-cr/SKILL.md:6,184`；`CLAUDE.md:67` | 本次优化只调整 x-cr 手动调查及其 x-fix 交接 | 把模块不变量检查改成自动 gate 调度 | 保持 | - |

---

## 审查结论

### P0：已确认正确性错误

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ✅已修复 | 仓库路径契约 | [B1] task CR 报告路径 | `skills/x-cr/SKILL.md:71` | 已确认 | 原始 spec 不一致 | 当前 task 报告会被引导到历史归档目录，破坏报告发现和后续修复交接 |

### P1：生产正确性风险

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ✅已修复 | 用户契约 + 当前流程 | [B2] 模块不变量缺少显式闭环 | `skills/x-cr/SKILL.md:49-61,102-145` | 已确认 | spec 缺口 | 模块 review 可能完成对抗性输入检查后仍漏掉跨路径安全、权限和信任不变量 |
| ✅已修复 | 判定规则 | [B3] 严重度与置信度耦合 | `skills/x-cr/SKILL.md:159-167` | 已确认 | spec 缺口 | 已确认的小影响问题可被升为 P0，高损失且证据待补的问题可被降入 P2 |
| ✅已修复 | 下游解析契约 | [B4] 结论表缺少稳定问题 ID | `skills/x-cr/references/report-template.md:61-90` | 高 | 实现过程偏移 | x-fix 依赖描述和位置推断 Bn 对应关系，重复或相近问题可能错配 |
| ✅已修复 | skill 边界 | [B5] 架构形态与正确性后果边界过粗 | `skills/x-cr/SKILL.md:20` | 高 | spec 缺口 | 单一事实源或分层绕过已经形成错误路径时，当前表述仍容易把问题整体移出 x-cr |
| ✅已修复 | 覆盖策略 | [B6] 固定 3-6 个候选且没有覆盖收口 | `skills/x-cr/SKILL.md:102-123` | 高 | spec 缺口 | 大模块可能在达到候选数量后提前结束，报告无法证明入口、状态所有者和不变量均已覆盖 |

### P2：正确性证据缺口

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ✅已修复 | 触发契约 | [B7] description 缺少不变量与信任边界触发词 | `skills/x-cr/SKILL.md:3-6` | 中 | spec 缺口 | “检查权限能力扩张、客户端伪造、模块不变量”类请求存在触发不稳定风险 |
| ✅已修复 | 渐进加载 | [B8] 每次执行都加载完整 338 行报告模板 | `skills/x-cr/SKILL.md:22-30` | 高 | 实现过程偏移 | 两个长示例持续占用审查上下文；模块 review 的关键判断获得较少注意力 |
| ✅已修复 | reference 边界 | [B9] 三份语言 reference 保留旧严重度与风格清单 | `skills/x-cr/references/lang-*.md` | 已确认 | 实现过程偏移 | 文件内容包含 P1.5/P3、命名和最佳实践，与当前 x-cr 的 P0/P1/P2 正确性范围冲突 |

---

## 问题详情

### B1: task CR 报告路径仍指向历史归档目录

**来源**: 仓库路径契约
**文件**: `skills/x-cr/SKILL.md`
**位置**: 第 71 行
**严重程度**: P0
**根因分类**: 原始 spec 不一致
**置信度**: 已确认

**问题描述**：
当前 task 统一位于 `docs/spec/<spec-name>/tasks/<task-name>/`，x-cr 仍要求写入
`dev-pipeline/tasks/<task>/reports/cr/`。该目录已被仓库声明为历史档案。

**影响**：
CR 报告可能进入未被当前工具识别的目录，x-fix 的定位优先级也无法稳定找到它。

**修复方向**：
统一为：

- task 调查：`docs/spec/<spec>/tasks/<task>/reports/cr/cr-report-YYYYMMDD-HHmmss.md`
- 普通仓库调查：`reports/cr/cr-report-YYYYMMDD-HHmmss.md`

同步更新 `x-fix/references/cr-fix-mode.md` 和 `CLAUDE.md` 的 x-cr 交接契约。

### B2: 模块不变量缺少显式提取、击穿和覆盖结论

**来源**: 用户期望 + 上游 spec 契约 + 当前流程
**文件**: `skills/x-cr/SKILL.md`
**位置**: 第 49-61、102-145 行
**严重程度**: P1
**根因分类**: spec 缺口
**置信度**: 已确认

**问题描述**：
当前流程能构造权限、状态、并发等对抗性输入，却没有先定义“任何修改前后都必须成立的规则”。审查者容易逐个检查输入类别，随后遗漏跨函数、跨模块和跨持久化边界的不变量。

**优化原则**：
把不变量定义成可判定规则：

```text
对所有允许到达该模块的输入与状态，规则 P 在修改前后持续成立。
```

每条不变量登记：

| 字段 | 含义 |
|------|------|
| INV-ID | 稳定编号，如 `INV-AUTHZ-01` |
| 规则 | 一条可判定陈述 |
| 所有者 / 范围 | 执行或维护该规则的模块 |
| 来源 | 用户约束、spec、策略、公开契约、调用方、测试、运行时证据 |
| 触达路径 | 本次 diff 或调查现象经过的入口、guard、状态所有者、副作用 |
| 最小反例 | 最小输入或状态，成立时即可证明规则被击穿 |
| 证据 | 代码、测试、日志、diff、schema、配置 |
| 结论 | 保持 / 破坏 / 未验证 / 来源冲突 |

**通用不变量方向**：
以下方向用于启发判断，保持开放集合：

- 授权能力单调性：批准后的能力范围保持在用户明确批准范围内。
- 服务端信任边界：身份、角色、租户、所有权和授权结果由服务端可信状态推导或校验。
- 隔离：租户、用户、线程、workspace、cwd、设备或会话边界持续成立。
- 状态与持久化：拒绝路径无副作用；成功只在持久化提交后返回；失败保持可恢复状态。
- 幂等与时序：重试不重复副作用；取消、终态和乱序完成保持状态机规则。
- 兼容与公开契约：调用方依赖的字段、错误、退出码和副作用保持。
- 资源与故障：资源在成功、失败、取消和超时路径中遵守生命周期。

这些实例表达上位原则，审查者继续主动寻找同类规则。

**审批路径验收样例**：

```text
INV-AUTHZ-01：
一次批准产生的可执行命令集合，必须是用户明确批准命令范围的子集。
精确命令或子命令审批不能被标准化、前缀记忆、序列化或匹配逻辑扩张为根命令能力。
```

最小反例：

1. 用户只批准 `git status`。
2. 复用审批结果执行 `git push` 或另一个 `git` 子命令。
3. 任一后续命令被放行，即证明不变量破坏。

取证路径固定覆盖：命令解析 → 规范化 → 审批匹配 → remember rule 持久化 → 执行 dispatch → 回归测试。

**登录与鉴权验收样例**：

```text
INV-TRUST-01：
服务端从已认证会话和服务端数据推导或校验 user_id、role、tenant_id、owner 与 permission。
所有客户端字段均作为声明进入校验，授权通过后才允许副作用。
```

最小反例：

1. 保持合法 token。
2. 修改请求中的 `user_id`、`role`、`tenant_id` 或 `owner_id`。
3. 服务端接受伪造值并读取或修改他人资源，即证明不变量破坏。

取证路径固定覆盖：请求 schema → 身份认证 → 授权策略 → 数据访问过滤条件 → 写入/返回 → 安全回归测试。

### B3: 严重度与置信度使用同一维度

**来源**: 判定规则
**文件**: `skills/x-cr/SKILL.md`
**位置**: 第 159-167 行
**严重程度**: P1
**根因分类**: spec 缺口
**置信度**: 已确认

**问题描述**：
当前 P0/P1/P2 同时表达影响和证据强度。严重度应回答“发生后损失多大”，置信度应回答“当前证据有多强”。

**修复方向**：

| 维度 | 建议取值 | 判定对象 |
|------|----------|----------|
| 严重度 | P0 / P1 / P2 | 安全、数据、核心路径、用户范围、可恢复性、阻断性 |
| 置信度 | 低 / 中 / 高 / 已确认 | 可达路径、复现、日志、测试、直接契约冲突、反证检查 |

建议严重度：

- P0：授权或隔离绕过、数据破坏/丢失、核心不变量破坏、核心路径不可用。
- P1：可达的用户可见错误、状态/边界/失败路径错误，影响可恢复或范围受限。
- P2：当前尚无可达破坏路径的 spec、测试、日志或可观测性缺口。

报告继续保留“置信度”列。阻断规则根据严重度与最低证据门槛组合判断。

### B4: 审查结论表缺少稳定问题 ID

**来源**: x-cr → x-fix 交接
**文件**: `skills/x-cr/references/report-template.md`
**位置**: 第 61-90 行
**严重程度**: P1
**根因分类**: 实现过程偏移
**置信度**: 高

**问题描述**：
问题详情使用 `B1`、`B2`，审查结论表没有 ID 列。x-fix 仍需在两处建立关联。

**修复方向**：

```markdown
| ID | 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|----|------|------|--------|-----------|--------|----------|------|
| B1 | ❌ | ... | ... | ... | ... | ... | ... |
```

增加一个轻量报告校验器，检查：

- 必需标题 `审查结论`、`问题详情`、`不变量覆盖`。
- ID 唯一。
- 每个结论 ID 恰好映射一个详情标题。
- 严重度、置信度和状态值合法。
- 每个“破坏/未验证”不变量映射到 Bn 或最短补证动作。

x-fix 先校验，再按 ID 解析和回写。

### B5: x-cr 与 x-audit-arch 的边界应按结果切分

**来源**: 相邻 skill 边界
**文件**: `skills/x-cr/SKILL.md`
**位置**: 第 20 行
**严重程度**: P1
**根因分类**: spec 缺口
**置信度**: 高

**问题描述**：
当前文字按“架构一致性、单一事实源、分层”这些问题形态分流。结构问题已经产生错误路径时，它同时属于正确性调查范围。

**修复方向**：

| 结果 | 归属 |
|------|------|
| 有可达错误路径、安全绕过、状态错误、数据错误或公开契约违背 | x-cr |
| 有结构腐化、重复事实源、分层错位，当前缺少可达错误结果 | x-audit-arch |
| 有表层命名、排版、格式问题 | x-audit-style |

例：客户端角色字段成为第二份授权真相源并被服务端直接使用时，x-cr 检查信任不变量；多份角色枚举尚未形成行为漂移时，x-audit-arch 检查单一事实源。

### B6: 候选数量限制缺少覆盖闭环

**来源**: 调查流程
**文件**: `skills/x-cr/SKILL.md`
**位置**: 第 102-123 行
**严重程度**: P1
**根因分类**: spec 缺口
**置信度**: 高

**问题描述**：
固定 `3-6` 个候选适合小型已知问题，无法表达大型模块的覆盖完成条件。

**修复方向**：
把数量改为软目标，把覆盖声明设为收口条件：

```text
先生成最有解释力的候选，数量随范围调整。
审查结束前逐项声明：
primary module → contract neighbors → state/authority owners
→ entry adapters → evidence/tests
均已覆盖，或写明未覆盖位置与原因。
```

每个被本次变更触达的不变量都必须得到 `保持 / 破坏 / 未验证 / 来源冲突` 之一。

### B7: 触发描述与事实源优先级缺少不变量语义

**来源**: YAML frontmatter 与 spec 定位
**文件**: `skills/x-cr/SKILL.md`
**位置**: 第 3-6、90-100 行
**严重程度**: P2
**根因分类**: spec 缺口
**置信度**: 中

**修复方向**：

- description 增加：模块不变量、信任边界、授权范围扩张、服务端校验、租户/会话隔离、持久化一致性。
- 事实源增加：安全策略、权限模型、schema、服务端状态所有者、威胁模型、负向测试和稳定运行时行为。
- 权威来源发生冲突时输出“来源冲突”，阻止审查者静默选择更宽松规则。
- 普通产品行为可由显式版本化契约调整；安全、授权、隔离和数据完整性规则通过权威策略变更、风险确认和回归证据完成迁移。

description 变更会影响触发面，实施时需要 should-trigger 与 should-not-trigger 查询验证。

### B8: 必读报告模板过长且最终结论只适合合并场景

**来源**: 渐进加载与输出契约
**文件**: `skills/x-cr/SKILL.md`、`skills/x-cr/references/report-template.md`
**位置**: `SKILL.md:22-30`、`report-template.md:149-338`
**严重程度**: P2
**根因分类**: 实现过程偏移
**置信度**: 高

**修复方向**：

- 调查阶段加载精简方法与清单。
- 写报告前加载模板骨架。
- 两个完整示例移动到 `report-examples.md`，仅在格式不确定时读取。
- 最终结论按模式输出：
  - diff / PR：可合并、阻断、需确认。
  - known issue：根因已确认、最高置信假设、证据不足。
  - module review：未发现阻断项、存在阻断项、覆盖不完整。

### B9: 语言 reference 仍保存旧版严重度和风格规则

**来源**: reference 边界
**文件**: `skills/x-cr/references/lang-ts.md`、`lang-js.md`、`lang-csharp.md`
**位置**: 各文件“专项检查项”与“代码风格”章节
**严重程度**: P2
**根因分类**: 实现过程偏移
**置信度**: 已确认

**问题描述**：
当前 `SKILL.md:30,183` 已把风格、命名和抽象偏好移出 x-cr，三份语言 reference
仍把 `any`、命名、callback hell、依赖注入、LINQ 性能等广泛归入 P0/P1/P1.5/P2/P3。
SKILL.md 当前没有加载这些文件，文件本身仍形成冲突的历史规则。

**修复方向**：

- 保留历史文件，文件顶部统一标记“历史参考，x-cr 当前流程不加载”。
- 运行时正确性规则精简迁入 `checklist-general.md` 的语言无关原则。
- 风格、命名、架构和纯性能条目保持在相邻 audit skill。
- 报告 schema 只接受 P0/P1/P2。

---

## 优化后的 SKILL.md 结构

```markdown
# x-cr · 软件正确性调查

## 定位与相邻 skill 边界
## 按需加载的参考
## 输入模式
## 审查范围与报告路径

## 执行流程
### 1. 建立调查对象
### 2. 建立模块正确性模型
### 3. 提取并登记模块不变量
### 4. 计算变更触达与最小反例
### 5. 建立候选根因
### 6. 用证据更新置信度并做反证检查
### 7. 判断不变量、根因和契约关系
### 8. 按影响判定严重度
### 9. 输出报告与下游交接

## 覆盖收口
## 关键约束
```

### 建立模块正确性模型

按以下顺序扩展范围：

```text
主模块
→ 契约相邻模块
→ 状态与权限所有者
→ 入口适配层
→ 副作用与下游消费者
→ 证据与测试
```

记录每一层的公开入口、可信输入、非可信输入、guard、状态所有者、副作用和失败返回。

### 不变量优先于根因假设

流程顺序采用：

```text
现象/变更
→ 模块模型
→ 不变量
→ 最小击穿反例
→ 可达路径
→ 候选根因
→ 证据更新
→ 严重度与置信度
→ CR 报告
```

原因：不变量提供固定判尺，候选根因解释“为什么判尺被击穿”。

---

## 需要修改的文件

| 优先级 | 文件 | 改动 |
|--------|------|------|
| P0 | `skills/x-cr/SKILL.md` | 修正 task 报告路径；新增不变量流程、覆盖收口、严重度/置信度分离和按结果切分的 skill 边界 |
| P0 | `skills/x-cr/references/report-template.md` | 新增不变量覆盖表和 ID 列；拆出完整示例；提供模式化最终结论 |
| P1 | `skills/x-cr/references/invariant-review.md` | 新增精简的不变量提取、来源优先级、触达路径和最小反例方法 |
| P1 | `skills/x-cr/references/checklist-general.md` | 按影响重写 P0/P1/P2；加入授权、信任、隔离、持久化、幂等、生命周期原则 |
| P1 | `skills/x-cr/references/bayesian-review.md` | 把不变量破坏作为候选生成输入；取消固定候选上限 |
| P1 | `skills/x-fix/references/cr-fix-mode.md` | 显式支持当前 task 路径；按 Bn ID 解析、处置和回写 |
| P1 | `CLAUDE.md` | 更新 x-cr producer/consumer 路径与 schema 契约 |
| P2 | `skills/x-cr/scripts/validate_report.py` | 校验标题、ID、严重度、置信度和不变量映射 |
| P2 | `skills/x-cr/evals/evals.json` | 保存行为与触发 eval |
| P2 | `skills/x-cr/references/lang-*.md` | 标记为历史参考并移除当前执行歧义 |

---

## 验证方案

### 行为 eval

| ID | 场景 | 期望 |
|----|------|------|
| E1 | Harness 只批准子命令，matcher/remember rule 扩张到根命令 | 报告 `INV-AUTHZ-01`，给出完整能力扩张路径和最小反例，定为 P0 |
| E2 | 登录接口接收客户端 `role/tenant_id/owner_id`，服务端直接信任 | 报告 `INV-TRUST-01`，追踪到数据访问或副作用，定为 P0 |
| E3 | 客户端携带显示用昵称，服务端身份与权限完全来自 session | 不生成信任边界误报，记录不变量保持证据 |
| E4 | 不变量未写进 spec，安全策略和负向测试已有明确约束 | 从权威策略与测试提取不变量，标记 spec 追溯缺口，同时判断实现是否保持 |
| E5 | 单一事实源重复，当前行为一致且无可达错误路径 | 路由 x-audit-arch，x-cr 报告保持无正确性问题 |
| E6 | 两条同文件、同严重度的相似问题 | 结论表 Bn 与详情一一对应，x-fix 可稳定解析 |

### 触发 eval

应触发：

- “检查审批模块有没有把子命令权限放大到根命令。”
- “review 登录接口，客户端改 role 或 tenant_id 能不能骗过服务端。”
- “检查这个模块改动有没有破坏不变量。”
- “查一下重试、取消和失败回滚的规则还成立吗。”

应路由相邻 skill：

- “全项目检查分层、循环依赖和重复事实源。” → x-audit-arch
- “检查命名、格式、死代码和函数长度。” → x-audit-style
- “跑 verify 证明 task 的命令和 Scenario 全部通过。” → x-verify

### 客观断言

1. 每个 module review 都有“不变量覆盖”章节。
2. 每个触达不变量都有 INV-ID、来源、所有者、最小反例、证据和结论。
3. 每个“破坏”结论映射一个 Bn 问题。
4. 每个“未验证/来源冲突”结论包含最短补证动作。
5. P0/P1/P2 由影响判定，置信度单列。
6. 结论表 ID 与问题详情 ID 一一对应。
7. 当前 task 报告写入 `docs/spec/<spec>/tasks/<task>/reports/cr/`。
8. 普通模块报告写入 `reports/cr/`。
9. `x-fix` 能定位、解析和回写两类路径。
10. 仓库版与安装缓存版同步后哈希一致。

### 实施后的检查命令

```bash
git diff --check -- skills/x-cr skills/x-fix/references/cr-fix-mode.md CLAUDE.md
python3 skills/x-cr/scripts/validate_report.py reports/cr/<sample-report>.md
cmp -s skills/x-cr/SKILL.md \
  /Users/kid/.codex/plugins/cache/local-plugins/x-dev-pipeline/<version>/skills/x-cr/SKILL.md
```

---

## 汇总

| 等级 | 数量 |
|------|------|
| P0 | 1 |
| P1 | 5 |
| P2 | 3 |

## 最终结论

- 2026-07-30 被审版本具备清晰标题、两种输入模式、贝叶斯调查和对抗性候选生成。
- 2026-07-31 已完成 spec 优先不变量、遗漏候选、最小反例、贝叶斯根因和覆盖收口改造。
- B1-B9 已全部处置，验证证据见下方修复备注。

---

## 修复备注

> 修复执行时间：2026-07-31

| ID | 处置结果 | 修复方式 | 证据 |
|----|----------|----------|------|
| B1 | ✅已修复 | task CR 路径改为 `docs/spec/<spec>/tasks/<task>/reports/cr/`，x-fix 保留历史路径兼容 | `skills/x-cr/SKILL.md`、`skills/x-fix/references/cr-fix-mode.md` |
| B2 | ✅已修复 | 新增 spec 声明不变量、遗漏候选、最小反例和可达路径流程 | `skills/x-cr/SKILL.md`、`references/invariant-review.md` |
| B3 | ✅已修复 | P0/P1/P2 按影响判定，贝叶斯置信度独立记录 | `references/checklist-general.md`、`references/bayesian-review.md` |
| B4 | ✅已修复 | x-cr-v2 结论表增加 Bn 与 INV-ID；新增校验器并由 x-cr/x-fix 在交接前运行 | `references/report-template.md`、`scripts/validate_report.py`、`skills/x-fix/references/cr-fix-mode.md` |
| B5 | ✅已修复 | skill 边界改为按可达正确性后果分流 | `skills/x-cr/SKILL.md#与相邻-skill-的边界` |
| B6 | ✅已修复 | 候选数量改为软起点，覆盖表与覆盖声明决定完成 | `skills/x-cr/SKILL.md#覆盖收口` |
| B7 | ✅已修复 | description 增加不变量、信任边界、授权范围和服务端校验触发语义 | `skills/x-cr/SKILL.md:3-6` |
| B8 | ✅已修复 | 报告模板改为写报告前加载，模板从 338 行精简为约 200 行 | `skills/x-cr/SKILL.md#按需加载的参考` |
| B9 | ✅已修复 | 三份语言 reference 标记为历史参考 | `skills/x-cr/references/lang-*.md` |

验证：

- `python3 -m unittest discover -s test`：120 tests passed。
- `git diff --check -- CLAUDE.md skills/x-cr skills/x-fix skills/x-cr-workspace`：通过。
- `skills/x-cr/evals/evals.json` 与四份 grading JSON：格式通过。
- `python3 skills/x-cr/scripts/validate_report.py <三份 x-cr-v2 dry-run 报告>`：通过。
- inline contract dry-run：18/18 条断言通过，详见 `skills/x-cr-workspace/iteration-1/summary.md`。
