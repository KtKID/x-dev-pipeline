# xspec-contract-upgrade

> 创建时间：2026-07-19
> updated: 2026-07-19 审核修订：Q2→Q3；新增 spec_tier 分档与 V1 联动、V3 契约 profile 隔离（保护 OpenSpec 存量包）、02/90 模板回指联动；补 V2 路径解析语义、update 双向对账可执行定义；T8 回归矩阵扩至全量
> updated: 2026-07-19 **已关闭（转型）**：用户拍板放弃修补 v1，改为新写 x-spec v2。本任务的有效设计（场景契约 profile、V2 死链语义、Requirement 名回指、update 可执行定义）已并入 `openspec/changes/xspec-v2/`；改老模板/老 SKILL 的任务作废。本 task 不再开发。
> 类型：优化
> spec:

risk: Q3

## 核心目标

让验收标准从 spec 出生起就是结构化场景条目（Requirement/Scenario），spec 与 task 层使用**同一套场景格式**（本 task 只做格式统一——把"人肉翻译"降为"词法核对"；Requirement/Scenario 名称与内容的原样传递契约不在本 task 范围，留待后续 task，90-task-map 回指 Requirement 名是第一根传递线）；同步落地 spec 分档（lite/full）、裁判降级、update 纪律，并让"包可移动"规则退役。

## 需求要点

1. spec 的验收标准（DoD）从勾选框散文升级为场景条目（Requirement/Scenario），与 task 层同一格式；范围声明：仅格式统一，不含内容级原样传递契约
2. 场景格式法律收敛，且**按包类型分 profile**：spec7/task 包用新契约（GIVEN 可选、WHEN/THEN 必须、`验证: auto|manual` 必须）；OpenSpec 存量 capability/change 包保持原契约（GIVEN/WHEN/THEN，无验证标记要求）——现有回归测试必须继续全绿
3. spec 分档显式化：spec 包 README 头部 `spec_tier: lite|full` 是档位唯一事实源；lite = README + 01 + 90 三件（导航 + 目标/DoD + task 映射），full = 7 件；V1 按档位查文件、裁判按档位审并注明跳过项
4. 裁判加降级：拿不准往轻了判（压误报 judge_fp）
5. 原地更新加三纪律（含可执行定义）：双向对账、不顺手造新文件、先判"细化还是变意图"
6. "包可移动"退役：V2 重定义为死链检查（带明确路径解析语义），路径形态禁令全删
7. V5 回指升级为 Requirement 名，**全部生产者联动**（01 追溯矩阵、02 模块详情、90 task-map 模板）；悬空名被抓、重名歧义被抓
8. 历史 spec7 包（checkbox 式 DoD）零迁移不受扰；OpenSpec 包（openspec/specs、openspec/changes）零迁移不受扰

## 涉及模块

- 工具层（格式法律）：改动 `repo:tools/xdev.py`——场景契约公共解析器 + profile 分派、V1 分档、V2 重定义、V5 升级
- x-spec 模板层：改动 `repo:skills/x-spec/templates/01-goals-and-boundaries.md`（DoD 段 R/S 化 + 追溯矩阵键）、`repo:skills/x-spec/templates/02-module-breakdown.md` 与 `repo:skills/x-spec/templates/90-task-map.md`（回指格式改 Requirement 名）、`repo:skills/x-spec/templates/TEMPLATE_GUIDE.md`（DoD 追溯段 + 路径规则段 + 分档说明）
- x-spec 流程层：改动 `repo:skills/x-spec/SKILL.md`（"全部 7 个产物"强约束按 tier 化改写、6.2 裁判降级与按档位审、update 三纪律、R7 引用更新）
- 测试层（样例冒烟）：新增 `repo:test/` 回归矩阵（新契约正反样例、lite/full 分档、OpenSpec 存量包回归、悬空/重名回指、路径族死链）

## 架构拆分策略

| 维度 | 结论 |
|------|------|
| 主边界 | xdev.py 校验规则是格式法律唯一执法点；模板是法律的模板体现；SKILL 是流程纪律。沿用"skills 管判断、xdev.py 管机械"边界，无新边界类 |
| 公开契约 | ①场景契约按 profile：`spec7/task` = GIVEN 可选 + WHEN/THEN + 验证标记；`capability/change` = 原契约不变。②档位契约：`spec_tier: lite\|full`（缺省 full），V1 按档位查件。③V2 契约：仅查链接目标存在，解析语义见技术设计。④V5 契约：按 Requirement 名回指，悬空报错、重名报歧义 |
| 数据流 | 01 模板（Requirement/Scenario 出生）→ 02/90 回指 Requirement 名（V5）→ task README 验收（V12 同格式）→ dev-report verify 回指 |
| 风险与依赖 | **Q3**：validate 规则是全流水线格式协议（spec 包、task 包、OpenSpec 包、测试、5 个 skill 都依赖），本次变更协议 + 历史兼容行为，符合"公开协议/schema"判据；契约与解析器（T1）先行，规则改造与模板随后，回归矩阵收口 |

## 技术设计

- 架构归属：校验逻辑全部收在 `repo:tools/xdev.py` 内；场景校验抽公共函数，按 profile 参数分派（V3 调用 spec7 侧 profile，V12 调用 task 侧 profile，capability/change 调用 legacy profile），一处实现防再漂移；SKILL/模板只写"怎么写"，不复制校验规则
- 外部入口：`python3 tools/xdev.py validate <包目录>`（行为变化：V1 按 spec_tier 分档；V3 按包类型分 profile；V2 只报死链；V5 匹配 Requirement 标头名）
- 事实源：场景契约正源 = xdev.py 公共校验实现（profile 表）；档位正源 = spec 包 README 头部 `spec_tier:`（缺省 full，保持存量语义）；写法说明正源 = TEMPLATE_GUIDE；裁判与 update 纪律正源 = x-spec SKILL.md
- V2 路径解析语义（契约级定义，实现按此执行）：
  - `./x` 与 `../x`：相对当前 Markdown 文件所在目录解析
  - 无前缀相对路径（如 `docs/spec/a/b.md`）：相对仓库根解析
  - `/` 开头绝对路径与 `file://`：不解析目标，直接报"机器绑定路径"issue（换机必死，属死链的确定态）
  - `http(s)://`、`mailto:`、纯 fragment `#x`：跳过不查
  - 带空格路径与 `<尖括号>` 链接形态：解析器必须支持（现 LINK_RE 的已知缺口）
  - 目标含 fragment（`a.md#锚`）：只查文件存在，不查锚点
- update 双向对账可执行定义（写入 SKILL update 纪律）：
  - 方向一（新意图 → 既有产物）：本次修订的每条新意图，列出受影响既有产物清单（02/03/04/05/90 的哪些段落），逐个检查并改齐
  - 方向二（既有声明 → 01 依据）：被修改产物中的每条既有声明，确认在 01 中仍有依据；失据的删除或回补 01
  - 判定条件：需求本质 / 系统目标 / 系统不变量任一变化 = **变意图**（新开 spec 包，旧包留档）；范围边界内的补充展开 = **细化**（原地改）
- 失败路径：混合包（部分 R/S、部分旧 checkbox）——spec7 新契约只对已含 Requirement 标头的文件生效，旧段落不报错，渐进迁移；无 spec_tier 头的存量包按 full 处理（与现状一致）；无对应 profile 的包类型回退 legacy 契约

## 验收

### Requirement: 场景格式按 profile 校验

场景校验 SHALL 抽公共实现并按包类型分派 profile：spec7/task 用新契约（GIVEN 可选、WHEN/THEN 必须、验证标记必须），capability/change 保持原契约。

#### Scenario: 新格式 spec 包通过

- **WHEN** 对含"GIVEN 可选 + WHEN/THEN + 验证标记"场景的 spec7 包跑 validate
- **THEN** 零 V3 issue
- 验证: auto

#### Scenario: 缺段被抓

- **WHEN** 对 Scenario 缺 THEN 或缺验证标记的 spec7 包跑 validate
- **THEN** V3 issue 报出对应行号
- 验证: auto

#### Scenario: OpenSpec 存量包保持原契约

- **WHEN** 对 `openspec/specs/` 现存 capability 包（R/S 格式、无验证标记）跑 validate
- **THEN** 零 issue，现有回归测试（含 test_spec_regression_uses_existing_v1_to_v7_path）保持通过
- 验证: auto

#### Scenario: 历史 spec7 包零迁移

- **WHEN** 对现存历史 spec 包（checkbox 式 DoD、无 Requirement 标头）跑 validate
- **THEN** 无 V3 issue
- 验证: auto

### Requirement: spec 分档与 V1 联动

spec 包 SHALL 以 README 头部 `spec_tier: lite|full` 为档位唯一事实源；V1 SHALL 按档位检查文件集合（lite = README + 01 + 90；full = 7 件；缺省 full）。

#### Scenario: lite 包通过

- **WHEN** 对声明 `spec_tier: lite` 且含 README/01/90 三件的包跑 validate
- **THEN** 零 V1 issue
- 验证: auto

#### Scenario: lite 缺件被抓

- **WHEN** lite 包缺 90-task-map.md
- **THEN** V1 issue 报出
- 验证: auto

#### Scenario: 无声明按 full 处理

- **WHEN** 对无 spec_tier 头的存量 7 件包跑 validate
- **THEN** V1 行为与现状一致（7 件齐 = 零 issue）
- 验证: auto

### Requirement: V2 死链检查

V2 SHALL 重定义为链接目标存在性检查，按技术设计的路径解析语义执行，不再限制路径形态。

#### Scenario: 死链被抓

- **WHEN** 包内 Markdown 链接指向不存在的文件（含 `./`、`../`、仓库相对三种形态）
- **THEN** V2 issue 报出
- 验证: auto

#### Scenario: 形态解禁

- **WHEN** 包内使用 `../` 上跳或仓库相对路径链接且目标存在
- **THEN** 零 V2 issue
- 验证: auto

#### Scenario: 机器绑定路径被抓

- **WHEN** 包内使用 `/` 开头绝对路径或 `file://` 链接
- **THEN** V2 issue 报出
- 验证: auto

### Requirement: V5 按 Requirement 名回指

90-task-map 的"对应 DoD"列与 02 的"对应 DoD"字段 SHALL 回指 01 中存在的 Requirement 标头名；悬空与重名 SHALL 被 validate 报出。

#### Scenario: 合法名称通过

- **WHEN** 90/02 回指 01 中存在且唯一的 Requirement 名
- **THEN** 零 V5 issue
- 验证: auto

#### Scenario: 悬空名称被抓

- **WHEN** 回指 01 中不存在的 Requirement 名
- **THEN** V5 issue 报出
- 验证: auto

#### Scenario: 重名歧义被抓

- **WHEN** 01 含两个同名 Requirement
- **THEN** validate 报出重名歧义 issue（规则编号由实现定）
- 验证: auto

### Requirement: 模板与纪律落地

x-spec 的模板与 SKILL MUST 体现新契约：01 产出 R/S 结构 DoD，02/90 模板回指 Requirement 名，SKILL 分档化并具备裁判降级与 update 三纪律。

#### Scenario: 01 模板 R/S 化

- **WHEN** 检查 01 模板"完成目标（DoD）"段与追溯矩阵
- **THEN** DoD 段为 Requirement/Scenario 结构、追溯矩阵键列为 Requirement 名
- 验证: auto

#### Scenario: 02/90 模板回指格式

- **WHEN** 检查 02 模板"对应 DoD"字段与 90 模板"对应 DoD"列示例
- **THEN** 均使用 Requirement 名（不再有 DoD#N / 条目 N 式引用）
- 验证: auto

#### Scenario: SKILL 分档化

- **WHEN** 检查 SKILL.md 步骤 6 与 6.2
- **THEN** "全部 7 个产物"强约束改为按 spec_tier 分档（lite 三件定义在列），裁判入口按档位审并注明跳过项
- 验证: auto

#### Scenario: 裁判降级条款

- **WHEN** 检查 SKILL.md 6.2 审核规则
- **THEN** 含"不确定往低判"条款
- 验证: auto

#### Scenario: update 三纪律可执行

- **WHEN** 检查 SKILL.md 更新模式段
- **THEN** 含双向对账的两方向操作定义、不造新文件、"细化 vs 变意图"判定条件（需求本质/系统目标/不变量任一变化 = 变意图）
- 验证: auto

### Requirement: 全量回归

改造后 SHALL 保持存量行为不回退。

#### Scenario: 现有测试全绿

- **WHEN** 运行 `python3 -m pytest test/`（或项目现行测试命令）
- **THEN** 现有 75 个测试全部通过（含新增用例）
- 验证: auto

### 自动化测试责任

- x-dev 必须补齐改动逻辑的单元、契约、边界测试（profile 分派、tier 解析、路径族、悬空/重名回指），并在 `dev-report.md` 写入对应 verify 块。

## 文件导航

- [开发清单](./dev-checklist.md)
- 模块/组件图：`diagram.md`（可选产物，存在时查看）
