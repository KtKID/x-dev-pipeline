# eval-recovery-risk 执行轨迹

## 读取输入

- 输入文件：`skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-dev-rag-call/evals/fixtures/recovery-spec.md`
- 指定 source：`skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references`
- top_n：`1`

输入原文：

```markdown
# 日志恢复 Spec

服务启动时读取追加日志并恢复状态。日志记录具备合法编码和校验和。恢复过程还需要验证序列连续性以及状态转换是否合法，防止格式完整的末条记录产生不可能状态。
```

## 提炼的 key_content

```text
功能关键词：追加日志、启动恢复、末条记录、序列连续性、状态转换
Risk：编码和校验和合法的日志记录仍可能违反序列连续性或状态转换规则，恢复过程可能接受语义非法状态。
```

## 完整 CLI 命令

```bash
uv run --offline --isolated --python /opt/homebrew/Caskroom/miniforge/base/bin/python3 --with 'sentence-transformers>=2.7.0' --with 'transformers>=4.51.0,<5' python skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-dev-rag-call/scripts/rag_retrieve.py --source skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references --query '功能关键词：追加日志、启动恢复、末条记录、序列连续性、状态转换
Risk：编码和校验和合法的日志记录仍可能违反序列连续性或状态转换规则，恢复过程可能接受语义非法状态。' --top-n 1 --json
```

## 执行结果

- CLI 退出码：`0`
- 召回数量：`1`

原始 JSON：

```json
{"matches": [{"id": "A-risk-003", "source": "/Volumes/machub_app/proj/x-dev-pipeline/skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references/risk-mistakes.md", "text": "## A-risk-003\n\n关键词：日志恢复、末条记录、校验和、状态迁移、序列完整性\nRisk：编码、字段和校验和都完整的日志末条记录仍可能违反序列或状态转换规则，恢复过程可能把语义非法记录当成有效状态。"}]}
```
