# fixes-and-metrics 开发方案（v2，依据外部审查 11 条修订）

> 两部分：**A 修改项**（三个小修，用新流程逐个跑，成为度量样本）；
> **B 挖掘度量**（transcript 挖掘脚本 + metrics 表 + 旧流程 baseline + 可选 A/B）。
> 样本 prompt 原文见文末**附录 P**，逐字使用。
> 本文档自包含；沿用既有做法：先转 OpenSpec change 交用户确认再实现。
> **归档纪律：OpenSpec change 在原方案作者验收通过之前保持活跃，不得提前 archive。**

---

## 0. 执行须知

- **仓库**：`/Volumes/machub_app/proj/x-dev-pipeline`
- **前置**：工作区 clean；57 测试全过为起点基线
- **执行顺序与 session 边界（共 5 个独立 session，样本纪律的核心）**：
  1. A1 → 2. A2 → 3. A3 → 4. B（建工具，**不填自身数据行**）→ 5. 收尾统计（回填全部行）
  每个都是**全新独立 session**，用附录 P 对应 prompt **逐字**发起；A1-A3、B 走 `/x-req` 统一入口。
  收尾统计 session 是纯统计动作，自身不入样本表——这样消除"session 自量必缺尾部"的悖论。
- **定级声明**：A1/A2 按 **Q1** 执行——依据主 spec"用户显式定级优先"通道，本方案即用户显式覆盖
  （修复+配套测试属局部修复，不因文件数升级；A2 会顺带把判据措辞修准，见其 prompt）。
  A3/B 预计 Q2，走一次确认 + RC。
- **禁止事项**：不动 capability 回流（第③步）；不做向后兼容；方案未定义数值一律问用户；
  历史 task 与已归档 change 不动
- **涉及 capability**（delta 基于 `openspec/specs/` 主 spec）：`xdev-task-artifact-engine`（A1）、
  `xreq-lean-planning`（A2，含定级判据措辞修正）、`risk-routed-development-flow`（A3）；
  Part B 新增 capability（建议名 `pipeline-cost-metrics`）

---

# Part A 修改项（先做）

## A1 修复 validate V2 对 HTML 注释的误报

**背景**：`dev-checklist.md` 模板 HTML 注释里的 `[ ](⏳▶️🟡)→todo` 等文字被 `LINK_RE` 当
markdown 链接，V2 误报"包内链接必须以 ./ 开头"（scaffold 原样目录稳定复现 3 条）。

**改法（精确到粒度）**：校验预处理阶段**移除 HTML 注释片段（span 级，含跨行 `<!-- ... -->`）**，
而不是跳过整行——"正文 `<!-- 注释 -->`"同行混排时正文必须保留并参与检查。

**验收测试矩阵**（防"整行跳过"的错误实现蒙混过关）：
1. scaffold 原样目录 → V2 issue = 0
2. 正文真实坏链接 `[x](../out.md)` → 仍触发
3. 行内混排 `[x](../bad.md) <!-- 说明 -->` → 仍触发
4. `<!-- 说明 --> [x](../bad.md)` → 仍触发
5. 跨行注释在某行中部关闭、同行尾部有坏链接 → 仍触发
6. 注释内含 ``` 围栏文字 → 不得扰乱围栏状态机（后续正常内容照常检查）

## A2 x-req 续接语义 + 确认授权 + 定级判据措辞

**背景**：三处问题一起修。① SKILL 定级表写全链直通、流程第 8 步写"输出下一步"，语义打架；
② `confirmation.md:40`"回 Y 我产出文件"未覆盖 Y 同时授权续接开发/验证/门禁（知情确认缺口）；
③ 定级表 Q2 判据"多文件"字面会把"修复+配套测试（必然两文件）"升 Q2，Q1 被架空。

**改法**：
1. SKILL 明确：Q0/Q1 完成产物后、Q2/Q3 确认 Y 后**直接继续 x-dev 流程**；确认回复"只出文档"则停
2. confirmation.md 结尾改为完整授权句：
   "以上 OK？回 **Y** = 产出文件并继续执行开发、验证与门禁；回 **只出文档** = 仅产出文件。"
3. Q2 判据"多文件"→"**跨模块或多实现点**"

## A3 qa-gate lens 收拢 + Q3 并行化 + 全仓引用同步

**背景**：四个 reference 的输出格式与降级规则重复 4 遍；Q3 串行在批量修模式下纯费墙钟。

**改法**：
1. 合并为 `references/reviewer-lenses.md`：头部"共享输出契约"节只写一遍
   （mini-report 结构/覆盖声明/发现表列/置信度降级），RC/R1/R2/R3 各一节只留输入+检查清单
   （语义原样迁移）；删原四文件
2. SKILL：Q3 三 lens **并行 dispatch**（同一冻结 diff、各自只读、prompt 带对应节），
   主 agent 聚合去重（同位置多 lens 报→合一条保留各视角理由）→ 排序 → 一次交 x-fix；
   增量复审规则不变。**文件合并 ≠ 视角合并**
3. **全仓同步清单（审查补全，逐个处理）**：
   - `CLAUDE.md` 56/81 行附近：reviewer 派发约定里的 `rc-unified.md`/`r{N}-*.md` 路径、
     "串行 dispatch"、"Context Completeness"（②已废除）——整段按新契约改写
   - `skills/x-dev/SKILL.md`："Q3 调 x-qa-gate R1→R2→R3" 改并行措辞
   - `skills/x-qa-gate/templates/qa-gate-report-template.md`：顺序语义与路径
   - `skills/x-fix/`：如有 R1→R2→R3 顺序语义同步
   - `README.md` / `README_zh.md`：门禁描述同步
4. **Q3 并行行为 dry-run（不只查文字）**：取 test 的 e2e fixture task 构造一个小 diff，
   实际并行 dispatch 三个 lens reviewer 各出 mini-report，核对：三者输入为**同一冻结 diff**、
   主 agent 聚合**一次**、（如有发现）x-fix 调用**一次**、复审走增量协议。结果记入该 task 的 dev-report

---

# Part B 挖掘度量

## B1 `tools/metrics.py`（独立脚本，标准库 only）

```
python3 tools/metrics.py scan [--projects-dir ~/.claude/projects] [--json]
python3 tools/metrics.py session <主session.jsonl> [--json]
```

**统计契约（错误做法已在真实数据上证伪，必须遵守）**：
1. **按 message.id 去重、取末次快照**：同一 message.id 以流式快照写入多条记录，
   逐行累加会虚高约 5 倍（实测同一会话 780,555 vs 去重后 141,950）
2. **分桶**：`parent_input` / `parent_output` / `cache_read` / `cache_creation` /
   `subagent_tokens`（Agent 工具结果字段 + 与主 session 同名子目录下 jsonl 汇总，
   注意与父桶不重复计数）/ `total` / `wall_clock`（首末时间戳差）/
   `user_turns`（真人输入，与 tool_result 条目区分）
3. **scan 不得把子 agent 转录当独立主 session**：与某主 session 同名的目录属于该 session，
   列表中标注归属
4. 字段结构以磁盘真实文件为准，先读样例，映射关系写进脚本 docstring，不确定处列出问用户
5. **交叉校验**：取一个当前可复核 session 与 `/cost` 读数对照，偏差与原因写进交付说明

## B2 `dev-pipeline/metrics.md` 两张表

```markdown
## 新流程样本
| task | risk | 日期 | session | parent_in | parent_out | cache_read | cache_creation | subagent | total | 墙钟 | 人轮次 | 子agent数 | fix轮 | checklist项 | tok/项 |

## 旧流程 baseline（观察性）
| 会话/任务 | 日期 | parent_in | parent_out | cache_read | cache_creation | subagent | total | 墙钟 | 人轮次 | 备注 |
```

B session 只建工具与表骨架；数据行全部由收尾统计 session 回填。

## B3 旧流程 baseline 挖掘（收尾统计 session 执行）

1. `scan` 出候选清单 → **用户点名**旧流程会话（已知起点：
   `-Volumes-machub-app-proj-x-dev-pipeline/` 2026-07-12/13 两个；其余用户补充），不得自行猜测
2. 逐个 `session` 挖掘入 baseline 表，观察性表述（归一指标 tok/checklist 项）

## B4 可选 A/B 受控对比（用户说做才做）

操作手册写进 B 的 task README，供用户择期执行：
1. 选 1 个 Q2 真实小任务，写定 prompt 原文
2. **隔离方式（审查修正）：每臂、每次重复都从同一 commit 新建独立 git worktree**——
   `git reset --hard` 清不掉新建 task 目录等 untracked 产物，会让下一臂进入更新模式污染样本；
   跑完整棵 worktree 删除
3. 旧臂用用户保存的原始 skill 目录（临时注册为插件），开跑前自检"`/x-qdev` 存在、
   `xdev.py verify` 不存在"证明环境；**记录两臂插件目录内容 hash**（如 `find skills -type f | sort | xargs shasum | shasum`）
4. prompt 逐字相同、fresh session、每臂 ≥2 次（或只对 ≥2 倍差异下结论）
5. 全部 session id 入 metrics.md

## B5 预算线草案（收尾统计 session 执行）

样本入表后按 risk 档位给实测分布与建议倍数，写"预算线（草案，待拍板）"节——数值由用户拍板。

---

## 范围守卫

- 不动 capability 回流、x-spec / x-cr 主体 / audit
- metrics.py 只读，不写不删不上传
- A3 只做合并/并行化/引用同步，不改各 lens 检查语义
- 状态符号单轨化（emoji 议题）**不在本单**——另行拍板

## DoD（可复跑）

| # | 验收项 | 复跑方式 | 预期 |
|---|--------|---------|------|
| 1 | 全部单测 | `python3 -m unittest discover -s test` | OK（含 A1 六用例矩阵） |
| 2 | V2 误报修复 | scaffold 原样目录 → validate | V2 = 0 |
| 3 | V2 不过修 | 矩阵用例 2-6 | 全部仍触发/不扰乱 |
| 4 | 续接与授权 | grep "只出文档" → SKILL + confirmation 双命中；grep "下一步 \`x-dev" → 0 | 如预期 |
| 5 | 判据措辞 | grep "跨模块或多实现点" skills/x-req/SKILL.md | 命中，"多文件"不再单列 |
| 6 | lens 收拢 | `ls skills/x-qa-gate/references/` = 1 文件；降级规则全仓唯一 | 如预期 |
| 7 | 引用同步 | 全仓 grep `rc-unified\|r1-spec\|r2-boundary\|r3-test\|串行`（历史档案除外） | 0 命中 |
| 8 | Q3 并行行为 | dry-run 记录（dev-report 内） | 同一冻结 diff / 聚合一次 / x-fix 一次 |
| 9 | metrics scan | 实跑 | 主 session 清单，子 agent 目录标注归属不独立成行 |
| 10 | metrics session | 对 7 月 13 日已知会话实跑 | 去重后 output ≈ 141,950（±字段映射说明） |
| 11 | 样本入表 | 读 metrics.md | 4 行样本（A1/A2/A3/B）各带 session id，由收尾 session 回填 |
| 12 | baseline 入表 | 同上 | 用户点名会话已挖掘 |
| 13 | OpenSpec | `openspec validate <本单 change> --strict` | 通过；**验收前不归档** |
| 14 | task 目录 | `ls dev-pipeline/tasks/` | A1/A2/A3/B 四个 task 目录齐全 |

## 交付材料

1. OpenSpec change（活跃）+ `git log` 与各 commit `--stat`
2. 单测输出；A1 修复前后 validate 对照
3. metrics.py 对已知会话输出（含 DoD-10 数字）+ `/cost` 交叉校验与字段映射说明（含不确定项）
4. 填好的 metrics.md（**4** 行样本 + baseline + 预算草案）
5. **5 个 session** 的运行方式说明（A1/A2/A3/B/收尾统计各自独立、prompt 与附录 P 逐字一致）
6. 每项偏离及理由

---

# 附录 P：样本 prompt 原文（逐字使用，每段开一个全新 session）

## P-A1

```
修复 x-dev-pipeline 仓库 tools/xdev.py 的 validate V2 规则对 HTML 注释的误报。

背景：skills/x-req/templates/dev-checklist.md 的 HTML 注释里有状态映射文字（如 [ ](⏳▶️🟡)→todo），
tools/xdev.py 的 LINK_RE 把它当 markdown 链接，V2 误报"包内链接必须以 ./ 开头"。
复现：python3 tools/xdev.py scaffold /tmp/v2-demo && python3 tools/xdev.py validate /tmp/v2-demo
→ dev-checklist.md 出 3 条 V2 误报。

要求：
1. 修法：校验预处理移除 HTML 注释片段（span 级、含跨行 <!-- ... -->），不是跳过整行——
   "正文 <!-- 注释 -->"同行混排时正文必须保留并参与检查。
2. 回归测试（标准库 unittest，放 test/，沿用临时目录 fixture 风格）六个用例：
   a) scaffold 原样目录 validate 后 V2=0；b) 正文坏链接 [x](../out.md) 仍触发；
   c) [x](../bad.md) <!-- 说明 --> 仍触发；d) <!-- 说明 --> [x](../bad.md) 仍触发；
   e) 跨行注释行中关闭后同行坏链接仍触发；f) 注释内 ``` 文字不扰乱围栏状态机。
3. python3 -m unittest discover -s test 全过。
风险定级：按 Q1 处理（用户显式覆盖：局部修复不因文件数升级）。
```

## P-A2

```
修正 x-dev-pipeline 仓库 x-req skill 的三处规划契约问题。

背景：① skills/x-req/SKILL.md 定级表"流程"列写全链直通，但流程第 8 步写"输出……下一步 x-dev"，
两处语义打架；② skills/x-req/templates/confirmation.md 结尾"回 Y 我产出文件"未覆盖 Y 同时授权
继续开发/验证/门禁；③ 定级表 Q2 判据"多文件"会把"修复+配套测试（必然两文件）"字面升级 Q2。

要求：
1. SKILL.md 明确：Q0/Q1 完成产物后、Q2/Q3 用户确认 Y 后，直接继续执行 x-dev 流程不停下；
   用户在确认回复中说"只出文档"则停。第 8 步改为"完成汇报（含 risk 依据与 Gate 结果）"。
2. confirmation.md 结尾改为："以上 OK？回 Y = 产出文件并继续执行开发、验证与门禁；
   回 只出文档 = 仅产出文件。"
3. 定级表 Q2 判据"多文件"改为"跨模块或多实现点"。
4. 自验：grep "只出文档" 在 SKILL.md 与 confirmation.md 各命中；
   grep "下一步 `x-dev" 零命中；grep "跨模块或多实现点" 命中。
风险定级：按 Q1 处理（用户显式覆盖）。
```

## P-A3

```
重构 x-dev-pipeline 仓库 x-qa-gate 的 reviewer 材料与 Q3 执行结构：四合一、并行化、全仓引用同步。

背景：skills/x-qa-gate/references/ 下 rc-unified/r1-spec-conformance/r2-boundary-coverage/
r3-test-integrity 四文件的输出格式与置信度降级规则重复 4 遍；SKILL 规定 Q3 串行 R1→R2→R3，
但发现是聚合后一次交 x-fix 批量修，串行不省 token 纯费墙钟。

要求：
1. 合并为 references/reviewer-lenses.md：头部"共享输出契约"节只写一遍（mini-report 结构、
   覆盖声明、发现表列、置信度降级），RC/R1/R2/R3 各一节只留输入清单+检查清单（语义原样迁移）；
   删除原四文件。
2. skills/x-qa-gate/SKILL.md：Q3 改三 lens 并行 dispatch（同一冻结 diff、各自只读、
   prompt 带 reviewer-lenses.md 对应节），主 agent 聚合去重排序后一次交 x-fix；增量复审不变。
3. 全仓同步旧路径与串行语义：CLAUDE.md（reviewer 派发约定段，含 rc-unified.md/r{N}-*.md 路径、
   "串行 dispatch"、已废除的"Context Completeness"）、skills/x-dev/SKILL.md（"Q3 调 x-qa-gate
   R1→R2→R3"改并行措辞）、skills/x-qa-gate/templates/qa-gate-report-template.md、
   skills/x-fix/ 顺序语义、README.md、README_zh.md。
4. Q3 并行行为 dry-run：取 test 的 e2e fixture task 造一个小 diff，实际并行 dispatch 三个
   lens reviewer 各出 mini-report，在 dev-report 记录核对结果：同一冻结 diff / 聚合一次 /
   （如有发现）x-fix 一次 / 复审走增量协议。
5. 自验：ls references/ 仅 1 文件；全仓 grep 四个旧文件名与"串行"零命中（openspec 归档与
   dev-pipeline/tasks 历史档案除外）。
预计定级 Q2（跨模块契约变化）。
```

## P-B

```
为 x-dev-pipeline 新建会话成本挖掘工具 tools/metrics.py（标准库 only，独立于 xdev.py）
与 dev-pipeline/metrics.md 表骨架。

命令：
- python3 tools/metrics.py scan [--projects-dir ~/.claude/projects] [--json]：
  列出各项目主 session（项目、id、起止时间、大小、消息数）；与主 session 同名的子 agent
  转录目录不得列为独立 session，标注归属。
- python3 tools/metrics.py session <主session.jsonl> [--json]：输出成本汇总。

统计契约（错误做法已被证伪，必须遵守）：
1. 同一 message.id 以流式快照写入多条记录——必须按 message.id 去重、取末次快照的 usage；
   逐行累加虚高约 5 倍（已知会话实测：逐行 780,555 vs 去重 141,950）。
2. 分桶：parent_input/parent_output/cache_read/cache_creation/subagent_tokens（Agent 结果
   字段与子目录 jsonl 汇总，不与父桶重复计数）/total/wall_clock/user_turns（区分 tool_result）。
3. 字段结构以磁盘真实文件为准（可用
   ~/.claude/projects/-Volumes-machub-app-proj-x-dev-pipeline/6495693e-*.jsonl 摸底），
   映射关系写进 docstring，不确定处列出问用户。
4. 交叉校验：取一个当前可复核 session 与 /cost 对照，偏差与原因写进交付说明。
5. 单测：对构造的迷你 jsonl fixture 验证去重、分桶、子目录归属。

metrics.md 骨架两张表（新流程样本/旧流程 baseline），样本表列：
task|risk|日期|session|parent_in|parent_out|cache_read|cache_creation|subagent|total|墙钟|人轮次|子agent数|fix轮|checklist项|tok/项。
本 session 只建工具与骨架，不填自身数据行（由收尾统计 session 回填）。
预计定级 Q2。
```

## P-收尾统计

```
x-dev-pipeline 度量收尾：用 tools/metrics.py 回填 dev-pipeline/metrics.md。

1. python3 tools/metrics.py scan 列出候选会话，向用户确认 A1/A2/A3/B 四个样本 session 的 id，
   以及旧流程会话归属（已知起点：-Volumes-machub-app-proj-x-dev-pipeline 下 2026-07-12/13
   两个会话；其余由用户点名，不得猜测）。
2. 对四个样本 session 逐个跑 session 子命令，填"新流程样本"表（含 checklist 项数与 tok/项）。
3. 对点名的旧流程会话挖掘填 baseline 表，观察性表述。
4. 末尾写"预算线（草案，待拍板）"：按 risk 档位给实测分布与建议倍数，数值留用户拍板。
本 session 是纯统计动作，自身不入样本表。
```
