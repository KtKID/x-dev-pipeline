# MiniMax ConfigResolver：x-spec3 → x-req3 Pipeline Run 评审

## 判定

本次行为计为一次独立 pipeline run。

- `pipeline_run_id`：`prun-97e550db-df5c-4a1d-8824-4bf8cbc5a672-001`
- 外部执行来源：Mavis Session `mvs_97e550dbdf5c4a1d88244bf8cbc5a672`
- Run 类型：`evaluation`
- 阶段：`x-spec3.spec → x-req3.task → spec_quality_review`
- 执行结果：完成，三个文档成功落盘
- 质量门禁：失败，停在 dev 之前
- accepted delivery：0
- Token 归属：本次消耗计入 `evolution_eval_tokens`

一个用户任务对应一个 run；x-spec3 和 x-req3 是同一 run 内的两个 phase。Mavis Session 是执行器来源标识，pipeline_run_id 是跨执行器、报告、知识和后续阶段使用的统一审计标识。

## 产物

| Phase | 产物 | SHA-256 |
|---|---|---|
| x-spec3 | `/Volumes/machub_app/proj/x-dev-world/minimax/configresolver/docs/spec/config-resolver/spec.md` | `fb88f6251c3934f370dc3c0322b9533f0b03c8752edcabc31b576691e6117e00` |
| x-req3 | `/Volumes/machub_app/proj/x-dev-world/minimax/configresolver/docs/spec/config-resolver/tasks/config-resolver-impl/dev-checklist.md` | `5d89a29b70a8acfc98b343f566744dda054c514be93633b89c9c083ba16b464b` |
| x-req3 | `/Volumes/machub_app/proj/x-dev-world/minimax/configresolver/docs/spec/config-resolver/tasks/config-resolver-impl/diagram.md` | `0711644084d3eceb12c9a292179f833051feb4648e4a3383ae90af772d3b2e73` |

## 质量结果

| 指标 | 当前 MiniMax run | 受控 x-spec3 pilot | 差异 |
|---|---:|---:|---:|
| 任务语义 | 60/100（12/20） | 85/100（17/20） | -25 分 |
| 规格结构 | 6/8 | 8/8 | -2 |
| 合计断言 | 18/28 | 25/28 | -7 |
| Scenario | 14 | 14 | 0 |
| spec 字节 | 12,856 | 16,557 | -22.35% |

受控 pilot 与当前运行使用不同模型、不同执行器上下文；质量分采用相同任务和 rubric，Token 与耗时只作描述性观察。

### P0：阻止进入 dev

1. `nil-removes-field` 的 schema 只声明 `debug`，输入同时包含 `extra`，THEN 又要求成功保留 `extra`。任务契约要求该输入返回 `ErrUnknownField`。同一 Scenario 无法被实现同时满足。
2. 两个 Scenario 把输入整数 `80` 强制断言为 `float64(80)`。任务只定义 number 接受整数和浮点类型，未定义归一化；J7 也声明不强制单一数字类型。
3. spec 与 req 把 module root 固定到 `task-01-configresolver/` 子目录，开发清单继续传播该路径决定，形成交付根目录漂移风险。

### P1：隐藏边界缺口

- 递归对象只有两层例子，缺少三层嵌套。
- 确定性只比较同一 map 的重复调用，缺少不同插入顺序的逻辑等价 map。
- 不可变性与结果所有权没有显式覆盖 schema、嵌套数组和全部可变别名。
- 覆盖了 `Source.Data == nil`，缺少 nil/空 schema 与 nil/空 sources 结果矩阵。

### 有效设计

- 单文件 spec、目标/非目标、边界、判断依据、六元组覆盖、验收与 TDD 结构完整。
- Required 删除与全来源缺失均落到 `errors.Is(..., ErrRequiredRemoved)`。
- Race、性能、`go test`、`go vet` 与 E2E 省略依据均有明确落点。
- x-req3 保留 Scenario 名并生成了可执行顺序，说明 spec3 → req3 的结构交接有效；上游语义错误也被忠实传播。

## Token 与耗时

数据来自 `/Users/kid/.mavis/sqlite.db` 的 `sessions`、`session_messages`、`token_usage`，范围是该 Mavis root session；该 session 没有子 session。

| 指标 | 数值 |
|---|---:|
| 模型调用 | 16 |
| 输入 Token | 42,586 |
| 输出 Token | 8,281 |
| 推理 Token | 0 |
| Cache read Token | 626,811 |
| 非缓存读取总 Token | 50,867 |
| 含缓存读取总 Token | 677,678 |
| Cache read 占比 | 92.49% |
| 成本 | $0.06032166 |
| Prompt → final | 110.754 秒 |
| Session lifecycle | 121.836 秒 |
| 工具调用 | 20 |
| 工具失败 | 0 |
| 用户追加消息 | 0 |

### Phase Token

按首条 x-req3 规划消息 `session_messages.id=11990` 的时间戳机械切分。完整 session 总量是权威值，phase 值用于定位成本。

| Phase | LLM calls | 非缓存读取 Token | Cache read | 含缓存总量 | 成本 |
|---|---:|---:|---:|---:|---:|
| x-spec3.spec | 10 | 46,872 | 344,340 | 391,212 | $0.03943980 |
| x-req3.task | 6 | 3,995 | 282,471 | 286,466 | $0.02088186 |

缓存读取占完整用量的 92.49%。后续 Token 优化应优先检查 skill、模板和历史上下文的重复注入，同时保持正确性门禁优先。

## 后续门禁

当前文档应先修复三个 P0，再重跑同一 rubric。三层递归、map 插入顺序、深层所有权和 nil/空输入矩阵进入固定回归 case。通过规格质量门禁后，再执行 dev 与隐藏功能测试；最终实现结果决定该 run 是否进入 accepted 分母。

## 审计引用

- 结构化遥测：`telemetry.json`
- 结构化评分：`grading.json`
- 事件账本：`events.jsonl`
- 知识条目：`pipeline-data/knowledge/entries/pkn-20260722-minimax-configresolver-run-001.json`
