# verify-module-extraction

> 创建时间：2026-07-20
> 类型：重构
> 风险等级：Q2
> 审查路线：综合 reviewer

## 用户原始请求

> verify相关的都搬到tools/verify.py脚本

## 任务说明

把旧 task 与 req2 task 的 verify 解析、执行、验收对账和路径分流集中到
`tools/verify.py`。`tools/xdev.py` 保留统一 CLI，`tools/req.py` 保留 req2
task/spec 的非 verify 领域能力；现有命令输出、退出码和覆盖范围保持稳定。

## 明示假设

| 编号 | 假设 | 依据 | 影响 |
|------|------|------|------|
| A1 | `tools/verify.py` 同时承接旧路径和 req2 路径 | 用户要求“verify 相关的都搬到”且当前实现分别位于 `xdev.py`、`req.py` | 若只迁旧路径，重复实现继续存在 |
| A2 | `python3 tools/xdev.py verify ...` 继续作为公开入口 | `skills/x-verify/SKILL.md` 与现有测试均从该 CLI 调用 | 内部 Python 调用方需改为导入 `verify.py` |

## 涉及模块

- `tools/xdev.py` — CLI 入口和旧 verify 实现所在地
- `tools/req.py` — req2 verify 实现所在地
- `tools/verify.py` — 新的统一 verify owner
- `test/test_xdev_verify.py`、`test/test_req_engine.py` — 旧、新路径回归契约

## DoD 与证据

| 编号 | DoD | 来源 | 证据计划 | 最终证据 | 状态 |
|------|-----|------|----------|----------|------|
| D1 | verify 专属常量和函数集中在 `tools/verify.py` | 用户原始请求 | `rg` 检查定义位置 | 12 个 verify 专属函数定义只命中 `tools/verify.py`；owner 回归测试通过 | ✅ |
| D2 | `xdev.py verify` 对旧路径和 req2 路径保持现有行为 | 公开 CLI 与既有测试 | 运行 verify/req 定向测试 | 67 个定向测试通过，覆盖 pass/fail/exit 2、manual、timeout、`--only`、uncovered、req2 scope 与 legacy 标记兼容 | ✅ |
| D3 | 当前工作树中 `tools/req.py` 的 Requirement/None 契约改动完整保留 | 任务起点基线 | 对照迁移前 diff 与迁移后测试 | None、空列、悬空 Requirement 回归用例随 67/166 个测试通过 | ✅ |
| D4 | 全量标准库测试通过 | 仓库验证契约 | `python3 -m unittest discover -s test` | 166 个测试通过 | ✅ |

## 风险判断

- 风险等级：Q2
- 触发因素：迁移验证核心函数、同时覆盖新旧路径、错误分支较多、工作区存在重叠改动
- 升级条件：出现公开输出或退出码变更、无法保持现有测试、需要改变 verify block schema

## 任务起点基线

- `git status --short`：25 个 tracked 文件已有修改，另有 `.claude/`、两个既有 task/report 目录和 x-spec2 eval 文件未跟踪
- 起点 changed paths：包含 `tools/req.py`、`test/test_req_engine.py`、`skills/x-verify/*` 与两组 OpenSpec change
- 起点 untracked paths：`.claude/`、`dev-pipeline/tasks/fixes-and-metrics/`、`dev-pipeline/tasks/progress-engine/reports/`、`skills/x-spec2/evals/*`
- 与预期任务文件重叠：`tools/req.py`、`test/test_req_engine.py`
- 重叠文件初始 diff 摘要或 hash：`tools/req.py` 已收紧 Requirement 空值为 `None` 并增加悬空检查；`test/test_req_engine.py` 已增加对应回归用例
- 用户既有改动保护策略：从当前工作树内容搬迁完整函数体；不回退现有 diff；迁移后运行相关新增测试

## 开发清单

| 编号 | 优先级 | 状态 | 任务 | 备注 |
|------|--------|------|------|------|
| #1 | P0 | ✅ 已完成 | 新增统一 verify 模块并迁移共享执行逻辑 | D1 |
| #2 | P0 | ✅ 已完成 | 接入 xdev CLI 并移除 xdev/req 中的 verify 定义 | D1、D2 |
| #3 | P1 | ✅ 已完成 | 更新直接导入内部函数的测试 | D2、D3 |
| #4 | P1 | ✅ 已完成 | 定向与全量验证、综合 reviewer | reviewer 最终 PASS，P0/P1 none |

## 预期涉及文件

- `tools/verify.py` — 新增统一实现
- `tools/xdev.py` — 删除旧实现并转发 CLI
- `tools/req.py` — 删除 req2 verify 实现
- `test/test_req_engine.py` — 更新内部 owner 引用
- `dev-pipeline/tasks/verify-module-extraction/*` — qdev 证据

## 实际涉及文件

- `tools/verify.py` — 统一新旧 verify 实现与路径分流
- `tools/xdev.py` — 删除旧 verify 实现，CLI 委托 verify 模块
- `tools/req.py` — 删除 req2 verify 实现，保留 checklist/spec 通用解析
- `test/test_xdev_verify.py` — 增加单一 owner 回归测试
- `test/test_req_engine.py` — 直接内部调用改指 `verify.py`
- `README.md` — 说明统一 CLI 与 verify owner
- `openspec/changes/xdev-task-scoped-verify/{proposal.md,design.md,tasks.md}` — 更新 verify owner
- `openspec/changes/xreq-spec-driven/{proposal.md,design.md,tasks.md}` — 更新引擎边界
- `dev-pipeline/tasks/verify-module-extraction/*` — qdev 任务证据
