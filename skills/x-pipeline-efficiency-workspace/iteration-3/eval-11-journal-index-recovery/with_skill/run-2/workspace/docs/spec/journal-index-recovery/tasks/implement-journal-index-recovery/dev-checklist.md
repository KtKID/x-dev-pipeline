# implement-journal-index-recovery · 开发清单

> spec: docs/spec/journal-index-recovery
> risk: Q3

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | 实现严格 record codec，并用单元测试固定规范 JSON、字段类型、行尾和 CRC 契约 | SC_01 | J1/J2：损坏记录不得进入状态机 | fixture/backend/record.py, fixture/backend/tests/ | None | [x] ✅ | issue-1 |
| T2 | 实现 state-dir 生命周期及共享/独占跨进程文件锁 | None | J3：重放到持久化的独占区间保证 seq 与更新原子性 | fixture/backend/locking.py, fixture/backend/tests/ | None | [x] ✅ | None |
| T3 | 实现日志重放、put/get/delete/list、乐观版本和全局幂等状态机及单元测试 | SC_02, SC_03, SC_04, SC_05 | store 关键不变量、J4/J5：失败无追加且重试保留首次结果 | fixture/backend/store.py, fixture/backend/tests/ | T1, T2 | [x] ✅ | issue-2 |
| T4 | 实现尾部恢复、中段/快照损坏分类、原子 compact 与提交窗口兼容测试 | SC_06, SC_07, SC_08, SC_09 | J6/J7/J10：持久化故障不得静默回退或扩大损坏 | fixture/backend/store.py, fixture/backend/tests/ | T3 | [x] ✅ | issue-2, issue-3 |
| T5 | 实现单 JSON CLI、参数校验、业务错误退出码和真实子进程 smoke 测试 | SC_12 | CLI 公开契约、J8/J9：所有调用保持机器可消费 | fixture/backend/cli.py, fixture/backend/tests/ | T3, T4 | [x] ✅ | issue-4 |
| T6 | 增加真实多进程不同 key 与同 key 竞争 E2E，复跑完整验收并记录证据 | SC_10, SC_11 | J3、SC_10/SC_11：竞态可造成丢失更新或多胜者 | fixture/backend/tests/ | T5 | [x] ✅ | issue-5 |
