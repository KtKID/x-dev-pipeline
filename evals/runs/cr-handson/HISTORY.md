# cr-handson · 运行历史

测什么：真跑 x-cr / x-fix。每道题一个埋了问题和陷阱的小项目，`evals/scripts/handson_grade.py` 按 `evals/answers/cr-handson/<题目>/checks.json` 判分，修复阶段另跑隐藏测试，并把答题方写的反例测试放到修之前的代码上跑，确认它真能测出错。

每轮产物在 `iteration-N/`：`<题目>-rM.json` 是判分结果，`-report.md` 是答题方写的报告（x-fix 阶段是修完后的报告），`.diff` 是 x-fix 改的代码和测试。

| iteration | 结果 | 发生了什么 |
|---|---|---|
| 1 | 12/12 份全过（haiku）：cr-renew、cr-fine-diff、cr-reserve、cr-recommend 的 x-cr 各 ×2，cr-renew 接 x-fix ×2，fix-mixed ×2 | 首次运行，替换掉原来的 22 道判断题。cr-fine-diff 两次都额外报了一条题目没埋、但确实存在的问题：新日志读 `loan["id"]`，没有 id 的借阅会抛 KeyError（P2，没法验证），属于真发现，不算误报。cr-renew 接 x-fix 时题面只有 x-cr 的 request.md，答题方要靠调用方说明切换阶段，已补 request-fix.md |
