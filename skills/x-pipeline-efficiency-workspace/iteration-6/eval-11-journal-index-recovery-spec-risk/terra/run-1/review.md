# Iteration 6 Terra Spec 风险评测复盘

## 结论

本次运行完成了干净上下文、Terra/xhigh、单 turn、仅 Spec 与按需 deep 对抗审查的执行。四轮效率契约达到目标：对抗阶段 3 次工具调用、4 轮推理、199,733 tokens；相比 iteration-5 的 960,376 tokens 下降 79.20%。隐藏评分为 41/100（7/17），低于 90 分晋级线；当前结果为 blocked。

## 隐藏评分

隐藏评分器与 iteration-5 使用同一份 `evaluate_spec_risk.py`。当前结果：

- 风险评分错误：Terra 写成 complexity 4、importance 3；隐藏契约要求 complexity 5、importance 1，因此预算应为 full。
- 五个隐藏问题中，SC_14 语义覆盖 AR-001，SC_13 语义覆盖 AR-004。
- AR-002 语义快照一致性、AR-003 结构完整但逻辑非法的日志记录、AR-005 完整错误响应契约缺少可判定 Scenario。
- v2 的 `pattern:` 来源使旧评分器得到 0 个 AR-nnn 可追踪命中。
- YAML metadata 和已删除的 corpus validator 共同导致机械门禁项失败。

## 正确性结果

Terra 生成 12 个 initial-spec Scenario，并在 deep 审查中新增 SC_13、SC_14，覆盖失败 mutation 残留和 compact 分阶段提交窗口。它同时修正 SC_04 的 tombstone expected_version，并扩展 SC_08 的损坏命令覆盖。

失败根因是 metadata 方言漂移。模板要求：

```text
> adversarial_risk_version: 2
> complexity: 4
```

Terra 输出了 YAML frontmatter。`risk_contract.py` 聚合返回 12 项错误，全部来自六个风险字段无法按 blockquote 语法解析。

## 效率结果

| 指标 | iteration-5 | iteration-6 | 变化 |
|---|---:|---:|---:|
| Spec turn tokens | 1,411,304 | 270,385 | -80.84% |
| 对抗阶段 tokens | 960,376 | 199,733 | -79.20% |
| Spec turn 工具调用 | 25 | 5 | -80.00% |
| 对抗工具调用 | 13 | 3 | -76.92% |
| 对抗推理轮次 | 14 | 4 | -71.43% |
| Spec turn 时长 | 621.37s | 280.07s | -54.93% |

新流程消除了 deep/full 循环读取。对抗阶段只读取一次 skill、当前 Spec 和 21 行通用示例，随后执行一次 patch、一次验证和一次回执。

## 上下文隔离

线程继承历史 turn 数为 0，模型与思考等级由 `turn_context` 证明为 Terra/xhigh。全部工具路径位于隔离 workspace，外部资料命中数为 0。

首轮命令使用 `task/*`，读取了四个顶层任务文件，并遗漏嵌套的 `task/specs/storage-layout.md`。最终回执声称读取五份文档，这一声明与 tool trace 不一致。

## 建议

1. x-spec3 把头部格式设为强契约：复制模板前七行，只替换值，保留 `>` 前缀。
2. 隔离 prompt 显式列出五个任务文件路径，避免 glob 丢失嵌套文档。
3. 完成上述两处修复后运行全新的 run-2；继续保持单 turn 和对抗阶段 3 次工具调用上限。
