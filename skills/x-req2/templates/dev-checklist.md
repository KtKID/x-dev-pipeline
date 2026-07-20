# <task-name> · 开发清单

<!--
x-req2 dev-checklist 模板填写规则（仅适用于 docs/spec/<spec-name>/tasks/ 下、有 spec 归属的新结构 task）：
- 头部只需两行：`spec:`（归属 spec 包路径，须存在且为合法 v2 包）与 `risk: Q0|Q1|Q2|Q3`（task 级路由依据）。
- risk 定级只读归属 spec 包信号，不自造判据：任务触及 spec.md#系统不变量、或所属 modules.md 模块风险列标"高" → Q3；模块风险列标"中"且不触及不变量 → Q2；仅局部低风险改动 → Q0/Q1。用户显式指定的风险覆盖默认定级。
- 任务表 "Requirement" 列：填归属 spec.md 验收中存在且唯一的 Requirement 名；纯技术/重构行没有对应 Requirement 时写 `None`（不计入覆盖率统计）。
- 任务表 "风险" 列：该行触及的 spec.md#系统不变量 或 modules.md 模块风险等级；无触及写 `None`。
- 覆盖是 spec 级门槛：这个 spec 下所有 task 的 checklist 合并后，spec.md 每条 Requirement 须至少被一行承接；单个 task 不必独自覆盖全部 Requirement。
- 需求、模块、架构、验收内容不复制进本文件，只引用归属 spec 包（spec.md + modules.md）。
- "涉及文件"列可写 product:<相对路径> 锚点（可选），供 status 命令做产物存在性交叉验证。
- 状态列采用 token+emoji 双轨格式，规则与旧结构 dev-checklist 一致（见下方状态体系）。
- "依赖"列写前置任务编号（如 T1 或 #1 或 T2,T3），无依赖写 None；引擎据此做拓扑排序。
- P0：阻塞性，必须立即做；P1：重要，必须完成；P2：增强，可后续处理（写在"任务说明"描述里）。
- 质检（"涉及文件"列标注 🔍 前缀）：涉及核心业务逻辑、数据持久化/迁移、安全相关、跨模块集成、公共 API 变更；标记 🔍 的任务在 x-dev 并行执行时需立即做代码审查，审查通过才继续。
- 更新已有 task 时，在头部追加一行 `updated: YYYY-MM-DD <summary>`，保留无关行不动。
- 清除本注释块与占位符后再交付。
-->

**状态体系**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

需求、模块与验收 Scenario 见归属 spec 包（`spec.md` + `modules.md`）。本清单只跟踪任务拆解与状态，不复述 spec 内容。

---

> spec: docs/spec/<spec-name>
> risk: <Q0|Q1|Q2|Q3>

## 任务清单

| # | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---------|-------------|------|---------|------|------|-----|
| T1 | <P0 契约与事实源：定义公开入口、schema/config 或 API contract> | <Requirement 名 或 None> | <触及的不变量/模块风险，或 None> | <path> | None | [ ] ⏳ | None |
| T2 | <P0 核心实现：在主边界类内实现核心行为和状态变化> | <Requirement 名 或 None> | <触及的不变量/模块风险，或 None> | <path> | T1 | [ ] ⏳ | None |
| T3 | <P1 适配集成：接入 CLI/Web/API/repository 等外部入口> | <Requirement 名 或 None> | <触及的不变量/模块风险，或 None> | <path> | T2 | [ ] ⏳ | None |
| T4 | <P1 验证闭环：补单元/契约/边界测试和 Smoke/E2E> | <Requirement 名 或 None> | <触及的不变量/模块风险，或 None> | <path> | T2,T3 | [ ] ⏳ | None |

## 并行机会

无依赖关系、可并行起子 agent 同时做（也可由 `python3 tools/xdev.py graph <task-dir> --json` 的 parallel_batches 自动算出）：

- <列出无依赖的任务组，如 T3 与 T4 在 T2 完成后可并行>

## 推荐执行顺序

```
T1 → T2 → [T3 ‖ T4]
```

## fix-attempts 记录

每个 task 自身走完整 verify + qa-gate 流程时的 fix 次数累计，超 6 次须升级。

| Task | fix 次数 | 触发节点 | 备注 |
|------|---------|---------|------|
| None | 0       | None    | 尚未开始 |

---

*产出时间：<date>*
