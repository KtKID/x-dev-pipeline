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
