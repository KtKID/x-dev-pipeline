# 测试用例索引（仅评审侧）

每条设计规则测哪些题、每道题考什么，都记在这里。本目录只给评分脚本和评审看，答题者不读 `evals/answers/`。

新增或修改一条设计规则时，在这里登记它对应的题。没有题的规则，就是还没有测过的规则。

## spec 归属（spec-scope）

- 规则：`skills/x-explore-for-spec/references/spec-scope.md`
- 题面：`evals/problems/spec-scope/`；答案：`evals/answers/spec-scope/expected.json`
- 测什么：一个需求是新建 spec、加到已有 spec，还是只记变更记录；要写几份 spec。

| 用例 | 考的规则 | 正确判断 | 常见错误 |
|---|---|---|---|
| S01 S02 S03 S10 | 改的数据有明确所有者 → 加到已有 spec | 各加到一份 | — |
| S04 S14 | 被调用方行为没变 → 只写调用方 | 只加到调用方 | 把 message 也列上 |
| S05 S12 | 表里没有所有者 → 新建 | 新建一份 | 塞进 catalog |
| S06 | 只展示的场景，看展示的是谁的数据 | 加到 loan | 按页面放进 member |
| S07 | 纯工程改动 → 只记变更 | engineering 只记变更 | 写场景或新建 spec |
| S08 | 只改文案 → 只记变更 | catalog 只记变更 | 写场景 |
| S09 | 看"可借上限"归谁，不看"等级"这个词 | 加到 loan | 放进 member |
| S11 | 只读取别的数据不算改它 | 只加到 member | 多列 loan |
| S13 | 一个需求改两块数据 → 两份都写 | fine + member 都加 | 只写一份 |
| S15 | 只新增消息类型，不涉及调用方 | 只加到 message | 新建 spec 或多列 loan |

## qdev 路由（qdev-spec-routing）

- 规则：`skills/x-qdev/SKILL.md` 第 1–3 节，加上 spec-scope
- 题面：`evals/problems/qdev-spec-routing/`；答案：`evals/answers/qdev-spec-routing/expected.json`
- 测什么：在 spec 归属之外，再判断四件事：留在 qdev 还是转主线、task 放哪份 spec、写完 spec 停不停下来给用户确认、技术设计写在 tech-design.md 还是 task ②。

| 用例 | 考的规则 | 正确判断 |
|---|---|---|
| Q01 | 修 bug，spec 已写明正确行为 → 只记变更、不停 | 只记变更，不确认 |
| Q11 | 修 bug，spec 没写这条行为 → 补场景、要停 | 加场景，确认 |
| Q02 Q08 | 加场景 → 要停；文件少 → task ② | 确认，task ② |
| Q03 | 新建 spec → 调 x-tech-design；task 放新 spec 下 | 新建，确认，x-tech-design |
| Q04 Q05 Q10 | 不写场景 → 不停；Q10 改 3 个文件不算超过 3 | 不确认，task ② |
| Q06 | 场景跨两份 spec → x-tech-design；task 放主场景所在的 spec | fine 下，x-tech-design |
| Q07 | 鉴权 + 迁移 → 转主线 | mainline |
| Q09 | 只写一份 spec，但源码文件超过 3 个 → x-tech-design | x-tech-design |

## 还没有题的规则

- spec-scope 的例外：一条场景改两块数据、被调用方接口变化、边界表重叠、spec 本身写错、外观和行为分不清、配置文件计数、没有直接操作者时的主场景。
- spec 变化后 tech-design、task、代码和测试的同步（spec → tech → dev 链路）。
- x-verify-spec 检查 task 是否记录了用户确认。
