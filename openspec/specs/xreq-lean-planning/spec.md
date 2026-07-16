# xreq-lean-planning Specification

## Purpose
TBD - created by archiving change xreq-instructions-engine. Update Purpose after archive.
## Requirements
### Requirement: 精简的 x-req 产物集合
活跃 x-req 工作流 SHALL 要求 `README.md` 和 `dev-checklist.md`；当涉及至少三个模块或用户明确要求图时 SHALL 创建 `diagram.md`；新流程 SHALL 停止创建 `changelog.md`。README SHALL 用 risk 字段与验收 Requirement/Scenario 结构表达 task 契约；Q0/Q1 可省略 Q2/Q3 才要求的完整设计章节。

#### Scenario: 准备普通 task
- **GIVEN** 已确认或直通的 task 涉及少于三个模块，且用户没有要求 diagram
- **WHEN** x-req 创建产物集合
- **THEN** task 包含已填写的 risk README 与 dev-checklist，且不新建 diagram 或 changelog

#### Scenario: 准备带图 task
- **GIVEN** 已确认 task 涉及至少三个模块，或用户明确要求 diagram
- **WHEN** x-req 创建产物集合
- **THEN** x-req 按 risk 写入 README 并额外填写 diagram

#### Scenario: 保留历史 task 产物
- **GIVEN** 现有 task 目录包含历史 `changelog.md`
- **WHEN** x-req 更新该 task
- **THEN** x-req 保持历史文件原状，并将其排除在活跃规划写入范围之外

#### Scenario: 准备普通 Q1 task
- **GIVEN** 已确认 task 为 Q1、涉及少于三个模块且用户没有要求 diagram
- **WHEN** x-req 创建产物集合
- **THEN** task 包含含 risk 与验收 Scenario 的 README 及 dev-checklist，不新建 diagram 或 changelog

#### Scenario: 准备带图 Q2 task
- **GIVEN** 已确认 task 为 Q2 且涉及至少三个模块
- **WHEN** x-req 创建产物集合
- **THEN** x-req 写入完整 README 契约并额外填写 diagram

### Requirement: 写入前只做一次确认
x-req SHALL 为每个新建或更新 task 选择并写入 `risk: Q0|Q1|Q2|Q3`。Q0 表示单文件且没有行为分支变化的琐碎改动；Q1 表示没有跨模块契约变化的局部低风险改动；Q2 表示新功能、多文件或契约、状态变化；Q3 表示鉴权、权限、加密、不可逆数据写入或迁移、公开 API/协议/schema、并发、状态机或缓存一致性。用户显式风险 SHALL 覆盖默认定级。Q0/Q1 SHALL 跳过确认并直接准备 lite task 后续接 x-dev；Q2/Q3 SHALL 在一次确认中展示风险后再写入产物。

#### Scenario: 用户确认新 task
- **GIVEN** x-req 已为 Q2 或 Q3 task 组装包含风险的确认内容
- **WHEN** 用户回复 `Y`
- **THEN** x-req 进入 task 包 scaffold 与填写流程

#### Scenario: 用户要求修改
- **GIVEN** x-req 已展示确认内容
- **WHEN** 用户回复修改项
- **THEN** x-req 更新确认内容、重新定级并再次请求确认

#### Scenario: 用户取消
- **GIVEN** x-req 已展示确认内容
- **WHEN** 用户取消
- **THEN** x-req 不写入 task 产物

#### Scenario: Q1 直接进入执行
- **GIVEN** x-req 将请求定级为 Q1 且用户没有指定更高风险
- **WHEN** x-req 准备 task
- **THEN** README 写入 `risk: Q1`，流程不等待确认并续接 x-dev，同时在完成汇报中记录定级依据

#### Scenario: Q3 经一次确认进入执行
- **GIVEN** 请求触发 Q3 判据
- **WHEN** x-req 展示确认内容
- **THEN** 确认内容包含 Q3 定级与判据，用户确认后流程续接 x-dev

#### Scenario: 用户覆盖默认风险
- **GIVEN** x-req 的默认定级与用户显式指定的风险不同
- **WHEN** x-req 写入 README
- **THEN** README 使用用户指定的合法 risk 值

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

### Requirement: 流水线记录职责
活跃 x-req 与 x-dev 工作流 SHALL 使用 git history 记录仓库变更历史，使用 dev-report 产物记录实现证据。它们的 skills 与活跃模板 SHALL 不再承担 changelog 创建、更新或消费职责；统一 risk 路由取代独立轻量入口。

#### Scenario: x-dev 执行已准备 task
- **GIVEN** task 包包含 README 与 dev-checklist
- **WHEN** x-dev 开发并验证 checklist 工作
- **THEN** 它更新 checklist 状态并将实现证据写入 dev-report，无需 changelog

#### Scenario: x-qdev 完成轻量 task
- **GIVEN** 历史 qdev task 已记录实现决策和验证结果
- **WHEN** 活跃流程读取该历史 task
- **THEN** 它保持历史证据，新 task 由 x-req 创建并使用统一 risk 路由

#### Scenario: 目标 workflow 引用搜索
- **GIVEN** 统一 risk 路由已经实现
- **WHEN** 在 `skills/x-req/`、`skills/x-dev/`、`skills/x-verify/` 与 `skills/x-qa-gate/` 中搜索 `changelog`、`qdev` 或 `x-plan`
- **THEN** 搜索不返回活跃工作流引用；历史 task 与归档保持原状

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
