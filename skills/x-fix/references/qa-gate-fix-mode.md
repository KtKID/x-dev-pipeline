# x-fix · qa-gate-fix-mode

> 当 x-fix 由 x-verify 或 x-qa-gate reviewer（RC/R1/R2/R3）触发时，进入本模式。

## 输入识别

- 入参里包含 `verify-report-*.md` 路径 → mode: verify-fix
- 入参里包含 RC/R1/R2/R3 review 问题映射，且每条带 `issue-<n>` → mode: gate-fix

## 通用流程

1. 读 fix-counter，counter >= 3 → 生成 fix-blocked-report.md，停。
2. counter +1，写回 .fix-counter（按轮计：本次批量修整体算 1 轮）。
3. 读 fail 报告的**完整 issue 清单**：P0 全修、P1 逐条修复或写豁免理由、P2 登记不修。
4. 一次修完本轮全部应修项；**每修一个 P0 留一条可复跑反例**（测试断言或 verify 脚本步骤）。
5. 自跑受影响验证（相关测试 + dev-report 受影响命令），全绿才继续。
6. 写 fix 报告（逐条处置表）到对应路径（见 SKILL.md 路径表）。
7. 控制权交回主 agent：verify-fix 回 x-verify 复跑；gate-fix 回 x-qa-gate 增量复审（尽量同一个 reviewer 承接）。
8. dev-checklist 状态单元格与 issue ledger 在修复过程中保持原样；主 agent 在增量复审通过后执行升钩。

## mode 特殊规则

### verify-fix

- 只修让命令 fail 的代码（编译错误 / 测试 fail / lint error / smoke-e2e fail）。
- 修完触发回流：回 x-verify 复跑本轮 fail 过的命令；最终通关前 x-verify 须完整跑一遍全清单。
- **注意**：不要去改 dev-report.md 里的命令清单或预期 exit！那会绕过验证。

### gate-fix

按 issue 清单的维度分别处理：

- **spec/契约类**（RC-Q1/Q2、R1 发现）：修实现偏差 / 删过度实现。涉及公开 API 签名变化时在处置表显式标注，提示复审对该 API 做定点契约对照。
- **边界/失败路径类**（RC-Q3、R2 发现）：补边界处理和失败路径覆盖，反例固化进测试或 verify 脚本。
- **测试真实性类**（RC-Q4、R3 发现）：默认**只改测试代码**。如果发现"测试改不对是因为业务代码本身有问题"，一并修复业务缺陷，并在处置表如实标注为上游漏检（供回执漏检统计）。

修完触发回流：回 x-qa-gate 对带 issue ID 的处置结果做增量复审，保持已 pass 的前置段结果。
