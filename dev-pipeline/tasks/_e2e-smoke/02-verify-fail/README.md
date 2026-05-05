# 02-verify-fail: 故意写错 dev-report 预期 exit

需求：同 01-positive。

人工注入：完成 dev 阶段后，手工编辑 dev-report.md，把某条命令的"预期 exit"从 0 改成 99。

预期：x-verify 拦下，生成 status: fail 的 verify-report，fix-counter +1。
