# xreq-lean-planning Delta

## MODIFIED Requirements

### Requirement: 精简的 x-req 产物集合

活跃 x-req 工作流 SHALL 只产出归属 spec 的 task，每个 task 只要求 `dev-checklist.md`（含头部与规定表头），SHALL NOT 产出 `README.md`；当涉及至少三个模块或用户明确要求图时 SHALL 额外创建 `diagram.md`；SHALL NOT 创建 `changelog.md`。需求、模块、架构与验收 SHALL NOT 复制进 task，只在 checklist 中以 `spec:` 指针与逐行 `Requirement` 回指引用归属 spec 包。

#### Scenario: 准备新结构 task

- **GIVEN** 已定级的 task 有归属 spec 且涉及少于三个模块
- **WHEN** x-req 创建产物集合
- **THEN** `docs/spec/<name>/tasks/<task>/` 下只含填写好的 `dev-checklist.md`，不新建 README、diagram 或 changelog

#### Scenario: 准备带图新结构 task

- **GIVEN** 已定级 task 有归属 spec 且涉及至少三个模块
- **WHEN** x-req 创建产物集合
- **THEN** x-req 填写 checklist 并额外填写 diagram，diagram 节点对照归属 `modules.md` 模块名

### Requirement: 主 agent 直接编写产物

无需二次确认，主 agent SHALL 直接编写 task 产物，并 SHALL 使用确定性引擎获取骨架和逐产物结构。该流程 SHALL 省去产物编写子 agent。新结构下 SHALL 对 `docs/spec/<name>/tasks/<task>/` 运行 `scaffold` 生成含头部与新表头的 checklist，再逐行填写 `任务说明`、`Requirement` 回指、`风险`、`涉及文件`。

#### Scenario: 编写前生成骨架

- **GIVEN** 已定位归属 spec 包与目标 task 目录
- **WHEN** x-req 开始创建产物
- **THEN** 它对 `docs/spec/<name>/tasks/<task>/` 运行 `scaffold`，并且只在满足 diagram 条件时增加 `--with-diagram`

#### Scenario: 按依赖顺序填写产物

- **GIVEN** scaffold 已创建
- **WHEN** x-req 填写产物
- **THEN** 它先填写 `dev-checklist`，再按需填写依赖它的可选 `diagram`，且在填写 diagram 前读取已存在的 checklist

#### Scenario: 清除编写注释

- **GIVEN** 模板包含 HTML 注释与占位符
- **WHEN** x-req 完成一个产物
- **THEN** 产物只保留 task 内容，移除模板注释和占位符

### Requirement: 机械校验循环

x-req SHALL 在编写后运行 `python3 tools/xdev.py validate <task-dir>` 并修复机械 issue，直到校验返回零 issue；新结构 task 的校验由 xdev.py 委托 `tools/req.py` 引擎执行，命令入口不变。

#### Scenario: 返回机械 issue

- **GIVEN** 已编写新结构 task 包违反头部、表头或逐行回指规则
- **WHEN** x-req 运行校验
- **THEN** x-req 修正受影响产物并重跑校验，无需重新请求产品决策

#### Scenario: 机械校验通过

- **GIVEN** task 包满足全部确定性规则
- **WHEN** x-req 运行校验
- **THEN** 校验以 0 退出且 issue 为零，x-req 继续执行判断自审

### Requirement: 四项判断自审

机械校验后，主 agent SHALL 检查：每行任务可追溯到归属 `spec.md` 的某个 Requirement；这个 spec 下所有 task 合并后每条 `spec.md` Requirement 至少被一行承接（spec 级需求覆盖，交接前自审）；验收 DoD 由归属 `spec.md` 的 Scenario 客观承接，不在 task 侧另造主观副本；`涉及文件` 与 `modules.md` 的模块边界一致（架构归属）；`风险` 列如实标注该任务触及的 `spec.md#系统不变量` 或高危点。任一检查失败时 SHALL 修复内容并重跑机械校验。

#### Scenario: 需求覆盖缺口

- **GIVEN** 归属 spec.md 某 Requirement 未被该 spec 下任何 task 承接
- **WHEN** 判断自审运行
- **THEN** 主 agent 补入承接该 Requirement 的任务行并重跑校验

#### Scenario: DoD 由 spec 承接

- **GIVEN** 某 checklist 行试图在 task 侧另写一份主观 DoD 而非引用 spec.md 的 Scenario
- **WHEN** 判断自审运行
- **THEN** 主 agent 改为以 `Requirement` 回指 spec.md 的客观验收，不在 task 侧复制 DoD

#### Scenario: 架构归属漂移

- **GIVEN** 某任务的 `涉及文件` 违背归属 modules.md 已确认的模块边界
- **WHEN** 判断自审运行
- **THEN** 主 agent 恢复已确认边界并对齐该行

#### Scenario: 风险标注遗漏不变量

- **GIVEN** 某任务会改动触及 `spec.md#系统不变量` 的逻辑但风险列未标注
- **WHEN** 判断自审运行
- **THEN** 主 agent 在风险列补标对应不变量并按映射复核 `risk:` 头部

### Requirement: 现有 task 更新模式

当新结构 task 目录已存在时，x-req SHALL 读取当前 checklist，展示需求与拆分 delta 供用户知悉，在原目录更新文件，并在 `dev-checklist.md` 头部加入 `updated: <date> <summary>` 行。

#### Scenario: 更新现有新结构 task

- **GIVEN** 目标 `docs/spec/<name>/tasks/<task>/` 已含 checklist
- **WHEN** x-req 应用更新
- **THEN** x-req 更新同一目录，保留无关行，并在 checklist 头部记录 `updated` 行

#### Scenario: 已有可选 diagram 不再满足新建条件

- **GIVEN** 现有新结构 task 已包含 diagram，且更新后涉及少于三个模块
- **WHEN** x-req 更新该 task
- **THEN** x-req 保留并对齐已有 diagram，因为 scaffold 与更新流程采用非破坏性策略

### Requirement: 流水线记录职责

活跃 x-req 与 x-dev 工作流 SHALL 使用 git history 记录仓库变更历史，使用 dev-report 产物记录实现证据。它们的 skills 与活跃模板 SHALL 不再承担 changelog 创建、更新或消费职责；统一 risk 路由取代独立轻量入口。

#### Scenario: x-dev 执行已准备 task

- **GIVEN** 新结构 task 包含 dev-checklist 头部与归属 spec 指针
- **WHEN** x-dev 开发并验证 checklist 工作
- **THEN** 它更新 checklist 状态并将实现证据写入 dev-report，无需 changelog

#### Scenario: 历史 qdev task 保持原状

- **GIVEN** 历史 qdev task 已记录实现决策和验证结果
- **WHEN** 活跃流程读取该历史 task
- **THEN** 它保持历史证据，新 task 由 x-req 创建并使用统一 risk 路由

#### Scenario: 目标 workflow 引用搜索

- **GIVEN** 统一 risk 路由已经实现
- **WHEN** 在 `skills/x-req/`、`skills/x-dev/`、`skills/x-verify/` 与 `skills/x-qa-gate/` 中搜索 `changelog`、`qdev` 或 `x-plan`
- **THEN** 搜索不返回活跃工作流引用；历史 task 与归档保持原状

### Requirement: x-req 完成汇报

x-req SHALL 汇报 task 路径、产物清单（`dev-checklist.md` 及可选 `diagram.md`）、零 issue 校验结果、四项判断自审结果和推荐的下一条命令 `x-dev <task-name>`。

#### Scenario: 规划成功完成

- **GIVEN** 机械校验与判断自审均通过
- **WHEN** x-req 交接 task
- **THEN** 汇报含所有必需字段，且只列出真实存在的产物（不含 README）

### Requirement: 工作流范围边界

x-req 的产物职责边界 SHALL 限于 task 拆解产物；v2 spec 包（`spec.md`、`modules.md`、按需 `design.md`）由 x-spec 维护，x-req SHALL NOT 修改 spec 包内容；x-cr、audit skills、历史 task 迁移、capability 归档自动化与指纹校验 SHALL 保留在 x-req 职责之外。

#### Scenario: x-req 不越界改 spec 包

- **GIVEN** 拆 task 时发现归属 spec.md 的某 Requirement 表述需要调整
- **WHEN** x-req 处理
- **THEN** x-req 不直接改写 spec 包，而是回到 x-spec 更新，范围外 skill 与历史 task 产物保持原状

## ADDED Requirements

### Requirement: risk 依托 spec 信号定级

x-req SHALL 为每个新结构 task 在 checklist 头部写入 `risk: Q0|Q1|Q2|Q3`，定级 SHALL 依据归属 spec 包的既有信号，SHALL NOT 自立独立判据：任务触及 `spec.md#系统不变量`、或所属 `modules.md` 模块风险列标「高」时定为 Q3；所属模块风险列标「中」时定为 Q2；仅局部低风险改动定为 Q0/Q1。用户显式风险 SHALL 覆盖默认定级。x-req SHALL NOT 对已在 spec 阶段确认的需求发起二次确认。

#### Scenario: 触及不变量定为 Q3

- **GIVEN** 某 task 覆盖的 Requirement 会改动 `spec.md#系统不变量` 中的规则
- **WHEN** x-req 定级
- **THEN** checklist 头部 `risk: Q3`，且对应任务行风险列标注该不变量

#### Scenario: 中风险模块定为 Q2

- **GIVEN** 某 task 只落在 `modules.md` 风险列标「中」的模块且不触及不变量
- **WHEN** x-req 定级
- **THEN** checklist 头部 `risk: Q2`

#### Scenario: 用户覆盖默认定级

- **GIVEN** x-req 默认定级与用户显式指定的风险不同
- **WHEN** x-req 写入头部
- **THEN** 使用用户指定的合法 risk 值

## REMOVED Requirements

### Requirement: 写入前只做一次确认

**Reason**: 需求确认已在 spec 阶段（用户确认 spec.md）完成，x-req 不重复确认；Q0/Q1 lite 直通与 Q2/Q3 一次确认的分叉一并取消。risk 定级改由 spec 信号驱动，见 ADDED「risk 依托 spec 信号定级」。
