# ok-task · 开发清单

> spec: docs/spec/demo
> risk: Q1

## 任务清单

| # | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---------|-------------|------|---------|------|------|-----|
| T1 | 实现功能A的核心行为 | 功能A | 低：不触及系统不变量 | src/demo.py | None | [ ] ⏳ | None |
| T2 | 补功能A的契约与边界测试 | 功能A | 低：仅新增测试 | test/test_demo.py | T1 | [ ] ⏳ | None |
