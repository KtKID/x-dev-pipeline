# filter-completed · 开发清单

> spec: docs/spec/checklist/spec.md
> 状态：待实现
> 执行者：未知
> tech-design: docs/spec/checklist/tech-design.md
> 本轮范围：feat01 场景1-2
> 范围依据：用户已确认的 spec 与技术设计
> 拆解基线：<由 xdev baseline 写入>
> 代码基线：（开工时由 xdev start 写入，不手填）
> risk: Q1
> 分组理由：1 组：改动小，文件相互依赖
> 创建: 2026-11-21

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待验证 / `[x] 🟢` 验证通过 / `[!] 🔴` 验证失败 / `[x] ✅` 已完成 / `[ ] ↗️` 已升级

| # | 任务 | 场景回指 | 涉及文件 | 风险 | 并行组 | 依赖 | 状态 |
|---|---|---|---|---|---|---|---|
| T1 | 加入并验证「只看已完成」按钮（D01；用例 T1、T2；集成） | feat01 场景1, 场景2 | index.html, app.js, test/checklist-filter.cjs | None | A | None | [ ] ⏳ |

## 影响文件树

```text
task/
├── index.html                M  # 清单上方加筛选按钮
├── app.js                    M  # 切换待完成事项可见性和按钮文字
└── test/checklist-filter.cjs U  # 新增：T1、T2 浏览器集成测试
```

## 结果

> 覆盖率：（由 xdev coverage 写入，不手填）

### 用例对应

| 用例 | 测试位置 | 层级 | 结果 |
|---|---|---|---|

### 问题与处置

- 无
