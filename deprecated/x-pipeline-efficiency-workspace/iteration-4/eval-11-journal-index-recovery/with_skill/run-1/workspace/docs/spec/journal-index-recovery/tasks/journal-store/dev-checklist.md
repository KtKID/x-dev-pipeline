# journal-store · 开发清单

> spec: docs/spec/journal-index-recovery
> risk: Q3

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | 实现规范 JSONL record 编解码、CRC 和严格字段校验；建立 codec 单元测试。 | SC_01, SC_08, SC_09 | J1：CRC/字段损坏分类决定恢复边界 | `fixture/backend/record.py`, `tests/test_journal.py` | None | [x] ✅ | None |
| T2 | 实现 state-dir 跨进程共享/独占文件锁和目录初始化。 | SC_11 | J5：mutation/recover/compact 独占串行，读取一致 | `fixture/backend/locking.py`, `tests/test_journal.py` | T1 | [x] ✅ | None |
| T3 | 实现 snapshot/log 加载、状态机、版本、tombstone、request registry 与安全 append。 | SC_01, SC_02, SC_03, SC_04, SC_05, SC_06, SC_07 | J2/J3：seq、version、首次结果与无写入失败不变量 | `fixture/backend/store.py`, `tests/test_journal.py` | T1, T2 | [x] ✅ | None |
| T4 | 实现尾部损坏分类/recover、snapshot 验证、原子 compact 与目录 fsync；覆盖重启和并发。 | SC_08, SC_09, SC_10, SC_11 | J4/J5/J7：持久化、故障恢复、replace 顺序与多进程安全 | `fixture/backend/store.py`, `fixture/backend/locking.py`, `tests/test_journal.py` | T2, T3 | [x] ✅ | None |
| T5 | 实现 CLI 参数、稳定 JSON/退出码，并执行真实子进程 smoke 验证。 | SC_01, SC_04, SC_05, SC_06, SC_07, SC_08, SC_09, SC_11 | J6：stdout 单 object、错误码稳定；跨进程并发 | `fixture/backend/cli.py`, `tests/test_journal.py` | T4 | [x] ✅ | None |
