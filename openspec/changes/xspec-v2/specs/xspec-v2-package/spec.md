# xspec-v2-package Delta

## ADDED Requirements

### Requirement: v2 spec 包结构与检测

v2 spec 包 SHALL 由 `spec.md`（需求与验收）与 `modules.md`（模块设计）两个必需文件构成，`design.md`（动态模型）为按需文件；spec.md 头部 SHALL 含 `> spec_version: 2` 标记行。包 SHALL NOT 包含 task 清单——task 拆解归 x-req。检测判据：`modules.md` 存在或 spec.md 含 spec_version: 2 标记，即按 v2 规则集校验，不落入 capability 单文件包分支。

#### Scenario: v2 包被正确检测并校验

- **GIVEN** 一个目录含带 spec_version: 2 标记的 spec.md 与 modules.md
- **WHEN** 运行 `python3 tools/xdev.py validate <目录>`
- **THEN** 包类型报告为 spec2 并按 v2 规则集校验

#### Scenario: 必需文件缺失被抓

- **GIVEN** spec.md 含 spec_version: 2 标记但目录缺 modules.md
- **WHEN** 运行 validate
- **THEN** 报出 v2 包缺件 issue

### Requirement: 建模覆盖声明

spec.md SHALL 含"建模覆盖声明"段：建模六元组（数据流、状态、时序、资源、不变量、故障）每项写明"落点（`文件#段落锚点`）"或"不适用理由"，任一项为空 SHALL 被 validate 报出。填写落点时，目标文件与段落锚点 SHALL 存在。

#### Scenario: 带理由的缺席通过

- **GIVEN** 声明表中"时序"一项写明"不适用：单模块纯函数改造，无跨模块调用顺序"
- **WHEN** 运行 validate
- **THEN** 该项零 issue

#### Scenario: 静默缺席被抓

- **GIVEN** 声明表中"故障"一项为空
- **WHEN** 运行 validate
- **THEN** 报出覆盖声明缺项 issue

#### Scenario: 建模落点悬空被抓

- **GIVEN** 声明表中"状态"一项填写 `design.md#状态流转`，但目标文件或段落不存在
- **WHEN** 运行 validate
- **THEN** 报出建模落点悬空 issue

### Requirement: design.md 按需生成

当数据流、状态、时序、资源、故障任一元组涉及跨模块传递、状态流转、顺序约束、资源生命周期或容量约束、故障恢复时，对应建模落点 SHALL 位于 `design.md`，且 `design.md` SHALL 存在。全部六元组均为不适用，或适用内容已完整落在 `spec.md` / `modules.md` 时，v2 包 MAY 省略 `design.md`；生成器 SHALL NOT 预生成空的 `design.md`。

#### Scenario: 跨模块动态模型要求 design.md

- **GIVEN** 一个需求包含跨模块状态流转，建模覆盖声明将"状态"标为适用
- **WHEN** 生成并 validate v2 包
- **THEN** `design.md` 存在，且"状态"落点指向其中的有效段落

#### Scenario: 无动态模型时省略 design.md

- **GIVEN** 一个单模块纯函数需求的六元组均有 `spec.md` / `modules.md` 落点或不适用理由
- **WHEN** 生成并 validate v2 包
- **THEN** 目录可不含 `design.md` 且零 design 缺件 issue

### Requirement: 验收场景契约

spec.md 的验收 SHALL 使用 Requirement/Scenario 结构：每条 Requirement 至少一个 Scenario；Scenario 中 GIVEN 可选、WHEN 与 THEN 必须、`验证: auto|manual` 标记必须。该契约 SHALL 仅适用于 v2 包与 task 包；OpenSpec 存量包（capability/change）保持原契约。

#### Scenario: 合规场景通过

- **GIVEN** v2 包验收场景含 WHEN、THEN 与验证标记（无 GIVEN）
- **WHEN** 运行 validate
- **THEN** 零场景契约 issue

#### Scenario: 缺验证标记被抓

- **GIVEN** v2 包某场景缺 `验证: auto|manual` 标记
- **WHEN** 运行 validate
- **THEN** 报出场景契约 issue 及行号

### Requirement: 用户要求追溯

spec.md SHALL 含用户要求追溯表：逐条记录用户原话要求（`U-ID` 编号），每条标注对应目标与落实位置（包内文件+段落锚点）。一句混合多个意图的原话 SHALL 在录入时拆成多条原子要求，每条 U 对应单一目标。行为型要求的对应目标 SHALL 是同一 spec.md 中存在且唯一的 Requirement 名；用户直接指定结构（模块边界）的要求，对应目标 MAY 回指 modules.md 中存在的模块名。对应目标或落实位置为空、回指目标悬空 SHALL 被 validate 报出。

#### Scenario: 用户要求正确回指 Requirement

- **GIVEN** 追溯表某行填写用户原话、spec.md 中唯一存在的 Requirement 名与有效落实位置
- **WHEN** 运行 validate
- **THEN** 该追溯行零 issue

#### Scenario: 追溯行落实位置为空被抓

- **GIVEN** 追溯表某行落实位置为空
- **WHEN** 运行 validate
- **THEN** 报出追溯缺口 issue

#### Scenario: 用户要求回指悬空 Requirement 被抓

- **GIVEN** 追溯表某行对应的 Requirement 名未出现在 spec.md 验收中
- **WHEN** 运行 validate
- **THEN** 报出用户要求回指悬空 issue

#### Scenario: 结构型要求回指模块

- **GIVEN** 追溯表某行是用户直接指定的模块边界，对应目标回指 modules.md 中存在的模块名
- **WHEN** 运行 validate
- **THEN** 该行零 issue

#### Scenario: 混合原话拆成原子要求

- **GIVEN** 用户一句原话同时包含一个行为要求与一个结构指定
- **WHEN** 录入用户要求追溯表
- **THEN** 该原话拆成两条 `U-ID`，分别回指 Requirement 名与模块名

### Requirement: 模块状态门禁字段

modules.md 每个模块 SHALL 含状态字段，取值 ∈ 受控词汇（探索中 / 方案确认 / 可进入 x-req / 开发中 / 已完成）；状态非"可进入 x-req"及之后的模块视为"不稳"。状态字段 SHALL 机器可解析，供后续 x-req 门禁消费。

#### Scenario: 非法状态取值被抓

- **GIVEN** 某模块状态写为"差不多能用"
- **WHEN** 运行 validate
- **THEN** 报出状态取值 issue

### Requirement: 判断依据与假设可追溯

spec.md SHALL 含“判断依据”段，使用唯一 `J-ID` 记录用户原话之外的仓库事实、外部规范、LLM 推断、暂定默认与待确认项。J SHALL 由 D 或 Requirement 的依据按需拉出，不预枚举：每条 J SHALL 被包内至少一处（D 依据、Requirement 或其他段落）引用，未被引用的孤儿 J SHALL 被 validate 报出。每条记录 SHALL 包含判断内容、来源类型、可定位证据或明确的推断说明、确认状态；直接来自用户原话的内容 SHALL 复用用户要求追溯表中的 `U-ID`，无需复制为 `J-ID`。

#### Scenario: 派生判断记录来源

- **GIVEN** 系统目标或模块方案依赖一条代码现状与一条 LLM 推断
- **WHEN** 生成并 validate v2 包
- **THEN** spec.md 的“判断依据”分别以唯一 `J-ID` 记录仓库事实证据和 LLM 推断，并标明已确认或待确认状态

#### Scenario: 用户原话复用 U-ID

- **GIVEN** 用户明确指定某个模块边界
- **WHEN** 生成判断依据与后续决策回指
- **THEN** 包复用对应 `U-ID` 表达来源，不为同一事实复制 `J-ID`

#### Scenario: 判断依据结构缺失被抓

- **GIVEN** v2 包缺少“判断依据”段，或某条 `J-ID` 缺来源、证据/推断说明或确认状态
- **WHEN** 运行 validate
- **THEN** 报出判断依据结构 issue

#### Scenario: 孤儿 J 被抓

- **GIVEN** 判断依据段存在未被包内任何 D 依据、Requirement 或其他段落引用的 `J-ID`
- **WHEN** 运行 validate
- **THEN** 报出孤儿 J issue

### Requirement: 关键决策与模块边界可还原

当模块拆分、依赖方向、边界类、数据归属、协议、迁移或动态行为存在多个合理方案，或选择会显著约束未来修改时，modules.md SHALL 含“关键决策”节（`D-ID` 定义的唯一真源）。每个决策 SHALL 使用唯一 `D-ID`，记录最终选择、`U/J` 依据（至少引用一个 `U` 或 `J`）、选择理由、至少一个真实备选及否决原因、重新评估触发条件。design.md 保持动态模型单触发，动态段落 MAY 反向引用 `D-ID`，SHALL NOT 定义 `D-ID`。modules.md 每个模块 SHALL 含“决策回指”：用户直接指定的模块边界可回指 `U-ID`；派生的模块拆分、依赖、边界类或数据归属 SHALL 回指 `D-ID`。所有 `U/J/D` 引用 SHALL 指向包内存在且唯一的记录。

#### Scenario: 派生模块边界回指关键决策

- **GIVEN** LLM 在多个合理边界方案中选择拆出独立传输模块
- **WHEN** 生成 modules.md
- **THEN** modules.md 关键决策节以 `D-ID` 保存选择、依据、备选、否决原因和重评条件，对应模块行回指该 `D-ID`

#### Scenario: 用户直接指定边界保持轻量

- **GIVEN** 用户明确指定模块及其边界，且方案不存在动态模型或其他关键决策
- **WHEN** 生成 v2 包
- **THEN** modules.md 可直接回指对应 `U-ID`，包可省略 design.md

#### Scenario: 决策回指悬空被抓

- **GIVEN** modules.md 某模块回指不存在或重名的 `D-ID`
- **WHEN** 运行 validate
- **THEN** 报出决策回指 issue

#### Scenario: D 依据凭空被抓

- **GIVEN** 某条 `D-ID` 的依据字段为空或未引用任何 `U/J`
- **WHEN** 运行 validate
- **THEN** 报出 D 依据缺失 issue

#### Scenario: 含关键决策的两件包合法

- **GIVEN** 建模六元组均可落在 spec.md 或 modules.md，模块边界的关键选择已记录于 modules.md 关键决策节
- **WHEN** 生成并 validate v2 包
- **THEN** 包可省略 design.md，零缺件 issue

### Requirement: 更新时可恢复原始判断

更新已有 V2 包时，执行者 SHALL 读取 `U/J/D` 证据链，说明目标修改影响的用户要求、判断依据、关键决策与重评条件，再判定原地细化或意图变化。仓库事实、推断、默认值或关键决策变化且系统需求本质、系统目标和不变量保持稳定时，执行者 SHALL 原地更新对应 `J/D` 记录及其引用；系统需求本质、系统目标或不变量变化时 SHALL 新建 spec 包。

#### Scenario: 重评条件触发原地更新

- **GIVEN** 新代码证据满足某个 `D-ID` 的重评条件，且需求本质、系统目标和不变量保持稳定
- **WHEN** 更新者修改模块边界
- **THEN** 更新者在原包更新相关 `J/D`、modules.md 和动态模型，并记录新证据

#### Scenario: 无原对话仍可解释边界

- **GIVEN** 新 agent 只能读取 V2 包与当前仓库，无法读取生成该包时的对话和 transcript
- **WHEN** 要求它解释指定模块为何独立、依赖为何朝当前方向、曾否决什么方案以及何时可以修改
- **THEN** agent 能从 `U/J/D` 回指链给出有包内证据的回答，或明确指出仍待确认的判断

### Requirement: Requirement 与模块双向追溯

modules.md 每个模块 SHALL 回指 spec.md 验收中至少一个 Requirement 名；spec.md 每个 Requirement SHALL 至少被 modules.md 中一个模块回指。模块回指 spec.md 中不存在的名称 SHALL 报悬空 issue，未被任何模块承接的 Requirement SHALL 报覆盖缺口 issue，spec.md 存在同名 Requirement SHALL 报重名歧义 issue。

#### Scenario: 合法回指通过

- **GIVEN** 模块回指的 Requirement 名在 spec.md 中存在且唯一
- **WHEN** 运行 validate
- **THEN** 零回指 issue

#### Scenario: 悬空回指被抓

- **GIVEN** 模块回指 spec.md 中不存在的 Requirement 名
- **WHEN** 运行 validate
- **THEN** 报出悬空回指 issue

#### Scenario: 未被模块承接的 Requirement 被抓

- **GIVEN** spec.md 中某个 Requirement 未被 modules.md 的任何模块回指
- **WHEN** 运行 validate
- **THEN** 报出 Requirement 模块覆盖缺口 issue

#### Scenario: 重名歧义被抓

- **GIVEN** spec.md 含两个同名 Requirement
- **WHEN** 运行 validate
- **THEN** 报出重名歧义 issue

### Requirement: 死链检查

v2 包内 Markdown 链接 SHALL 按解析语义检查目标存在性（`./`、`../` 相对当前文件；无前缀相对路径相对仓库根；http/mailto/纯锚点跳过；绝对路径与 file:// 报机器绑定 issue），不设路径形态禁令。

#### Scenario: 死链被抓

- **GIVEN** 包内链接指向不存在的文件
- **WHEN** 运行 validate
- **THEN** 报出死链 issue

#### Scenario: 路径形态自由

- **GIVEN** 包内使用 `../` 上跳链接且目标存在
- **WHEN** 运行 validate
- **THEN** 零死链 issue

### Requirement: 存量包行为不变

历史 v1 spec 包（7 件结构）与 OpenSpec 存量包（openspec/specs、openspec/changes）的 validate 行为 SHALL 与本变更前一致。

#### Scenario: 历史 v1 包不受扰

- **GIVEN** docs/spec/ 下现存 7 件结构的 v1 包
- **WHEN** 运行 validate
- **THEN** 按现行 spec7 规则校验，issue 集合与本变更前一致

#### Scenario: OpenSpec 存量包回归

- **GIVEN** openspec/specs/ 下现存 capability 包（R/S 格式、无验证标记）
- **WHEN** 运行现有回归测试
- **THEN** 全部通过
