# req2 引擎测试夹具

`test/test_req_engine.py` 直接读取本目录下的固定文件跑校验，不在运行时生成临时数据。

## ⚠️ 这里有大量「故意写错」的文件，不要修

`bad-*` / `uncovered` / `broken-pkg` / `verify-gap` 各目录里的错误是**测试用例的一部分**：
表头缺列、Requirement 悬空、risk 非法、依赖指向不存在的编号、spec 包缺文件、图与模块对不上……
都是有意为之，用来验证引擎**该报错时确实报错**。把它们「修好」会让对应测试失效。

每个坏夹具的文件头部都写明了它故意错在哪、预期报什么。改动前先看那段说明和下表。

## 夹具清单

| 目录 | 故意错在哪 | 预期结果 |
|---|---|---|
| `docs/spec/demo/` | 无（**正样例**，含匹配的 `diagram.md`） | validate 零 issue；spec 级覆盖闭合；REQ9 通过 |
| `docs/spec/bad-rows/` | 六种行级错各一行：悬空、重名、说明空、风险空、依赖悬空、状态非法 | 一次 validate 报齐 6 条（REQ4×2 / REQ5×2 / REQ7 / REQ8） |
| `docs/spec/bad-header/` | 任务表缺 `#` 与 `状态` 两个关键列 | 只报 REQ3；**不得**误报行级 issue |
| `docs/spec/bad-risk/` | 头部 `risk: Q9` | 只报 REQ2 |
| `docs/spec/pointer-mismatch/` | 头部 `spec:` 写 `docs/spec/demo`，实际在 `pointer-mismatch/` | REQ1（指针与实际归属不符） |
| `docs/spec/uncovered/` | 「无人认领的功能Z」没有任何 task 承接 | spec 级覆盖报 REQ6；单 task validate **零 issue** |
| `docs/spec/broken-pkg/` | 故意缺 `spec.md`，且清单里写了悬空需求 | 只报 1 条 REQ1（归属失效），**不级联**逐行 REQ5 |
| `docs/spec/bad-diagram/` | `diagram.md` 节点与 `modules.md` 模块名双向对不上 | REQ9 两条（缺节点 + 未声明） |
| `docs/spec/verify-gap/` | `dev-report.md` 的 verify 块指向别的场景名 | `verify` 退出码 1，「功能V生效」进 `uncovered` |

## 什么用夹具、什么用临时目录

- **校验「已有文件」的行为** → 用本目录的固化夹具（可见、可审、可复现）
- **验证「生成新文件」的行为**（`scaffold`、端到端全链路）→ 仍在测试里用临时目录，因为它要造的正是「原本不存在」的产物，固化下来反而自相矛盾

## 两个已知且预期的现象

1. **夹具的 spec 包是最小化的**：只写了 `## 验收`（外加 `modules.md` 的模块总览），够 req.py 用。
   若对夹具 spec 包跑**全量** validate（含 xdev.py 的 spec2 规则 V13-V18），会报「缺建模覆盖声明 / 缺用户要求追溯」等结构 issue——**这是预期的**，夹具不为那套规则服务。
   测试只调 `req.spec_requirement_coverage()` 等针对性接口，不跑全量。
2. **夹具位置刻意不在插件根的 `docs/spec/` 下**：引擎按 task 实际位置推定归属（往上两级），早期实现曾用插件仓库根去拼 `spec:` 指针，那样在插件仓库之外的真实项目里必然解析失败。夹具放在 `test/fixtures/req2/docs/spec/...`，**位置本身**就是这条契约的回归证据——谁改回「按根拼路径」，这些用例立刻红。
