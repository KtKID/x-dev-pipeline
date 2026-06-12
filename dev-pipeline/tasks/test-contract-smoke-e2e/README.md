# test-contract-smoke-e2e

> 创建时间：2026-06-12
> 类型：优化

## 说明

把测试分层契约写进 x-dev-pipeline：x-spec 定验证策略，x-req 显式写 smoke/e2e 验收用例，x-dev 继续负责单元/契约/边界测试并写入 dev-report。

## 涉及模块

- `CLAUDE.md` — skill 间总契约
- `skills/x-spec/templates/05-validation-and-evolution.md` — spec 验证策略模板
- `skills/x-req/SKILL.md` — x-req 生成和审核规则
- `skills/x-req/templates/README.md` — task README 模板
- `skills/x-dev/SKILL.md` — x-dev 执行和 dev-report 规则
- `skills/x-dev/templates/dev-report-template.md` — dev-report 命令清单模板
- `skills/x-qa-gate/references/r3-test-integrity.md` — R3 测试真实性审查规则

## DoD（怎么算完成）

- [x] x-req 明确只把 smoke/e2e 作为 README 显式验收用例。
- [x] x-dev 明确负责补齐单元/契约/边界测试，并进入 dev-report 验证命令。
- [x] R3 明确检查 README smoke/e2e 是否进入 dev-report。

## 开发清单

| 编号 | 优先级 | 质检 | 状态 | 任务 | 备注 |
|------|--------|------|------|------|------|
| #1 | P0 | 🔍 | 🟢 测试通过 | 更新测试分层契约 | 已完成 |

## 涉及文件

- `CLAUDE.md`
- `skills/x-spec/templates/05-validation-and-evolution.md`
- `skills/x-req/SKILL.md`
- `skills/x-req/templates/README.md`
- `skills/x-dev/SKILL.md`
- `skills/x-dev/templates/dev-report-template.md`
- `skills/x-qa-gate/references/r3-test-integrity.md`
