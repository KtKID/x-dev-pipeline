## Why

x-qa-gate reviewer 已能指出 task 级问题，但 issue 编号、台账落盘和 checklist 降级依赖 LLM 手写。v7 将写入口收窄为确定性 `flag` 命令：LLM 只传参数，代码完成校验、`issue-<n>` 编号、轮次管理、格式化、事务恢复与降级。

## What Changes

- 新增 `python3 tools/xdev.py flag <task-dir> --task <T#列表> --severity <P0|P1|P2> --loc <file:line> --msg <问题描述> [--new-round] [--json]`。
- 代码为每轮问题分配 `issue-1`、`issue-2`；只扫描代码生成的 issue 行首分配下一个编号，不解析台账内容字段。
- 参数校验覆盖 severity、严格 T# 列表、单行 `file:line` 和可打印 msg；校验失败返回 2 且零写入。
- 主 agent 串行调用 `flag`；使用 `.flag-transaction.json`、固定同目录临时路径、读取时/目标 SHA-256 与 `os.replace` 协调 issue 台账和唯一一份 checklist。内容无变化的目标不创建临时文件，提交与恢复完成后清理全部 scratch 文件。
- `--new-round` 同秒冲突采用 `-01`、`-02` 数值后缀，新轮 issue 编号重新从 1 开始。
- flag 对 P0/P1 只执行 `[!] 🔴` 降级，P2 只登记；主 agent 在复审确认后手动升回 `[x]`。
- **BREAKING**：Gate ② 活跃编号从 F1..Fn 迁移为代码分配的 `issue-<n>`；QA Gate 报告内容收敛为 flag 生成的 issue ledger 骨架。
- 同步 x-qa-gate、reviewer references、x-dev execution rules、x-fix、CLAUDE 与中英文 README。

## Capabilities

### New Capabilities

- `xdev-progress-engine`: 定义 flag 参数校验、轮次与 issue 编号、代码生成台账、单写者双文件事务恢复、唯一 checklist、CLI 输出和兼容行为。

### Modified Capabilities

- `risk-routed-development-flow`: Gate ② reviewer 只返回问题内容；主 agent 通过 flag 登记；issue ID、台账和降级由代码生成；修复与复审使用 `issue-<n>` 追踪。

## Impact

- 代码与测试：`tools/xdev.py`、`test/test_xdev_flag.py`。
- Skills：x-qa-gate SKILL/references/template、x-dev execution rules、x-fix SKILL 与 gate-fix reference。
- 仓库文档：`CLAUDE.md`、`README.md`、`README_zh.md`。
- Task 产物：目标 `dev-checklist.md` 与 `reports/qa-gate/qa-gate-report-*.md`；事务标记位于同一 reports 目录。
- 依赖：Python 标准库；历史 checklist 保持兼容，历史归档报告保持原样。
