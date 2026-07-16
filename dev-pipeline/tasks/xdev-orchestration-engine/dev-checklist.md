# xdev-orchestration-engine · 开发清单

<!--
状态列采用 token+emoji 双轨格式（本 task 自身定义的新规范，T3 落地后同步进 x-req 模板）：
- 机器读 token：[ ] 未完成 / [x] 完成 / [!] 阻塞
- 人读 emoji：⏳ 未开始 / ▶️ 进行中 / 🟡 待测试 / 🟢 测试通过 / ✅ 已完成 / 🔴 测试失败
- 列内格式：`[ ] ⏳`（token 在前，emoji 在后）
- status 子命令压缩映射：[ ](⏳▶️🟡)→todo、[x](🟢✅)→done、[!](🔴)→blocked
-->

**状态体系**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

需求、技术设计、DoD、Smoke/E2E 见同目录 `README.md`。本清单只跟踪状态。

---

## 任务清单

| # | 任务 | 涉及文件 | 依赖 | 状态 | fix |
|---|------|---------|------|------|-----|
| T1 | status 子命令：checklist 解析 + token 状态判定 + JSON 输出 | tools/xdev.py | — | [x] 🟢 | — |
| T2 | graph 子命令：拓扑排序 + ready/blocked + 环检测 + JSON 输出 | tools/xdev.py | T1 | [x] 🟢 | — |
| T3 | dev-checklist 格式升级：状态列 token+emoji 双轨 + x-req 模板同步 | skills/x-req/templates/dev-checklist.md, skills/x-dev/SKILL.md | T1,T2 | [x] 🟢 | — |
| T4 | x-dev skill 改造：并行判断段前调 status + graph，按 ready 派子 agent | skills/x-dev/SKILL.md | T1,T2,T3 | [x] 🟢 | — |
| T5 | 单元测试：status + graph + 兼容性 + 环检测 + fixture | test/ | T1,T2 | [x] 🟢 | — |
| T6 | 文档：README 顶部加编排引擎说明 + xdev.py docstring / --help 更新 | tools/xdev.py (docstring), README.md | T1,T2 | [x] 🟢 | — |

## 并行机会

无依赖关系、可并行起子 agent 同时做（依赖关系由 graph 子命令算出，以下是静态分析）：

- T3（格式升级 + 模板同步）与 T5（单元测试）在 T1/T2 完成后可并行：T3 改模板和 SKILL.md 文档段，T5 写测试，无写冲突。
- T4（x-dev skill 改造）与 T6（文档）在 T3/T5 完成后可并行：T4 改 skills/x-dev/SKILL.md，T6 改 tools/xdev.py docstring 和项目 README.md，无写冲突。

## 串行硬约束

- T1 → T2 必须串行：graph 复用 status 的 checklist 解析逻辑（first_table/col_values/token 判定），status 先落地。
- T3 依赖 T1+T2：格式升级要等两个子命令的 token 规范定型后再同步进模板。
- T4 依赖 T1+T2+T3：x-dev skill 改造要调真实的 status/graph，且依赖新格式落地。
- T5 依赖 T1+T2：测试要对着已定型的解析/排序逻辑写。

## 推荐执行顺序

```
T1 → T2 → [T3 ‖ T5] → T4 → T6
```

说明：T1 先落地 status（确立 JSON schema 和解析复用点）；T2 复用 T1 解析实现 graph；T3（格式升级）与 T5（单元测试）在 T1/T2 后并行；T4 在 T3 后改造 x-dev skill；T6 最后补文档。

## fix-attempts 记录

每个 task 自身走完整 verify + qua-gate 流程时的 fix 次数累计，超 6 次须升级。

| Task | fix 次数 | 触发节点 | 备注 |
|------|---------|---------|------|
| —    | 0       | —       | 尚未开始 |
