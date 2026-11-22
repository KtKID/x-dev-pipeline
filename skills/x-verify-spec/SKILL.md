---
name: x-verify-spec
description: |
  Gate ① 交付核对，支持 x-dev 的 dev-checklist 与 x-qdev 单文档。运行 xdev check 核对编号、状态、需求变化已同步、每个场景有通过的用例、每个用例有真实测试、高风险行有真实链路、测试通过且改动行覆盖率 100%、测试真实性检查已登记且没过期；qdev 另核对 spec 确认记录与文档同步。只读，输出核对通过、未完成或不通过。触发：x-dev/x-qdev 交付、用户提到 x-verify-spec 或要求 verify/复核 task。
---

# x-verify-spec · Gate ① 交付核对

## 定位

回答“交付记录是不是闭合的、测试和覆盖率是不是真跑过且达标、测试真实性检查是不是做过且没过期”。能用脚本判断的全部交给 `xdev check`，不靠 agent 逐项读。测试代码有没有造假由 x-dev 的 [测试真实性检查](../x-dev/references/test-integrity.md) 判断；测试内容是否对得上场景、设计是否落实，由 [x-qa-gate](../x-qa-gate/SKILL.md) 的 reviewer 判断，这里都不做。

只读：不改交付文档、不重跑开发、不修代码、不递增 `.fix-counter`。

## 做法

1. 运行 `python3 <x-dev skill 目录>/scripts/xdev.py check <目标> --json`。目标是常规 task 目录，或 qdev 的 task `.md`。
2. 它核对的内容：

   | 规则 | 意思 |
   |---|---|
   | TASK_FILE / HEADER* / COLUMNS / ROWS / ROW_ID / STATUS / SCENE_REF / C_REF / D_REF / CASE_REF / FILES / RISK_CELL / GROUP* / DEP* / RISK / BASELINE | 结构和编号（同 `xdev validate`） |
   | SPEC_CHANGED | 拆解基线之后 spec / tech-design 改了还没同步 |
   | ROW_STATUS | 有行不是 `[x] 🟢` 或 `[x] ✅` |
   | MAPPING / CASE_UNMAPPED / SCENE_UNCOVERED | 用例对应表是空的；用例没对应到测试；本轮场景没有通过的用例 |
   | MAPPING_PATH / MAPPING_RESULT / MAPPING_MANUAL | 测试文件或测试函数不存在；结果不是通过；人工记录不在证据目录 |
   | HIGH_RISK | 高风险行没有通过的 smoke / 集成 / e2e 用例 |
   | CODE_BASELINE / COVERAGE / TESTS / COVERAGE_STALE / COVERAGE_EXCLUDE | 没记代码基线；没有覆盖率记录或不到 100%（报告里没有、也没在「问题与处置」写理由的文件算没覆盖）；测试命令没通过；覆盖率跑完后代码又改了；新加的排除标记没写理由 |
   | INTEGRITY / INTEGRITY_STALE | 有新增或改动的测试，证据目录里却没有测试真实性检查回执，或回执没列全这些测试、结论没通过且问题没写不采纳理由；回执写在最后一次跑覆盖率之前（测试改过，要重查） |
   | SPEC_CONFIRM | qdev：①没有 spec 确认记录 |

3. qdev 另外人工看下面几项（脚本只查①的确认记录有没有填，查不了内容对不对）：
   - **spec 确认记录**：对照这次 spec 实际改了什么判断。
     - 改了场景或约束（新增、修改、退役，包括往 engineering 加约束），记录写了用户确认的时间和消息位置 → 这项通过。
     - 改了场景或约束，记录只写“已确认”、或是开发者自检、或没写时间和位置 → **核对未完成**：确认可能有，但拿不出可查的记录，补上再核。
     - 改了场景或约束，记录却写“只记变更 / 未写场景，无需确认” → **核对不通过**：记录和实际改动矛盾。
     - 只加了变更记录、没动任何场景和约束，记录写“未写场景，无需确认” → 这项通过。
   - spec 增量确实写进了所属 spec，场景原文和①一致。
   - changelog 和 task 互相有链接；①写的“修改前定位”能找到旧内容。
4. 各规则交给谁处理，见 [x-fix 门禁回流模式](../x-fix/references/qa-gate-fix-mode.md) 的去向表。
5. 多 agent 协作时，每组的核对由主 agent 在分支上跑 `xdev coverage --out` 完成（见 [多 agent 协作开发](../x-dev/references/parallel-dev.md)），这里只对合并后的整个 task 跑一次。

## 问题去向

- 结构、编号、范围、用例缺失：交 x-req / tech-design 负责方补。
- SPEC_CHANGED：按 [需求变化同步](../x-tech-design/references/change-sync.md) 同步后 `xdev baseline`。
- 行状态、测试、覆盖率、用例对应：交开发负责方（x-dev / x-qdev）修，修完重跑 `xdev coverage` 和 `xdev check`。
- 需求本身有歧义：列出 feat / 场景和要确认的行为，交 x-explore-for-spec 问用户。

一次列全，不自动启动其他 skill。

## 回执

```text
🛡️ Gate① 核对通过 · <task> · xdev check 0 项 · 改动行覆盖率 100%（N 行）· 测试真实性检查已登记
🛡️ Gate① 核对不通过 · <task> · <N> 项：<规则 · 摘要> · 去向：...
🛡️ Gate① 核对未完成 · <task> · 缺：<无法运行的原因，如没有 git、没有交付文档>
```

回执注明：这是机械核对，不是独立审查。
