# xreq-spec-driven

## Why

spec 体系已完成 v2 化：`docs/spec/<spec-name>/` 下的 `spec.md`（需求本质、范围、约束、系统不变量、用户要求追溯、验收 Requirement/Scenario）与 `modules.md`（模块职责、边界类、依赖、风险、状态、关键决策）已是需求与模块的唯一真源。

x-req 的 task 产物仍是旧契约：`README.md` 大段复述需求要点、涉及模块、架构拆分、验收场景——这些在 `spec.md`/`modules.md` 已有唯一真源，复述即两份副本各自腐化。x-req 还自带一套脱离 spec 的抽象 risk 判据（鉴权/并发/状态机…），与 `modules.md` 的模块风险列、`spec.md` 的系统不变量重复。

x-req 应收敛为单一职责：读 `spec.md` + `modules.md`，把需求拆成 checklist 任务；不再持有需求副本，不再自立风险判据。

## What Changes

- **README.md 退役（BREAKING）**：task 只产 `dev-checklist.md`（+按需 `diagram.md`）。需求/模块/验收/架构不再复述，回归 spec 包。
- **不兼容旧结构（BREAKING）**：pipeline 只认新结构一条路。历史 `dev-pipeline/tasks/`（README + 旧表头）不再被工具识别、校验或运行，作为死档案保留、不迁移。
- **task 归户 spec 包**：task 落 `docs/spec/<spec-name>/tasks/<task-name>/`。
- **checklist 承重**：头部 `spec:` 指针 + `risk:`；任务表 `# | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix`，每行回指 `spec.md` 的 Requirement 并标注触及的 `spec.md#系统不变量`。
- **risk 依托 spec 信号**：读 `modules.md` 风险列与 `spec.md` 系统不变量映射（触不变量/模块「高」→Q3；「中」→Q2；「低」局部→Q0/Q1），不自立抽象判据。
- **取消 x-req 确认**：需求确认已在 spec 阶段完成，x-req 不重复确认，无轻量/完整分叉。
- **新建 `tools/req.py`**：承载 task 的确定性引擎（骨架、checklist 解析、头部与行级校验、Requirement 跨文件校验、spec 级覆盖、进度/拓扑、verify 场景对账），从 `tools/xdev.py` 剥离；命令统一走 xdev.py 委托 req.py。
- **下游读取适配（单轨）**：x-dev / x-verify / x-qa-gate / x-fix 从「读 README」改为「读 checklist 头部 + 按 `spec:` 读 `spec.md`/`modules.md`」，不保留旧路。

## Capabilities

### New Capabilities

无——本变更修订既有 task 产物与流程能力，未引入新 capability。

### Modified Capabilities

- `xdev-task-artifact-engine`：checklist 头部+新表头契约、逐行 Requirement 跨文件回指、spec 级覆盖闭合、task 归户 `docs/spec/*/tasks/`；注册表去 readme、scaffold 只生新结构、Checklist 校验只认新表头、diagram 只对照 `modules.md`；README 契约校验（V11/V12）删除。引擎实现落 `tools/req.py`。
- `xdev-verification-engine`：verify 的验收场景对账源从 README 改为归属 `spec.md`。
- `xreq-lean-planning`：产物集合去 README、risk 依托 spec 信号、取消确认、拆解来源改 `spec.md`/`modules.md`、spec 级覆盖自审。
- `risk-routed-development-flow`：risk 来源改 checklist 头部、判据改 spec 信号；qa-gate/verify 读取源改 `spec.md`，不再读 README。
- `xspec-v2-package`：包根禁 task 清单保留，`tasks/` 子目录合法化为 x-req 产物区。**前置依赖：xspec-v2 change 先归档**（本 delta 的 MODIFIED 基于其合入主 spec 后的内容）。

## Impact

- 受影响代码：**新增 `tools/req.py`**；`tools/xdev.py`（委托 req.py、删除旧结构 task 校验路径）、`skills/x-req/`（SKILL + 模板）、`skills/x-dev|x-verify|x-qa-gate|x-fix/SKILL.md`（读取步骤）、`test/`
- 不变量（不许破坏）：status/graph 编排引擎对新表头的解析（req.py 提供）；v1 spec 包、OpenSpec 存量包 validate 行为不变（spec 包层面，与 task 无关）；dev-report issue ledger 契约不变
- 明确破坏（不兼容）：历史 `dev-pipeline/tasks/` task 不再被识别/校验/运行；旧结构 README 校验（V11/V12）与相关测试删除
- 前置依赖：xspec-v2 change 先归档
- 后续边界：`x-qdev` / `x-plan` retire 已由 `risk-routed-development-flow` 既有 Requirement 承接，本变更不重复处理；spec2 包内 U/J/D 账本命令与 spec check 门禁属其他变更范围
- 取代关系：本变更取代 `xreq-task-v2`（已删）
