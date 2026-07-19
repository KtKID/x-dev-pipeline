# xspec-v2

## Why

x-spec v1 的 7 件产物结构存在大量无下游消费者的内容（目标充分性判断表仪式性填表、05 与验收段大面积重叠、README 导航对小包无价值、90 排序表实操中由用户拍板替代），单包 500+ 行 token 税。且 7 件互引网络（模板互链 + V1-V7 规则 + 裁判 R1-R8 + TEMPLATE_GUIDE）导致补丁式修改必遗漏——xspec-contract-upgrade 任务的外部审核是直接实证（3 个 P0：lite 档位与 V1 硬规则冲突、90/02 回指生产者漏改、OpenSpec 存量包被新 V3 破坏）。按"每段内容必须有下游消费者"原则以新命名空间重建 v2，不再修补 v1。

归档前 review 发现 v2 草案把“未来更新者”漏出消费者集合：模板能保存需求和模块拆分结果，却没有稳定保存仓库事实、LLM 推断、模块边界选择理由、被否决方案和重评条件。三个月后的更新者无法仅凭 2+1 包可靠区分“边界细化”与“原始意图变化”，因此需在保持精简的同时补入稀疏、可回指的理由层。

## What Changes

- 新建 x-spec2 skill（`skills/x-spec2/`），产物 2+1 件：
  - `spec.md`：需求本质、范围边界、约束与不变量、用户要求→Requirement 追溯表、建模覆盖声明、验收（Requirement/Scenario）
  - `modules.md`：模块设计——职责 / 边界类 / 依赖 / 接口与数据结构 / 风险 / 状态（含"不稳，禁入 x-req"门禁标记），与 spec.md 的 Requirement 双向覆盖
  - `design.md`（按需）：动态模型——核心时序、数据与状态流转、迁移方案；跨模块动态模型触发生成，其余情况不生成空文件
- 建模覆盖声明为 spec.md 硬性段落：建模六元组（数据流、状态、时序、资源、不变量、故障）每项写"落点"或"不适用理由"，禁止静默缺席
- task 拆解职责移交 x-req：v2 不产 task-map（**BREAKING**：v1 的 90-task-map 产物与"spec 内排序"能力在 v2 不存在）
- `tools/xdev.py` 新增 v2 包检测与 v2 规则集：包结构、覆盖声明完整性及落点、design.md 按需生成、场景契约（GIVEN 可选；WHEN、THEN 必须；`验证: auto|manual` 必须）、用户要求→Requirement 回指、Requirement↔模块双向覆盖（悬空/漏覆盖/重名报错）、死链检查（含路径解析语义，无形态禁令）
- `spec.md` 增加拉式“判断依据”账本：由 Requirement 或关键决策按需拉出仓库事实、外部规范、LLM 推断、暂定默认和待确认项，以 `J-ID` 标识来源、证据与确认状态；未被消费的孤儿 J 报 issue
- `modules.md` 增加“关键决策”唯一真源：以 `D-ID` 保存选择、`U/J` 依据、备选方案与否决原因、重新评估触发条件；每个模块以 `U-ID` 回指用户直接指定的边界，或以 `D-ID` 回指派生出来的拆分、依赖、边界类和数据归属决定
- `design.md` 保持纯动态模型，由跨模块数据、状态、时序、资源或故障关系单触发；动态段落可回指 modules.md 中的 `D-ID`
- 扩展 validator、语义 rubric 与 eval：校验 `U/J/D` 唯一性和双向闭合、D 依据强制引用 U/J、结构型 U 回指模块，并用“清空原对话后由新 agent 更新包”的 round-trip case 验证理由可还原性
- **BREAKING（相对尚未归档的 v2 草案）**：此前缺少“判断依据”或模块“决策回指”的 spec2 包将产生新 issue；v1 历史包与 OpenSpec capability/change 包行为保持不变
- x-spec v1 冻结：本变更不修改 v1 的 skill 与模板（**BREAKING** 的 v1 删除动作在后续阶段，待 v2 验证）
- 历史 v1 spec 包（docs/spec/ 现存 7 件包）与 OpenSpec 存量包（openspec/specs/）validate 行为不变（数据兼容）

## Capabilities

### New Capabilities

- `xspec-v2-package`: v2 spec 包的结构定义、建模覆盖声明、场景契约与机器校验能力

### Modified Capabilities

无——现有 capability（xdev-task-artifact-engine 等）需求不变；v1 冻结不改。

## Impact

- 受影响代码：`tools/xdev.py`（v2 检测 + 规则集）、`skills/x-spec2/`（新建 SKILL.md 与 templates/）、`skills/x-spec2/evals/` 与 `skills/x-spec2-workspace/`（生成质量和 round-trip 理由还原 eval）、`test/`（v2 正反样例 + 回归）
- 不受影响：`skills/x-spec/`（冻结）、`openspec/specs/` 存量包（legacy 场景契约不变）、`dev-pipeline/tasks/` 既有 task 包、解析器可见的 checklist 契约（不触碰）
- 前置依赖：尚待提交的 xdev-orchestration-engine 工作（本变更不改其契约）
- 后续阶段（本变更不含，按序另立 change）：
  1. `xreq-adopt-specv2`——x-req 消费接口适配：读 modules.md 的边界类/状态做归属判断与"不稳禁入"门禁
  2. `xspec-v1-retire`——删除 v1 skill 与模板（历史包数据兼容永续保留）
  3. 恢复暂停中的 bench 基建（pipeline-bench-infra），v2 落地后的首个正式基线任务
