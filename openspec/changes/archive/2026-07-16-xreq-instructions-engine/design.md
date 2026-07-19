## 上下文

### 当前仓库事实

- 已提交基线中的 `tools/xdev.py` 已负责确定性的 V1-V7 包校验。
- 工作区中的 `xdev-orchestration-engine` 前置变更加入了 `status`、`graph`、共享 checklist 解析、token+emoji 状态处理和标准库测试；本变更沿用这些接缝继续扩展。
- `skills/x-req/SKILL.md` 当前约 235 行，要求产出 README、dev-checklist、diagram、changelog，并采用“子 agent 编写—主 agent 审核—子 agent 修复一轮”的流程。
- 产物结构、填写指导和判断指导目前分散在 SKILL 散文与模板注释中。
- `skills/x-dev` 在执行阶段读取并更新 changelog；`skills/x-qdev` 也维护 changelog 模板和升级引用。
- 当前 checklist 模板已经采用进行中的编排契约：`# | 任务 | 涉及文件 | 依赖 | 状态 | fix` 与 token+emoji 状态值。

### 约束

- 开始实现前，前置编排变更必须独立提交，保证代码、skill 和文档变更均可单独评审。
- 运行时代码只使用 Python 标准库；测试使用 `unittest` 和临时目录。
- 本变更直接实施已声明的破坏性工作流调整，不增加废弃别名或兼容分支。
- 历史 `dev-pipeline/tasks/` 内容保持原状；兼容范围包括读取纯 emoji 状态和容纳已有 changelog 文件。
- 交付拆成三个 commit：代码与测试；skills 与模板；仓库 README 文档。

## 目标与范围

### 目标

- 将产物图、模板读取、骨架写入和 task 包机械校验沉入 `tools/xdev.py`。
- 通过按需 `instructions` 提供格式规则，缩减每次 x-req 加载的上下文。
- 由主 agent 直接填写已确认产物，同时保留四项产品/架构判断检查。
- 精简活跃 task 产物集合，明确记录职责归属。
- 通过回归测试保持现有 status/graph 与 V1-V7 契约。

### 本阶段范围外

- x-verify、x-qa-gate、x-fix、x-cr 和 audit 系列 skill 的调整。
- dev-report 命令清单治理、capability/delta 归档自动化和产物指纹。
- 第三方依赖、xdev 全局配置文件和历史 task 迁移。
- x-spec 七件套产物模型调整。

## 设计决策

### 决策 1：在 `tools/xdev.py` 中维护单一产物注册表

`ARTIFACTS` 使用稳定 artifact ID 作为 Python 字典键。每个条目包含 `generates`、`template`、`requires` 和 `instruction`。模板路径采用仓库相对路径，并从 `Path(__file__).resolve().parent.parent` 解析。

`instructions` 与 `scaffold` 共用这一个产物图，文件名和依赖顺序因此只有一个事实源。

备选方案：

- YAML 注册表：当前只有三个条目，Python 字典能保持零依赖和单文件确定性边界。
- 各命令维护独立常量：会让文件名与依赖顺序形成多个事实源。

### 决策 2：分离结构规则与按需填写指导

模板 HTML 注释继续承载紧邻字段的局部结构约束。instruction 常量承载从 SKILL 散文迁出的跨产物流程、判断和填写顺序指导。每条 instruction 末尾都要求作者删除模板注释，并避免把 instruction 文本复制进产物。

同一条规范只归属模板注释或 instruction 常量中的一处。

备选方案：

- 将全部模板注释移入 Python 字符串：会削弱 scaffold 文件中的字段就近指导，并让大段字符串重复模板职责。

### 决策 3：`instructions` 只报告事实且保持无副作用

`instructions` 返回请求产物、输出路径与存在状态、完整模板、完整 instruction、声明依赖和依赖存在状态。依赖缺失作为事实返回，退出码保持 0；非法 artifact ID 和 IO 错误使用退出码 2。

工具负责报告事实；x-req 负责写入顺序和可选 diagram 的价值判断。

备选方案：

- 依赖缺失时直接失败：会隐藏骨架信息，并把编排策略放进查询命令。

### 决策 4：scaffold 采用增量写入和永不覆盖策略

`scaffold` 创建父目录、复制必需模板、仅对新建 README 替换标题占位符，并按需加入 diagram。已有文件统一进入 `skipped`，不提供 force 参数。

该策略支持新建、更新和中断恢复流程，并完整保留用户内容。

备选方案：

- 使用最新模板刷新已有文件：模板升级无法安全合并已经填写的内容。

### 决策 5：显式 task 校验使用“内容 + 标准路径”双重识别

显式目标满足任一条件即识别为 task 包：

1. 包含 `dev-checklist.md`；
2. 解析后的路径位于 `dev-pipeline/tasks/` 路径段下。

路径 fallback 解决原方案中的识别矛盾：仅靠 `dev-checklist.md` 内容无法识别 checklist 已缺失的标准 task，V8 也就无法报告该缺失。对应单元测试 fixture 在临时目录中复刻 `dev-pipeline/tasks/<name>` 结构。

无目标自动发现继续只扫描 spec/change 位置，避免对全部历史 task 进行追溯校验。

备选方案：

- 增加 `--type task`：标准目录已经携带类型信息，现有 CLI 无需再增加公共参数。

### 决策 6：V9 复用 checklist 解析器

V9 调用 status/graph 共用的解析器，再增加六列表头、受支持状态词汇和表内依赖存在性校验。依赖环继续由 graph 报告，V9 不重复实现。

精确表头是当前解析器可见契约。使用当前表头的历史行仍可通过纯 emoji 状态兼容映射。

备选方案：

- 新建第二套校验解析器：会让规划阶段与编排阶段接受不同格式。

### 决策 7：V10 保持可选和词法确定性

V10 只在 `diagram.md` 存在时运行。它归一化 README 模块标签与 Mermaid 节点标签，并双向报告集合差异。实现优先复用现有 Markdown/Mermaid 归一化辅助函数，并保持输出确定性。

README 是架构文字事实源，diagram 是 README 的只读投影。

备选方案：

- 所有 task 强制生成 diagram：小型或双模块变更从强制图中获得的价值较低。

### 决策 8：明确 V11 标题层级

V11 通过前缀识别所需 H2，以容纳说明性后缀和全角标点。`自动化测试责任` 是 Smoke/E2E 区域内的 H3。验收证据要求该区域内至少包含一个围栏命令代码块或一个 `manual` 标记。

该决策消解原方案的混合表述：原文把 `自动化测试责任` 放进必需章节列表，同时又指定为 H3。

备选方案：

- 标题全文精确相等：无害的标题后缀会产生机械噪声。

### 决策 9：主 agent 直接编写 x-req 产物

主 agent 已持有用户确认的需求和架构决策。确认后依次运行 scaffold、按依赖顺序请求产物 instructions、填写内容、修复确定性 issue、执行四项判断自审，并重跑 validate。

该流程减少两次上下文转移，同时保留机械检查和产品判断之间的明确边界。

备选方案：

- 保留子 agent 编写并只增加 validate：会保留最大的重复上下文成本，并继续拆分产物所有权。

### 决策 10：统一结束 x-req、x-dev、x-qdev 的活跃 changelog 职责

新 task 包使用 README 记录需求与更新、dev-checklist 记录执行状态、dev-report 记录实现与验证证据、git 历史记录仓库变更。活跃 skill 内容和模板停止读写 changelog。历史 task changelog 保持可读和原状。

该决策采用源方案对 T6 的推荐，使升级和执行契约保持一致。

备选方案：

- 只从 x-req 移除 changelog：x-dev 与 x-qdev 仍会要求新 x-req task 不再创建的文件。

方案 A 第②步继续处理 Gate/cr 的记录契约：移除 x-qa-gate 对 changelog 的必读输入、Context Completeness 项、reviewer reference 输入和通关写入动作，并清理 x-cr 的 changelog spec 来源。当前步骤的引用清理与验收搜索限定为 x-req、x-dev、x-qdev。

### 决策 11：使用显式前置门禁保持交付边界

实现从 `xdev-orchestration-engine` 独立提交之后开始。本变更随后按三段提交：

1. `tools/xdev.py`、`test/test_xdev_artifacts.py` 和必要测试调整。
2. `skills/` 工作流与模板变更。
3. `README.md` 与 `README_zh.md` 同步。

该结构让前置引擎可单独评审，并符合用户的提交边界偏好。

## 风险与权衡

- [风险] V10 词法归一化可能对别名或描述性标签产生误差。→ [措施] 归一化代码标记、标点、节点 ID 和标签包装；为两个方向建立 fixture；仅对可选 diagram 运行 V10。
- [风险] V9 表头严格性会在显式校验时暴露旧的非标准 task 表格。→ [措施] task 保持关闭自动发现；当前表头内继续兼容纯 emoji 状态。
- [风险] `instructions` 与模板注释形成重复事实源。→ [措施] 测试覆盖注册表完整性；评审时把字段局部规则归入模板，把跨产物规则归入 instructions。
- [风险] changelog 退出活跃流程后可能丢失有价值的推理。→ [措施] 需求演进写入 README 更新行，实现推理和证据写入 dev-report，仓库历史写入 git。
- [风险] x-req 为达到 100 行目标而压缩必要判断。→ [措施] SKILL 保留确认、架构归属、四项判断自审和范围路由，只迁移确定性格式内容。
- [权衡] 直接编写让创建与判断集中在主 agent。→ 确定性机械校验提供独立门禁，用户确认继续承担产品决策门禁。

## 迁移计划

1. 确认当前 `xdev-orchestration-engine` diff 与 task 产物已经独立提交；该前置完成后进入实现。
2. 增加产物注册表、instruction 常量、`instructions`、`scaffold`、V8-V11 分发和标准库测试。
3. 在调整 skill 契约前运行全部单元测试和定向 CLI smoke。
4. 重写 x-req 并更新模板；删除活跃 changelog 与 subagent-completion 文件和引用；对齐 x-dev 与 x-qdev 的记录职责。
5. 运行仓库 skill 校验、完成 skill 引用搜索，并重跑全部单元测试。
6. 更新英文与中文仓库文档。
7. 交付三个 commit 和指定评审证据；实现、验证和用户验收完成后归档本 OpenSpec 变更。

回滚按相反顺序使用同样三个边界：依次回滚仓库文档、skill 行为与模板、代码与测试。历史 task 包无需数据回滚。

## 待确认事项

当前开发范围已经闭合。实现中出现新的数值默认值、超时、限制或破坏性迁移时，暂停执行并请求用户确认，因为本变更尚未定义这些决策。
