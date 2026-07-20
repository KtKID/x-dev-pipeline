# xdev-task-artifact-engine Delta

## ADDED Requirements

### Requirement: task checklist 头部与表头契约

task 的 `dev-checklist.md` SHALL 由头部与任务表构成，SHALL NOT 产出或依赖 README。头部 SHALL 含 `spec:`（归属 spec 包路径）与 `risk: Q0|Q1|Q2|Q3`。归属 spec 包 SHALL 由 task 实际所在位置推定——即 `docs/spec/<spec-name>/tasks/<task-name>/` 的上两级，该目录 SHALL 为合法 v2 包；`spec:` SHALL 与推定出的实际归属一致，不一致 SHALL 被 validate 报出（指针作核对项，不用于定位）。任务表表头 SHALL 为 `# | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix`，接受既有 token+emoji 双轨状态；每行 `任务说明`、`Requirement`、`风险` 三列 SHALL 非空。纯技术/重构行没有对应验收 Requirement 时 SHALL 在 `Requirement` 列显式写 `None`；`None` SHALL 为唯一合法的「无值」写法，其它占位符（`—`、`-`、`n/a` 等）与空单元格 SHALL 被 validate 报出——该列由 LLM 按模板填写，容忍多种形近写法只会把错误推迟到下游。头部或表头字段缺失、非法 SHALL 被 validate 报出。

#### Scenario: 合法 checklist 通过

- **GIVEN** checklist 的 `spec:` 与 task 实际归属一致、`risk:` 合法、规定表头且各行三列非空
- **WHEN** 运行 validate
- **THEN** 头部与表头零 issue

#### Scenario: 缺 spec 指针被抓

- **GIVEN** checklist 头部缺 `spec:` 行
- **WHEN** 运行 validate
- **THEN** 报出头部缺 `spec:` 的 issue

#### Scenario: spec 指针与实际归属不符被抓

- **GIVEN** checklist 头部 `spec:` 写的路径与 task 实际所在的 `docs/spec/<spec-name>/` 不一致
- **WHEN** 运行 validate
- **THEN** 报出指针与实际归属不符的 issue

#### Scenario: 非法 risk 被抓

- **GIVEN** checklist 头部 `risk:` 不是 Q0/Q1/Q2/Q3
- **WHEN** 运行 validate
- **THEN** 报出 risk issue

#### Scenario: 行缺必填列被抓

- **GIVEN** 某任务行 `Requirement` 或 `风险` 列为空
- **WHEN** 运行 validate
- **THEN** 报出该行必填列缺失 issue

#### Scenario: 纯技术行显式声明无 Requirement

- **GIVEN** 某纯技术任务行没有对应验收 Requirement，且 `Requirement` 列填写 `—`
- **WHEN** 运行 validate
- **THEN** 该行不参与 Requirement 存在性与覆盖检查，且不因 `Requirement` 列报 issue

### Requirement: checklist 逐行 Requirement 跨文件回指

checklist 每行非 `—` 的 `Requirement` 列引用 SHALL 存在且唯一于归属 `spec.md` 的验收；引用不存在或重名的 Requirement SHALL 被 validate 报出。`—` SHALL 只表示该行不承接验收 Requirement。task 实际位置的上级不是合法 spec 包时 SHALL 降级为单条归属失效 issue，不对逐行回指级联报错。

#### Scenario: 合法回指通过

- **GIVEN** 每行 `Requirement` 名在归属 `spec.md` 验收中存在且唯一
- **WHEN** 运行 validate
- **THEN** 零回指 issue

#### Scenario: 悬空回指被抓

- **GIVEN** 某行 `Requirement` 引用 `spec.md` 中不存在的名字
- **WHEN** 运行 validate
- **THEN** 报出回指悬空 issue

#### Scenario: 归属 spec 失效不级联

- **GIVEN** task 上级目录缺 `spec.md`/`modules.md`（未放在合法 spec 包的 `tasks/` 下）
- **WHEN** 运行 validate
- **THEN** 报出单条归属失效 issue，不为每行回指重复报错

### Requirement: spec 级 Requirement 覆盖闭合

一个 spec 包 `tasks/` 下所有 task 的 checklist 合并后，归属 `spec.md` 的每条 Requirement SHALL 至少被其中一行 `Requirement` 列承接。存在未被任何 task 承接的 Requirement 时 SHALL 报硬 issue（需求漏做）。该检查 SHALL 在 spec 级（合并该 spec 下全部 `tasks/`）运行，SHALL NOT 在单个 task 的 validate 中判定全覆盖，以免多 task 拆分互相误报。

#### Scenario: 全部 Requirement 被覆盖

- **GIVEN** 某 spec 下所有 task 的 checklist 合并后，spec.md 每条 Requirement 都被至少一行承接
- **WHEN** 运行 spec 级覆盖检查
- **THEN** 零覆盖 issue

#### Scenario: 有 Requirement 没人承接

- **GIVEN** spec.md 某条 Requirement 未被该 spec 下任何 task 的任何 checklist 行承接
- **WHEN** 运行 spec 级覆盖检查
- **THEN** 报出该 Requirement 的覆盖缺口硬 issue

#### Scenario: 单 task validate 不判全覆盖

- **GIVEN** 某 spec 拆成多个 task，单个 task 只承接部分 Requirement
- **WHEN** 对单个 task 运行 validate
- **THEN** 不因该 task 未覆盖其他 task 负责的 Requirement 而报缺口

### Requirement: task 归户

task SHALL 位于 `docs/spec/<spec-name>/tasks/<task-name>/`。`status`、`graph`、`verify`、`flag` 与显式 `validate` SHALL 支持该路径；自动发现 SHALL 继续不扫描任何 task 包。历史 `dev-pipeline/tasks/` 结构不再被工具识别为 task 包（作为死档案保留，不迁移、不校验、不可运行）。

#### Scenario: spec 包内 task 被识别

- **GIVEN** `docs/spec/foo/tasks/bar/` 含合法 checklist
- **WHEN** 对该目录运行 status 或显式 validate
- **THEN** 被识别为 task 包并正常解析

#### Scenario: 历史 dev-pipeline task 不再被识别

- **GIVEN** `dev-pipeline/tasks/` 下存在带 README 的历史目录
- **WHEN** 对其运行 validate
- **THEN** 不被识别为合法 task 包（不产生新结构 issue，也不再走已删除的旧结构校验）

#### Scenario: 自动发现不扫 task

- **GIVEN** 仓库存在 `docs/spec/*/tasks/` 下的 task 包
- **WHEN** 运行未指定目标的 validate
- **THEN** 自动发现不包含任何 task 包

## MODIFIED Requirements

### Requirement: 任务产物注册表

确定性工具层 SHALL 维护单一 task 产物注册表：`dev-checklist`（生成含头部与规定表头的 dev-checklist.md，无依赖）与可选 `diagram`（依赖 `dev-checklist`）；SHALL NOT 含 `readme` 条目。注册表模板 SHALL 从 `tools/xdev.py` 推导出的插件根目录解析，与调用方 cwd 解耦。

#### Scenario: 注册表无 readme

- **GIVEN** 产物引擎已加载
- **WHEN** 调用方查询 task 产物注册表
- **THEN** `dev-checklist` 无依赖、`diagram` 依赖 `dev-checklist`，且不存在 `readme` 条目

#### Scenario: 模板解析与调用方 cwd 解耦

- **GIVEN** 命令从插件仓库外的项目目录调用
- **WHEN** 系统加载注册表模板
- **THEN** 系统从 `tools/xdev.py` 推导出的插件根目录解析模板，并返回相同模板内容

### Requirement: 幂等 task 骨架

工具层 SHALL 提供 `scaffold <task-dir> [--with-diagram] [--json]`，只在 `docs/spec/*/tasks/` 位置生成 task 骨架。该命令 SHALL 创建父目录、复制注册表模板、完整保留所有已有产物，只生成含头部与规定表头的 `dev-checklist.md`（不产 README）；`--with-diagram` 追加 `diagram.md`。重复调用 SHALL 保持已有文件逐字节一致并在 `skipped` 报告；IO 失败 SHALL 以退出码 2 返回可操作错误。

#### Scenario: 创建 task 骨架

- **GIVEN** `docs/spec/foo/tasks/bar/` 尚未创建
- **WHEN** 调用方执行未带 `--with-diagram` 的 `scaffold`
- **THEN** 命令以 0 退出，仅创建含头部与规定表头占位的 `dev-checklist.md`，不创建 `README.md`

#### Scenario: 创建可选 diagram

- **GIVEN** task 目录尚未创建
- **WHEN** 调用方执行 `scaffold --with-diagram`
- **THEN** 命令以 0 退出，并额外创建 `diagram.md`

#### Scenario: 重复 scaffold 保留已有内容

- **GIVEN** 一个或多个目标产物已包含用户内容
- **WHEN** 调用方再次执行 `scaffold`
- **THEN** 命令以 0 退出，已有文件逐字节一致并在 `skipped` 报告

#### Scenario: 报告 scaffold IO 失败

- **GIVEN** 目标目录无法创建或写入
- **WHEN** 调用方执行 `scaffold`
- **THEN** 命令以 2 退出，并返回可操作的错误信息

### Requirement: Task 包分发与完整性校验

显式校验 SHALL 在目标含 `dev-checklist.md`，或解析后位于 `docs/spec/*/tasks/` 下时，将其识别为 task 包，并运行头部契约、表头契约、逐行 Requirement 回指与通用路径规则 V2。工具层 SHALL NOT 再识别或校验 `dev-pipeline/tasks/` 下的历史结构，SHALL NOT 保留任何 README 结构检测或旧表头分支。自动发现 SHALL 继续只发现 spec 与 change 包。

#### Scenario: task 被识别并校验

- **GIVEN** `docs/spec/foo/tasks/bar/` 含合法 checklist
- **WHEN** 调用方执行 `validate`
- **THEN** 按头部、表头、逐行回指规则校验，缺件零 issue

#### Scenario: 缺 checklist 被抓

- **GIVEN** `docs/spec/foo/tasks/bar/` 缺 `dev-checklist.md`
- **WHEN** 调用方执行 `validate`
- **THEN** 报告缺少 `dev-checklist.md`

#### Scenario: 识别仓库外 task 测试夹具

- **GIVEN** 仓库外的显式临时目标含 `dev-checklist.md`
- **WHEN** 调用方执行 `validate`
- **THEN** 系统将其识别为 task 包并按 checklist 规则校验

### Requirement: Checklist 契约校验

Checklist 契约校验 SHALL 复用 `status` 与 `graph` 使用的解析器，要求表头为 `# | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix`，接受已定义的 token+emoji 状态和现有纯 emoji 兼容状态，并报告表中不存在的依赖 ID。SHALL NOT 保留旧表头 `# | 任务 | 涉及文件 | 依赖 | 状态 | fix` 分支。

#### Scenario: 接受合法 checklist

- **GIVEN** checklist 使用规定表头、合法 task ID、合法依赖 ID 和合法双轨状态
- **WHEN** 契约校验运行
- **THEN** 不返回表头或状态 issue

#### Scenario: 接受纯 emoji 历史状态

- **GIVEN** checklist 使用规定表头，且 task 状态含受支持的 emoji 而无 token
- **WHEN** 契约校验运行
- **THEN** 通过现有兼容映射接受该状态

#### Scenario: 拒绝错误表头

- **GIVEN** checklist 表头偏离规定契约
- **WHEN** 契约校验运行
- **THEN** 报告表头不匹配

#### Scenario: 拒绝非法状态

- **GIVEN** checklist 行包含受支持 token+emoji 与纯 emoji 集合之外的状态
- **WHEN** 契约校验运行
- **THEN** 报告对应行和非法状态

#### Scenario: 拒绝悬空依赖

- **GIVEN** checklist 依赖引用同一表中不存在的 task ID
- **WHEN** 契约校验运行
- **THEN** 报告缺失的依赖 ID

### Requirement: 可选 diagram 一致性校验

V10 SHALL 只在 `diagram.md` 存在时运行，双向比较归一化后的 Mermaid 节点标签与归属 spec 包 `modules.md` 的模块名清单。SHALL NOT 保留与 README `涉及模块` 清单对照的旧分支。

#### Scenario: 缺少 diagram 跳过 V10

- **GIVEN** 合法 task 包没有 `diagram.md`
- **WHEN** task 校验运行
- **THEN** V10 不产生 issue

#### Scenario: 对照 modules.md 报差异

- **GIVEN** task 的 diagram 节点标签与归属 spec 包 modules.md 的模块名集合不一致
- **WHEN** V10 运行
- **THEN** V10 报告双向差异

## REMOVED Requirements

### Requirement: README 契约校验

**Reason**: 不兼容旧结构，task 不再产出 README，V11/V12 失去校验对象。risk 校验由「task checklist 头部与表头契约」承接，验收校验由「checklist 逐行 Requirement 跨文件回指」承接。历史 `dev-pipeline/tasks/` task 不再被工具识别或校验。
