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

- 父 `### Requirement:` 为空的 Scenario SHALL 始终报告，**不分 `auto` 与 `manual`**，不受本 task 范围限制（成因含整节无 Requirement 分层、以及非 `### Requirement:` 的 H3 截断了当前作用域）——这类场景不属于任何 task，无人可归。
- 本 task 范围内的 Requirement 在 spec.md 下**没有任何 `#### Scenario:`** 时 SHALL 报告——需求被 task 承接却无验收场景，范围会算空并静默通过。
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

### Requirement: Requirement-scenario pair binding

auto verify 块 SHALL 同时给出 `requirement:` 与 `scenario:`，缺任一 SHALL 以退出码 2 报告。覆盖判定 SHALL 使用 `(requirement, scenario)` 组合键，`expected_auto` 每项 SHALL 含所属 Requirement。同一 Requirement 内的 Scenario 重名 SHALL 以退出码 2 报告。

verify SHALL 输出结构化 `mismatch`，至少覆盖越界绑定（块回指的 Requirement 不在本 task 范围内）、父级错配（`requirement:` 与 `scenario:` 在 spec.md 中不构成父子）、mode 漂移（spec.md 标 manual 的场景被 auto 块回指，或标 auto 的场景只有 manual 块）。

#### Scenario: 跨 Requirement 同名场景各自独立对账

- **GIVEN** 本 task 承接的两个 Requirement 下有同名 Scenario，dev-report 只给出其中一个 Requirement 的证据
- **WHEN** 调用方运行 `verify --json`
- **THEN** 另一个 Requirement 下的同名场景仍出现在 `uncovered`，命令以退出码 1 结束

#### Scenario: 证据缺少 requirement 回指

- **GIVEN** dev-report 的 auto 块只写了 `scenario:`，没有 `requirement:`
- **WHEN** 调用方运行 `verify`
- **THEN** 命令以退出码 2 结束并指出该块

#### Scenario: 越界绑定进入 mismatch

- **GIVEN** auto 块回指的 Requirement 不在本 task checklist 承接的范围内
- **WHEN** 调用方运行 `verify --json`
- **THEN** 该块出现在 `mismatch` 中并标明越界，不计入覆盖

### Requirement: Partial execution disclosure

`--only <id>` SHALL 使结果标注 `partial: true` 与 `selected`，且 SHALL NOT 计算 `uncovered`——未执行块的 `scenario:` 声明 SHALL NOT 计入覆盖。全量执行时 `partial` SHALL 为 false。Gate① SHALL NOT 使用 `partial` 为真的结果放行。

#### Scenario: 抽查结果不得冒充完整验收

- **GIVEN** dev-report 含两个 auto 块，其中未被选中的那个会失败
- **WHEN** 调用方运行 `verify --only <通过的块 id> --json`
- **THEN** 结果标注 `partial: true` 与 `selected`，不含 `uncovered`，Gate① 不得据此放行

### Requirement: Manual scenario reconciliation

verify 的 `manual` 输出 SHALL 以本 task 范围内 spec.md 的 manual Scenario 为基准，与 dev-report 的 manual 块对账；spec.md 声明而 dev-report 缺失的 manual 场景 SHALL 列为未认领，SHALL NOT 静默省略。

#### Scenario: spec 声明的人工场景缺步骤块

- **GIVEN** 本 task 承接的 Requirement 下有 `验证: manual` 的 Scenario，dev-report 没有对应 manual 块
- **WHEN** 调用方运行 `verify --json`
- **THEN** 该场景在 `manual` 中标为未认领，而不是同时缺席 `expected_auto` 与 `manual`

#### Scenario: checklist 不可读时报告用法错误

- **GIVEN** task 缺少 `dev-checklist.md`，或其任务表缺 `#`/`状态` 关键列
- **WHEN** 调用方运行 `verify --json`
- **THEN** 命令以退出码 2 结束，并指出是 checklist 而非 dev-report 的问题
