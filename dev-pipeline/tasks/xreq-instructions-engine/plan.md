# xreq-instructions-engine 开发方案

> 方案 A 第①步：x-req 产物瘦身 + instructions/scaffold 机制。
> 本文档自包含，执行方（LLM）不需要任何对话上下文即可开工。
> 完成后交回原方案作者做 review，交付材料清单见文末第 8 节。

---

## 0. 执行须知（先读）

- **仓库**：`/Volumes/machub_app/proj/x-dev-pipeline`（本文件所在仓库）
- **前置条件**：本仓库当前有一批未提交改动（xdev-orchestration-engine 这单：`tools/xdev.py` 的 status/graph 引擎 + `skills/x-dev/SKILL.md` 等）。**本方案构建在这批改动之上**（会继续扩展 `tools/xdev.py`）。开工前确认这批改动已由用户提交收口；若未提交，先停下向用户确认，不要混着改。
- **提交拆分**（用户硬性偏好，不混提交）：
  1. commit A：`tools/xdev.py` 新子命令 + `test/` 新测试（纯代码）
  2. commit B：`skills/` 下 SKILL.md 与模板改动（产品行为）
  3. commit C：仓库级 `README.md` / `README_zh.md` 文档同步（纯文档）
- **禁止事项**：
  - 不做向后兼容垫片（deprecated alias / 兼容分支）——破坏性变更直接做
  - 不动 `skills/x-verify`、`skills/x-qa-gate`、`skills/x-fix`、`skills/x-cr`、audit 系列（那是方案 A 第②步）
  - 不做 capability / delta spec / archive（那是第③步）
  - 不自作主张新增数值常量、超时、默认值——方案未定义的数值一律列问题问用户
- **测试风格**：沿用 `test/test_xdev_orchestration.py`——标准库 unittest、零第三方依赖、fixture 用临时目录构造。运行方式 `python3 -m unittest discover -s test`。

---

## 1. 背景与目标（为什么做）

x-dev-pipeline 正在借鉴 OpenSpec 的核心思路做立法层改造：**机械活沉进脚本（`tools/xdev.py`），LLM 只做判断活**。已完成的部分：status/graph 引擎（读 checklist 算状态和并行批次）、validate V1-V7（spec 包结构校验）。

本单解决的是 x-req 环节"写产物"和"审产物"两端的浪费：

1. **同一内容三过手**：现在 x-req 是"主 agent 整理确认项 → 复制全文进子 agent（agent1）的自包含 prompt → agent1 写完 → 主 agent 读回产出审核"。同一份需求要点在 LLM 上下文里流过 3 遍。改成**主 agent 直接填空**，砍掉 agent1 往返。
2. **格式法律写在 SKILL.md 散文里**：SKILL.md 每次触发全文加载（235 行），其中大量是表格列名、状态枚举这类格式规则。改成 OpenSpec 式的 **instructions 按需下发**：要写哪个产物，才把哪个产物的模板和规则下发。
3. **审核清单一半是机械项**：x-req 审核 8 条里"三文件一致 / 模板结构 / 状态符号 / 优先级枚举"是机械可判定的，现在由 LLM 花 token 判。改成 `xdev.py validate` 新增 task 包规则（V8-V11）机械拦截，LLM 审核只留 4 条判断项。
4. **产物冗余**：changelog.md 是冗余真源（git log + dev-report 已覆盖同一信息，req 极少二次修改），删除；diagram.md 降级为可选产物。

量化目标（验收时对照）：x-req SKILL.md ≤ 100 行；单次 x-req 流程子 agent 派发次数从 1-2 次降到 0；机械格式问题由 validate 拦截而非 LLM 审核报告。

---

## 2. 现状盘点（改之前长什么样）

```
tools/xdev.py                 # 已有子命令：validate（V1-V7，spec 包）、status、graph
test/test_xdev_orchestration.py
skills/x-req/SKILL.md         # 235 行，含 agent1 派发流程 + 全部产出规则散文
skills/x-req/templates/
├── README.md                 # task 需求文档模板（章节含：核心目标/需求要点/涉及模块/
│                             #   架构拆分策略/技术设计/DoD（验收清单）/Smoke / E2E 验收用例/
│                             #   自动化测试责任/风险/文件导航）
├── dev-checklist.md          # 已机器可解析化（列契约 # | 任务 | 涉及文件 | 依赖 | 状态 | fix，
│                             #   token+emoji 双轨状态）
├── diagram.md                # mermaid 模块图模板
├── changelog.md              # 【本单删除】
├── confirmation.md           # 一次确认消息模板（保留）
└── subagent-completion.md    # agent1 回报模板【本单删除】
skills/x-qdev/templates/changelog.md   # 【本单删除，见 T6 决策点】
skills/x-dev/SKILL.md         # 有"changelog 追加"职责【本单移除该职责】
```

---

## 3. 改动总览（模块 → 职责 → 文件）

| # | 模块职责 | 文件 | 动作 |
|---|---------|------|------|
| T1 | 产物注册表 + instructions 子命令（确定性工具层） | `tools/xdev.py` | 新增 |
| T2 | scaffold 子命令（骨架落盘，幂等） | `tools/xdev.py` | 新增 |
| T3 | validate 扩展 task 包规则 V8-V11 | `tools/xdev.py` | 扩展 |
| T4 | 产物瘦身：删 changelog / subagent-completion 模板，diagram 转可选 | `skills/x-req/templates/` | 删除+微调 |
| T5 | x-req 流程重写：主 agent 亲写 + 机械校验 + 4 条判断自审 | `skills/x-req/SKILL.md` | 重写 |
| T6 | 连带引用清理（x-dev / x-qdev 的 changelog 职责与引用） | `skills/x-dev/`、`skills/x-qdev/` | 修改 |
| T7 | 单元测试 + e2e fixture | `test/test_xdev_artifacts.py`（新文件） | 新增 |
| T8 | 仓库文档同步 | `README.md`、`README_zh.md` | 修改 |

---

## 4. 详细设计

### T1 产物注册表 + `instructions` 子命令

在 `tools/xdev.py` 顶部新增注册表（单 schema，用 Python dict，不引入 yaml）：

```python
# 产物注册表：x-req task 包的产物图。
# template = 结构骨架（相对本仓库根，经 __file__ 解析，不依赖 cwd）
# instruction = 填写规则正文（从原 SKILL.md 的"XX 产出规则"章节迁入，见下）
# requires = 依赖产物 id（写作顺序约束：先读依赖再写自己）
ARTIFACTS = {
    "readme": {
        "generates": "README.md",
        "template": "skills/x-req/templates/README.md",
        "requires": [],
        "instruction": README_INSTRUCTION,
    },
    "dev-checklist": {
        "generates": "dev-checklist.md",
        "template": "skills/x-req/templates/dev-checklist.md",
        "requires": ["readme"],
        "instruction": CHECKLIST_INSTRUCTION,
    },
    "diagram": {   # 可选产物：scaffold 默认不产，instructions 按需取
        "generates": "diagram.md",
        "template": "skills/x-req/templates/diagram.md",
        "requires": ["readme"],
        "instruction": DIAGRAM_INSTRUCTION,
    },
}
```

模板路径解析：`PLUGIN_ROOT = Path(__file__).resolve().parent.parent`，模板 = `PLUGIN_ROOT / entry["template"]`。这样无论 cwd 在用户项目哪里、插件装在哪里都能找到模板。

**instruction 常量的内容来源**（执行方从现 SKILL.md 迁移，迁移后 SKILL.md 删除原文）：

- `README_INSTRUCTION` ← SKILL.md「README.md 产出规则」+ 审核项里与 README 相关的判断提示（要点必须逐条落进 README、DoD 必须可客观判定、Smoke/E2E 优先命令化且人工用例标 manual、自动化测试责任写明由 x-dev 补齐）
- `CHECKLIST_INSTRUCTION` ← SKILL.md「dev-checklist.md 产出规则」+「架构驱动拆分」细则（P0 放契约/边界入口/核心状态，P1 放适配层/集成/主要验证，P2 放文档增强；🔍 标记条件：核心业务逻辑/持久化迁移/安全/跨模块集成/公共 API；同优先级按依赖分组，无写冲突可并行）
- `DIAGRAM_INSTRUCTION` ← SKILL.md「diagram.md 产出规则」（README 是文字事实源，diagram 是只读视图，节点须与 README 涉及模块一致）

每条 instruction 末尾统一追加一句：**"以上规则与模板内 HTML 注释是给你的约束，不是产物内容——填写时删除模板注释，不要把规则文字抄进产物。"**

**命令**：

```
python3 tools/xdev.py instructions <artifact-id> --task <task-dir> [--json]
```

输出 JSON（`--json`；无该 flag 时人类可读格式化输出同样信息）：

```json
{
  "artifact": "dev-checklist",
  "output_path": "dev-pipeline/tasks/foo/dev-checklist.md",
  "exists": false,
  "template": "<模板文件全文>",
  "instruction": "<填写规则全文>",
  "requires": ["readme"],
  "dependencies": [
    {"id": "readme", "path": "dev-pipeline/tasks/foo/README.md", "exists": true}
  ]
}
```

- `artifact-id` 不在注册表 → 退出码 2，报错并列出合法 id
- 依赖产物文件不存在时 `dependencies[].exists=false`，命令本身不报错（写作顺序由 skill 层守，工具只报事实）

### T2 `scaffold` 子命令

```
python3 tools/xdev.py scaffold <task-dir> [--with-diagram] [--json]
```

行为：

1. 创建 `<task-dir>`（含父目录）
2. 落盘 README.md + dev-checklist.md 骨架（复制注册表模板原文；README 首行 `# <task-name>` 占位替换为目录名）；`--with-diagram` 时追加 diagram.md
3. **幂等**：目标文件已存在则跳过不覆盖（这是硬规则——scaffold 永不覆盖已有内容），输出 created / skipped 两个清单
4. 不再产出 changelog.md（产物集里没有它）

退出码：0 正常（含全部 skipped）；2 用法/IO 错误。

### T3 validate 扩展：task 包规则 V8-V11

**包类型识别**：validate 的 target 目录含 `dev-checklist.md` → 判定为 task 包，走 V8-V11 + 通用 V2（路径引用规则复用现有实现）；否则维持现有 spec 包逻辑（V1-V7）不变。自动发现逻辑不变（task 包只走显式 target，不加入自动发现，避免扫全部历史 task）。

新规则（编号接续现有 V 系列，规则文字加进 xdev.py 顶部 docstring 的规则编号表）：

- **V8 task 包文件齐全**：README.md 与 dev-checklist.md 必须存在。diagram.md 可选，不查存在性。changelog.md 若存在不报错（历史遗留，不迁移不清理）。
- **V9 checklist 结构合法**：复用 status 子命令的既有解析器（不重复实现）——表头列必须等于契约 `# | 任务 | 涉及文件 | 依赖 | 状态 | fix`；状态列必须落在 token+emoji 双轨枚举内（纯 emoji 旧格式按既有兼容降级逻辑放行）；依赖列引用的任务编号必须在本表中存在。依赖环不在 V9 重复检测（graph 子命令已负责）。
- **V10 diagram 与 README 一致**：仅当 diagram.md 存在时触发。mermaid 节点标签集合与 README「涉及模块」清单做词法比对（实现风格参照现有 V6 的模块清单比对），README 有而 diagram 无 → finding；diagram 有而 README 无 → finding。
- **V11 README 必备章节**：按模板标题词法检查以下二级标题存在：`核心目标`、`需求要点`、`涉及模块`、`架构拆分策略`、`技术设计`、`DoD（验收清单）`、`Smoke / E2E 验收用例`；`自动化测试责任` 为三级标题，按三级查。另查：Smoke/E2E 段内至少存在 1 个 fenced code block（可复跑命令）或 1 处 `manual` 标记——两者都没有 → finding。

### T4 模板层改动

- **删除** `skills/x-req/templates/changelog.md`
- **删除** `skills/x-req/templates/subagent-completion.md`
- `skills/x-req/templates/README.md`：「文件导航」段删去 changelog 条目；如提及 diagram，标注"（可选产物）"
- `skills/x-req/templates/confirmation.md`：删去与 changelog / agent1 相关的表述（如有）；确认项结构不变（一次确认流程保留）
- `skills/x-req/templates/dev-checklist.md`：内容不动（已是机器契约），仅当其中提及 changelog 时删除该提法

### T5 x-req SKILL.md 重写

目标 ≤ 100 行（现 235 行）。frontmatter 的 description 保留触发场景语义，正文按以下骨架重写：

```
# x-req 需求+开发准备

核心定位（5 行内）：回答"做什么 + 架构上怎么切 + 怎么算完成"，产出交给 x-dev 执行。
产物：README.md（必产）+ dev-checklist.md（必产）+ diagram.md（可选）。无 changelog。

## 流程

0. 新建 vs 更新：task 目录已存在 → 更新模式（读现有产物，对齐变更 diff，确认后原地更新，
   更新记录写 README 头部 `updated: <日期> <一句话>`）。qdev Q3 升级（promotion）：
   读原 qdev task 的 README.md 与 dev-report.md（不再有 changelog），新建 <name>-full，
   README 头部写 source-qdev 指向。
1. 理解任务（判断活，保留现版要点但压缩）：确定归属 spec（docs/spec/ 匹配；无则提示）；
   架构归属检查（找模块边界类，禁止散装函数跨模块调用，找不到归属就建议新建 XxxService
   或先跑 x-spec，由用户拍板）；模糊则一次性问 1-3 个关键问题；明显太大（>10 项、跨多模块
   架构改造）建议先 x-spec。
2. 一次确认：按 templates/confirmation.md 结构一次性展示，等用户 Y / 改 / 取消。
3. 骨架 + 填空（用户 Y 后，主 agent 亲写，不派子 agent）：
   a. python3 tools/xdev.py scaffold dev-pipeline/tasks/<task-name>/
      （涉及模块 ≥3 或用户点名要图时加 --with-diagram）
   b. 对每个产物按 readme → dev-checklist（→ diagram）顺序：
      python3 tools/xdev.py instructions <artifact-id> --task <task-dir> --json
      读 dependencies 里已存在的文件 → 按 template 结构填写 → instruction 与模板注释是
      约束不是内容，填完删除模板注释。
4. 机械校验：python3 tools/xdev.py validate <task-dir>
   有 finding → 修文件 → 重跑，直到 0 finding（工具拦截的是格式问题，直接修不用问用户）。
5. 判断自审（只审这 4 条，机械项已由 validate 拦截）：
   ① 确认过的需求要点每条都落进 README（漏 = 修）
   ② 每条 DoD 客观可判定
   ③ 确认过的架构归属体现在技术设计里
   ④ checklist 每个任务能从 README 架构拆分策略追溯到模块边界/契约/依赖
   发现问题直接修（主 agent 自己写的，自己修），修完重跑 validate。
6. 收尾汇报：task 路径、产物清单、validate 结论（0 finding）、自审结论、
   推荐下一步 x-dev <task-name>。

## 职责边界（压缩保留）
x-req 不负责：spec 需求包（x-spec）、代码执行（x-dev）、任务状态更新（x-dev）。
```

**明确删除的内容**：agent1 派发流程（3.1/3.2/3.3 全部）、8 条审核清单（4 条机械项进 validate，4 条判断项进上面第 5 步）、三个"产出规则"章节（迁入 T1 的 instruction 常量）、changelog 相关全部表述、subagent-completion 引用。

### T6 连带引用清理

- `skills/x-dev/SKILL.md` + `skills/x-dev/references/execution-rules.md`：移除"changelog 追加"职责及相关步骤，关键修改的记录职责统一归 dev-report（现状已记录，无需新增）
- `skills/x-qdev/SKILL.md` + 删除 `skills/x-qdev/templates/changelog.md`：qdev 产物集同步去掉 changelog（**决策点**：推荐一并删除保持全线一致——理由与 x-req 相同，git + dev-report 已覆盖；若用户 review 时否决，恢复此项即可，其余改动不受影响）
- x-req promotion mode 读取清单：从「README.md / changelog.md / dev-report.md」改为「README.md / dev-report.md」
- 定向 grep `changelog`、`subagent-completion`、`agent1`：清理 `skills/x-req/`、`skills/x-dev/`、`skills/x-qdev/` 下的活跃引用（`dev-pipeline/tasks/` 下的历史 task 文件属于档案，**不动**）
- 方案 A 第②步清理 x-qa-gate 的 changelog 必读、Context Completeness、reviewer references 和通关写入动作，并清理 x-cr 的 changelog spec 来源；本单保持这些范围外 skills 原状

### T7 测试（新文件 `test/test_xdev_artifacts.py`）

沿用既有风格（unittest + 临时目录 fixture + 直接 import xdev 测内部函数）。至少覆盖：

1. instructions：合法 id 返回全部字段且 template 非空；非法 id 退出码 2；依赖缺失时 `exists:false`
2. scaffold：首跑创建 README + dev-checklist（无 changelog）；`--with-diagram` 多产 diagram；重跑幂等（文件内容不变、退出码 0、报告 skipped）；README 首行占位替换为目录名
3. validate task 包：V8-V11 每条规则至少一个坏 fixture 触发 finding + 好 fixture 通过；含 changelog.md 的旧 task 不因 V8 报错；spec 包路径回归（V1-V7 行为不变，跑一个既有 spec fixture 确认）
4. e2e 闭环 fixture：scaffold → 程序化填入最小合法内容 → validate 退出码 0、finding 为空

### T8 仓库文档同步（单独 commit）

`README.md` / `README_zh.md`：x-req 产物清单更新（去 changelog、diagram 标可选）、x-req 命令描述更新（主 agent 亲写 + validate 机械校验）、统一状态标记章节如提及 changelog 一并修正。

---

## 5. 明确不做（本单范围守卫）

- 不动 verify / qa-gate / fix / cr / audit 任何 skill
- 不做 dev-report 命令清单立法（第②步）
- 不做 capability / delta spec / archive / 指纹校验（第③步）
- 不给 xdev.py 加配置文件、不引入第三方依赖
- 不迁移/清理 `dev-pipeline/tasks/` 下的历史 task（含它们的 changelog.md）
- 不改 x-spec 的产物模型（docs/spec 七件套维持现状）

---

## 6. DoD（验收清单，全部可复跑）

| # | 验收项 | 复跑命令 | 预期 |
|---|--------|---------|------|
| 1 | 全部单测通过 | `python3 -m unittest discover -s test` | OK，0 失败 |
| 2 | scaffold 冒烟 | `python3 tools/xdev.py scaffold /tmp/xreq-smoke --json` | 产 README.md + dev-checklist.md，无 changelog.md |
| 3 | scaffold 幂等 | 上一命令连跑两次 | 第二次退出码 0，文件内容不变，报告 skipped |
| 4 | instructions 冒烟 | `python3 tools/xdev.py instructions readme --task /tmp/xreq-smoke --json` | JSON 含 artifact/output_path/exists/template/instruction/requires/dependencies，template 非空 |
| 5 | validate 好样本 | 对 T7 的 e2e fixture 跑 `validate` | 退出码 0 |
| 6 | validate 坏样本 | 单测覆盖 | V8/V9/V10/V11 各至少 1 个 finding 用例 |
| 7 | spec 包回归 | 对既有 spec fixture 跑 `validate` | V1-V7 行为与改前一致 |
| 8 | SKILL.md 瘦身 | `awk 'END{print NR}' skills/x-req/SKILL.md` | ≤ 100 |
| 9 | agent1 清除 | `grep -rn "agent1\|subagent-completion" skills/x-req skills/x-dev skills/x-qdev` | 0 命中 |
| 10 | changelog 清除 | `grep -rln "changelog" skills/x-req skills/x-dev skills/x-qdev` | 0 命中（范围外 skills 与历史 task 档案保持原状） |
| 11 | 提交拆分 | `git log --oneline -3` | 代码 / skills / 文档 三个独立 commit |

---

## 7. 风险与注意

- **V9 复用 status 解析器**：不要复制解析逻辑，直接调用既有函数；若既有函数签名不便复用，重构为共享内部函数（保持 status/graph 行为不变，跑既有单测确认）
- **V11 章节词法检查**要容忍标题后缀差异（如 `## DoD（验收清单）` 全角括号），按"标题以关键词开头"匹配，不做全等
- **模板即真源**：模板文件内的 HTML 注释规则保持在模板里（scaffold 原样落盘，由 LLM 填写时删除）；xdev.py 的 instruction 常量只放流程性规则，不复制模板注释内容——同一规则只能有一个家
- README 模板改动会影响 V11 的标题清单——若执行中发现模板标题与本方案 V11 清单不一致，以模板现状为准并在交付说明里指出

## 8. 交付材料（交回 review 时提供）

1. `git log --oneline` 与三个 commit 的 `git show --stat`
2. `python3 -m unittest discover -s test` 完整输出
3. `xdev.py instructions dev-checklist --task <e2e-fixture> --json` 的实际输出样例
4. e2e fixture 的目录树与 validate 输出
5. 新旧 SKILL.md 行数对比；若有任何偏离本方案的决定（含 V11 标题清单调整、T6 决策点处理），逐条列出理由
