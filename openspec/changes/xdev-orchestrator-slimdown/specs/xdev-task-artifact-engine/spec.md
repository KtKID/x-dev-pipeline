## MODIFIED Requirements

### Requirement: 产物 instructions 命令

工具层 SHALL 提供 `python3 tools/xdev.py instructions <artifact-id> --task <task-dir> [--json]`。命令 SHALL 委托 `req3.py` 的产物注册表。JSON 输出 SHALL 包含 `artifact`、`output_path`、`exists`、`template`、`instruction`、`requires`、`dependencies` 和 `profile`；每个 dependency SHALL 包含 `id`、`path` 和 `exists`。命令 SHALL 只支持 spec3 的 `docs/spec/*/tasks/*` task。

#### Scenario: 返回 req3 产物 instructions

- **GIVEN** 合法 spec3 task 和已注册 artifact
- **WHEN** 调用方使用 `--json` 请求 instructions
- **THEN** 命令以 0 退出，返回 `profile: req3` 和当前 x-req3 模板

#### Scenario: 拒绝历史 task instructions

- **GIVEN** task 位于 `dev-pipeline/tasks/`
- **WHEN** 调用方请求 instructions
- **THEN** 命令以 2 退出，并说明只支持 `docs/spec/*/tasks/*`

#### Scenario: 拒绝未知 artifact ID

- **GIVEN** artifact ID 不在目标 req 引擎注册表中
- **WHEN** 调用方请求 instructions
- **THEN** 命令以 2 退出，并列出该引擎合法 artifact ID

### Requirement: Task 包分发与完整性校验

显式校验 SHALL 只在目标解析后位于 spec3 的 `docs/spec/*/tasks/` 下时将其识别为 task 包，并委托 `req3.py`。工具层 SHALL NOT 识别或校验 spec2 task 与 `dev-pipeline/tasks/` 下的历史结构，SHALL NOT 保留 V8-V12、README 结构检测、旧 checklist、旧 status/graph 或旧 scaffold 分支。自动发现 SHALL 继续只发现 spec 与 change 包。

#### Scenario: 当前 task 被识别并校验

- **GIVEN** `docs/spec/foo/tasks/bar/` 含合法 checklist
- **WHEN** 调用方执行显式 validate
- **THEN** 委托 req3 引擎

#### Scenario: 历史 task 被拒绝

- **GIVEN** `dev-pipeline/tasks/` 下存在 README 和旧 checklist
- **WHEN** 对其运行 validate、scaffold、status、graph 或 instructions
- **THEN** 命令以 2 退出或返回 unknown target，且不执行旧 V8-V12 规则

#### Scenario: 自动发现不扫 task

- **GIVEN** 仓库同时存在 spec 包和历史/current task
- **WHEN** 运行未指定目标的 validate
- **THEN** 自动发现只返回 spec 与 change 包

## REMOVED Requirements

### Requirement: README 契约校验

**Reason**: 当前 task 由 checklist 指针关联 spec，README/V11/V12 已由 req3 契约取代。

**Migration**: 新 task 使用 `docs/spec/<spec-name>/tasks/<task-name>/dev-checklist.md`；历史目录保留为只读文档。
