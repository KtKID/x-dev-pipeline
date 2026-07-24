# Baseline transcript：幂等重试 Risk 召回

## 基线有效性

状态：**污染，禁止进入有效对比结论。**

原因：准备运行环境时，一次范围过宽且排除规则未生效的 `rg` 命令，意外输出了 `x-dev-rag-call/SKILL.md` 的两行元数据和 `x-dev-rag-call/scripts/rag_retrieve.py` 的三行路径、模型及依赖信息。后续查询没有调用该脚本；召回执行使用 `x-adversarial-risk/scripts/risk_retrieve.py`。

## 输入读取

读取 Spec：

```text
# 幂等重试 Spec

创建订单接口接收 `request_id`。请求在持久化业务结果之前可能失败，客户端会携带同一个 `request_id` 重试。系统需要保证一次有效业务副作用，并允许失败后的合法重试继续执行。
```

读取指定语料：

```text
skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references/risk-mistakes.md
```

## 查询提炼

```text
关键词：幂等请求、request_id、失败重试、唯一业务副作用、去重标识
Risk：请求在持久化业务结果前失败时，如果系统提前占用 request_id，同一 request_id 的合法重试可能被拒绝；如果未正确复用历史结果，也可能产生重复业务副作用。
TopN：1
```

查询保留了 Spec 的对象、失败时机和不变量：

- 对象：`request_id`
- 失败时机：业务结果持久化之前
- 不变量：允许合法重试，同时只产生一次业务副作用

## 执行过程

第一次使用系统 Python 执行，返回：

```json
{"error": "MODEL_ERROR", "message": "sentence-transformers 未安装；请先准备依赖和本地模型"}
```

第二次切换到仓库已有的离线 `uv` 依赖环境。沙箱内访问用户级 uv 缓存失败：

```text
error: failed to open file `/Users/kid/.cache/uv/sdists-v9/.git`: Operation not permitted (os error 1)
```

获得授权后离线读取现有 uv 缓存，执行命令：

```bash
uv run --offline --isolated \
  --python /opt/homebrew/Caskroom/miniforge/base/bin/python3 \
  --with 'sentence-transformers>=2.7.0' \
  --with 'transformers>=4.51.0,<5' \
  python skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/scripts/risk_retrieve.py query \
  --catalog skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references/risk-mistakes.md \
  --keywords '幂等请求、request_id、失败重试、唯一业务副作用、去重标识' \
  --risk '请求在持久化业务结果前失败时，如果系统提前占用 request_id，同一 request_id 的合法重试可能被拒绝；如果未正确复用历史结果，也可能产生重复业务副作用。' \
  --top-n 1 \
  --json
```

退出码：`0`

原始输出：

```json
{"matches": [{"id": "A-risk-004", "text": "关键词：幂等请求、失败重试、请求历史、去重标识\nRisk：失败请求提前占用幂等标识时，同一标识的后续合法请求可能被错误拒绝或丢失应产生的唯一副作用。"}]}
```

## 命中使用

Top1 命中 `A-risk-004`。它直接覆盖 Spec 的核心风险：失败请求对幂等标识的占用时机决定后续合法重试能否继续，也决定唯一业务副作用是否丢失。
