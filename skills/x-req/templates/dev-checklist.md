# <task-name> · 开发清单

<!--
填写后删除本注释和占位行。
- 本文件位于 docs/spec/<spec-name>/tasks/<task-name>/dev-checklist.md，一个 task 一份。
- spec 指向 v6 格式的 spec.md（标题 + 概述 + feat 列表，无元数据头）。
- 场景回指写 featNN 场景M，如 `feat02 场景3`；同行多场景逗号分隔；纯技术支撑行写 None。
- 风险列：鉴权/持久化或迁移/并发/不可逆写 `高:<一句依据>`，其余写 None。
- 不建依赖图：行序即实现顺序，先做被别人依赖的。
- 不复制 spec 的 GIVEN/WHEN/THEN，验收只看回指场景。
- 影响文件树与「涉及文件」列一一对应；标记 U 新增 / M 修改 / D 删除，# 后一句改动说明；同目录同标记同说明可合并一行（/ 分隔）；glob 写目录级节点。
-->

> spec: docs/spec/<spec-name>/spec.md
> 创建: YYYY-MM-DD

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[x] 🟢` 验证通过 / `[!] 🔴` 验证失败

| # | 任务 | 场景回指 | 涉及文件 | 风险 | 状态 |
|---|---|---|---|---|---|
| T1 | <可独立执行并验证的任务> | feat01 场景1, 场景2 | <path> | None | [ ] ⏳ |

## 影响文件树

```text
<repo-root>/
├── <path/to/file>   M  # <一句改动说明>
├── <path/to/file>   U  # 新增：<做什么>
├── <path/to/dir>/   U  # glob 待定位：<定位动作>
└── <path/to/file>   D  # 删除：<为什么删>
```
