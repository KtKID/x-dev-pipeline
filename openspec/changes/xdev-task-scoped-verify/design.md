## Context

`xreq-spec-driven` 把 task 归户 `docs/spec/<spec>/tasks/<task>/`，checklist 每行通过 `Requirement` 列回指归属 `spec.md`，并允许一个 spec 拆成多个 task。`tools/verify.py` 的 req2 verify 路径已经把验收数据源从 task README 切到归属 `spec.md`，但对账范围没跟着切——仍是整份 spec.md 的 auto Scenario 对本 task dev-report 的 `scenario:` 回指集合。

单 task 时两者恰好重合，缺陷不显形；一旦拆成多 task 就必然互相拖累。

## Goals / Non-Goals

**Goals:**

- 每个 task 只对账自己 checklist 承接的 Requirement 下的 Scenario。
- 收敛后不留验收黑洞：全 spec 的 Scenario 仍须有人认领。
- 让「范围」在 verify 输出里可见，避免范围算空被误读成验收通过。

**Non-Goals:**

- 改 dev-report 的 verify 块 schema。
- 改 checklist 表头、risk 定级或 task 归户规则。
- 改 x-dev / x-verify / x-qa-gate 的产出与读取契约。
- 检测越界绑定、跨 Requirement 同名 Scenario、mode 漂移（见 proposal 的「不在本变更范围」）。

## Decisions

1. **checklist 的 `Requirement` 列是 task 验收范围的唯一来源**
   - 范围 = 当前 checklist 中所有非空占位的 Requirement，按声明顺序去重（空占位集合见决策 7）。
   - 依据：task 拆分时已经在 checklist 建立了 Requirement 归属，复用该结构即可，不必新增 scope 文件或把 Scenario 复制进 task。
   - 弃：在 dev-checklist 头部新增 `scenarios:` 白名单——制造第二份归属真源，与 `Requirement` 列必然漂移。

2. **spec 验收解析保留 Scenario 的父 Requirement**
   - `acceptance_scenarios()` 每项从 `{name, mode}` 扩为 `{requirement, name, mode}`；非 `### Requirement:` 的 H3 结束当前 Requirement 作用域，此时父级为空串。
   - 依据：裁剪需要父子关系，这是范围判定的最小信息量。

3. **收敛不产生验收黑洞：REQ6 兜底 + verify 侧前提自检，两者缺一不可**
   - `spec_requirement_coverage()`（REQ6）保证归属 spec 的每个 Requirement 都被该 spec 下某个 task 承接。
   - 「因此每个 Scenario 一定落在某个 task 的范围内」这一步推理有三个前提，**都不由 REQ6 保证**，必须逐个落实，否则收窄即等于开洞：
     - **(a) 每个 Scenario 都有父 `### Requirement:`**。无父级时 `requirement` 为空串，而范围只收非空名字 → 该 Scenario 永不进入任何 task 的 `expected_auto`；同时 `spec_requirements()` 为空使 REQ6 直接返回空清单，两道关卡同时静默。由决策 6 在 verify 侧封堵。
     - **(b) `## 验收` 节内不出现非 Requirement 的 H3**。决策 2 规定这类 H3 结束当前作用域，其后的 Scenario 父级为空 → 后果同 (a)。同由决策 6 封堵（一个判定覆盖两种形状）。
     - **(c) REQ6 要在正确时机跑**。REQ6 只在 spec 包级 `xdev.py validate docs/spec/<name>` 触发（`validate_pkg` 的 spec2 分支），`validate <task-dir>` 走 `req.validate_issues`，**不含 REQ6**。而 x-req2 流程只跑 task 级 validate、x-verify 只跑 verify——task 阶段把 `Requirement` 列改成 `—`、或往 spec.md 追加 Requirement，都不会重新触发兜底。故 verify 不能把「REQ6 已经跑过」当作既成事实，只能把自己范围内的前提自检做实（决策 6），跨 task 的覆盖闭合仍依赖 x-spec2 阶段的 spec 级 validate。
   - 防：只收窄 verify 而不逐条落实上述前提，会让「没有任何 task 承接的 Requirement」和「没有挂在任何 Requirement 下的 Scenario」在 Gate① 彻底静默——本该 fail 的 spec 变成全绿，且改造前这些 Scenario 是会被对账的（属回归）。

4. **范围随结果一起输出**
   - JSON 增加 `requirements` 与 `expected_auto`，人类可读输出增加 `requirements:` 一行（空范围显示「(无验收绑定)」）。
   - 防：`uncovered: []` 有两种成因——真覆盖了，和 checklist 的 Requirement 列全是空占位导致范围为空。不输出范围就无法区分，纯技术 task 与漏填 Requirement 的 task 在 Gate① 长得一模一样。

5. **checklist 不可解析时沿既有失败路径**
   - verify 因此新增了对 `dev-checklist.md` 的读取依赖；缺失或表头不合法时 `parse_checklist()` 抛错，由 verify 既有的 except 收敛为退出码 2。
   - 依据：与 spec 包非法、dev-report 缺失的处理一致，不为新依赖另立错误码。
   - 连带：exit 2 的成因集合因此扩大，x-verify 现有的「退回 x-dev」单一分诊会把 x-req 的产物问题指错人，须按来源拆开（见 Risks 与 proposal Impact）。

6. ~~**验收标注不足以判定归属时 verify 自行检查**~~ **（已撤销，见决策 13）**
   - 本决策建立在一个未经核实的前提上：以为没有现成的 spec 结构校验。实际 `xdev.py` 的 V3（`scenario_contract_issues`，spec2 profile）早已覆盖「Requirement 无 Scenario」「Scenario 无上级 Requirement」「Scenario 缺 `验证:` 标记」三条。下面的论证保留作记录，实现按决策 13 撤销。
   - 判定单点实现在 `acceptance_defects(spec_md, scope)`，verify 调用后非空即退出码 2 并一次列全；spec 级 validate 的早期检测留给后续 change 复用同一函数（不传 scope 即全量），不各写一份。收两类缺陷：
     - **无父 `### Requirement:` 的 auto 场景**：不进入任何 task 的范围，REQ6 又因 Requirement 全集为空而静默，两道关卡同时失效 → **不受 scope 限制，始终报**。
     - **解析不出合法 `验证: auto|manual` 的场景**：`mode` 为 `None` 时既不进 `expected_auto` 也不进 `manual`，等于自动免检 → 这类场景有父 Requirement、**能够归属**，故按 task-scoped 原则只报落在本 task 范围内的；范围外由承接它的那个 task 拦。两类的范围差异不是随意的：能归属的按归属拦，不能归属的只好全局拦。
   - 依据：裁剪有两个前提——场景挂在 Requirement 下、且标了谁来验。任一不成立时 verify 都无法判断该场景归谁，唯一诚实的结果是拒绝判定；算出空范围再返回 0，等于把「无法判定」伪装成「验收通过」。
   - 位置选在 verify 而非只在 spec 级 validate：见决策 3(c)，spec 级 validate 不在 Gate① 的执行路径上，只加那一处等于没补。
   - 前提自检排在跑命令之前：exit 2 的语义是「判不了」，判不了就不该先烧一遍命令再报错。`task_requirements()` 因此也提前，checklist 缺失不再等到命令跑完才暴露。
   - 配套放宽 `VALIDATION_RE` 容忍全角冒号（`验证：auto`）：中文输入法下是高频误击。**容忍只是减少误击，不是兜底**——真正的兜底是上面那条「解析不出就拦」，否则换任何分隔符都会有新的打错方式重新打开这个洞。
   - 弃：把分隔符从冒号改成等号——`＝` 同样有全角形态，症状原样搬家；且 `key: value` 是 checklist 头部、dev-report verify 块通用的写法，单给验证标记换符号多一套规矩。同一个半角冒号在这三处的区别本来就不是符号，而是前两处打错会报错、这一处打错会静默。
   - 弃：把漏标记的场景默认当 auto 处理——猜测意图，且会把「spec 没写清楚」变成「dev 没给证据」，报错指向错误的人。
   - 弃：把无父级 Scenario 并入所有 task 的范围——会让每个 task 都为同一个孤儿场景背锅，正是本变更要消除的互相拖累。
   - 弃：静默忽略并在输出里提示——Gate① 是拦截点不是告警面板，退出码 0 会被 x-verify 直接当作放行信号。

7. **范围判定的两处口径与既有解析对齐**
   - `expected_auto` 按名称去重：同一 task 承接多个 Requirement 且其下有同名 Scenario 时，不产生重复条目污染 `expected_auto` 与 `uncovered`。
   - `Requirement` 列的空占位判定收敛为与 `parse_deps` 同一集合（`—` / `-` / `n/a` / 空）。
   - 防：现状只排除全角 `—`，写成 ASCII `-` 时范围变成 `["-"]`，`expected_auto` 算空静默返回 0，而人类可读输出显示 `requirements: -`，比全 `—` 显示的「(无验收绑定)」更像正常绑定——恰好废掉决策 4 想要的可区分性。

8. **对账主键用 `(requirement, scenario)`，不是 Scenario 名**
   - auto 块必须同时写 `requirement:` 与 `scenario:`；同一 Requirement 内 Scenario 重名 → exit 2。
   - 依据：Scenario 名只在其父 Requirement 内唯一（spec 侧只约束了 Requirement 名唯一）。仅按名字对账时，跨 Requirement 的同名场景一份证据点亮两条，去重消除的是输出重复项，不是歧义本身。
   - 代价：改 dev-report schema + 四个 skill。这是上游指派的范围，不是可选项。

9. **`--only` 产出 partial 结果，且不计算 `uncovered`**
   - 现状：只执行选中块，覆盖判定却把未执行块的 `scenario:` 声明算作已覆盖 → 抽查一个块能返回正式 exit 0。
   - 决策：`partial: true` + `selected` 随结果输出，partial 时不给 `uncovered`；x-verify 禁止用 partial 放行。
   - 防：同一份产物全量跑 exit 1、`--only` 跑 exit 0，而 Gate① 只看退出码。

10. **`manual` 输出以 spec.md 为准，与 dev-report 对账**
    - 现状：`manual` 列表只来自 dev-report 的 manual 块，spec.md 里标 manual 的场景完全不被感知——x-dev 漏写 steps 块时没有任何机制发现。
    - 决策：以范围内的 manual Scenario 为基准，缺对应块的列为未认领。
    - 防：manual 场景既不进 `expected_auto` 也不进 `manual`，是一条验收要求凭空蒸发，与 Goals「全 spec 的 Scenario 仍须有人认领」直接冲突。

11. **无归属或无场景一律拦截**
    - 无父 `### Requirement:` 的 Scenario 不分 auto/manual 都 exit 2：决策 6 当初只拦 auto，理由是「manual 不参与 auto 对账」——该理由只在场景有归属时成立，孤儿 manual 是彻底无人认领。
    - scope 内的 Requirement 在 spec.md 下没有任何 Scenario → exit 2：需求被 task 承接却没有验收场景，范围算空后静默通过。

12. **已知限制：空壳证据块不由引擎判定**
    - `cmd: true` 这类命令能通过一切事实检查（exit 0、无 expect_contains），引擎无法区分"真验了"和"敷衍了"。
    - 不在引擎侧加启发式（如禁止 `true`/要求 `expect_contains` 非空）——黑名单绕得过，白名单会误伤合法用法。该判断属 x-qa-gate R3「每个自动验收 Scenario 是否被实际执行」的职责。

13. **spec 结构合法性由 V3 单点负责，verify 前置调用而非重写**
    - `spec.md` 是 x-spec2 的产出，它写得全不全属 spec 包门禁（V3），不属 Gate①。verify 的职责边界是「本 task 的证据是否对得上范围内的场景」。
    - verify 需要的是**前提已被校验**，不是自己再查一遍：在 `xdev.py` 调用 `verify.py` 前置跑 spec 包校验，有 issue 即 exit 2 退回 x-spec。放在 CLI 层可直接复用 `xdev.py` 的 V3；`verify.py` 保持执行与对账 owner。
    - 防：同一条规则两处实现，改一处忘另一处，两边判定漂移后没有任何机制发现。
    - 教训：动手加检查前先查这条检查是否已存在。决策 6 整段论证、四条「弃」和五个测试用例，都建立在「没有现成检查」这个没核实的前提上。

## Risks / Trade-offs

- [Risk] dev-report 的块回指了本 task 范围外的 Scenario 时不再报错，只是不计入覆盖 → 该 task 自己的 Scenario 仍会因缺证据进入 `uncovered`，Gate① 照样拦；代价是报错指向结果（缺覆盖）而非病因（写错回指）。留给后续的 `mismatch` 能力。
- [Risk] 引入 `requirement:` 会破坏已写好的 dev-report。当前 `docs/spec/` 下没有真实 req2 task，破坏面为零——这是做该变更最便宜的时机，推迟只会变贵。
- [Trade-off] 决策 8-11 让 verify 的拦截面显著变宽，spec 写得不规整时会频繁 exit 2。这是有意的：Gate① 的作用是拦，不是尽量放行；每一条拦截都对应一条此前会静默通过的误绿路径。
- [Trade-off] verify 从「只读 spec.md + dev-report」变成「还要读 dev-checklist.md」，耦合面扩大一个文件；换来的是范围判定不需要任何新增产物。

## Migration Plan

1. 修改 `verify.py` 的解析与对账，按需复用 `req.py` 的 checklist/spec 解析能力，跑 `python3 -m unittest discover -s test`。
2. 既有测试中把「单 task 必须覆盖整个 spec」写成断言的用例改写为多 task 独立验收，并补范围内缺口仍 exit 1 的反例。
3. 补决策 6/7 的封堵与反例用例：无父 Requirement 的 auto Scenario → exit 2、非 Requirement 的 H3 截断作用域 → exit 2、同一 task 内同名 Scenario 的 `expected_auto` 不重复、`Requirement` 列写 `-` 与写 `—` 等价。
4. 同步 x-verify 的 exit 2 分诊话术与 `xdev.py` 的 verify 子命令 help 文案。

现有 spec 包若已存在无父 Requirement 的 Scenario，升级后其所属 task 的 verify 会从「静默 exit 0」变为 exit 2——这是暴露既有验收黑洞，不是回归；修法是把该 Scenario 挪到某个 `### Requirement:` 下。

回滚时恢复扁平 Scenario 对账即可；本变更不迁移持久化数据、不改文件格式。

## Open Questions

无。
