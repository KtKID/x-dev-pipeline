# xreq-spec-driven Design

## Context（当前仓库事实）

- spec v2 已实现：`docs/spec/<name>/` 的 `spec.md`（含「系统不变量」段、「用户要求追溯」U-ID、验收 `### Requirement:`/`#### Scenario:`）与 `modules.md`（含「模块总览」表：风险列 低/中/高、状态列「可进入 x-req」、回指 Requirement 列）已是需求与模块真源。
- x-req 现状：产 `README.md` + `dev-checklist.md`（+按需 `diagram.md`）。README 扛 `risk:`、需求要点、涉及模块、架构拆分、技术设计、验收 R/S——其中需求/模块/验收/架构是对 spec 包的复述。
- risk 判据现状：`xreq-lean-planning` 的「写入前只做一次确认」用抽象清单定级（Q3=鉴权/并发/状态机…），与 spec 包信号无关联。
- 工具现状：`tools/xdev.py` 单文件承载 spec7/spec2/change/task 全部校验 + scaffold/instructions/status/graph/verify/flag，体量已达数千行，任何 task 侧改动都要在其中穿插分支。
- checklist 现状：旧任务表 `# | 任务 | 涉及文件 | 依赖 | 状态 | fix`，token+emoji 双轨状态，是 status/graph 编排引擎的解析契约。
- 历史 task：`dev-pipeline/tasks/` 下已有带 README 的旧结构 task，是已完成的历史档案。

## Goals / Non-Goals

**Goals：**
- x-req 零复述：需求/模块/验收信息只存在于 spec 包，checklist 只留指针与逐行回指。
- risk 有据：定级依据 spec 包已声明的模块风险与系统不变量，而非 x-req 自造判据。
- 工具解耦：task 规划引擎归 `tools/req.py`，verify 执行与对账归 `tools/verify.py`，xdev.py 保留统一 CLI 与校验编排。
- 单轨清爽：pipeline 只认一种 task 结构，不维护新旧双轨。
- spec 包回归安全：v1/v2 spec 包、OpenSpec 存量包的 validate 行为完全不变（spec 包层面，与 task 无关）。

**Non-Goals：**
- `x-qdev` / `x-plan` 退役——已由 `risk-routed-development-flow` 既有 Requirement 承接，本变更只保证不复活引用。
- spec2 包内 U/J/D 账本命令与 spec check 门禁——属其他变更范围。
- 历史 `dev-pipeline/tasks/` task——不迁移、不兼容、不再被工具支持，作为死档案保留。

## Decisions（拟议行为 + 依据/弃选）

1. **新建 `tools/req.py` 承载 task 引擎**
   - 依据：xdev.py 已过载，改一处 task 逻辑要在数千行里穿插；req 流程（scaffold→解析→校验 checklist）是内聚子域，独立成文件后「改 req 只动 req.py」，可从零写干净解析器，不背旧分支包袱。
   - 弃选：继续在 xdev.py 加 task 分支（进一步膨胀，回归风险高）。
2. **README 退役、checklist 承重**
   - 依据：README 八段里需求/模块/验收/架构四段是 spec 包复述；剩 risk 与拆解要点几行，独立成文件是两文件税。
   - 弃选：保留瘦身版 README（仍两个文件，「写哪个」的分界说不清）。
3. **checklist 表头升级 + 解析器**
   - 依据：用户要求每行携带 `Requirement` 来源与 `风险`，塞进旧列会失去结构化校验能力。本变更重写 task 引擎，正式定新表头契约，由 req.py 作唯一解析实现。
   - 弃选：保持旧表头把回指塞进「任务」列（无法机器校验 Requirement 悬空）。
4. **risk 依托 spec 信号**
   - 依据：`modules.md` 风险列与 `spec.md` 系统不变量已是权威风险来源；x-req 复用它们，消除自造判据的漂移。
   - 弃选：x-req 保留抽象判据清单（与 spec 信号双源，且脱离具体不变量）。
5. **task 归户 `docs/spec/<name>/tasks/`**
   - 依据：x-req 现行规则已是「一个 task 只归一个 spec」——task:spec 多对一，按归属分目录不撕裂；一个 spec 目录即得需求+实现史全景。
   - 弃选：留 `dev-pipeline/tasks/` 平铺（归属只是字段，查询弱）。
6. **取消 x-req 确认**
   - 依据：需求确认已在 spec 阶段（用户确认 spec.md）完成；x-req 不重新定义需求，无需二次确认。
   - 弃选：保留 Q2/Q3 一次确认（对已确认需求的重复闸）。
7. **不兼容旧结构（单轨）**
   - 依据：新旧双轨要在 validator、scaffold、注册表、diagram 校验、五个下游 skill 里各留两条路——永久双轨税、bug 面翻倍；历史 task 是已完成死数据，没有「用旧 skill 继续产旧结构 task」的需求。一刀切单轨，删掉所有旧结构分支（含 V11/V12 README 校验）。
   - 弃选：新旧并存零迁移（省一次性清理，换永久维护成本）。历史 task 不删、不迁，只是工具不再解析。
8. **下游适配单轨、同变更内完成**
   - 依据：不兼容后下游只需读新结构一条路，不用「看到 README 走老路」；实现上可放在 req.py 与 x-req 主体成型后，但必须在同一变更内接完，不留 req→dev 断裂。
   - 弃选：下游留双轨兼容（与「不兼容」决策矛盾）。
9. **测试夹具按「遮蔽关系」分组，不用单个「全缺」样例**
   - 依据：一个「什么都缺」的样例会被三类遮蔽吃掉——① **降级遮蔽**：`spec:` 指针失效时按既定规矩不再级联查行级回指，两者同时写坏只会报指针错；② **解析遮蔽**：表头错则整表读不出，全部行级检查被跳过；③ **层级/命令不同**：spec 级覆盖缺口单 task 不判、verify 的 `uncovered` 属另一条命令。被遮的规则**看似测了实则没测**，是假覆盖。
   - 分法：1 个完整正样例（验「不误报」）+ 6 个坏样例（A 行级错合并、B 表头错、C 指针失效、D risk 非法、E spec 级覆盖缺口、F verify 无回指）。互不遮蔽的错合并进同一样例的不同行，会遮蔽的必须分开。
   - 断言纪律：每个坏样例断言「预期规则 issue 出现」**且**「无意外 issue」；只断「报错了」会在报错原因漂移后仍显绿（假绿）。
   - 弃选：单个全缺样例（假覆盖）；每个指标各一个样例（冗余——互不遮蔽的错本可合并）。
10. **归属 spec 包按 task 实际位置推定，`spec:` 改作核对项**
    - 依据：task 固定住在 `<项目>/docs/spec/<name>/tasks/<task>/`，**位置本身已唯一确定归属**。用头部指针字符串去拼路径必须先有个"根"，而实现里复用了 `PLUGIN_ROOT`（插件仓库根，本是给插件自带模板用的）——拿它拼用户项目数据，在插件仓库之外的真实项目里**必然解析失败**（spec 包明明就在也报找不到）；若插件仓库恰好有同名 spec，还会**静默校验错对象**（比报错更难查）。按位置推定不依赖任何根变量、也不依赖调用方 cwd，插件仓库内外一致成立。
    - `spec:` 的去向：保留并改作**核对项**（与推定归属不一致即报），把"写错路径 / 清单放错目录"从静默错误变成可抓的错误。弃：删掉指针（清单里看不出归属，只能靠目录路径认）；弃：留着但不校验（写错不报，反倒误导）。
    - 边界：`PLUGIN_ROOT` **仅**保留给插件自带资源（模板）解析；verify 块的 `cwd` 改为相对**项目根**（task 往上四级）而非插件根——命令跑在用户项目里。
    - 回归证据：固化夹具置于 `test/fixtures/req2/docs/spec/demo/`，该位置**不在**插件根的 `docs/spec/` 下——旧实现必然解析失败，因此**夹具位置本身**就是这条契约的看门狗（防以后有人改回按根拼路径）。
## tools/req.py ↔ tools/verify.py ↔ tools/xdev.py 边界

| 关注点 | `tools/req.py` | `tools/verify.py` | `tools/xdev.py` |
|---|---|---|---|
| task（`docs/spec/*/tasks/`） | scaffold / validate / status / graph | verify 的执行与对账 | 统一 CLI，委托对应引擎 |
| spec 包（spec.md / modules.md / v1 七件） | 提供 req2 task 所需解析能力 | 读取验收 Scenario 与 Requirement scope | spec2 / spec7 校验原样 |
| change 包 | — | — | 校验原样 |
| checklist 表头解析 | 唯一实现（供 status/graph/verify 复用） | 调用 req.py，不自造 | 需要时 import req.py，不自造 |
| flag / issue ledger | — | — | 原样 |
| 旧结构 task（dev-pipeline/tasks/） | 不支持 | 迁移期间保留 legacy verify | 旧校验分支按 1.2.1 后续删除 |

衔接（已决 A）：命令入口统一 `python3 tools/xdev.py <cmd>`；scaffold/validate/status/graph 委托 `req.py`，verify 委托 `verify.py`。两个模块都作为被 import 的引擎模块，不单独作主 CLI 入口——下游 x-dev/x-verify/x-qa-gate 的命令零变化。

Gate① 的 task-scoped Scenario 裁剪、Requirement/Scenario 成对绑定与结构化 mismatch 由后续独立 change `xdev-task-scoped-verify` 承接；归档顺序为本变更在前。

## Risks / Trade-offs

- [风险] 删旧结构 task 校验会让现有旧结构测试失败 → 一并删除相关测试；spec/change 包回归测试保留验证「spec 包层面零改动」。
- [风险] Requirement 跨文件校验（checklist → 归属 spec.md）引入跨文件读取 → 归属 spec 缺失/非法时降级为「指针失效」单条 issue，不级联。
- [破坏] 历史 `dev-pipeline/tasks/` task 变死数据，工具不再解析 → 可接受：它们已完成，需查阅时靠文件与 git 本身；不再有工具级支持。
- [取舍] req.py 与 xdev.py 短期有少量重复的通用工具函数 → 换取子域解耦；可后续抽公共模块。

## Migration Plan

不兼容旧结构、无数据迁移。新 task 一律进 `docs/spec/*/tasks/`。历史 `dev-pipeline/tasks/` 不迁移、不再被工具识别或校验，作为死档案保留。删除 xdev.py 里旧结构 task 的校验路径（V8-V12 旧分支、V11/V12 README 校验）及相关测试。回滚：移除 req.py 与新模板、恢复 xdev.py 旧路径（历史 task 数据未被触碰）。

## Open Questions

1. （已决 → A）命令入口统一走 `xdev.py` 委托：用户/skill 敲 `xdev.py <cmd>`，xdev.py 检测 task 后委托 req.py 引擎；req.py 不单独作主 CLI，下游命令零变化。
2. risk 头部机械校验强度：仅校验 `risk:` 是合法值（轻），还是 req.py 交叉读 `modules.md` 风险列做一致性校验（强，引入跨文件读取）——推荐先轻，交叉一致性作为 x-req 语义自审。
3. （已决）Requirement 覆盖闭合：**硬 issue**，且在 **spec 级**（一个 spec 下所有 `tasks/` 的 checklist 合并）判定——未被任何 task 承接的 Requirement 报错；单 task 的 validate 不判全覆盖，免多 task 互相误报。
