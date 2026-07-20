## 1. 代码

- [x] 1.1 `req.py::acceptance_scenarios` 保留 Scenario 的父 `### Requirement:`，每项输出 `requirement/name/mode`；非 Requirement 的 H3 结束当前作用域
- [x] 1.2 新增 `req.py::task_requirements`，从 `parse_checklist()` 结果按声明顺序去重提取非 `—` 的 Requirement，作为 verify 验收范围
- [x] 1.3 `req.py::verify` 只对账父 Requirement 落在该范围内的 auto Scenario；JSON 增加 `requirements`/`expected_auto`，人类可读输出增加 `requirements:` 一行
- [x] 1.4 新增 `req.py::unparented_auto_scenarios(spec_md)`（返回父 Requirement 为空的 auto 场景名），`verify` 在裁剪前调用：非空时以退出码 2 报告并列出场景名，封堵决策 3(a)(b) 的验收黑洞（判定单点实现，后续 spec 级早期检测复用同一函数）
- [x] 1.5 `req.py::verify` 的 `expected_auto` 按名称去重（同一 task 承接多个 Requirement 且场景重名时不产生重复条目）
- [x] 1.6 `req.py::task_requirements` 的空占位判定对齐 `parse_deps`：抽 `EMPTY_CELL_TOKENS` + `is_empty_cell()`，`#` / `Requirement` / `依赖` 三列共用同一判定，消除写成 ASCII `-` 时「范围静默算空却显示成正常绑定」
- [x] 1.7 订正 `xdev.py` 的 `verify` 子命令 help：去掉「对账 README 自动场景」「含 README.md」，改为按归属 spec.md 对账、需要 `dev-checklist.md` 与 `dev-report*.md`（旧结构分支仍注明 README）
- [x] 1.8 堵掉「验证标记解析不出 = 静默免检」：`VALIDATION_RE` 容忍全角冒号；把 1.4 的 `unparented_auto_scenarios` 扩成 `acceptance_defects(spec_md, scope)`，同时收「无父 Requirement 的 auto 场景」（全局判定）与「解析不出 `验证: auto|manual` 的场景」（本 task 范围内判定，父级为空时一并报）；前提自检与 `task_requirements()` 一起提到执行 auto 命令之前

## 2. 测试

- [x] 2.1 改写 `test_req_engine.py` 中把「单 task 必须覆盖整个 spec」写成断言的用例，替换为同一 spec 下 task-a/task-b 各承接一个 Requirement、各自独立退出码 0
- [x] 2.2 补范围内缺口仍 exit 1、范围内全覆盖 exit 0、Requirement 全 `—` 时范围为空只跑命令、`acceptance_scenarios` 保留父级四条用例
- [x] 2.3 运行 `python3 -m unittest discover -s test`（149 passed）
- [x] 2.4 补 1.4 的三条用例：验收节无 `### Requirement:` 分层、非 Requirement 的 H3 截断作用域（两者均 exit 2 且错误只点名掉队场景），以及无父级的 manual 场景不构成拦截
- [x] 2.5 补 1.5/1.6 的用例：同一 task 内同名 Scenario 的 `expected_auto` 不重复；`Requirement` 列写 `-` 与写 `—` 结果等价（范围为空、exit 0）
- [x] 2.6 补 `dev-checklist.md` 缺失与表头缺关键列各一条 exit 2 用例（spec delta 的 SHALL 此前无覆盖），并断言错误指向 checklist 而非 dev-report
- [x] 2.7 补 1.8 的四条用例：全角冒号与半角等价识别、漏标记 exit 2、范围外漏标记不拦本 task、无父级且无标记仍被报出
- [x] 2.8 重跑 `python3 -m unittest discover -s test`（160 passed）

## 3. skill 与文案对齐

- [x] 3.1 `skills/x-verify/SKILL.md` 的 exit 2 分诊按来源拆开：dev-report 的 verify 块格式/路径问题退回 x-dev；`dev-checklist.md` 缺失或表头不可解析、归属 spec.md 验收分层不合法退回 x-req。（新成因由本变更引入，不属 `xreq-spec-driven` 的下游适配范围；x-verify `## 输入` 的 README→spec.md 迁移仍归那边）

## 4. 归档前自查

- [x] 4.1 运行 `openspec validate xdev-task-scoped-verify --strict`（valid）与 `python3 tools/xdev.py validate`（0 issue）
- [x] 4.2 确认与 `xreq-spec-driven` 的归档顺序：本变更覆盖其 `xdev-verification-engine` delta 中「整份 spec.md 对账」的语义，须在其后归档
- [x] 4.3 补完 1.4-1.8 / 2.4-2.8 / 3.1 后重跑 4.1（strict valid、`xdev.py validate` 0 issue、160 passed）
- [x] 4.4 确认 proposal「不在本变更范围」三项各有归属：`mismatch` + Requirement/Scenario 组合键（后续 change，同时根治同一 task 内同名场景）、spec 级验收分层早期检测（跨 `xdev-task-artifact-engine`，与 xreq delta 交叉）、x-verify/x-qa-gate 读取源迁移（`xreq-spec-driven` tasks 2.3）
