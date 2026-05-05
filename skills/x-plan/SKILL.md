---
name: x-plan
description: |
  ⚠️ 已废弃：本 skill 已合并到 x-req。x-req 现在一步产出 README.md + dev-checklist.md + diagram.html。
  保留触发关键词兼容：x:plan、计划、制定计划、开发计划、plan。
  调用时自动重定向到 x-req。
---

# x-plan ⚠️ 已废弃 → 重定向到 x-req

本 skill 自 v0.2（2026-05-04）起已合并到 **x-req**。

## 调用本 skill 时怎么办

改用 x-req。它现在一步产出 README.md + dev-checklist.md + diagram.html，不再需要先 req 后 plan。

新链路：

```
x-req → README.md + dev-checklist.md + diagram.html → x-dev
```

## 旧 plan.md 文件

已有 task 里的 plan.md **保留**，x-dev 仍可读（向后兼容）。新 task 不再产出 plan.md。

## 原 x-plan 独特能力去哪了

| 原 x-plan 功能 | 现在在哪 |
|---------------|---------|
| dev-checklist.md 生成 | x-req 直接产出 |
| 技术选型对比表 | x-req README.md "## 技术设计 → 技术选型" 段 |
| 风险点及应对 | x-req README.md "## 风险" 段 |
| 模块落地方式 | x-req README.md "## 技术设计 → 关键链路" 段 |
| 分阶段实施顺序 | dev-checklist.md 的优先级排序（P0→P1→P2） |
| 质检标记 🔍 | x-req 继承，规则不变 |
