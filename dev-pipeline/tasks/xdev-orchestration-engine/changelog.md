# 变更记录

<!--
x-req 产出本文件初始版本（表头 + 一条"创建 task"记录）。
后续状态变更、开发进度、修复记录由 x-dev 维护（见 x-dev references/execution-rules.md 的变更记录格式）。
列结构：时间 / 操作 / 内容，与 x-qdev changelog 保持一致。
-->

| 时间 | 操作 | 内容 |
|------|------|------|
| 2026-07-15 | 创建 task | x-req 产出 README / dev-checklist / diagram。本次 task 目的：给 tools/xdev.py 加编排引擎 status + graph 两个子命令，把 x-dev-pipeline 从「LLM 自己推理调度」升级为「脚本算调度，LLM 照 JSON 执行」——status 解析 dev-checklist 输出进度 JSON，graph 做依赖拓扑排序输出 ready/blocked/parallel_batches，并配套升级 dev-checklist 为 token+emoji 双轨格式、改造 x-dev skill 在派子 agent 前调用这两个子命令。 |
| 2026-07-15 | 开始开发 | 开始处理 T1+T2（串行：graph 复用 status 解析）。实现 parse_checklist/parse_deps/task_engine_status/resolve_task_list/compute_progress（status 段）+ topo_sort/compute_graph/graph_command（graph 段）+ 改造 main() argparse 注册两个子命令。 |
| 2026-07-15 | 修复 | 修正 parallel_batches 逻辑：原版把 done 任务和悬空依赖任务也排进批次；修正为只含未 done 任务、悬空依赖任务排除、done 视作前置已满足起步集。修正后 SM-002（全 done）batches 为空、SM-003 T5（悬空依赖）被正确排除。 |
| 2026-07-15 | 发现设计问题 | T1/T2 标 `[x] 🟡`（token=done + emoji=待测试）导致 status 判 done，但实际未过 gate。修正为 `[ ] 🟡`（token=todo + emoji=待测试）。这验证了 token 优先于 emoji 的设计：引擎让状态语义精确化，矛盾标注立刻暴露。 |
| 2026-07-15 | 测试通过 | SM-001~SM-005 全部通过（旧 emoji 兼容/拓扑排序/状态混合+product 锚点+悬空依赖/环检测）。自测覆盖边界：依赖分隔符多格式、task id 归一化、纯 emoji 降级。dev-report 已写，准备进 Gate ① x-verify。 |
| 2026-07-15 | Gate ② fix | RC 第 1 轮发现 F1（P1）：纯数字 task id 被静默丢弃但 dev-report 声称已支持。修复：新增 ID_COL_RE（id 列接受纯数字），parse_checklist 改用它，parse_deps 仍用 TASK_ID_RE（依赖列要求前缀，符合契约）。F2-F5（P2）登记：priority 字段未解析、graph schema 多 task 字段、T2T3 粘连、纯数字 id 丢弃——均 P2 不阻塞。fix-counter 1/3，准备增量复审。 |
| 2026-07-15 | Gate ② pass | RC 第 2 轮增量复审 pass：F1 已修（实测 fixture 验证）+ F5 随 F1 解决 + F2-F4 登记。fix-counter 重置为 0。T1/T2 标 🟢。存档 reports/qa-gate/qa-gate-report-20260715-013500.md。 |
| 2026-07-15 | 开始开发 | 开始 T3-T6。T3：统一 x-req 模板列结构（|#|任务|涉及文件|依赖|状态|fix|，与引擎解析契约一致）+ 双轨状态说明；发现并修复"模板列结构 ≠ 实际产出列结构"的格式契约不一致。T4：x-dev SKILL.md 并行段插入"用编排引擎算调度"小节（先 status+graph 再派子 agent）。T5：新增 test/test_xdev_orchestration.py（31 条 unittest，零依赖标准库）。T6：README 加 Orchestration engine 小节。 |
| 2026-07-15 | 发现设计问题 | T3-T6 初标 `[x] 🟡` → 引擎判 done（token 优先）但实际未过 gate。修正为 `[ ] 🟡`。再次验证 token+emoji 必须一致，引擎让矛盾标注立刻暴露。 |
| 2026-07-15 | 测试通过 | T5 31/31 unittest 通过。全量回归通过（自身 task status 准确、旧 emoji 兼容、语法 OK）。dev-report 更新覆盖 T3-T6，准备进 Gate ① 验证 T3-T6。 |
| 2026-07-15 | Gate ① pass | T3-T6 verify 7/7 命令通过（含 unittest 31→33、SKILL.md 引擎调用落地、旧 emoji 兼容） |
| 2026-07-15 | Gate ② fix | RC（T3-T6）第 1 轮发现 F1（P1）：表头缺关键列失败分支无测试。修复：补 test_missing_required_column + test_status_command_happy_path（顺带激活 F2 的死 helper）。fix-counter 1/3。 |
| 2026-07-15 | Gate ② pass | RC（T3-T6）第 2 轮增量复审 pass：F1 已修（分支命中正确）+ F2 已修（死 helper 激活）。33/33 测试通过。fix-counter 重置为 0。T3-T6 标 🟢。全部 6 任务完成。 |
