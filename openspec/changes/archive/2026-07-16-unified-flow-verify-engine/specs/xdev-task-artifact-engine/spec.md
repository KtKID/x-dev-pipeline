## MODIFIED Requirements

### Requirement: Task 包分发与完整性校验
显式校验 SHALL 在目标含 `dev-checklist.md` 或解析后位于 `dev-pipeline/tasks/` 下时，将其识别为 task 包。Task 包 SHALL 运行通用路径规则 V2 和 task 规则 V8-V12。自动发现 SHALL 继续只发现 spec 与 change 包。

#### Scenario: 识别缺少 checklist 的标准 task
- **GIVEN** `dev-pipeline/tasks/` 下的显式目标包含 `README.md` 且缺少 `dev-checklist.md`
- **WHEN** 调用方执行 `validate`
- **THEN** V8 报告缺少 `dev-checklist.md`

#### Scenario: 识别仓库外 task 测试夹具
- **GIVEN** 仓库外的显式临时目标包含 `dev-checklist.md`
- **WHEN** 调用方执行 `validate`
- **THEN** 系统将其识别为 task 包并运行 V8-V12

#### Scenario: 要求精简文件集合
- **GIVEN** task 包缺少 `README.md` 或 `dev-checklist.md`
- **WHEN** V8 运行
- **THEN** V8 报告每个缺失的必需文件，并将 `diagram.md` 视为可选文件

#### Scenario: 容纳历史 changelog
- **GIVEN** 合法 task 包同时包含 `changelog.md`
- **WHEN** V8 运行
- **THEN** 历史文件不产生 finding，并保持原状

### Requirement: README 契约校验
V11 SHALL 要求 README 头部含有且仅有合法值的 `risk: Q0|Q1|Q2|Q3`。Q0/Q1 README SHALL 要求 `核心目标` 与 `验收` 二级节；Q2/Q3 README SHALL 额外要求 `需求要点`、`涉及模块`、`架构拆分策略` 与 `技术设计` 二级节。V12 SHALL 要求 `验收` 中每个 `### Requirement:` 至少有一个 `#### Scenario:`，每个 Scenario 必须包含 WHEN、THEN 和 `验证: auto` 或 `验证: manual` 标记；`### 自动化测试责任` SHALL 位于验收节内。

#### Scenario: 接受完整 README
- **GIVEN** README 声明合法 Q2 或 Q3 risk，并含完整章节、自动化测试责任和结构完整的验收 Scenario
- **WHEN** task 校验运行
- **THEN** V11 与 V12 不产生 finding

#### Scenario: 接受纯人工验收路径
- **GIVEN** README 的验收 Scenario 使用 `验证: manual` 且含 WHEN、THEN 和自动化测试责任
- **WHEN** task 校验运行
- **THEN** V11 与 V12 接受该人工验收路径

#### Scenario: 容纳标题后缀
- **GIVEN** 必需标题以规定关键词开头，并增加说明性后缀或全角标点
- **WHEN** task 校验运行
- **THEN** V11 识别该标题

#### Scenario: 报告技术设计缺失
- **GIVEN** README 声明 Q2 或 Q3 risk 且缺少以 `技术设计` 开头的二级标题
- **WHEN** task 校验运行
- **THEN** V11 报告技术设计缺失 finding

#### Scenario: 报告结构或验收证据缺失
- **GIVEN** README 缺少 risk、必需标题、自动化测试责任，或验收结构不完整
- **WHEN** task 校验运行
- **THEN** V11 或 V12 报告每个缺失的契约元素

#### Scenario: 接受 Q0 lite README
- **GIVEN** README 声明合法 Q0 risk，含核心目标、验收、自动化测试责任和结构完整的 Scenario
- **WHEN** task 校验运行
- **THEN** V11 与 V12 不产生 finding

#### Scenario: 拒绝缺少风险或非法风险
- **GIVEN** README 缺少 risk 字段或 risk 不是 Q0、Q1、Q2、Q3
- **WHEN** task 校验运行
- **THEN** V11 报告 risk finding

#### Scenario: 拒绝 Q2 缺少技术设计
- **GIVEN** README 声明 Q2 risk 但缺少技术设计节
- **WHEN** task 校验运行
- **THEN** V11 报告技术设计缺失

#### Scenario: 拒绝不完整验收 Scenario
- **GIVEN** 验收 Requirement 没有 Scenario，或 Scenario 缺少 WHEN、THEN 或验证标记
- **WHEN** task 校验运行
- **THEN** V12 为每个缺失结构产生 finding
