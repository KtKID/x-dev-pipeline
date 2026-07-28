# Correctness Review 报告

> Report ID: 20260727-221443
> Mode: known-issue
> Scope: RAG corpus field migration
> Task ID: rag-content-field-migration
> Review 日期：2026-07-27
> 审查范围：默认 corpus、现有五条 fixture、新字段 writer 与 validator

## 调查对象

| 字段 | 内容 |
|------|------|
| 模式 | 已知问题 |
| 用户现象 | 需要确认已有 RAG 内容是否已按新字段处理 |
| 期望行为 | 已有风险条目包含关键词、Risk、场景、错误实现、正确实现、可观察差异和分类 |
| 实际行为 | 新 writer 与 validator 已支持丰富字段；默认 corpus 为空；现有五条 fixture 仍只有关键词和 Risk |
| 原始 spec 来源 | 用户当前消息；当前工作树 `x-bug2rag` 条目格式 |

## 审查范围

| 文件 | 角色 | 当前状态 |
|------|------|----------|
| `skills/x-adversarial-risk/references/risk-catalog.md` | 默认运行时 corpus | 只有说明头，0 条记录 |
| `skills/x-dev-rag-call/evals/fixtures/risk-catalog.md` | 现有五条测试语料 | 每条只有关键词和 Risk |
| `skills/x-bug2rag/SKILL.md` | 新条目格式 | 定义六个内容字段及分类、来源 |
| `skills/x-bug2rag/scripts/triage_store.py` | 新条目 writer | 新写入会生成完整字段 |
| `skills/x-adversarial-risk/scripts/risk_contract.py` | corpus validator | 关键词、Risk 必填；丰富字段可选 |

## 贝叶斯根因调查

| H | 先验 | 证据 E | 影响 | 更新后置信度 | 下一步 |
|---|------|--------|------|--------------|--------|
| H1：已有五条内容已迁移到新字段 | 高 | 五条 fixture 的场景、错误实现、正确实现、可观察差异、分类、来源计数均为 0 | 削弱 | 已确认不成立 | 迁移或重建内容 |
| H2：validator 会阻止旧两字段内容继续使用 | 中 | `REQUIRED_CATALOG_FIELDS` 仍为关键词与 Risk；fixture 验证 `valid: true` | 削弱 | 已确认不成立 | 增加迁移门禁或 schema 版本 |
| H3：默认 corpus 已承载迁移结果 | 中 | 文件只有说明头；验证返回 `CATALOG_EMPTY` | 削弱 | 已确认不成立 | 写入经过筛选的正式风险经验 |
| H4：后续新增内容会按新字段写入 | 高 | `x-bug2rag` 要求完整字段，`triage_store.py` 负责格式化和验证 | 支持 | 高 | 补 writer 测试并提交当前工作树 |

## Spec 对照

| 项 | 新字段契约 | 当前内容 | 分类 | 证据 |
|----|------------|----------|------|------|
| 默认 corpus | 包含可召回的正式经验 | 0 条记录 | 实现过程未完成 | `risk-catalog.md` |
| 现有五条 | 每条含完整对错反例字段 | 只有关键词、Risk | 实现过程未完成 | eval fixture |
| 新增条目 | writer 自动生成完整字段 | 当前工作树已实现 | 符合新契约 | `x-bug2rag` |
| 向后兼容 | 旧两字段记录仍可通过 | validator 保持两字段必填 | 符合当前兼容策略 | `risk_contract.py:40-50` |

## 审查结论

### P0：已确认正确性错误

无。

### P1：生产正确性风险

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ✅已修复 | 默认运行时 corpus | corpus 可用性 | `skills/x-adversarial-risk/references/risk-catalog.md` | 已确认 | 实现过程未完成 | 默认 corpus 为空，无法执行正式经验召回 |

### P2：正确性证据缺口

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ✅已修复 | 内容迁移 | 新字段覆盖 | `skills/x-dev-rag-call/evals/fixtures/risk-catalog.md` | 已确认 | 实现过程未完成 | 现有五条没有丰富字段 |
| ✅已修复 | schema 门禁 | 新旧格式区分 | `risk_contract.py:40-50` | 高 | spec 缺口 | validator 接受旧两字段和新丰富字段，无法证明迁移完成 |

## 问题详情

### B1：已有五条仍使用旧两字段格式

**来源**：字段计数与文件读取
**文件**：`skills/x-dev-rag-call/evals/fixtures/risk-catalog.md`
**位置**：第 5-27 行
**严重程度**：P2
**根因分类**：实现过程未完成
**置信度**：已确认

五条记录都包含 `关键词` 和 `Risk`，缺少 `场景`、`错误实现`、`正确实现`、`可观察差异`、`分类`、`来源`。validator 以向后兼容方式接受这些记录，因此 `valid: true` 只证明旧契约成立。

**处置结果**：✅已修复
**处置说明**：保留 `AR-001`～`AR-005`，逐条补齐场景、错误实现、正确实现、可观察差异、分类和来源，并同步 eval fixture。

### B2：默认 corpus 尚未装入正式内容

**来源**：文件读取与 validator
**文件**：`skills/x-adversarial-risk/references/risk-catalog.md`
**位置**：第 1-6 行
**严重程度**：P1
**根因分类**：实现过程未完成
**置信度**：已确认

文件声明了新字段顺序，正文没有任何 `## AR-NNN` 条目。`validate-corpus` 返回 `CATALOG_EMPTY`。

**处置结果**：✅已修复
**处置说明**：把迁移后的五条正式经验写入默认运行时 corpus；随后通过 x-bug2rag 显式写入已确认的 `AR-006`，当前默认 corpus 共六条。

### B3：validator 无法证明丰富字段迁移完成

**来源**：schema 门禁
**文件**：`skills/x-adversarial-risk/scripts/risk_contract.py`
**严重程度**：P2
**根因分类**：spec 缺口
**置信度**：高

**问题描述**：
兼容校验只要求关键词和 Risk，迁移验收需要独立的完整字段门禁。

**处置结果**：✅已修复
**处置说明**：新增 `--require-rich-fields`，要求场景、错误实现、正确实现、可观察差异和分类非空；正式 RAG 验证启用该门禁，x-bug2rag 使用自身等价的 rich-card contract 完成写入和聚合校验。

## 汇总

| 等级 | 数量 |
|------|------|
| P0 | 0 |
| P1 | 1 |
| P2 | 2 |

## 最终结论

- 新字段的 writer 和 parser 已进入当前工作树。
- 现有五条 fixture 已迁移为丰富字段。
- 默认运行时 corpus 已装入五条迁移经验和一条后续确认经验，共六条。
- validator 保持兼容模式，并提供 `--require-rich-fields` 作为正式语料门禁。

---
## 修复备注
> 修复执行时间：2026-07-27 22:33

| # | 严重程度 | 文件 | 处置结果 | 修复方式 | 备注 |
|---|----------|------|----------|----------|------|
| B1 | P2 | `skills/x-dev-rag-call/evals/fixtures/risk-catalog.md` | ✅已修复 | 迁移五条旧卡 | ID 保持 AR-001 至 AR-005 |
| B2 | P1 | `skills/x-adversarial-risk/references/risk-catalog.md` | ✅已修复 | 写入五条迁移经验并追加 AR-006 | plugin skills 目录包含六条丰富字段经验 |
| B3 | P2 | `skills/x-adversarial-risk/scripts/risk_contract.py` | ✅已修复 | 增加完整字段门禁 | 来源继续保持可选 |

### 汇总
| 处置类型 | 数量 |
|----------|------|
| ✅ 已修复 | 3 |
| ➖ 无需修复（误报） | 0 |
| ⏭ 已跳过（P3） | 0 |
