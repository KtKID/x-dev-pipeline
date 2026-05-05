# 05-r3-fail: 故意写"测试镜像化"代码

需求：写 `calculateTotal(items)` 函数 + 单元测试。

人工注入：让 dev 在测试里用 reduce 复制业务公式做断言，而不是写死期望值。

预期：x-verify / R1 / R2 全 pass，R3 拦下"反模式 A 测试镜像化"，fix-counter +1。
