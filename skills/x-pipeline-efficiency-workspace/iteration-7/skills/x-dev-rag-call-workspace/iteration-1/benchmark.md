# Skill Benchmark: x-dev-rag-call

**Model**: GPT-5 Codex
**Date**: 2026-07-24T14:12:47Z
**Evals**: 1, 2 (1 run each per configuration)

## Summary

| Metric | With Skill | Without Skill | Delta |
|--------|------------|---------------|-------|
| Pass Rate | 100% ± 0% | 75% ± 0% | +0.25 |
| Time | 0.0s ± 0.0s | 0.0s ± 0.0s | +0.0s |
| Tokens | 0 ± 0 | 0 ± 0 | +0 |

## Notes

- 两条 with-skill 用例都真实调用 `x-dev-rag-call/scripts/rag_retrieve.py`，并分别命中 `A-risk-004` 与 `A-risk-003`。
- without-skill 执行使用已有 `x-adversarial-risk` 检索器，说明仓库已有领域专用能力；它缺少指定任意文件或目录的通用调用契约。
- baseline 搜索意外暴露目标 skill 的少量元数据，因此 75% 与 25 个百分点差值只用于展示，禁止作为有效 A/B 因果结论。
- 执行通知未提供可持久化的 token 与 duration 数据，本轮保留为 0，禁止解读为真实成本。
