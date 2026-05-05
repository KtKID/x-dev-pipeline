# 04-r2-fail: 故意不处理边界

需求：写一个函数 `normalize(s)` 把字符串去空格转小写。

人工注入：让 dev 实现时不处理 null 输入（直接 `s.trim()` 会 NPE）。

预期：x-verify pass，R1 pass，R2 拦下"未处理 null 输入"，fix-counter +1。
