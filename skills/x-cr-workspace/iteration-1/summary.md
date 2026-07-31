# x-cr iteration-1 inline dry-run

> Execution mode: inline-contract-dry-run
> Baseline: `/private/tmp/x-cr-snapshot.LVbgQq/x-cr`

| Eval | 通过 | 总数 | 结果 |
|------|------|------|------|
| Harness 审批范围 | 5 | 5 | spec 不变量优先，发现可达 P0 |
| 服务端信任边界 | 5 | 5 | 发现 spec 缺口与越权 P0 |
| 幂等路径未触达 | 5 | 5 | 保持低误报，继续检查遗漏候选 |
| 纯架构问题分流 | 3 | 3 | 路由 x-audit-arch |

合计 18/18 条契约断言通过。该结果由当前主 agent 串行执行，验证指令结构与报告 schema；独立模型方差尚未测量。

补充结构验证：

- 三份 x-cr-v2 dry-run 报告通过 `scripts/validate_report.py`。
- 校验器的 5 个单元测试覆盖合法报告、详情缺失、Bn 重复、不变量未映射及非法状态/严重度/置信度。
