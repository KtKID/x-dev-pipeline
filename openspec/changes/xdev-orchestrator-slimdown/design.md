## Context

改造前 `tools/xdev.py` 有 2252 行。spec3 已由 `spec.py` 实现，task 曾由两个脚本分别实现，verify 已由 `verify.py` 实现；`xdev.py` 仍保存约 580 行旧 task 兼容、约 500 行 flag 事务、约 900 行包校验与解析器。现有决策已将 `dev-pipeline/tasks/` 定义为死档案，并把删除旧 V8-V12 路径列为待办。

约束：

- 公开命令继续使用 `python3 tools/xdev.py <command>`。
- 当前 spec3/spec7/change 校验结果和规则编号保持。
- 当前 `docs/spec/*/tasks/*` 的 req3 命令保持。
- Python 只使用标准库。
- benchmark 隔离 workspace 必须带齐所有 import 依赖。
- 共享 dirty tree 中的任务外改动保持原样。

## Goals / Non-Goals

**Goals:**

- 将 `xdev.py` 控制在 400 行以内，职责只包含 CLI 参数、发现和分流。
- 每类业务逻辑形成单一模块所有者。
- 删除已决退役的旧 task 运行时与专属测试。
- 用回归测试证明当前 CLI 的 JSON、退出码和分流结果保持。

**Non-Goals:**

- 重写 spec3、req3 或 verify 的文档契约。
- 合并各引擎内部少量 Markdown 解析重复。
- 删除 `dev-pipeline/tasks/` 历史文档。
- 归档其他 active OpenSpec change。

## Decisions

1. **包校验统一进入 `validator.py`**
   - `validator.py` 接管 package 类型识别、V1-V7、V13-V20、spec 级 task 覆盖与 `validate_pkg`。
   - `xdev.py` 只判断 task 路径后转发统一 `req3.py`，其余目标转发 `validator.py`。
   - 选择依据：这些规则共享 Markdown 包解析器和 CHECKS 注册表，整体迁移能避免拆成多个互相依赖的小模块。
   - 备选：只拆 `spec2.py`。该方案仍会让 xdev 保留通用 parser、legacy/change/spec7 分支，瘦身幅度有限。

2. **QA issue 事务进入 `flag.py`**
   - `flag.py` 独立拥有输入校验、checklist 目标行定位、ledger 编号、双文件事务与崩溃恢复。
   - `flag.py` 保留解析目标行所需的最小表格逻辑，避免依赖 validator。
   - 选择依据：flag 是一个有独立状态机和故障恢复语义的写入子域，约 500 行，适合形成单一所有者。
   - 备选：移动到 req3.py。flag 的写入事务与 task 规划解析职责不同。

3. **旧 task 支持直接删除**
   - 删除 V8-V12、旧 README 产物注册表、旧 status/graph 解析与 `test_xdev_artifacts.py` / `test_xdev_orchestration.py`。
   - 历史任务目录继续留在 git 中供查阅。
   - 选择依据：`xreq-spec-driven` 已明确单轨和 BREAKING 退役；继续保留会让旧测试反向固定已废弃行为。
   - 备选：移动到 `legacy_task.py`。该方案降低 xdev 行数，同时继续产生永久兼容成本。

4. **当前 task instructions 归 req3 引擎**
   - `req3.py` 保存 req3 ARTIFACTS、Scenario 解析、校验、状态与依赖图能力。
   - xdev 和 verify 只依赖 `req3.py`；`spec.py` 自持 issue 与模块名归一化小工具，解除循环 import。
   - 选择依据：task 的 scaffold、validate、instructions、status、graph 使用一个入口，分发包只需携带一个 task 引擎。

5. **spec2 与 req2 直接退役**
   - task 命令只接受父 spec 含 `spec_version: 3` 的目录。
   - 删除 `req.py`、spec2 task 路由、spec2 task 覆盖校验和对应测试。
   - 选择依据：当前流水线以 spec3 为唯一方案契约，旧 profile 会持续扩大脚本和分发面。

6. **兼容面限定为 CLI**
   - 测试和仓库代码改为直接 import 对应引擎，停止把 `xdev.py` 内部函数当公共 Python API。
   - `xdev.main()`、命令名、JSON 顶层字段和退出码保持。
   - 选择依据：当前生产调用全部是 CLI；直接函数引用只存在于测试。

7. **bundled runtime 使用显式清单**
   - benchmark manifest 和复制清单加入 `validator.py`、`flag.py`，只分发 `req3.py`。
   - 预检继续逐个 import，防止隔离 workspace 遗漏新依赖。

## Risks / Trade-offs

- [风险] 移动大量代码时产生漏 import 或调用名漂移 → 先做纯移动和所有权测试，再跑全量 unittest 与隔离 workspace 预检。
- [风险] 删除旧测试降低历史行为覆盖 → 以“旧路径明确失败”的 CLI 测试替代，固化退役契约。
- [风险] active `xreq-spec-driven` 与本变更都触及旧 task 退役 → 本变更只落实其已决代码清理，并在 delta 中引用同一目标行为。
- [风险] `flag.py` 自带少量表格解析 → 仅保留定位 ID/状态列所需逻辑，当前 req parser 继续拥有 status/graph。

## Migration Plan

1. 新增 `validator.py` 和 `flag.py`，先保持现有当前路径行为。
2. 重写 `xdev.py` 为薄路由器，增加模块所有权测试。
3. 将 instructions 切换到 task 引擎委托。
4. 删除旧 task 实现和专属测试，增加旧路径拒绝测试。
5. 同步 bundled runtime，运行定向与全量测试。
6. strict validate 本 OpenSpec change，记录前后行数和命令证据。
7. 让 `req3.py` 自包含通用 task 工具，删除 `req.py`、spec2/req2 路由、测试和分发条目。

回滚时恢复原 `xdev.py` 与两份旧测试，并移除新模块；历史 task 数据从未移动，回滚不涉及数据恢复。

## Open Questions

无。旧 task 退役、统一 CLI、当前引擎单一所有权均已有仓库决策或用户本次授权。
