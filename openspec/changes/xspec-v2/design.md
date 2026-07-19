# xspec-v2 Design

## Context

x-spec v1 是 7 件产物的重结构（README/01/02/03/04/05/90 + TEMPLATE_GUIDE + 裁判 R1-R8 + xdev.py V1-V7）。外部审核对 xspec-contract-upgrade（给 v1 打补丁的任务）报出 3 P0，证明 v1 的互引网络使补丁必遗漏。用户决策：冻结 v1、以新命名空间重建 v2。v2 的产物哲学：**每段内容必须有至少一个下游消费者（用户确认 / x-req / 裁判 / x-verify），无消费者的字段就是 token 税**。OpenSpec 的产物结构（proposal+specs / design 按需 / tasks 归实现）是参照系。

## Goals / Non-Goals

**Goals:**
- 最小消费者驱动产物集：2 必需 + 1 按需
- 建模缺席显式化：六元组每项"落点或不适用理由"，机器可查
- 关键判断可还原：未来更新者只读 2+1 包即可区分用户要求、仓库事实、LLM 推断、暂定默认和架构选择
- 一套场景契约（GIVEN 可选 / WHEN、THEN 必须 / 验证标记必须）贯穿 v2 spec → task，验收从 spec 出生即结构化
- 存量零破坏：v1 历史包、OpenSpec 包、checklist 契约行为不变

**Non-Goals:**
- 内容级原样传递契约（spec 场景逐字流入 task）——留待后续
- x-req 适配（后续 change `xreq-adopt-specv2`）
- v1 包迁移（不迁移，数据兼容永续）
- v1 skill 删除（后续 change `xspec-v1-retire`）

## Decisions

1. **2+1 件，按消费者切分**（弃 7 件：无消费者字段税；弃单文件：需求与模块的消费者不同——用户确认读 spec.md，x-req 读 modules.md，裁判读两者对账；合并会让每个消费者都读全量）
2. **六元组覆盖声明表**（防：砍掉 03/04 后动态模型静默消失——覆盖声明强制作者对六元组逐项表态并提供有效的 `文件#段落锚点`；弃：六项全必填——重回 v1 充分性判断表的仪式化老路。"有理由的缺席"是合法状态）
3. **v2 检测判据 = modules.md 存在 OR spec.md 含 `> spec_version: 2` 标记**（防：v2 的 spec.md 与 OpenSpec capability 单文件包同名，仅凭 spec.md 存在会误判为 capability；双判据让"缺 modules.md 的 v2 包"仍可被识别并报缺件，而非静默走错规则集）
4. **场景契约按包类型分 profile**：v2/task = 新契约；capability/change = 原契约（防：xspec-contract-upgrade 审核 P0-3 的重演——OpenSpec 存量包无验证标记，全局收紧会打爆回归测试；实现上抽公共场景校验函数 + profile 参数，一处实现防两处漂移）
5. **消费者接口清单作为模板字段的准入标准**：spec.md 每段与 modules.md 每字段在模板注释中标注消费者（用户确认 / x-req / 裁判 / x-verify / qa-gate r1 / 未来更新者）；设计评审时无消费者的字段不得进入模板（防：v2 逐步长回 v1 的肥）
6. **task 拆解出 spec**（用户决策：spec 准确 → req 拆解不偏移。v1 的 90 隐藏职责"不稳模块禁入"由 modules.md 状态字段承接，"跨 task 排序"由 x-req 读模块依赖+风险推导，实操中用户拍板驱动）
7. **v1 退役分两步**（冻结随本变更即刻生效；删除待 v2 经两个真实 spec 验证——防：v2 未经实战即杀 v1，回退无路）
8. **追溯链压缩为机器可查关系**：行为型用户要求→Requirement、结构型用户要求→模块记录在 spec.md；Requirement↔模块通过 modules.md 回指并做双向集合对账。混合原话先拆为原子 U，再分别进入行为或结构出口；由校验器推导反向覆盖，不另建追溯矩阵文件
9. **design.md 由动态模型单触发**：跨模块数据传递、状态流转、顺序约束、资源生命周期/容量、故障恢复触发 design.md；关键决策统一落在 modules.md，动态段落可反向引用 `D-ID`；无动态模型时不生成 design.md
10. **新旧技能物理隔离**：新技能固定为 `skills/x-spec2/`，现有 `skills/x-spec/` 作为冻结版本保持文件级零修改；两者不共享模板，避免 v2 契约反向污染 v1
11. **理由层采用 `U/J/D` 三类拉式标识**：`U-ID` 沿用用户要求追溯并按原子意图拆条；`J-ID` 由 Requirement 或 D 的依据按需拉出，记录事实、外部规范、LLM 推断、暂定默认与待确认项，孤儿 J 视为无消费者 token 税；`D-ID` 记录存在合理备选或会显著约束未来修改的关键选择
12. **理由单点存储、消费者只做回指**：spec.md 的“判断依据”是 `J-ID` 真源；modules.md 的“关键决策”是 `D-ID` 真源；模块行通过“决策回指”引用 `U-ID` 或 `D-ID`，design.md 只消费 D。一个模块由用户直接指定时回指 `U-ID`；由 LLM 设计出的拆分、依赖、边界类或数据归属回指 `D-ID`；每个 D 的依据至少引用一个 U/J
13. **机器校结构，裁判校语义**：validator 校验必需段、字段、ID 唯一性、U/J/D 引用悬空与孤儿、D 依据引用和结构型 U 出口；裁判判断某项是否属于关键决策、依据是否支持选择、备选是否真实、重评条件是否足以指导 update。机器不尝试判断自然语言理由质量
14. **future updater 是可执行验收消费者**：round-trip eval 第一步生成 V2 包，第二步清空对话上下文，只向新 agent 提供包和仓库，要求解释指定模块边界的来源、理由、备选及重评条件，再执行一次边界更新分类。无法从 `U/J/D` 证据链完成说明即判失败

## Risks / Trade-offs

- [风险] v2 包与 capability 包检测歧义 → 双判据 + 检测顺序（v2 判据先于 capability），测试覆盖两类包的交叉样例
- [风险] x-req 未适配期间 v2 包无法进入开发链 → 后续阶段清单已排 `xreq-adopt-specv2` 为第一优先；过渡期 x-req 仍可人工读 modules.md
- [风险] 裁判 rubric 未随 v2 重写会拿 v1 的 R1-R8 硬审 → v2 SKILL 内置精简 rubric（对账 spec.md ↔ modules.md、追溯表落实、覆盖声明真实性），并含"不确定往低判"降级条款
- [风险] 单向回指让 Requirement 无模块承接仍可通过 → 校验器同时检查模块→Requirement 合法性与 Requirement→模块覆盖率
- [取舍] 六元组声明是自由文本理由，机器只查"非空"不查"理由是否成立"——理由质量由裁判与用户确认把关（机器管形式，人管语义）
- [风险] 理由层重新膨胀为 v1 的逐结论仪式 → J 仅由 Requirement/D 按需拉出，孤儿 J 由 validator 拦截；直接用户要求复用 `U-ID`
- [风险] 关键决策判定依赖 LLM 语义 → validator 管 ID 与引用闭合，裁判和 round-trip eval 管遗漏与理由真实性
- [取舍] modules.md 同时承载静态模块边界与关键决策 → D 与被约束模块保持同一真源，design.md 保持纯动态模型并维持两件包能力

## Migration Plan

无数据迁移。流程切换：新 spec 一律用 v2；v1 历史包原地不动，validate 的 spec7 规则集保留为数据兼容层。回滚：删除 v2 规则集与 skill 目录即回到现状（v1 未被触碰）。

## Open Questions

- v2 裁判是否需要独立 run-log 字段口径（沿用 v1 的 judge_p0/judge_fp 还是简化）——实现时随 SKILL 定稿
- `spec_version` 标记的语法形态（引用行 `> spec_version: 2` vs YAML frontmatter）——实现时按 stdlib 解析成本定，倾向引用行
