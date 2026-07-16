---
name: x-verify
description: |
  Gate ① 事实验证 skill。运行 xdev verify 引擎；全过给回执，失败诊断事实并交 x-fix。
  触发：x-dev 收尾、用户要求 verify 或复跑 task 证据。
---

# x-verify · Gate ①

## 输入

`README.md` 的验收 Scenario 与 `dev-report*.md` fenced `verify` 块。引擎负责复跑命令、比较 exit/输出、列出 manual 和自动场景覆盖。

## 流程

1. 运行 `python3 tools/xdev.py verify <task-dir> --json`。
2. exit 0：输出 `pass N / manual M` 回执，不写报告。
3. exit 1：读取 fail 的 `output_tail` 与 uncovered，必要时用 `--only <id>` 复跑一个块；写 `reports/verify/verify-report-<timestamp>.md`，将完整 failure 清单交 x-fix。
4. exit 2：指出 dev-report verify 格式或路径问题，退回 x-dev；不递增 fix-counter。

## 约束

- 只报告命令与覆盖事实；代码质量由 x-qa-gate 处理。
- fail 时跑完全部 auto 块后一次交付完整清单。
- `reports/.fix-counter`、三轮上限和 x-fix 批量修复协议保持现有定义。

## 回执

```
🛡️ Gate① verify ✅ · pass N · manual M 待人工
🛡️ Gate① verify ❌ · fail N · uncovered M → x-fix
```
