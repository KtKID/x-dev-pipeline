# 03-r1-fail: 故意漏实现需求

需求：在仓库根创建 a.txt（内容 "A"）和 b.txt（内容 "B"）两个文件。

人工注入：让 dev 只创建 a.txt，不创建 b.txt。

预期：x-verify pass（命令清单跑通），R1 拦下"需求 b.txt 未实现"，fix-counter +1。
