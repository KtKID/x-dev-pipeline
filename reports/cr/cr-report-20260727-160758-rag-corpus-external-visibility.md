# Correctness Review 报告

> Report ID: 20260727-160758
> Mode: known-issue
> Scope: repository release and plugin runtime assets
> Task ID: rag-corpus-external-visibility
> Review 日期：2026-07-27
> 审查范围：RAG 错题集的公开分支、Release、插件缓存与运行时路径

## 调查对象

| 字段 | 内容 |
|------|------|
| 模式 | 已知问题 |
| 用户现象 | 外部安装或查看 x-dev-pipeline 时看不到当前 RAG 错题集 |
| 期望行为 | 公开安装入口提供当前 RAG 能力，并按明确产品契约提供可用的风险经验集 |
| 实际行为 | v0.5.0 仅位于 `evo`；公开默认分支 `main` 仍为 v0.3.6；v0.5.0 插件缓存包含检索 skill 和脚本，未包含错题集正文 |
| 原始 spec 来源 | 用户当前消息；`README_zh.md` 安装说明；当前 skill 输入契约 |

## 修改文件 / 审查范围

| 文件或对象 | 角色 | 说明 |
|------|------|------|
| `origin/main` | public default branch | GitHub 与默认 clone 的公开安装事实源 |
| `origin/evo` | development branch | 当前 v0.5.0 元数据和 RAG skill 所在分支 |
| `.codex-plugin/plugin.json` | release metadata | `evo` 声明 v0.5.0 |
| `skills/x-adversarial-risk/SKILL.md` | runtime contract | 要求调用方明确提供风险语料路径 |
| `skills/x-dev-rag-call/evals/fixtures/risk-catalog.md` | eval fixture | 仓库中现存的五条测试语料 |
| Codex plugin cache `local-plugins/x-dev-pipeline/0.5.0` | installed runtime package | 包含 RAG skill 和脚本，未包含 `evals/` fixture 或旧 `references/risk-mistakes.md` |
| GitHub Releases | public release channel | 当前 Latest Release 为 v0.1.2 |

---

## 贝叶斯根因调查

| H | 先验 | 证据 E | 影响 | 更新后置信度 | 下一步 |
|---|------|--------|------|--------------|--------|
| H1：v0.5.0 只推送到开发分支 | 高 | `origin/HEAD -> origin/main`；`origin/main...origin/evo = 0/64`；发布提交 `90a42d3` 位于 `origin/evo` | 支持 | 已确认 | 将经过验收的发布提交进入默认公开分支 |
| H2：正式 Release 已发布，外部缓存尚未刷新 | 中 | GitHub Latest Release 为 v0.1.2；本地 tag 仅有 v0.1.2、v0.1.3 | 削弱 | 低 | 创建与分支内容一致的版本 tag/Release |
| H3：v0.5.0 插件包携带当前错题集 | 中 | 缓存存在两个 RAG skill 及脚本；两个候选 corpus 路径均不存在 | 削弱 | 已确认不成立 | 明确 corpus 的分发所有权和运行时路径 |
| H4：错题集正文仍属于运行时 skill 资产 | 中 | `e2d345d` 删除 `skills/x-adversarial-risk/references/risk-mistakes.md`，新增 `skills/x-dev-rag-call/evals/fixtures/risk-catalog.md` | 削弱 | 已确认不成立 | 将 fixture 保持为测试资产；另行建立可发布的通用 corpus |
| H5：插件缓存停留在旧 skill | 低 | 缓存 skill 与 `evo` 当前 skill 逐字一致，版本为 0.5.0 | 削弱 | 低 | 无需把缓存刷新当作本次主因 |

### 已排除假设

| H | 排除证据 |
|---|----------|
| `evo` 发布提交尚未推送 | 当前 `evo` 与 `origin/evo` 同步，HEAD 为 `90a42d3` |
| Codex v0.5.0 缓存缺少 RAG 代码 | 缓存包含 `x-dev-rag-call`、`x-adversarial-risk` 及对应脚本，且与仓库当前内容一致 |

---

## Spec 对照

| 项 | 原始 spec / 契约 | 当前实现 / 行为 | 分类 | 证据 |
|----|------------------|----------------|------|------|
| 默认公开安装 | README 使用无分支参数的 `git clone` | GitHub 默认分支为 `main`，其插件元数据为 v0.3.6 | 实现过程偏移 | `README_zh.md:167`；`origin/main:.claude-plugin/plugin.json:4` |
| 公开版本 | 当前仓库元数据声明 v0.5.0 | GitHub Latest Release 为 v0.1.2，v0.5.0 无 tag | 实现过程偏移 | `.codex-plugin/plugin.json:3`；GitHub Releases |
| corpus 所有权 | 当前 skill 要求调用方提供语料路径 | 共享插件只分发流程、检索脚本和校验脚本 | 符合当前 skill 契约 | `skills/x-adversarial-risk/SKILL.md:17-23` |
| README 产品说明 | README 声明 deep/full 读取 skill 独占错题集 | 当前运行时没有 skill 独占错题集 | 文档与实现不一致 | `README_zh.md:64`；插件缓存文件清单 |

---

## 审查结论

### P0：已确认正确性错误

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ❌ | 公开安装链路 | 默认分支版本 | `origin/main:.claude-plugin/plugin.json:4` | 已确认 | 实现过程偏移 | 默认 clone 获取 v0.3.6，无法获得 v0.5.0 的 RAG skill |

### P1：生产正确性风险

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ✅已修复 | 插件运行时 | corpus 可用性 | `skills/x-adversarial-risk/SKILL.md:17` | 已确认 | spec 缺口 | v0.5.0 要求调用方提供 corpus；外部用户缺少随产品提供的默认通用 corpus |
| ⚠️ | 发布渠道 | 版本可发现性 | GitHub Releases | 已确认 | 实现过程偏移 | v0.5.0 缺少 tag/Release，外部版本发现仍指向 v0.1.2 |

### P2：正确性证据缺口

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ✅已修复 | 文档契约 | corpus 所有权 | `README_zh.md:64` | 已确认 | spec 缺口 | README 声明 skill 独占错题集，当前 skill 声明调用方提供风险语料 |

---

## 问题详情

### B1：公开默认安装仍停留在 v0.3.6

**来源**：Git 分支、GitHub 默认分支、安装说明
**文件**：`origin/main:.claude-plugin/plugin.json`
**位置**：第 4 行
**严重程度**：P0
**根因分类**：实现过程偏移
**置信度**：已确认

**问题描述**：
发布提交 `90a42d3` 已推送到 `origin/evo`。GitHub 默认分支仍为 `main`，无参数 clone 和 README 安装命令都获取 `main`。`main` 声明 v0.3.6，且不存在 `skills/x-dev-rag-call/SKILL.md`。

**影响**：
外部用户按照公开安装说明无法发现或安装当前 RAG skill。

**修复建议**：
把验收通过的 v0.5.0 发布提交合入公开默认分支，并从默认分支重新验证 Claude Code 与 Codex 两条安装链路。

### B2：v0.5.0 运行时包没有错题集正文

**来源**：提交 diff、skill 契约、插件缓存文件清单
**文件**：`skills/x-adversarial-risk/SKILL.md`
**位置**：第 17-23 行
**严重程度**：P1
**根因分类**：spec 缺口
**置信度**：已确认

**问题描述**：
`e2d345d` 删除旧运行时文件 `skills/x-adversarial-risk/references/risk-mistakes.md`，并将五条语料放入 `skills/x-dev-rag-call/evals/fixtures/risk-catalog.md`。Codex v0.5.0 缓存排除 `evals/`，因此运行时只具备“读取调用方指定 corpus”的能力。

**影响**：
安装 v0.5.0 的外部用户仍需自行提供经验集路径。产品没有可直接使用的默认错题集。

**修复建议**：
确定 corpus 产品边界：建立跨领域、可公开分发的通用 corpus，并作为运行时资产发布；benchmark fixture 继续留在 eval 范围。

**处置结果**：✅已修复
**处置说明**：建立 `skills/x-adversarial-risk/references/risk-catalog.md`，装入五条迁移经验并追加已确认的 `AR-006`，当前共六条丰富字段经验；plugin manifest 的 `skills: ./skills/` 会包含该运行时资产。已安装 v0.5.0 缓存仍需版本刷新。

### B3：v0.5.0 缺少正式版本入口

**来源**：本地 tag、GitHub Releases
**文件**：GitHub release metadata
**严重程度**：P1
**根因分类**：实现过程偏移
**置信度**：已确认

**问题描述**：
仓库元数据声明 v0.5.0，本地 tag 最高为 v0.1.3，GitHub Latest Release 为 v0.1.2。

**影响**：
依赖 tag、Release 或 Latest Release 的外部发现与安装链路无法识别 v0.5.0。

**修复建议**：
默认分支发布验证通过后创建 v0.5.0 tag 和 GitHub Release，确保 Release 指向同一提交。

### B4：README 延续旧 corpus 描述

**来源**：文档与 skill 对照
**文件**：`README_zh.md`
**位置**：第 64 行
**严重程度**：P2
**根因分类**：spec 缺口
**置信度**：已确认

**问题描述**：
README 声明 deep/full 读取 skill 独占错题集；当前 skill 要求调用方提供路径。两条契约会让用户把缺 corpus 误判为缓存或安装故障。

**修复建议**：
在选定 corpus 分发方案后同步 README、skill、manifest 描述和安装验收。

**处置结果**：✅已修复
**处置说明**：中英文 README 与 x-spec、x-adversarial-risk、x-bug2rag 已统一为“skill 内默认 corpus + 调用方显式覆盖路径”。

---

## 汇总

| 等级 | 数量 |
|------|------|
| P0 | 1 |
| P1 | 2 |
| P2 | 1 |

## 最终结论

- 当前 v0.5.0 只完成 `evo` 分支元数据发布。
- 公开默认安装链路仍提供 v0.3.6。
- 当前源码已提供 RAG 检索能力与六条丰富字段默认通用 corpus。
- 已安装的 Codex v0.5.0 缓存仍是旧副本。
- 后续发布顺序为“版本更新 → 默认分支 → tag/Release → 外部干净环境安装验收”。

---
## 修复备注
> 修复执行时间：2026-07-27 22:33

| # | 严重程度 | 文件 | 处置结果 | 修复方式 | 备注 |
|---|----------|------|----------|----------|------|
| B1 | P0 | `origin/main` | ⏭已跳过 | - | 本轮限定 corpus 与路径改造 |
| B2 | P1 | `skills/x-adversarial-risk/references/risk-catalog.md` | ✅已修复 | 发布目录内建立默认 corpus | 缓存刷新待版本发布 |
| B3 | P1 | GitHub release metadata | ⏭已跳过 | - | 发布动作需在当前改动提交后执行 |
| B4 | P2 | `README.md`、`README_zh.md` | ✅已修复 | 同步默认 corpus 契约 | 覆盖路径规则已写明 |

### 汇总
| 处置类型 | 数量 |
|----------|------|
| ✅ 已修复 | 2 |
| ➖ 无需修复（误报） | 0 |
| ⏭ 已跳过（发布动作） | 2 |
