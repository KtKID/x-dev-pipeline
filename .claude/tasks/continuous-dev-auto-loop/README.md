# continuous-dev-auto-loop

> 创建时间：2026-04-09
> 类型：功能
> 方案来源：[docs/continuous-development/00-simplified-plan.md](../../../docs/continuous-development/00-simplified-plan.md)

## 说明

为 x-dev-pipeline 增加"连续开发自动循环"能力：x-dev 完成任务后自动调用 x-cr 审查；x-cr 发现 P0/P1 自动调用 x-fix 修复；x-fix 修复后自动回到 x-cr 复审；通过后自动取下一个任务。仅修改 3 个现有 SKILL.md 的尾部，不新增 skill。

核心规则：
- 只自动修 P0+P1，P1.5/P2/P3 记录不修
- x-fix 累计 6 次仍未通过 → 停下上报
- x-cr 必须独立验证，不信任 x-dev 自我报告
- 规则是"连续开发模式"下生效，手动调用各 skill 的行为不变

## 开发清单

| 编号 | 优先级 | 状态 | 任务 | 备注 |
|------|--------|------|------|------|
| #1 | P0 | ✅ 已完成 | 修改 skills/x-dev/SKILL.md，追加"自动流转规则"章节 | 完成任务→自动 x-cr、停止条件、最终汇报格式；review 后移除 --auto 参数，改为上下文识别 |
| #2 | P0 | ✅ 已完成 | 修改 skills/x-cr/SKILL.md，追加"自动流转规则"章节 | 独立验证硬约束、P0+P1 自动 x-fix、复审循环、fix_attempts 计数、6 次上限；review 后明确"P0 追加子项"、简化方式 A/B 为单一方式、移除 --auto |
| #3 | P0 | ✅ 已完成 | 修改 skills/x-fix/SKILL.md，追加"自动流转规则"章节 | 只修 P0+P1、修完自动回 x-cr 复审、与 cr-fix-mode 的差异；review 后移除 --auto，明确"用户可自由指定修复范围" |
| #4 | P1 | ✅ 已完成 | 三方一致性检查 + Quick Review | 调用链闭合无漏洞；修正 1 处 P1（spec 合规追加而非替换）+ 2 处 P2（方式 A/B 冗余 / --auto 参数） |
| #5 | P0 | 🟡 待执行 | auto-loop-e2e-test | 新建 `.claude/tasks/auto-loop-e2e-test/` 准备 fixture（故意埋 P0 bug 的小 task），验证 x-dev → x-cr → x-fix → x-cr 闭环能否自动跑通；由用户触发跑一遍 |

## 涉及文件

- `skills/x-dev/SKILL.md` — 尾部追加自动流转规则章节
- `skills/x-cr/SKILL.md` — 尾部追加自动流转规则 + 独立验证硬约束
- `skills/x-fix/SKILL.md` — 尾部追加自动流转规则，限定只修 P0/P1
