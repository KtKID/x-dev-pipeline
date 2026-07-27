# implement-journal-index · 开发清单

> spec: docs/spec/journal-index-recovery
> risk: Q3

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[ ] 🟡` 待测试 / `[x] 🟢` 测试通过 / `[x] ✅` 已完成 / `[!] 🔴` 测试失败

| # | 任务说明 | Scenario IDs | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---|---|---|---|---|---|---|
| T1 | 建立标准库自动化测试与真实 CLI/并发进程测试夹具 | SC_01, SC_02, SC_03, SC_04, SC_05, SC_06, SC_07, SC_08, SC_09, SC_10, SC_11, SC_12, SC_13, SC_14 | 持久化、故障恢复与并发验收必须具有可复跑证据 | fixture/backend/tests/ | None | [!] 🔴 | None |
| T2 | 实现严格 record codec 与跨进程共享/独占锁 | SC_01, SC_08, SC_14 | record 真相完整性；J1、J2、J6 | fixture/backend/record.py, fixture/backend/locking.py | T1 | [!] 🔴 | None |
| T3 | 实现 snapshot/log 加载、mutation、版本、tombstone 与幂等状态机 | SC_02, SC_03, SC_04, SC_05, SC_08 | seq/version/request 历史关键不变量；J3、J4、J5 | fixture/backend/store.py | T2 | [!] 🔴 | None |
| T4 | 实现损坏分类、recover 与原子 compact | SC_09, SC_10, SC_11, SC_12, SC_13 | 错误截断或非原子替换可造成不可逆数据丢失；J8、J9、J10、J11 | fixture/backend/store.py | T3 | [!] 🔴 | None |
| T5 | 实现 CLI 命令、单 JSON envelope 与稳定退出码 | SC_05, SC_06, SC_07 | 公开契约与错误路由；J7 | fixture/backend/cli.py | T3, T4 | [!] 🔴 | None |
| T6 | 复跑 unit、Smoke、损坏注入、compact 重启与多进程 E2E | SC_01, SC_02, SC_03, SC_04, SC_05, SC_06, SC_07, SC_08, SC_09, SC_10, SC_11, SC_12, SC_13, SC_14 | SC_09 至 SC_14 高损失失败/资源/并发路径 | fixture/backend/tests/ | T5 | [!] 🔴 | None |
