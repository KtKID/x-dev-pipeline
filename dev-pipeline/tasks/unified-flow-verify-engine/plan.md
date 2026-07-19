# unified-flow-verify-engine 开发方案

> 方案 A 第②步：统一任务流（qdev 退役）+ 证据机械化（verify 引擎）。
> 本文档自包含，执行方（LLM）不需要任何对话上下文即可开工。
> 建议沿用上一单（xreq-instructions-engine）的做法：先把本方案转成 OpenSpec change
> （proposal / design / specs delta / tasks）交用户确认，再实现。
> 完成后交回原方案作者 review，交付材料清单见文末第 9 节。

---

## 0. 执行须知（先读）

- **仓库**：`/Volumes/machub_app/proj/x-dev-pipeline`
- **前置条件（两条都必须满足，否则停下问用户）**：
  1. 上一单 xreq-instructions-engine 的返修改动（`tools/xdev.py` / `test/` / `skills/x-req/SKILL.md` / `.gitignore`）已提交。
  2. **OpenSpec 变更 `xreq-instructions-engine` 已归档**（`openspec archive`），即 `openspec/specs/xdev-task-artifact-engine/spec.md` 与 `openspec/specs/xreq-lean-planning/spec.md` 已作为主 spec 存在。本单的 delta spec 会 MODIFY 这两个 capability——归档前就写 MODIFIED 会踩"并行 delta 覆盖"的坑。
- **提交拆分**（用户硬性偏好，不混提交）：
  1. commit A：`tools/xdev.py`（verify 子命令 + V 规则调整）+ `skills/x-req/templates/`、`skills/x-dev/templates/dev-report-template.md`（机器契约与校验器必须同步落地，视作一体）+ `test/`
  2. commit B：`skills/` 行为改动（x-req / x-dev / x-verify / x-qa-gate / x-fix / x-cr / x-spec / x-multi-llm-align 修改；x-qdev、x-plan 删除）
  3. commit C：发行面文案（`README.md`、`README_zh.md`、`install.sh`、`.codex-plugin/plugin.json` 示例命令）
- **禁止事项**：
  - 不做向后兼容：qdev 直接删，不留 alias/重定向 skill；dev-report 旧表格式不做双格式解析
  - 不动 capability 归档自动化 / delta 指纹（那是第③步）；不动 audit 系列
  - 不自作主张新增数值常量、超时默认值——方案未定义的数值一律列问题问用户
  - `dev-pipeline/tasks/` 与 `openspec/changes/archive/` 下的历史档案一律不动
- **测试风格**：标准库 unittest、零第三方依赖、fixture 用临时目录。运行 `python3 -m unittest discover -s test`。

---

## 1. 背景与目标（为什么做）

第①步已完成：x-req 走 scaffold/instructions/validate 闭环，主 agent 亲写，产物瘦身。本单解决剩余两大浪费源，并按"路由公理"完成流程统一：

1. **verify 是 token 大头**：现在 x-verify 由 LLM 读 dev-report 命令清单 + README 用例，逐条人肉复跑比对。复跑命令、比 exit code、比输出片段是纯机械活——沉进 `xdev.py verify`，LLM 只诊断失败项。
2. **qa-gate 输入过肥 + 假 P0 引发无效 fix 轮**：reviewer 现在读全量产物；且缺"置信度降级"纪律。裁剪输入、立降级规则。qa-gate 还欠着上一单记账的债（design.md 已备忘）：changelog 必读输入、Context Completeness 项、reviewer reference 输入、通关写 changelog 动作，全部清除。
3. **qdev 退役（用户已拍板：一次性删掉）**：设计依据是路由公理——流程重量 = f(风险)，不是 f(入口选择)。qdev 当初存在是因为完整链路固定成本高；①②之后固定成本消失（scaffold 一条命令、产物随规模缩、verify 是脚本），第二条流程只剩维护成本。qdev 唯一必须活下来的资产是 **Q0-Q3 风险定级**——从"选哪个 skill"变成 task 的数据字段 `risk:`，全链读它路由。
4. **验收区升级 Scenario 格式**：README 的验收从"清单 + 用例散文"改成 Requirement/Scenario（GIVEN/WHEN/THEN）结构——每条场景是一条可判定契约，同时成为 verify 的覆盖对账对象。

量化目标（验收对照）：verify 环节 LLM 零参与（全过时无任何 LLM 复跑动作）；x-verify SKILL ≤ 60 行；x-qa-gate SKILL ≤ 170 行（现 226）；`skills/` 内 qdev 引用清零。

---

## 2. 现状盘点（改之前长什么样）

```
tools/xdev.py                    # validate(V1-V11) / status / graph / instructions / scaffold
skills/x-verify/SKILL.md         # 104 行：LLM 复跑 dev-report 命令表 + README smoke/e2e，两处清单
skills/x-qa-gate/SKILL.md        # 226 行：风险路由(default RC/high R1-R3)、qdev 专属门禁路线、
                                 #   changelog 必读+通关写 changelog（上单遗留债，见其 design.md 145 行）
skills/x-qa-gate/references/     # rc-unified / r1 / r2 / r3（各自带必读清单，含 changelog、qdev 路线）
skills/x-qdev/                   # 【本单整目录删除】SKILL + references/execution-rules + templates/(README, dev-report)
skills/x-plan/                   # 已废弃重定向壳【本单删除，决策点见 T9】
skills/x-dev/templates/dev-report-template.md
                                 # 已有「验证命令清单」markdown 表（命令/工作目录/预期 exit/关键输出片段）
                                 #   和「风险等级 risk: default/high」——本单把两者分别改造/收拢
skills/x-req/templates/README.md # 含 ## DoD（验收清单）+ ## Smoke / E2E 验收用例（### 自动化测试责任）
qdev/x-plan 引用散布：skills/{x-req,x-dev,x-verify,x-fix,x-spec,x-multi-llm-align}/、
  skills/x-cr/references/auto-loop-mode.md（整张 qdev 路由表）、
  README.md / README_zh.md（首体验章节以 /x-qdev 为主角）、install.sh（3 行）、
  .codex-plugin/plugin.json（示例命令 "x-qdev add dark mode..."）
```

---

## 3. 统一流程的目标形态（先看全景再看任务）

```
用户请求 → x-req
  ├─ 定级 risk: Q0|Q1|Q2|Q3（判定标准见 T5，写入 README 头部，用户可显式覆盖）
  ├─ Q0/Q1：不停确认，lite 产物，直接续接 x-dev
  └─ Q2/Q3：一次确认（确认项含 risk），Y 后默认续接 x-dev（用户答"只出文档"则停）
x-dev：按 checklist 实现（引擎算并行批次）→ 写 dev-report（含 verify 块）
  └─ 收尾自动跑 python3 tools/xdev.py verify <task-dir>
      ├─ 有 fail / uncovered → x-fix 闭环（3 轮上限不变）
      └─ 全过 → Q0/Q1 完成汇报；Q2/Q3 续接 x-qa-gate
x-qa-gate：Q2 → RC 单 reviewer；Q3 → R1→R2→R3 串行 → 有发现 → x-fix → 增量复审
归档回流（第③步，本单不做）
```

流程是常量，产物是变量：Q0 的 README 可能 8 行、checklist 1 行、verify 1 条命令；Q3 全量。命令与证据纪律完全相同。

---

## 4. 改动总览（模块 → 职责 → 文件）

| # | 模块职责 | 文件 | 动作 |
|---|---------|------|------|
| T1 | verify 引擎：解析 dev-report verify 块、复跑、比对、场景覆盖对账 | `tools/xdev.py` | 新增子命令 |
| T2 | dev-report 立法：验证命令清单改 fenced `verify` 块；删 risk 字段（真源移 README） | `skills/x-dev/templates/dev-report-template.md` | 重写两节 |
| T3 | README 验收区改 Requirement/Scenario 结构 + `risk:` 头部字段 | `skills/x-req/templates/README.md`、`templates/confirmation.md` | 修改 |
| T4 | 校验器同步：V11 改必需章节集 + risk 感知；新增 V12 验收结构 | `tools/xdev.py` | 修改+新增 |
| T5 | x-req：risk 定级并入 + Q0/Q1 免确认 + 续接 x-dev | `skills/x-req/SKILL.md` | 修改 |
| T6 | x-dev：写 verify 块 + 收尾自动 verify + 按 risk 续接 gate | `skills/x-dev/SKILL.md`、`references/execution-rules.md` | 修改 |
| T7 | x-verify 薄壳化：跑引擎、只诊断失败、无发现不产报告 | `skills/x-verify/SKILL.md`、`templates/verify-report-template.md` | 重写 |
| T8 | x-qa-gate 重构：清 changelog 债 + 删 qdev 路线 + risk 读字段 + 输入裁剪 + 置信度降级 | `skills/x-qa-gate/SKILL.md`、`references/{rc-unified,r1,r2,r3}*.md` | 重写 |
| T9 | qdev/x-plan 退役 + 全仓引用改写 | `skills/x-qdev/`、`skills/x-plan/`、x-fix/x-cr/x-spec/x-multi-llm-align 引用处 | 删除+修改 |
| T10 | 测试 | `test/test_xdev_verify.py`（新）、既有测试调整 | 新增 |
| T11 | 发行面文案：首体验改 x-req、命令清单、Codex 示例 | `README.md`、`README_zh.md`、`install.sh`、`.codex-plugin/plugin.json` | 修改 |

---

## 5. 详细设计

### T1 `xdev.py verify` 子命令

```
python3 tools/xdev.py verify <task-dir> [--json] [--only <id>]
```

输入：`<task-dir>/dev-report*.md`（取最新一份；不存在 → 退出码 2，提示先跑 x-dev）中的全部 fenced `verify` 块。

每块语法（`key: value` 行，未知 key 报解析错误）：

````
```verify
id: S1                          # 必填，本报告内唯一
scenario: 进程首次出现            # 可选，回指 README 验收场景名（覆盖对账用）
cmd: python3 -m unittest discover -s test   # 必填（auto 时）；shell 执行
cwd: .                          # 可选，相对 repo 根，缺省 = repo 根
expect_exit: 0                  # 可选，缺省 0
expect_contains: OK             # 可选，可多行重复；stdout+stderr 合并后做子串匹配
timeout: 120                    # 可选，秒；缺省不限时。模板不预填数值，由写报告者按命令实况填
mode: auto                      # 可选 auto|manual，缺省 auto；manual 块可省 cmd，必须给 steps
steps: 打开设置页手动切换深色模式    # manual 专用，人工步骤描述
```
````

行为：
1. 逐块执行 auto 项：跑 `cmd`，比对 exit code 与全部 `expect_contains`
2. manual 项不执行，归入 `manual` 清单
3. **场景覆盖对账**：解析 README 验收区全部 `#### Scenario:`；标记 `验证: auto` 的场景若没有任何 verify 块以 `scenario:` 回指 → 记入 `uncovered`
4. 输出 JSON：`{"pass": [...], "fail": [{"id","cmd","exit_code","expected_exit","missing_contains","output_tail"}], "manual": [...], "uncovered": [...]}`；`output_tail` 为合并输出的末尾若干行（条数写成模块级常量并注释语义，不散落魔法数）
5. 退出码：**0** = 无 fail 且无 uncovered；**1** = 存在 fail 或 uncovered；**2** = 用法 / IO / verify 块解析错误（含 id 重复、auto 缺 cmd、未知 key）

工具只报事实，不写任何报告文件，不递增 fix-counter（那是 skill 层的事）。

### T2 dev-report 模板立法

- 「验证命令清单」markdown 表整节替换为 verify 块区：模板给 1 个 auto 示例 + 1 个 manual 示例（示例即上文语法样例；`timeout` 示例行留空说明为可选，不预填数值）
- 保留三条硬规则文字（本节是 verify 引擎的输入；至少一条测试类命令，无测试框架必须写 `no-test-framework: true` + 理由；README auto 场景必须有回指块）
- **删除「风险等级」节**：risk 真源移到 task README 头部（见 T3）；原"高危判据"文字并入 x-req 的 Q3 定级标准（见 T5），此处不再保留副本
- 「自检结论」中 x-qdev 字样删除

### T3 README 模板：risk 字段 + 验收区 Scenario 化

头部字段区新增一行：`risk: Q0|Q1|Q2|Q3`（必填，x-req 定级写入；含义速查注释一行，正源在 x-req SKILL）。

`## DoD（验收清单）` 与 `## Smoke / E2E 验收用例` 两节合并为一节 `## 验收`，结构：

```markdown
## 验收

### Requirement: <行为域名>
<一句话需求描述，SHALL/MUST 措辞>

#### Scenario: <场景名>
- **GIVEN** <前置状态，可省>
- **WHEN** <触发条件>
- **THEN** <可观察结果>
- 验证: auto        # auto = dev-report 必须有 verify 块回指本场景名；manual = 人工验收

### 自动化测试责任
<不变：x-dev 按改动补齐单元/契约/边界测试并将命令写入 dev-report verify 块>
```

DoD 概念不消失，收敛为一句定义（写进模板注释与 x-req instruction）："DoD = 验收节全部场景 pass（auto 由 verify 引擎判定，manual 由用户确认）+ checklist 全部 done"。confirmation.md 确认项同步：加 risk 定级项，DoD/用例预览改为场景预览。

### T4 校验器同步（V11 调整 + V12 新增）

- **V11 必需章节集**（Q2/Q3）：`核心目标`、`需求要点`、`涉及模块`、`架构拆分策略`、`技术设计`、`验收`（替换原 `DoD` 与 `Smoke / E2E 验收用例` 两项）；`自动化测试责任` H3 改为在 `验收` 区内查找。原"fenced 命令块或 manual 标记"检查移交 V12。
- **V11 risk 感知**：读 README 头部 `risk:`——缺失或值不在 {Q0,Q1,Q2,Q3} → issue；Q0/Q1 的必需章节集收缩为 `核心目标`、`验收`（其余章节可省，存在则不报错）。
- **V12 验收结构**（task 包新规则，复用 V3 的 Requirement/Scenario 解析逻辑）：`验收` 区内每条 `### Requirement:` ≥1 个 `#### Scenario:`；每个 Scenario 含 WHEN 与 THEN（GIVEN 可省）；每个 Scenario 末行必须有 `验证: auto` 或 `验证: manual` 标记。
- xdev.py 顶部 docstring 规则编号表同步 V11 新文字与 V12。
- 上一单的 e2e/坏 fixture 按新契约更新。

### T5 x-req 改动（在 56 行基础上小幅增量，总量仍 ≤ 100 行）

1. **步骤 1 增加 risk 定级**（qdev 的 Q0-Q3 迁入，判定标准收拢为唯一正源）：
   - Q0 琐碎：单文件、无行为分支变化（改文案/样式/配置值）
   - Q1 低危：局部小功能或小修复，无跨模块契约变化
   - Q2 中危：新功能/多文件/有契约或状态变化
   - Q3 高危：命中任一判据——鉴权/权限/加密；不可逆数据写入/迁移；公开 API/协议/schema 变更；并发/状态机/缓存一致性（原 dev-report 高危判据原文迁入）
   - 用户显式指定 risk 时以用户为准；定级写入 README 头部
2. **Q0/Q1 免确认**：跳过一次确认，直接 scaffold + lite 填写（满足 V11 Q0/Q1 章节集）+ 续接 x-dev；完成汇报时附一句定级依据
3. **Q2/Q3**：确认项含 risk 定级；Y 后默认续接 x-dev，用户回复"只出文档"则停
4. 删除"小型单模块任务转 /x-qdev"路由与 Q3 promotion 模式（统一流程内不存在升级换轨——risk 改字段 + 补产物即可）；x-spec 转介条件保留
5. instruction 常量（xdev.py 内 README_INSTRUCTION/CHECKLIST_INSTRUCTION）同步验收区新结构与 risk 语义

### T6 x-dev 改动

1. 执行规则新增：实现每个 auto 场景时在 dev-report 写对应 verify 块（`scenario:` 回指场景名）；补齐的单元/契约/边界测试命令也写成 verify 块
2. 收尾流程：跑 `python3 tools/xdev.py verify <task-dir> --json` → 有 fail/uncovered → 进 x-fix（沿用现有回流规则与 3 轮上限）→ 全过 → 按 README `risk:`：Q0/Q1 完成汇报；Q2/Q3 续接 x-qa-gate
3. 删除 dev-report 风险等级填写职责（字段已移 README）；dispatch 模板与报告路由中 qdev 字样清除

### T7 x-verify 薄壳化（≤ 60 行）

保留 Gate ① 定位与对话回执，流程改为：

1. 跑 `python3 tools/xdev.py verify <task-dir> --json`
2. 全过（exit 0）：对话一行回执（pass N / manual M 待人工），**不产报告文件**；manual 清单列给用户
3. 有 fail/uncovered：LLM 只读失败项的 `output_tail` 做诊断（可用 `--only <id>` 重跑单条核实），按模板写失败报告到 `reports/verify/`（模板同步为只含失败项 + 诊断 + uncovered），交 x-fix；fix-counter 与 3 轮上限规则保持不变
4. 解析错误（exit 2）：指出 dev-report verify 块格式问题，退回 x-dev 修报告，不计 fix 轮

删除"两处必跑清单"（README 用例已由场景对账覆盖，不再由 LLM 二次比对）。

### T8 x-qa-gate 重构（≤ 170 行）

1. **清上单记账的债**（其 design.md 145 行原文）：changelog 必读输入、Context Completeness 项、reviewer reference 输入、通关写 changelog 动作，全部移除；r1/r2/r3/rc 必读清单同步
2. **删 qdev 专属路线**：rc-unified 的"qdev 完整门禁把 plan/checklist 标 N/A"等全部路线分支
3. **风险路由读 README `risk:`**：Q2 → RC 单 reviewer 一轮列全；Q3 → R1→R2→R3 串行；Q0/Q1 不属于 gate 流程（被显式调用时按 Q2 处理并说明）。原"default/high"术语全文替换为 Q2/Q3
4. **输入裁剪**（dispatch prompt 列精确文件与节，明示不读清单外内容）：
   - RC：diff + README `验收`/`架构拆分策略` 节 + dev-report
   - R1 spec 一致：diff + README `需求要点`/`验收` 节
   - R2 边界：diff + README `技术设计`/`架构拆分策略` 节
   - R3 测试真实性：diff + dev-report verify 块 + 测试文件
5. **置信度降级纪律**（写入 SKILL 与全部 reference 的报告规则）：能指认文件行号且可复现 → 才可评 P0；不确定一律降一级；每条发现必须带 file:line 与可执行修复建议，禁止"建议关注"类空话
6. fix 闭环、增量复审、与 verify 共享 3 轮上限：不变

### T9 qdev / x-plan 退役与全仓引用改写

- 删除 `skills/x-qdev/` 整目录、`skills/x-plan/` 整目录（**决策点**：x-plan 是废弃重定向壳，按用户"拒绝过度兼容"原则一并删；若用户 review 时要留，恢复该目录即可，其余不受影响）
- 引用改写（不是简单删词，是把"qdev/完整流程"双轨话术改成"risk 路由"单轨话术）：
  - `skills/x-fix/SKILL.md`：qdev 链路描述改 risk 路由
  - `skills/x-cr/references/auto-loop-mode.md`：qdev 路由表整段重写为 Q0-Q3 路由表；顺带清除 x-cr 的 changelog 引用（上单 design 备忘）
  - `skills/x-spec/SKILL.md`：三处入口路由（"小功能走 x-qdev"→"x-req 定级 Q0/Q1"）
  - `skills/x-multi-llm-align/SKILL.md`：下一步清单去 x-qdev
  - `skills/x-verify/SKILL.md`、`skills/x-qa-gate/`：随 T7/T8 重写覆盖
- 收尾全仓 grep `qdev`、`x-plan`：`skills/`、`install.sh`、`.codex-plugin/`、`README*.md` 零命中（`dev-pipeline/tasks/`、`openspec/` 历史档案除外）

### T10 测试（新文件 `test/test_xdev_verify.py` + 既有调整）

1. verify 块解析：合法块、多 expect_contains、manual 块省 cmd、未知 key/重复 id/auto 缺 cmd → 解析错误（exit 2）
2. 执行与比对：exit 不符 → fail；expect_contains 缺失 → fail（列出 missing）；全过 → exit 0；timeout 字段生效（用 `sleep` 类命令 + timeout: 1 验证，fixture 内显式写 1 并注释这是测试专用值）
3. 场景对账：README auto 场景无回指块 → uncovered + exit 1；manual 场景不要求块；场景名匹配按 strip 后全等
4. V11 新章节集 + risk 感知（Q0 lite 通过 / Q2 缺技术设计 issue / risk 缺失或非法 issue）；V12 好坏 fixture（缺 WHEN/THEN、缺 验证: 标记、Requirement 无场景）
5. e2e：scaffold → 填 Q2 最小合法包（新验收结构）→ validate 0 issue → 写含 1 pass + 1 manual 的 dev-report → verify exit 0
6. 既有 48+ 测试全数调整通过（V11 契约变更处按新契约改 fixture）

### T11 发行面文案

- README / README_zh：首体验章节主角从 `/x-qdev` 换成 `/x-req <小需求>`（演示 Q1 免确认直达完成）；命令总表删 x-qdev/x-plan；"统一状态标记"等处随新契约更新；风险分流说明改为 risk 字段语义
- `install.sh`：Get started / Commands / Legacy 三行更新（Legacy 行删 x-plan 映射）
- `.codex-plugin/plugin.json`：示例命令改 x-req

---

## 6. 明确不做（范围守卫）

- 不做 capability 归档自动化、delta 指纹、`docs/specs/` 主 spec 目录（第③步）
- 不动 `skills/x-audit-*`；x-cr 只动 auto-loop-mode 路由表与 changelog 引用，贝叶斯调查主体不动
- 不改 fix-counter 机制与 3 轮上限数值
- 不做版本号 bump 与 CHANGELOG 发布记录（发布走独立流程）
- 历史 task、已归档 OpenSpec change 不迁移不清理

---

## 7. DoD（验收清单，全部可复跑）

| # | 验收项 | 复跑命令 | 预期 |
|---|--------|---------|------|
| 1 | 全部单测通过 | `python3 -m unittest discover -s test` | OK，0 失败 |
| 2 | verify 好样本 | 对 T10-5 的 e2e fixture 跑 `verify --json` | exit 0，fail/uncovered 为空，manual 列出 |
| 3 | verify 坏样本 | fixture 含 exit 不符 + 片段缺失 + uncovered | exit 1，三类各至少 1 条且字段完整 |
| 4 | verify 解析错误 | fixture 含重复 id / auto 缺 cmd | exit 2，指明块与原因 |
| 5 | V11/V12 | Q0 lite 通过；Q2 全集缺项、risk 缺失、场景缺 WHEN/THEN、缺 `验证:` 标记各出 issue | 单测覆盖 |
| 6 | x-verify 瘦身 | `awk 'END{print NR}' skills/x-verify/SKILL.md` | ≤ 60 |
| 7 | x-qa-gate 瘦身 | 同上 qa-gate | ≤ 170 |
| 8 | changelog 债清偿 | `grep -rn "changelog" skills/` | 0 命中 |
| 9 | qdev/x-plan 清除 | `grep -rln "qdev\|x-plan" skills/ install.sh .codex-plugin/ README.md README_zh.md` | 0 命中（历史档案除外） |
| 10 | 目录删除 | `ls skills/` | 无 x-qdev、无 x-plan |
| 11 | OpenSpec 校验 | `openspec validate <本单 change> --strict` | 通过 |
| 12 | 提交拆分 | `git log --oneline` | A/B/C 三个独立 commit，文件边界如第 0 节 |

---

## 8. 风险与注意

- **场景名回指是字符串耦合**：README 场景改名而 dev-report 未同步 → uncovered 误报。这是特性不是缺陷（对账本来就该报），但 verify 输出信息里要把"README 场景清单 vs 块回指清单"都列出来方便肉眼对齐
- **Q0/Q1 免确认是行为变化**：x-req SKILL 里必须写明"完成汇报时附定级依据 + 用户可随时说'按 Q2 走'升级"，防止免确认被滥用于实际中危改动
- **V11 章节集变更会让上一单刚写的 fixture 大面积过期**：这是预期内返工，按新契约改，不做双契约兼容
- **x-cr 的 `/x-cr -> /x-qa-gate` legacy 映射**（install.sh Legacy 行）：x-cr 现在是独立调查 skill，不是 qa-gate 别名——更新文案时顺带修正这句陈旧描述，不要照抄
- 执行中任何需要新数值（超时默认、输出截断行数之外的）→ 停下问用户，不要自填

## 9. 交付材料（交回 review 时提供）

1. OpenSpec change 目录（proposal/design/specs delta/tasks，MODIFIED 基于已归档的两个主 spec）
2. `git log --oneline` 与 A/B/C 三 commit 的 `git show --stat`
3. `python3 -m unittest discover -s test` 完整输出
4. e2e fixture 的 `verify --json` 实际输出（好样本 + 坏样本各一份）
5. x-verify / x-qa-gate 新旧行数对比；qdev/x-plan/changelog 三个 grep 的实际结果
6. 每项偏离本方案的决定及理由（含 T9 x-plan 决策点的处理）
