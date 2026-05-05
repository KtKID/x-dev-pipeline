# qa-gate-pipeline · 变更记录

| 时间 | 操作 | 内容 |
|------|------|------|
| 2026-04-27 | 计划落地 | 完成 README.md（设计） + plan.md + dev-checklist.md |
| 2026-04-27 | T1 partial | 添加 dev-report.md 模板（commit 430cb7e） |
| 2026-04-28 | T1 完成 | x-dev/SKILL.md 与 x-qdev/SKILL.md 增加 "任务完成时必须输出 dev-report.md" 段；自动流转规则中"调 x-cr"全部改为"调 x-verify → x-qua-gate"；创建 _smoke/dev-report-sample.md |
| 2026-04-28 | T2 完成 | 创建 skills/x-verify/SKILL.md + templates/verify-report-template.md；按 SKILL.md 流程对 dev-report-sample 手工跑过两条命令并产出 _smoke/verify-report-manual.md（status: fail，验证拦截能力） |
| 2026-04-28 | T3 完成 | 创建 skills/x-qua-gate/SKILL.md + templates/qa-gate-report-template.md；framework only，references 由 T4-T6 接力 |
| 2026-04-28 | T4-T6 完成 | 创建 references/r1-spec-conformance.md、r2-boundary-coverage.md、r3-test-integrity.md（含反测试镜像化反模式 A/B/C 举例） |
| 2026-04-28 | T7 完成 | x-fix/SKILL.md 追加"失败回流规则（qa-gate-pipeline 改造）"段，含 4 条回流规则 + fix-counter 6 次共享 + 报告路径分类；新建 references/qa-gate-fix-mode.md（verify/r1/r2/r3 四个子模式） |
| 2026-04-28 | T8 完成 | 创建 skills/x-audit-perf/SKILL.md + templates/audit-perf-template.md（独立巡检，5 类检查清单） |
| 2026-04-28 | T9 完成 | 创建 skills/x-audit-style/SKILL.md + templates/audit-style-template.md（独立巡检，6 类检查清单） |
| 2026-04-28 | T10 完成 | x-cr/SKILL.md 改为重定向 stub；README.md 与 README_zh.md 链路图与命令简介更新；.codex-plugin/plugin.json defaultPrompt 更新；创建 _e2e-smoke 5 个 case 脚手架；dev-checklist 全部任务标 🟢 |
| 2026-04-28 | 验收待办 | T1-T10 代码改动落地，整体 task 进入 🟢 测试通过；待用户在新会话依次跑 5 个 e2e smoke case 后才升 ✅ |

## 关键决策

- **未自动 commit**：本次执行不自动 git commit，待用户审核后由用户决定切分提交（plan 中每 task 各自一个 commit step 在用户审核时再分批落地）。
- **fix-counter 重置归属**：x-verify 负责首次创建 `.fix-counter`，x-fix 负责递增，x-qua-gate 在 R3 通过后负责重置——三方协议一致写入了三个 SKILL.md。
- **manifest 不列 skill 清单**：现有 `.claude-plugin/plugin.json` / `marketplace.json` / `.codex-plugin/plugin.json` 均不显式列出 skill 名（auto-discover via `./skills/`），故新增 4 个 skill 不需要改 manifest 字段；只更新了 `.codex-plugin/plugin.json` 的 `defaultPrompt` 示例引导。
- **e2e 验收延后**：5 个 e2e smoke case 仅写需求 README，由用户在新会话人工触发完整 dev → verify → qua-gate 链路。

## 已知盲点

- dev-report 完全漏报某条命令（dev 没跑某个验证），verify 没法察觉——这是"自报清单"机制的固有限制（设计文档第 9 节已显式列出，未来可加白名单 cross-check）。

## 待用户 e2e 验收

整个 task 状态先停在 🟢 测试通过；待用户在新会话依次完成 `_e2e-smoke/01-positive` ... `_e2e-smoke/05-r3-fail` 五个用例验收后，才升级整 task 为 ✅ 已完成。
