# xdev-verification-engine Delta

## MODIFIED Requirements

### Requirement: Deterministic verification execution

verify SHALL 在**项目根目录**（task 目录往上四级，不相对插件仓库根）或块声明的项目内相对 `cwd` 执行每个 auto `cmd`，合并 stdout 与 stderr，比对实际退出码以及每个 `expect_contains` 子串。显式 `timeout` 超时 SHALL 形成失败项；`--only <id>` SHALL 只执行指定 auto 块。

JSON 结果 SHALL 含 `requirements`、`expected_auto`、`pass`、`fail`、`manual` 与 `uncovered` 六个字段。人类可读结果 SHALL 含 `requirements` 一行（范围为空时显式标注无验收绑定）、`pass`/`fail`/`manual` 计数、每个失败项与每个 `uncovered` 场景名；`expected_auto` 只在 JSON 中给出。每个失败项 SHALL 包含 id、命令、实际与预期退出码、缺失片段和合并输出。

#### Scenario: 命令事实全部匹配

- **GIVEN** auto verify 块的命令退出码和全部预期片段均匹配
- **WHEN** 调用方运行 `verify --json`
- **THEN** 该块位于 `pass`，且不产生 `fail`

#### Scenario: 命令事实不匹配

- **GIVEN** auto verify 块产生错误退出码、缺失输出片段或显式超时
- **WHEN** 调用方运行 `verify --json`
- **THEN** 结果以退出码 1 结束，并在 `fail` 中保留可诊断字段

#### Scenario: 结果声明本 task 的验收范围

- **GIVEN** 任意合法 task
- **WHEN** 调用方运行 `verify --json`
- **THEN** 结果包含 `requirements`（本 task 承接的 Requirement）与 `expected_auto`（裁剪后的预期自动场景），使空 `uncovered` 可与空范围区分

### Requirement: Scenario coverage reconciliation

verify SHALL 读取当前 task 的 `dev-checklist.md`，取 `Requirement` 列中所有非空占位的名字（按声明顺序去重）作为本 task 的验收范围；`—`、`-`、`n/a` 与空单元格 SHALL 同等视为无绑定，判定集合与依赖列保持一致。verify 再由 task 实际所在位置推定归属 spec 包并读取其 `spec.md`，只把父 `### Requirement:` 落在该范围内的 `#### Scenario:` 纳入对账，`expected_auto` SHALL 按场景名去重。

范围内每个标记 `验证: auto` 的 Scenario SHALL 至少有一个 auto verify 块以 `scenario:` 回指同名场景；strip 后仍不匹配的名称 SHALL 出现在 `uncovered`。manual 场景 SHALL 不要求 verify 块。verify SHALL NOT 要求当前 task 覆盖归属 spec 中由其他 task 承接的 Requirement 及其 Scenario。

Scenario 的验证标记 SHALL 写作独立一行 `验证: auto|manual`；冒号 SHALL 接受半角与全角两种形态，取值大小写不敏感，允许 `-`/`*`/`+` 列表前缀。

归属 `spec.md` 的验收标注不足以判定场景归属时，verify SHALL 以退出码 2 一次列全问题场景名，SHALL NOT 返回裁剪结果——此时范围判定的前提不成立，任何 `uncovered` 结论都无意义。两类判定的范围不同：

- 父 `### Requirement:` 为空的 `验证: auto` Scenario SHALL 始终报告，不受本 task 范围限制（成因含整节无 Requirement 分层、以及非 `### Requirement:` 的 H3 截断了当前作用域）——这类场景不属于任何 task，无人可归。
- 解析不出合法验证标记的 Scenario SHALL 在其父 Requirement 落入本 task 范围时报告，父 Requirement 为空时一并报告；父 Requirement 属于其他 task 时 SHALL NOT 拦截本 task——这类场景能够归属，按 task-scoped 原则由承接方拦。

上述检查 SHALL 在执行任何 auto `cmd` 之前完成。

`dev-checklist.md` 缺失或表头不可解析 SHALL 以退出码 2 报告。verify SHALL NOT 从 task README 读取验收场景。

#### Scenario: 自动场景已有证据回指

- **GIVEN** 本 task 承接的 Requirement 下的 auto Scenario 与 dev-report auto verify 块的 scenario 值匹配
- **WHEN** 调用方运行 `verify --json`
- **THEN** 该场景不出现在 `uncovered`

#### Scenario: 自动场景缺少证据回指

- **GIVEN** 本 task 承接的 Requirement 下的 auto Scenario 没有匹配的 auto verify 块
- **WHEN** 调用方运行 `verify --json`
- **THEN** 命令以退出码 1 结束，且该场景出现在 `uncovered`

#### Scenario: 其他 task 承接的场景不进入本 task 范围

- **GIVEN** 同一 spec 下 task A 的 checklist 只承接 Requirement A，task B 只承接 Requirement B，两者各自给出自己场景的证据
- **WHEN** 分别对 task A 与 task B 运行 `verify --json`
- **THEN** 两者的 `expected_auto` 各只含自己 Requirement 下的场景，`uncovered` 均为空，且都以退出码 0 结束

#### Scenario: 无验收绑定的 task 范围为空

- **GIVEN** task 的 checklist 中 `Requirement` 列全为 `—`、`-`、`n/a` 或空
- **WHEN** 调用方运行 `verify --json`
- **THEN** `requirements` 与 `expected_auto` 均为空，verify 只复跑 dev-report 中的命令，不产生 `uncovered`

#### Scenario: 验收分层不合法时拒绝放行

- **GIVEN** 归属 `spec.md` 的验收节中有 `验证: auto` 的 Scenario 没有父 `### Requirement:`（无分层，或被非 Requirement 的 H3 截断作用域）
- **WHEN** 调用方运行 `verify --json`
- **THEN** 命令以退出码 2 结束并列出这些场景名，不输出 `uncovered` 为空的通过结果

#### Scenario: 场景缺少验证标记时拒绝放行

- **GIVEN** 本 task 承接的 Requirement 下有 Scenario 未写出可解析的 `验证: auto|manual` 行
- **WHEN** 调用方运行 `verify --json`
- **THEN** 命令以退出码 2 结束并点名该场景，不把它当作无需证据的场景放行

#### Scenario: 其他 task 范围内的缺标记场景不拦本 task

- **GIVEN** 同一 spec 下 task B 承接的 Requirement 有场景漏写验证标记，task A 承接的 Requirement 标注完整
- **WHEN** 分别对 task A 与 task B 运行 `verify --json`
- **THEN** task A 正常给出对账结果，task B 以退出码 2 报告该场景

#### Scenario: 全角冒号的验证标记等价识别

- **GIVEN** Scenario 的标记行写作 `验证：auto`（全角冒号）
- **WHEN** 调用方运行 `verify --json`
- **THEN** 该场景与半角冒号写法一样进入 `expected_auto` 并参与覆盖判定

#### Scenario: 同一 task 内的同名场景只计一次

- **GIVEN** 本 task 承接的两个 Requirement 下存在同名 auto Scenario
- **WHEN** 调用方运行 `verify --json`
- **THEN** `expected_auto` 中该名称只出现一次

#### Scenario: checklist 不可读时报告用法错误

- **GIVEN** task 缺少 `dev-checklist.md`，或其任务表缺 `#`/`状态` 关键列
- **WHEN** 调用方运行 `verify --json`
- **THEN** 命令以退出码 2 结束，并指出是 checklist 而非 dev-report 的问题
