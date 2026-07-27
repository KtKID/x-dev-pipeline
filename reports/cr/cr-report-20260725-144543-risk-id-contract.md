# Correctness Review 报告

> Report ID: 20260725-144543
> Mode: module-review
> Scope: module
> Task ID: risk-id-contract
> Review 日期：2026-07-25
> 审查范围：Spec3 风险 ID、RAG 语料、校验器、提示文档、测试与考试目录副本

## 调查对象

| 字段 | 内容 |
|------|------|
| 模式 | 模块正确性 review |
| 用户现象 | `<namespace>-risk-NNN` 规则增加提示长度和 LLM 推理负担；怀疑 `AR-001` 仍残留 |
| 期望行为 | 风险条目保留稳定唯一 ID；检索结果、ARV 记录和 Scenario 来源使用同一套简单规则 |
| 实际行为 | 当前运行面同时存在 `AR-NNN` 与 `A-risk-NNN`；考试目录语料能召回，随后被 v3 校验器拒绝 |
| 原始 spec 来源 | 用户当前消息；当前 `tools/spec.py`、iteration-7 技能包及考试目录副本 |

## 审查范围

| 文件 | 角色 |
|------|------|
| `tools/spec.py` | Spec3 最终结构与交叉引用校验 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/scripts/risk_contract.py` | v3 风险语料与来源契约 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-dev-rag-call/scripts/rag_retrieve.py` | 通用 RAG 切片与召回 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/SKILL.md` | 最新对抗审查提示 |
| `skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-dev-rag-call/SKILL.md` | 最新 RAG 调用提示 |
| `skills/x-adversarial-risk/SKILL.md` | 根目录现存旧版提示 |
| `skills/x-adversarial-risk/references/risk-mistakes.md` | 根目录现存风险语料 |
| `/Volumes/machub_app/proj/x-dev-world/minimax/journal-index-recovery/skills/x-adversarial-risk/` | 考试目录实际副本 |

## 贝叶斯根因调查

| H | 先验 | 证据 E | 更新后置信度 | 结论 |
|---|------|--------|--------------|------|
| H1：命名空间结构参与向量检索或排序 | 中 | `rag_retrieve.py:125-148` 直接把清理后的 Markdown 标题写入 `TextChunk.id`；编码与排序只消费正文 | 低 | 该结构对检索结果没有功能贡献 |
| H2：稳定 ID 对跨文档追踪有必要 | 高 | `tools/spec.py:703-745,885-905` 用 ID 关联 RAG 来源、召回记录和 Scenario | 已确认 | 保留单一、唯一、稳定 ID |
| H3：`AR-001` 只存在于历史材料 | 中 | 根目录当前 skill、当前语料、旧测试和考试目录实际语料仍使用 `AR-001` | 低 | 当前运行面仍有活跃残留 |
| H4：双规则已经造成实际失败 | 高 | 考试目录 `validate-corpus` 返回 exit 1；`spec.md:109` 记录召回成功后按 `skipped:no-corpus` 处理 | 已确认 | 已形成核心链路正确性错误 |
| H5：主要成本是字面 token 数 | 中 | 命名空间规则散布于校验器、两个 skill、Spec 校验和测试；实测影响表现为协议拒绝和回退 | 中低 | 字面 token 成本有限；分叉、纠错和回退成本更高 |

## 规则用途判断

| 规则 | 价值 | 建议 |
|------|------|------|
| ID 唯一 | 支撑召回结果、ARV 记录、Scenario 来源交叉引用 | 保留 |
| ID 稳定 | 支撑文档更新和审计 | 保留 |
| `AR-NNN` 三位序号 | 简单、现有真实语料已采用 | 作为唯一当前格式 |
| `<namespace>-risk-NNN` | 当前只有一个风险语料库；检索层按不透明标题处理 | 删除 |
| 首条必须为 `A-risk-001` | 与唯一性、稳定性和排序均无直接关系 | 删除 |
| v2 / v3 / legacy 多分支来源语法 | 增加生成和校验分支 | 收敛为 `rag:AR-NNN` 与 `assumption:<slug>` |

## 审查结论

### P0：已确认正确性错误

| 状态 | 检查项 | 文件:位置 | 置信度 | 描述 |
|------|--------|-----------|--------|------|
| ✅已修复 | 语料与 v3 ID 契约一致性 | 考试目录 `risk-mistakes.md:5`、`risk_contract.py:29-37,319-325` | 已确认 | 语料、校验器和来源统一使用 `AR-NNN`；真实 RAG 与 validate-review 均通过 |

### P1：生产正确性风险

| 状态 | 检查项 | 文件:位置 | 置信度 | 描述 |
|------|--------|-----------|--------|------|
| ✅已修复 | 当前仓库双 ID 规则 | 根目录与 iteration-7 `risk_contract.py`、Skill、模板和测试 | 已确认 | 两份校验器逐字一致，当前规则统一为 v3 + `AR-NNN` |
| ✅已修复 | Spec3 强绑定 namespaced ID | `tools/spec.py:85-92,703-745,885-905` | 已确认 | Spec3 统一解析 `RAG:AR-NNN` 与 `adversarial-review (rag:AR-NNN)` |

### P2：复杂度与提示成本

| 状态 | 检查项 | 文件:位置 | 置信度 | 描述 |
|------|--------|-----------|--------|------|
| ✅已修复 | 重复协议规则 | iteration-7 两个 skill、`risk_contract.py`、`tools/spec.py` 与测试 | 已确认 | 删除 namespace、v1/v2、首条固定 ID 和多来源兼容分支，只保留 v3 当前契约 |

## `AR-001` 活跃残留

| 范围 | 位置 | 状态 |
|------|------|------|
| 根目录旧版 skill | `skills/x-adversarial-risk/SKILL.md:107` | 当前文件 |
| 根目录风险语料 | `skills/x-adversarial-risk/references/risk-mistakes.md:5-53` | 当前文件，含 `AR-001..005` |
| 根目录旧测试 | `test/test_adversarial_risk.py:41,59,148,167-168` | 当前测试 |
| iteration-7 最新测试 | `skills/x-pipeline-efficiency-workspace/iteration-7/tests/test_adversarial_risk.py:201` | 反例测试，用于确认 `AR-001` 会被拒绝 |
| 当前 OpenSpec change | `openspec/changes/adversarial-risk-vector-retrieval-mvp/design.md` 等 | 设计与兼容性记录 |
| 考试目录风险语料 | `journal-index-recovery/skills/x-adversarial-risk/references/risk-mistakes.md:5-53` | 实际运行文件，含 `AR-001..005` |
| 考试目录生成 Spec | `journal-index-recovery/docs/spec/journal-index-recovery/spec.md:109` | 失败事实记录 |

历史 iteration、eval 输出和归档材料还包含两种 ID；它们属于运行证据，保留原样有利于审计。

## 修复建议

1. 统一当前规则为 `AR-\d{3}`，来源统一为 `rag:AR-NNN`。
2. 保留 ID 唯一性、召回记录存在性和 Scenario 交叉引用校验。
3. 删除 `NAMESPACED_RISK_ID_PATTERN`、首条 `A-risk-001` 固定规则、v2 namespaced 兼容分支及相关提示。
4. 同步修改 `tools/spec.py`、iteration-7 skill、validator、fixtures/tests 和考试目录副本。
5. 把根目录语料压缩为最新两字段格式；当前语料除 ID 外还因标题带说明、字段过多和证据路径标记被 v3 拒绝。

## 实测证据

```text
python3 .../risk_contract.py validate-corpus .../references/risk-mistakes.md
exit=1
[CATALOG_ID] 错题 ID 必须匹配 <namespace>-risk-<三位序号>：AR-001...
[CATALOG_FIRST_ID] 首条错题 ID 必须为 A-risk-001
```

考试目录生成 Spec 已记录：Qwen RAG Top5 技术召回成功，命中 `AR-001..AR-005`；v3 契约拒绝后写成 `skipped:no-corpus`。

## 最终结论

- 当前契约统一为 `AR-NNN`，承担唯一定位和追踪。
- `AR-001` 是当前合法 ID；`A-risk-NNN` 只保留在拒绝旧格式的反例测试。
- 考试目录真实 RAG、Spec3 校验与 validate-review 已通过。
- 实现修复与验证记录见下方修复备注。

---
## 修复备注

> 修复执行时间：2026-07-25 15:06

| # | 严重程度 | 文件 | 处置结果 | 修复方式 | 备注 |
|---|----------|------|----------|----------|------|
| B1 | P0 | `risk_contract.py`、`risk-mistakes.md`、考试目录副本 | ✅已修复 | 统一 v3 + `AR-NNN`，压缩语料为关键词与 Risk | 真实 Top5 exit=0 |
| B2 | P1 | `tools/spec.py`、Skill、模板、测试、OpenSpec | ✅已修复 | 删除 namespace、v1/v2 和首条固定 ID 规则 | 活跃规则残留扫描通过 |
| B3 | P2 | Skill 分发文档与 `x-spec3.skill` | ✅已修复 | 示例显式使用 `AR-NNN`，重建压缩包 | 4 个 Skill quick validation 通过 |
| B4 | P1 | `x-spec3/templates/spec.md`、`risk_contract.py` | ✅已修复 | 审查记录标题统一为精确二级标题 | forward-test 复验通过 |
| B5 | P2 | `x-req3/SKILL.md` | ✅已修复 | 删除 spec2 与无版本存量路径说明 | 当前只保留 v3 |
| B6 | P2 | `tools/spec.py` | ✅已修复 | Top5 成功路径接受 1..5 个唯一 ID，要求 matches 与实际数量一致 | 新增 4 条语料回归测试 |

### 汇总

| 处置类型 | 数量 |
|----------|------|
| ✅ 已修复 | 6 |
| ➖ 无需修复（误报） | 0 |
| ⏭ 已跳过（P3） | 0 |
