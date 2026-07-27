# ConfigResolver sol5.6 规格评测报告

## 判定

- `pipeline_run_id`：`prun-acb50794-d518-4fef-8e3a-8785795f1b94-001`
- Run 类型：`evaluation`
- Source Session：`019f89d3-3a38-7572-8835-4a7c22bb5f36`
- 生成器：Codex Desktop `0.144.2` / OpenAI `gpt-5.6-sol` / `xhigh`
- 执行阶段：`x-spec3.spec → x-req3.task → source_validation_handoff`
- 评测阶段：`spec_quality_review → report_persistence`
- 执行终态：completed
- 规格质量门禁：failed
- accepted delivery：false
- 下一阶段：`revise_spec`

这份规格达到 **语义 85/100、结构 8/8**。P0 为 0，17 个 Scenario 内部可联合满足。三层递归实例、空输入结果矩阵、返回值可变别名三项 P1 仍会削弱 dev 测试与 verify 兜底，当前版本应先修订，再进入 req/dev。

生成记录已经精确恢复。Codex rollout 创建的原始 spec 与被评文件均为 233 行，全文只有标题一处变化：`# 多来源配置解析器` 被改成 `# 多来源配置解析器 模型 sol5.6极高`。原始内容 SHA-256 为 `52e7d2cd18bf6200467df2fbf2cf5a63dfe1758554a39bdc167d9d8c2aa5b746`，被评文件 SHA-256 为 `b5574b99cc8ce35b3e544963181854d7556ad69faadf51e3d706d633f9866b40`。

## 评测有效性

产物质量评分有效；该评分只判断文档是否覆盖验收要求。模型与 skill 的盲测归因无效：生成者写 spec 前搜索了 Codex memory，并读取同题历史验收报告。该报告披露了 object nil 合并屏障、覆盖前逐来源校验、父对象缺失时嵌套 required 报错三个 hidden 失败点；生成者随后明确表示会将三点写成 Scenario。

| 项目 | 结论 |
|---|---|
| evaluator-only rubric / harness 直接读取 | false |
| 同题 hidden 失败记忆读取 | true |
| `tainted_state` | true |
| 产物质量评分 | 有效 |
| 模型/skill 因果对比 | 无效 |

## 评测依据

| 输入 | 结果 |
|---|---|
| 原始任务 SHA-256 | `0484ec1f9e5deb29ecfc38a6d572460bc56825a75a8d7c620c2067183af703be` |
| x-evals 题面 SHA-256 | 同上，字节级一致 |
| 评分 rubric SHA-256 | `c970f0440b7db906949325464d87063b12f2e1fb800e4084dc66830f3b662f3d` |
| hidden harness SHA-256 | `e77d0a68a24af9df67e2c2338b636bbf863288bebbe64cf988950d0e958e787c` |
| Codex rollout SHA-256 | `14c8353383b292aa30a2703b3f004e5fd97b8dbc5472bd97d6a068d1a55d4308` |
| 被评 spec SHA-256 | `b5574b99cc8ce35b3e544963181854d7556ad69faadf51e3d706d633f9866b40` |
| rubric 直接暴露状态 | false |

`EVALUATION.md`、17 条 harness 测试和本项目 28 条细化断言共同参与评审。harness 用于核对规格覆盖真实失败路径；本次目标是规格文档，未执行 Go hidden tests。

## 质量

| 维度 | 通过 | 得分 |
|---|---:|---:|
| 合并语义 | 6/7 | 30/35 |
| Schema 校验 | 4/4 | 20/20 |
| Provenance | 3/3 | 15/15 |
| 边界条件 | 1/3 | 5/15 |
| 性能与确定性 | 2/2 | 10/10 |
| 工具门禁 | 1/1 | 5/5 |
| 任务语义合计 | 17/20 | **85/100** |
| 规格结构 | 8/8 | **8/8** |
| 全部断言 | 25/28 | 89.29% |

### P0

`0`。删除、未知字段、类型错误、required、Provenance、确定性和竞态 Scenario 保持联合可满足。上一份 MiniMax 规格出现过的“删除 Scenario 同时触发未知字段”矛盾已消除。

### 产物 P1

1. `SPEC_MISSING_THREE_LEVEL_EXAMPLE`：递归合并只描述“同一对象的互补子字段”，缺少 `app.server.tls.enabled/cert` 这类至少三层的具体 GIVEN 与最终值。证据：[spec 快照](artifacts/configresolver-sol5.6-spec.md) 第 115–121 行。
2. `SPEC_EMPTY_INPUT_MATRIX_MISSING`：当前输入不变 Scenario 覆盖 `nil Source.Data`，缺少 nil/空 schema、nil/空 sources 的成功或错误结果。证据：第 195–201 行。
3. `SPEC_RESULT_ALIAS_OWNERSHIP_MISSING`：当前深比较发生在 `Resolve` 返回时；测试缺少修改 `Result.Config` 或嵌套数组后复查输入的所有权断言。证据：第 195–201 行。

### 评测有效性 P1

- `EVAL_HIDDEN_MEMORY_CONTAMINATION`：生成者读取同题 hidden 失败历史，污染了盲测上下文。语义评分保持 85/100；x-spec3 和模型能力的因果结论撤销。

### P2

- `SPEC_INFERENCE_STATUS_UNVERIFIED`：J3、J4、J5、J8 的来源写为“LLM 推断”，状态同时写为“已确认”。产物缺少确认主体，更准确的状态是“待验证假设”。
- `SPEC_EVIDENCE_SOURCE_UNRESOLVED`：判断表引用 `task.md`，目标产物包只包含 `spec.md`。本 run 通过原始 `task.md` 与 x-evals `PROMPT.md` 的相同哈希补齐审计链。
- `EVAL_SOURCE_PROVENANCE_MISSING`：原交付包缺少生成 session。attempt 2 已通过当日 Codex rollout 恢复，后续应在生成时直接持久化。

### 有效设计

- 对象删除后的子树与 Provenance 清理完整，并覆盖“删除后由更高来源重建”的隐蔽状态路径。
- 未知字段和类型错误覆盖低优先级错误被后续合法值覆盖的情况，能防止只校验最终值的实现。
- 确定性 Scenario 明确构造不同 map 插入顺序，补上上一份 x-spec3 pilot 的关键缺口。
- 输入不可变覆盖成功、错误、嵌套 map/slice 与 `nil Data`；并发 Scenario 共享同一 Schema 和 sources，和 race 门禁对齐。
- API、错误哨兵、JSON Pointer 转义、Config 原始键和五类动态类型均有可执行落点。

## Hidden harness 对齐

| 真实验收簇 | 规格状态 | 证据/缺口 |
|---|---|---|
| 标量覆盖 | 通过 | Scenario“高优先级覆盖普通字段” |
| 三层对象递归 | 弱覆盖 | 递归原则明确，具体三层测试数据缺失 |
| 数组整体替换 | 通过 | 高来源完整数组胜出，Provenance 指向高来源 |
| optional/required 删除 | 通过 | Config、子树 Provenance、`errors.Is` 均覆盖 |
| unknown/type | 通过 | 根级/嵌套、低来源被覆盖仍报错 |
| 调用期间输入不变 | 通过 | 成功/失败、嵌套容器、nil Data 深比较 |
| Result 所有权 | 缺口 | harness 当前也没有直接封闭返回后别名 |
| Provenance 与 Pointer | 通过 | 最终叶子、数组叶子、`~` 与 `/` 转义 |
| map 插入顺序 | 通过 | 有效结果与多错误输入均要求稳定 |
| 性能与 race | 通过 | 100 字段 × 10,000 次、共享输入并发 |

## Token 与耗时

Codex `input_tokens` 包含 cached input，`output_tokens` 包含 reasoning。统一口径如下：

```text
Input 64,438 + Output 10,575 + Reasoning 7,196
+ Cache Read 990,208 + Cache Write 0
= Total 1,072,417
```

| 阶段 | 非缓存 Token | Cache Read | 总 Token |
|---|---:|---:|---:|
| `x-spec3.spec` | 53,540 | 406,272 | 459,812 |
| `x-req3.task` | 13,432 | 191,488 | 204,920 |
| `source_validation_handoff` | 15,237 | 392,448 | 407,685 |
| 全流程 | **82,209** | **990,208** | **1,072,417** |

| 时间指标 | 实测 |
|---|---:|
| 会话开始（北京时间） | 2026-07-22 20:35:49 |
| 用户任务消息（北京时间） | 2026-07-22 20:36:14 |
| Prompt → spec 写入 | 245.305 秒 |
| Prompt → final | 373.992 秒 |
| task_started → task_complete | 374.056 秒 |
| session_meta → task_complete | 398.638 秒 |

其他实测：24 次 LLM 累计快照、23 次工具调用、工具失败 0、用户追加消息 0。一次预期的非零验证结果来自 spec 已生成、req 尚未生成时的 17 个未认领 Scenario，属于流程状态信号。

项目解析器 `tools/metrics.py:parse_codex_session_source` 返回 `session_meta.git.commit_hash 必须是非空字符串`，因为生成工作区没有 Git 元数据。本报告按 task complete 前最后一个累计 `token_count` 与 spec/req 写入边界直接计算。该限制记为 `CODEX_METRICS_NON_GIT_UNSUPPORTED`。

## 与受控 x-spec3 pilot 对比

| 指标 | 当前 sol5.6 | 受控 x-spec3 pilot | 变化 |
|---|---:|---:|---:|
| 任务语义 | 85/100 | 85/100 | 0 |
| 结构 | 8/8 | 8/8 | 0 |
| 全部断言 | 25/28 | 25/28 | 0 |
| Scenario | 17 | 14 | +3（+21.4%） |
| 行数 | 233 | 213 | +20 |
| 字节 | 14,602 | 16,557 | -1,955（-11.8%） |
| `wc -w` | 1,088 | 1,206 | -118（-9.8%） |
| spec 阶段总 Token | 459,812 | 331,824 | +127,988（+38.6%） |
| Prompt → spec | 245.305 秒 | 283.084 秒 | -37.779 秒（-13.3%） |

两份产物使用相同题面、rubric、模型和 spec 类型，可描述文档质量、体积和运行成本。当前 run 还读取 x-req3 并接触同题 hidden 失败记忆，受控 pilot 的上下文也与本 run 不同；这些差异使模型/skill 纯增益与盲测结论失效。

当前版本以更短文本承载更多 Scenario，质量分保持 85：它修复 assertion 18“不同 map 插入顺序”，同时丢失 assertion 16“空输入结果矩阵”；三层递归和 Result 所有权继续缺失。Scenario 数量适合作为描述指标，assertion 覆盖增量更适合作为优化指标。

### 可继续压缩的内容

- J1、J2、J6、J7、J9、J10 大量复述题面硬规则。判断表保留会改变实现的推断，题面事实改为短引用。
- “测试驱动开发”十一个步骤基本复述 Scenario 顺序。保留统一循环“Scenario → 失败测试 → 最小实现 → 重构回归”，另写风险优先顺序。
- “标准交付命令通过”与 Smoke 清单内容重复。命令集中在验收清单，Scenario 配额留给空输入或所有权边界。
- 任务目标与 Smoke 清单都重复性能、race、test、vet。目标保留可观察终态，命令细节集中在验收清单。

## 归因与知识

- 最早责任阶段：`spec`
- 发现阶段：`spec_quality_review`
- 产物 Reason codes：`SPEC_MISSING_THREE_LEVEL_EXAMPLE`、`SPEC_EMPTY_INPUT_MATRIX_MISSING`、`SPEC_RESULT_ALIAS_OWNERSHIP_MISSING`
- 评测 Reason codes：`EVAL_HIDDEN_MEMORY_CONTAMINATION`、`CODEX_METRICS_NON_GIT_UNSUPPORTED`、`EVAL_SOURCE_DISCOVERY_EXACT_MATCH_BLIND_SPOT`
- 知识条目：`pkn-20260722-configresolver-sol56-spec-eval-001`
- 固定回归 case：`configresolver-three-level-merge-and-provenance`、`configresolver-nil-empty-input-matrix`、`configresolver-result-alias-ownership`、`pipeline-run-source-telemetry-required`、`eval-same-task-memory-isolation`

来源搜索先按最终标题和当前文件路径匹配时没有命中；原文件已经移动或删除，标题在复制后被追加模型标签。按日期、工作区、prompt 和写入 patch 联合检索后恢复。后续生成阶段应直接保存 source session id；评测搜索应同时支持时间窗口、工作区、任务哈希和写入内容匹配。

## 下一门禁

在同一 attempt 的修订版完成以下四项，再重新评分：

1. 把对象递归 Scenario 改成至少三层的具体值与具体 Provenance，例如 default 提供 `app.server.tls.enabled=false`、`cert=a.pem`，environment 只覆盖 `enabled=true`。
2. 新增 nil/空 schema 与 nil/空 sources 结果矩阵，明确合法空结果与 required 缺失错误。
3. 新增 Result 所有权 Scenario：修改返回 Config 的嵌套 map/slice，再深比较输入快照。
4. 重新跑隔离同题 memory 的盲测，并由生成阶段直接保存 source session、模型、skill hash、Token、耗时与污染状态。

完成前三项后，当前 rubric 的预期分数为 100/100。第四项恢复模型与 skill 的可信因果比较。下一高成本阶段保持 `revise_spec`。

## 审计引用

- Manifest：`manifest.json`
- Events：`events.jsonl`
- Telemetry：`telemetry.json`
- Grading：`grading.json`
- 被评产物快照：`artifacts/configresolver-sol5.6-spec.md`
- Codex rollout：`/Users/kid/.codex/sessions/2026/07/22/rollout-2026-07-22T20-35-49-019f89d3-3a38-7572-8835-4a7c22bb5f36.jsonl`
