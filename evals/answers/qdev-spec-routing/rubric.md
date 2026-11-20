# qdev-spec-routing 评分说明（仅评审侧）

每题 5 个字段，各 1 分；`writes` 按集合比较。`*` 表示任意不在索引表里的新名字（task_spec 的 `*` 须与 writes 里新建的名字相同）。

各题考点：
- Q01：修 bug 且 spec 已写明正确行为 → 只记变更记录、不停。
- Q11：修 bug 但 spec 没写这条行为 → append 补场景、要确认。
- Q02/Q08：append + 要确认 + 文件少，在 task ②简写。
- Q03：新建 spec → 必须调 x-tech-design；task 放在新 spec 下。
- Q04/Q05/Q10：不写场景 → 不停；Q10 改 3 个文件不超过 3，仍是 task。
- Q06：场景跨两份 spec → x-tech-design；task 放在主场景（读者申请减免）所在的 fine。
- Q07：鉴权 + 迁移 → 转主线。
- Q09：只写 loan，但源码文件 4 个（超过 3）→ x-tech-design。
- Q12：5 个文件里配置算源码、测试和文档不算 → 源码 2 个 → task②；等级只被读取，member 不列。
- Q13：没有直接操作者，fine、member 各一条场景 → task 放边界表靠前的 member；跨两份 spec → x-tech-design；每晚的检查不是一次性批量改写，风险规则第 3 条答否。
- Q14：退款到外部账户收不回 → 风险规则第 5 条，转主线。
- Q15：只改罚款计算规则 → 风险规则第 5 条答否，留在 qdev。
- Q16：spec 写错了 → 修改场景，要确认（区别于 Q01 的修 bug）。
