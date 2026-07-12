# Qdev Report — qdev-risk-routed-verification — 20260711

## 风险与审查路线

- 风险等级：Q2
- 触发因素：修改公开 skill 路由，涉及 qdev、verify、qa-gate、req、fix 和仓库入口文档
- 审查路线：一个综合只读 reviewer

## 改动文件

- `skills/x-qdev/**` — 风险分流、任务起点基线、证据闭环、综合 reviewer、升级终态和独立报告模板
- `skills/x-req/SKILL.md` — qdev Q3 promotion mode 工件交接
- `skills/x-verify/SKILL.md`、`skills/x-qa-gate/**`、`skills/x-fix/SKILL.md`、`skills/x-cr/references/auto-loop-mode.md` — 上下游路由和事实源契约
- `skills/x-dev/templates/dev-report-template.md` — 完整门禁 schema 边界
- `CLAUDE.md`、`README.md`、`README_zh.md`、`CHANGELOG.md` — 活跃仓库说明
- `examples/req-modules-diagram-demo.md`、`examples/req-modules-diagram-demo.html` — 公开流程示例
- `dev-pipeline/tasks/qdev-risk-routed-verification/**` — 本次任务记录

## DoD 证据矩阵

| DoD | 证据类型 | 命令 / 文件 | 实际结果 | 状态 |
|-----|----------|-------------|----------|------|
| D1 Q0/Q1 默认在 qdev 内闭环 | 契约扫描 | `rg` 检查旧自动链与 `Q0 / Q1：主 agent 闭环` | 旧自动链无命中，新路线存在 | pass |
| D2 Q2 只使用一个综合 reviewer | 代码路径 + 真实 review | `skills/x-qdev/SKILL.md` Q2 段；本次综合 reviewer 两轮对抗审查 | 单 reviewer、fail 续接、两轮失败升级规则齐全 | pass |
| D3 Q3 升级完整流程 | 跨 skill 契约 | `source-qdev` 同时存在于 x-qdev 与 x-req promotion mode | 新建 `*-full` task，原 qdev 使用 ↗️ 终态 | pass |
| D4 原始请求、假设、证据分层 | 模板检查 | `skills/x-qdev/templates/README.md`、本 task README | 原始消息、脱敏规则、假设、DoD 证据和起点基线均存在 | pass |
| D5 活跃文档和触发说明一致 | validator + 全局扫描 | quick_validate、旧链 adversarial `rg`、Markdown fence 检查 | 5 个 skill valid；旧链无命中；fence 平衡 | pass |

## 实际验证命令

| 命令 | 工作目录 | 实际 exit | 关键输出 |
|------|----------|-----------|----------|
| `python .../quick_validate.py skills/{x-qdev,x-req,x-verify,x-qa-gate,x-fix}`（逐项执行） | 项目根 | 0 | 5 次 `Skill is valid!` |
| `git diff --check` | 项目根 | 0 | 无输出 |
| 旧自动链与废弃命名 adversarial `rg` | 项目根 | 0 | 目标模式无命中 |
| Q0-Q3、起点基线、↗️、P0/P1 映射、`source-qdev` contract `rg` | 项目根 | 0 | `qdev-adversarial-contract-ok` |
| 修改 Markdown 的 fence 偶数检查 | 项目根 | 0 | `markdown-fences-ok` |
| 活跃文件同步到 Codex plugin cache 后逐文件 `cmp` | 项目根 / cache | 0 | `codex-cache-sync-ok` |

```text
no-test-framework: true
reason: 当前仓库是 Markdown skill/plugin 集合，没有应用运行时或自动化测试套件
manual-check: skill validator + route contract scan + adversarial stale-chain scan + Markdown structure check + combined reviewer
```

## Diff 审查

- 任务起点基线：tracked worktree clean；既有未跟踪目录为 `.claude/`、`.kongming/`、`.xcodeatlas/`
- `git diff --stat`：16 个 tracked 文件为 skill 路由、模板、活跃说明和公开示例；新增 qdev report 模板与本 task 三个工件
- 实际范围与声明范围：一致；reviewer 要求补充的 x-req promotion 和 examples 路由属于契约闭环
- 成功路径证据：Q0/Q1 直接闭环、Q2 单 reviewer、Q3 promotion 三条路径均通过契约扫描
- 关键失败路径证据：>2h/>5 DoD、行为歧义、dirty worktree、reviewer fail/unavailable、Q3 完成状态均有明确处理
- 用户既有改动保护：三个既有未跟踪目录保持原状，任务未写入其中

## 综合 Reviewer（Q2）

- Status：pass
- Evidence：第一轮和第二轮共发现 8 个 P1/P2 流程边界，均已逐条修正并续接同一 reviewer
- P0：none
- P1：全部 resolved；最终复审确认 P1 为 0

## 最终结论

- [x] 每条 DoD 都有真实证据
- [x] 实际 diff 与任务范围一致
- [x] 成功路径已验证
- [x] 适用的关键失败路径已验证
- [x] Q2 综合 reviewer 最终通过

结论：complete
