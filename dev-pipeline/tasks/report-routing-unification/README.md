# report-routing-unification

> 创建时间：2026-04-21
> 类型：优化

## 说明

统一 x-cr 和 x-fix 的报告路径、回写方式和轻量修补记录，避免 CR 报告与修复结果分散在不同位置。目标是让同一份 CR 主档承载审查结论和修复回写，让 fix-report 和 fix-note 只承担修复过程留痕。

## 开发清单

| 编号 | 优先级 | 状态 | 任务 | 备注 |
|------|--------|------|------|------|
| #1 | P0 | ✅ 已完成 | 统一 x-cr 的报告落点与回写约定 | |
| #2 | P0 | ✅ 已完成 | 统一 x-fix 的 fix-report / fix-note 产出规则 | |
| #3 | P1 | ✅ 已完成 | 更新 README 与任务记录说明 | |

## 涉及文件

- `skills/x-cr/SKILL.md` — 统一 CR 主档路径和回写规则
- `skills/x-cr/references/report-template.md` — 统一 CR 报告模板头部与修复备注区
- `skills/x-fix/SKILL.md` — 统一 fix-report / fix-note 规则
- `skills/x-fix/references/cr-fix-mode.md` — 统一 CR 报告定位与回写规则
- `skills/x-fix/references/bug-fix-mode.md` — 统一轻量修补记录规则
- `skills/x-fix/templates/fix-report-template.md` — 统一修复报告模板
- `skills/x-fix/templates/fix-note-template.md` — 新增轻量修补模板
- `README.md` — 更新英文说明
- `README_zh.md` — 更新中文说明
