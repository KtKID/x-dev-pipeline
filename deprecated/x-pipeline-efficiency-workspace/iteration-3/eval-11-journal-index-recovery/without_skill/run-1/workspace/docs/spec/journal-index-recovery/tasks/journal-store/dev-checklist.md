# journal-store · 开发清单

> spec: docs/spec/journal-index-recovery
> risk: Q3

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | 建立 record、状态机、损坏/恢复/压缩的失败先行单元与 CLI smoke 测试 | SC_01, SC_02, SC_03, SC_04, SC_05, SC_06, SC_07, SC_08, SC_09, SC_10, SC_11, SC_12, SC_13, SC_16 | 持久化不变量；J1–J7 | `tests/test_journal.py` | None | [x] ✅ | None |
| T2 | 实现严格 record codec 和 POSIX state-dir 读写锁资源生命周期 | SC_01, SC_08 | record/locking 不变量；J1、J4 | `fixture/backend/record.py`, `fixture/backend/locking.py` | T1 | [x] ✅ | None |
| T3 | 实现 snapshot+log 加载、严格重放、CRUD、版本和幂等提交 | SC_02, SC_03, SC_04, SC_05, SC_06, SC_07, SC_08 | seq/version/幂等不变量；J2、J3、J7 | `fixture/backend/store.py` | T2 | [x] ✅ | None |
| T4 | 实现最后物理记录分类、精确尾部截断与中段/snapshot 损坏只读失败 | SC_09, SC_10, SC_11 | 恢复错误改写会丢失真相 | `fixture/backend/store.py` | T3 | [x] ✅ | None |
| T5 | 实现 snapshot 完整序列化、tmp+replace+目录 fsync 压缩与崩溃重叠重放 | SC_12, SC_13 | compact 两阶段崩溃窗口；J3、J6 | `fixture/backend/store.py` | T4 | [x] ✅ | None |
| T6 | 实现全命令 CLI、唯一 JSON 渲染和稳定退出码 | SC_02, SC_10, SC_12, SC_16 | 公开 CLI 契约；J5 | `fixture/backend/cli.py` | T3, T4, T5 | [x] ✅ | None |
| T7 | 建立并发不同 key 和同 key 版本竞态的真实多进程 E2E 测试 | SC_14, SC_15 | 独占锁原子性；J4 | `tests/test_journal.py` | T6 | [x] ✅ | None |
| T8 | 复跑全部 unit/smoke/e2e 并记录每个 Scenario 的可执行事实证据 | SC_01, SC_02, SC_03, SC_04, SC_05, SC_06, SC_07, SC_08, SC_09, SC_10, SC_11, SC_12, SC_13, SC_14, SC_15, SC_16 | Q3 全契约交付门禁 | `tests/test_journal.py`, `docs/spec/journal-index-recovery/tasks/journal-store/dev-report.md` | T7 | [x] ✅ | None |
