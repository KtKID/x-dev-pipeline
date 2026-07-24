# Iteration 7 pipeline skill snapshot

执行顺序：

1. `x-spec3`
2. `x-adversarial-risk`
3. `x-req3`
4. `x-dev`
5. `x-verify`
6. `x-qa-gate`
7. `x-fix`

共享召回 skill：

- `x-dev-rag-call`：接收调用方指定的本地纯文本路径和关键内容，实时计算向量并返回 TopN 原文。它作为通用检索入口独立于七个阶段，可由任一阶段显式调用。

iteration-7 以 iteration-6 的七个 skills 为冻结基线。本轮只优化对抗风险审查：

```text
读取 Spec
→ 生成“功能关键词 + Risk”
→ 本地 Embedding 向量召回 Top1
→ 使用返回的 id + text 做对抗分析
→ 集中修改
→ 契约验证
→ 回执
```

错题集保持为一个 Markdown 文件，每条记录只有稳定 ID、关键词和 Risk。`x-adversarial-risk` 调用 `x-dev-rag-call` 从指定错题集路径召回，agent 直接接收 TopN 正文。RAG 产生的 Scenario 使用 `adversarial-review (rag:<risk-id>)` 显式记录来源。

## Embedding 运行条件

- Python 包：`sentence-transformers>=2.7.0`、`transformers>=4.51.0`
- 默认模型：`Qwen/Qwen3-Embedding-0.6B`
- 默认目录：`iteration-7/models/Qwen3-Embedding-0.6B/`
- 模型加载：`local_files_only=True`
- 可选模型：查询命令增加 `--model <本地路径或本地模型名>`

查询使用 Qwen3 官方 `query` 提示模板，错题正文按普通文档编码；两侧向量都归一化。离线单元测试使用假 Embedding 后端，运行时代码只读取本地模型。

真实模型 Smoke 使用下方查询，验收 Top1 为 `A-risk-003`。

依赖准备命令：

```bash
python3 -m pip install "sentence-transformers>=2.7.0" "transformers>=4.51.0"
```

查询命令：

```bash
python3 skills/x-dev-rag-call/scripts/rag_retrieve.py \
  --source skills/x-adversarial-risk/references/risk-mistakes.md \
  --query "功能关键词：日志恢复、状态迁移、完整性校验
Risk：校验和正确的末条记录违反状态转换规则" \
  --top-n 1 \
  --json
```

成功输出只有：

```json
{"matches":[{"id":"A-risk-003","source":".../risk-mistakes.md","text":"## A-risk-003\n..."}]}
```

真实 eval 的运行时验收读取 session JSONL，并核对：

- agent 只读取 skill 与目标 Spec。
- 错题正文由召回 CLI 返回。
- 对抗阶段依次完成读取、召回、集中 patch、聚合 `validate-review` 和回执。
- 回执记录查询、召回 ID、复用或新增 Scenario 和 CLI 结果。
