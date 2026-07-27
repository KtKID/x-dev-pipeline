# spec3-validator-rewrite

> 创建时间：2026-07-25
> 类型：重构
> 风险等级：Q2
> 审查路线：综合 reviewer

## 用户原始请求

> 新增spec.py，把当前skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-spec3 的需要检验的功能放进去，就是把xdev.py里spec部分改造成当前spec3的版本，理解我意思吗，我倾向根据最新版本重新脚本

## 任务说明

从 iteration-7 当前 `x-spec3` 契约重新设计 `tools/spec.py`，集中实现 spec3 的机械校验。`tools/xdev.py` 保持统一 CLI 入口并委托新引擎，`tools/req3.py` 保留 task 拆解、Scenario 覆盖和状态管理职责。

## 明示假设

| 编号 | 假设 | 依据 | 影响 |
|------|------|------|------|
| A1 | `tools/spec.py` 只承接 iteration-7 当前 spec3 契约 | 用户要求根据最新版本重新脚本 | 老 spec2/spec7 继续留在 `xdev.py` 的既有兼容路径 |
| A2 | V19/V20 规则编号继续作为 `xdev.py` 与测试的兼容输出 | 现有 CLI、测试和报告使用该编号 | 调用方无需同步迁移错误码 |
| A3 | `pending` 表示文档结构可解析，同时阻断 x-req3 交接 | iteration-7 x-spec3 与 risk contract 的交接语义 | deep/full 初稿需完成对抗审查后才能通过就绪门禁 |
| A4 | spec3 文档契约进入 `spec.py`，task 覆盖关系继续由 `req3.py` 负责 | 两者输入边界分别为 spec.md 与 tasks/* | 避免 spec 引擎反向依赖 task 引擎 |

## 涉及模块

- `tools/spec.py` — iteration-7 spec3 的单一机械校验引擎。
- `tools/xdev.py` — 包识别和统一 validate CLI 委托入口。
- `tools/req3.py` — task 引擎通过兼容包装复用 spec3 解析与门禁。
- `test/` — spec3 成功路径、元数据、表格、Scenario、审查记录失败路径。
- `skills/pipeline-efficiency-benchmark/` — bundled runtime 增加 `spec.py`。

## DoD 与证据

| 编号 | DoD | 来源 | 证据计划 | 最终证据 | 状态 |
|------|-----|------|----------|----------|------|
| D1 | 新增 `tools/spec.py`，覆盖 iteration-7 当前元数据、预算、章节、表格、Scenario 来源和对抗审查契约 | 用户原始请求、当前 x-spec3 | 新引擎单元测试 | `test/test_spec_engine.py` 覆盖 RAG/no-corpus/召回失败、fence、占位符、sidecar 与交叉矛盾；相关定向 38 项通过 | ✅ |
| D2 | `xdev.py` 与 `req3.py` 委托新引擎，spec3 文档校验实现只保留一份 | 用户原始请求、调用边界 | scoped diff、委托测试 | `xdev.py` 直接委托 `spec.validate_issues`；`req3.py` 只保留兼容包装，综合 reviewer 确认单一实现 | ✅ |
| D3 | 正向与关键失败路径均有自动化证据 | Q2 验证要求 | unittest 定向与全量相关测试 | 仓库 226 项、iteration-7 48 项全部通过；综合 reviewer P0/P1/P2 为 0 | ✅ |
| D4 | benchmark bundled tools 包含 `spec.py` 且 workspace preflight 通过 | runtime 下游消费者 | bundle 测试和 preflight | bundle 6 个工具刷新；benchmark 4 项通过；spec/xdev/req3 source 与 bundled 逐字节一致 | ✅ |

## 风险判断

- 风险等级：Q2
- 触发因素：核心 validator 重写、多个失败路径、`xdev.py`/`req3.py`/bundled runtime 三个调用面。
- 升级条件：需要改变公开 CLI schema、V19/V20 编号或 task checklist 协议时升级完整流程。

## 任务起点基线

- `git status --short`：共享工作区存在大量用户既有修改和未跟踪运行产物。
- 起点 changed paths：`tools/req3.py`、`test/test_req3_engine.py` 与 iteration-7 x-spec3 文件已有修改；`tools/xdev.py` clean。
- 起点 untracked paths：包含 `reports/`、iteration/eval 运行目录及多个任务产物。
- 与预期任务文件重叠：`tools/req3.py`、`test/test_req3_engine.py`。
- 重叠文件初始 diff 摘要或 hash：
  - `tools/req3.py`：`93fbc21b3e757679056d4003c6dd37bde63cd945`
  - `test/test_req3_engine.py`：`88dbbeb12c309acef7a6257c527d2704db76d08c`
  - `tools/xdev.py`：`87aec4ee97db2f3e13ce005b0b6c28f6d22b19eb`
- 用户既有改动保护策略：对重叠文件只做局部委托改造；新测试独立写入 `test/test_spec_engine.py`；其余 dirty paths 保持原样。

## 开发清单

| 编号 | 优先级 | 状态 | 任务 | 备注 |
|------|--------|------|------|------|
| #1 | P0 | ✅ 已完成 | 从当前 iteration-7 契约实现 `tools/spec.py` | 对应 D1 |
| #2 | P0 | ✅ 已完成 | 改造 xdev/req3 委托关系 | 对应 D2 |
| #3 | P1 | ✅ 已完成 | 补充正向和关键失败路径测试 | 对应 D3 |
| #4 | P1 | ✅ 已完成 | 同步 bundled tools 并执行验证 | 对应 D4 |
| #5 | P1 | ✅ 已完成 | 执行 Q2 综合 reviewer 并收口报告 | 对应 D1-D4 |

## 预期涉及文件

- `tools/spec.py`
- `tools/xdev.py`
- `tools/req3.py`
- `test/test_spec_engine.py`
- `skills/pipeline-efficiency-benchmark/SKILL.md`
- `skills/pipeline-efficiency-benchmark/scripts/benchmark_common.py`
- `skills/pipeline-efficiency-benchmark/tests/test_pipeline_efficiency_benchmark.py`
- `skills/pipeline-efficiency-benchmark/assets/tools/`
- `dev-pipeline/tasks/spec3-validator-rewrite/`

## 实际涉及文件

- `tools/spec.py` — 新增 iteration-7 spec3 独立校验引擎和 standalone CLI。
- `tools/xdev.py` — spec3 识别与校验委托 `spec.py`，删除旧 sidecar 特判。
- `tools/req3.py` — 删除重复 spec3 文档解析/校验，仅保留 task 逻辑和兼容包装。
- `test/test_spec_engine.py` — 新增当前契约的成功、失败和交叉矛盾测试。
- `test/test_req3_engine.py` — 将共享 spec fixture 升级到当前七行元数据、审查记录和来源格式。
- `skills/pipeline-efficiency-benchmark/SKILL.md`、`scripts/benchmark_common.py`、`tests/test_pipeline_efficiency_benchmark.py` — bundled 工具数量和清单同步。
- `skills/pipeline-efficiency-benchmark/assets/executor-tools/{spec.py,xdev.py,req3.py,manifest.json}` — 隔离 workspace runtime 快照。
- `dev-pipeline/tasks/spec3-validator-rewrite/` — Q2 基线、变更记录与证据报告。
