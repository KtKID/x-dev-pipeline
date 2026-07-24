---
name: x-req3
description: |
  x-spec3 的任务拆解 skill。读取 `docs/spec/{spec-name}/spec.md` 的目标、边界与不变量、判断依据、验收清单和直接 GWT Scenarios，生成 `docs/spec/{spec-name}/tasks/{task-name}/dev-checklist.md`，并以 Scenario ID 精确回指实现范围。用户提到 x-req3、要求把 spec3 拆成开发任务，或目标规格含 `spec_version: 3` 时使用。spec2 包继续使用 x-req2。
---

# x-req3 — spec3 场景驱动任务拆解

x-req3 把 spec3 的行为契约压缩成可执行 checklist。spec.md 保留目标、边界、不变量和验收真源；task 只保存执行拓扑、文件范围、风险依据和 Scenario 回指。

## 输入与产物

输入是含 `> spec_version: 3` 的 `docs/spec/<spec-name>/spec.md`。在 `docs/spec/<spec-name>/tasks/<task-name>/` 生成：

- `dev-checklist.md`：必需；头部包含 `spec:` 与 `risk:`，任务表使用 `Scenario IDs` 列。
- `diagram.md`：影响边界达到三个模块或用户明确要求时由 scaffold 生成；节点来自 spec.md 的“影响边界与不变量”表。

不生成 README，也不复制目标、GWT、验收清单和判断表。`Scenario IDs` 只填写 `SC_01` 或 `SC_01, SC_02`；纯技术行写 `None`。

## 就绪门禁

拆解前确认：

1. `python3 tools/xdev.py validate <spec-dir> --json` 对 spec3 返回零 issue；该检查会把任一待确认 J-ID 判为未就绪。
2. spec 含 `> adversarial_risk_version: 1`、`2` 或 `3` 时，运行 `python3 skills/x-adversarial-risk/scripts/risk_contract.py validate-spec <spec.md> --json`。退出码必须为 0；`pending`、评分/预算不一致、审查记录或 Scenario 来源缺失都会停止 scaffold 和 task 写入。v3 要求 RAG 召回场景显式使用 `adversarial-review (rag:<risk-id>)`。退出码为 1 时停止写入，把完整聚合 issue 作为下一次显式 `$x-adversarial-risk` 修正调用的输入；该修正调用执行当前 x-adversarial-risk 定义的五轮契约。
3. spec3 的 J-ID 状态全部为“已确认”。x-spec3 只保存会改变实现或验收的判断，因此任一“待确认”都会停止 scaffold 和 task 写入。
4. Scenario ID 符合 `SC_01` 两位格式、顺序递增且唯一，GIVEN/WHEN/THEN 可直接转成测试，测试层为 unit、smoke 或 e2e。

执行环境缺少命令工具时，直接读取判断依据表、风险元数据、审查记录和 Scenario 来源并执行同一门禁；“待确认”或 `pending` 始终是阻断状态，不能解释为可在开发中处理。未带 adversarial risk 版本标记的存量 spec3 沿用原门禁。

## 拆解规则

1. 以 Scenario 划定 task 的行为范围；同一任务行可用逗号引用多个紧密相关的 Scenario ID，一个 Scenario 也可被实现行和验证行重复引用。
2. 按公开契约与事实源、核心状态变化、边界/失败/并发路径、集成、验证证据形成任务行。强模型可以合并同文件、同依赖、同验证闭环的细碎步骤。
3. `涉及文件`保持在 spec 影响边界内。仓库调查尚无法确定的文件写最小目录或 glob，并在任务说明注明定位动作。
4. 依赖只表达真实前置关系；`graph` 自动计算 ready 和并行批次，无需在文档中重复执行顺序。
5. 一个 spec 下全部 task 合并后覆盖每个 Scenario。一个 task 只负责自己 checklist 引用的 Scenario。

## 风险定级

按 task 触及的最高风险信号定级，并在任务行“风险”列写出 Scenario、模块不变量或 J-ID 依据：

| 等级 | spec3 信号 | 下游路由 |
|---|---|---|
| Q3 | 改动公开契约或关键不变量；安全、持久化/迁移、并发/竞态、不可逆副作用 | x-dev → verify → R1→R2→R3 |
| Q2 | 跨模块集成、失败恢复、资源生命周期、真实 E2E 链路 | x-dev → verify → RC |
| Q1 | 局部功能行为，主要由 unit/smoke 覆盖 | x-dev → verify → 交付 |
| Q0 | 纯机械、文档或内部整理，Scenario 为 `None` | x-dev → verify → 交付 |

用户显式指定的等级优先。风险依据来自 spec3 已记录的边界、不变量、判断和 Scenario；发现缺失信号时回到 x-spec3 补充事实。

## 验证契约

- unit、smoke Scenario 必须在 dev-report 中具有相同 ID 的 `mode: auto` verify 块。
- e2e Scenario 必须具有相同 ID 的 verify 块，可使用 `mode: auto` 或 `mode: manual`。
- `scenario:` 只填写单个 `SC_01` 格式 ID。
- verify 对账范围只包含当前 checklist 的非 `None` Scenario。

## 工作流

高能力模型按一个压缩批次完成拆解：一次读取完整 spec、scaffold 模板和相关目录；一次写完 checklist 与按需 diagram；随后把 validate、status、graph 作为同一验证批次执行。机械检查返回多个 issue 时一次修全并整体复跑。除非文件内容变化，省略重复读取 spec、模板和已验证产物。

1. 读取完整 spec.md，先完成就绪门禁，再确定本 task 的 Scenario、影响模块、不变量、判断依据和测试层；风险审查新增 Scenario 与第一版 Scenario 使用同一拆解规则。
2. 运行 `python3 tools/xdev.py scaffold <task-dir>`；达到三个影响模块时自动生成图，少于三个模块但用户要求图时加 `--with-diagram`。
3. 填写 `dev-checklist.md`，删除模板注释与占位行。每个 Scenario ID 必须在 spec.md 中存在且唯一；一个任务行可引用多个 ID。
4. scaffold 生成 `diagram.md` 时填写它，每个影响边界模块恰好一个节点。
5. 运行 `python3 tools/xdev.py validate <task-dir> --json`，修复所有机械 issue。
6. 运行 `status` 和 `graph`，确认状态、依赖与并行批次可解析。
7. 报告 task 路径、Scenario 覆盖、risk 及其证据、validate 结果和下一步 `x-dev <task-dir>`。

## 自审

- checklist 中每个非 `None` Scenario ID 都精确存在于 spec3。
- spec 下全部 task 合并后覆盖所有 Scenario。
- 带 adversarial risk v1、v2 或 v3 标记的 spec 已通过风险契约门禁，审查状态为 `skipped-standard` 或 `complete`。
- 高损失边界、失败、并发和资源 Scenario 已落到实现或验证任务。
- 每行文件范围足够执行，依赖图无悬空和环。
- task 文档没有复述 spec 正文。
