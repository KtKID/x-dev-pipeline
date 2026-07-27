# Skill Benchmark: x-spec2

**Model**: GPT-5 Codex
**Date**: 2026-07-19T07:29:16Z
**Evals**: 1 (1 run each per configuration)

## Summary

| Metric | With Skill | Without Skill | Delta |
|--------|------------|---------------|-------|
| Pass Rate | 100% ± 0% | 100% ± 0% | +0.00 |
| Time | 0.0s ± 0.0s | 0.0s ± 0.0s | +0.0s |
| Output chars (token proxy) | 23679 ± 0 | 31934 ± 0 | -8255 |

## Findings

- 两组十条语义断言均为 100%；本 case 证明 `x-spec2` 在复杂动态链路上保持完整性。
- `with_skill` 在相同通过率下减少 8,255 个输出字符，约 25.8%。
- `with_skill` 使用 19 次工具调用，基线使用 13 次；额外调用来自 skill、模板读取和校验。
- 测试 case 向两组公开完整 rubric，本轮对产物质量和压缩效果有直接证据；跨题稳定性仍需更多 case。
- 本轮缺少可靠 wall-clock timing，时间指标保留为 0。
