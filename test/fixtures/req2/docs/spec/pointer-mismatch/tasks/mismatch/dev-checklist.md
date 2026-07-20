# mismatch · 开发清单

> spec: docs/spec/demo
> risk: Q1

⚠️ 故意写错的夹具，勿修。本 task 实际位于 `docs/spec/pointer-mismatch/tasks/`，
但头部 `spec:` 写的是 `docs/spec/demo`——归属由**实际位置**推定，指针只作核对，
因此预期报 REQ1「指针与实际归属不符」。其余内容合法。

## 任务清单

| # | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---------|-------------|------|---------|------|------|-----|
| T1 | 实现功能A | 功能A | 低：不触及不变量 | src/a.py | — | [ ] ⏳ | — |
