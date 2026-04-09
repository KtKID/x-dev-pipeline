# x-cr-optimization

> 创建时间：2026-04-09
> 类型：重构

## 说明

按 skill-creator 规范优化 `skills/x-cr/SKILL.md`：下沉详细内容到 references/ 以实现 progressive disclosure，主体瘦身到 ~150 行作为路由层；修复语言列表与实际文件不一致、路径矛盾等 bug；重写 description 解决 undertrigger；软化硬性 MUST 表述为 why-based 解释。最后跑一次 skill-creator 的 trigger eval 验证。

用户确认的决策：
1. 语言列表：只保留 TS/JS/C# 3 个已存在文件，未来按需扩充
2. 报告保存路径：软表述"跟随调用者 task 目录"
3. 自动流转规则：下沉到 references/，主体留简短摘要 + 指针
4. 一次性实施（不分阶段）
5. 最后跑 skill-creator trigger eval

## 开发清单

| 编号 | 优先级 | 状态 | 任务 | 备注 |
|------|--------|------|------|------|
| #1 | P0 | ✅ 已完成 | 创建 `skills/x-cr/references/checklist-general.md` | P0-P3 详细清单 + P0 spec 合规子项 |
| #2 | P0 | ✅ 已完成 | 创建 `skills/x-cr/references/report-template.md` | 模板骨架 + 真实登录 bug 填充示例 + 状态符号表 |
| #3 | P0 | ✅ 已完成 | 创建 `skills/x-cr/references/auto-loop-mode.md` | 触发判定 + 独立验证 + 修复循环 + fix_attempts + 约束速查表 |
| #4 | P0 | ✅ 已完成 | 重写 `skills/x-cr/SKILL.md` 主体 | 132 行（目标 ~150），路由层 + 工作方式 + 流程 + 全局原则 + references 指针 |
| #5 | P1 | ✅ 已完成 | 修复语言列表 | 只保留 TS/JS/C# 3 项；其他语言明确说明"未加载专项规则" |
| #6 | P1 | ✅ 已完成 | 修复路径矛盾 | 统一为"跟随调用者 task 目录"软表述 |
| #7 | P1 | ✅ 已完成 | 重写 description | 加入触发关键词 + "不要因为说'只是看一下'就跳过"的 pushy 表述 |
| #8 | P2 | ✅ 已完成 | 软化硬 MUST 为 why-based | 硬 MUST 从 ~20 次降到 1 次；每个流程步骤加 "原因是..." |
| #9 | P2 | ✅ 已完成 | 跑 skill-creator trigger eval | 已执行但结果不可采纳：x-cr 是 plugin skill，run_loop 的 claude CLI 环境无法加载 plugin skill，所有 20 个 query 触发率均为 0（工具局限，非 description 问题）；详情见 changelog |

## 涉及文件

- `skills/x-cr/SKILL.md` — 重写主体，瘦身到 ~150 行
- `skills/x-cr/references/checklist-general.md` — 新建
- `skills/x-cr/references/report-template.md` — 新建
- `skills/x-cr/references/auto-loop-mode.md` — 新建
