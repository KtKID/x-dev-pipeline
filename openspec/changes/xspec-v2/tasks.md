# xspec-v2 Tasks

## 1. 规则层（tools/xdev.py）

- [x] 1.1 v2 包检测：modules.md 存在 OR spec.md 含 `> spec_version: 2` 标记；检测顺序先于 capability 分支
- [x] 1.2 场景契约公共校验函数 + profile 分派（v2/task = GIVEN 可选、WHEN/THEN 必须、验证标记必须；capability/change = 原契约；V12 改为调用公共函数）
- [x] 1.3 v2 结构规则：必需文件（spec.md + modules.md）、spec_version 标记、包内无 task 清单
- [x] 1.4 建模覆盖声明规则：六元组（数据流/状态/时序/资源/不变量/故障）逐项非空（`文件#段落锚点` 或不适用理由），填写落点时校验目标文件与段落存在
- [x] 1.5 用户要求追溯规则：追溯表存在，每行对应 Requirement 名与落实位置非空，Requirement 名在 spec.md 中存在且唯一
- [x] 1.6 模块状态规则：状态字段 ∈ 受控词汇，机器可解析
- [x] 1.7 Requirement↔模块双向追溯规则：modules.md → spec.md 合法/悬空/重名检查；spec.md → modules.md 全 Requirement 覆盖检查
- [x] 1.8 v2 死链规则：路径解析语义（./ 与 ../ 相对文件、无前缀相对仓库根、绝对与 file:// 报机器绑定、http/mailto/锚点跳过、支持空格与尖括号形态）
- [x] 1.9 design.md 按需规则：跨模块数据/状态/时序/资源/故障模型要求 design.md；覆盖声明引用 design.md 时文件和锚点必须存在；无触发项时允许省略

## 2. 模板层（skills/x-spec2/templates/）

- [x] 2.1 spec.md 模板：spec_version 标记、需求本质、范围边界、约束与不变量、用户要求→Requirement 追溯表、建模覆盖声明表、验收（R/S + 验证标记）；每段模板注释标注消费者
- [x] 2.2 modules.md 模板：模块字段（职责/边界类/依赖/接口与数据结构/风险/状态/回指 Requirement）；模板说明 Requirement 必须被至少一个模块承接；跨模块时序进入 design.md；每字段标注消费者
- [x] 2.3 design.md 模板（按需件）：核心时序、数据与状态流转、资源生命周期/容量、故障恢复、迁移方案；仅在动态模型触发时生成

## 3. Skill 层（skills/x-spec2/SKILL.md）

- [x] 3.1 流程主干：上下文收敛（沿用第一性推导与头脑风暴，砍仪式性表格）→ 写 spec.md → 用户确认 → 写 modules.md（+按需 design.md）→ validate 零 issue → 裁判 → 修复 → 输出
- [x] 3.2 裁判精简 rubric：用户要求→Requirement、Requirement↔模块双向对账、覆盖声明理由与 design.md 触发真实性；内置"不确定往低判"降级条款
- [x] 3.3 update 纪律：双向对账两方向操作定义、不顺手造新文件、"细化 vs 变意图"判定条件（需求本质/系统目标/不变量任一变化 = 变意图，新开包）
- [x] 3.4 与 x-req 的交接说明：v2 不产 task-map，模块状态"不稳禁入"语义，指向后续 change xreq-adopt-specv2

## 4. 测试（test/）

- [x] 4.1 v2 正样例包：合规 mini 包 validate 零 issue
- [x] 4.2 v2 反样例：缺件 / 覆盖声明缺项或落点悬空 / design.md 触发后缺失 / 缺验证标记 / 用户要求回指悬空 / 模块回指悬空 / Requirement 无模块承接 / 重名 / 死链逐一被抓
- [x] 4.3 存量回归：历史 v1 包 issue 集合不变、OpenSpec capability 包零 issue、现有全部测试通过
- [x] 4.4 检测歧义交叉样例：纯 capability 包不被误判 v2、缺 modules.md 的 v2 标记包报缺件

## 5. 收尾

- [x] 5.1 旧版零修改保护：本 change 不修改 `skills/x-spec/**`；新实现全部落在 `skills/x-spec2/`，验证前后旧版目录内容一致
- [x] 5.2 关闭 dev-pipeline/tasks/xspec-contract-upgrade：README updated 行注记转型至本 change，不再开发
- [x] 5.3 openspec archive 前自查：tasks 全勾、spec delta 与实现一致

## 6. 理由层增补前置门禁

- [x] 6.1 确认本增补继续落在未归档的 `xspec-v2` change，并记录相对当前 V2 草案的 BREAKING 范围：只影响 spec2，新旧 v1 与 OpenSpec profile 行为保持不变
- [x] 6.2 用现有 StackChan eval 包标注预期 `U/J/D` 映射，确定哪些内容属于直接用户要求、事实/推断和关键决策，作为实现与评审基准

## 7. 校验器与测试

- [x] 7.1 先增加失败测试：`J/D` 重名/缺字段、`U/J/D` 引用悬空、**孤儿 J**（存在但未被任何 D/Requirement 引用）、**D 依据未引用任何 U/J**、结构型 U 回指的模块不存在
- [x] 7.2 增加正向测试：无动态模型的包（含派生模块边界与 `D-ID`）允许两件包——D 住 modules.md，不触发 design.md；结构型 U 回指模块通过；一句混合原话拆成多条原子 U 各自回指通过
- [x] 7.3 在 `tools/xdev.py` 增加理由层结构规则：`J/D` 唯一性、必需字段、`U/J/D` 引用**双向**闭合（悬空与孤儿都报 issue）、每个 D 的依据至少引用一个 U/J；V15 开结构型 U 出口（"对应"列允许回指模块名）；design.md 保持**动态模型单触发**
- [x] 7.4 复跑 spec2 全部正反样例与 v1/OpenSpec profile 回归，确认新增 issue 只作用于 spec2

## 8. Skill 与模板

- [x] 8.1 更新 `templates/spec.md`：增加"判断依据"段，定义 `J-ID`、来源类型、证据/推断说明与确认状态；注明 **J 由 D/Requirement 的依据按需拉出，不预枚举**（拉式生产，孤儿 J 由 validate 拦截）；追溯表注明一句混合原话拆成多条原子 U
- [x] 8.2 更新 `templates/modules.md`：增加"关键决策"节（**D-ID 定义的唯一真源**）——每个 `D-ID` 写选择、`U/J` 依据、理由、备选与否决原因、重评条件；模块行"决策回指"用 `U-ID`（用户直接指定边界）或 `D-ID`（派生的拆分、依赖、边界类、数据归属）
- [x] 8.3 更新 `templates/design.md`：保持纯动态模型（不定义 D），动态段落可反向引用 `D-ID`
- [x] 8.4 更新 `SKILL.md`：补充拉式 J 生产规则、D 住 modules.md 与 design 单触发、`U/J/D` 单一真源、原子 U 拆条规则、语义审核和基于证据链的 update 纪律

## 9. Eval 与归档前验证

- [x] 9.1 更新 StackChan 生成 eval，明确评分模块拆分依据、备选方案、重评条件与 `U/J/D` 回指闭合
- [x] 9.2 新增 round-trip update eval：清空原对话后由新 agent 只读需求包与仓库，解释一个模块边界并完成“细化还是变意图”分类
- [x] 9.3 重新生成 with-skill 样例，运行 `python3 tools/xdev.py validate`、机械 grader 与人工语义审核，确认理由能从正式 2+1 包恢复
- [x] 9.4 严格运行 `openspec validate xspec-v2 --strict` 与仓库测试；全部新增 tasks 完成后再 archive
