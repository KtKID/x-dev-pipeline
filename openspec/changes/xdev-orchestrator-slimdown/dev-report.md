# Implementation Report — xdev-orchestrator-slimdown

> 日期：2026-07-25
> 状态：complete
> OpenSpec：`openspec/changes/xdev-orchestrator-slimdown/`

## 结果

`tools/xdev.py` 从 2252 行降到 235 行，减少 2017 行（89.6%）。统一 CLI 命令保持，具体实现形成以下单一所有者：

| 关注点 | 所有者 | 行数 |
|---|---|---:|
| CLI 参数、发现、分流 | `tools/xdev.py` | 235 |
| 当前 package 识别与校验 | `tools/validator.py` | 371 |
| QA issue ledger 与可恢复事务 | `tools/flag.py` | 547 |
| req3 task | `tools/req3.py` | 720 |
| spec3 文档 | `tools/spec.py` | 984 |
| req3 verify | `tools/verify.py` | 293 |

## 删除

- `xdev.py` 的 V8-V12 旧 task 校验。
- `dev-pipeline/tasks/` 的旧 README/checklist 识别、status、graph、scaffold、instructions。
- 无调用的 `has_spec3_marker` 兼容包装。
- `SCENARIO_PROFILES["task"]` 和旧 task 专属常量/解析器。
- `test/test_xdev_artifacts.py`、`test/test_xdev_orchestration.py`。
- `tools/req.py`、spec2/req2 路由、校验规则、verify 分支、测试与夹具。

历史 `dev-pipeline/tasks/` 目录及文档保持原样。

## 新增与迁移

- `tools/validator.py`：从 xdev 迁移 package validator。
- `tools/flag.py`：从 xdev 迁移 flag 事务引擎。
- `tools/req3.py`：内聚 req3 checklist、Scenario 覆盖、状态、进度和依赖拓扑。
- `tools/spec.py`：自持 issue 与模块名归一化工具，解除 task 引擎循环依赖。
- `test/test_xdev_router.py`：400 行预算、单一所有权、req3 instructions、spec2/旧路径拒绝。
- benchmark executor tools：6 个运行工具，bundle 总计 7 个工具。

## 验证证据

| 命令 | 结果 |
|---|---|
| `python3 -m unittest discover -s test` | 104 项通过 |
| `python3 -m unittest discover -s skills/x-pipeline-efficiency-workspace/iteration-7/tests` | 48 项通过 |
| `python3 -m unittest skills.pipeline-efficiency-benchmark.tests.test_pipeline_efficiency_benchmark` | 4 项通过 |
| `openspec validate --all --strict` | 12 项通过 |
| `git diff --check` | 通过 |

## 兼容与破坏

- 保持：validate、instructions、scaffold、status、graph、verify、flag 命令名；当前 req3 路径；JSON 顶层字段；退出码 0/1/2。
- BREAKING：`dev-pipeline/tasks/*` 的运行时工具支持退役。显式 status/graph/instructions/scaffold 返回退出码 2；validate 将其视为 unknown，且不会执行 V8-V12。
- BREAKING：spec2 包返回 `unsupported-spec2`，req2 task 命令返回退出码 2。
