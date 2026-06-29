# 历史说明：x-cr 自动流转模式

本文件保留旧版 `x-dev -> x-cr -> x-fix` 自动循环的迁移背景。当前 x-cr 主流程已经转为手动软件正确性调查，独立于自动门禁。

当前职责边界：

| 场景 | 使用 skill |
|------|------------|
| 用户说某功能不太对，需要查根因 | x-cr |
| 用户要求 review 模块、文件、diff、PR 的正确性 | x-cr |
| x-dev / x-qdev 完成后复跑验证命令 | x-verify |
| x-verify 通过后的流水线质量门禁 | x-qa-gate |
| verify / qa-gate / CR 报告里的问题修复 | x-fix |

当前自动链路：

```text
x-dev / x-qdev -> x-verify -> x-qa-gate -> x-fix
```

当前手动正确性调查链路：

```text
x-cr -> x-fix（用户要求修复时）
```

x-cr 的报告路径仍为 `reports/cr/cr-report-*.md`，用于保留手动正确性调查和 x-fix 修复回写的共同载体。
