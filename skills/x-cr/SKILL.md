---
name: x-cr
description: |
  ⚠️ 已废弃：本 skill 已被 x-qua-gate 取代。请改用 x-qua-gate。
  保留触发关键词以兼容老调用：review、code review、代码审查、检查一下、看看有没有问题、帮我 review、PR 前检查、合并前检查、提交前检查、代码审计。
  当前调用会被自动重定向到 x-qua-gate。
---

# x-cr ⚠️ 已废弃 → 重定向到 x-qua-gate

本 skill 自 qa-gate-pipeline 改造（2026-04-27）起已被 **x-qua-gate** 取代。

## 调用本 skill 时怎么办

立刻**改用 x-qua-gate**——它做了 x-cr 原本的所有事，并把检查拆成 3 个独立 reviewer（spec / 边界 / 测试真实性），用 opus 子 agent 串行评审。

新链路：

```
x-dev / x-qdev → x-verify (Gate ① 命令复跑) → x-qua-gate (Gate ② R1 → R2 → R3)
                                                   ↓ fail
                                                x-fix → 回流目标节点
```

## 旧 cr-report 路径

历史 cr-report 仍在 `reports/cr/cr-report-*.md`，**不会删除**，但新报告写到 `reports/qa-gate/qa-gate-report-*.md`。

## references/ 旧文件

`references/auto-loop-mode.md` 等旧文件保留作历史参考，不再生效。新逻辑见 `skills/x-qua-gate/SKILL.md` 与 `skills/x-fix/references/qa-gate-fix-mode.md`。
