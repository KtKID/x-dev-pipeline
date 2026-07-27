# implementation · 开发清单

> spec: docs/spec/journal-index-recovery
> risk: Q3

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | 实现 canonical journal record 编码、CRC 与严格解码校验。 | SC_01 | `J1`：journal 格式与 CRC 是重放真相源 | `fixture/backend/record.py` | None | [x] 🟢 | R3 re-review resolved issue-1 |
| T2 | 实现锁内加载、状态机、版本、请求幂等与有序查询。 | SC_02, SC_03, SC_04, SC_05, SC_06, SC_07 | `J2`：seq、tombstone、request history 持久化不变量 | `fixture/backend/store.py`, `fixture/backend/record.py` | T1 | [!] 🔴 | None |
| T3 | 实现 state-dir 共享/独占进程锁和初始化资源生命周期。 | None | `J6`：并发决策与 append 在同一独占锁内 | `fixture/backend/locking.py` | None | [x] 🟢 | None |
| T4 | 实现日志损坏分类、recover、snapshot 校验与原子 compact。 | SC_08, SC_09, SC_10, SC_11 | `J3`、`J4`、`J5`：恢复、临时文件与 fsync 持久化窗口 | `fixture/backend/store.py`, `fixture/backend/record.py`, `fixture/backend/locking.py` | T1, T2, T3 | [x] 🟢 | R3 re-review resolved issue-5,issue-6 |
| T5 | 实现 CLI 参数/JSON/退出码，并添加真实进程 smoke、重启与并发验证。 | SC_12, SC_13 | `J6`、`J7`：公开 CLI 契约和跨进程序列化 | `fixture/backend/cli.py`, `fixture/backend/store.py`, `fixture/backend/locking.py`, `tests/test_journal_cli.py` | T1, T2, T3, T4 | [!] 🔴 | None |
