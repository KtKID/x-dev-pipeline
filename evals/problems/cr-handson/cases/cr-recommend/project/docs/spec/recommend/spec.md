# recommend：推荐书单

> spec：recommend
> 主要入口：src/library/recommend.py
> 状态：在用

## feat01: 个人推荐

> 状态：已验收

场景1: 按自己的借阅历史推荐
- GIVEN 读者已登录，借过若干本书
- WHEN 读者打开推荐页
- THEN 推荐的书来自和他借过的书同类、他还没借过的书；不出现只有别的读者借过的书的痕迹（比如“因为你借过《X》”里的 X 必须是他自己借过的）
