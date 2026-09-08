<p align="center">
  <img src="assets/pic.png" alt="x-dev-pipeline" />
</p>

# x-dev-pipeline

[English](./README.md)

**当前版本：** v1.0.0

> 给 AI coding agent 一套可审计的开发工作流：需求契约、实现证据、确定性检查、按风险评审。

`x-dev-pipeline` 让 spec 承载需求场景，dev-checklist 承载执行状态，dev-report 承载验证结论。每一步交付都可回溯、可对账、可退回到出问题的那一环。

## 两条工作路径

大需求走主线四步，小任务走单文档闭环：

```text
完整流程：x-spec → x-req → x-dev → x-verify(Gate ①) → x-qa-gate(Gate ②) → 交付
              写需求     拆任务     逐行TDD      交付对账          质量评审

小任务：x-qdev（一份 task 文档：需求 → 测试 → 实现 → 验证，一次闭环）
```

## 主线：spec → req → dev → verify

### 1. x-spec · 写需求

把沟通完的需求写成纯功能性 spec：`docs/spec/<spec-name>/spec.md`。

- 结构固定：标题 + 概述 + `featNN` 列表，每个 feat 是一个用户能说出名字的功能点。
- 每个 feat 配 Given/When/Then 场景，正常、边界、异常三类必备；THEN 只写用户能看到的结果。
- 全文不出现技术词汇（不写"数据库""API""缓存"），用户能看懂每一行。
- 题目没说死的默认值记入结尾待确认清单，让用户一次性 review。

```markdown
## feat02: 按书名搜索

用户可以通过书名快速找到想要的图书。

场景1: 匹配成功
- GIVEN 首页有《三体》和《三体2》在售
- WHEN 用户在搜索框输入"三体"
- THEN 展示《三体》和《三体2》两本书

场景2: 无匹配
- GIVEN 首页没有包含"小说"的书
- WHEN 用户搜索"小说"
- THEN 提示"没有找到相关图书"
```

### 2. x-req · 拆任务

按 feat 分组拆成 task，每个 task 一份开发清单：`docs/spec/<spec-name>/tasks/<task-name>/dev-checklist.md`。

- 任务行只写 `featNN 场景M` 回指 spec 场景，不复制 GIVEN/WHEN/THEN——spec 是唯一事实源。
- 行序即实现顺序，不建依赖图；全部 task 的行合并后覆盖 spec 的每个 feat、每个场景。
- 风险列：改动鉴权、持久化、并发或不可逆操作的行标 `高:`，这类行的验证必须含真实链路。
- 表下带一棵影响文件树（`U` 新增 / `M` 修改 / `D` 删除），与「涉及文件」列一一对应。

````markdown
| # | 任务 | 场景回指 | 涉及文件 | 风险 | 状态 |
|---|---|---|---|---|---|
| T1 | 小组数据结构与创建小组 | feat01 场景1-3 | src/groups.py | None | [ ] ⏳ |
| T2 | 邀请码加入小组 | feat02 场景1-5 | src/groups.py, src/join.py | None | [ ] ⏳ |

## 影响文件树

```text
reading-club/
├── src/groups.py        M  # 小组数据结构、创建校验、邀请码生成
└── src/join.py          U  # 新增：邀请码加入、昵称校验、上限与重复拦截
```
````

### 3. x-dev · 逐行 TDD

x-dev 一次只执行一个 task：从 T1 开始按行序做，先测试后实现，顺序不能反。

- 当前行标 `[ ] ▶️`，为它回指的场景写测试（场景的 THEN 就是断言），先跑红再实现变绿，通过后标 `[x] 🟢`。
- 改动保持在影响文件树范围内，不"顺便"改别的；风险列 `高:` 的行必须有 smoke 或以上真实链路验证。
- 全部行 🟢 后跑本 task 全量测试 + 一次既有测试回归。
- `dev-report.md` 只记验证结论：全绿或 N 个 🔴、回归结果、高风险行验证情况，不粘贴测试输出。

### 4. x-verify · Gate ① 交付对账

x-verify 核对的是交付证据链，不重跑测试、不评判实现质量：以 spec 场景为事实源，对账 checklist 与 dev-report 两份文档——

1. 回指有效：每行 `featNN 场景M` 都真实存在于 spec；
2. 影响树一致：树上没有表外文件，表内文件都在树上；
3. 行状态闭合：全部任务行 `[x] 🟢`，无 ⏳ / ▶️ / 🔴 残留；
4. 高风险行：dev-report 声明了真实链路验证；
5. 结论一致：dev-report 的结论与 checklist 状态对得上。

全部一致只输出回执；发现问题按来源退回——spec 结构问题退 x-spec，回指/树问题退 x-req，报告矛盾退 x-dev，已知失败交 x-fix。

```text
🛡️ Gate① verify ✅ · task-group-management · 行 3/3 🟢 · 回指场景 8/8 有效 · 影响树一致 · 高风险行 1（已声明）· 结论一致
```

## 检查流程：两道门禁

Gate ①（上文 x-verify）守住文档证据链的一致性；Gate ②（x-qa-gate）守住实现本身的质量。verify 通过后按 task 的 risk 路由：

| risk | 典型范围 | Gate ② 路径 |
|------|----------|-------------|
| Q0/Q1 | 单文件小改 / 局部功能或修复 | 直接交付，不启动评审 |
| Q2 | 新功能、多文件、契约或状态变化 | 一个精简 tri-lens reviewer |
| Q3 | 安全、不可逆写入、公开 API/schema、并发或状态机变化 | 一个完整 tri-lens reviewer |

### Gate ② x-qa-gate：tri-lens 质量评审

reviewer 在单轮内按三个独立 lens 穷尽检查，一个 lens 的判断不能替代另两个：

- **q1-intent**：实现是否对齐用户意图、验收 Scenario、既有公开契约和声明的改动范围；
- **q2-correctness**：非法输入、边界条件、失败路径、状态转换、并发、幂等和资源清理；
- **q3-evidence**：测试与 verify 证据是否真实触达改动路径，断言能否击穿错误实现。

reviewer 只读代码、只返回问题候选（`lens` + `task` + `severity` P0/P1/P2 + `loc` + `msg`），不改任何文件。主 agent 复核后逐条调用 `xdev.py flag` 登记为带 `issue-<n>` 编号的 issue 台账，同步降级 checklist 对应行：P0/P1 标 `[!] 🔴`，P2 只登记不阻塞。

### 问题回流：flag → x-fix → 增量复审

```text
Gate ①/② 发现问题
   ├─ 文档不一致 → 按来源退回 x-spec / x-req / x-dev
   └─ P0/P1 → flag 登记 issue → x-fix 一次批量修复
                  → 聚焦反例 + 一次完整 verify 收证 → 增量复审
                  → 最多 3 轮（fix-counter），通过后 checklist 升 [x] ✅
```

- x-fix 一次处理完整 issue 清单，不逐条挤牙膏；每条 P0 固化一条可复跑反例。
- 主 agent 用回归证据关闭 issue，不把修复结果发回原 reviewer。
- 修复范围扩大到新文件或公开 API 时，启动只查新增边界的裁剪 reviewer。
- Gate ① 与 Gate ② 共享三轮 fix-counter；质量审查最终通过后归零。

## x-qdev：小任务单文档闭环

"加个搜索框""修一下导出的 bug"这类具体、范围明确的单一改动，不必走四步主线。x-qdev 先在 `docs/spec/*/spec.md` 里找归属 spec——找到则 task 建在 `docs/spec/<spec-name>/tasks/task-<task-name>.md` 并标注对应 feat；确认无 spec 需求则建独立文档 `docs/task/task-<task-name>.md`。

然后在**一份 task 文档**里依次完成四段，一份文档就是完整交付物：

1. **①需求**——功能性语言：功能方向、功能边界（做/不做）、不能破坏的不变量；
2. **②测试用例**——先写、此刻是失败的：unit + smoke，按需 e2e，必须覆盖边界；
3. **③技术实现**——实现步骤与涉及文件，让 ② 变绿；
4. **④验证结果**——只粘贴真实运行输出和不变量回归结果，结论四个勾选与实际内容一致。

交付前对 task 文档自身做五项自检 gate：结构完整、回指有效、覆盖闭合、结论一致、边界核对——不依赖其他 skill 收口。任务超出小任务范围（跨多模块、需要重新讨论需求、涉高风险）时，提示转 x-spec + x-req 完整流程。

```text
✅ x-qdev 完成 · task-todo-search · 测试 5/5 通过 · 不变量回归通过 · 改动文件 1 个
```

## 可选：Spec 对抗性风险复核

spec 包在 task 拆解前可经过一次独立风险门禁（`x-spec → x-adversarial-risk → x-req`）：

x-spec 分别记录 1–5 的复杂度和重要性；`x-bug2rag/scripts/home_corpus.py` 先初始化 `~/.x-dev-pipeline/rag/`，再把插件种子语料复制为 `risk-catalog.md`。风险审查与 Bug 沉淀在所有项目间共享这份用户级 corpus，调用方也可显式覆盖路径。`x-adversarial-risk` 按 review_budget 执行一次 Top5 向量召回，用召回经验构造能区分正确实现与常见错误实现的最小反例，并以 `adversarial-review` 来源补进 spec 场景；带风险版本标记的 Spec 审查状态仍为 pending 时，x-req 阻断任务拆解。

## 命令

| 命令 | 职责 |
|------|------|
| `/x-spec` | 把需求写成纯功能性 spec（feat + GWT 场景） |
| `/x-req` | 按 feat 拆 task，生成场景回指式 dev-checklist |
| `/x-dev` | 逐行 TDD 执行单个 task，写结论式 dev-report |
| `/x-verify` | Gate ①：交付对账，按来源分诊退回 |
| `/x-qa-gate` | Gate ②：tri-lens 质量评审，flag 登记 issue |
| `/x-qdev` | 小任务单文档闭环：需求 → 测试 → 实现 → 验证 |
| `/x-fix` | 批量修复 verify、gate 或 CR 发现的 issue 清单 |
| `/x-cr` | 调查已知正确性问题、模块、diff 或 PR |
| `/x-adversarial-risk` | 推翻 Spec 风险假设并补充可追溯反例 Scenario |
| `/x-multi-llm-align` | 对齐协议、数据结构或流程 |
| `/x-audit-perf` | 独立性能巡检 |
| `/x-audit-style` | 独立规范巡检 |
| `/x-audit-arch` | 独立架构巡检 |

## 确定性引擎

`skills/x-dev/scripts/xdev.py` 是机械规则的薄 CLI 入口；包校验由
`skills/x-spec/scripts/validator.py` 负责，spec task 规划由
`skills/x-req/scripts/req.py` 负责，验证由 `skills/x-verify/scripts/verify.py` 负责，QA issue
事务由 `skills/x-qa-gate/scripts/flag.py` 负责：

```text
validate [pkg...]                 校验 spec、change、task 契约
status <task-dir> [--json]        解析 checklist 进度
graph <task-dir> [--json]         计算 ready task 与并行批次
instructions <artifact> --task    返回 task 产物填写规则
scaffold <task-dir>               只创建缺失 task 产物
verify <task-dir> [--json]        执行证据并对账 Scenario
flag <task-dir> --task T2,T3 --severity P0 --loc src/a.py:10 --msg "..." [--new-round] [--json]
```

task 命令只接收 `docs/spec/<spec-name>/tasks/<task-name>/`。历史
`dev-pipeline/tasks/` 目录继续作为可读档案保留，不再获得运行时校验或编排支持。

v1.0.0 起 Gate ① 改为 x-verify skill 的交付对账，verify 引擎保留给既有 `spec_version: 3` 契约包；v6 链路日常使用 `status`（进度）与 `flag`（issue 台账）。`flag` 通过持久事务协调 issue ledger 与每个 task 唯一的一份 `dev-checklist.md`：内容无变化不创建临时文件，pending 事务恢复返回 `recovered:true`，调用方重试本条 issue。

## x-spec2 pilot 计量

`skills/pipeline-efficiency-benchmark/scripts/metrics.py` 从一个显式 Codex rollout JSONL，或保存后的子 agent 完成通知中记录一次 x-spec2 eval。最小 measurement 包含执行来源 ID、模型、仓库 SHA、prompt 哈希、耗时、provider 返回的真实总 token，以及独立 grader 给出的断言通过率。

```bash
python3 skills/pipeline-efficiency-benchmark/scripts/metrics.py extract \
  --timing <run-dir>/timing.json \
  --metadata <run-dir>/eval_metadata.json \
  --grading <run-dir>/grading.json \
  --output <run-dir>/measurement.json

python3 skills/pipeline-efficiency-benchmark/scripts/metrics.py aggregate-spec2 deprecated/x-spec2-workspace/iteration-2
```

退出码 0 表示提取或聚合成功；1 表示可读取的样本违反 fresh-session、rubric 隔离或 paired 可比性边界；2 表示参数、IO、JSON 或 schema 错误。单个 paired run 标记为 `pilot: true`，它用于证明测量流程成立，稳定效果判断需要更多题目与重复运行。

## 安装

仓库同时提供 Claude Code 与 Codex 的 manifest：

```text
.claude-plugin/plugin.json
.claude-plugin/marketplace.json
.codex-plugin/plugin.json
.agents/plugins/marketplace.json
```

Claude Code：

```bash
git clone https://github.com/KtKID/x-dev-pipeline.git ~/.claude/plugins/x-dev-pipeline
claude plugin marketplace add ~/.claude/plugins/x-dev-pipeline/.claude-plugin/marketplace.json
claude plugin install x-dev-pipeline@x-dev-pipeline --scope user
```

Codex：把 `.agents/plugins/marketplace.json` 中的仓库条目加入 marketplace，重启 Codex 后从本地插件目录安装 `x-dev-pipeline`。

## 状态标记

| 标记 | 含义 |
|------|------|
| `[ ] ⏳` | 未开始 |
| `[ ] ▶️` | 进行中 |
| `[!] 🔴` | 验证失败 / P0-P1 issue 降级 |
| `[x] 🟢` | 验证通过 |
| `[x] ✅` | 质量评审通过 |

## License

MIT
