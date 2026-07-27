## Why

`tools/xdev.py` 已增长到 2252 行，同时承载包校验、旧 task 兼容、QA issue 事务和 CLI 路由。spec、req、verify 已经形成独立引擎，继续把实现堆在统一入口会扩大修改面，也让已经决定退役的 `dev-pipeline/tasks/` 运行时长期存活。

## What Changes

- 将 spec7/change/capability 的包识别与机械校验拆到独立 `tools/validator.py`。
- 将 `flag` 的输入校验、ledger 写入和崩溃恢复事务拆到独立 `tools/flag.py`。
- `tools/xdev.py` 收敛为薄 CLI：参数解析、目标发现和向 `validator.py`、`spec.py`、`req3.py`、`verify.py`、`flag.py` 分流。
- 删除 req2 task 兼容能力和 `tools/req.py`，只保留自包含的 `tools/req3.py`。
- **BREAKING**：删除 `dev-pipeline/tasks/` 旧结构的 V8-V12 校验、旧 README 产物 instructions/scaffold、旧 status/graph 实现及其专属测试；历史目录作为文档保留。
- 公开 task 命令统一返回 req3 的 `dev-checklist` / `diagram` 产物。
- 删除 `xdev.py` 中无调用的兼容包装、重复用法说明和仅供旧结构使用的常量/解析函数。
- 同步 benchmark bundled runtime 的新增模块、manifest 和隔离 workspace 预检。

## Capabilities

### New Capabilities

- `xdev-command-router`: 定义薄 CLI 的模块所有权、命令分流、运行时依赖完整性和行数预算。

### Modified Capabilities

- `xdev-task-artifact-engine`: 完成旧 task 与 req2 运行时退役，并将 instructions/scaffold/status/graph 统一委托给 req3 task 引擎。

## Impact

- 代码：`tools/xdev.py`、新增 `tools/validator.py` / `tools/flag.py`、统一 `tools/req3.py`，以及相关测试。
- 运行时：benchmark executor tools 增加 `validator.py`、`flag.py` 并更新 manifest。
- CLI：当前 spec3 task 的 validate/instructions/scaffold/status/graph/verify/flag 命令保持；spec3/spec7/change 校验输出保持。
- 破坏面：spec2 包与 req2 task 不再识别。
- 破坏面：显式对 `dev-pipeline/tasks/*` 调用 validate/instructions/scaffold/status/graph 将返回用法或目标类型错误。
- 后续阶段：公共 Markdown 解析器合并和 OpenSpec 存量 active change 归档留给独立变更。
