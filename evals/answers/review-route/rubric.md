# review-route 评分说明（仅评审侧）

每题 1 分，`answer` 完全一致才得分。

- R01–R04：risk 决定 lens。Q0 不派；Q1 = q1+q3+q4；Q2 四个；Q3 四个且逐 lens 回执。
- R05：违反架构偏好 → q4-design P1。
- R06：断言证明不了 THEN → q3-evidence P1。
- R07：确定会给用户错误结果且已复现 → q2-correctness P0。
- R08：机械项由 xdev check 做，reviewer 不重复。
- R09：方案和偏好冲突 → 单独问用户，不悄悄违反也不悄悄改偏好。
- R10：没有偏好文件 → 不从代码推测填写。
- R11：用户说了新偏好 → 写进文件并注明来源。
- R12：修复不发回原 reviewer，用反例测试、xdev coverage 和 xdev check 关闭。
