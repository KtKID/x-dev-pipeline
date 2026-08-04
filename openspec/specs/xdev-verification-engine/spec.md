# xdev-verification-engine Specification

## Purpose
TBD - created by archiving change unified-flow-verify-engine. Update Purpose after archive.
## Requirements
### Requirement: Verify block parser
`python3 skills/x-dev/scripts/xdev.py verify <task-dir> [--json] [--only <id>]` SHALL 从 task 最新 dev-report 读取全部 fenced `verify` 块。每个块 SHALL 使用 `key: value` 行；支持 `id`、`scenario`、`cmd`、`cwd`、`expect_exit`、重复的 `expect_contains`、`timeout`、`mode` 与 `steps`。auto 块必须有唯一 `id` 和 `cmd`，manual 块必须有唯一 `id` 和 `steps`；未知 key、重复 id、非法 mode、非法数值和缺少必要字段 SHALL 以退出码 2 报告。

#### Scenario: 解析自动与人工证据
- **GIVEN** dev-report 包含一个 auto 块和一个 manual 块
- **WHEN** 调用方运行 `verify --json`
- **THEN** 结果包含可执行的 auto 项和不执行的 manual 项，且命令以退出码 0 或 1 结束

#### Scenario: 拒绝无效 verify schema
- **GIVEN** dev-report 包含未知 key、重复 id 或 auto 块缺少 cmd
- **WHEN** 调用方运行 `verify`
- **THEN** 命令以退出码 2 结束，并指出对应块与格式原因

### Requirement: Deterministic verification execution
verify SHALL 在仓库根目录或块声明的相对 `cwd` 执行每个 auto `cmd`，合并 stdout 与 stderr，比对实际退出码以及每个 `expect_contains` 子串。显式 `timeout` 超时 SHALL 形成失败项；`--only <id>` SHALL 只执行指定 auto 块。结果 SHALL 以 JSON 或人类可读形式列出 `pass`、`fail`、`manual` 与 `uncovered`；每个失败项 SHALL 包含 id、命令、实际与预期退出码、缺失片段和合并输出。

#### Scenario: 命令事实全部匹配
- **GIVEN** auto verify 块的命令退出码和全部预期片段均匹配
- **WHEN** 调用方运行 `verify --json`
- **THEN** 该块位于 `pass`，且不产生 `fail`

#### Scenario: 命令事实不匹配
- **GIVEN** auto verify 块产生错误退出码、缺失输出片段或显式超时
- **WHEN** 调用方运行 `verify --json`
- **THEN** 结果以退出码 1 结束，并在 `fail` 中保留可诊断字段

### Requirement: Scenario coverage reconciliation
verify SHALL 解析 README `## 验收` 中标记 `验证: auto` 的 `#### Scenario:` 名称。每个自动场景 SHALL 至少有一个 auto verify 块以 `scenario:` 回指同名场景；strip 后仍不匹配的名称 SHALL 出现在 `uncovered`。manual 场景 SHALL 不要求 verify 块。

#### Scenario: 自动场景已有证据回指
- **GIVEN** README 的 auto Scenario 与 auto verify 块的 scenario 值匹配
- **WHEN** 调用方运行 `verify --json`
- **THEN** 该场景不出现在 `uncovered`

#### Scenario: 自动场景缺少证据回指
- **GIVEN** README 的 auto Scenario 没有匹配的 auto verify 块
- **WHEN** 调用方运行 `verify --json`
- **THEN** 命令以退出码 1 结束，且该场景出现在 `uncovered`
