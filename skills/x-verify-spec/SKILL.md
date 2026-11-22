---
name: x-verify-spec
description: |
  开发后唯一的一道验收，支持 x-dev 的 dev-checklist 与 x-qdev 单文档。先派一个便宜的子 agent 做一次功能检查：本轮场景、约束和设计有没有做到、有没有漏做多做，测试是不是真的在测、有没有测到场景的预期结果；再运行 xdev check 机械核对编号、状态、场景→用例→测试、测试全绿、改动行覆盖率 100% 和功能检查回执。risk Q0 不做功能检查。发现问题交 x-fix 批量修，最多 3 轮。全项目的约束、规范和性能交给定期巡检，这里不查。触发：x-dev/x-qdev 交付、用户提到 x-verify-spec、verify、验收或复核 task。
---

# x-verify-spec · 验收

## 定位

开发做完以后只验收一次，查过的不再查第二遍。分两部分：

| 部分 | 谁做 | 查什么 |
|---|---|---|
| 功能检查 | 一个便宜的子 agent，只跑一次 | 任务文档和本轮设计都做完了没有：本轮场景、本轮 C（含用户定的“架构：”约束）、本轮 D，没漏做、没多做；测试是不是真的在测、有没有测到场景要的结果 |
| `xdev check` | 脚本 | 能机械判断的全部：编号、状态、场景→用例→测试、测试全绿、改动行覆盖率 100%、功能检查回执 |

范围只到本轮 spec 和 tech-design。不在这里查的：本轮没用到的约束和设计、`engineering` 的全项目约束、开发规范 R1–R7、边界扫查、代码规范、死代码、性能。这些交给定期巡检：`x-audit-arch`、`x-audit-style`、`x-audit-perf`。

覆盖率不在这里跑：开发阶段由开发者自己跑 `xdev coverage`，不到 100% 自己补测试（见 [x-dev「测试是硬规则」](../x-dev/SKILL.md#测试是硬规则)）。这里只核对记录。

下文的 `xdev` 指 `python3 <x-dev skill 目录>/scripts/xdev.py`。目标是常规 task 目录，或 qdev 的 task `.md`。

## 做法

1. **确认开发已做完**：全部行 `[x] 🟢`，`xdev coverage` 通过。没做完就退回开发负责方。
2. **功能检查**：checklist 头部 `risk: Q0`，或 qdev 只记变更、没写场景，跳过这一步。其余先运行一次 `xdev check`，它报 FEATURE_CHECK 并列出要检查的测试文件完整清单；再按 [功能检查](references/feature-check.md) 的派工单派一个子 agent，回执原样存为证据目录里的 `feature-check.md`，只存这一份。环境里派不了子 agent 时，主 agent 不自己代查：回执写 `⏸️ 验收未完成 · 缺功能检查`，把填好的派工单交给调用方代派，回执按原样存好后再往下走。
3. **运行 `xdev check <目标> --json`**，它核对的内容：

   | 规则 | 意思 |
   |---|---|
   | TASK_FILE / HEADER* / COLUMNS / ROWS / ROW_ID / STATUS / SCENE_REF / C_REF / D_REF / CASE_REF / FILES / RISK_CELL / GROUP* / DEP* / RISK / BASELINE | 结构和编号（同 `xdev validate`） |
   | PHASE_LIMIT | 只在校验 spec 目录时出现：同一期没交付的 feat 超过 5 个 |
   | SPEC_CHANGED | 拆解基线之后 spec / tech-design 改了还没同步 |
   | ROW_STATUS | 有行不是 `[x] 🟢` 或 `[x] ✅` |
   | MAPPING / CASE_UNMAPPED / SCENE_UNCOVERED | 用例对应表是空的；用例没对应到测试；本轮场景没有通过的用例 |
   | MAPPING_PATH / MAPPING_RESULT / MAPPING_MANUAL | 测试文件或测试函数不存在；结果不是通过；人工记录不在证据目录 |
   | HIGH_RISK | 高风险行没有通过的 smoke / 集成 / e2e 用例 |
   | CODE_BASELINE / COVERAGE / TESTS / COVERAGE_STALE / COVERAGE_EXCLUDE | 没记代码基线；没有覆盖率记录或不到 100%（报告里没有、也没在「问题与处置」写理由的文件算没覆盖）；测试命令没通过；覆盖率跑完后代码又改了；新加的排除标记没写理由 |
   | FEATURE_CHECK / FEATURE_CHECK_STALE | 要做功能检查却没有回执，或回执没列全改动的测试文件；回执写在最后一次跑覆盖率之前（代码或测试改过，要重做）。报错里都带要检查的测试文件完整清单 |
   | FEATURE_CHECK_OPEN | 回执里还有 P0/P1 没修，也没写不采纳理由 |
   | SPEC_CONFIRM | qdev：①没有 spec 确认记录 |

4. **qdev 另外人工看三项**（脚本只查①的确认记录有没有填，查不了内容对不对）。每项结论是核对通过、核对未完成或核对不通过；有一项未完成，整体就是验收未完成，有一项不通过，整体就是验收不通过：
   - **spec 确认记录**：对照这次 spec 实际改了什么判断。
     - 改了场景或约束（新增、修改、退役，包括往 engineering 加约束），记录写了用户确认的时间和消息位置 → 核对通过。
     - 改了场景或约束，记录只写“已确认”、或是开发者自检、或没写时间和位置 → **核对未完成**：确认可能有，但拿不出可查的记录，补上再验。
     - 改了场景或约束，记录却写“只记变更 / 未写场景，无需确认” → **核对不通过**：记录和实际改动矛盾。
     - 只加了变更记录、没动任何场景和约束，记录写“未写场景，无需确认” → 核对通过。
   - spec 增量确实写进了所属 spec，场景原文和①一致。
   - changelog 和 task 互相有链接；①写的“修改前定位”能找到旧内容。
5. **有问题就修**：问题去向见下一节。需要改代码或测试的，一次交 x-fix 批量修完，按 [x-fix 验收回流模式](../x-fix/references/verify-fix-mode.md) 走。x-fix 交回时已重跑 `xdev coverage`；代码或测试改过，主 agent 就重做第 2 步，再跑第 3 步。最多 3 轮，轮数记在「问题与处置」的 `x-fix 第 N 轮` 行；3 轮还不过，x-fix 记一行 `x-fix 卡住`，主 agent 停下告诉用户卡在哪。
6. **通过**：`xdev check` 通过，功能检查（要做时）通过或只剩 P2。常规 task：主 agent 把行升为 `[x] ✅`，头部状态改为已完成；qdev：⑤的交付状态写验收通过。再把 spec 里本轮 feat 的状态改为“已验收”，变更记录里本轮那一行的状态也改为“已验收（<日期> 验收通过）”。P2 在「问题与处置」各记一行登记。多 agent 协作时只对合并后的整个 task 验收一次，见 [多 agent 协作开发](../x-dev/references/parallel-dev.md)。

## 问题去向

| 问题 | 交给谁 |
|---|---|
| FEATURE_CHECK_OPEN（功能检查的 P0、P1）；TESTS、COVERAGE、HIGH_RISK、MAPPING_PATH（测试不存在）、CASE_UNMAPPED、SCENE_UNCOVERED、MAPPING_RESULT（用例失败） | x-fix，占一轮 |
| COVERAGE_STALE | 主 agent 重跑 `xdev coverage`，不占轮数；已经做过功能检查的，接着重做功能检查 |
| FEATURE_CHECK、FEATURE_CHECK_STALE（回执缺失、没列全或过期） | 主 agent 按报错里的完整清单重新派子 agent，不占轮数 |
| COVERAGE_EXCLUDE、MAPPING_MANUAL、MAPPING（表为空）、ROW_STATUS、CODE_BASELINE | 开发负责方补记录或状态（x-dev / x-qdev），不占轮数 |
| 结构与编号类、SPEC_CHANGED、SPEC_CONFIRM | 来源负责方（x-req / x-tech-design / x-ask-spec），不调 x-fix。SPEC_CHANGED 按 [需求变化同步](../x-tech-design/references/change-sync.md) 处理后 `xdev baseline` |
| 需求本身有歧义 | 列出 feat / 场景和要确认的行为，交 x-ask-spec 问用户 |

一次列全，不自动启动其他 skill。

## 回执

```text
✅ 验收通过 · <task> · 功能检查通过（P2 ×N）/ Q0 不需要 · xdev check 通过 · 改动行覆盖率 100%（K 行）
❌ 验收不通过 · <task> · <N> 项：<来源 · 编号或规则 · 摘要> · 去向：...
⏸️ 验收未完成 · <task> · 缺：<无法运行的原因，如没有 git、没有交付文档、开发没做完、派不了功能检查的子 agent>
```
