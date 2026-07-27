# Correctness Review 报告

> Report ID: 20260725-112322
> Mode: module-review
> Scope: file + current workflow contract
> Task ID: N/A
> Review 日期：2026-07-25
> 审查范围：`tools/xdev.py` 及其 `req.py` / `req3.py` / `verify.py` 委托链、当前 x-spec3/x-req3 契约、旧 task 兼容分支

## 调查对象

| 字段 | 内容 |
|------|------|
| 模式 | 模块正确性 review |
| 用户现象 | 用户要求确认最新 `xspec.py` 的功能与新优化后应删除的老功能 |
| 期望行为 | 当前主流程使用 x-spec3 → x-adversarial-risk → x-req3；`xdev.py` 作为统一 CLI 与 spec 校验编排层，task 子域委托 `req.py` / `req3.py`，verify 委托 `verify.py` |
| 实际行为 | 仓库中对应实现文件为 `tools/xdev.py`；文件仍保留旧 README task 的 instructions、V8-V12、status/graph 解析与 fallback |
| 原始 spec 来源 | `CLAUDE.md:31-60`、`openspec/changes/xreq-spec-driven/design.md:12-61`、`openspec/changes/xreq-spec-driven/tasks.md:22-28`、`skills/x-req3/SKILL.md:11-29` |

## 修改文件 / 审查范围

| 文件 | 角色 | 语言 | 说明 |
|------|------|------|------|
| `tools/xdev.py` | implementation | Python | 统一 CLI、spec/change 校验、flag 事务、旧 task fallback |
| `tools/req.py` | implementation | Python | spec2 task scaffold/validate/status/graph |
| `tools/req3.py` | implementation | Python | spec3 与 Scenario-ID task 契约 |
| `tools/verify.py` | implementation | Python | verify 复跑与场景证据对账 |
| `openspec/changes/xreq-spec-driven/` | spec | Markdown | task 单轨化与旧实现删除决策 |
| `test/test_xdev_artifacts.py` | test | Python | 旧 instructions 与 V8-V12 测试 |
| `test/test_xdev_orchestration.py` | test | Python | 旧 status/graph 引擎测试 |

---

## 当前脚本功能总览

| 功能 | 入口 / 位置 | 当前职责 | 判断 |
|------|-------------|----------|------|
| 包发现与类型识别 | `discover`、`detect_type` | 识别 spec7、spec2、spec3、OpenSpec change/capability、legacy 图集 | 保留；删除旧 `task` 分类 |
| 通用结构校验 | `CHECKS` | 文件齐全、链接、Requirement/Scenario、delta、状态与追溯规则 | 保留；修正 REMOVED 段误报 |
| spec2 校验 | V13-V18 | 2+1 文件、六元组、U/J/D、Requirement↔模块、design 触发 | 保留；x-req3 明确 spec2 继续由 x-req2 消费 |
| spec3 校验 | V19-V20 → `req3.spec3_contract_issues` | 单文件固定章节、J-ID 就绪、边界表、连续 Scenario ID、GWT/测试层/依据 | 保留 |
| spec 级 task 覆盖 | `req.spec_requirement_coverage` / `req3.spec_scenario_coverage` | spec2 Requirement 覆盖、spec3 Scenario 覆盖 | 保留 |
| scaffold | CLI → `req.scaffold` / `req3.scaffold` | 生成当前 checklist 与按需 diagram | 保留 |
| status / graph | CLI → `req` / `req3` | 当前 task 状态、依赖拓扑、ready、parallel batches | 保留公开命令；删除 xdev 内旧实现 |
| verify | CLI → `verify.verify` | 复跑 dev-report 命令并对账 task 范围内 Scenario | 保留 |
| flag | `flag_command` | 生成 QA issue ledger、P0/P1 状态降级、双文件事务恢复 | 保留；当前 x-qa-gate 仍直接调用 |
| instructions | req3 委托 + xdev 旧 fallback | req3 返回当前模板；spec2/其他路径返回已归档 README 结构 | 修复路由并删除旧 fallback |
| 旧 task 校验 | V8-V12 / `TASK_CHECKS` | 校验 `dev-pipeline/tasks/<task>/README.md + dev-checklist.md` | 删除 |
| 旧 status/graph 引擎 | `parse_checklist` 至 `graph_command` | 解析旧 task 表头并计算进度/拓扑 | 删除 |

## 贝叶斯根因调查

| H | 先验 | 证据 E | 影响 | 更新后置信度 | 下一步 |
|---|------|--------|------|--------------|--------|
| H1：旧 task 执行层在新单轨设计后仍可达 | 高 | `xdev.py:30-40` 自注释“废弃待删除”；`design.md:46-48` 决策历史 task 只作死档案；main 仍在 `xdev.py:2190,2224-2226` 进入旧 fallback | 支持 | 已确认 | 删除旧 fallback、旧规则和旧测试 |
| H2：旧 instructions 会向当前 spec2 task返回错误模板 | 中 | 实测 `instructions readme` 返回 `deprecated/x-req/templates/README.md`；`instructions dev-checklist` 返回旧六列表头并声明依赖 README；当前 req2/req3 均只生成 checklist + diagram | 支持 | 已确认 | 给 req2 增加当前 profile instructions，xdev 仅做版本分流 |
| H3：spec2/spec7 校验层均可随 spec3 一起删除 | 中 | `skills/x-req3/SKILL.md:4` 明确 spec2 继续使用 x-req2；`xspec-v2/design.md:14-20` 要求历史 spec 数据兼容 | 削弱 | 低 | 保留 spec2；spec7 作为历史数据校验层保留 |
| H4：flag 属于旧 task 残留 | 中 | `CLAUDE.md:60` 与 `skills/x-qa-gate/SKILL.md` 仍把 `xdev.py flag` 定义为 issue/state 唯一写入口；其表头定位支持当前列 | 削弱 | 低 | 保留 flag，复用 `req.ID_COL_RE` 与 `req.task_engine_status` |
| H5：change 的 REMOVED Requirement 会被通用 V3 误判 | 高 | `check_req_scenario` 对 change 全部 Markdown 使用 legacy profile；实测当前 `xreq-spec-driven` 被误报 2 个缺 Scenario，`openspec validate --strict` 同包通过 | 支持 | 已确认 | 跳过 `## REMOVED Requirements` 段 |

### 已排除假设

| H | 排除证据 |
|---|----------|
| spec2 已无消费者 | x-req3 skill 明确把 spec2 路由给 x-req2；`tools/req.py`、对应 fixtures 与 80+ 测试仍构成活跃链路 |
| flag 只服务旧 README task | flag 只定位 checklist 的 ID/状态列，当前 x-qa-gate 和新 checklist 都在使用 |
| 全量测试可证明旧分支适用 | 207 个标准库测试通过；其中约 672 行测试专门固化旧 V8-V12 与旧 status/graph，因此绿灯同时反映兼容实现仍存在 |

---

## Spec 对照

| 项 | 原始 spec / 契约 | 当前实现 / 行为 | 分类 | 证据 |
|----|------------------|----------------|------|------|
| task 单轨 | task 只认 `docs/spec/*/tasks/`；历史 `dev-pipeline/tasks/` 为死档案 | `detect_type`、`TASK_CHECKS`、status/graph fallback 继续支持旧目录 | 实现过程偏移 | `design.md:18-24,46-48`；`xdev.py:515-524,1213-1231,2214-2226` |
| task 产物 | 当前 req2/req3 产出 checklist + 按需 diagram | xdev fallback 暴露 README 和旧 checklist 模板 | 原始 spec 不一致 | `req.py:33-42`、`req3.py:22-33`；`xdev.py:136-160,441-496` |
| change REMOVED 语义 | OpenSpec REMOVED Requirement 只需 Reason/Migration，可省略 Scenario | V3 报 Requirement 没有 Scenario | 实现过程偏移 | `tasks.md:27`；实测 xdev 2 issues、OpenSpec strict 通过 |
| spec2 历史与存量支持 | spec2 继续走 x-req2 | V13-V18 与 req2 委托仍可用 | 符合 spec | `skills/x-req3/SKILL.md:4`、`xdev.py:542-1000,2132-2139` |
| QA issue 写入 | flag 是当前 ledger 与状态写入口 | 新旧 checklist 均可定位 ID/状态列 | 符合 spec | `CLAUDE.md:60`、`xdev.py:1308-1762` |

---

## 审查结论

### P0：已确认正确性错误

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ✅ | 代码路径 | 数据破坏 / 核心路径 | - | 高 | 符合 spec | 本次未发现 P0 |

### P1：生产正确性风险

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ⚠️ | 契约 + 复现 | 旧 task fallback | `tools/xdev.py:128` | 已确认 | 实现过程偏移 | 当前 spec2 task 的 instructions 返回 README 与旧表头，生成物会偏离 req2/req3 契约 |
| ⚠️ | 契约 + 复现 | REMOVED Requirement | `tools/xdev.py:625` | 已确认 | 实现过程偏移 | 合法 OpenSpec change 被 V3 误报，当前 xreq-spec-driven 产生 2 个假 issue |

### P2：正确性证据缺口

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ⚠️ | spec 状态 | 主 spec 与当前 change 同步 | `openspec/specs/xdev-task-artifact-engine/spec.md:6` | 高 | spec 缺口 | 主 spec 仍声明 README、V8-V12；删除动作需随 xreq-spec-driven 完成 delta 合并与归档 |

---

## 问题详情

### B1: 旧 task 执行层仍可达并向当前 task 返回旧模板

**来源**: 代码路径 + 当前设计 + 命令复现
**文件**: `tools/xdev.py`
**位置**: 第 128-160、441-496、1003-1258、1765-2084、2187-2190、2214-2226 行
**严重程度**: P1
**根因分类**: 实现过程偏移
**置信度**: 已确认

**问题描述**：
当前设计已经把 task 引擎分离到 `req.py` / `req3.py`，并把历史 `dev-pipeline/tasks/` 定义为只读死档案。`xdev.py` 仍保留三组旧实现：

1. README + 旧 checklist + diagram 的 ARTIFACTS 与 instructions fallback。
2. V8-V12 README task 校验与 `TASK_CHECKS`。
3. 旧 checklist 解析、status、graph 及 main fallback。

实测对 spec2 task 请求 `instructions readme` 返回旧 README；请求 `dev-checklist` 返回 `# | 任务 | 涉及文件 | 依赖 | 状态 | fix`，并声明 README 依赖。当前 req2 使用 Requirement/风险列，req3 使用 Scenario IDs/风险列。

**反证检查**：

- spec2 的 validate/scaffold/status/graph 当前委托 `req.py`，应保留这些公开命令。
- spec3 当前委托 `req3.py`，应保留 V19/V20、Scenario coverage 与 req3 instructions。
- flag 仍是当前 QA Gate 写入口，应保留事务逻辑；状态解析可改为复用 `req` 的常量与函数。
- 三个曾被列为暂缓原因的历史 task 已具备收尾证据：`xdev-orchestration-engine` 全部完成，`qa-gate-pipeline` 全部完成，`xspec-contract-upgrade` 明确关闭转型。

**影响**：
调用方会拿到与当前 task schema 冲突的模板；维护者还需同时修改 xdev、req、req3 三套 task 逻辑；旧测试会把废弃行为持续固化为“绿灯”。

**验证方式**：

```bash
python3 tools/xdev.py instructions readme \
  --task test/fixtures/req2/docs/spec/demo/tasks/ok-task --json
python3 tools/xdev.py instructions dev-checklist \
  --task test/fixtures/req2/docs/spec/demo/tasks/ok-task --json
```

**修复建议**：

1. 保留 `instructions` CLI；由 `req.instructions` / `req3.instructions` 返回各自当前模板。
2. 删除 xdev 内旧 `ARTIFACTS`、旧 instructions helpers、V8-V12、`TASK_CHECKS`、旧 task 检测和旧 status/graph fallback。
3. flag 改用 `req.ID_COL_RE`、`req.task_engine_status`、`req.BLOCKED`，避免为 flag 保留整套旧引擎。
4. 删除或迁移 `test/test_xdev_orchestration.py` 与 `test/test_xdev_artifacts.py` 的旧契约测试；当前 status/graph 覆盖集中到 `test/test_req_engine.py` / `test/test_req3_engine.py`。
5. 清理无运行时消费者的 `deprecated/x-req/` 模板，并通过 Git 历史保留追溯。
6. 运行 benchmark bundled-tools 刷新脚本，同步 `assets/executor-tools/xdev.py` 与 manifest。

### B2: OpenSpec REMOVED Requirement 被 V3 当作活跃验收契约

**来源**: spec 对照 + 命令复现
**文件**: `tools/xdev.py`
**位置**: 第 625-634 行
**严重程度**: P1
**根因分类**: 实现过程偏移
**置信度**: 已确认

**问题描述**：
`check_req_scenario` 对 change 下全部 Markdown 逐行运行 legacy Scenario 契约。REMOVED 段中的 Requirement 只记录删除原因时，`scenario_contract_issues` 仍要求 Scenario，产生假 issue。

**反证检查**：

- `openspec validate xreq-spec-driven --strict` 通过。
- `python3 tools/xdev.py validate openspec/changes/xreq-spec-driven --json` 报 2 个 V3 issue。
- `openspec/changes/xreq-spec-driven/tasks.md:27` 已登记同一缺陷，当前状态未完成。

**影响**：
合法 change 无法通过 xdev 零 issue 门禁，维护者可能向 REMOVED 段补无意义 Scenario，增加噪音并偏离 OpenSpec 语义。

**验证方式**：

```bash
openspec validate xreq-spec-driven --strict
python3 tools/xdev.py validate openspec/changes/xreq-spec-driven --json
```

**修复建议**：
让 change profile 在 `## REMOVED Requirements` 区间跳过 Requirement/Scenario 完整性检查；ADDED 与 MODIFIED 继续执行 legacy GWT 契约。增加一个 REMOVED 无 Scenario 的正向回归测试。

### B3: 主 spec 与新 task 单轨设计处于过渡冲突

**来源**: spec 对照
**文件**: `openspec/specs/xdev-task-artifact-engine/spec.md`
**位置**: 第 6-20、42-175 行
**严重程度**: P2
**根因分类**: spec 缺口
**置信度**: 高

**问题描述**：
主 spec 仍声明 README 注册表、README scaffold、V8-V12 与旧表头。未归档的 `xreq-spec-driven` delta 已删除 README 契约并定义新 task 单轨，相关 tasks 的 1.2.1、1.2.4、2.x、3.x 仍待完成。

**影响**：
直接删除代码会让主 spec 与实现继续分离；持续保留代码会让当前主流程承担双轨税。

**修复建议**：
把清理作为 `xreq-spec-driven` 的收尾批次：先补 REMOVED 过滤与当前 instructions profile，再删除旧层、更新 README/CLAUDE、刷新 bundled tools，最后运行 OpenSpec strict 与全量 unittest 后归档 change。

---

## 建议删除清单

| 删除批次 | 内容 | 关联位置 |
|----------|------|----------|
| A | 旧 task artifact 注册表、README/旧 checklist instructions 常量与 helpers | `xdev.py:128-160,441-496` |
| B | V8-V12 与 task-only helpers、`TASK_CHECKS` | `xdev.py:1003-1221` |
| C | 旧 task `detect_type` 分支 | `xdev.py:521-524` |
| D | xdev 内旧 checklist/status/graph 引擎及 main fallback | `xdev.py:1224-1258,1765-2084,2224-2226` |
| E | 旧契约测试；保留并扩充 req2/req3 测试 | `test/test_xdev_orchestration.py`、`test/test_xdev_artifacts.py` |
| F | 失去运行时消费者的旧模板与文档引用 | `deprecated/x-req/`、README/CLAUDE、主 OpenSpec |
| G | benchmark 运行工具副本 | `skills/pipeline-efficiency-benchmark/assets/executor-tools/xdev.py` + manifest |

预计可从 `tools/xdev.py` 移除约 650 行旧 task 代码；公开 CLI 继续保留 validate、instructions、scaffold、status、graph、verify、flag，task 行为统一委托当前 profile 引擎。

## 建议保留清单

| 内容 | 原因 |
|------|------|
| spec2 V13-V18 | x-req3 明确 spec2 继续走 x-req2 |
| spec7 / capability / change 历史校验 | 历史包与 OpenSpec 数据兼容仍有消费者 |
| spec3 V19-V20 | 当前主流程机械门禁 |
| req2/req3 task coverage | 防 Requirement/Scenario 漏承接 |
| verify 委托 | 当前 Gate ① |
| flag 事务 | 当前 QA Gate ledger 与状态唯一写入口 |
| CLI 外壳与 JSON/退出码 | 当前所有 skill 的稳定调用面 |

## 汇总

| 等级 | 数量 |
|------|------|
| P0 | 0 |
| P1 | 2 |
| P2 | 1 |

## 最终结论

- 当前主流程已经完成 spec3/req3 单文件与 Scenario-ID 优化。
- 旧 task 执行层具备完整删除条件；历史 task 文件继续作为档案保留。
- 删除目标集中在 README task、V8-V12、旧 status/graph fallback 与旧模板测试。
- spec2/spec7 校验属于数据兼容层，继续保留。
- REMOVED Requirement 误报应与旧层清理同批修复。
- 推荐以 `xreq-spec-driven` 收尾批次执行清理，完成 OpenSpec 主契约更新后归档。

## 验证记录

| 命令 | 结果 |
|------|------|
| `python3 -m unittest discover -s test -p 'test_*.py' -q` | 207 tests，OK |
| `openspec validate xreq-spec-driven --strict` | valid |
| `python3 tools/xdev.py validate openspec/changes/xreq-spec-driven --json` | 2 个假 V3 issue |
| `python3 tools/xdev.py validate test/fixtures/req2/docs/spec/demo/tasks/ok-task --json` | 0 issue |
| `cmp tools/xdev.py assets/executor-tools/xdev.py` | 当前副本一致 |

## 修复备注（x-fix 回写）

> 仅在修复后由 x-fix 追加到同一份 CR 主档。

| # | 严重程度 | 文件 | 处置结果 | 修复方式 | 备注 |
|---|----------|------|----------|----------|------|
| B1 | P1 | `tools/xdev.py` | 待处理 | 删除旧 task 层并把当前 profile instructions 委托到 req2/req3 | |
| B2 | P1 | `tools/xdev.py:625` | 待处理 | REMOVED 区间过滤 | |
| B3 | P2 | `openspec/specs/xdev-task-artifact-engine/spec.md` | 待处理 | 完成并归档 xreq-spec-driven | |
