# Correctness Review 报告

> Report ID: 20260727-161830
> Mode: known-issue
> Scope: Codex plugin runtime path
> Task ID: rag-plugin-path-portability
> Review 日期：2026-07-27
> 审查范围：`x-dev-rag-call` 与 `x-adversarial-risk` 的路径解析和外部项目可执行性

## 调查对象

| 字段 | 内容 |
|------|------|
| 模式 | 已知问题 |
| 用户现象 | RAG 已进入 Codex plugin，外部环境仍无法正常使用 |
| 期望行为 | 插件从任意项目目录调用自身脚本，并允许调用方提供 corpus |
| 实际行为 | corpus 使用运行时参数；Python 解释器使用固定绝对路径；插件脚本使用相对当前工作目录的仓库路径 |
| 原始 spec 来源 | 用户当前问题；`skills/x-dev-rag-call/SKILL.md` 输入与执行契约 |

## 修改文件 / 审查范围

| 文件 | 角色 | 说明 |
|------|------|------|
| `skills/x-dev-rag-call/SKILL.md` | runtime instruction | 召回命令与 corpus 输入 |
| `skills/x-adversarial-risk/SKILL.md` | runtime caller | Top5 召回命令 |
| `skills/x-dev-rag-call/scripts/rag_retrieve.py` | implementation | CLI 参数和路径读取 |
| Codex plugin cache `local-plugins/x-dev-pipeline/0.5.0` | installed runtime | 插件脚本真实安装位置 |

---

## 贝叶斯根因调查

| H | 先验 | 证据 E | 影响 | 更新后置信度 | 下一步 |
|---|------|--------|------|--------------|--------|
| H1：corpus 写死为开发机绝对路径 | 高 | CLI 将 `--source` 声明为必填参数，运行时通过 `Path(args.source)` 读取 | 削弱 | 低 | 已排除 |
| H2：Python 解释器写死为开发机绝对路径 | 高 | 两个 skill 都使用 `/opt/homebrew/Caskroom/miniforge/base/bin/python3` | 支持 | 已确认 | 改为可发现的解释器或插件运行环境 |
| H3：脚本路径正确解析到插件安装目录 | 中 | 命令使用 `python skills/x-dev-rag-call/scripts/rag_retrieve.py`，没有插件根目录解析 | 削弱 | 已确认不成立 | 使用插件资源解析机制或自包含入口 |
| H4：相对脚本路径只影响少数目录结构 | 中 | 外部临时项目复现 `script_exists=1`，插件缓存中的真实脚本 `script_exists=0` | 削弱 | 已确认不成立 | 增加外部项目安装验收 |
| H5：默认模型在外部可自动取得 | 中 | `local_files_only=True`，默认模型为 `Qwen/Qwen3-Embedding-0.6B` | 削弱 | 高 | 明确模型预装、发现和错误提示契约 |

### 已排除假设

| H | 排除证据 |
|---|----------|
| corpus 路径固定到 `/Volumes/...` | `--source` 由调用方传入；脚本支持文件和目录 |
| RAG 脚本未进入 Codex plugin | v0.5.0 缓存存在 `skills/x-dev-rag-call/scripts/rag_retrieve.py` |

---

## Spec 对照

| 项 | 原始 spec / 契约 | 当前实现 / 行为 | 分类 | 证据 |
|----|------------------|----------------|------|------|
| corpus 输入 | 调用方明确提供文件或目录 | `--source` 必填并交给 `Path(args.source)` | 符合 spec | `SKILL.md:15-19`；`rag_retrieve.py:281,313` |
| 插件脚本定位 | 插件在任意目标项目中可调用自身资源 | 脚本路径相对目标项目 cwd | 实现过程偏移 | `SKILL.md:66` |
| Python 运行时 | 外部 Codex 环境可执行召回命令 | 固定 Homebrew Miniforge 路径 | 环境兼容缺口 | `SKILL.md:63` |
| 模型可用性 | 本地离线召回 | 仅从本机模型缓存加载 | 符合离线方向，缺少分发契约 | `rag_retrieve.py:30-31,79-82` |

---

## 审查结论

### P0：已确认正确性错误

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ✅已修复 | 外部项目复现 | 插件脚本定位 | `skills/x-dev-rag-call/SKILL.md:66` | 已确认 | 实现过程偏移 | 命令从目标项目 cwd 查找插件脚本，普通外部项目缺少该路径 |

### P1：生产正确性风险

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ✅已修复 | 命令契约 | Python 解释器 | `skills/x-dev-rag-call/SKILL.md:63` | 已确认 | 环境数据问题 | 固定路径只覆盖当前开发机安装布局 |
| ✅已修复 | 模型加载 | 离线模型可用性 | `rag_retrieve.py:79` | 高 | spec 缺口 | 外部环境缺少预缓存模型时返回 `MODEL_ERROR` |

### P2：正确性证据缺口

| 状态 | 来源 | 检查项 | 文件:位置 | 置信度 | 根因分类 | 描述 |
|------|------|--------|-----------|--------|----------|------|
| ✅已修复 | 验收覆盖 | 外部项目插件 E2E | `test/test_rag_skill_portability.py` | 已确认 | 测试缺口 | 当前验证都在插件仓库根目录运行，未覆盖普通项目 cwd |

---

## 问题详情

### B1：插件脚本路径绑定插件仓库 cwd

**来源**：命令路径 + 外部目录复现
**文件**：`skills/x-dev-rag-call/SKILL.md`
**位置**：第 66 行
**严重程度**：P0
**根因分类**：实现过程偏移
**置信度**：已确认

**问题描述**：
skill 调用 `python skills/x-dev-rag-call/scripts/rag_retrieve.py`。该相对路径以当前目标项目为基准。插件仓库根目录存在这个路径，普通外部项目中缺失。Codex 缓存里的真实脚本位于插件安装目录，当前命令没有解析该目录。

**验证方式**：

```text
插件仓库 cwd：script_exists=0
外部临时项目 cwd：script_exists=1
Codex v0.5.0 插件缓存：script_exists=0
```

数值为 shell 退出码，`0` 表示存在，`1` 表示缺失。

**影响**：
外部项目执行 RAG 时，Python 在加载召回脚本前即失败。

**修复建议**：
为插件脚本建立与 cwd 无关的资源入口，并从 Codex 提供的插件根目录或安装资源解析机制定位脚本。

**处置结果**：✅已修复
**处置说明**：命令先从当前已加载的 `x-dev-rag-call/SKILL.md` 取得 skill 根目录，再调用 `${RAG_SKILL_DIR}/scripts/rag_retrieve.py`。

### B2：Python 解释器绑定当前开发机

**来源**：skill 命令
**文件**：`skills/x-dev-rag-call/SKILL.md`
**位置**：第 63 行
**严重程度**：P1
**根因分类**：环境数据问题
**置信度**：已确认

**问题描述**：
命令固定使用 `/opt/homebrew/Caskroom/miniforge/base/bin/python3`。该路径对应 Apple Silicon Homebrew + Miniforge 的特定安装布局。

**影响**：
Linux、Windows、Intel macOS、系统 Python、pyenv、uv-managed Python 和其他 Miniforge 路径都会在命令启动阶段失败。

**修复建议**：
使用可发现的 Python 运行时，并在启动前验证版本与依赖；把自定义解释器保留为可选配置。

**处置结果**：✅已修复
**处置说明**：移除固定 Miniforge 路径，`uv run` 使用当前环境可发现的 Python。

### B3：本地模型缓存形成第三个环境前置条件

**来源**：模型加载代码
**文件**：`skills/x-dev-rag-call/scripts/rag_retrieve.py`
**位置**：第 30-31、79-82 行
**严重程度**：P1
**根因分类**：spec 缺口
**置信度**：高

**问题描述**：
默认模型固定为 `Qwen/Qwen3-Embedding-0.6B`，加载设置为 `local_files_only=True`。外部环境需要提前准备同名本地缓存或显式传入另一个本地模型。

**影响**：
脚本路径和 Python 路径修复后，缺少模型缓存的环境仍会得到 `MODEL_ERROR`。

**修复建议**：
把模型准备方式、缓存发现、可选模型路径和安装验收写入插件分发契约。

**处置结果**：✅已修复
**处置说明**：召回命令显式传入 `Qwen/Qwen3-Embedding-0.6B`；skill 说明模型权重由运行环境缓存提供，脚本的 `MODEL_ERROR` 给出缓存模型或传入本地模型目录的处置方式。

### B4：外部 cwd 缺少验收覆盖

**来源**：验收覆盖
**文件**：`test/test_rag_skill_portability.py`
**严重程度**：P2
**根因分类**：测试缺口
**置信度**：已确认

**问题描述**：
原测试从仓库根目录执行，无法证明插件脚本和默认 corpus 在普通项目 cwd 下可定位。

**处置结果**：✅已修复
**处置说明**：新增外部临时目录验收，覆盖召回脚本入口、风险契约、默认 corpus、x-bug2rag 显式目标与自包含校验、目录级单批编码。

---

## 汇总

| 等级 | 数量 |
|------|------|
| P0 | 1 |
| P1 | 2 |
| P2 | 1 |

## 最终结论

- 默认 corpus 以 `x-adversarial-risk` skill 目录为根解析，调用方可显式覆盖。
- `x-bug2rag` 要求调用方显式给出目标 corpus，并只调用自身目录内的写入、聚合与校验代码。
- Python 由当前运行环境发现。
- 插件脚本以各自 `SKILL.md` 所在目录为根解析。
- 默认模型为 `Qwen/Qwen3-Embedding-0.6B`，运行环境缓存提供权重。

---
## 修复备注
> 修复执行时间：2026-07-27 22:33

| # | 严重程度 | 文件 | 处置结果 | 修复方式 | 备注 |
|---|----------|------|----------|----------|------|
| B1 | P0 | `skills/x-dev-rag-call/SKILL.md` | ✅已修复 | skill 根目录定位脚本 | 外部 cwd 已覆盖 |
| B2 | P1 | `skills/x-dev-rag-call/SKILL.md` | ✅已修复 | 使用环境可发现 Python | 固定解释器已移除 |
| B3 | P1 | `skills/x-dev-rag-call/scripts/rag_retrieve.py` | ✅已修复 | 明确模型缓存契约与错误处置 | 模型 ID 保持 Qwen 0.6B |
| B4 | P2 | `test/test_rag_skill_portability.py` | ✅已修复 | 增加外部 cwd 自动化验收 | 覆盖批量单次编码和 x-bug2rag 自包含契约 |

### 汇总
| 处置类型 | 数量 |
|----------|------|
| ✅ 已修复 | 4 |
| ➖ 无需修复（误报） | 0 |
| ⏭ 已跳过（P3） | 0 |
