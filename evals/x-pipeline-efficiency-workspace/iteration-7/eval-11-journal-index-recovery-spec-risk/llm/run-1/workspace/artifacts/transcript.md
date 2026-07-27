# Journal Index Recovery Spec + Risk 执行轨迹

## 运行范围

- Task：`evals/problems/journal-index-recovery/PROMPT.md`
- Fixture：`cases/journal-index-recovery/fixture/`
- Skills：`skills/x-pipeline-efficiency-workspace/iteration-7/skills/`
- 流程：`x-spec3 → x-adversarial-risk → x-dev-rag-call`
- 输出：本 run 的 `workspace/docs/spec/journal-index-recovery/` 与 `workspace/artifacts/`

## x-spec3

LLM 完整读取：

- `x-spec3/SKILL.md`
- `x-spec3/templates/spec.md`
- Journal Index Recovery 任务原文
- fixture README 与 `backend/*.py` 模块入口

从任务事实得出：

- complexity：`5`，依据为幂等、跨进程锁、崩溃恢复和多阶段持久化提交。
- importance：`1`，依据为本地单用户 CLI。
- risk_average：`3.0`。
- review_budget：`full`，由 complexity 单维 5 升级。
- adversarial_review：初稿为 `pending`。

LLM 生成 19 个 `initial-spec` Scenario，并冻结：

```text
workspace/artifacts/spec.initial.md
```

初稿验证：

```text
python3 tools/xdev.py validate <spec-dir> --json
exit=0; total_issues=0
```

风险契约初稿验证仅返回预期阻断：

```json
{
  "valid": false,
  "issues": [
    {
      "code": "SPEC_PENDING",
      "line": 7,
      "message": "对抗性风险审查仍为 pending，阻断 x-req3"
    }
  ]
}
```

## x-adversarial-risk

LLM 完整读取 `x-adversarial-risk/SKILL.md` 与初稿 Spec，重算结果仍为 `5 / 1 / 3.0 / full`。

提炼查询：

```text
功能关键词：journal、snapshot、compact、events.log、崩溃恢复、旧日志前缀、序列单调
Risk：snapshot 已发布但 journal 清空尚未稳定提交时发生崩溃，重启可能重复应用已被 snapshot 覆盖的 mutation 或丢失提交状态。
```

## x-dev-rag-call

真实调用：

```bash
uv run --offline --isolated \
  --python /opt/homebrew/Caskroom/miniforge/base/bin/python3 \
  --with 'sentence-transformers>=2.7.0' \
  --with 'transformers>=4.51.0,<5' \
  python skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-dev-rag-call/scripts/rag_retrieve.py \
  --source skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references/risk-mistakes.md \
  --query '功能关键词：journal、snapshot、compact、events.log、崩溃恢复、旧日志前缀、序列单调
Risk：snapshot 已发布但 journal 清空尚未稳定提交时发生崩溃，重启可能重复应用已被 snapshot 覆盖的 mutation 或丢失提交状态。' \
  --top-n 1 \
  --json
```

执行结果：

- exit：`0`
- matches：`1`

原始 JSON：

```json
{"matches": [{"id": "A-risk-003", "source": "/Volumes/machub_app/proj/x-dev-pipeline/skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/references/risk-mistakes.md", "text": "## A-risk-003\n\n关键词：日志恢复、末条记录、校验和、状态迁移、序列完整性\nRisk：编码、字段和校验和都完整的日志末条记录仍可能违反序列或状态转换规则，恢复过程可能把语义非法记录当成有效状态。"}]}
```

## 按需风险处理

`A-risk-003` 适用于当前任务。初稿 `SC_11` 已明确覆盖：

- 尾部 record 的 UTF-8、换行、JSON、字段和 CRC 均正确。
- seq、expected_version 或状态转换语义非法。
- get、put、compact、recover 全部返回 `CORRUPT_LOG`。
- 所有持久化文件与状态保持不变。

因此本轮复用 `SC_11`，保留其真实来源 `initial-spec`。Spec 的对抗性审查记录显式写入：

```text
RAG:A-risk-003
```

full 预算继续独立推导一个故障假设：空 journal 已 replace、第二次 state-dir fsync 尚未完成时崩溃。初稿只覆盖 snapshot 已发布、旧 journal 尚未清空的窗口，因此新增：

```text
SC_20
来源：adversarial-review (assumption:compact-log-replace-dir-fsync-window)
```

错题记录决策：本轮命中已有 `A-risk-003`；独立假设仍属于 Spec 设计检查，当前缺少已验证的新错题事实，因此本轮保持错题集不变。

## 最终验证

```text
python3 skills/.../risk_contract.py validate-review <spec.md> --catalog <risk-mistakes.md> --json
exit=0; valid=true; issues=[]
```

```text
python3 tools/xdev.py validate <spec-dir> --json
exit=0; total_issues=0
```

```text
python3 -B -m unittest discover -s skills/x-pipeline-efficiency-workspace/iteration-7/tests -v
exit=0; Ran 46 tests; OK
```

最终 Spec 已冻结为 `workspace/artifacts/spec.final.md`，状态为 `ready-for-x-req3`。
