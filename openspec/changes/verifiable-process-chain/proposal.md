## Why

`x-tech-design` 已经建好，但按它自己 SKILL.md:76 的声明——「不修改现有 `x-req` 行为，也不向其添加自动门禁；不自动调用 x-req」——它是一个**可选文档而非门禁**。用户报的三类实际损失，各自对应一个结构性缺口，而不是执行不力：

| 实际损失 | 结构性缺口 |
|---|---|
| 插件开发功能正确，但违反架构规定 | 架构约束只存在于 `tech-design.md` 散文里；x-req 不校验、x-verify 六项对账全无设计一致性检查；`x-audit-arch` 按 SKILL.md:11 是「不在主流程内、手动触发、里程碑后」，发现时代码已交付 |
| 测试用例不充分，重要 case 没写 | spec 的 GWT 只描述**用户可观察行为**（功能视角），没有**技术边界契约**（协议非法输入、并发、幂等、失败恢复、超时）。CLAUDE.md:62 把单元/契约/边界测试交给「x-dev 按实际改动补齐」，等于作者自评；R3 是事后抽查且只有 Q3 走完整版 |
| 弄虚作假（伪造测试通过） | `dev-report` 规定「只记结论，不粘贴测试输出」，`x-verify` 规定「不重跑测试，只核对结论与证据是否一致」。两份文档互相对账 = **完全自证的闭环**，没有任何外部事实锚点 |

第三点是根因性质的：**Gate① 的可信度完全建立在 dev 的诚实上**。洪乐潼那场访谈里真正可迁移的不是 Lean 本身，而是它把「证明的正确性」从作者声明移交给了独立内核——一个不认识作者、只做机械规则检查、不接受「相信我」的小程序。本仓库的 `xdev.py` 已经是这个内核的雏形，但它现在只检查文档结构，没有检查「命题与证明的对应」。

真正用 Lean 形式化业务代码不现实（语义编码成本远高于收益），可迁移的是三条原则：

1. **命题先于证明**——先钉死「必须守住什么」，再写实现；
2. **内核独立于作者**——检查者不能是作者本人，且检查是机械的、无自由裁量；
3. **结论不可自证**——任何「通过」声明必须能被第三方复算。

## What Changes

分三层，按依赖顺序落地，每层独立可用。

### L1 · 技术设计契约化（堵架构违规）

- **新增**：`x-tech-design` 除 `tech-design.md` 外，产出同目录机器可解析的 `tech-design.contract.yaml`。每个稳定设计编号 `DNN` 声明 `modules`（允许涉及的路径）、`public_interface`（公开入口符号）、`allowed_deps`、`forbidden_deps`；`schema_authority` 段声明协议权威源与消费者。散文版设计继续给人读，contract 给内核读。
- **BREAKING**：`xdev.py validate` 增加 `tech-design` 校验项。`x-req` 拆任务前校验 `dev-checklist.md` 的**影响文件树 ⊆ contract.modules**（contract 显式登记的差异项除外）。越界 = 设计外改动，退回 x-tech-design，不进开发。
- **新增**：`x-verify` Gate① 增加第 7 项「设计一致性」对账：
  1. 影响文件树 ⊆ contract.modules；
  2. 新增/变更的公开接口在 contract 中登记；
  3. 每个 `DNN` 至少被一个场景回指或验证方式覆盖（防「写了设计没人验」）；
  4. `forbidden_deps` 用静态 import 图机械检查。
- **下沉**：`x-audit-arch` 检查清单中**可机械判定**的三项——循环依赖、单一事实源重复定义、越界 import——抽为 `xdev.py archcheck` 进 Gate①。语义类判断（命名归属感、过度抽象、契约清晰度）继续留在手动巡检，边界维持 SKILL.md:142「单任务级别小范围结构审查不在范围」。

### L2 · 验证契约 VC（堵用例漏写）

- **新增**：`x-tech-design` 增加「验证契约」段。每个 `DNN` 声明 `invariants`（不变量）与 `boundary_cases`（边界/失败/并发/幂等/恢复），统一编号 `VC-NN`。**spec 场景是功能视角（用户看到什么），VC 是技术视角（实现必须守住什么）**，两者正交，缺一不可。
- **BREAKING**：`x-req` 的 `dev-checklist.md` 增加 `验证契约` 列，行 = 场景回指 + VC 回指。「重要 case 没写」在 req 阶段就暴露为「该行 VC 无对应测试」，而不是等 R3 抽查。
- **升级**：R3（`references/r3-test-integrity.md`）从「断言是否独立于实现」的主观判断，改为可机械化的**变异抽查**：x-dev 为每个 VC 在 dev-report 写明 `kill:`（破坏实现会让哪个测试失败）；Gate① 随机挑 1–2 个 VC 实际改坏实现重跑，测试不失败即判 P0。随机性使造假无法预知哪些会被查。

### L3 · 证据可复算（堵伪造结论）

- **BREAKING**：`dev-report` 的 verify 块从「结论-only」改为产出**证据包**：

  ```yaml
  evidence:
    - id: E1
      vc: VC-03
      cmd: "python3 -m pytest tests/test_foo.py::test_boundary -q"
      exit_code: 0
      stdout_sha256: "a3f2…"        # 哈希而非全文，避免 token 爆炸
      captured_at: "2026-10-09T15:20:00+08:00"
      raw_log: .evidence/E1.log     # 落盘保留可追溯性
  ```

- **BREAKING**：`x-verify` 从「不重跑测试」改为——**重跑全部 auto verify 块**（快），对完整测试套件做**随机抽样 20%**。比对 `exit_code` 与 `stdout_sha256`，不一致即 fail。这把「自证」变成「他证」。
- **机制设计要点**：引入重跑后，「写假报告」的成本从 0 变成「必须真跑一遍」，而真跑的成本远低于造假被抓的成本——靠成本不对称抑制造假，不靠道德劝诫。

## Capabilities

### New Capabilities

- `tech-design-contract`：机器可解析的技术设计契约（`tech-design.contract.yaml`）及其校验入口。
- `verification-contract`：设计条目派生的验证契约（VC）与证据包（evidence）格式。

### Modified Capabilities

- `xdev-verification-engine`：Gate① 新增设计一致性对账、证据重跑与随机抽样、变异抽查。
- `xdev-task-artifact-engine`：`validate` 新增 tech-design 校验项；checklist 表头新增 `验证契约` 列。
- `risk-routed-development-flow`：主流程从 `x-spec → x-req` 变为 `x-spec → x-tech-design → x-req`（tech-design 由可选升为前置）。

## Impact

- 代码：`skills/x-dev/scripts/xdev.py`（新增 `archcheck` 子命令与 tech-design 校验）、`skills/x-verify/scripts/verify.py`（设计一致性对账 + 证据重跑 + 抽样 + 变异）、`skills/x-spec/scripts/validator.py`（contract schema 校验）、`skills/x-req/scripts/req.py`（checklist 新列解析）。
- skills：`x-tech-design`（产出 contract + VC 段，删除「不添加自动门禁」的自我限制）、`x-req`（前置校验）、`x-dev`（evidence 包 + `kill:` 声明）、`x-verify`（新增对账项）、`x-qa-gate`（R3 升级）、`x-audit-arch`（机械化部分下沉，语义部分保留）。
- 文档：`README.md` 主流程图与命令表、`README_zh.md`、`CLAUDE.md` 核心管线与 skill 契约表。
- 兼容性：L1/L3 均为 **BREAKING**——已有 task 目录缺 `tech-design.contract.yaml` 或旧格式 dev-report 时，Gate① 以退出码 2 拒绝放行（与 `xdev-task-scoped-verify` 决策 6「解析不出就拦」一致），不静默放行。

## 后续阶段（本变更明确不做）

- 不引入 Lean / Coq / TLA+ 等重型形式化工具。
- 不对业务代码做全量变异测试，只做 Gate① 随机抽查。
- 不改变 `x-audit-arch` 的手动触发定位，只下沉其中可机械判定的三项。
