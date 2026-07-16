## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Q3 升级模式
**Reason**: 风险定级成为 README task 数据，所有风险等级都进入同一条 x-req→x-dev→verify 流程。
**Migration**: 原 qdev task 保持历史档案；新任务从 x-req 创建并直接写入 Q0-Q3 risk。

#### Scenario: 历史 qdev task 保持档案
- **GIVEN** 一个已有的 qdev task 目录
- **WHEN** 活跃流程完成迁移
- **THEN** 该目录保持历史证据，新 task 使用统一 risk 路由
