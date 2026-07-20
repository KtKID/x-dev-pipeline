# xreq-spec-driven Tasks

## 0. 前置门禁

- [ ] 0.1 xspec-v2 change 已归档（`xspec-v2-package` 进主 specs），否则本变更的 xspec-v2-package delta MODIFIED 无 base
- [ ] 0.2 冻结上游解析目标：确认 `spec.md`「系统不变量」段与验收 `### Requirement:` 命名、`modules.md`「模块总览」的风险列/状态列/回指 Requirement 列格式，作为 req.py 的解析契约

## 1. 代码与测试

### 1.1 新建 `tools/req.py`（task 确定性引擎）

- [ ] 1.1.1 task 识别：只认 `docs/spec/*/tasks/` 位置（不再有新旧结构检测）；xdev.py 遇此路径委托 req.py
- [x] 1.1.2 `scaffold`：生成含头部（`spec:`、`risk:`）与新表头的 `dev-checklist.md` 骨架（不产 README）；`--with-diagram` 追加 `diagram.md`；幂等保留、`skipped` 报告、`--json`、IO 失败退出码 2
- [ ] 1.1.3 checklist 解析器：解析新表头 `# | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix`，接受 token+emoji 状态，按依赖列建拓扑；作为 status/graph/verify 的唯一解析实现
- [ ] 1.1.4 头部校验：`spec:` 指针存在且指向合法 spec 包；`risk:` ∈ {Q0,Q1,Q2,Q3}
- [ ] 1.1.5 行级校验：每行 `Requirement` 存在且唯一于归属 `spec.md` 验收（跨文件，悬空/重名报 issue，归属 spec 失效降级为单条指针 issue 不级联）；`风险` 与 `任务说明` 非空
- [ ] 1.1.6 spec 级覆盖检查：一个 spec 下所有 `tasks/` 的 checklist 合并后，未被任何行承接的 Requirement 报**硬 issue**（需求漏做）；spec 级运行，单 task 的 validate 不判全覆盖（免多 task 误报）
- [ ] 1.1.7 `status` / `graph`：checklist 的状态压缩与并行批次，输出格式对齐现有引擎
- [ ] 1.1.8 `verify` 数据源：场景对账指向归属 `spec.md` 的 auto 场景，dev-report verify 块以 spec.md 场景名回指
- [ ] 1.1.9 req.py 作为被 xdev.py import 的引擎模块暴露 scaffold/validate/status/graph/verify 函数，退出码与 JSON 契约字段沿用 xdev.py 风格；不单独作主 CLI 入口（命令统一走 `xdev.py`，见 design 决策 A）

### 1.2 `tools/xdev.py` 分流与清理

- [ ] 1.2.1 遇 `docs/spec/*/tasks/` 委托 req.py；**删除旧结构 README 检测、V8-V12 旧分支与 V11/V12 README 契约校验**
- [ ] 1.2.2 路径发现：显式 validate/status/graph/verify/flag 支持 `docs/spec/*/tasks/`（委托 req.py）；自动发现继续不扫 task；不再识别 `dev-pipeline/tasks/`
- [ ] 1.2.3 spec / change 规则零改动；xdev.py 不内嵌任何新表头解析
- [ ] 1.2.4 修 `check_req_scenario`：校验 change delta 时跳过 `## REMOVED Requirements` 段的 Requirement（当前对 REMOVED 的 Requirement 误报 V3 缺 Scenario，与官方 openspec CLI 豁免行为不一致）

### 1.3 测试（`test/`）

- [ ] 1.3.1 req.py 正样例：合法头部 + Requirement 引用 + 风险 → validate 零 issue，status/graph 正常解析
- [ ] 1.3.2 req.py 反样例：缺 `spec:` / risk 非法 / Requirement 悬空 / Requirement 重名 / 风险空 / 表头错 → 逐一被抓
- [ ] 1.3.3 spec 级覆盖：spec 下多 task 合并缺某 Requirement 承接 → 硬 issue；单 task validate 不误报
- [ ] 1.3.4 删除旧结构 task 校验路径及其测试；spec / change 包 validate 回归不变，全仓其余测试全绿
- [ ] 1.3.5 端到端：`xdev.py scaffold`（委托 req.py）→ 填写 → `xdev.py validate` → 模拟 dev-report 回指 → verify 对账通过

## 2. skills

- [ ] 2.1 `skills/x-req`（现 `x-req2`，最终改名回 `x-req`）SKILL：读 `spec.md`+`modules.md` → 定位 `docs/spec/<name>/tasks/` → `xdev.py scaffold`（委托 req.py）→ 填 checklist（任务说明/Requirement 回指/风险标注不变量/涉及文件）→ risk 依托模块风险+不变量映射 → `xdev.py validate` 零 issue → 汇报。不含 README 产出、确认步骤、抽象 risk 判据、qdev/x-plan 引用
- [ ] 2.2 `skills/x-req` 模板：`dev-checklist.md`（新表头 + 头部）+ 按需 `diagram.md`；无 README、无 confirmation 模板
- [ ] 2.3 下游读取适配（单轨，不留旧路）：
  - x-dev：删除「必须有 README」；风险读 checklist 头，需求/验收/架构按 `spec:` 读 `spec.md`/`modules.md`；dev-report verify 回指 `spec.md` 场景名
  - x-verify：复跑场景来源改为归属 `spec.md` 的 auto 场景（对应 `xdev-verification-engine` delta）
  - x-qa-gate：RC/R1 对照对象改为 `spec.md` 验收；risk 从 checklist 头读
  - x-fix：risk 从 checklist 头读

## 3. 仓库文档

- [ ] 3.1 `CLAUDE.md`：管线图 task 落点（`docs/spec/*/tasks/`）、skill 间契约表（README→checklist 头、risk 来源、`req.py`/`xdev.py` 分工、不兼容旧结构声明）
- [ ] 3.2 `README.md` / `README_zh.md`：如涉及 x-req 产物形态描述，同步更新
- [ ] 3.3 归档前自查：tasks 全勾、五个 delta 与实现一致、开放问题有用户结论（`xreq-task-v2` 已删）
