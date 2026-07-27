# Pipeline Eval 评分与归因指南

## 严重度

| 等级 | 判定 | 默认门禁 |
|---|---|---|
| P0 | 违反题面硬契约、关键不变量、安全/并发/持久化语义，或会让下游按文档实现错误行为 | 立即阻止下一高成本阶段 |
| P1 | 高价值边界、失败路径、所有权或确定性证据缺失；常见路径仍可能完成 | 要求修订或显式风险接受 |
| P2 | 局部证据、可维护性或低损失覆盖不足 | 可带记录进入下一阶段 |

## 语义检查顺序

1. 目标与非目标是否匹配题面。
2. GIVEN 是否属于题面允许输入。
3. WHEN 是否唯一且可执行。
4. THEN 是否与题面、同文档判断和其他 Scenario 同时一致。
5. 验收命令是否能在声明目录运行。
6. 上下游是否读取同一契约。
7. 隐蔽边界是否被具体反例覆盖。

## Scenario 联合可满足性

把每个 Scenario 看作一组约束。先列出 GIVEN 触发的全部规则，再检查 THEN：

```text
schema 仅含 debug
source 同时包含 extra
任务规则：schema 外字段返回 ErrUnknownField
THEN：成功返回并保留 extra
```

这组约束无共同解。该 Scenario 不能为可选字段删除提供通过证据，并形成 `SPEC_CONTRACT_CONTRADICTION`。将无关 `extra` 移到独立 unknown-field Scenario 后，删除路径才能单独验收。

## 覆盖质量

类别声明只证明模型知道概念。高价值 assertion 需要具体输入和可观察结果：

- 递归：至少超过常见两层的嵌套实例。
- 确定性：逻辑相同、构造顺序不同的输入对照。
- 所有权：修改返回结果后复查全部输入 map/slice。
- 并发：共享输入、明确 goroutine 数、race 命令和结果。
- 删除：Config 与全部后代 Provenance 同时消失。
- 空值：nil 与 empty 的结果矩阵。

## 最早责任阶段

| 现象 | 最早责任阶段 | 发现阶段示例 |
|---|---|---|
| spec 写出矛盾 Scenario，req 原样下传 | spec | req review / dev failure |
| spec 正确，req 遗漏 Scenario | req | verify / QA |
| spec 与 req 正确，代码违反契约 | dev | test / verify |
| 错误实现通过 verify | verify | QA / hidden test |
| QA 放行已知 P0 | QA | canary / 用户反馈 |

`origin_stage` 保存最早责任阶段，`detected_stage` 保存发现位置。交接忠实度可以通过，同时上游语义质量失败。

## 比较结论

形成因果性 skill 结论前确认任务、rubric、模型、权限、预算、工具、仓库 SHA 和执行阶段范围一致。存在差异时报告观察值和混杂因素。正确性硬门槛通过后，再比较：

- `tokens_to_accepted`
- `false_accept_rate`
- `repair_rounds`
- prompt-to-final 时间
- cache read、输出 Token 和工具调用
