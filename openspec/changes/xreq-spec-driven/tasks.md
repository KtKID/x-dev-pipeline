# xreq-spec-driven Tasks

## 0. 前置门禁

- [ ] 0.1 xspec-v2 change 已归档（`xspec-v2-package` 进主 specs），否则本变更的 xspec-v2-package delta MODIFIED 无 base
- [ ] 0.2 冻结上游解析目标：确认 `spec.md`「系统不变量」段与验收 `### Requirement:` 命名、`modules.md`「模块总览」的风险列/状态列/回指 Requirement 列格式，作为 req.py 的解析契约

## 1. 代码与测试

### 1.1 新建 `tools/req.py`（task 确定性引擎）

- [ ] 1.1.1 task 识别：只认 `docs/spec/*/tasks/` 位置（不再有新旧结构检测）；xdev.py 遇此路径委托 req.py
- [x] 1.1.2 `scaffold`：生成含头部（`spec:`、`risk:`）与新表头的 `dev-checklist.md` 骨架（不产 README）；`--with-diagram` 追加 `diagram.md`；幂等保留、`skipped` 报告、`--json`、IO 失败退出码 2
- [x] 1.1.3 checklist 解析器：解析新表头 `# | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix`，接受 token+emoji 状态，按依赖列建拓扑；作为 status/graph/verify 的唯一解析实现
- [x] 1.1.4 头部校验：`spec:` 指针存在且指向合法 spec 包；`risk:` ∈ {Q0,Q1,Q2,Q3}
- [x] 1.1.5 行级校验：每行 `Requirement` 存在且唯一于归属 `spec.md` 验收（跨文件，悬空/重名报 issue，归属 spec 失效降级为单条指针 issue 不级联）；`风险` 与 `任务说明` 非空
- [x] 1.1.6 spec 级覆盖检查：一个 spec 下所有 `tasks/` 的 checklist 合并后，未被任何行承接的 Requirement 报**硬 issue**（需求漏做）；spec 级运行，单 task 的 validate 不判全覆盖（免多 task 误报）
- [x] 1.1.7 `status` / `graph`：checklist 的状态压缩与并行批次，输出格式对齐现有引擎
- [x] 1.1.8 `verify` 数据源：场景对账指向归属 `spec.md` 的 auto 场景，dev-report verify 块以 spec.md 场景名回指；实现现统一归 `tools/verify.py`
- [x] 1.1.9 req.py 作为被 xdev.py import 的引擎模块暴露 scaffold/validate/status/graph 函数；verify.py 暴露 verify 函数；退出码与 JSON 契约字段沿用 xdev.py 风格，命令统一走 `xdev.py`

### 1.2 `tools/xdev.py` 分流与清理

- [ ] 1.2.1 遇 `docs/spec/*/tasks/` 委托 req.py；**删除旧结构 README 检测、V8-V12 旧分支与 V11/V12 README 契约校验**
- [x] 1.2.2 路径发现：显式 validate/status/graph/verify/flag 支持 `docs/spec/*/tasks/`；自动发现继续不扫 task；validate/status/graph 委托 req.py，verify 委托 verify.py；`flag` 不需要委托——其表格定位按关键词找 "#"/"状态" 列，不关心中间列数，对新旧表头原生兼容，已用 req2 checklist 实测验证（T3 正确降级 + ledger 正确生成）
- [x] 1.2.3 spec / change 规则零改动；xdev.py 不内嵌任何新表头解析
- [ ] 1.2.4 修 `check_req_scenario`：校验 change delta 时跳过 `## REMOVED Requirements` 段的 Requirement（当前对 REMOVED 的 Requirement 误报 V3 缺 Scenario，与官方 openspec CLI 豁免行为不一致）
- [x] 1.2.5 修复 `instructions` 命令的产物模板路径指向已搬迁的旧目录 `skills/x-req/`：`ba2ea44` 把旧结构 `skills/x-req` 整体归档到 `deprecated/x-req/`（非改名到 `x-req2`——`x-req2` 是表头/流程都不同的全新精简结构，无 README 模板），`xdev.py` 的 `ARTIFACTS` 注册表（readme/dev-checklist/diagram 三个模板路径）未同步，导致 `instructions` 命令三个 artifact 全部读模板失败（`FileNotFoundError`，标准库测试 `test_xdev_artifacts.py::TestInstructions` 首次跑全量测试时暴露）。旧结构 `instructions`/V8-V12 校验按 1.2.1（未做）仍存活，故模板须指向表头兼容的旧版本：改为 `deprecated/x-req/templates/...`（曾误改成 `skills/x-req2/templates/...`，因表头不兼容且缺 README 模板已改正）

### 1.3 测试夹具（`test/`）

分组原则见 design 决策 9（按遮蔽关系分，避免假覆盖）。每个坏样例 SHALL 断言「预期规则的 issue 出现」**且**「无意外的其他 issue」——只断「报错了」会在原因漂移后仍显绿（假绿）。

- [x] 1.3.1 **正样例（验不误报）**：一个 spec 包（`spec.md`+`modules.md`）+ 多个 task，Requirement 全被承接、状态与依赖合法、含 `diagram.md` → `validate` 零 issue，`status`/`graph` 拓扑与批次正确；另加一个无图变体，验证缺 `diagram.md` 时跳过图一致性校验。覆盖 delta 场景：合法 checklist 通过 / 合法回指通过 / 全部 Requirement 被覆盖 / 接受合法 checklist / 缺少 diagram 时跳过 V10
- [x] 1.3.2 **坏 A · 行级错合并**（互不遮蔽，可塞同一样例的不同行）：第 1 行 Requirement 悬空、第 2 行 Requirement 重名、第 3 行风险空、第 4 行任务说明空、第 5 行依赖悬空、第 6 行状态非法 → 一次 `validate` 报齐 6 条对应 issue。覆盖：悬空回指被抓 / 行缺必填列被抓 / 拒绝悬空依赖 / 拒绝非法状态
- [x] 1.3.3 **坏 B · 表头错**（必须单独：整表读不出，会遮蔽全部行级检查）：表头少列或改名 → 报表头不匹配，并断言此时**不**误报行级 issue。覆盖：拒绝错误表头
- [x] 1.3.4 **坏 C · spec 指针失效**（必须单独：按既定规矩会抑制行级回指检查）：`spec:` 指向不存在目录，同时行内故意写悬空 Requirement → **只报一条指针失效**，不为每行回指重复报错（正是验证「降级不级联」这条规矩本身）。覆盖：缺 spec 指针被抓 / 归属 spec 失效不级联
- [x] 1.3.5 **坏 D · risk 非法**：`risk: Q9` 或缺 `risk:` 行 → 报 risk issue。覆盖：非法 risk 被抓
- [x] 1.3.6 **坏 E · spec 级覆盖缺口**（必须单独：层级不同，单 task 不判）：一个 spec + 多个 task，合并后某条 Requirement 无人承接 → spec 级检查报**硬 issue**；同时断言对单个 task 跑 `validate` **不**报覆盖缺口。覆盖：有 Requirement 没人承接 / 单 task validate 不判全覆盖
- [x] 1.3.7 **坏 F · verify 无证据回指**（必须单独：另一条命令，需 dev-report）：dev-report 缺某个 auto 场景的回指块 → `verify` 以退出码 1 结束，该场景出现在 `uncovered`；另含正向对照（有回指则不进 uncovered）。覆盖：自动场景缺少证据回指 / 自动场景已有证据回指
- [x] 1.3.8 **端到端**：`xdev.py scaffold`（委托 req.py）→ 填清单 → `xdev.py validate` 零 issue → `status`/`graph` → 造 dev-report 回指 → `verify` 对账通过
- [x] 1.3.9 回归：spec / change 包 validate 行为不变，全仓其余测试全绿

> 老流程清理（删除旧结构 task 校验路径及其旧测试）另行处理，不计入 req2 收尾。

## 2. skills

- [ ] 2.1 `skills/x-req`（现 `x-req2`，最终改名回 `x-req`）SKILL：读 `spec.md`+`modules.md` → 定位 `docs/spec/<name>/tasks/` → `xdev.py scaffold`（委托 req.py）→ 填 checklist（任务说明/Requirement 回指/风险标注不变量/涉及文件）→ risk 依托模块风险+不变量映射 → `xdev.py validate` 零 issue → 汇报。不含 README 产出、确认步骤、抽象 risk 判据、qdev/x-plan 引用
- [ ] 2.2 `skills/x-req` 模板：`dev-checklist.md`（新表头 + 头部）+ 按需 `diagram.md`；无 README、无 confirmation 模板
- [ ] 2.3 下游读取适配（单轨，不留旧路）：
  - x-dev：删除「必须有 README」；风险读 checklist 头，需求/验收/架构按 `spec:` 读 `spec.md`/`modules.md`；dev-report verify 回指 `spec.md` 场景名
  - x-verify：复跑场景来源改为归属 `spec.md` 的 auto 场景（对应 `xdev-verification-engine` delta）
  - x-qa-gate：RC/R1 对照对象改为 `spec.md` 验收；risk 从 checklist 头读
  - x-fix：risk 从 checklist 头读

> task-scoped Scenario 裁剪、Requirement/Scenario 成对绑定、结构化 mismatch 与多 task Gate① 独立闭环由后续 change `xdev-task-scoped-verify` 承接。

## 3. 仓库文档

- [ ] 3.1 `CLAUDE.md`：管线图 task 落点（`docs/spec/*/tasks/`）、skill 间契约表（README→checklist 头、risk 来源、`req.py`/`xdev.py` 分工、不兼容旧结构声明）
- [ ] 3.2 `README.md` / `README_zh.md`：如涉及 x-req 产物形态描述，同步更新
- [ ] 3.3 归档前自查：tasks 全勾、五个 delta 与实现一致、开放问题有用户结论（`xreq-task-v2` 已删）
