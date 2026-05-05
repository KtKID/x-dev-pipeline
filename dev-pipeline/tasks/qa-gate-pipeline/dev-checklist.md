# qa-gate-pipeline · 开发清单

**状态体系**：⏳ 未开始 / ▶️ 进行中 / 🟡 待测试 / 🟢 测试通过 / ✅ 已完成 / 🔴 测试失败

详细 step 与代码见同目录 `plan.md`。本清单只跟踪状态。

---

## 任务清单

| # | 任务 | 涉及文件 | 依赖 | 状态 | fix |
|---|------|---------|------|------|-----|
| T1 | dev-report.md schema 与 x-dev/x-qdev 输出改造 | skills/x-dev/templates/dev-report-template.md, skills/x-dev/SKILL.md, skills/x-qdev/SKILL.md | — | 🟢 | — |
| T2 | x-verify skill 实现（Gate ① 命令复跑） | skills/x-verify/SKILL.md, skills/x-verify/templates/verify-report-template.md | T1 | 🟢 | — |
| T3 | x-qua-gate skill 框架（Gate ② 评审聚合层） | skills/x-qua-gate/SKILL.md, skills/x-qua-gate/templates/qa-gate-report-template.md | T2 | 🟢 | — |
| T4 | R1 spec-conformance reviewer prompt | skills/x-qua-gate/references/r1-spec-conformance.md | T3 | 🟢 | — |
| T5 | R2 boundary-coverage reviewer prompt | skills/x-qua-gate/references/r2-boundary-coverage.md | T3 | 🟢 | — |
| T6 | R3 test-integrity reviewer prompt（反测试镜像化） | skills/x-qua-gate/references/r3-test-integrity.md | T3 | 🟢 | — |
| T7 | x-fix 失败回流改造（4 条规则 + fix-counter 共享） | skills/x-fix/SKILL.md, skills/x-fix/references/qa-gate-fix-mode.md | T2,T3 | 🟢 | — |
| T8 | x-audit-perf skill（独立巡检） | skills/x-audit-perf/SKILL.md, skills/x-audit-perf/templates/audit-perf-template.md | — | 🟢 | — |
| T9 | x-audit-style skill（独立巡检） | skills/x-audit-style/SKILL.md, skills/x-audit-style/templates/audit-style-template.md | — | 🟢 | — |
| T10 | 老 x-cr 重定向 stub + 全局文档更新 + e2e smoke | skills/x-cr/SKILL.md, README.md, README_zh.md, manifests, dev-pipeline/tasks/_e2e-smoke/ | T1-T7 | 🟢 | — |

## 并行机会

无依赖关系、可并行起子 agent 同时做：
- T8 与 T9（两个独立 audit skill）可同时进行
- T4 / T5 / T6 在 T3 完成后可并行（三个 reviewer prompt 互不依赖）

## 串行硬约束

- T1 → T2 → T3 必须串行（dev-report schema → verify 复跑 → qua-gate 调度）
- T4/T5/T6 完成后才能做 T7（x-fix 回流要知道有哪些 fail 类型）
- T10 必须最后做（依赖 T1-T7 全部落地）

## 推荐执行顺序

```
T1 → T2 → T3 → [T4 ‖ T5 ‖ T6 ‖ T8 ‖ T9 (并行)] → T7 → T10
```

## fix-attempts 记录

每个 task 自身走完整 verify + qua-gate 流程时的 fix 次数累计，超 6 次须升级。

| Task | fix 次数 | 触发节点 | 备注 |
|------|---------|---------|------|
| —    | 0       | —       | 本次实现期间未触发回流 |

## 验收联通测试（须用户在新会话人工触发）

⚠️ AI 实现只准备 5 个 case 的 README.md 脚手架（位于 `dev-pipeline/tasks/_e2e-smoke/`），实际触发跑链路必须由用户在新会话执行。

- [ ] Case 01-positive: 端到端正向通过 — 用户跑过且 reports/.fix-counter 为 0
- [ ] Case 02-verify-fail: x-verify 拦下 — 用户确认 verify-report status: fail
- [ ] Case 03-r1-fail: R1 拦下 — 用户确认 qa-gate-report R1 fail
- [ ] Case 04-r2-fail: R2 拦下 — 用户确认 qa-gate-report R2 fail
- [ ] Case 05-r3-fail: R3 拦下 — 用户确认 qa-gate-report R3 fail

**在收到用户全部 5 项确认前，本 task 不能进 ✅ 状态**。在 changelog.md 里也写明"待用户 e2e 验收"。

## changelog 触发

T10 Step 8 完成后，本 task 整体进入 🟢 测试通过（待 e2e 用户验收后再升 ✅），写入 `changelog.md`。
