# x-dev 执行规则

## Checklist 状态

| token + emoji | 含义 | 责任 |
|---|---|---|
| `[ ] ⏳` | 未开始 | 等待依赖满足；需求变化后重开的行也回到这里 |
| `[ ] ▶️` | 进行中 | x-dev 已开始实现 |
| `[ ] 🟡` | 待验证 | 实现完成，等待验证（多 agent 协作时工人交回、还没合并） |
| `[!] 🔴` | 验证失败 | x-fix 批量修复 |
| `[x] 🟢` | 测试通过 | 用例对应表已登记；等待 `xdev check` 和审查 |
| `[x] ✅` | 已完成 | 主 agent 升级：risk Q0 在 `xdev check` 通过后；Q1/Q2/Q3 在 x-qa-gate 通过后。同时把 `reports/.fix-counter` 写回 0（存在时） |
| `[ ] ↗️` | 已升级 | 超出本 task 范围（如 qdev 转主线、某组 3 轮验收不过）交给用户或主线 |

`xdev status` 与 `xdev graph` 以 emoji 判定状态。多 agent 协作时，状态列只由主 agent 写，见 [多 agent 协作开发](parallel-dev.md)。每次变更状态立即回写 checklist；结果与证据按 [证据约定](test-reporting.md) 写在 checklist 的「结果」节和 `evidence/`。

### QA Gate 写权

- 子 agent 实现或修复代码时保持 checklist 状态单元格与 `reports/qa-gate/qa-gate-report-*.md` 原样。
- `python3 "${XDEV_SKILL_DIR}/scripts/xdev.py" flag ...` 是 issue ledger 和 P0/P1 `[!] 🔴` 降级的唯一写入口。
- 主 agent 按 reviewer 候选顺序串行调用 `flag`；每个 task 长期只保留一份 `dev-checklist.md`。
- x-fix 修完、主 agent 按 x-qa-gate「回流」关闭问题后，主 agent 亲自确认并把对应 `[!]` 升为 `[x]`。
- P2 flag 只登记 issue，所有 task 状态保持原样。

## Verify 块（仅旧契约包）

只适用于父 spec 声明 `spec_version: 3` 的旧契约包。当前格式的 task 不写 verify 块：交付核对用 `xdev check`，需求变化用 `xdev impact` 检查。

```verify
id: S1
scenario: <单个 Scenario ID，例如 SC_01>
cmd: <可复跑命令>
expect_exit: 0
expect_contains: <关键输出>
```

- auto 块执行命令；manual 块只记录 `steps`。
- req 的 `scenario:` 只填写单个 Scenario ID 并精确匹配；verify 块按 ID 分别保存证据。
- `python3 "${XDEV_SKILL_DIR}/scripts/xdev.py" verify <task-dir> --json` 返回 0、1、2；1 的全部 failure 与 uncovered 同轮进入 x-fix，2 回到 dev-report 编辑（旧契约包的 dev-report 用 `templates/dev-report-template.md`）。

## Risk 路由

checklist 头部的 `risk` 由 x-req 按任务行算出（`xdev validate` 核对）。`xdev check` 通过后：Q0 直接交付，由主 agent 升 ✅；Q1 / Q2 / Q3 交 x-qa-gate，怎么审以 [x-qa-gate](../../x-qa-gate/SKILL.md) 的「路由」为准。
