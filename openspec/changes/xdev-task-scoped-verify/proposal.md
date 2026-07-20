## Why

`xreq-spec-driven` 允许一个 spec 拆成多个 task，但 verify 的场景对账仍拿整份归属 `spec.md` 的 auto Scenario 作为单个 task 的覆盖范围。结果是同一 spec 下的 task 互相承担对方验收：task-a 明明跑通了自己的场景，也会因为 task-b 的 Scenario 没有证据回指而 uncovered、退出码 1，Gate① 永远过不去。

该缺口是 `xreq-spec-driven` 有意推迟的范围（见其 proposal「后续 change」），不是那份变更的实现 bug。

## What Changes

- **BREAKING**：verify 的验收对账范围从「整份归属 spec.md 的 auto Scenario」收敛为「本 task `dev-checklist.md` 的 `Requirement` 列所承接的 Requirement，及其在归属 spec.md 下的 Scenario」。
- spec 验收解析保留 Scenario 的父 Requirement，作为裁剪依据。
- verify JSON 增加 `requirements`（本 task 承接的 Requirement）与 `expected_auto`（裁剪后的预期自动场景）两个只读字段，人类可读输出增加一行 `requirements:`——让「uncovered 为空」可被区分为「真的覆盖了」还是「范围算空了」。
- 归属 spec.md 的验收标注不足以判定归属时，verify 以退出码 2 拒绝放行（详见 design 决策 6）：**无父 `### Requirement:`** 的 auto Scenario（全局判定），以及**解析不出 `验证: auto|manual`** 的 Scenario（只判本 task 范围内）。后者原本 `mode` 为 `None`，既不进 `expected_auto` 也不进 `manual`，等于自动免检。同时放宽 `VALIDATION_RE` 容忍全角冒号——但容忍只减少误击，兜底靠「解析不出就拦」。
- `expected_auto` 按名称去重；`Requirement` 列的空占位判定与 `parse_deps` 对齐（`—` / `-` / `n/a` / 空同等对待），避免写成 `-` 时范围静默算空却显示成正常绑定。
- verify 块 `cwd` 的解析基准在规格文本中由「仓库根目录」明确为「项目根目录」——承接 `xreq-spec-driven` 已实现的行为（`project_root_of_task_dir`，task 往上四级），本变更只是把该语义并入 `Deterministic verification execution`，代码行为不变。

- **BREAKING**：对账主键从 Scenario 名改为 `(requirement, scenario)`。auto verify 块 SHALL 同时给出 `requirement:` 与 `scenario:`，缺任一即 exit 2；同一 Requirement 内的 Scenario 重名视为结构错误。仅按名字对账时，跨 Requirement 的同名场景一份证据即可点亮两条——去重只能消除输出里的重复项，消不掉这个歧义。
- 输出结构化 `mismatch`：越界绑定（回指的 Requirement 不在本 task scope 内）、父级错配（`requirement:` 与 `scenario:` 在 spec.md 中不构成父子）、mode 漂移（spec 标 manual 却被 auto 块回指，或反之）。
- `--only` 输出 `partial: true` 与 `selected`，且不计算 `uncovered`；x-verify SHALL NOT 用 partial 结果放行 Gate①。现状是抽查一个块也能返回正式 exit 0，未执行块的 `scenario:` 声明照样计入覆盖。
- `manual` 输出改以 spec.md 范围内的 manual Scenario 为准，与 dev-report 的 manual 块对账；现状 `manual` 只来自 dev-report，spec.md 里标 manual 的场景完全不被感知。
- 无父 `### Requirement:` 的 Scenario 不分 auto/manual 一律拦截；scope 内的 Requirement 在 spec.md 下没有任何 Scenario 时同样拦截。

这些能力由上游 [`xreq-spec-driven` tasks.md:56](../xreq-spec-driven/tasks.md) 明确指派给本 change（「task-scoped Scenario 裁剪、Requirement/Scenario 成对绑定、结构化 mismatch 与多 task Gate① 独立闭环」），不再往后推。

dev-report 的 verify 块 schema 因 `requirement:` 而变更，x-dev / x-verify / x-qa-gate / x-fix 四个 skill 的证据读写须同步（见 Impact）。

前置依赖：`xreq-spec-driven` 的 checklist 新表头、`Requirement`/`—` 行契约与 task 归户已落地（代码侧已完成，该 change 的 skill/文档收尾仍在进行）。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `xdev-verification-engine`：task-scoped Scenario 对账范围，以及 verify 结果新增的 `requirements`/`expected_auto` 字段。

## Impact

- 代码：`tools/verify.py`（`acceptance_scenarios` 保留父级、新增 `task_requirements`、`verify` 裁剪对账、验收分层不合法时 exit 2、`expected_auto` 去重）；`tools/req.py` 提供 checklist/spec 解析能力与空占位判定。
- 测试：`test/test_req_engine.py::TestVerifyEvidence`。
- 报告协议：verify JSON 增加两个只读字段，既有字段语义不变。
- 产物格式：dev-report 的 auto verify 块新增 `requirement:`（BREAKING）；`skills/x-dev/templates/dev-report-template.md` 与 x-dev / x-verify / x-qa-gate / x-fix 四个 skill 的证据读写同步。
- skill：`skills/x-verify/SKILL.md` 的 exit 2 分诊须按来源拆开——dev-report 的 verify 块格式/路径问题退回 x-dev，`dev-checklist.md` 缺失或表头不可解析、归属 spec.md 验收分层不合法退回 x-req。verify 新增 checklist 依赖是本变更引入的，该话术不属 `xreq-spec-driven` 的下游适配范围。
- CLI 文案：`tools/xdev.py` 的 `verify` 子命令 help 仍写「对账 README 自动场景」「task 目录（含 README.md 与 dev-report*.md）」，与 req2 路径的实际读取源不符，随本变更一并订正。

## 不在本变更范围（留给后续）

- 验收分层不合法的**早期检测**：在 spec 级 validate（`xdev.py validate docs/spec/<name>`）把「无父 Requirement 的 Scenario」报成硬 issue，让 x-spec2 阶段就拦住。本变更只在 verify 侧拒绝放行（Gate① 不误绿），早期检测跨到 `xdev-task-artifact-engine` capability，与 `xreq-spec-driven` 的同名 delta 交叉，留给后续单独处理。
- x-verify / x-qa-gate 的验收对照**读取源**仍停在 task `README.md`（x-verify `## 输入`、x-qa-gate 的 `risk:` 来源与 RC/R1/R2 对照对象），尚未迁到 checklist 头部 + 归属 `spec.md`——注意这不只是「范围没收窄」，是整个数据源未迁移；该项由 `xreq-spec-driven` 的 tasks 2.3 认领，本变更不代做。x-dev 侧已完成迁移，其「本 task 承接的 Requirement 下每个 auto Scenario 写一个 verify 块」的产出语义与本变更的裁剪范围一致。
