# pipeline-skills：管线各 x-* skill 对使用者承诺的流程

> spec：pipeline-skills
> 主要入口：skills/x-*/SKILL.md、skills/*/references/、skills/x-dev/scripts/xdev.py、skills/x-req/scripts/checklist_engine.py
> 状态：在用
> 最近更新：2026-11-20

管线 skill 的行为本身也按 spec 管：改一条 skill 规则，就在这里新增或修改场景，并写明用哪组 eval 或测试验收。

规则的完整写法以各 skill 的 SKILL.md 和 references 为准，这里不重复，只写使用者能观察到的结果。验收题登记在 `evals/answers/INDEX.md`，运行记录在 `evals/runs/<eval>/`。

## 本次目标与完成条件

- 本次目标与范围：把 spec-scope-qdev 分支里已经改好的 skill 行为补进本 spec，作为第一批内容（feat01–feat06）。
- 验证证据：每个场景列出的 eval 最近一轮全对；`test/` 全部通过。
- 完成条件：用户确认本 spec（2026-11-20 已确认），feat06 补题验收（td-confirm 已通过）。

## 关键约束（用户已确认）

| 编号 | 约束与适用范围 | 可观察判据与禁止结果 | 确认依据 / 关联场景 |
|---|---|---|---|
| C1 | 每个场景都要有验收：一组 eval 题或确定性测试 | `evals/answers/INDEX.md` 或 `test/` 里能找到它；没有题的规则不能标已验收 | 用户 2026-11-19：每个设计都要有 eval；全部 feat |
| C2 | 能机械判断的交给脚本，不让 agent 猜 | 编号引用、文件交集、依赖、risk、需求变化清单由 xdev 命令给出结果 | 用户 2026-11-20：能自动化的就不让 agent 猜；feat03、feat04 |

## feat01: spec 归属

> 状态：已验收

需求写进哪份 spec，按改的是谁的数据来定。

场景1: 有所有者就加到已有 spec
依据与价值：用户 2026-11-19 要求写清是加到已有 spec 还是新建；避免同一行为散在多份 spec。
- GIVEN 边界表里有一行"拥有什么"包含这块数据
- WHEN agent 判断一条场景的去处
- THEN 加到那份已有 spec，不新建

场景2: 没有所有者才新建
依据与价值：同上。
- GIVEN 边界表所有行都管不着这块数据
- WHEN agent 判断去处
- THEN 新建 spec，并在边界表加一行"拥有什么 / 不管什么"

场景3: 边界表重叠就问用户
依据与价值：边界表写重了，agent 自己挑会选错。
- GIVEN 边界表有两行都说拥有同一块数据
- WHEN agent 判断去处
- THEN 停下问用户，不自己挑

验收：eval spec-scope（20 题）。

## feat02: qdev 的停点和路由

> 状态：已验收

小任务走 qdev 时，什么时候停、什么时候转主线、技术设计写在哪。

场景1: 写了场景就停下确认
依据与价值：用户 2026-11-19 要求 spec 写完必须展示给用户检查。
- GIVEN qdev 新增、修改或退役了场景或 C，或新建了 spec
- WHEN spec 增量写完
- THEN 把归属表、场景原文和改法发给用户，确认后才开始写代码

场景2: 只记变更的不停
依据与价值：纯工程、只改外观、修 bug 且 spec 已写明正确行为，没有需要确认的内容。
- GIVEN 改动只在变更记录里记一行
- WHEN spec 增量写完
- THEN 用 1–3 句话告知改法后直接执行

场景3: 风险规则有一条答"是"就转主线
依据与价值：用户 2026-11-19 要求用硬规则把握"度"。
- GIVEN 风险规则 7 个问题里有一个答"是"
- WHEN agent 判断是否留在 qdev
- THEN 停下交接，转完整主线

场景4: 技术设计写在哪
依据与价值：用户 2026-11-19 要求按需写 tech-design。
- GIVEN 新建了 spec、场景跨两份以上 spec，或源码文件超过 3 个
- WHEN agent 决定技术设计写在哪
- THEN 调 x-tech-design 写 tech-design.md；否则在 task ②写几行

场景5: 对账能发现漏记确认
依据与价值：确认记录缺失时没人发现，停点就形同虚设。
- GIVEN qdev 改了场景，但 task 里没有记用户确认的时间和消息位置
- WHEN x-verify-spec 对账
- THEN 判"对账未完成"，不能用开发者的声明代替

验收：eval qdev-spec-routing（17 题）、qdev-confirm-check（6 题）。

## feat03: 需求变化同步

> 状态：已验收

spec 变了，顺着编号找到要动的 D、T、任务行和测试。

场景1: 列出要同步的项
依据与价值：用户 2026-11-19 要求修改 spec 后 tech 也按需改，到 dev 的链路都检查。
- GIVEN 拆解基线之后 spec 或 tech-design 变了
- WHEN 运行 `xdev impact <task>`
- THEN 列出要改、新增、退役、重开、重跑的 T、D、任务行和测试文件；只有"这条 D 还成立吗"标为需要判断

场景2: 没同步不开工
依据与价值：避免按旧需求开发。
- GIVEN `xdev impact` 报出变化
- WHEN x-dev 准备开工
- THEN 受影响的行不开工；同步完运行 `xdev baseline` 记新基线后才开工

验收：eval change-sync（7 题）；`test/test_checklist_engine.py` 的 impact 与 baseline 用例。

## feat04: x-req 的并行组和 checklist 校验

> 状态：已验收

场景1: 文件有交集必须同组
依据与价值：两个工人同时改一个文件，合并会冲突或互相覆盖。
- GIVEN 两行的涉及文件有交集，但分在不同的并行组
- WHEN 运行 `xdev validate <task>`
- THEN 报 GROUP_OVERLAP，不通过

场景2: 按任务量决定组数
依据与价值：用户 2026-11-20 要求不一定多派，看任务量，由主 agent 自己安排。
- GIVEN 文件不重叠，但合计只是几处小改动
- WHEN x-req 分组
- THEN 只分一组，并在头部写分组理由

场景3: risk 按任务行算出
依据与价值：x-qa-gate 按它决定审查强度，必须只有一个来源。
- GIVEN 任务行里有 N 个高风险行
- WHEN 运行 `xdev validate`
- THEN 头部 risk 必须等于按规则算出的值（2 个及以上 Q3，1 个 Q2，没有时有场景回指 Q1、否则 Q0），不一致就报错

验收：eval req-grouping（7 题）；`test/test_checklist_engine.py`。

## feat05: 多 agent 协作开发

> 状态：已验收

场景1: 两个及以上并行组才派工人
依据与价值：用户 2026-11-20 选定方案 A（主 agent 派验收）。
- GIVEN checklist 有两个及以上并行组
- WHEN x-dev 开始开发
- THEN 主 agent 按 `xdev graph` 的批次派工人，每组做完另派验收 agent；只有一组时不走这套

场景2: 工人越界就停下报回
依据与价值：工人改派工单以外的文件，会和别的组撞车。
- GIVEN 工人要改派工单以外的文件，哪怕只改一行
- WHEN 工人开发中
- THEN 不改，停下这一行报回主 agent

场景3: 合并后才算通过
依据与价值：没合并的改动不能算完成。
- GIVEN 一组验收通过，还没合进主干
- WHEN 主 agent 回写 checklist
- THEN 这组的行写 🟡；合并并通过全量测试后才写 🟢

场景4: 一组 3 轮不过就升级
依据与价值：避免无限返工，同时不拖住别的组。
- GIVEN 某组验收第 3 轮仍不通过
- WHEN 主 agent 处理
- THEN 这组标 ↗️ 升级给用户，其他组照常进行

验收：eval dev-worker（10 题）、dev-main（13 题）。

## feat06: tech-design 不需要用户确认

> 状态：已验收

场景1: 写完直接交接
依据与价值：用户已定 spec 必须确认、tech-design 可选审阅。
- GIVEN tech-design 写完，没有需要用户拍板的取舍
- WHEN x-tech-design 交接
- THEN 直接交给 x-req，不停下等确认

场景2: 需要拍板的取舍单独问
依据与价值：会改变产品结果的取舍仍要用户决定。
- GIVEN 设计中有会改变产品结果的边界取舍
- WHEN x-tech-design 交接
- THEN 只把这一项单独问用户，其他部分照常交接

验收：eval td-confirm（6 题）。

## 变更记录

| 日期 | 改了什么 | 依据 / task | 状态 |
|---|---|---|---|
| 2026-11-20 | 新建本 spec，补入 feat01–feat06 | 用户 2026-11-20 选方案 A，并确认本 spec 内容；分支 spec-scope-qdev | 已确认 |
| 2026-11-20 | feat06 补验收题 td-confirm，6/6 ×2 | evals/runs/td-confirm/ | 已验收 |
