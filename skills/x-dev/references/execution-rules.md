# x-dev 执行规则

## Checklist 状态

| token + emoji | 含义 | 责任 |
|---|---|---|
| `[ ] ⏳` | 未开始 | 等待依赖满足 |
| `[ ] ▶️` | 进行中 | x-dev 已开始实现 |
| `[ ] 🟡` | 待测试 | 实现完成，等待声明验证 |
| `[!] 🔴` | 验证失败 | x-fix 批量修复 |
| `[x] 🟢` | 测试通过 | 等待 risk 路由结束 |
| `[x] ✅` | 已完成 | Gate ② 通过，或 Q0/Q1 verify 通过 |

`status` 与 `graph` 以 token 判定；纯 emoji 历史 checklist 按引擎兼容规则读取。每次变更状态立即回写 checklist；实现与验证事实回写 dev-report。

## Verify 块

```verify
id: S1
scenario: <README Scenario 名>
cmd: <可复跑命令>
expect_exit: 0
expect_contains: <关键输出>
```

- auto 块执行命令；manual 块只记录 `steps`。
- `scenario:` 与 auto Scenario strip 后精确匹配。
- `python3 tools/xdev.py verify <task-dir> --json` 返回 0、1、2；1 的全部 failure 与 uncovered 同轮进入 x-fix，2 回到 dev-report 编辑。

## Risk 路由

| README risk | verify 通过后的动作 |
|---|---|
| Q0 / Q1 | 交付回执，列出 manual 与定级依据 |
| Q2 | x-qa-gate RC |
| Q3 | x-qa-gate R1 → R2 → R3 |
