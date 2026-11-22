# 历史说明：x-cr 自动流转模式

本文件保留旧版 `x-dev -> x-cr -> x-fix` 自动循环的迁移背景。当前 x-cr 主流程已经转为手动软件正确性调查，独立于自动门禁。

当前职责边界以 [x-cr SKILL.md](../SKILL.md) 和 [x-verify-spec](../../x-verify-spec/SKILL.md) 为准：x-cr 是手动正确性调查；每个任务开发后由 x-verify-spec 验收一次（功能检查 + `xdev check`），问题交 x-fix。下文是旧设计，只作历史参考。

统一开发链路：

```text
x-req -> risk 定级 -> x-dev -> verify
                              ├─ Q0/Q1 -> 完成
                              ├─ Q2 -> RC
                              └─ Q3 -> R1 -> R2 -> R3
```

当前手动正确性调查链路：

```text
x-cr -> x-fix（用户要求修复时）
```

x-cr 的 task 报告路径为 `docs/spec/<spec>/tasks/<task>/reports/cr/cr-report-*.md`，普通仓库调查使用 `reports/cr/cr-report-*.md`；两者都是手动正确性调查和 x-fix 修复回写的共同载体。
