# progress-engine 开发方案（v5，依据第四轮外部审查 5 P1 + 11 P2 修订）

> 一句话：checklist 状态列缩成三符号；每个 task 增加"进度节"（按 risk 预植的步骤格）；
> 打钩由引擎依据**绑定了代码状态指纹的证据**执行——防跳步、防作弊、防过期、可对账。
> 本文档自包含。先转 OpenSpec change 交用户确认再实现。**验收通过前不得 archive。**
>
> v5 核心修订：① 指纹**锚定仓库根**——由 `<task-dir>` 推导 `git -C <root>`，全部 git
> 调用 `-z` 输出，指纹与 cwd 无关；② **指纹域界定补全**——排除/投影用仓库根相对
> pathspec 写死（模板不投影）、工作区已删除路径跳过、changelog 与 fix-attempts 纳入
> 排除/投影域；③ 新包状态列三符号契约**归属 V9 按包型分叉**，非法 risk 归还既有 V11；
> ④ DoD-28 改走 `.git/info/exclude`（.gitignore 文件自身计入清单，字面写法不可满足），
> DoD 修订并新增 35–41（共 41 条）。

---

## 0. 执行须知

- **仓库**：`/Volumes/machub_app/proj/x-dev-pipeline`
- **前置条件（不满足就停下问用户）**：
  1. fixes-and-metrics 单已验收并提交：`skills/x-qa-gate/references/reviewer-lenses.md` 与
     `tools/metrics.py` 已存在；
  2. **commit 0 先行**：把本 plan、`dev-pipeline/tasks/progress-engine/` 与本单 OpenSpec
     change 文档作为 planning 提交入库；随后确认实现基线 clean 且
     `python3 -m unittest discover -s test` 全过，再开工。
     **commit 0 的 OpenSpec tasks.md 必须包含映射表：每条任务 T# → 触及文件 → 对应
     规格节 → 覆盖的 DoD 编号**（41 条 DoD 需要能反向找到实现负责任务）。
- **提交拆分**：commit 0（planning）→ A（`tools/xdev.py` + `skills/x-req/templates/dev-checklist.md` + `test/`）→
  B（`skills/` 同步）→ C（`README.md`/`README_zh.md`）→ 收尾归档提交（任务档案）；
  可选 metrics 补行独立 chore commit
- **禁止事项**：不迁移历史 task；不做兼容垫片；未定义数值一律问用户；不动第③步（capability 回流）
- **涉及 capability**（全部 MODIFIED）：`xdev-task-artifact-engine`、`xreq-lean-planning`、
  `risk-routed-development-flow`、`xdev-verification-engine`

---

## 1. 背景与目标

现状问题：① emoji 状态有 LLM 写入字节隐患，六态是装饰层；② 可变状态是覆写语义的断言，
跳步不可见；③ 打钩者与被验者同为 LLM，可自盖章；④ 证据不绑代码状态——改完代码不重验，
旧"通过"永远有效。

目标：三符号行状态 + 按 risk 预植的进度节 + 引擎依据带指纹的证据打钩 + `--check`
零副作用对账。作弊与过期都在重算面前现形。

---

## 2. 设计总览

### 2.1 写者模型

| 文件/区域 | 写者 | 说明 |
|-----------|------|------|
| checklist 任务行状态 | LLM **升级**（`[ ]`→`[x]`；修复后 `[!]`→`[x]`）；progress **仅降级**（→`[!]`） | 流程上严格串行 |
| checklist **进度节** | `xdev.py progress` | 唯一写者 |
| 验证回执 `reports/verify/last-verify.json` | `xdev.py verify` 完整运行 | `--only` 不写；开跑失效旧回执，结束原子替换（4.4） |
| gate 报告 `reports/qa-gate/qa-gate-report-<时间戳>.md` | **主 agent（聚合）** | reviewer 只交 mini-report 返回值不落盘；主 agent 聚合本轮全部 lens 写单一时间戳文件 |
| checklist `## fix-attempts 记录` 节 | x-fix（补记轮数） | 投影域内→不动指纹（2.2） |
| `changelog.md` | LLM（收尾档案） | 排除域→不动指纹（2.2） |

并发说明：磁盘写者两两不相交且流程串行；不加文件锁（单人本地工具，取舍记录于此）；
异常写入由 `--check` 对账兜底。

### 2.2 证据指纹（v4 内容寻址 + v5 仓库根锚定与域界定）

**唯一实现**：新增公开子命令，所有生产者与校验者调用同一实现——

```
python3 tools/xdev.py fingerprint <task-dir> [--json]
```

- **仓库根锚定（v5）**：根 = `git -C <task-dir> rev-parse --show-toplevel`；此后全部 git
  调用统一 `git -C <root> … -z`（NUL 分隔原始字节路径、相对仓库根输出，规避 cwd 依赖与
  core.quotePath 转义）。**指纹与调用时的 cwd 无关**（进 DoD-30）
- **输出契约**：`--json` 输出恰为两个 key：`{"fingerprint": "<sha256:64hex 或 no-git>",
  "root": "<仓库根绝对路径，no-git 时为 null>"}`；无 `--json` 时输出指纹值单行
- verify/progress 内部调用同一 Python 函数（根由各自的 `<task-dir>` 参数推导）；x-qa-gate
  的主 agent 在 dispatch reviewer **之前**运行本 CLI（带 `<task-dir>`）取值写入
  gate-verdict 块。**禁止任何地方按散文公式自行拼算**——上一版公式歧义已证明，
  指纹的正确性来自单一实现，不来自公式描述

**计算定义（内容寻址，不依赖 git diff 文本）**：

1. 文件清单 = `git -C <root> ls-files -z`（已跟踪）∪ `git -C <root> ls-files -o
   --exclude-standard -z`（未跟踪且未被 ignore——新功能源码在首次提交前也计入，
   堵住"改未跟踪文件不失效"漏洞）
2. **工作区实态（v5）**：内容寻址以工作区实际字节为准，staged/unstaged 无别（进 DoD-29）。
   清单中的路径在工作区不存在（未暂存的删除）或非常规文件（子模块 gitlink、断开的符号
   链接）→ 视为不存在，跳过不计入（进 DoD-35）；符号链接按其链接文本字节参与
3. **排除与投影域（v5 用仓库根相对 pathspec 写死，消灭自失效反馈环）**：
   - 整体排除 `dev-pipeline/tasks/*/reports/**`（回执与全部报告）与
     `dev-pipeline/tasks/*/changelog.md`（叙事档案：通关后补写不得打红对账，进 DoD-41）
   - 规范化投影仅作用于 `dev-pipeline/tasks/*/dev-checklist.md`：移除 `## 进度` 节的进度行；
     任务表每行"状态"列替换为固定占位 `[ ]`、"fix"列替换为 `—`；移除 `## fix-attempts 记录`
     节的表体行；其余内容原样
   - **不匹配上述 pathspec 的文件一律按普通内容计入**——尤其
     `skills/x-req/templates/dev-checklist.md`（模板是 commit A 交付物，不投影，进 DoD-40）
   ——这样 progress 写进度行/降级行、LLM 打行钩、x-fix 补记 fix-attempts、收尾写 changelog
   都**不改变指纹**；而任务表增删行、README/plan/dev-report/源码/测试的任何改动**都改变指纹**
4. 规范字节流：按路径（相对仓库根）字典序，对每个计入文件拼 `path 字节 + NUL +
   sha256(内容字节) + NUL`（checklist 用投影后内容），整体再 sha256。二进制拼接、NUL
   分隔，无换行歧义
5. **非 git 降级**：由 `<task-dir>` 推根失败（rev-parse 非零）→ 指纹取常量 `"no-git"`；
   此时过期检测**不可用**（"no-git" 恒等于 "no-git"），progress 每次输出警告"无 git，
   证据过期检测不可用，关键节点请用 --reverify"。这是明示的残余风险，不用 mtime 假装检测
6. 性能注记：对大仓库逐文件 hash 有成本；单次运行内每文件只读一次即可。**不做跨进程
   缓存**——CLI 每次调用都是新进程，缓存无处驻留；对外语义 = 全量重算

**校验规则**：progress 每次运行重算当前指纹；证据指纹 ≠ 当前指纹 → 该格清空 +
issue"证据过期"。指纹格式必须匹配 `^sha256:[0-9a-f]{64}$` 或 `^no-git$`，否则按 schema 违例 exit 2。

### 2.3 每格的打钩依据（所有符号每次从证据全量重算）

| 步骤格 | 依据（均由 progress 推导） |
|--------|--------------------------|
| `dev` | **降级后的虚拟任务表**全部 `[x]` → `x`；任一 `[!]` → `!`；其余（存在 `[ ]` 且无 `[!]`）→ 空；空表 → exit 2 |
| `verify` | 回执 schema 合法、指纹相符：`ok: true` → `x`，`ok: false` → `!`；指纹不符 → 空 + stale issue；无回执 → 空（初始态，不产 issue） |
| `rc`/`r1`/`r2`/`r3` | 该 lens 当前结论块（3.3 选取）、指纹相符：pass → `x`，fail → `!`；指纹不符 → 空 + stale issue；无块 → 空（不产 issue） |

行级降级：只消费**当前有效**（指纹相符）fail 结论中的 P0/P1 issue；P2 登记不动行。
lens 合法但不在当前 risk 步骤集（如 Q0/Q1 显式调 gate 按 Q2 处理产出的 rc 块）：无格可打，
登记 warning，但其有效 fail 的 P0/P1 **仍参与行降级**——证据不因格缺席而作废（进 DoD-39）。

### 2.4 按 risk 预植与变更

| risk | 步骤集 |
|------|--------|
| Q0/Q1 | `dev verify` |
| Q2 | `dev verify rc` |
| Q3 | `dev verify r1 r2 r3` |

预植时机 = scaffold；README `risk:` 是唯一真源；**risk 迁移只决定格名称与顺序**，
全部符号每次从证据重算（不存在"保留旧钩"）。

注意：改 README 的 `risk:` 行本身就改变指纹 → 既有证据全部过期，迁移后 verify/review
格必然清空并报 stale issue（dev 格由行状态重算，行不绑指纹），需重跑 verify 与 gate
（进 DoD-11 预期）。

### 2.5 数据流

```
x-dev/x-fix 升级任务行（投影排除→不动指纹） ────┐
xdev.py verify（完整）→ 回执(含指纹) ──────────┼─→ xdev.py progress
主 agent 聚合 reviewer 结论(含指纹)落盘 ────────┘   1.解析证据(schema+指纹校验)
                                                   2.算行降级→虚拟表 3.推导全部格
                                                   4.一次写回（写动作均在指纹排除域内→幂等）
                任何人：progress --check（零副作用对账）/ --reverify（重跑 verify 后对账）
```

---

## 3. 语法契约

### 3.1 checklist 进度节与状态列

文件：`dev-pipeline/tasks/<task-name>/dev-checklist.md`（模板：`skills/x-req/templates/dev-checklist.md`）

```markdown
## 进度

dev[ ] verify[ ] rc[ ]

## 任务清单

| # | 任务 | 涉及文件 | 依赖 | 状态 | fix |
|---|------|---------|------|------|-----|
| T1 | 契约设计 | src/a.py | — | [x] | — |
| T2 | 核心实现 | src/b.py | T1 | [!] | 1 |
```

- 进度行 = `## 进度` 后第一个非空行；**行首尾允许空白，其余位置只允许步骤格与分隔空白**
- 符号枚举（行与格通用）：`[ ]`/`[x]`/`[!]`，仅此三种（大写 X、emoji、双轨一律非法；
  **新包状态列契约进 V9 按包型分叉**，见 4.6）
- 任务表 ≥1 条合法任务行、T# 表内唯一（进 V9；T# 重复时 progress exit 2，见 4.3）
- fix 列与 fix-attempts 机制不变；fix-attempts 记录节表体在指纹投影域内（2.2）

### 3.2 验证回执（v4 补严格 schema）

`reports/verify/last-verify.json`，完整 verify 覆盖式写入。**解析契约（违反 → 三种
progress 模式统一 exit 2）**：

- 顶层必须是 JSON object；**必需 key 恰为**：`ok`、`timestamp`、`fingerprint`、`pass`、
  `fail`、`manual`、`uncovered`；出现任何未知 key → 非法
- `ok` 必须是 JSON **boolean**（字符串 `"false"` 非法——宽松真值判断会把它当 True）
- 自洽校验：`ok == (fail 为空 且 uncovered 为空)`，不符 → 非法
- `fingerprint` 匹配 `^sha256:[0-9a-f]{64}$` 或 `^no-git$`
- `pass`/`fail`/`manual`/`uncovered` 均为**元素唯一的字符串数组**，且四数组两两不相交
- `timestamp` 为 ISO-8601 字符串
- 非法 JSON、schema 违例、IO 错误 → exit 2

示例（仅示意，契约以上文为准）：

```json
{"ok": true, "timestamp": "2026-07-17T08:30:00Z", "fingerprint": "sha256:9f2c…",
 "pass": ["S1", "S2"], "fail": [], "manual": ["M1"], "uncovered": []}
```

`--only <id>`：不写回执、不影响进度（纯诊断）。"全过不产报告"政策指人读报告，回执是机器证据。

### 3.3 报告结论块（gate-verdict）

落点：主 agent 聚合写入的 `reports/qa-gate/qa-gate-report-<时间戳>.md`；契约文字进
`skills/x-qa-gate/references/reviewer-lenses.md`"共享输出契约"节。

````markdown
```gate-verdict
lens: r1
round: 2
fingerprint: sha256:9f2c…
verdict: fail
issue: F1 | P0 | T2 | src/b.py:120 | 空输入未处理
issue: F2 | P2 | T3 | src/c.py:45 | 命名与惯例不一致
```
````

**解析契约（违反 → exit 2 并指明文件与块位置）**：

- 必需 key：`lens`、`round`、`fingerprint`、`verdict`；可选 key：`issue`（可多行）；其余非法
- 同一块内除 `issue` 外 key 重复 → 非法；同块 issue 编号重复 → 非法
- `lens` ∈ {rc,r1,r2,r3}；`round` 正整数；`verdict` ∈ {pass,fail}；fingerprint 格式同 3.2
- **同一文件内同 lens 同 round 出现多块 → 非法**（同 lens 不同 round 取 round 最大）
- 报告文件名必须含可解析时间戳（`qa-gate-report-<YYYYMMDD-HHmmss>.md`），不合规文件名 → exit 2
- issue 五段 `编号|严重度|T#列表|file:line|摘要`：按**前 4 个 `|`**切分、各段去两侧
  空白，前四段不得含 `|`，摘要可含；T# 列表逗号分隔（如 `T2,T3`），逐个判定；
  严重度一致性：pass 不得含 P0/P1，fail 必须 ≥1 条 P0/P1；引用的 T# 不存在 →
  该条不参与降级 + progress issue
- **当前结论选取（按 lens 独立）**：对每个 lens 取"含该 lens 块的最新时间戳文件"，
  时间戳并列时取文件名字典序最大者；增量复审只补部分 lens 时其余 lens 沿用各自
  最新文件，天然正确
- lens 合法但不在当前 risk 步骤集 → 不打格，判定与降级规则见 2.3

---

## 4. 实现细节（`tools/xdev.py`）

### 4.1 进度行解析器

1. 定位 `## 进度` 后第一个非空行；`re.finditer(r"([a-z0-9_]+)\[([ x!])\]", line)` 扫描
2. 合法性：行首尾空白允许；相邻匹配间必须有 ≥1 空白（粘连 → V13 issue）；
   全部匹配 + 间隔空白 + 首尾空白必须覆盖整行（杂字/0 匹配/非法符号 → issue）；
   不能先按空白 split（`[ ]` 内含空格）
3. 步骤名重复 → V13 issue
4. 包类型三态：README 无 `risk:` 行 → 旧包（progress exit 2 提示不适用；V13 不触发；
   validate 侧既有 V11 仍报缺 risk，本单不改 V11）；有行但值非法 → progress exit 2
   提示先修 README（该违例静态归属**既有 V11**，V13 不重复立规）；合法 → 全套规则生效

### 4.2 gate-verdict 解析器

按 3.3 契约实现；遍历 `reports/qa-gate/*.md` 抽块；产出
`{lens: {round, verdict, fingerprint, issues, 来源文件}}`。

### 4.3 `progress` 子命令

```
python3 tools/xdev.py progress <task-dir> [--json]
python3 tools/xdev.py progress <task-dir> --check [--json]
python3 tools/xdev.py progress <task-dir> --reverify [--json]
```

- `--check` 与 `--reverify` 互斥，同时传入 → exit 2

写入模式算法（顺序是正确性关键）：

1. 读 README `risk:`（4.1 三态）→ 目标步骤集；由 `<task-dir>` 推仓库根，调用指纹函数
   （2.2）算当前值
2. 解析任务表；空表或 T# 重复 → exit 2
3. 解析回执（3.2 schema）与报告（3.3），指纹校验 → 各证据的**有效**结论
   （过期 → 对应格记空 + issue）
4. **先算行降级**：有效 fail 结论的 P0/P1 issue 引用的 T# → 降级集合 → 应用到虚拟
   任务表（含越集 lens 的有效 fail，2.3）
5. 从虚拟表推导 `dev` 格；verify/review 格按 2.3
6. 按当前 risk 生成步骤集，全部符号来自本次推导，重建进度行
7. 一次写回。**幂等成立的机制**：progress 的全部写入（进度行、行状态列）都在指纹的
   排除/投影域内——写回不改变指纹，连跑两次文件与判定均不变
8. `--json`：`{"progress":…, "downgraded_rows":…, "p2_registered":…, "stale_evidence":…, "warnings":…, "issues":…}`；
   --check/--reverify 模式额外含 `consistent`、`complete`

**手工试跑示例（规格的一部分，执行方照此写首个测试；须在真 git 仓库 fixture 中执行，
checklist 为已跟踪文件）**：
行 T1`[x]` T2`[x]`；回执 ok:true 指纹相符；r1 fail 含 `F1|P0|T2|…`。
→ 降级集合 {T2}；虚拟表 T1`[x]` T2`[!]`；dev=`!`、verify=`x`、r1=`!`；
首跑写回：T2 行 `[!]`，进度行 `dev[!] verify[x] r1[!] r2[ ] r3[ ]`；
**再跑：指纹未因上次写回而变化，证据仍有效，文件无变化**。

**`--check`**：零副作用（不执行命令、不写文件）；同样先模拟降级得虚拟表，再逐格、逐行
比对磁盘实际值与推导值（"应降级却仍 `[x]` 的行"是必查差异）。
**语义（v4 明确）**：`--check` 的退出码表达**账实一致性**，不表达"全部通过"——JSON 里
同时给 `consistent`（bool）与 `complete`（bool：当前 risk 步骤集是否全 `x`）两个字段，
调用方要判完成度读 `complete`。文档与回执措辞不再使用"全绿"。

**`--reverify`**：先完整重跑 verify（刷新回执，有副作用，显式使用），再走 --check 逻辑。

**退出码矩阵（v4 重写）**：

| 情形 | 写入模式 | `--check` | `--reverify` |
|------|---------|-----------|--------------|
| 解析/schema/用法/IO/原子写失败/空表/T# 重复/旧包/非法 risk/互斥参数 | 2 | 2 | 2（verify exit 2 → 直接 2，跳过对账） |
| verify 失败（--reverify 重跑结果） | — | — | 1 |
| 账实不一致 | 0（写成推导值） | 1 | 1 |
| 一致（含格中有 `!`、stale/T# issue 但磁盘已同步的情况） | 0 | 0 | 0（且 verify 通过） |

优先级：错误类（2）> 失败/不一致（1）> 0。stale issue 在 JSON 里始终报告，不影响一致性判定。

### 4.4 verify 子命令（回执生命周期）

- 完整运行：**开跑即删除旧回执**（崩溃/exit 2 都不会留下过期成功）；结束调用指纹函数、
  写临时文件、`os.replace` 原子落位；原子写失败 → exit 2
- `--only`：不删不写回执，stdout 行为不变
- verify 不写 checklist 任何区域

### 4.5 scaffold `--risk`

- README 不存在：`--risk` 必填并写入；缺参 exit 2
- README 已存在且含合法 `risk:`：README 为真源——省略沿用；不一致 → exit 2 提示先改 README
- 幂等不变：已存在文件跳过

### 4.6 validate（V9 扩展 + V13）

- V9 扩展：任务表 ≥1 行；T# 唯一；**状态列按包型分叉**——新包（README 含合法 `risk:`）
  仅接受裸 `[ ]`/`[x]`/`[!]`（emoji、双轨、大写 X → issue，进 DoD-36）；旧包沿用既有
  双轨/emoji 兼容契约不变
- V13（仅新包）：进度节存在可解析（含首尾空白与间隔规则）；步骤集与 risk 精确一致
  （进 DoD-38）；进度行符号合法。risk 值本身的合法性归**既有 V11**，V13 不重复立规
- 分工：validate 静态结构；证据一致性归 `progress --check`；docstring 规则表同步

---

## 5. skill 与文档同步清单

| 文件 | 改动 |
|------|------|
| `skills/x-req/templates/dev-checklist.md` | 进度节、三符号、删 emoji 图例（commit A） |
| `skills/x-req/SKILL.md` | scaffold 带 `--risk`；三符号表述 |
| `skills/x-dev/SKILL.md` | 收尾："完整 verify（产回执）→ progress → risk 路由"；`--only` 仅诊断；禁止手写进度节；原"Gate ② 全部通过后把 checklist 标为 `[x] ✅`"改为"跑 progress 重算进度节"（DoD-18 清除对象） |
| `skills/x-dev/references/execution-rules.md` | 行升级归 LLM、降级归 progress |
| `skills/x-verify/SKILL.md` | 回执生命周期；`--only` 不产回执 |
| `skills/x-qa-gate/SKILL.md` | dispatch 前跑 `xdev.py fingerprint <task-dir>` 取值；聚合单文件落盘；P2 登记不降行；原"标为 `[x] ✅`"改为"跑 progress 重算进度节"（DoD-18 清除对象） |
| `skills/x-qa-gate/references/reviewer-lenses.md` | gate-verdict 语法全文（3.3） |
| `skills/x-qa-gate/templates/qa-gate-report-template.md` | gate-verdict 示例（含 fingerprint） |
| `skills/x-fix/SKILL.md` | 修复后升级行、补记 fix-attempts（投影域内不动指纹），复审与 progress 重新打格 |
| `README.md` / `README_zh.md` | 三符号 + 进度节说明（commit C） |
| `test/test_xdev_progress.py`（新）+ 既有 fixture | 见 DoD |

历史兼容：旧 task 由既有解析兼容逻辑只读消化；不迁移。

## 6. 明确不做

不做行级 verify；不引入记账 LLM；不加文件锁；不动 fix 计数、lens 语义、第③步（capability 回流）。

## 7. DoD（v5 = 前 34 条修订 + 锚定/域界定专项 35–41）

| # | 验收项 | 预期 |
|---|--------|------|
| 1 | `python3 -m unittest discover -s test` | OK |
| 2 | scaffold 预植（`--risk Q2`） | 进度节三格 + README risk 行 |
| 3 | scaffold 真源（README Q3 + `--risk Q2`） | exit 2；省略沿用 Q3 |
| 4 | 完整 verify 通过/失败 | 回执 schema 合法、指纹正确；checklist 未被 verify 触碰 |
| 5 | `--only` 隔离（单块过、整体有败） | 无回执更新；progress 后 verify 格非 `x` |
| 6 | review 打格（pass 块） | `rc[x]` |
| 7 | verdict 违例（pass 带 P0 / fail 仅 P2 / 缺 fingerprint / 重复 key / 重复 issue 编号 / round 非法 / 同 lens 同 round 双块 / 文件名无时间戳） | 各 exit 2 |
| 8 | P2 不降行 | P0(T2) 降、P2(T3) 不降且进 `p2_registered` |
| 9 | 空表 | progress exit 2；V9 issue |
| 10 | 重复 T# | V9 issue；progress 对重复 T# 表 exit 2（降级目标歧义） |
| 11 | risk 迁移（Q2 有钩 → Q3） | 步骤集精确替换；README 改动致证据全过期：verify 格清空 + stale issue，dev 格由行状态重算（2.4 注意项） |
| 12 | `--check` 零副作用 | 目录快照前后无变化；伪造 `rc[x]` 无据 → exit 1 |
| 13 | 退出码矩阵 | 按 4.3 表逐格测：写入含 issue 仍 0；--check 一致 0/不一致 1；--reverify verify 败 1、verify exit 2 → 2；互斥参数 → 2 |
| 14 | 幂等（git 集成 fixture，checklist 已跟踪） | progress 连跑两次文件与判定均不变 |
| 15 | 粘连拒绝（`dev[ ]verify[ ]`） | V13 issue |
| 16 | 旧包三态 | 旧包全套跳过；非法 risk V13+exit 2 |
| 17 | 旧格式回归（emoji fixture 的 status/graph） | 行为不变 |
| 18 | 旧状态组合清除 | 文件集 = `skills/**` + `README.md` + `README_zh.md`：grep 六种双轨组合（`[ ] ⏳`/`[ ] ▶️`/`[ ] 🟡`/`[x] 🟢`/`[x] ✅`/`[!] 🔴`）与字样"双轨" = 0 命中（对话回执单独 emoji 不在禁令内；tools/xdev.py 旧包兼容分支不在此列） |
| 19 | `openspec validate <change> --strict` | 通过；验收前不归档 |
| 20 | 提交结构 | commit 0/A/B/C/归档；tasks.md 含 T#→文件→规则→DoD 映射 |
| 21 | 源码变更失效回执 | verify pass 后改已跟踪源文件 → verify 格清空 + stale issue |
| 22 | exit 2 不留旧成功回执 | 弄坏 dev-report 跑完整 verify → 旧回执已不存在 |
| 23 | QA pass 后 diff 变化 | rc pass → 改代码 → rc 格清空 + stale issue |
| 24 | Q3 三 lens 分布多文件 | 各自独立取最新，三格判定正确 |
| 25 | 首跑降级即 dev[!] | 4.3 试跑示例场景一次到位 |
| 26 | `--check` 检出行差异 | 应降级却仍 `[x]` → 列出差异 exit 1 |
| 27 | **指纹自反性** | git fixture 中 progress 写回（进度行+降级行+LLM 打行钩+x-fix 补记 fix-attempts）后指纹不变（DoD-14 的机制性验证） |
| 28 | **untracked 源码计入** | 新增未跟踪 .py → 指纹变化；将该路径写入 `.git/info/exclude` → 指纹回到基线值（**不可用 `.gitignore`**——该文件自身计入清单，指纹回不到基线） |
| 29 | **staged 等价** | 同一内容改动，staged 与 unstaged 状态下指纹相同 |
| 30 | **单一实现一致** | `xdev.py fingerprint <task-dir>` == verify 回执内指纹 ==（模拟）主 agent 取值；在仓库根与任意子目录 cwd 下运行值相同 |
| 31 | **checklist 投影正确性** | 改任务表"任务"列文字 → 指纹变；只改状态/fix 列 → 不变 |
| 32 | **no-git 降级** | 非 git 目录：指纹 `no-git`、warning 输出、判定继续 |
| 33 | **回执 schema 违例** | `ok:"false"`（字符串）/未知 key/ok 与 fail 不自洽/指纹格式错 → 各 exit 2 |
| 34 | **原子写失败** | 模拟 reports/verify 不可写 → verify exit 2，无半成品回执 |
| 35 | **删除态可算** | 删除已跟踪文件（未暂存）→ 指纹正常算出且值变化，不报错；恢复文件 → 回原值 |
| 36 | **新包状态列拦截** | 新包任务行写 `[x] ✅` / `[X]` → V9 issue；旧包 emoji fixture 不受影响（与 DoD-17 互证） |
| 37 | **scaffold 缺参** | README 不存在且未传 `--risk` → exit 2 |
| 38 | **步骤集一致性** | 新包 README Q2 而进度行手改为 Q3 步骤集 → V13 issue |
| 39 | **issue 文法与越集 lens** | 摘要含竖线仍正确切分（按前 4 个分隔）；`T2,T3` 多 T# 全部降级；Q1 显式 gate 产 rc 块 → 不打格 + warning + 仍降级 |
| 40 | **模板不投影** | 改 `skills/x-req/templates/dev-checklist.md` 示例状态列 → 指纹变化（投影仅限 `dev-pipeline/tasks/*/dev-checklist.md`） |
| 41 | **changelog 排除** | 通关后写 task `changelog.md` → 指纹不变，`--check` 仍一致 |

## 8. 交付材料

1. OpenSpec change（活跃，tasks.md 含 DoD 反向映射）+ 各 commit `git show --stat`
2. 单测完整输出
3. 手工全链样例（git fixture：scaffold → 填行 → verify → 聚合报告 → progress →
   --check 一致 → 伪造钩被抓 → 改源码 stale 被抓 → progress 写回后指纹不变 →
   写 changelog 后 --check 仍一致）
4. DoD-5 / 11 / 21 / 27 / 29 / 30 / 35 / 40 / 41 的实际输出
5. 每项偏离及理由
