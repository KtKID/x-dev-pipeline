# x-fix · qa-gate-fix-mode

> 当 x-fix 由 `xdev check`（x-verify-spec）不通过回执或 x-qa-gate reviewer 的问题清单触发时，进入本模式。

## 输入识别

- 入参是 `xdev check` 列出的问题中需要改代码或测试的那些，主 agent 按顺序编号 V1、V2…；或旧契约包的 `verify-report-*.md` 路径 → mode: verify-fix

`xdev check` 规则的去向（主 agent 分流）：

| 规则 | 去向 |
|---|---|
| TESTS、COVERAGE、HIGH_RISK、MAPPING_PATH（测试不存在）、CASE_UNMAPPED、SCENE_UNCOVERED、MAPPING_RESULT（用例失败） | 交 x-fix，占一轮 |
| COVERAGE_STALE | 主 agent 直接重跑 `xdev coverage`，不占轮数 |
| INTEGRITY、INTEGRITY_STALE | 主 agent 按测试真实性检查重新派轻量子 agent；查出的问题由开发负责方修测试，不占 x-fix 轮数 |
| COVERAGE_EXCLUDE、MAPPING_MANUAL、MAPPING（表为空）、ROW_STATUS、CODE_BASELINE | 开发负责方补记录或状态（x-dev / x-qdev），不占轮数 |
| 结构与编号类（HEADER、SCENE_REF、CASE_REF、D_REF、GROUP_*、DEP_*、RISK 等）、SPEC_CHANGED、SPEC_CONFIRM | 交来源负责方（x-req / x-tech-design / x-explore-for-spec），不调 x-fix |
- 入参是 x-qa-gate 问题映射，且每条带 `issue-<n>` → mode: gate-fix

## 通用流程

1. 读 fix-counter，counter >= 3 → 生成 fix-blocked-report.md，停。
2. 本轮至少有一条要修的问题时，counter +1，写回 .fix-counter（按轮计：本次批量修整体算 1 轮）；一条都没有就不递增，直接退回主 agent。
3. 读 fail 报告的**完整 issue 清单**：P0 全修、P1 逐条修复或写豁免理由、P2 登记不修。
4. 一次修完本轮全部应修项；**每修一个 P0 留一条可复跑反例**（测试断言或 verify 脚本步骤）。
5. 修复触及配置、CLI、公开 API、协议/schema 或落盘布局时，列出修复前已接受的最小输入样本；新增配置字段使用兼容默认值，或按 spec 提供显式迁移验收。
6. 自跑每条的聚焦反例，再跑 `xdev coverage`（修复前原始样本原样参与的全量测试与既有回归，改动行覆盖率仍 100%）；旧契约包为完整入口 verify。不跑 `xdev check`：被 flag 降为 🔴 的行由主 agent 改回 🟢 后，再由主 agent 运行。扩展后的 fixture 只作附加覆盖。
7. 新增的反例测试登记进用例对应表；处置逐条写进 checklist「问题与处置」（qdev 为⑤的同名节），不另建 fix 报告文件。
8. 控制权交回主 agent：verify-fix 由主 agent 重跑 `xdev check` 关闭（旧契约包为复跑 `xdev verify`）；gate-fix 由主 agent 按 x-qa-gate「回流」的顺序关闭（先把行改回 🟢 再跑 `xdev check`），不发回原 reviewer。
9. dev-checklist 状态单元格与 issue ledger 在修复过程中保持原样；主 agent 关闭问题后执行升钩。

## mode 特殊规则

### verify-fix

- 只修让检查不过的代码：测试失败、编译错误、没覆盖的行（补测试）、缺真实链路用例（补 smoke / 集成测试）。
- V 项不能豁免：覆盖率和测试必须真的达标。万一收到悬空引用、范围遗漏、SPEC_CHANGED 这些文档或分配问题，不改，在回执里退回主 agent，由主 agent 交 x-req / x-tech-design。本轮如果一条可修的问题都没有，不递增 fix-counter，直接退回。
- 旧契约包复跑本轮 fail 过的 verify 块，最终通关前完整跑一遍全清单。
- **注意**：不要为了通过去改用例对应表的结果、删用例、降低断言或加没有理由的覆盖率排除标记！那会绕过验证。

### gate-fix

按 issue 清单的维度分别处理：

- **spec/契约类**（q1-intent 发现）：修实现偏差 / 删过度实现。涉及公开 API 签名变化时在处置里显式标注，主 agent 据此决定是否派裁剪 reviewer。
- **边界/失败路径类**（q2-correctness 发现）：补边界处理和失败路径覆盖，反例固化进测试。
- **设计与架构类**（q4-design 发现）：按 D 机制、R1–R7 或架构偏好改实现；要改偏好或设计本身的，退回主 agent 问用户。
- **测试真实性类**（q3-evidence 发现）：默认**只改测试代码**。如果发现"测试改不对是因为业务代码本身有问题"，一并修复业务缺陷，并在处置里如实标注为上游漏检。

修完交回主 agent：主 agent 依据聚焦反例与全量测试证据关闭对应 issue；公开 API 签名变化或修复扩大到新文件时，由主 agent 另派一个裁剪 reviewer，只查新增边界。
