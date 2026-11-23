# 测试用例索引（仅评审侧）

每条设计规则测哪些题、每道题考什么，都记在这里。本目录只给评分脚本和评审看，答题者不读 `evals/answers/`。

新增或修改一条设计规则时，在这里登记它对应的题。没有题的规则，就是还没有测过的规则。

题目项目里的 spec 名：member（读者账号）、catalog（馆藏目录）、loan（借阅）、fine（罚款）、message（消息）、engineering（工程）。

## spec 归属（spec-scope）

- 规则：`skills/x-ask-spec/references/spec-scope.md`
- 题面：`evals/problems/spec-scope/`；答案：`evals/answers/spec-scope/expected.json`
- 测什么：一个需求是加到已有 spec、新建 spec、只记变更，还是要问用户；要写几份 spec。

| 用例 | 考的规则 | 正确判断 | 常见错误 |
|---|---|---|---|
| S01 S02 S03 S10 | 改的数据有明确所有者 → 加到已有 | 各加到一份 | — |
| S04 S14 | 被调用方输入输出没变 → 只写调用方 | 只加到调用方 | 把 message 也列上 |
| S05 S12 | 表里没有所有者 → 新建 | 新建一份 | 塞进 catalog |
| S06 | 只展示的场景，看展示的是谁的数据 | 加到 loan | 按页面放进 member |
| S07 | 纯工程改动 → 只记变更 | engineering 只记变更 | 写场景或新建 spec |
| S08 | 只改文案 → 只记变更 | catalog 只记变更 | 写场景 |
| S09 | 看"可借上限"归谁，不看"等级"这个词 | 加到 loan | 放进 member |
| S11 | 只读取别的数据不算改它 | 只加到 member | 多列 loan |
| S13 | 一个需求改两块数据 → 两份都写 | fine + member | 只写一份 |
| S15 | 只新增消息类型，不涉及调用方 | 只加到 message | 新建 spec 或多列 loan |
| S16 | 一条场景改两块数据 → 先拆开 | fine + member | 整条放进 fine |
| S17 | 被调用方输入输出变了 → 它也要加 | 只加到 message | 多列 loan，或漏掉 message |
| S18 | 边界表两行重叠 → 问用户 | 问用户 | 自己挑一份 |
| S19 | spec 写的不是用户要的 → 修改场景 | 加到 loan | 当成修 bug 只记变更 |
| S20 | 去掉一个能力是行为，不是外观 | 加到 catalog | 只记变更 |

## qdev 路由（qdev-spec-routing）

- 规则：`skills/x-qdev/SKILL.md` 第 1–3 节、`skills/x-qdev/references/risk-rules.md`，加上 spec-scope
- 题面：`evals/problems/qdev-spec-routing/`；答案：`evals/answers/qdev-spec-routing/expected.json`
- 测什么：在 spec 归属之外，再判断四件事：留在 qdev 还是转主线、task 放哪份 spec、写完 spec 停不停下来给用户确认、技术设计写在 tech-design.md 还是 task ②。

| 用例 | 考的规则 | 正确判断 |
|---|---|---|
| Q01 | 修 bug，spec 已写明正确行为 → 只记变更、不停 | 只记变更，不确认 |
| Q11 | 修 bug，spec 没写这条行为 → 补场景、要停 | 加场景，确认 |
| Q16 | spec 写错了 → 修改场景、要停 | 加到 loan，确认 |
| Q02 Q08 | 加场景 → 要停；文件少 → task ② | 确认，task ② |
| Q03 | 新建 spec → 调 x-tech-design；task 放新 spec 下 | 新建，确认，x-tech-design |
| Q04 Q05 Q10 | 不写场景 → 不停；Q10 改 3 个文件不算超过 3 | 不确认，task ② |
| Q06 | 场景跨两份 spec → x-tech-design；task 放主场景所在的 spec；照用已有权限判断不算改权限；审批靠状态判断防重复，不算防并发 | fine 下，x-tech-design |
| Q09 | 只写一份 spec，但源码文件超过 3 个 → x-tech-design | x-tech-design |
| Q12 | 配置算源码，测试和文档不算 | 源码 2 个，task ② |
| Q17 | 没有直接操作者 → task 放边界表靠前的那份；重跑结果一样不算防重复 | member 下，x-tech-design |
| Q13 | 风险规则：定时任务重跑会重复生成罚款 → 转主线 | 转主线 |
| Q07 | 风险规则：鉴权 + 迁移 → 转主线 | 转主线 |
| Q14 | 风险规则：钱退出去收不回 → 转主线 | 转主线 |
| Q15 | 风险规则反例：只改金额计算规则 → 留在 qdev | qdev |

## 需求变化同步（change-sync）

- 规则：`skills/x-tech-design/references/change-sync.md`
- 题面：`evals/problems/change-sync/`（含 fixture：loan 的 spec、tech-design、开发清单）；答案：`evals/answers/change-sync/expected.json`
- 测什么：spec 的一处变化，下游哪些 D、T、任务行、测试文件要改、新增、退役、重开或重跑；没被引用的不动。

| 用例 | 考的规则 | 正确判断 | 常见错误 |
|---|---|---|---|
| C01 | 改场景结果，D 仍成立 | T3 改、行 2 重开、续借测试改 | 把 D02 也改了 |
| C02 | 改 C → 引用 C 的 T 改，D 仍成立不动 | T2 改、行 1 重开、借书测试改 | 改 T1 或 D01 |
| C03 | 新增场景，无新技术约束 | 新 T、行 2 重开、续借测试改 | 新增 D 或新增任务行 |
| C04 | 删除场景，共用的 D 不退役 | T5 退役、新 T、行 3 重开、逾期测试改 | 退役 D02 |
| C05 | 只改措辞 → 全不动 | 不动 | 重开任务行 |
| C06 | 修 bug，spec 不变 | 新 T、行 2 重开、续借测试改 | 改 spec 或 D |
| C07 | 场景变化让 D 不成立 → D 改，引用它的所有行重开 | D02 改、T3 改、行 1/2/3 重开、续借测试改、其他两份测试重跑 | 只重开行 2 |

## qdev 核对：spec 确认记录（qdev-confirm-check）

- 规则：`skills/x-verify-spec/SKILL.md` 做法第 3 步的"spec 确认记录"
- 题面：`evals/problems/qdev-confirm-check/`；答案：`evals/answers/qdev-confirm-check/expected.json`
- 测什么：x-verify-spec 能不能发现"改了场景却没记用户确认"。

| 用例 | 考的规则 | 正确判断 |
|---|---|---|
| V01 V06 | 写了场景，有确认时间和消息位置 | 核对通过 |
| V02 | 只写"已确认"，缺时间和位置 | 核对未完成 |
| V03 | 只有变更记录行，写"无需确认" | 核对通过 |
| V04 | 改了场景却写"无需确认" | 核对不通过 |
| V05 | 开发者声明不能代替用户确认 | 核对未完成 |

## x-req 分组（req-grouping）

- 规则：`skills/x-req/SKILL.md`「分组：派给几个工人」
- 题面：`evals/problems/req-grouping/`；答案：`evals/answers/req-grouping/expected.json`
- 测什么：并行组怎么分。硬规则（文件有交集必须同组）由 `xdev validate` 机械核对；这组题测 agent 自己定的软规则：按任务量决定组数，不为并行而拆。
- 每题 3 分：每行恰好在一组、硬规则与指定同组、组数在范围内。

| 用例 | 考的规则 | 正确判断 |
|---|---|---|
| G01 | 文件不重叠但都是小改动 | 1 组 |
| G02 | 两行共用 date.ts 必须同组；另两块大功能可分开 | 2–3 组，T1、T2 同组 |
| G03 | 三行都改同一个文件 | 1 组 |
| G04 | 五块大功能互不重叠，用户没说工人数 | 2–3 组（最多 3） |
| G05 | 都很小且 T2 依赖 T1 | 1 组 |
| G06 | 用户说只有 2 个工人 | 正好 2 组 |
| G07 | 同一场景的实现和测试分在两行 | 两行同组，共 2–3 组 |

## 工人越界判断（dev-worker）

- 规则：`skills/x-dev/references/parallel-dev.md`「工人的规则」
- 题面：`evals/problems/dev-worker/`；答案：`evals/answers/dev-worker/expected.json`
- 对应 spec：`docs/spec/pipeline-skills/spec.md` feat05（W01–W10）、feat10 场景3（W11、W12）

| 用例 | 考的规则 | 正确判断 |
|---|---|---|
| W01 W09 | 派工单以外的文件，哪怕只改一行 | 停下报回 |
| W02 | 自己行用的新测试文件 | 新建并列出 |
| W03 | 别组的 bug | 记进报回问题 |
| W04 | 共享文件（变更记录） | 写进集成时处理 |
| W05 | spec 和设计对不上 | 停下报回 |
| W06 | 同组其他行不依赖停下的行 | 继续做其他行 |
| W07 | 派工单内的文件 | 正常改 |
| W08 | 多次失败原因不清 | 停下报回 |
| W10 | 状态列只由主 agent 写 | 在回执里报状态 |
| W11 | 只满足了约束、场景没做 | 把场景做完再报已完成 |
| W12 | 读完约束、没读场景就动手 | 先读场景正文再动手 |

## 主 agent 下一步（dev-main）

- 规则：`skills/x-dev/references/parallel-dev.md`「主 agent 的步骤」
- 题面：`evals/problems/dev-main/`；答案：`evals/answers/dev-main/expected.json`

| 用例 | 考的规则 | 正确判断 |
|---|---|---|
| M01 | 工人交回 | 自己在这组分支上跑覆盖率核对 |
| M02 | 第 1 次核对不过（覆盖率 92%） | 交回原工人修 |
| M03 | 一组 3 轮不过 | 停这组并升级给用户 |
| M04 | 合并冲突 | 打回后合的组重做 |
| M05 | 开工前 impact 有变化 | 先同步再记新基线 |
| M06 | 工人要改范围外文件，且不属于别的组 | 调整派工单和清单并重跑校验 |
| M07 | 中途需求变化只影响一组 | 只停受影响的组 |
| M08 | 全部合并后 | 整体跑覆盖率 |
| M09 | 整体覆盖率 100%、Q3 | 交 x-verify-spec 验收 |
| M10 | 只有一组 | 不走多 agent 流程 |
| M11 | 和本 task 无关的 bug | 登记成后续任务 |
| M12 | 验收通过 | 升为已完成并交付 |
| M13 | 要改的文件属于另一组 | 把这一行并进那一组 |
| M14 | 整体覆盖率 100%、Q1 | 交 x-verify-spec 验收 |

## 开发收尾（dev-delivery）

- 规则：`skills/x-dev/SKILL.md`「测试是硬规则」与「执行」第 4–6 步、`skills/x-dev/references/test-reporting.md`、`skills/x-qdev/SKILL.md` 第 4–5 节、`skills/x-verify-spec/SKILL.md`、`skills/x-verify-spec/references/feature-check.md`
- 题面：`evals/problems/dev-delivery/`；答案：`evals/answers/dev-delivery/expected.json`
- 对应 spec：`docs/spec/pipeline-skills/spec.md` feat07、feat08、feat09 场景4、feat11 场景1
- 测什么：看到 `xdev coverage` / `xdev check` / 功能检查的结果后，agent 知不知道下一步；交付不再另写测试报告。

| 用例 | 考的规则 | 正确判断 |
|---|---|---|
| D01 D03 | 覆盖率不到 100% / 改动文件不在报告里 | 补测试后重跑 xdev coverage（D03 答“写测试并登记到用例对应表”也算对） |
| D02 | 本 task 新写的测试红了 | 修好失败的测试再重跑 xdev coverage |
| D04 | 新加覆盖率排除标记 | 在问题与处置写理由 |
| D05 | 覆盖率跑完代码又改了 | 重跑 xdev coverage |
| D06 | SPEC_CHANGED | 按 change-sync 同步后 xdev baseline |
| D07 | 开发阶段用例还没有测试 | 写测试并登记到用例对应表 |
| D08 | 只能人工验证 | 写人工记录到 evidence 并记人工通过 |
| D09 | 验收通过 | 升为已完成并交付 |
| D10 D12 D13 | 开发做完（Q2 / qdev 没写场景 / qdev 写了场景） | 交 x-verify-spec 验收 |
| D11 | qdev 开工 | 运行 xdev start 记代码基线 |
| D14 | 功能检查有 P1 | 退回开发者修，修完重跑 coverage 再重做功能检查 |
| D17 | 验收通过后 | 运行 xdev usage fill 填这一期的用量 |
| D18 | 换会话接着开发 | 先运行 xdev usage start 在用量表加一行 |
| D15 | 检查后又改了测试 | 重跑 xdev coverage 后重做功能检查 |
| D16 | 原有测试红了，需求没改这块 | 查是不是自己改坏的，不删不跳过 |

## 验收路由与架构约束（verify-route）

- 规则：`skills/x-verify-spec/SKILL.md`、`skills/x-verify-spec/references/feature-check.md`、`skills/x-tech-design/SKILL.md` 第 2 步、`skills/x-ask-spec/templates/spec.md`「关键约束」
- 题面：`evals/problems/verify-route/`；答案：`evals/answers/verify-route/expected.json`
- 对应 spec：`docs/spec/pipeline-skills/spec.md` feat09、feat10

| 用例 | 考的规则 | 正确判断 |
|---|---|---|
| V01 V04 | Q0、qdev 没写场景 | 只跑 xdev check，不做功能检查 |
| V02 V03 | Q1、Q3 | 派一个子 agent 做一次功能检查，再跑 xdev check |
| V05 V15 | engineering 全项目约束、本轮没提的开发规范 | 不报，交给定期架构巡检 |
| V06 V08 V19 V20 | 测试问题、漏了要的（含本轮 D 没落实、本轮“架构：”约束被违反） | P1 |
| V07 | 已复现的错误结果 | P0 |
| V09 | 机械项不重复 | 不做，xdev check 已核对 |
| V10 | 派工单不加话 | 不加，照派工单模板只填路径 |
| V11 | 回执只存一份 | 不另存，只留 evidence/feature-check.md 一份 |
| V12 | 开发者修完（已重跑 coverage）后关闭 | 重做功能检查，再跑 xdev check |
| V13 | P2 | 在问题与处置登记，不修 |
| V21 | 测试没测到设计写的结果，代码碰巧对 | P1 |
| V22 | 只是写法可以更简洁 | P2 |
| V14 | 记账类 | 不报，记账由主 agent 和 xdev check 管 |
| V16 | 设计和约束冲突 | 单独问用户这一项 |
| V17 | 用户没说过 | 不写，只记用户说过的约束 |
| V18 | 用户说了全项目的架构要求 | 写进 engineering spec 的关键约束并注明来源 |

## 功能检查（feature-check）

- 规则：`skills/x-verify-spec/references/feature-check.md`
- 题面：`evals/problems/feature-check/`；答案：`evals/answers/feature-check/expected.json`
- 对应 spec：`docs/spec/pipeline-skills/spec.md` feat09 场景1、feat11 场景2
- 测什么：便宜的模型只凭这份清单，能不能分出功能漏做、多做，测试是真是假、有没有测到场景要的结果；并且不把外部依赖的 mock、fixture、手写常量误报成问题。

| 用例 | 考的规则 | 正确判断 |
|---|---|---|
| I15 I17 | 代码没做到场景的一个 THEN、本轮 D 没落实 | 漏了要的 |
| I16 | 改了场景没提、也不在涉及文件里的代码 | 做了没要的 |
| I01 | 期望值照抄生产公式 | 重写了生产逻辑 |
| I08 | 测试文件里自己定义了被测函数 | 没调用项目代码 |
| I10 | 直接写存储，没调借书入口 | 绕过要测的流程 |
| I03 | patch 了被测函数本身 | mock 掉了被测对象 |
| I05 | 只断言被调用 | 只断言调用不断言结果 |
| I07 | 期望值来自被测函数自己 | 断言恒真 |
| I09 I12 | try/catch 吞断言、skip | 吞掉失败 |
| I06 | 上限 5 本只借 2 本 | 数据测不出对错 |
| I14 | 代码做到了，测试没断言“到期日不变” | 没测到场景要的结果 |
| I02 I04 I11 I13 | 手写常量、只 mock 存储、假时钟、fixture | 通过 |

## 问清需求再写 spec（ask-spec）

- 规则：`skills/x-ask-spec/SKILL.md`
- 题面：`evals/problems/ask-spec/`；答案：`evals/answers/ask-spec/expected.json`
- 对应 spec：`docs/spec/pipeline-skills/spec.md` feat12
- 测什么：agent 会不会主动复述、追问，什么时候才写 spec，超过 5 个 feat 怎么分期。

| 用例 | 考的规则 | 正确判断 |
|---|---|---|
| A01 | 刚开始 | 先复述理解再提问 |
| A02 | 还有类别没问 | 继续追问还没清楚的类别 |
| A03 A12 | 用户说过、代码查得到 | 不重复问，记下答案和来源 |
| A04 | 五类有答案且用户认可 | 开始写 spec |
| A05 | 还没给用户看最终复述 | 先给用户看最终复述 |
| A06 | 一次想问 9 个 | 每轮只问 2–3 个最影响结果的 |
| A07 | 用户没回答 | 这条记为没定，其他清楚的照常往下走 |
| A08 | 7 个 feat | 选 5 个标 1 期，其余标 2 期 3 期并告诉用户 |
| A09 | 2 期 feat 写多少 | 只写名称、用途和已确认要点 |
| A10 | 只想讨论 | 在对话里给结论，不写 spec |
| A11 | 和已有约束冲突 | 指出冲突请用户决定 |

## 脚本的确定性测试

`skills/x-req/scripts/checklist_engine.py` 的机械规则（编号引用、文件交集必须同组、依赖无环、risk 计算、impact 列出的同步项、baseline）由 `test/test_checklist_engine.py` 覆盖；`skills/x-dev/scripts/delivery.py` 的 start / coverage / check（代码基线、四种覆盖率报告格式、改动行和新文件计入、测试文件和文档不计、排除标记要写理由、覆盖率过期、场景→用例→测试、高风险行要真实链路、qdev 确认记录、测试真实性回执的格式、范围、过期和不采纳）由 `test/test_delivery.py` 覆盖。都不需要 LLM 判题。

## tech-design 不需要用户确认（td-confirm）

- 规则：`skills/x-tech-design/SKILL.md`、`skills/x-req/SKILL.md`「就绪检查」、`skills/x-qdev/SKILL.md` 第 3 节
- 题面：`evals/problems/td-confirm/`；答案：`evals/answers/td-confirm/expected.json`
- 对应 spec：`docs/spec/pipeline-skills/spec.md` feat06

| 用例 | 考的规则 | 正确判断 |
|---|---|---|
| T01 T05 | 只有实现层面的选择 | 直接交给 x-req |
| T02 | 会改变使用者看到的结果的取舍 | 单独问用户这一项，其余照常交接 |
| T03 | tech-design 没被用户看过 | 可以拆任务 |
| T04 | 有未决取舍，只影响一个场景 | 受影响的部分等答复，其余先拆 |
| T06 | qdev 里调 x-tech-design | 继续开发，交付时一起告知 |

干扰项"停下等用户确认整份设计"任何一题选它都算错。

## 实操：x-cr 与 x-fix（cr-handson）

- 规则：`skills/x-cr/`、`skills/x-fix/SKILL.md`
- 题面：`evals/problems/cr-handson/`；考点、隐藏测试：`evals/answers/cr-handson/<题目>/`；判分：`evals/scripts/handson_grade.py`
- 测什么：真跑。每道题埋了问题和陷阱，脚本核对报告、代码、测试。

| 题目 | 考的规则 | 正确做法 |
|---|---|---|
| cr-renew | 判尺原编号、严重度、位置、不改代码；接 x-fix：都修、反例修前失败 | 三个问题都找到；修完隐藏测试过 |
| cr-fine-diff | 没给范围查 diff、task 里报告位置、不报 diff 外问题和风格 | 只报 calc_fine 负数罚款 |
| cr-reserve | 来源不一开 P2；调用方已守住的不误报 | 报有库存能预约、上限说法不一；不报 cancel_reservation |
| cr-recommend | 已知问题原因不明时逐个排除；隔离突破 P0 | 原因排查坐实缓存键 |
| fix-mixed | 已修跳过、误报不改、来源不一待确认、行号过期按函数找、不修报告外 | B1/B2 修、B3 误报、B4 待确认、B5 不动、extend_due 不动 |

## 代码巡检（code-audit）

- 规则：`skills/x-code-audit/`
- 题面：`evals/problems/code-audit/`；考点：`evals/answers/code-audit/checks.json`；判分：`evals/scripts/audit_grade.py`

| 用例 | 考的规则 | 正确做法 |
|---|---|---|
| full | 一份报告、8 位检查 ID、开头写范围、verify 通过、P0→P2、大白话三要素；AI 层找到吞异常、职责混杂、只断言 mock 的测试、N+1、常量多处不一致；不把 week_header 的七天双循环报成严重性能问题，不在 L4–L6 审命名 | 全部满足 |
| module | 只查 src/library/notify：找到 send() 把失败当成功；L2/L4/L6 不报模块外的问题 | 全部满足 |

## 还没有题的规则

- 暂无。
