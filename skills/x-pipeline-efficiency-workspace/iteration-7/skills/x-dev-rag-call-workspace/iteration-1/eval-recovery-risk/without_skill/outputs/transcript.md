# Baseline transcript：日志恢复 Risk 召回

## 基线有效性

状态：**污染，禁止进入有效对比结论。**

原因：准备运行环境时，一次范围过宽且排除规则未生效的 `rg` 命令，意外输出了 `x-dev-rag-call/SKILL.md` 的两行元数据和 `x-dev-rag-call/scripts/rag_retrieve.py` 的三行路径、模型及依赖信息。后续查询没有调用该脚本；召回执行使用 `x-adversarial-risk/scripts/risk_retrieve.py`。

## 输入读取

读取 Spec：

```text
# 日志恢复 Spec

服务启动时读取追加日志并恢复状态。日志记录具备合法编码和校验和。恢复过程还需要验证序列连续性以及状态转换是否合法，防止格式完整的末条记录产生不可能状态。
```

指定路径是目录：

```text
skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references
```

目录扫描只发现一个可召回文本：

```text
skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references/risk-mistakes.md
```

## 查询提炼

```text
关键词：追加日志、启动恢复、校验和、序列连续性、状态转换、末条记录
Risk：日志记录编码和校验和完整时，末条记录仍可能破坏序列连续性或违反合法状态转换，导致恢复出不可能状态。
TopN：1
```

查询保留了 Spec 的恢复对象、已满足条件和待验证语义：

- 对象：追加日志的末条记录
- 已满足条件：合法编码和校验和
- 待验证语义：序列连续性与状态转换合法性

## 执行过程

使用仓库已有离线依赖环境和本地模型执行：

```bash
uv run --offline --isolated \
  --python /opt/homebrew/Caskroom/miniforge/base/bin/python3 \
  --with 'sentence-transformers>=2.7.0' \
  --with 'transformers>=4.51.0,<5' \
  python skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/scripts/risk_retrieve.py query \
  --catalog skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references/risk-mistakes.md \
  --keywords '追加日志、启动恢复、校验和、序列连续性、状态转换、末条记录' \
  --risk '日志记录编码和校验和完整时，末条记录仍可能破坏序列连续性或违反合法状态转换，导致恢复出不可能状态。' \
  --top-n 1 \
  --json
```

退出码：`0`

原始输出：

```json
{"matches": [{"id": "A-risk-003", "text": "关键词：日志恢复、末条记录、校验和、状态迁移、序列完整性\nRisk：编码、字段和校验和都完整的日志末条记录仍可能违反序列或状态转换规则，恢复过程可能把语义非法记录当成有效状态。"}]}
```

## 命中使用

Top1 命中 `A-risk-003`。它直接覆盖 Spec 的核心风险：完整编码与校验和只能证明记录形式完整，恢复逻辑还需要按前序状态验证序列和状态迁移。
