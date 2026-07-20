---
name: x-req2
description: |
  Spec 驱动 task 拆解 skill：只服务已有 docs/spec/<spec-name>/ 归属的 task，读 spec.md 与 modules.md 直接拆 dev-checklist.md（新头部 spec:/risk:，新表头 任务说明/Requirement/风险），不产出 README，不复述需求/模块/验收内容，risk 依托 spec 包既有信号定级（不自造判据）。x-req2 是 openspec/changes/xreq-spec-driven 变更的过渡期命名，该变更单轨替换旧版 x-req（旧结构已删除、不再维护），实现完成后会改名替换 skills/x-req。

  调用时机（命中任一即优先使用）：
  - 用户提到 x-req2。
  - 用户给出的 task 明确归属某个已建好的 docs/spec/<spec-name>/ 包（该 spec 所属模块状态已是"可进入 x-req"）。
  - 已跑过 x-spec2 建模，需要把稳定 spec 拆成可执行 task。

  不要用：历史 `dev-pipeline/tasks/` task 的更新（旧结构已删除，工具不再识别，作为死档案保留）；项目未建 docs/spec/，或 spec 所属模块仍是"探索中"或"方案确认"（先用 x-spec2 建好/稳定 spec 包，pipeline 不支持无 spec 归属的新 task）。
---

# x-req2 — Spec 驱动的 task 拆解

x-req2 服务已有 spec 归属的 task 拆解，产物只留 `dev-checklist.md`，需求、模块、架构与验收内容留在归属 spec 包一份，task 侧只放指针与逐行回指。`x-req2` 是 `openspec/changes/xreq-spec-driven` 变更的过渡期命名——该变更是单轨替换（不兼容旧结构）：旧版 `skills/x-req/`（`dev-pipeline/tasks/`，README + 旧表头）已删除、不再维护，pipeline 只认这一种结构。

## 产物

在 `docs/spec/<spec-name>/tasks/<task-name>/` 中生成：

- `dev-checklist.md`：必需。头部含 `spec:`（归属 spec 包路径）与 `risk:`（Q0-Q3）；任务表表头 `# | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix`。
- `diagram.md`：按需（涉及至少三个模块，或用户明确要求）。节点对照归属 `modules.md` 的模块名清单。

不产出 `README.md`、`changelog.md`、确认文档。需求、模块、架构与验收内容 SHALL NOT 复制进 task，只在 checklist 中以 `spec:` 指针与逐行 `Requirement` 回指引用归属 spec 包。

## 定级

| 等级 | 判据（来自归属 spec 包既有信号） | 流程 |
|---|---|---|
| Q3 | task 覆盖的 Requirement 会改动 `spec.md#系统不变量`，或所属 `modules.md` 模块风险列标"高" | x-dev → verify → R1→R2→R3 |
| Q2 | 所属 `modules.md` 模块风险列标"中"，且不触及不变量 | x-dev → verify → RC |
| Q0/Q1 | 局部低风险改动，不触及不变量、所属模块风险不为中/高 | x-dev → verify → 交付 |

risk 定级 SHALL NOT 自造判据，只读归属 spec 包既有信号。用户显式指定的风险覆盖默认定级。**不做二次确认**——需求确认已在 x-spec2 阶段（用户确认 spec.md）完成。

## 流程

1. 定位归属 spec：确认目标 task 对应的 `docs/spec/<spec-name>/` 已存在，`spec.md`/`modules.md` 已通过校验；所属模块状态为"探索中"或"方案确认"（不稳定模块）时退回 x-spec2 完成建模，不派生 task。新建 task 落 `docs/spec/<spec-name>/tasks/<task-name>/`；更新已有 task 先读现有 checklist，保留无关行。
2. 读 `spec.md`（系统不变量、Requirement/Scenario 验收）与 `modules.md`（模块职责、依赖、风险列、状态、回指 Requirement），确定本次 task 覆盖哪些 Requirement、涉及哪些模块。
3. 按"定级"表判断 risk；用户显式指定时覆盖默认定级。
4. 运行 `python3 tools/xdev.py scaffold <task-dir>`（新结构由 xdev.py 委托 `tools/req.py` 引擎处理）；涉及图或用户要求时加 `--with-diagram`。
5. 填写 `dev-checklist.md`：头部 `spec:` 指针 + `risk:`；逐行填 `任务说明`、回指的 `Requirement`（名字须在归属 spec.md 验收中存在且唯一；纯技术/重构行没有对应 Requirement 时该列写 `—`）、`风险`（该行触及的 `spec.md#系统不变量` 或 `modules.md` 模块风险等级，无触及写 `—`）、`涉及文件`、`依赖`、初始状态 `[ ] ⏳`。按需填写 `diagram.md`，节点对照 `modules.md` 模块名。删除模板 HTML 注释与占位符。更新已有 task 时在头部追加一行 `updated: YYYY-MM-DD <summary>`。
6. 运行 `python3 tools/xdev.py validate <task-dir>`，修复机械 issue 直到零 issue（新结构校验由 xdev.py 委托 `tools/req.py` 执行，命令入口不变）。
7. 判断自审（机械校验之外，主 agent 检查；任一失败时修复内容并重跑第 6 步）：
   1. **需求覆盖**：每行 `Requirement` 可追溯到归属 spec.md 的某个 Requirement；且这个 spec 下所有 task（含既有 task）合并后，spec.md 每条 Requirement 至少被一行承接——出现缺口时补入承接该 Requirement 的任务行，不留给"以后再说"。这是 spec 级的硬性交接前提，不是要求单个 task 独自覆盖全部 Requirement（task:spec 多对一）。
   2. **DoD 由 spec 承接**：验收 DoD 由归属 spec.md 的 Scenario 客观承接，不在 task 侧另造一份主观 DoD。
   3. **架构归属**：`涉及文件` 与 `modules.md` 已确认的模块边界一致。
   4. **风险标注**：`风险` 列如实标注该任务触及的 `spec.md#系统不变量`，并按映射复核头部 `risk:`。
8. 汇报：task 路径、产物清单（仅 `dev-checklist.md`，按需 `diagram.md`，不含 README）、risk 定级依据、零 issue 校验结论、判断自审结果、下一步命令 `x-dev <task-name>`。

## 内容规则

- checklist 表头固定 `# | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix`，token+emoji 双轨状态与依赖拓扑规则与旧结构一致。
- 需求、模块、架构、验收内容不复制进 task，只用指针/回指引用归属 spec 包；risk 判据不区分 Q 等级——checklist 形态在所有风险等级下相同，只有头部 `risk:` 值与下游评审路由不同。
- 纯技术/重构任务没有对应 spec.md Requirement 时，`Requirement` 列写 `—`，不计入覆盖率。
- spec 级 Requirement 覆盖是硬性门槛：一个 spec 包 `tasks/` 下所有 task 的 checklist 合并后，spec.md 每条 Requirement 必须被至少一行承接；单个 task 的校验不判全覆盖，避免多 task 拆分互相误报。
- x-req2 不改 spec 包内容；拆 task 时发现 spec.md 表述需要调整，回到 x-spec2 更新，不在 task 侧绕过。
- 历史 `dev-pipeline/tasks/` task 是死档案，已不再被工具识别或校验，不属于本 skill 范围；新 task 一律要求 spec 归属，没有归属先用 x-spec2 建 spec 包，不再有"跳过 spec 直接建 task"的路径。

## 过渡状态说明

`x-req2` 不是永久并列品种（不同于 x-spec/x-spec2 的长期并存模式），是 `openspec/changes/xreq-spec-driven` 变更的过渡期命名。该变更单轨替换（design.md Decision 7：不兼容旧结构）：旧版 `skills/x-req/`（`dev-pipeline/tasks/`、README + 旧表头、xdev.py 的 V8-V12 校验分支）已删除，历史 task 作为死档案不再被工具识别或校验；pipeline 之后只认 `docs/spec/*/tasks/` 一种结构，新 task 一律要求 spec 归属。待 `tools/req.py` 引擎（tasks.md 1.1/1.2）与下游 skill（x-dev/x-verify/x-qa-gate/x-fix，tasks.md 2.3）适配在同一变更内完成后，`x-req2` 会改名替换为 `skills/x-req`——本节与本文件名届时都需要同步更新，不是稳定契约。
