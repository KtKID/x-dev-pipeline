# x-dev 执行规则

## Checklist 状态

| token + emoji | 含义 | 责任 |
|---|---|---|
| `[ ] ⏳` | 未开始 | 等待依赖满足；需求变化后重开的行也回到这里 |
| `[ ] ▶️` | 进行中 | x-dev 已开始实现 |
| `[ ] 🟡` | 待验证 | 实现完成，等待验证（多 agent 协作时工人交回、还没合并） |
| `[!] 🔴` | 开发中失败 | 开发负责方修好后恢复 |
| `[x] 🟢` | 测试通过 | 用例对应表已登记；等待 x-verify-spec 验收 |
| `[x] ✅` | 已完成 | 主 agent 在 x-verify-spec 验收通过后升级 |
| `[ ] ↗️` | 已升级 | 超出本 task 范围（如 qdev 转主线、某组 3 轮核对不过、验收 3 轮修复不过）交给用户或主线 |

`xdev status` 与 `xdev graph` 以 emoji 判定状态。多 agent 协作时，状态列只由主 agent 写，见 [多 agent 协作开发](parallel-dev.md)。每次变更状态立即回写 checklist；结果与证据按 [证据约定](test-reporting.md) 写在 checklist 的「结果」节和 `evidence/`。

### 验收问题的写权

- 功能检查的问题只写在证据目录的 `feature-check.md` 回执里，编号 issue-1、issue-2…；处置写进 checklist「问题与处置」。不另建 issue 登记本，验收发现问题时不把行降为 🔴。
- 子 agent（功能检查、x-fix）不改 checklist 状态列；状态由主 agent 写。

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

checklist 头部的 `risk` 由 x-req 按任务行算出（`xdev validate` 核对）。验收时 risk Q0 不做功能检查，只跑 `xdev check`；Q1 / Q2 / Q3 都做一次同样的功能检查。见 [x-verify-spec](../../x-verify-spec/SKILL.md)。
