## 1. 前置门禁与 OpenSpec

- [x] 1.1 归档 `xreq-instructions-engine`，将 `xdev-task-artifact-engine` 与 `xreq-lean-planning` 写入主 specs。（`2c25a67`）
- [x] 1.2 创建本 change，完成 proposal、design、两个新 capability spec 与两个主 spec delta。
- [x] 1.3 运行本 change 的严格 OpenSpec 校验，修复全部结构 finding 后进入实现。（`openspec validate unified-flow-verify-engine --strict` 通过）

## 2. Commit A：确定性 verify 引擎与 task 契约

- [x] 2.1 为 `tools/xdev.py` 添加 verify CLI、fenced block 解析、auto/manual 规则、相对 cwd、显式 timeout、exit/contains 事实比对和 JSON/人类输出。
- [x] 2.2 添加 README 自动 Scenario 覆盖对账；fail、uncovered 返回 1，输入、IO 或 parse 错误返回 2。
- [x] 2.3 更新 README instructions、x-req README 模板、confirmation 模板和 x-dev dev-report 模板，采用 risk 字段、验收 Scenario 和 verify 块，删除旧表与 dev-report risk。
- [x] 2.4 修改 V11 并增加 V12，覆盖 Q0/Q1 lite、Q2/Q3 完整章节、risk 合法性、Requirement/Scenario/验证标记和验收内测试责任。
- [x] 2.5 新增 verify 单测，迁移 task validator fixture，并完成 scaffold→validate→verify 的端到端覆盖。
- [x] 2.6 运行完整 unittest、verify 正反样本和 task validate 证据；仅提交 `tools/xdev.py`、模板与测试为 Commit A。（56 tests OK；`/private/tmp/xdev-verify-evidence-{good,bad}` 覆盖 pass/manual 与 fail/uncovered。）

## 3. Commit B：统一活跃流程与退役入口

- [x] 3.1 更新 x-req：集中 Q0-Q3 判据，Q0/Q1 免确认、Q2/Q3 一次确认，写入 risk 并续接 x-dev；删除 qdev promotion。
- [x] 3.2 更新 x-dev：以 verify 块记录场景证据，收尾调用引擎并按 README risk 决定交付或 qa-gate。
- [x] 3.3 将 x-verify 重写为失败诊断薄壳；全过无报告，解析错误退回 x-dev，失败保持现有 fix-counter 规则。
- [x] 3.4 将 x-qa-gate 与 reviewer references 改为 Q2/Q3 路由、最小输入和置信度纪律；清除 changelog 与 qdev 路线。
- [x] 3.5 删除 `skills/x-qdev/` 与 `skills/x-plan/`；改写 x-fix、x-cr auto-loop、x-spec、x-multi-llm-align 的活跃路由与 changelog 引用。
- [x] 3.6 运行 skill 结构检查、行数约束与活跃引用清理；仅提交 `skills/` 为 Commit B。（`claude plugin validate . --strict` 通过；skills 内 qdev/x-plan/changelog 零命中；x-verify 32 行、x-qa-gate 62 行。）

## 4. Commit C：发行面与交付验证

- [x] 4.1 更新中英文 README、install.sh 与 plugin manifest：首体验使用 x-req，命令清单与流程图使用 risk 字段，移除 qdev/x-plan 与陈旧 x-cr alias。
- [x] 4.2 复跑全量 unittest、OpenSpec strict、verify 正反 JSON、x-verify/x-qa-gate 行数、changelog/qdev/x-plan 清理和 diff check。（56 tests OK；plugin strict 通过；OpenSpec strict 通过。）
- [x] 4.3 仅提交 README、install.sh、plugin manifest 为 Commit C；本 change/task 交付材料随归档单独提交；不推送远端。（`889cd07`；后续 `8477628` 修复模板与 schema 的 P1 契约冲突。）
- [x] 4.4 归档本 change，复验主 specs，并生成睡眠开发报告，列出本地 commits、验证证据和未推送状态。（归档为 `2026-07-16-unified-flow-verify-engine`；`openspec validate --all --strict` 4/4 通过；睡眠报告见 `dev-pipeline/sleep-reports/`。）
