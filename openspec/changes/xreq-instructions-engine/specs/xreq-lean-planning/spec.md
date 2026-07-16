## ADDED Requirements

### Requirement: 精简的 x-req 产物集合
活跃 x-req 工作流 SHALL 要求 `README.md` 和 `dev-checklist.md`；当涉及至少三个模块或用户明确要求图时 SHALL 创建 `diagram.md`；新流程 SHALL 停止创建 `changelog.md`。

#### Scenario: 准备普通 task
- **GIVEN** 已确认 task 涉及少于三个模块，且用户没有要求 diagram
- **WHEN** x-req 创建产物集合
- **THEN** task 包含已填写的 `README.md` 与 `dev-checklist.md`，且不新建 `diagram.md` 或 `changelog.md`

#### Scenario: 准备带图 task
- **GIVEN** 已确认 task 涉及至少三个模块，或用户明确要求 diagram
- **WHEN** x-req 创建产物集合
- **THEN** x-req 额外填写 `diagram.md`

#### Scenario: 保留历史 task 产物
- **GIVEN** 现有 task 目录包含 `changelog.md`
- **WHEN** x-req 更新该 task
- **THEN** x-req 保持历史文件原状，并将其排除在活跃规划写入范围之外

### Requirement: 写入前只做一次确认
x-req SHALL 保留基于 `templates/confirmation.md` 的一次用户确认。确认内容 SHALL 覆盖需求要点、spec 关联、架构归属、拆分策略、技术决策、DoD、验收路径和 checklist 预览。

#### Scenario: 用户确认新 task
- **GIVEN** x-req 已组装确认内容
- **WHEN** 用户回复 `Y`
- **THEN** x-req 进入 task 包 scaffold 与填写流程

#### Scenario: 用户要求修改
- **GIVEN** x-req 已展示确认内容
- **WHEN** 用户回复修改项
- **THEN** x-req 更新确认内容，并在写入 task 产物前再次请求确认

#### Scenario: 用户取消
- **GIVEN** x-req 已展示确认内容
- **WHEN** 用户取消
- **THEN** x-req 不写入 task 产物

### Requirement: 主 agent 直接编写产物
用户确认后，主 agent SHALL 直接编写 task 产物，并 SHALL 使用确定性引擎获取结构和逐产物 instructions。该流程 SHALL 省去产物编写子 agent。

#### Scenario: 编写前生成骨架
- **GIVEN** 用户已经确认 task
- **WHEN** x-req 开始创建产物
- **THEN** 它对 task 目录运行 `scaffold`，并且只在满足 diagram 条件时增加 `--with-diagram`

#### Scenario: 按依赖顺序填写产物
- **GIVEN** scaffold 已创建
- **WHEN** x-req 填写产物
- **THEN** 它依次请求 instructions 并填写 `readme`、`dev-checklist`、可选 `diagram`，且在填写每个依赖产物前读取已存在的前置文件

#### Scenario: 清除编写注释
- **GIVEN** 模板包含 HTML 注释，instructions 包含编写约束
- **WHEN** x-req 完成一个产物
- **THEN** 产物只保留 task 内容，移除模板注释和复制的 instruction 散文

### Requirement: 机械校验循环
x-req SHALL 在编写后运行 `python3 tools/xdev.py validate <task-dir>`，并 SHALL 修复机械 finding，直到校验返回零 finding。

#### Scenario: 返回机械 finding
- **GIVEN** 已编写 task 包违反 V2 或 V8-V11
- **WHEN** x-req 运行校验
- **THEN** x-req 修正受影响产物并重跑校验，无需重新请求产品决策

#### Scenario: 机械校验通过
- **GIVEN** task 包满足全部确定性规则
- **WHEN** x-req 运行校验
- **THEN** 校验以 0 退出且 finding 为零，x-req 继续执行判断自审

### Requirement: 四项判断自审
机械校验后，主 agent SHALL 检查需求覆盖、DoD 客观可判定性、已确认架构归属，以及 checklist 对架构边界、契约和依赖的可追溯性。任一检查失败时 SHALL 修复内容并重跑机械校验。

#### Scenario: 需求要点缺失
- **GIVEN** 已确认的用户需求没有写入 README
- **WHEN** 判断自审运行
- **THEN** 主 agent 补入该需求，并同步更新受影响的下游产物

#### Scenario: DoD 主观模糊
- **GIVEN** DoD 条目无法通过命令、产物、可观察输出或明确人工结果证明
- **WHEN** 判断自审运行
- **THEN** 主 agent 将其改写为客观验收条件

#### Scenario: 架构归属漂移
- **GIVEN** 技术设计遗漏或违背已确认的模块边界
- **WHEN** 判断自审运行
- **THEN** 主 agent 恢复已确认边界，并对齐 checklist

#### Scenario: Checklist 任务缺少追溯
- **GIVEN** checklist 行无法从 README 架构拆分策略推导
- **WHEN** 判断自审运行
- **THEN** 主 agent 改写或删除该行并重跑校验

### Requirement: 现有 task 更新模式
当 task 目录已存在时，x-req SHALL 读取当前活跃产物，展示需求与架构 delta 供用户确认，在原目录更新文件，并在 README 头部附近加入 `updated: <date> <summary>` 行。

#### Scenario: 更新现有 task
- **GIVEN** 目标 task 目录已经包含活跃产物
- **WHEN** 用户确认展示的 delta
- **THEN** x-req 更新同一目录，保留无关内容，并在 README 中记录 updated 行

#### Scenario: 已有可选 diagram 不再满足新建条件
- **GIVEN** 现有 task 已包含 diagram，且确认后的更新涉及少于三个模块
- **WHEN** x-req 更新该 task
- **THEN** x-req 保留并对齐已有 diagram，因为 scaffold 与更新流程采用非破坏性策略

### Requirement: Q3 升级模式
当 qdev Q3 task 升级时，x-req SHALL 将源 README 与 dev-report 作为只读证据；用户未指定名称时创建 `<source-name>-full` task；并在新 README 中记录 `source-qdev: dev-pipeline/tasks/<source-name>`。

#### Scenario: 使用默认名称升级
- **GIVEN** qdev task 升级到 Q3，且用户没有指定目标名称
- **WHEN** x-req 启动升级模式
- **THEN** 它创建 `<source-name>-full`，并读取源 README 与 dev-report，同时保持源文件原状

#### Scenario: 使用用户指定名称升级
- **GIVEN** qdev task 升级到 Q3，且用户指定目标名称
- **WHEN** x-req 启动升级模式
- **THEN** 它使用指定名称，并记录 source-qdev 指针

### Requirement: 流水线记录职责
活跃 x-req、x-dev 和 x-qdev 工作流 SHALL 使用 git history 记录仓库变更历史，使用 dev-report 产物记录实现证据。它们的 skills 与活跃模板 SHALL 不再承担 changelog 创建、更新或消费职责。

#### Scenario: x-dev 执行已准备 task
- **GIVEN** task 包包含 README 与 dev-checklist
- **WHEN** x-dev 开发并验证 checklist 工作
- **THEN** 它更新 checklist 状态并将实现证据写入 dev-report，无需 changelog

#### Scenario: x-qdev 完成轻量 task
- **GIVEN** x-qdev 记录有价值的实现决策和验证结果
- **WHEN** 它准备最终产物
- **THEN** 它将这些事实记录在 README 与 dev-report 中，并且不创建 changelog

#### Scenario: 目标 workflow 引用搜索
- **GIVEN** 新产物生命周期已经实现
- **WHEN** 在 `skills/x-req/`、`skills/x-dev/` 和 `skills/x-qdev/` 中搜索 `changelog`、`subagent-completion` 或 `agent1`
- **THEN** 搜索不返回活跃工作流引用；范围外 skills 与历史 task 档案保持原状

### Requirement: x-req 完成汇报
x-req SHALL 汇报 task 路径、产物清单、零 finding 校验结果、四项判断自审结果和推荐的下一条命令 `x-dev <task-name>`。

#### Scenario: 规划成功完成
- **GIVEN** 机械校验与判断自审均通过
- **WHEN** x-req 向用户交接 task
- **THEN** 汇报包含所有必需字段，且只列出真实存在的产物

### Requirement: 工作流范围边界
本变更 SHALL 保持 x-spec 七件套产物模型，并 SHALL 将 x-verify、x-qa-gate、x-fix、x-cr、audit skills、历史 task 迁移、dev-report 命令清单治理、capability 归档自动化和指纹校验保留在实现范围之外。

#### Scenario: 实现精简规划变更
- **GIVEN** 开发者按照本变更 task 清单执行
- **WHEN** 实现完成
- **THEN** 范围外 skill 与历史 task 产物保持原状
