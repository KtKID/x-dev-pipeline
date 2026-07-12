# qa-gate-round-review

> 创建时间：2026-07-12
> 类型：优化
> 风险等级：Q2（修改公开 skill 路由与共享契约）
> 审查路线：用户逐条拍板方案 + 主 agent 自动化核查闭环

## 用户原始请求

> "我觉得x dev后续的 qa r1， r2，r3 检查有点冗余，流程太长，而且后面问题往往是e2e才发现，从第一性原理思考如何缩短这个流程，并且要引导llm回复 review的过程到底发现了多少不同等级的bug，而不是让用户自己看文档，你先给我方案"
>
> （x-auth-identity-foundation 实证分析后）"你的方案A说具体一点"
>
> "你不要看claude code，你就改成 尽量用同一个reviewer，让llm自己处理。然后你用一句话概括dev 后半部分的 review流程"
>
> "y"

## 任务说明

把 Gate ②（x-qa-gate）从"三段串行 + 逐问题打回 + 回 R1 全量重审"改造为"风险路由 + 一轮列全 + 批量修 + 增量复审"，并为 verify/qa-gate/fix 三个 gate 节点加统一门禁回执契约。方案由 x-infra `x-auth-identity-foundation` 任务实测数据驱动：该任务 5 个 P0 全部由静态评审抓到（质量有效），但 R2 逐问题打回 4 轮 + 每次 fix 回 R1 空转 4 次，6 次修复配额被结构性耗尽（效率失败）。

## 明示假设

| 编号 | 假设 | 依据 | 影响 |
|------|------|------|------|
| A1 | 用户同意方案 A′（风险路由 + 一轮列全 + 批量修 + 增量复审 + 回执 + counter 3 轮） | 当前会话逐条拍板后回 "y" | 决定全部改动结构 |
| A2 | "尽量用同一个 reviewer"不绑定 harness 机制，由执行时 LLM 自行处理 | 用户明确指示 | 复审条款措辞 |
| A3 | R1/R2/R3 检查清单内容是有效资产不砍 | x-auth 实测 5/5 真 P0 | 三份手册只加输出契约不改清单 |

## DoD 与证据

| 编号 | DoD | 证据 | 状态 |
|------|-----|------|------|
| D1 | Gate ② 风险路由：默认单综合 reviewer RC，高危 R1→R2→R3 | `skills/x-qa-gate/SKILL.md`「风险路由」+ 新增 `references/rc-unified.md` | ✅ |
| D2 | 一轮列全契约进入全部 reviewer 手册（覆盖声明/发现清单 F#/穷尽声明/漏检） | rc-unified + r1/r2/r3 四份手册 + SKILL.md 硬约束 | ✅ |
| D3 | x-fix 批量修：一次修完清单、逐条处置表、每 P0 固化反例、废除 4 条回流规则 | `skills/x-fix/SKILL.md`「Gate 回流」+ `references/qa-gate-fix-mode.md` 重写 | ✅ |
| D4 | 增量复审：尽量同 reviewer 续审 + 三条熔断 | `skills/x-qa-gate/SKILL.md`「增量复审」 | ✅ |
| D5 | fix-counter 按批量修轮数计，上限 6 → 3 | verify/qa-gate/fix 三处 SKILL.md + 模板 + CLAUDE.md 契约表 | ✅ |
| D6 | x-verify 必跑清单 = dev-report 命令 + README Smoke/E2E（manual 列待人工验收） | `skills/x-verify/SKILL.md` + verify-report 模板 + x-req 用例命令化要求 | ✅ |
| D7 | 门禁回执强制对话输出（分级计数 + 拦截来源 + 零发现也报） | verify/qa-gate SKILL.md 回执节 + CLAUDE.md 契约表新增行 | ✅ |
| D8 | 全仓一致：无"6 次上限/旧 fix 模式名"残留，13 个 SKILL.md frontmatter 有效、围栏平衡 | grep 零命中（exit 1）+ python 校验全 ✅ | ✅ |

## 风险判断

- 风险等级：Q2
- 触发因素：修改 x-qa-gate/x-verify/x-fix 共享契约与 description 触发面（触发关键词全部保留）
- 升级条件：e2e smoke 实测发现路由或计数协议歧义

## 涉及文件

- `skills/x-qa-gate/SKILL.md`（重写）、`references/rc-unified.md`（新增）、`references/r{1,2,3}-*.md`、`templates/qa-gate-report-template.md`（重写）
- `skills/x-fix/SKILL.md`、`references/qa-gate-fix-mode.md`（重写）
- `skills/x-verify/SKILL.md`（重写）、`templates/verify-report-template.md`（重写）
- `skills/x-dev/SKILL.md`、`templates/dev-report-template.md`（新增 risk 字段）
- `skills/x-req/SKILL.md`（验收用例优先命令化）
- `CLAUDE.md`、`README.md`、`README_zh.md`、`CHANGELOG.md`
- `examples/req-modules-diagram-demo.md` / `.html`（gate 节点文字同步）

## 开发清单

| 编号 | 优先级 | 状态 | 任务 |
|------|--------|------|------|
| #1 | P0 | ✅ 已完成 | x-qa-gate 风险路由 + 一轮列全 + 增量复审 + 回执 |
| #2 | P0 | ✅ 已完成 | rc-unified 综合 reviewer 手册 + r1/r2/r3 输出契约 |
| #3 | P0 | ✅ 已完成 | x-fix 批量修 + counter 按轮上限 3 |
| #4 | P0 | ✅ 已完成 | x-verify 纳入 Smoke/E2E + 回执 |
| #5 | P1 | ✅ 已完成 | 模板（dev-report risk / verify / qa-gate report）与 x-req 同步 |
| #6 | P1 | ✅ 已完成 | CLAUDE.md / README 双语 / CHANGELOG / examples 契约同步 |
| #7 | P1 | ✅ 已完成 | 全仓残留核查 + frontmatter 校验 |
