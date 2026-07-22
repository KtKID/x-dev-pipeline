---
name: x-verify
description: |
  Gate ① 事实验证 skill。运行 xdev verify 引擎；全过给回执，失败诊断事实并交 x-fix。
  触发：x-dev 收尾、用户要求 verify 或复跑 task 证据。
---

# x-verify · Gate ①

## 输入

task 的 `dev-checklist.md`、归属 `spec.md` 和 `dev-report*.md` fenced `verify` 块。req2 按 Requirement 限定验收 Scenario；req3 直接按 Scenario 限定范围。引擎复跑命令、比较 exit/输出并检查当前 task 的证据覆盖。

## 流程

1. 运行 `python3 tools/xdev.py verify <task-dir> --json`。
2. exit 0：输出 `pass N / manual M` 回执，不写报告。
3. exit 1：读取 fail 的 `output_tail` 与 uncovered，必要时用 `--only <id>` 复跑一个块；写 `reports/verify/verify-report-<timestamp>.md`，将完整 failure 清单交 x-fix。
4. exit 2：按错误来源分诊，不递增 fix-counter。
   - dev-report 的 verify 块格式、id 冲突、`cwd` 路径问题 → 退回 x-dev。
   - `dev-checklist.md` 缺失或表头不可解析 → 退回对应 x-req2/x-req3。
   - req2 Scenario 缺父 Requirement 或验证标记 → 退回 x-spec2。
   - req3 Scenario 缺测试层、名称重名或 checklist 回指悬空 → 退回 x-spec3/x-req3。
   这两类是 task / spec 产物的问题，退给 x-dev 无从下手。

## 约束

- 只报告命令与覆盖事实；代码质量由 x-qa-gate 处理。
- fail 时跑完全部 auto 块后一次交付完整清单。
- req3 的 unit/smoke Scenario 必须由 auto 块覆盖；e2e Scenario 必须由 auto 或 manual 块声明。
- `reports/.fix-counter`、三轮上限和 x-fix 批量修复协议保持现有定义。

## 回执

```
🛡️ Gate① verify ✅ · pass N · manual M 待人工
🛡️ Gate① verify ❌ · fail N · uncovered M → x-fix
```
