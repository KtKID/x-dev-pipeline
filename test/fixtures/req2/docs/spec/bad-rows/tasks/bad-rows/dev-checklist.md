# bad-rows · 开发清单

> spec: docs/spec/bad-rows
> risk: Q1

⚠️ 故意写错的夹具，勿修。六种行级错各占一行，验证它们互不遮蔽、一次 validate 全报。

## 任务清单

| # | 任务说明 | Requirement | 风险 | 涉及文件 | 依赖 | 状态 | fix |
|---|---------|-------------|------|---------|------|------|-----|
| T1 | 回指一个不存在的需求 | 并不存在的需求 | 低 | src/a.py | None | [ ] ⏳ | None |
| T2 | 回指重名需求 | 重名需求 | 低 | src/b.py | None | [ ] ⏳ | None |
| T3 |  | 功能A | 低 | src/c.py | None | [ ] ⏳ | None |
| T4 | 风险列故意留空 | 功能A |  | src/d.py | None | [ ] ⏳ | None |
| T5 | 依赖指向不存在的编号 | 功能A | 低 | src/e.py | T99 | [ ] ⏳ | None |
| T6 | 状态列写非法值 | 功能A | 低 | src/f.py | None | 差不多了 | None |
