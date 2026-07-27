# <task-name> · 开发清单

<!--
填写后删除本注释和占位行。
- spec 指向含 `> spec_version: 3` 的单文件规格包。
- risk 按本 task 触及的最高 spec 风险信号填写 Q0/Q1/Q2/Q3。
- Scenario IDs 只填 spec.md 中存在的 ID；单个写 `SC_01`，多个写 `SC_01, SC_02`，纯技术行写 None。
- 风险列写紧凑证据：模块不变量、J-ID 或 Scenario；无功能风险写 None。
- 每行只保留任务执行信息，不复制 GIVEN/WHEN/THEN 或验收清单。
-->

> spec: docs/spec/<spec-name>
> risk: <Q0|Q1|Q2|Q3>

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | <可独立执行并验证的任务> | <SC_01 或 SC_01, SC_02 或 None> | <不变量/J-ID/Scenario 或 None> | <path> | None | [ ] ⏳ | None |
