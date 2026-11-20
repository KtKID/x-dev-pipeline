# x-fix · qa-gate-fix-mode

> 当 x-fix 由 x-verify-spec 不通过回执或 x-qa-gate tri-lens reviewer 的问题清单触发时，进入本模式。

## 输入识别

- 入参是 x-verify-spec 回执里的问题清单（当前格式 task；主 agent 给每条编号 V1、V2…），或旧契约包的 `verify-report-*.md` 路径 → mode: verify-fix
- 入参是 x-qa-gate tri-lens 问题映射，且每条带 `issue-<n>` → mode: gate-fix

## 通用流程

1. 读 fix-counter，counter >= 3 → 生成 fix-blocked-report.md，停。
2. counter +1，写回 .fix-counter（按轮计：本次批量修整体算 1 轮）。
3. 读 fail 报告的**完整 issue 清单**：P0 全修、P1 逐条修复或写豁免理由、P2 登记不修。
4. 一次修完本轮全部应修项；**每修一个 P0 留一条可复跑反例**（测试断言或 verify 脚本步骤）。
5. 修复触及配置、CLI、公开 API、协议/schema 或落盘布局时，列出修复前已接受的最小输入样本；新增配置字段使用兼容默认值，或按 spec 提供显式迁移验收。
6. 自跑一个聚焦反例，并用修复前原始样本复跑完整入口 smoke/verify。原始样本保持原样，扩展后的 fixture 作为附加覆盖。
7. 将本轮用例明细、改动覆盖率、未覆盖位置及原始执行记录收录到统一测试报告与附件；fix 报告按对应路径保留逐条处置表，以用例/执行编号链接验证结果。
8. 控制权交回主 agent：verify-fix 由主 agent 重新发起 x-verify-spec 对账（旧契约包为复跑 `xdev verify`）；gate-fix 由主 agent 按 x-qa-gate「回流」用聚焦反例和项目全量测试关闭，不发回原 reviewer。
9. dev-checklist 状态单元格与 issue ledger 在修复过程中保持原样；主 agent 关闭问题后执行升钩。

## mode 特殊规则

### verify-fix

- 只修让命令 fail 的代码（编译错误 / 测试 fail / lint error / smoke-e2e fail）。
- 当前格式 task 的 V 项统一按 P1 处理（修复或写豁免理由），处置表严重度写 `P1(V)`。x-fix 只处理其中"已如实记录的执行失败"这一类；悬空引用、覆盖遗漏、证据缺失、记录矛盾这些文档或分配问题不改，在回执里退回主 agent，由主 agent 交 x-req / x-tech-design / 开发负责方。
- 修完交回主 agent 重新发起对账；旧契约包复跑本轮 fail 过的 verify 块，最终通关前完整跑一遍全清单。
- **注意**：不要去改 dev-report.md、测试报告里的命令清单或预期结果！那会绕过验证。

### gate-fix

按 issue 清单的维度分别处理：

- **spec/契约类**（q1-intent 发现）：修实现偏差 / 删过度实现。涉及公开 API 签名变化时在处置表显式标注，主 agent 据此决定是否派裁剪 reviewer。
- **边界/失败路径类**（q2-correctness 发现）：补边界处理和失败路径覆盖，反例固化进测试或 verify 脚本。
- **测试真实性类**（q3-evidence 发现）：默认**只改测试代码**。如果发现"测试改不对是因为业务代码本身有问题"，一并修复业务缺陷，并在处置表如实标注为上游漏检。

修完交回主 agent：主 agent 依据聚焦反例与全量测试证据关闭对应 issue；公开 API 签名变化或修复扩大到新文件时，由主 agent 另派一个裁剪 reviewer，只查新增边界。
