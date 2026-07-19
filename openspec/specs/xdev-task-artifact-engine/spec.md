# xdev-task-artifact-engine Specification

## Purpose
TBD - created by archiving change xreq-instructions-engine. Update Purpose after archive.
## Requirements
### Requirement: 任务产物注册表
确定性工具层 SHALL 为 `readme`、`dev-checklist` 和 `diagram` 三类 task 产物定义唯一的代码内注册表。每个条目 SHALL 声明生成文件名、仓库相对模板路径、依赖 artifact ID 和产物专属 instructions；`diagram` SHALL 为可选产物。

#### Scenario: 注册表暴露完整产物图
- **GIVEN** x-req 产物引擎已经加载
- **WHEN** 调用方查询每个已注册产物
- **THEN** `readme` 生成 `README.md` 且没有依赖，`dev-checklist` 生成 `dev-checklist.md` 并依赖 `readme`，`diagram` 生成 `diagram.md` 并依赖 `readme`

#### Scenario: 模板解析与调用方 cwd 解耦
- **GIVEN** 命令从插件仓库外的项目目录调用
- **WHEN** 系统加载注册表模板
- **THEN** 系统从 `tools/xdev.py` 推导出的插件根目录解析模板，并返回相同模板内容

### Requirement: 产物 instructions 命令
工具层 SHALL 提供 `python3 tools/xdev.py instructions <artifact-id> --task <task-dir> [--json]`。JSON 输出 SHALL 包含 `artifact`、`output_path`、`exists`、`template`、`instruction`、`requires` 和 `dependencies`；每个 dependency SHALL 包含 `id`、`path` 和 `exists`。

#### Scenario: 返回合法产物的 instructions
- **GIVEN** 合法 artifact ID 和已存在的 task 目录
- **WHEN** 调用方使用 `--json` 请求 instructions
- **THEN** 命令以 0 退出，并返回全部契约字段以及非空 template 和 instruction 内容

#### Scenario: 将依赖缺失作为事实返回
- **GIVEN** `dev-checklist` 依赖 `readme`，且 task README 缺失
- **WHEN** 调用方请求 `dev-checklist` instructions
- **THEN** 命令以 0 退出，并返回 `exists: false` 的 `readme` dependency

#### Scenario: 拒绝未知 artifact ID
- **GIVEN** artifact ID 不在注册表中
- **WHEN** 调用方请求 instructions
- **THEN** 命令以 2 退出，并列出合法 artifact ID

#### Scenario: 渲染人类可读 instructions
- **GIVEN** 合法 artifact ID
- **WHEN** 调用方省略 `--json`
- **THEN** 命令以 0 退出，并以人类可读格式渲染同一份契约信息

### Requirement: 幂等 task 骨架
工具层 SHALL 提供 `python3 tools/xdev.py scaffold <task-dir> [--with-diagram] [--json]`。该命令 SHALL 创建父目录、复制注册表模板，并完整保留所有已有产物。

#### Scenario: 创建精简的必需骨架
- **GIVEN** task 目录尚未创建
- **WHEN** 调用方执行未带 `--with-diagram` 的 `scaffold`
- **THEN** 命令以 0 退出，创建 `README.md` 和 `dev-checklist.md`，将 README 标题占位符替换为 task 目录名，并且不创建 `diagram.md` 与 `changelog.md`

#### Scenario: 创建可选 diagram
- **GIVEN** task 目录尚未创建
- **WHEN** 调用方执行 `scaffold --with-diagram`
- **THEN** 命令以 0 退出，并额外创建 `diagram.md`

#### Scenario: 重复 scaffold 时保留已有内容
- **GIVEN** 一个或多个目标产物已经包含用户内容
- **WHEN** 调用方再次执行 `scaffold`
- **THEN** 命令以 0 退出，已有文件保持逐字节一致，并在 `skipped` 中报告这些文件

#### Scenario: 报告 created 与 skipped 产物
- **GIVEN** task 目录中只有 `README.md`
- **WHEN** 调用方执行 `scaffold --json`
- **THEN** 结果在 `created` 中列出新写入文件，并在 `skipped` 中列出保留文件

#### Scenario: 报告 scaffold IO 失败
- **GIVEN** 目标目录无法创建或写入
- **WHEN** 调用方执行 `scaffold`
- **THEN** 命令以 2 退出，并返回可操作的错误信息

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
- **THEN** 历史文件不产生 issue，并保持原状

### Requirement: Checklist 契约校验
V9 SHALL 复用 `status` 与 `graph` 使用的解析器。它 SHALL 要求表头为 `# | 任务 | 涉及文件 | 依赖 | 状态 | fix`，接受已定义的 token+emoji 状态和现有纯 emoji 兼容状态，并报告表中不存在的依赖 ID。

#### Scenario: 接受合法的当前 checklist
- **GIVEN** checklist 使用精确契约表头、合法 task ID、合法依赖 ID 和合法双轨状态
- **WHEN** V9 运行
- **THEN** V9 不返回 issue

#### Scenario: 接受纯 emoji 历史状态
- **GIVEN** 表格使用当前列，且 task 状态包含受支持的 emoji 而没有 token
- **WHEN** V9 运行
- **THEN** V9 通过现有兼容映射接受该状态

#### Scenario: 拒绝错误表头
- **GIVEN** checklist 的一个或多个列偏离必需契约
- **WHEN** V9 运行
- **THEN** V9 报告表头不匹配

#### Scenario: 拒绝非法状态
- **GIVEN** checklist 行包含受支持 token+emoji 与纯 emoji 集合之外的状态
- **WHEN** V9 运行
- **THEN** V9 报告对应行和非法状态

#### Scenario: 拒绝悬空依赖
- **GIVEN** checklist 依赖引用同一表中不存在的 task ID
- **WHEN** V9 运行
- **THEN** V9 报告缺失的依赖 ID

### Requirement: 可选 diagram 一致性校验
V10 SHALL 只在 `diagram.md` 存在时运行，并 SHALL 双向比较归一化后的 Mermaid 节点标签与 README `涉及模块` 清单。

#### Scenario: 缺少 diagram 时跳过 V10
- **GIVEN** 合法 task 包没有 `diagram.md`
- **WHEN** task 校验运行
- **THEN** V10 不产生 issue

#### Scenario: 报告只存在于 README 的模块
- **GIVEN** README 列出的模块不存在于任何归一化 Mermaid 节点标签中
- **WHEN** V10 运行
- **THEN** V10 报告缺失的 diagram 节点

#### Scenario: 报告只存在于 diagram 的模块
- **GIVEN** 归一化 Mermaid 节点标签在 README 中没有对应模块
- **WHEN** V10 运行
- **THEN** V10 报告未声明模块

### Requirement: README 契约校验
V11 SHALL 要求 README 头部含有且仅有合法值的 `risk: Q0|Q1|Q2|Q3`。Q0/Q1 README SHALL 要求 `核心目标` 与 `验收` 二级节；Q2/Q3 README SHALL 额外要求 `需求要点`、`涉及模块`、`架构拆分策略` 与 `技术设计` 二级节。V12 SHALL 要求 `验收` 中每个 `### Requirement:` 至少有一个 `#### Scenario:`，每个 Scenario 必须包含 WHEN、THEN 和 `验证: auto` 或 `验证: manual` 标记；`### 自动化测试责任` SHALL 位于验收节内。

#### Scenario: 接受完整 README
- **GIVEN** README 声明合法 Q2 或 Q3 risk，并含完整章节、自动化测试责任和结构完整的验收 Scenario
- **WHEN** task 校验运行
- **THEN** V11 与 V12 不产生 issue

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
- **THEN** V11 报告技术设计缺失 issue

#### Scenario: 报告结构或验收证据缺失
- **GIVEN** README 缺少 risk、必需标题、自动化测试责任，或验收结构不完整
- **WHEN** task 校验运行
- **THEN** V11 或 V12 报告每个缺失的契约元素

#### Scenario: 接受 Q0 lite README
- **GIVEN** README 声明合法 Q0 risk，含核心目标、验收、自动化测试责任和结构完整的 Scenario
- **WHEN** task 校验运行
- **THEN** V11 与 V12 不产生 issue

#### Scenario: 拒绝缺少风险或非法风险
- **GIVEN** README 缺少 risk 字段或 risk 不是 Q0、Q1、Q2、Q3
- **WHEN** task 校验运行
- **THEN** V11 报告 risk issue

#### Scenario: 拒绝 Q2 缺少技术设计
- **GIVEN** README 声明 Q2 risk 但缺少技术设计节
- **WHEN** task 校验运行
- **THEN** V11 报告技术设计缺失

#### Scenario: 拒绝不完整验收 Scenario
- **GIVEN** 验收 Requirement 没有 Scenario，或 Scenario 缺少 WHEN、THEN 或验证标记
- **WHEN** task 校验运行
- **THEN** V12 为每个缺失结构产生 issue

### Requirement: 现有 spec 校验回归安全
加入 task 包校验后 SHALL 保持 spec 与 change 包的既有 V1-V7 行为，并 SHALL 保持 task 包不进入自动发现。

#### Scenario: 校验现有 spec 测试夹具
- **GIVEN** 一个在变更前通过 V1-V7 的 fixture
- **WHEN** 调用方运行扩展后的 validator
- **THEN** 它产生与变更前相同的 V1-V7 结果

#### Scenario: 无显式目标运行校验
- **GIVEN** 仓库中包含历史 task 包
- **WHEN** 调用方运行未指定目标路径的 `validate`
- **THEN** 自动发现不扫描这些 task 包
