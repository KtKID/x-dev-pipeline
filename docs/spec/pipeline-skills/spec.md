# pipeline-skills：管线各 x-* skill 对使用者承诺的流程

> spec：pipeline-skills
> 主要入口：skills/x-*/SKILL.md、skills/*/references/、skills/x-dev/scripts/xdev.py、skills/x-dev/scripts/delivery.py、skills/x-req/scripts/checklist_engine.py
> 状态：在用
> 最近更新：2026-11-21

管线 skill 的行为本身也按 spec 管：改一条 skill 规则，就在这里新增或修改场景，并写明用哪组 eval 或测试验收。

规则的完整写法以各 skill 的 SKILL.md 和 references 为准，这里不重复，只写使用者能观察到的结果。验收题登记在 `evals/answers/INDEX.md`，运行记录在 `evals/runs/<eval>/`。

## 本次目标与完成条件

- 本次目标与范围：第一批（feat01–feat06）补入 spec-scope-qdev 分支已改好的 skill 行为；第二批（feat07–feat12）是交付精简、覆盖率 100%、审查去重、架构约束、测试真实性检查和问清需求再写 spec，用户 2026-11-21 已确认。
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
- WHEN x-verify-spec 核对
- THEN 判"核对未完成"，不能用开发者的声明代替

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
依据与价值：用户 2026-11-20 选定方案 A（主 agent 负责验收）；2026-11-21 要求去掉重复验收，每组不再另派验收 agent，独立审查只在整体做一次。
- GIVEN checklist 有两个及以上并行组
- WHEN x-dev 开始开发
- THEN 主 agent 按 `xdev graph` 的批次派工人，每组交回后主 agent 自己在这组分支上跑 `xdev coverage` 核对；只有一组时不走这套

场景2: 工人越界就停下报回
依据与价值：工人改派工单以外的文件，会和别的组撞车。
- GIVEN 工人要改派工单以外的文件，哪怕只改一行
- WHEN 工人开发中
- THEN 不改，停下这一行报回主 agent

场景3: 合并后才算通过
依据与价值：没合并的改动不能算完成。
- GIVEN 一组核对通过，还没合进主干
- WHEN 主 agent 回写 checklist
- THEN 这组的行写 🟡；合并并通过全量测试后才写 🟢

场景4: 一组 3 轮不过就升级
依据与价值：避免无限返工，同时不拖住别的组。
- GIVEN 某组核对第 3 轮仍不通过
- WHEN 主 agent 处理
- THEN 这组标 ↗️ 升级给用户，其他组照常进行

验收：eval dev-worker（10 题）、dev-main（14 题）。

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

## feat07: 交付只有一份文件

> 状态：已验收

场景1: 结果写回 checklist
依据与价值：用户 2026-11-21：dev-report 产物太多，必须精简。
- GIVEN x-dev 做完一个 task
- WHEN 记录交付结果
- THEN 用例对应、覆盖率、问题与处置都写在 dev-checklist.md 末尾的「结果」节，原始输出放 evidence/；不另写 dev-report 和测试报告

场景2: 门禁修复不另建报告
依据与价值：同上。
- GIVEN x-fix 修完 xdev check 或 x-qa-gate 的问题
- WHEN 记录处置
- THEN 每条一行写进 checklist「问题与处置」；只有直接 bug 修复和 CR 驱动修复才写 reports/fix/

验收：eval dev-delivery（16 题）；`test/test_delivery.py`。

## feat08: 改动行覆盖率 100%

> 状态：已验收

场景1: 不到 100% 就补测试
依据与价值：用户 2026-11-21：测试用例覆盖率必须 100%，开发时必须有流程检查覆盖率，不到就补，要让 agent 看到覆盖率。
- GIVEN 全部行做完，和代码基线相比改了若干代码行
- WHEN 运行 `xdev coverage <task> --cmd ... --report ...`
- THEN 它真的跑测试，列出没被测试跑到的 `文件:行`，不到 100% 退出 1；agent 补测试再跑，直到 100%

场景2: 交付前脚本核对
依据与价值：能自动化的就不让 agent 猜。
- GIVEN 覆盖率记录已生成
- WHEN 运行 `xdev check <task>`
- THEN 核对每个场景有通过的用例、每个用例对应真实测试函数、测试通过、覆盖率 100% 且之后代码没再改；任何一项不满足就列出并退出 1

验收：`test/test_delivery.py`；eval dev-delivery。

## feat09: 一次独立审查

> 状态：已验收

场景1: 按 risk 派一个 reviewer
依据与价值：用户 2026-11-21：verify 去掉重复。
- GIVEN `xdev check` 通过
- WHEN 进入审查
- THEN Q0 不派；Q1 一个 reviewer 做需求对齐、测试证明力、设计与架构；Q2 再加边界；Q3 四个 lens 逐项回执。机械项不重复核对

验收：eval review-route（R01–R08、R12）。

## feat10: 架构要求记在用户约束里

> 状态：已验收

场景1: 设计和约束冲突就问
依据与价值：管线目标之一是架构要符合用户偏好；用户 2026-11-21：架构偏好就是用户约束里的一类，不另建文件。
- GIVEN 本 spec 或 engineering spec 的关键约束里有一条“架构：”约束，方案会违反它
- WHEN x-tech-design 写设计
- THEN 把这一条当作需要用户拍板的取舍单独问，不悄悄违反也不悄悄改约束

场景2: 只记用户说过的，全项目的放 engineering
依据与价值：约束是用户的，不能由 agent 从代码推测。
- GIVEN 用户没说过某个架构要求，或用户在对话里说出新的架构要求
- WHEN agent 处理
- THEN 没说过的不从代码推测填写；说过的写进对应 spec 的关键约束，开头写“架构：”并注明来源，对全项目都成立的写进 engineering spec

场景3: 约束只是任务的一部分
依据与价值：用户 2026-11-21：子 agent 开发时容易只看用户约束、忘了看 feat。
- GIVEN 一行任务回指了场景，也有适用的约束
- WHEN 工人或开发 agent 开工、报完成
- THEN 先读场景正文再读约束；只满足约束、场景的 THEN 没有测试证明的，不能报完成；审查时这种情况算漏了要的

验收：eval review-route（R05、R09–R11）、dev-worker（W11、W12）。

## feat11: 测试必须真跑、真测

> 状态：已验收

场景1: 完成必须全量全绿、100% 覆盖
依据与价值：用户 2026-11-21：本来代码都有测试用例，完成功能必须跑测试用例，不仅要全绿，还要 100% 覆盖率。
- GIVEN x-dev 或 x-qdev 做完一个功能
- WHEN 准备报完成
- THEN 项目全量测试（原有的加新写的）用真实命令跑过且全绿，改动行覆盖率 100%；原有测试红了不删、不跳过、不改断言迁就，先查是不是自己改坏的

场景2: 轻量子 agent 查假测试
依据与价值：用户 2026-11-21：派一个轻量级子 agent 检查测试用例是否弄虚作假，比如自己写流程而不是调用项目里的流程，禁止写重复逻辑，否则生产代码改了测试就废了；还要检查是否偷懒乱写导致测不到真实内容。
- GIVEN 覆盖率已到 100%，本次有新增或改动的测试
- WHEN 派最便宜的模型只读这些测试和它们要测的生产代码
- THEN 它按清单找出：重写了生产逻辑、没调用项目代码、绕过要测的流程、mock 掉了被测对象、只断言调用不断言结果、断言恒真、吞掉失败、数据测不出对错；外部依赖的 mock、fixture、手写常量期望值不算问题

场景3: 检查结果由脚本把关
依据与价值：能自动化的就不让 agent 猜。
- GIVEN 子 agent 的回执已存进证据目录
- WHEN 运行 `xdev check`
- THEN 有改动的测试却没有回执、结论不通过且问题没写不采纳理由、回执没列全改动的测试文件、回执写在最后一次跑覆盖率之前（测试改了覆盖率就要重跑），都不通过

验收：eval test-integrity（13 题）、dev-delivery（D14–D16）；`test/test_delivery.py`。

## feat12: 问清需求再写 spec

> 状态：已验收
> 期次：1 期

需求 skill 改名 x-ask-spec，主体是和用户讨论，spec 只是讨论结果。

场景1: 先复述，再主动问
依据与价值：用户 2026-11-21：以前和用户聊完是单向的，一直是用户在说，agent 缺少提问；要苏格拉底式和用户讨论清楚需求。
- GIVEN 用户只说了一句想法，比如“给借阅列表加个导出”
- WHEN x-ask-spec 开始
- THEN agent 先用大白话复述理解，再按正常情况、边界、出错、不做什么、怎么算做完五类列出没想清楚的地方，每轮问 2–3 个；用户说过的、代码查得到的不重复问

场景2: 问到没有疑问才写
依据与价值：同上；spec 文档只是产物。
- GIVEN 讨论还有类别没答案，或最终复述还没给用户看
- WHEN agent 想开始写 spec
- THEN 不写；五类都有答案、agent 说出“没有要问的了”、用户认可最终复述后才写；用户没回答的记为没定

场景3: 一期最多 5 个 feat
依据与价值：用户 2026-11-21：一版不能超过 5 个 feat，剩余功能放进迭代，标明 2 期、3 期。
- GIVEN 讨论下来超过 5 个还没交付的 feat
- WHEN 写进 spec
- THEN 选 5 个标 1 期，其余标 2 期、3 期，只写名称、一句话用途和已确认要点，并告诉用户这些放进后续迭代；`xdev validate <spec 目录>` 发现同一期没交付的 feat 超过 5 个就报 PHASE_LIMIT

场景4: 后面几期不往下传，qdev 不走完整讨论
依据与价值：同上；qdev 是范围明确的小任务，不应和主线一样重。
- GIVEN spec 里有 1 期和 2 期的 feat；或者用户用 qdev 做一件说得很清楚的小事
- WHEN x-req 拆任务；或者 qdev 核对需求
- THEN x-req 只拆当前这一期（还有没交付 feat 的最小期次）；qdev 按五类核对一遍，只对会改变结果的缺口提问

验收：eval ask-spec（12 题）、qdev-spec-routing（复跑）；`test/test_checklist_engine.py` 的 PHASE_LIMIT 测试。

## 变更记录

| 日期 | 改了什么 | 依据 / task | 状态 |
|---|---|---|---|
| 2026-11-20 | 新建本 spec，补入 feat01–feat06 | 用户 2026-11-20 选方案 A，并确认本 spec 内容；分支 spec-scope-qdev | 已确认 |
| 2026-11-20 | feat06 补验收题 td-confirm，6/6 ×2 | evals/runs/td-confirm/ | 已验收 |
| 2026-11-21 | 新增 feat07–feat10；feat02 场景5、feat05 场景1/3/4 改为新核对流程 | 用户 2026-11-21：覆盖率 100%、精简 dev-report、verify 去重 | 已验收（用户 2026-11-21 确认） |
| 2026-11-21 | feat10 改为“架构要求记在用户约束里”，加场景3“约束只是任务的一部分”；不再单独建架构偏好文件 | 用户 2026-11-21 | 已验收（用户 2026-11-21 确认） |
| 2026-11-21 | 新增 feat11：测试必须真跑、真测（全量全绿、改动行 100%、轻量子 agent 查假测试） | 用户 2026-11-21 | 已验收（用户 2026-11-21 确认） |
| 2026-11-21 | 新增 feat12：问清需求再写 spec（x-explore-for-spec 改名 x-ask-spec，苏格拉底式讨论，一期最多 5 个 feat） | 用户 2026-11-21 | 已验收（用户 2026-11-21 确认） |
