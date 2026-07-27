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
→ 检查调用方是否提供风险语料路径
→ 有路径：本地 Embedding 向量召回 Top5
→ 缺路径：暂停并询问；用户确认无经验集后跳过 RAG
→ standard：记录命中与适用性，零 Scenario 扩张
→ deep：使用召回正文或 1 个独立假设做对抗分析
→ full：使用召回正文加独立假设，或执行最多 2 个独立假设
→ 契约验证
→ 回执
```

风险语料由调用方以本地纯文本文件或目录提供，每条记录使用稳定 ID、关键词和 Risk。共享 skill 只保存召回与审查流程。缺少路径时 agent 停下工作并向用户询问；用户确认没有 RAG 经验集后跳过召回，评分继续决定 standard、deep、full 的分析深度。RAG 产生的 Scenario 使用 `adversarial-review (rag:<risk-id>)`，独立假设使用 `adversarial-review (assumption:<短说明>)`。

## Embedding 运行条件

- Python 包：`sentence-transformers>=2.7.0`、`transformers>=4.51.0`
- 默认模型：`Qwen/Qwen3-Embedding-0.6B`
- 默认目录：`iteration-7/models/Qwen3-Embedding-0.6B/`
- 模型加载：`local_files_only=True`
- 可选模型：查询命令增加 `--model <本地路径或本地模型名>`

查询使用 Qwen3 官方 `query` 提示模板，风险语料正文按普通文档编码；两侧向量都归一化。离线单元测试使用假 Embedding 后端，运行时代码只读取本地模型。

真实模型 Smoke 使用调用方准备的风险语料。下方命令是跨功能调用示例，验收目标由该语料的预期命中 ID 决定。

当前仓库使用已有 uv 离线环境加载依赖，无需向 base Python 安装包。

查询命令：

```bash
uv run --offline --isolated \
  --python /opt/homebrew/Caskroom/miniforge/base/bin/python3 \
  --with "sentence-transformers>=2.7.0" \
  --with "transformers>=4.51.0,<5" \
  python skills/x-dev-rag-call/scripts/rag_retrieve.py \
  --source /absolute/path/to/risk-corpus.md \
  --query "功能关键词：目标模块、关键状态、核心动作
Risk：关键不变量在失败窗口中被破坏" \
  --top-n 1 \
  --model "/Volumes/machub_app/proj/x-dev-pipeline/skills/x-pipeline-efficiency-workspace/iteration-7/models/Qwen3-Embedding-0.6B" \
  --json
```

成功输出只有：

```json
{"matches":[{"id":"<risk-id>","source":"/absolute/path/to/risk-corpus.md","text":"## <risk-id>\n..."}]}
```

真实 eval 的运行时验收读取 session JSONL，并核对：

- agent 只读取 skill 与目标 Spec。
- 错题正文由召回 CLI 返回。
- 对抗阶段依次完成读取、召回、集中 patch、聚合 `validate-review` 和回执。
- 回执记录查询、召回 ID、复用或新增 Scenario 和 CLI 结果。
