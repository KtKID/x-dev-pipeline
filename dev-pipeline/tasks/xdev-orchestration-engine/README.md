# xdev-orchestration-engine

> 创建时间：2026-07-15
> 类型：功能
> spec: <!-- 本项目无 docs/spec/ 需求包，无归属 spec -->

## 核心目标

给 `tools/xdev.py` 加 `status` 和 `graph` 两个子命令，把 x-dev-pipeline 从「LLM 自己推理调度」升级为「脚本算调度，LLM 照 JSON 执行」。当前编排全靠 LLM 读 `dev-checklist.md` 表格自己推理（依赖靠自然语言、状态靠 emoji、并行批次靠判断），存在状态不可恢复、依赖无强制保证、调度依赖 LLM 记忆的问题。参考 OpenSpec 的引擎设计（文件即状态 + 依赖图拓扑排序），用最小改动补齐编排层。

## 需求要点

1. 新增 `xdev.py status` 子命令：解析任意 task 的 `dev-checklist.md`，输出含 progress 的 JSON。
2. 新增 `xdev.py graph` 子命令：基于依赖列做拓扑排序，输出 ready / blocked / order / parallel_batches。
3. 状态判定走双轨制：机器读 token（`[ ]` / `[x]` / `[!]`），人读 emoji；状态列格式 `| [x] 🟢 |`（token + emoji 双标）。
4. 状态机压缩成 3 态：todo / done / blocked（编排只关心"能不能往下走"，不关心中间态）。
5. 对纯 emoji 旧 checklist（无 token）兼容降级，不报错。
6. 可选产物锚点：task 项备注列写 `product:reports/T1.md`，status 额外交叉验证文件存在性。
7. graph 必须能检测依赖环，发现环报错并列出环节点。
8. 改造 `skills/x-dev/SKILL.md` 并行判断段：派子 agent 前先调 status + graph。
9. 升级 `skills/x-req/templates/dev-checklist.md` 模板支持 token+emoji 双轨格式。

## 涉及模块

> 本项目无 docs/spec/ 需求包文档，直接写涉及的代码文件 + 简述作用。

- `tools/xdev.py`（核心，现有 399 行）：确定性工具层。现有 `validate` 子命令做 spec/change 包结构校验。本 task 新增 `status` 和 `graph` 两个子命令，挂在 `main()` 的 `add_subparsers` 分发器下，复用现有 `first_table` / `col_values` / `cells` / `detect_type` 解析函数。
- `skills/x-dev/SKILL.md`（改造）：当前「并行开发」段（第 112-163 行）依赖 LLM 读备注列和涉及模块段自行判断依赖与并行。改造为派子 agent 前先调 `xdev.py status` + `graph`，按返回 JSON 的 `ready` 派子 agent。
- `skills/x-req/templates/dev-checklist.md`（格式升级）：状态列从纯 emoji 升级为 token+emoji 双轨（`[ ] ⏳`），让 status 子命令有确定性 token 可读。

## 架构拆分策略

### 拆分依据

| 维度 | 结论 |
|------|------|
| 主边界 | `tools/xdev.py` 的子命令分发器（`main()` 的 `add_subparsers`）。xdev.py 自身是确定性工具边界（CLI 子命令），不新增散装函数 |
| 公开契约 | `status <task-dir> --json` / `graph <task-dir> --json` 两个 CLI 入口 + 固定 JSON schema（见技术设计）。退出码：0 正常；1 数据问题（如环）；2 用法/IO 错误（与现有 validate 一致） |
| 数据流 | dev-checklist.md → first_table/col_values 解析 → token 状态判定 + 依赖列拆分 → status JSON / graph Kahn 拓扑排序 → x-dev skill 按 JSON 派子 agent |
| 状态变化 | 只读 dev-checklist.md 和可选产物文件，不写任何状态。状态更新仍由 x-dev 主流程负责（与现有分工一致） |
| 风险层级 | 中。解析逻辑确定性高、无外部副作用；主要风险是旧 emoji checklist 兼容和环检测正确性 |
| 事实源 | dev-checklist.md 的表格是任务/状态/依赖的单一事实源；JSON schema 定义在 xdev.py 内 |

### 开发任务切分

| 架构单元 | 边界 / 入口 | 产出 | 优先级 | 依赖 |
|----------|-------------|------|--------|------|
| status 子命令（契约+核心实现） | `xdev.py status` 子解析器 | checklist 解析 + token 状态判定 + JSON 输出（含 progress），复用现有 first_table/col_values | P0 | 无 |
| graph 子命令（核心实现） | `xdev.py graph` 子解析器 | 拓扑排序（Kahn）+ ready/blocked/order/parallel_batches + 环检测，复用 T1 的解析 | P0 | T1 |
| 格式升级 + 模板同步 | x-req templates / x-dev SKILL.md | dev-checklist 状态列 token+emoji 双轨 + x-req 模板同步 | P1 | T1, T2 |
| x-dev skill 改造 | skills/x-dev/SKILL.md | 并行判断段前调 status+graph，按 ready 派子 agent | P1 | T1, T2, T3 |
| 验证闭环 | test/ | 单元测试：表格解析 / token 映射 / 拓扑排序（含环）/ 旧 emoji 兼容 + fixture | P1 | T1, T2 |
| 文档 | xdev.py docstring / README.md | 编排引擎说明 + xdev --help 更新 | P2 | T1, T2 |

### 执行顺序

1. T1 先落地 status（契约 + 解析复用，确立 JSON schema）
2. T2 复用 T1 的解析实现 graph（拓扑排序 + 环检测）
3. T3（格式升级）与 T5（单元测试）在 T1/T2 后可并行
4. T4（x-dev skill 改造）在 T3 后（依赖新格式落地）
5. T6（文档）最后

```
T1 → T2 → [T3 ‖ T5] → T4 → T6
```

## 技术设计

### 架构归属

- 边界类：`tools/xdev.py` 的子命令分发器（`main()` 内 `add_subparsers`）。xdev.py 是 x-dev-pipeline 的确定性工具层（立法层），本 task 不新增散装函数、不新建边界类，只在现有 CLI 内扩展子命令。
- 外部入口：`python3 tools/xdev.py status <task-dir> [--json]` 和 `python3 tools/xdev.py graph <task-dir> [--json]`。调用方为 `skills/x-dev/SKILL.md`（程序化调用）+ 人工终端。
- 调用约束：status/graph 只读 dev-checklist.md 和可选产物文件，不写任何状态、不改 checklist。状态更新仍由 x-dev 主流程统一负责（避免写冲突，与现有 x-dev 硬规则一致）。新增的解析/排序逻辑作为模块级函数挂在 xdev.py 现有「基础解析」段附近，由子命令分发器调用。

### 公开契约与事实源

| 项目 | 内容 |
|------|------|
| 输入 | `status` / `graph` 各接收一个 task 目录位置参数（指向 `dev-pipeline/tasks/<name>/`，内含 dev-checklist.md）。可选 `--json` 切机器可读输出 |
| 输出 | 见下方 JSON schema。无 `--json` 时打印人类可读摘要 |
| 错误 | 目录不存在 / 无 dev-checklist.md / 表格不可解析 → 退出码 2（用法/IO）；依赖环 → 退出码 1 并列出环节点；正常 → 0 |
| 空值 / 缺省 | 依赖列写 `—` / 空 / 缺列 → 当作无依赖；状态列空 → 当作 todo |
| 状态副作用 | 无（纯只读） |
| 幂等性 / 并发 | 完全幂等，可并发执行 |
| 单一事实源 | dev-checklist.md 表格（任务/状态/依赖）；JSON schema 定义在 xdev.py |

### 数据结构

#### status 状态判定规则（核心决策）—— 双轨制

状态列格式：`| [x] 🟢 |`（token + emoji 双标）。机器读 token，人读 emoji。

**6 emoji → 3 引擎状态压缩映射**：

| token | emoji（人读） | 引擎状态 | 含义 |
|-------|--------------|----------|------|
| `[ ]` | ⏳ 未开始 / ▶️ 进行中 / 🟡 待测试 | `todo` | 编排视为未完成 |
| `[x]` | 🟢 测试通过 / ✅ 已完成 | `done` | 编orchestration 视为已完成 |
| `[!]` | 🔴 测试失败 | `blocked` | 编排视为阻塞 |

设计取舍：把 6 个 emoji 状态压缩成 3 个引擎状态，理由是编排只关心「能不能往下走」，不关心中间态（那是 LLM 的事）。对标 OpenSpec 只用 done / not-done 两态；本 task 多保留一个 `blocked`（🔴）是因为测试失败需要显式暴露给调度层而非混入 todo。

#### 旧 emoji 兼容降级

纯 emoji checklist（状态列无 token，如现有的 qa-gate-pipeline checklist）→ 按如下降级，不报错：
- 含 🟢 / ✅ → `done`
- 含 🔴 → `blocked`
- 其余（⏳ / ▶️ / 🟡 / 空）→ `todo`

这让 status/graph 能直接跑在历史 task 上，无需先迁移格式。

#### 可选产物锚点

task 项备注/涉及文件列可写 `product:reports/T1.md`（相对 task 目录的路径）。status 在判完 token 后，若该项标记为 done 但产物文件不存在（或反过来），在 JSON 中给出 `product_check: "missing"` / `"stale"` 字段作交叉验证提示（不改变 status 本身，纯靠 token）。无 `product:` 锚点则不检查。对标 OpenSpec `detectCompleted` 用文件存在性判定；本 task 因 task 项不一定有独立产物文件，主判依据是 token，产物锚点只作可选交叉验证。

#### graph 拓扑排序

依赖列格式不变（如 `T1` / `T2,T3` / `—` / 空），用 `,` `/` 分隔多依赖。算法用 Kahn：
- 维护入度表 + 反向邻接（dependents）。
- 入度为 0 的根节点入队，**排序后入队**保证确定性（对标 OpenSpec `getBuildOrder` 的 `.sort()`）。
- 每弹出一个节点，将其 dependents 入度 -1，归零者排序后追加。
- 环检测：若最终 `order` 长度 < 节点总数 → 存在环，报错并列出未入序的环节点（退出码 1）。这是与 OpenSpec `getBuildOrder` 的关键差异——OpenSpec 不显式抛环错误（环内节点静默不进 order），本 task 要求显式报错并定位环节点，因为依赖环是 checklist 作者的笔误，必须暴露。
- `parallel_batches`：按拓扑层分层，同一层（同时变为 ready）的节点归一批，供 x-dev 派并行子 agent。

#### JSON 输出 schema

```json
// python3 tools/xdev.py status <task-dir> --json
{
  "task": "xdev-orchestration-engine",
  "tasks": [
    {
      "id": "T1",
      "title": "status 子命令：checklist 解析 + token 状态判定 + JSON 输出",
      "status": "done",
      "deps": [],
      "priority": "P0",
      "product": "reports/T1.md"
    }
  ],
  "progress": { "total": 6, "done": 0, "todo": 6, "blocked": 0 }
}

// python3 tools/xdev.py graph <task-dir> --json
{
  "ready": ["T1"],
  "blocked": [ { "id": "T4", "missing": ["T3"] } ],
  "order": ["T1", "T2", "T3", "T4", "T5", "T6"],
  "parallel_batches": [ ["T1"] ]
}
```

字段说明：
- `status.tasks[].status` ∈ `todo` / `done` / `blocked`；`deps` 为依赖 id 数组；`priority` 从任务行解析（P0/P1/P2，缺失则省略）；`product` 为可选产物锚点路径（无则省略）。
- `graph.ready` = 当前依赖全 done 且自身未 done 的任务（对标 OpenSpec `getNextArtifacts`）；`blocked` = 有未满足依赖的任务及其 `missing` 列表（对标 `getBlocked`）；`order` = 合法拓扑序（无环时覆盖全部节点）；`parallel_batches` = 按拓扑层分组的并行批次。

### 关键链路

x-dev skill 收到开发请求 → 读 README.md 了解任务 → 调 `python3 tools/xdev.py status <task-dir> --json` 拿当前进度 → 调 `python3 tools/xdev.py graph <task-dir> --json` 拿 ready/blocked/parallel_batches → 按 `ready`（或 `parallel_batches[0]`）派子 agent 并行开发 → 子 agent 完成后主流程更新 dev-checklist 状态 token → 下一轮 status/graph 自动反映新进度。调度判定从「LLM 读散文推理」变成「LLM 照 JSON 执行」。

### 失败路径与回滚点

| 场景 | 预期处理 | 验证方式 |
|------|----------|----------|
| task 目录不存在 / 无 dev-checklist.md | 退出码 2，stderr 提示 | 单元测试 + smoke |
| dev-checklist 无表格 / 表头缺关键列 | 退出码 2，stderr 提示缺哪列 | 单元测试 |
| 依赖列写了不存在的 task id | graph 在 `blocked` 里列出（missing 指向不存在的 id），不崩 | 单元测试 |
| 依赖列写 `—` / 空 | 正确当作无依赖 | smoke（qa-gate-pipeline T1/T8/T9 都是 — ） |
| 依赖环（T1→T2→T1） | 退出码 1，列出环节点 T1,T2 | smoke + 单元测试 |
| 纯 emoji 旧 checklist（无 token） | 兼容降级不报错 | smoke（qa-gate-pipeline） |

## DoD（验收清单）

- [ ] 1. `python3 tools/xdev.py status <task-dir>` 能正确解析任意 task 的 dev-checklist，输出合法 JSON（含 progress）
- [ ] 2. `python3 tools/xdev.py graph <task-dir>` 能算出 ready / blocked / order / parallel_batches
- [ ] 3. status 对纯 emoji 旧 checklist（无 token）能兼容降级，不报错
- [ ] 4. graph 能检测依赖环并报错列出环节点（退出码 1）
- [ ] 5. graph 对依赖列写 `—` 或空正确当作无依赖
- [ ] 6. 改造后的 x-dev SKILL.md 在并行判断段前明确调用 status + graph
- [ ] 7. dev-checklist 模板（x-req templates）状态列支持 token + emoji 双轨
- [ ] 8. 单元测试覆盖：表格解析、token 映射、拓扑排序（含环）、旧 emoji 兼容

## Smoke / E2E 验收用例

### Smoke

| ID | 覆盖目标 | 执行方式 | 预期结果 |
|----|----------|----------|----------|
| SM-001 | status 正向（命令化） | `python3 tools/xdev.py status dev-pipeline/tasks/qa-gate-pipeline --json` | 返回 10 个 task，`progress.done=10`（qa-gate-pipeline 全 🟢，旧 emoji 降级为 done） |
| SM-002 | graph 正向（命令化） | `python3 tools/xdev.py graph dev-pipeline/tasks/qa-gate-pipeline --json` | `order` 为合法拓扑序，`ready` 为空（全部 done） |
| SM-003 | 状态混合（命令化） | 造含 `[ ]`/`[x]`/`[!]` 的 checklist 跑 status | `progress` 计数正确；graph 的 `ready` 只含依赖全 done 的 |
| SM-004 | 环检测（命令化） | 造 T1→T2→T1 的环跑 graph | 退出码 1，错误信息列出 T1, T2 |
| SM-005 | 旧 emoji 兼容（命令化） | 用纯 emoji checklist（无 token）跑 status | 不报错且正确降级（🟢→done） |

### E2E

| ID | 覆盖链路 | 执行方式 | 预期结果 |
|----|----------|----------|----------|
| E2E-001 | x-dev 调度链路（manual） | 用户在新会话对一个真实开发任务触发改造后的 x-dev | x-dev 先调 status + graph 再按 ready 派子 agent（需用户在新会话人工触发验证） |

### 自动化测试责任

x-dev 实现时必须补齐以下测试并进入 `dev-report.md` 验证命令清单：

- `test_xdev_status.py`：表格解析（first_table/col_values 复用）、token→引擎状态映射（`[ ]`/`[x]`/`[!]` 三态）、progress 计算（total/done/todo/blocked）、纯 emoji 旧 checklist 兼容降级、可选产物锚点交叉验证。
- `test_xdev_graph.py`：Kahn 拓扑排序正确性、环检测（报错 + 列环节点）、ready/blocked 计算、空依赖（`—`/空）处理、parallel_batches 分层。
- 测试 fixture：含 token 的新 checklist + 纯 emoji 旧 checklist（可直接用 qa-gate-pipeline）+ 含环 checklist。

## 风险（可选）

| 风险 | 应对 |
|------|------|
| 现有 qa-gate-pipeline 等 task 用纯 emoji，新格式上线后历史 task 不带 token | status 内置 emoji 兼容降级，历史 task 无需迁移即可被解析 |
| 依赖列分隔符不统一（`,` `/` 空格） | 解析时同时识别三种分隔符，smoke SM-001/SM-002 用真实 task 覆盖 |

## 文件导航

- [模块/组件图](./diagram.md)
- [开发清单](./dev-checklist.md)
- [变更记录](./changelog.md)
