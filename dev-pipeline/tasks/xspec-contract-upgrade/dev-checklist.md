# xspec-contract-upgrade · 开发清单

**状态体系**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

需求、技术设计与验收 Scenario 见同目录 `README.md`。本清单只跟踪状态。

---

## 任务清单

| # | 任务 | 涉及文件 | 依赖 | 状态 | fix |
|---|------|---------|------|------|-----|
| T1 | P0 场景契约公共解析器 + profile 分派（spec7/task=新契约；capability/change=原契约；V3/V12 共用） | 🔍 tools/xdev.py | — | [ ] ⏳ | — |
| T2 | P0 V2 重定义：死链检查 + 按 README 路径解析语义表实现（含空格/尖括号/fragment/绝对路径族） | 🔍 tools/xdev.py | — | [ ] ⏳ | — |
| T3 | P0 spec_tier 档位事实源解析 + V1 分档（lite=README/01/90，full=7 件，缺省 full） | 🔍 tools/xdev.py | — | [ ] ⏳ | — |
| T4 | P0 V5 升级：Requirement 名回指（合法通过 / 悬空报错 / 重名歧义） | 🔍 tools/xdev.py | T1 | [ ] ⏳ | — |
| T5 | P0 01 模板：DoD 段 R/S 化 + 追溯矩阵键改 Requirement 名 | skills/x-spec/templates/01-goals-and-boundaries.md | T1 | [ ] ⏳ | — |
| T6 | P0 02/90 模板：回指格式改 Requirement 名（删 DoD#N、条目 N 示例） | skills/x-spec/templates/02-module-breakdown.md, skills/x-spec/templates/90-task-map.md | T4 | [ ] ⏳ | — |
| T7 | P1 TEMPLATE_GUIDE：DoD 追溯段按 R/S 改写 + 路径规则段替换为死链语义 + spec_tier 分档说明 | skills/x-spec/templates/TEMPLATE_GUIDE.md | T1,T2,T3 | [ ] ⏳ | — |
| T8 | P1 SKILL.md：步骤 6"全部 7 产物"tier 化改写 + 6.2 裁判降级与按档位审 + R7 引用更新 | skills/x-spec/SKILL.md | T2,T3 | [ ] ⏳ | — |
| T9 | P1 SKILL.md：update 三纪律（双向对账两方向操作定义 + 细化 vs 变意图判定条件） | skills/x-spec/SKILL.md | — | [ ] ⏳ | — |
| T10 | P1 全量回归矩阵：新契约正反样例 + lite/full 分档 + OpenSpec 存量包回归 + 悬空/重名 + 路径族 + 现有测试全绿 | test/ | T1,T2,T3,T4,T5,T6,T7,T8,T9 | [ ] ⏳ | — |

## 并行机会

无依赖关系、可并行起子 agent 同时做（也可由 `python3 tools/xdev.py graph <task-dir> --json` 的 parallel_batches 自动算出）：

- 第一批：T1 ‖ T2 ‖ T3 ‖ T9（注意 T8/T9 同文件 SKILL.md，T9 先行、T8 随后，避免写冲突）
- 第二批：T4 ‖ T5（T1 完成后）；T7、T8（各自依赖齐后）
- 第三批：T6（T4 后）
- 收口：T10

## 推荐执行顺序

```
[T1 ‖ T2 ‖ T3 ‖ T9] → [T4 ‖ T5 ‖ T7 ‖ T8] → T6 → T10
```

## fix-attempts 记录

每个 task 自身走完整 verify + qua-gate 流程时的 fix 次数累计，超 6 次须升级。

| Task | fix 次数 | 触发节点 | 备注 |
|------|---------|---------|------|
| —    | 0       | —       | 尚未开始 |

---

*产出时间：2026-07-19（审核修订版）*
