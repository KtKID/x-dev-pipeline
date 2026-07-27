# implementation · 开发清单

> spec: docs/spec/journal-index-recovery
> risk: Q3

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | 建立 record、状态机、损坏分类与 CLI 契约的失败先行测试 | SC_01, SC_02, SC_03, SC_04, SC_05, SC_06, SC_07, SC_08, SC_09, SC_10, SC_11, SC_12, SC_13 | 持久化与错误契约；J1-J8 | fixture/backend/tests/test_journal.py | None | [x] ✅ | None |
| T2 | 实现规范 record CRC 编解码与严格字段校验 | SC_01 | record 编码不变量；J1、J2 | fixture/backend/record.py | T1 | [x] ✅ | None |
| T3 | 实现 snapshot+log 重放、状态机、版本和幂等语义 | SC_02, SC_03, SC_04, SC_05, SC_06, SC_07 | seq/version/幂等持久化不变量；J3、J4 | fixture/backend/store.py | T2 | [x] ✅ | None |
| T4 | 实现尾部恢复、严格损坏分类与 crash-safe compact | SC_08, SC_09, SC_10, SC_11, SC_12 | 故障恢复与原子持久化；SC_08-SC_12 | fixture/backend/store.py | T3 | [x] ✅ | None |
| T5 | 实现跨进程锁、CLI 参数/JSON/退出码并补齐真实子进程与并发测试 | SC_13, SC_14 | 公开契约与并发关键不变量；J5-J7 | fixture/backend/locking.py, fixture/backend/cli.py, fixture/backend/tests/test_journal.py | T4 | [x] ✅ | None |
| T6 | 复跑 unit、Smoke、E2E 场景并记录可复跑事实证据 | SC_01, SC_02, SC_03, SC_04, SC_05, SC_06, SC_07, SC_08, SC_09, SC_10, SC_11, SC_12, SC_13, SC_14 | 全部验收与 Q3 路由 | docs/spec/journal-index-recovery/tasks/implementation/dev-report.md | T5 | [x] ✅ | None |
