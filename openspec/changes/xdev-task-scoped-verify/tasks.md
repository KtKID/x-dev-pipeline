## 0. 范围基线

上游 [`xreq-spec-driven` tasks.md:56](../xreq-spec-driven/tasks.md) 指派给本 change 四件事，全部在范围内，不得再往后推：

1. task-scoped Scenario 裁剪 —— 见 §1
2. Requirement/Scenario 成对绑定 —— 见 §3
3. 结构化 mismatch —— 见 §3
4. 多 task Gate① 独立闭环 —— 见 §1 + §4

验收基线：`verify` 返回 0 的路径已穷举为 8 条（脚本见 §7.1），每条须归入「合法通过」或「已拦截」，不得存在第三态。

## 1. 已完成：task-scoped 裁剪

- [x] 1.1 `acceptance_scenarios` 保留 Scenario 的父 `### Requirement:`，每项输出 `requirement/name/mode`；非 Requirement 的 H3 结束当前作用域
- [x] 1.2 新增 `task_requirements`，按声明顺序去重提取 checklist 承接的 Requirement
- [x] 1.3 `verify` 只对账父 Requirement 落在范围内的 auto Scenario；JSON 增加 `requirements`/`expected_auto`，人类可读输出增加 `requirements:` 一行
- [x] 1.4 `expected_auto` 按名称去重
- [x] 1.5 订正 `xdev.py` 的 `verify` 子命令 help（去 README 说法）

## 2. 已完成：前提自检与占位符收敛

- [x] ~~2.1 `acceptance_defects(spec_md, scope)`：无父 `### Requirement:` 的场景、解析不出 `验证: auto|manual` 的场景 → exit 2~~ **应撤销，见 §2.8**：这两条检查 `xdev.py` 的 V3（`scenario_contract_issues`，spec2 profile）早已实现，属重复造轮子
- [x] 2.2 `VALIDATION_RE` 容忍全角冒号（V3 用的是同一个 `VALIDATION_RE`，放宽对两处同时生效，保留）
- [x] 2.3 撤销自造的 `EMPTY_CELL_TOKENS`：改用「scope 内每个名字必须在 spec.md 验收 Requirement 中存在」的悬空检查，一条规则顶掉所有形近写法特判
- [x] 2.4 `Requirement` 列缺失（表头无该列）与空单元格 → exit 2，不再静默算作无绑定
- [x] 2.5 占位符统一 `None`：上游契约条文、x-req2 模板/SKILL、`req.py` 五处判定、测试与 30 个夹具文件（185 处）
- [x] 2.6 x-verify 去 README：`SKILL.md` 输入描述改 checklist + spec.md；`templates/verify-report-template.md` 的旧路径 `dev-pipeline/tasks/` 与表头 `README Scenario` 同步
- [x] 2.7 x-verify exit 2 按来源分诊：dev-report → x-dev，dev-checklist → x-req，验收标注 → x-spec
- [ ] 2.8 **消除与 V3 的重复实现**：删除 `verify.py::acceptance_defects` 及其五条测试；改为在 `xdev.py` 调用 `verify.py` 前置调用 spec 包校验，V3 有 issue 时 exit 2 并退回 x-spec。理由：`scenario_contract_issues` 的 spec2 profile 已覆盖「Requirement 无 Scenario」「Scenario 无上级 Requirement」「Scenario 缺验证标记」三条，verify 侧重写一份必然漂移

## 3. 待做：成对绑定与结构化 mismatch（上游指派 2、3）

对账主键从 `scenario` 名改为 `(requirement, scenario)`。这是本 change 唯一改产物格式的部分。

- [ ] 3.1 `parse_verify_blocks` 增加 `requirement` key（`VERIFY_KEYS` 扩容）；auto 块 SHALL 同时给出 `requirement:` 与 `scenario:`，缺任一 → exit 2
- [ ] 3.2 `verify` 的覆盖判定改用 `(requirement, scenario)` 组合键；`expected_auto` 每项输出 `{requirement, name}` 而非裸名字
- [ ] 3.3 输出结构化 `mismatch`，至少覆盖三类：
  - 越界绑定：块回指的 Requirement 不在本 task scope 内（穷举 ⑧）
  - 父级错配：`requirement:` 与 `scenario:` 在 spec.md 中不构成父子
  - mode 漂移：spec.md 标 manual 的场景被 auto 块回指，或反之
- [ ] 3.4 同一 Requirement 内的 Scenario 重名 → exit 2（结构错误，非去重可解）
- [ ] 3.5 删除 [`test_duplicate_scenario_name_in_scope_counts_once`](../../../test/test_req_engine.py)——它把「一份证据顶两份」固化成了期望行为，改为断言组合键下两条各自独立
- [ ] 3.6 dev-report 模板与四个 skill 同步 `requirement:` 字段：`skills/x-dev/templates/dev-report-template.md`、x-dev（写证据）、x-verify（读回执）、x-qa-gate（R3 对照）、x-fix（修复后补证据）

## 4. 待做：`--only` 的 partial 语义（上游指派 4）

- [ ] 4.1 `--only` 时输出 `partial: true` 与 `selected: [id...]`；全量执行时 `partial: false`
- [ ] 4.2 `partial` 为真时不计算 `uncovered`（未执行块的 `scenario:` 声明 SHALL NOT 计入覆盖），JSON 与人类可读输出都要显式标注
- [ ] 4.3 x-verify SKILL：`partial` 结果 SHALL NOT 用于 Gate① 放行，只用于定位单块失败

## 5. 待做：manual 场景与空 Requirement 的丢失面

- [ ] 5.1 输出的 `manual` 列表改为以 **spec.md 范围内的 manual Scenario** 为准，与 dev-report 的 manual 块做对账；spec 有而 dev-report 缺 → 列入未认领而非静默（现状：`manual` 只来自 dev-report，spec.md 的 manual 场景完全不被感知，穷举 ④）
- [ ] ~~5.2 无父 Requirement 的 Scenario 不分 auto/manual 一律 exit 2~~ → 并入 §2.8：V3 的 `orphan: True` 已对所有孤儿 Scenario 报 issue，不分 mode，verify 侧不需要自己判
- [ ] ~~5.3 scope 内的 Requirement 在 spec.md 下一个 Scenario 都没有 → exit 2~~ → 并入 §2.8：V3 的「Requirement 没有任何 Scenario」已覆盖。**这条本就不该由 verify 承担**——spec.md 是 x-spec2 的产出，写得全不全属 spec 包门禁，verify 只负责证据对账
- [ ] 5.4 `cmd: true` 之类空壳证据块（穷举 ⑦）：引擎不可判定，写入 design「已知限制」并注明由 x-qa-gate R3 承担，不在引擎侧加启发式

## 6. 待做：文档与文案

- [ ] 6.1 proposal 的「不在本变更范围」删除成对绑定 / mismatch / partial 三项（它们已在 §3、§4）
- [ ] 6.2 design 补决策：组合键、partial 语义、manual 对账、空 Requirement 拦截、空壳块的已知限制
- [ ] 6.3 spec delta 增补对应 SHALL 与 Scenario，覆盖 §3-§5 每一条
- [ ] 6.4 统一分诊文案：本 change tasks 与 x-verify SKILL 都写「验收标注错误 → x-spec」（当前 tasks 残留「→ x-req」）

## 7. 待做：报回上游 `xreq-spec-driven`

- [ ] 7.1 `validate` 未实现契约已声明的「`Requirement` 空单元格 SHALL 被报出」——REQ4 只查了 `任务说明` 与 `风险` 两列，实测空 Requirement 单元格 validate 返回 0
- [ ] 7.2 `skills/x-qa-gate/` 4 个文件（SKILL.md、rc-unified.md、r1-spec-conformance.md、r2-boundary-coverage.md）与 `skills/x-fix/SKILL.md` 仍以 README 为读取源，属其 tasks 2.3 未完项
- [ ] 7.3 上游 11 个未勾任务完成前，本 change 不得归档

## 8. 归档前自查

- [x] 8.1 `openspec validate --strict`、`xdev.py validate`、全量单测（现 164 passed）
- [ ] 8.2 §3-§5 完成后重跑 8.1，并重跑通过路径穷举脚本，确认 8 条路径各自归位
- [ ] 8.3 确认归档顺序：本 change 覆盖 `xreq-spec-driven` 的 `xdev-verification-engine` delta，须在其后归档
- [ ] 8.4 端到端：在 `docs/spec/` 下建一个真实 req2 spec 包 + 两个 task，跑通 scaffold → 填写 → validate → dev-report → verify 全链路（至今全部验证都在临时目录的构造样本上完成）
