---
name: x-dev-rag-call
description: |
  从需求、Spec、代码调查、故障描述或计划中提炼关键内容，调用本地 Embedding 模型，从调用方明确指定的 Markdown 或纯文本文件/目录进行语义 TopN 召回，并把命中的原文交回当前 LLM。用户提到“从这个路径召回”“查 RAG”“匹配错题集”“根据 Spec 找相关经验”“取 TopN”时使用；其他 skill 需要从指定本地知识路径获取相关内容时也使用。
---

# x-dev-rag-call

把“LLM 理解任务”和“Python 确定性检索”连接成一条最小 RAG 召回链路。

## 输入

调用需要三项信息：

1. `source`：调用方明确指定的 `.md`、`.txt` 文件或包含这些文件的目录。
2. `key_content`：需求、Spec、问题或计划中的关键内容。
3. `top_n`：需要返回的数量，默认 `1`。

路径在当前上下文中唯一明确时直接使用。路径存在多个候选或尚未给出时，请调用方明确指定。保持路径边界，避免自行扩展到其他知识目录。

## 职责

LLM 负责：

- 阅读任务输入。
- 提炼语义完整的检索内容。
- 调用检索脚本。
- 使用脚本返回的原文完成当前分析。

Python 脚本负责：

- 读取指定路径中的纯文本。
- 按 Markdown 二级及更深标题或纯文本段落切分内容。
- 实时计算查询向量和文本向量。
- 计算相似度并返回 TopN。

纯文本是知识事实源。每次调用实时计算向量；第一版保持零索引文件、零向量数据库和零 LLM 精排。

## 执行流程

### 1. 提炼关键内容

从输入中提炼一段适合语义检索的 `key_content`。保留：

- 功能或领域名词。
- 模块、对象和关键动作。
- 状态、时序和约束。
- 已知或担心的失败机制。

优先写成一至三句语义完整的短文本。仅有关键词时，用逗号连接。Spec 风险召回可使用：

```text
功能关键词：<模块、状态、动作>
Risk：<具体失败机制>
```

### 2. 调用本地召回脚本

运行：

```bash
uv run --offline --isolated \
  --python /opt/homebrew/Caskroom/miniforge/base/bin/python3 \
  --with "sentence-transformers>=2.7.0" \
  --with "transformers>=4.51.0,<5" \
  python skills/x-dev-rag-call/scripts/rag_retrieve.py \
  --source "<指定文件或目录>" \
  --query "<key_content>" \
  --top-n <N> \
  --json
```

脚本默认从本地模型缓存加载 `Qwen/Qwen3-Embedding-0.6B`，并通过 `local_files_only=True` 禁止联网下载。调用方明确指定另一个本地模型时增加：

```bash
--model "<本地模型路径>"
```

命令复用当前仓库已有的 uv 离线缓存环境。脚本使用本地文件加载模型；查询向量使用 Qwen 的 `query` 提示模板，文档向量使用普通文档编码，两侧向量均归一化。

### 3. 使用召回结果

成功输出：

```json
{
  "matches": [
    {
      "id": "AR-001",
      "source": "/absolute/path/risk-mistakes.md",
      "text": "## AR-001\n..."
    }
  ]
}
```

直接使用 `matches[].text` 完成当前任务。脚本已经返回原文，因此无需按 ID 再次读取文件。TopN 大于 1 时，同时处理本次返回的全部结果。

当前任务需要适用性判断时，由 LLM 说明每条命中如何影响分析。当前任务只验证召回链路时，成功返回一条完整原文即可。

### 4. 处理失败

脚本失败时读取：

```json
{
  "error": "ERROR_CODE",
  "message": "具体原因"
}
```

路径、语料或参数问题先修正输入。本地模型或依赖问题原样报告，保留实际退出码。召回失败时停止依赖召回结果的后续判断。

## 返回

向调用方返回：

- `source`。
- 实际 `key_content`。
- `top_n`。
- CLI 退出码和召回数量。
- 每条命中的 `id`、`source` 和完整 `text`。
- 召回内容在当前任务中的用途。

保持脚本原始命中顺序。输出省略相似度分数，因为 TopN 顺序已经表达本轮排序结果。
